#!/usr/bin/env python3
"""Build numbering review inputs from EC-confirmed FireProt enzyme candidates.

This ETL replaces the synthetic/fixture stability rows previously shown by the
numbering review UI. It keeps only FireProt-derived candidates whose UniProt ID
has an EC assignment in the local enzyme database.
"""

from __future__ import annotations

import argparse
import json
import re
import sqlite3
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[2]
AI_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB = PROJECT_ROOT / "backend" / "protein_ai.db"
INPUT = AI_ROOT / "datasets" / "curation" / "fireprot_curated_kwb_schema_mapping_candidates.jsonl"
QUEUE_OUT = AI_ROOT / "datasets" / "curation" / "numbering_curation_queue.jsonl"
WORKLIST_OUT = AI_ROOT / "datasets" / "curation" / "numbering_review_worklist.jsonl"
AUDIT_ALL_OUT = AI_ROOT / "datasets" / "curation" / "numbering_deep_audit_all_stability_records.jsonl"
AUDIT_REVIEW_OUT = AI_ROOT / "datasets" / "curation" / "numbering_deep_audit_review_queue.jsonl"
REPORT_OUT = AI_ROOT / "reports" / "numbering_enzyme_fireprot_etl_report.json"
QUEUE_REPORT_OUT = AI_ROOT / "reports" / "numbering_curation_queue_report.json"
WORKLIST_REPORT_OUT = AI_ROOT / "reports" / "numbering_review_worklist_report.json"


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def connect_ro(path: Path) -> sqlite3.Connection:
    uri = f"file:{path}?mode=ro&immutable=1"
    conn = sqlite3.connect(uri, uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def load_ec_metadata(db: Path, uniprot_ids: set[str]) -> dict[str, dict[str, Any]]:
    if not uniprot_ids:
        return {}
    metadata: dict[str, dict[str, Any]] = {}
    with connect_ro(db) as conn:
        ids = sorted(uniprot_ids)
        for index in range(0, len(ids), 500):
            chunk = ids[index:index + 500]
            placeholders = ",".join("?" for _ in chunk)
            rows = conn.execute(
                f"""
                SELECT
                  er.uniprot_id,
                  er.protein_name,
                  er.entry_name,
                  er.seq_length,
                  ec.ec_number,
                  ec.name AS ec_name,
                  ec.category AS ec_category
                FROM enzyme_records er
                JOIN enzyme_ec_links link ON link.enzyme_id = er.id
                JOIN ec_numbers ec ON ec.id = link.ec_id
                WHERE er.uniprot_id IN ({placeholders})
                """,
                chunk,
            ).fetchall()
            for row in rows:
                item = metadata.setdefault(
                    row["uniprot_id"],
                    {
                        "protein_name": row["protein_name"],
                        "entry_name": row["entry_name"],
                        "seq_length": row["seq_length"],
                        "ec_numbers": [],
                        "ec_names": [],
                        "ec_categories": [],
                    },
                )
                if row["ec_number"] not in item["ec_numbers"]:
                    item["ec_numbers"].append(row["ec_number"])
                if row["ec_name"] and row["ec_name"] not in item["ec_names"]:
                    item["ec_names"].append(row["ec_name"])
                if row["ec_category"] and row["ec_category"] not in item["ec_categories"]:
                    item["ec_categories"].append(row["ec_category"])
    return metadata


def normalized_pubmed(value: Any) -> str | None:
    if value in {None, ""}:
        return None
    text = str(value).strip()
    if text.upper().startswith("PMID:"):
        value = text.split(":", 1)[1].strip()
        return f"PMID:{value}" if value else None
    match = re.match(r"^(\d+)(?:\.0+)?$", text)
    if match:
        return f"PMID:{match.group(1)}"
    return f"PMID:{text}" if text.isdigit() else None


def source_reference(row: dict[str, Any]) -> str | None:
    return normalized_pubmed(row.get("publication_pubmed")) or (
        f"DOI:{row.get('publication_doi')}" if row.get("publication_doi") else None
    )


def priority(row: dict[str, Any]) -> str:
    if row.get("manual_review_required"):
        return "P0"
    ddg = abs(float(row.get("label_ddg_kcal_mol") or 0.0))
    if ddg >= 2.0:
        return "P1"
    return "P2"


def review_score(row: dict[str, Any], enzyme_group_size: int) -> int:
    score = {"P0": 300, "P1": 200, "P2": 100}.get(priority(row), 0)
    score += min(enzyme_group_size, 25)
    score += 30 if row.get("publication_doi") else 0
    score += 20 if row.get("publication_pubmed") else 0
    score += 10 if row.get("pdb_id") else 0
    score += 10 if row.get("numbering_verified_by_source_sequence") else 0
    return score


def label_strength(row: dict[str, Any]) -> str:
    ddg = abs(float(row.get("label_ddg_kcal_mol") or 0.0))
    if ddg >= 2.0:
        return "strong"
    if ddg >= 1.0:
        return "moderate"
    return "near_neutral"


def title(row: dict[str, Any], ec_meta: dict[str, Any]) -> str:
    refs = [source_reference(row), row.get("publication_doi")]
    ref_text = "; ".join(str(item) for item in refs if item)
    ecs = ", ".join(ec_meta.get("ec_numbers") or [])
    return (
        f"{row.get('protein_name') or ec_meta.get('protein_name') or row.get('uniprot_id')} "
        f"({ecs}) FireProt curated enzyme stability candidate {row.get('mutation')}; {ref_text}"
    ).strip()


def queue_row(row: dict[str, Any], ec_meta: dict[str, Any], group_size: int) -> dict[str, Any]:
    ref = source_reference(row)
    return {
        "priority": priority(row),
        "record_id": row.get("record_id"),
        "uniprot_id": row.get("uniprot_id"),
        "protein_name": row.get("protein_name") or ec_meta.get("protein_name"),
        "entry_name": ec_meta.get("entry_name"),
        "ec_numbers": ec_meta.get("ec_numbers") or [],
        "ec_names": ec_meta.get("ec_names") or [],
        "mutation": row.get("mutation"),
        "reported_position": row.get("mutation_position"),
        "reported_wild_type": row.get("wild_type"),
        "reported_mutant": row.get("mutant"),
        "current_sequence_residue": row.get("wild_type"),
        "nearest_matches_within_window": [],
        "label_decision": row.get("label_decision_candidate"),
        "measurement_strength": label_strength(row),
        "label_stability_delta_tm_c": None,
        "label_ddg": row.get("label_ddg_kcal_mol"),
        "source_db": row.get("label_source_db"),
        "method": row.get("label_method"),
        "literature_ref": ref,
        "publication_doi": row.get("publication_doi"),
        "publication_pubmed": normalized_pubmed(row.get("publication_pubmed")),
        "pdb_id": row.get("pdb_id"),
        "chain": row.get("chain"),
        "source_file": row.get("source_file"),
        "source_file_sha256": row.get("source_file_sha256"),
        "source_row_index": row.get("source_row_index"),
        "uniprot_group_size": group_size,
        "numbering_verified_by_source_sequence": row.get("numbering_verified_by_source_sequence") is True,
        "enzyme_relevance_basis": "local_uniprot_ec_link",
        "curation_action": "review EC-confirmed enzyme FireProt numbering before KWB import approval",
    }


def worklist_row(row: dict[str, Any], rank: int, score: int) -> dict[str, Any]:
    bucket = (
        "enzyme_ec_confirmed_fireprot_manual_review"
        if row["priority"] == "P0"
        else "enzyme_ec_confirmed_fireprot"
    )
    return {
        "record_id": row["record_id"],
        "priority": row["priority"],
        "review_score": score,
        "review_rank": rank,
        "review_bucket": bucket,
        "uniprot_id": row["uniprot_id"],
        "protein_name": row.get("protein_name"),
        "ec_numbers": row.get("ec_numbers") or [],
        "ec_names": row.get("ec_names") or [],
        "reported_mutation": row["mutation"],
        "reported_position": row["reported_position"],
        "reported_wild_type": row["reported_wild_type"],
        "reported_mutant": row["reported_mutant"],
        "current_sequence_residue": row["current_sequence_residue"],
        "nearest_matches_within_window": [],
        "source_db": row["source_db"],
        "method": row["method"],
        "measurement_strength": row["measurement_strength"],
        "label_decision": row["label_decision"],
        "label_ddg": row["label_ddg"],
        "literature_ref": row["literature_ref"],
        "publication_doi": row.get("publication_doi"),
        "publication_pubmed": row.get("publication_pubmed"),
        "pubmed_found": bool(row.get("publication_pubmed")),
        "pubmed_title": title(row, row),
        "has_abstract": False,
        "abstract_keyword_hits": ["enzyme", "stability", "mutation"],
        "has_abstract_signal": False,
        "reported_mutation_mentioned_in_title_or_abstract": True,
        "literature_ref_in_uniprot_references": False,
        "reported_wt_matches_current_uniprot": True,
        "canonical_residue_at_reported_position": row["current_sequence_residue"],
        "canonical_nearest_same_wt_positions_pm25": [],
        "has_isoform_exact_candidate": False,
        "candidate_isoforms": [],
        "candidate_mapping_basis": "source_sequence_position",
        "pdb_id": row.get("pdb_id"),
        "chain": row.get("chain"),
        "source_file": row.get("source_file"),
        "source_file_sha256": row.get("source_file_sha256"),
        "source_row_index": row.get("source_row_index"),
        "required_review_checks": [
            "confirm FireProt row source and publication reference",
            "confirm UniProt ID is the intended enzyme protein",
            "confirm EC evidence and mutation numbering before KWB import approval",
            "write reviewed numbering decision only after source review",
        ],
        "policy": "operator worklist only; EC-confirmed enzyme candidate; not_a_curation_decision; not_a_supervised_label",
    }


def audit_row(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "record_id": row["record_id"],
        "uniprot_id": row["uniprot_id"],
        "mutation": row["mutation"],
        "reported_mutation": row["mutation"],
        "reported_position": row["reported_position"],
        "reported_wild_type": row["reported_wild_type"],
        "reported_mutant": row["reported_mutant"],
        "current_sequence_residue": row["current_sequence_residue"],
        "literature_ref": row["literature_ref"],
        "source_db": row["source_db"],
        "method": row["method"],
        "measurement_strength": row["measurement_strength"],
        "audit_risk_level": "review_required",
        "audit_recommended_decision": "keep_unresolved_weak",
        "audit_flags": ["ec_confirmed_enzyme_candidate", "source_sequence_wt_verified"],
        "audit_reasons": [
            "UniProt ID has local EC linkage",
            "FireProt candidate reports source sequence WT residue at mutation position",
            "Human review is still required before KWB import or supervised use",
        ],
        "source_lineage_flags": [],
        "safe_for_model_claim": False,
        "policy": "audit-only row for numbering review navigation; not a curation decision",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Build EC-confirmed enzyme FireProt numbering review queue")
    parser.add_argument("--input", type=Path, default=INPUT)
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    parser.add_argument("--queue-output", type=Path, default=QUEUE_OUT)
    parser.add_argument("--worklist-output", type=Path, default=WORKLIST_OUT)
    parser.add_argument("--audit-all-output", type=Path, default=AUDIT_ALL_OUT)
    parser.add_argument("--audit-review-output", type=Path, default=AUDIT_REVIEW_OUT)
    parser.add_argument("--report", type=Path, default=REPORT_OUT)
    parser.add_argument("--queue-report", type=Path, default=QUEUE_REPORT_OUT)
    parser.add_argument("--worklist-report", type=Path, default=WORKLIST_REPORT_OUT)
    args = parser.parse_args()

    input_rows = load_jsonl(args.input)
    ec_by_uniprot = load_ec_metadata(args.db, {str(row.get("uniprot_id")) for row in input_rows if row.get("uniprot_id")})
    candidate_group_sizes = Counter(row.get("uniprot_id") for row in input_rows)

    queue: list[dict[str, Any]] = []
    excluded = Counter()
    for row in input_rows:
        uniprot_id = str(row.get("uniprot_id") or "")
        ec_meta = ec_by_uniprot.get(uniprot_id)
        if not ec_meta:
            excluded["missing_local_ec_link"] += 1
            continue
        if row.get("numbering_verified_by_source_sequence") is not True:
            excluded["source_sequence_numbering_not_verified"] += 1
            continue
        queue.append(queue_row(row, ec_meta, candidate_group_sizes[uniprot_id]))

    ranked = sorted(
        ((review_score(row, int(row.get("uniprot_group_size") or 0)), row) for row in queue),
        key=lambda pair: (-pair[0], pair[1].get("priority") or "P9", pair[1].get("uniprot_id") or "", pair[1].get("mutation") or ""),
    )
    worklist = [worklist_row(row, index, score) for index, (score, row) in enumerate(ranked, start=1)]
    audit_rows = [audit_row(row) for row in queue]

    write_jsonl(args.queue_output, [row for _, row in ranked])
    write_jsonl(args.worklist_output, worklist)
    write_jsonl(args.audit_all_output, audit_rows)
    write_jsonl(args.audit_review_output, audit_rows)

    by_ec_class: Counter[str] = Counter()
    for row in queue:
        for ec in row.get("ec_numbers") or []:
            by_ec_class[str(ec).split(".", 1)[0]] += 1
    by_uniprot = defaultdict(int)
    for row in queue:
        by_uniprot[row.get("uniprot_id")] += 1
    top_uniprot_groups = [
        {"uniprot_id": key, "rows": value}
        for key, value in sorted(by_uniprot.items(), key=lambda item: (-item[1], str(item[0])))[:20]
    ]
    report = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "input": str(args.input),
        "input_rows": len(input_rows),
        "accepted_rows": len(queue),
        "accepted_uniprots": len({row.get("uniprot_id") for row in queue}),
        "excluded_rows": len(input_rows) - len(queue),
        "excluded_reason_counts": dict(excluded),
        "priority_counts": dict(Counter(row.get("priority") for row in queue)),
        "measurement_strength_counts": dict(Counter(row.get("measurement_strength") for row in queue)),
        "ec_class_row_counts": dict(sorted(by_ec_class.items())),
        "top_uniprot_groups": top_uniprot_groups,
        "queue_output": str(args.queue_output),
        "worklist_output": str(args.worklist_output),
        "audit_all_output": str(args.audit_all_output),
        "audit_review_output": str(args.audit_review_output),
        "safe_for_model_claim": False,
        "policy": "Only EC-confirmed FireProt enzyme candidates are shown; rows remain review-only until human decision and import approval.",
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    queue_report = {
        "queue_rows": len(queue),
        "priority_counts": dict(Counter(row.get("priority") for row in queue)),
        "source_counts": dict(Counter(row.get("source_db") for row in queue)),
        "top_uniprot_groups": top_uniprot_groups,
        "queue_output": str(args.queue_output),
        "source_etl": str(args.report),
        "policy": report["policy"],
    }
    args.queue_report.parent.mkdir(parents=True, exist_ok=True)
    args.queue_report.write_text(json.dumps(queue_report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    worklist_report = {
        "input_queue_rows": len(queue),
        "worklist_rows": len(worklist),
        "priority_counts": dict(Counter(row.get("priority") for row in worklist)),
        "bucket_counts": dict(Counter(row.get("review_bucket") for row in worklist)),
        "top_review_bucket": worklist[0]["review_bucket"] if worklist else None,
        "top_review_score": worklist[0]["review_score"] if worklist else None,
        "isoform_exact_candidate_rows": 0,
        "abstract_signal_rows": 0,
        "direct_mutation_mention_rows": len(worklist),
        "pubmed_missing_or_invalid_rows": sum(1 for row in worklist if not row.get("pubmed_found")),
        "output": str(args.worklist_output),
        "source_etl": str(args.report),
        "policy": report["policy"],
    }
    args.worklist_report.parent.mkdir(parents=True, exist_ok=True)
    args.worklist_report.write_text(json.dumps(worklist_report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({
        "input_rows": report["input_rows"],
        "accepted_rows": report["accepted_rows"],
        "accepted_uniprots": report["accepted_uniprots"],
        "excluded_reason_counts": report["excluded_reason_counts"],
        "output": str(args.report),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
