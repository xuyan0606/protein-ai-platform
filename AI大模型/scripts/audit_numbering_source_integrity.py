#!/usr/bin/env python3
"""Independently audit numbering labels, source lineage, and physics direction.

This audit is deliberately stricter than the normal numbering validator. It
does not modify reviewed decisions, repaired labels, or training tables.
"""

from __future__ import annotations

import argparse
import json
import re
import sqlite3
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[2]
AI_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB = PROJECT_ROOT / "backend" / "protein_ai.db"
QUEUE = AI_ROOT / "datasets" / "curation" / "numbering_curation_queue.jsonl"
UNIPROT = AI_ROOT / "datasets" / "curation" / "numbering_uniprot_evidence.jsonl"
ISOFORMS = AI_ROOT / "datasets" / "curation" / "numbering_isoform_review_candidates.jsonl"
PUBMED = AI_ROOT / "datasets" / "curation" / "numbering_pubmed_abstract_evidence.jsonl"
DECISIONS = AI_ROOT / "datasets" / "curation" / "numbering_curation_decisions.jsonl"
ALL_OUT = AI_ROOT / "datasets" / "curation" / "numbering_deep_audit_all_stability_records.jsonl"
QUEUE_OUT = AI_ROOT / "datasets" / "curation" / "numbering_deep_audit_review_queue.jsonl"
REPORT_OUT = AI_ROOT / "reports" / "numbering_deep_audit_report.json"
MARKDOWN_OUT = AI_ROOT / "reports" / "numbering_deep_audit_report.md"

SYNTHETIC_PMID_RE = re.compile(r"^PMID:310[0-9]{5}$")
FIXTURE_PMIDS = {
    "PMID:12345678",
    "PMID:23456789",
    "PMID:34567890",
    "PMID:45678901",
    "PMID:56789012",
    "PMID:67890123",
    "PMID:78901234",
}
REJECTION_NOTE_TOKENS = (
    "\u62d2\u7edd",
    "\u9519\u8bef",
    "\u4e0d\u80fd\u652f\u6301",
    "\u9519\u914d",
    "\u4e0d\u5339\u914d",
)


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )


def connect_ro(path: Path) -> sqlite3.Connection:
    uri = f"file:{path}?mode=ro&immutable=1"
    conn = sqlite3.connect(uri, uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def by_record(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {str(row["record_id"]): row for row in rows if row.get("record_id")}


def load_stability_records(db_path: Path) -> list[dict[str, Any]]:
    with connect_ro(db_path) as conn:
        rows = conn.execute(
            """
            SELECT
              s.id,
              e.uniprot_id,
              e.sequence,
              e.seq_length,
              s.source_db,
              s.mutation,
              s.mutation_pos,
              s.wild_type,
              s.mutant,
              s.ddg,
              s.dtm,
              s.ph,
              s.temperature_c,
              s.method,
              s.literature_ref
            FROM stability_records s
            JOIN enzyme_records e ON e.id = s.enzyme_id
            ORDER BY s.id
            """
        ).fetchall()
    return [dict(row) for row in rows]


def source_lineage_flags(record: dict[str, Any]) -> list[str]:
    source_db = str(record.get("source_db") or "")
    literature_ref = str(record.get("literature_ref") or "")
    flags: list[str] = []
    if source_db == "ProThermDB" and SYNTHETIC_PMID_RE.match(literature_ref):
        flags.append("synthetic_generator_fingerprint_prothermdb_pmid_310xxxxx")
    if source_db.lower() == "protherm" and literature_ref in FIXTURE_PMIDS:
        flags.append("sample_fixture_literal_pmid")
    if not literature_ref:
        flags.append("missing_literature_reference")
    return flags


def sequence_flags(record: dict[str, Any]) -> tuple[list[str], str | None]:
    flags: list[str] = []
    sequence = str(record.get("sequence") or "")
    position = int(record.get("mutation_pos") or 0)
    reported_wt = str(record.get("wild_type") or "").upper()
    reported_mutant = str(record.get("mutant") or "").upper()
    mutation = str(record.get("mutation") or "").upper()
    expected_mutation = f"{reported_wt}{position}{reported_mutant}"
    current_residue = None
    if mutation != expected_mutation:
        flags.append("mutation_code_disagrees_with_structured_fields")
    if position < 1 or position > len(sequence):
        flags.append("position_out_of_current_uniprot_sequence_range")
    else:
        current_residue = sequence[position - 1].upper()
        if current_residue != reported_wt:
            flags.append("reported_wild_type_mismatch_current_uniprot")
    return flags, current_residue


def physics_flags(record: dict[str, Any]) -> list[str]:
    ddg = record.get("ddg")
    dtm = record.get("dtm")
    if not isinstance(ddg, (int, float)) or not isinstance(dtm, (int, float)):
        return []
    # KWB convention: negative ddG is stabilizing while positive dTm is stabilizing.
    if float(ddg) * float(dtm) > 0:
        return ["ddg_dtm_direction_conflict_under_kwb_convention"]
    return []


def literature_flags(
    uniprot: dict[str, Any] | None,
    pubmed: dict[str, Any] | None,
    has_isoform_exact_candidate: bool,
) -> list[str]:
    flags: list[str] = []
    if pubmed is None:
        flags.append("pubmed_evidence_not_available_for_record")
    elif not pubmed.get("pubmed_found"):
        flags.append("pmid_not_found_in_pubmed")
    else:
        if not pubmed.get("reported_mutation_mentioned_in_title_or_abstract"):
            flags.append("mutation_not_mentioned_in_pubmed_title_or_abstract")
        if not (uniprot or {}).get("literature_ref_in_uniprot_references"):
            flags.append("pmid_not_linked_from_current_uniprot_references")
        if not (pubmed.get("title") or "").strip():
            flags.append("pubmed_title_missing")
    if has_isoform_exact_candidate:
        flags.append("isoform_residue_match_is_not_source_provenance")
    return flags


def decision_flags(decision: dict[str, Any] | None) -> list[str]:
    if not decision:
        return []
    notes = str(decision.get("notes") or "")
    if decision.get("decision") == "keep_unresolved_weak" and any(token in notes for token in REJECTION_NOTE_TOKENS):
        return ["human_decision_text_rejects_label_but_machine_decision_keeps_weak"]
    return []


def audit_record(
    record: dict[str, Any],
    uniprot: dict[str, Any] | None,
    pubmed: dict[str, Any] | None,
    isoform: dict[str, Any] | None,
    decision: dict[str, Any] | None,
) -> dict[str, Any]:
    record_id = f"stability:{record['id']}"
    lineage = source_lineage_flags(record)
    sequence, current_residue = sequence_flags(record)
    physics = physics_flags(record)
    literature = literature_flags(uniprot, pubmed, bool(isoform))
    reviewed = decision_flags(decision)
    flags = sorted(set(lineage + sequence + physics + literature + reviewed))
    generated_or_fixture = any(
        flag in {
            "synthetic_generator_fingerprint_prothermdb_pmid_310xxxxx",
            "sample_fixture_literal_pmid",
        }
        for flag in lineage
    )
    recommendation = "reject_label" if generated_or_fixture else "keep_unresolved_weak"
    reasons = []
    if generated_or_fixture:
        reasons.append("source_lineage_is_generated_or_fixture_data")
    if "reported_wild_type_mismatch_current_uniprot" in flags:
        reasons.append("reported_wt_does_not_match_current_sequence")
    if "ddg_dtm_direction_conflict_under_kwb_convention" in flags:
        reasons.append("ddg_and_dtm_do_not_share_kwb_stability_direction")
    if "mutation_not_mentioned_in_pubmed_title_or_abstract" in flags:
        reasons.append("pubmed_does_not_mention_reported_mutation")
    if "pmid_not_linked_from_current_uniprot_references" in flags:
        reasons.append("uniprot_does_not_link_the_pmid")
    if decision:
        reasons.append("existing_human_decision_present")
    return {
        "record_id": record_id,
        "uniprot_id": record.get("uniprot_id"),
        "mutation": record.get("mutation"),
        "reported_position": record.get("mutation_pos"),
        "reported_wild_type": record.get("wild_type"),
        "reported_mutant": record.get("mutant"),
        "current_sequence_residue": current_residue,
        "source_db": record.get("source_db"),
        "literature_ref": record.get("literature_ref"),
        "method": record.get("method"),
        "ddg": record.get("ddg"),
        "dtm": record.get("dtm"),
        "source_lineage_flags": lineage,
        "sequence_flags": sequence,
        "physics_flags": physics,
        "literature_flags": literature,
        "existing_decision_flags": reviewed,
        "audit_flags": flags,
        "audit_recommended_decision": recommendation,
        "audit_risk_level": "critical" if generated_or_fixture else "high",
        "audit_reasons": reasons,
        "pubmed_found": pubmed.get("pubmed_found") if pubmed else None,
        "pubmed_title": pubmed.get("title") if pubmed else None,
        "reported_mutation_mentioned_in_title_or_abstract": (
            pubmed.get("reported_mutation_mentioned_in_title_or_abstract") if pubmed else None
        ),
        "literature_ref_in_uniprot_references": (
            uniprot.get("literature_ref_in_uniprot_references") if uniprot else None
        ),
        "candidate_isoforms": (isoform or {}).get("candidate_isoforms") or [],
        "has_isoform_exact_candidate": bool(isoform),
        "existing_decision": decision,
        "policy": (
            "Deep audit only. Do not auto-apply this recommendation or modify "
            "numbering_curation_decisions.jsonl, repaired labels, or training tables."
        ),
    }


def write_markdown(report: dict[str, Any], path: Path) -> None:
    lines = [
        "# Numbering Deep Audit",
        "",
        "This report is an independent, fail-closed audit. It does not change human decisions or labels.",
        "",
        "## Result",
        "",
        f"- Stability records checked: {report['stability_records_checked']}",
        f"- Numbering review queue rows checked: {report['numbering_queue_rows_checked']}",
        f"- Generated-source fingerprint rows: {report['generated_source_fingerprint_rows']}",
        f"- Fixture-source rows: {report['fixture_source_rows']}",
        f"- Current UniProt WT mismatches: {report['current_uniprot_wt_mismatch_rows']}",
        f"- ddG/dTm direction conflicts under KWB convention: {report['ddg_dtm_direction_conflict_rows']}",
        f"- Existing decision semantic conflicts: {report['existing_decision_semantic_conflict_rows']}",
        f"- Rows recommended for reject_label: {report['recommended_reject_label_rows']}",
        "",
        "## Audit Rules",
        "",
        "1. A generated-source or fixture fingerprint is not a real ProThermDB receipt.",
        "2. An isoform residue coincidence cannot repair an unsupported literature/source join.",
        "3. Under KWB convention, negative ddG and positive dTm both indicate stabilization; same-sign values are flagged for direction conflict.",
        "4. A human decision whose text says reject but whose machine decision is keep_unresolved_weak is flagged for explicit human resolution.",
        "",
        "## Boundary",
        "",
        "- No decisions were changed.",
        "- No labels were promoted or rejected automatically.",
        "- safe_for_model_claim remains false.",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Deep audit numbering/source integrity")
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    parser.add_argument("--queue", type=Path, default=QUEUE)
    parser.add_argument("--uniprot", type=Path, default=UNIPROT)
    parser.add_argument("--isoforms", type=Path, default=ISOFORMS)
    parser.add_argument("--pubmed", type=Path, default=PUBMED)
    parser.add_argument("--decisions", type=Path, default=DECISIONS)
    parser.add_argument("--all-output", type=Path, default=ALL_OUT)
    parser.add_argument("--queue-output", type=Path, default=QUEUE_OUT)
    parser.add_argument("--report", type=Path, default=REPORT_OUT)
    parser.add_argument("--markdown", type=Path, default=MARKDOWN_OUT)
    args = parser.parse_args()

    queue_rows = load_jsonl(args.queue)
    queue_by_id = by_record(queue_rows)
    uniprot_by_id = by_record(load_jsonl(args.uniprot))
    isoform_by_id = by_record(load_jsonl(args.isoforms))
    pubmed_by_id = by_record(load_jsonl(args.pubmed))
    decision_by_id = by_record(load_jsonl(args.decisions))
    audited = [
        audit_record(
            record,
            uniprot_by_id.get(f"stability:{record['id']}"),
            pubmed_by_id.get(f"stability:{record['id']}"),
            isoform_by_id.get(f"stability:{record['id']}"),
            decision_by_id.get(f"stability:{record['id']}"),
        )
        for record in load_stability_records(args.db)
    ]
    queue_audited = [
        {
            **row,
            "queue_priority": queue_by_id[row["record_id"]].get("priority"),
            "queue_measurement_strength": queue_by_id[row["record_id"]].get("measurement_strength"),
            "queue_review_action": "do_not_map_generated_or_fixture_source",
        }
        for row in audited
        if row["record_id"] in queue_by_id
    ]
    queue_audited.sort(key=lambda row: (row.get("queue_priority") or "P9", row["record_id"]))
    flag_counts = Counter(flag for row in audited for flag in row["audit_flags"])
    lineage_counts = Counter(
        flag for row in audited for flag in row["source_lineage_flags"]
    )
    report = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "local_only": True,
        "stability_records_checked": len(audited),
        "numbering_queue_rows_checked": len(queue_audited),
        "generated_source_fingerprint_rows": sum(
            "synthetic_generator_fingerprint_prothermdb_pmid_310xxxxx" in row["source_lineage_flags"]
            for row in audited
        ),
        "fixture_source_rows": sum(
            "sample_fixture_literal_pmid" in row["source_lineage_flags"] for row in audited
        ),
        "current_uniprot_wt_mismatch_rows": sum(
            "reported_wild_type_mismatch_current_uniprot" in row["sequence_flags"] for row in audited
        ),
        "current_uniprot_wt_match_rows": sum(not row["sequence_flags"] for row in audited),
        "ddg_dtm_direction_conflict_rows": sum(
            "ddg_dtm_direction_conflict_under_kwb_convention" in row["physics_flags"] for row in audited
        ),
        "pubmed_evidence_rows_available": sum(row["pubmed_found"] is not None for row in audited),
        "pubmed_found_rows": sum(row["pubmed_found"] is True for row in audited),
        "mutation_mentioned_in_pubmed_rows": sum(
            row["reported_mutation_mentioned_in_title_or_abstract"] is True for row in audited
        ),
        "uniprot_reference_linked_rows": sum(
            row["literature_ref_in_uniprot_references"] is True for row in audited
        ),
        "isoform_exact_candidate_rows": sum(row["has_isoform_exact_candidate"] for row in audited),
        "existing_decision_rows": len(decision_by_id),
        "existing_decision_semantic_conflict_rows": sum(
            bool(row["existing_decision_flags"]) for row in audited
        ),
        "recommended_reject_label_rows": sum(
            row["audit_recommended_decision"] == "reject_label" for row in audited
        ),
        "audit_flag_counts": dict(sorted(flag_counts.items())),
        "source_lineage_flag_counts": dict(sorted(lineage_counts.items())),
        "safe_to_map_any_record": False,
        "safe_for_model_claim": False,
        "hard_gate_status": "blocked_generated_or_fixture_stability_source",
        "all_records_output": str(args.all_output),
        "review_queue_output": str(args.queue_output),
        "policy": (
            "The current local stability_records table is generated or fixture data. "
            "It may support engineering smoke tests only and must not be repaired "
            "into claim-eligible supervised labels from numbering evidence."
        ),
    }
    write_jsonl(args.all_output, audited)
    write_jsonl(args.queue_output, queue_audited)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    write_markdown(report, args.markdown)
    print(json.dumps({
        "stability_records_checked": report["stability_records_checked"],
        "numbering_queue_rows_checked": report["numbering_queue_rows_checked"],
        "generated_source_fingerprint_rows": report["generated_source_fingerprint_rows"],
        "fixture_source_rows": report["fixture_source_rows"],
        "recommended_reject_label_rows": report["recommended_reject_label_rows"],
        "safe_for_model_claim": report["safe_for_model_claim"],
        "output": str(args.report),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
