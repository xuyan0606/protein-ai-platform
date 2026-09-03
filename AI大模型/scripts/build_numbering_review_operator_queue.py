#!/usr/bin/env python3
"""Build a full operator queue for numbering review.

This report is navigation-only. It helps a human decide which numbering row to
review next, but it does not write reviewed decisions or promote weak labels.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
WORKLIST = AI_ROOT / "datasets" / "curation" / "numbering_review_worklist.jsonl"
DEEP_AUDIT = AI_ROOT / "datasets" / "curation" / "numbering_deep_audit_review_queue.jsonl"
DECISIONS = AI_ROOT / "datasets" / "curation" / "numbering_curation_decisions.jsonl"
SEMANTIC_CONFLICTS = AI_ROOT / "datasets" / "curation" / "numbering_decision_semantic_conflict_queue.jsonl"
PACKET_DIR = AI_ROOT / "datasets" / "curation" / "numbering_review_packets"
OUT_JSON = AI_ROOT / "reports" / "numbering_review_operator_queue.json"
OUT_MD = AI_ROOT / "reports" / "numbering_review_operator_queue.md"


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def packet_by_record(packet_dir: Path) -> dict[str, str]:
    mapping: dict[str, str] = {}
    for path in sorted(packet_dir.glob("*.jsonl")):
        packet_id = path.stem
        for row in load_jsonl(path):
            record_id = str(row.get("record_id") or "")
            if record_id:
                mapping[record_id] = packet_id
    return mapping


def title_flag(row: dict[str, Any]) -> str:
    title = (row.get("pubmed_title") or "").lower()
    mutation = (row.get("reported_mutation") or row.get("mutation") or "").lower()
    protein_words = {"protein", "enzyme", "mutation", "mutant", "residue", "amino acid", "stability"}
    if mutation and mutation in title.replace(" ", ""):
        return "title_mentions_mutation"
    if any(word in title for word in protein_words):
        return "title_has_broad_protein_signal"
    if row.get("pubmed_found"):
        return "title_mismatch_risk"
    return "pubmed_missing_or_invalid"


def source_lineage_group(audit: dict[str, Any]) -> str:
    flags = set(audit.get("source_lineage_flags") or [])
    if "synthetic_generator_fingerprint_prothermdb_pmid_310xxxxx" in flags:
        return "generated_source_fingerprint"
    if "sample_fixture_literal_pmid" in flags:
        return "fixture_or_sample_source"
    return "source_lineage_needs_review"


def plain_next_action(status: str, audit: dict[str, Any]) -> str:
    if status == "semantic_conflict":
        return "先处理意见/字段冲突：按意见改 reject，或重写意见确认只保留 weak。"
    if audit.get("audit_recommended_decision") == "reject_label":
        return "深度审计建议 reject：除非能补独立真实来源回执，否则人工确认后应拒绝该标签。"
    return "逐项核实蛋白、突变、编号体系、WT 残基和实验来源；证据不足则保持 weak。"


def operator_sort_key(row: dict[str, Any]) -> tuple[int, int]:
    status_order = {
        "semantic_conflict": 0,
        "todo": 1,
        "reviewed_no_conflict": 2,
    }
    return (
        status_order.get(str(row.get("operator_status")), 9),
        int(row.get("review_rank") or 999999),
    )


def build_rows(
    worklist: list[dict[str, Any]],
    deep_audit: list[dict[str, Any]],
    decisions: list[dict[str, Any]],
    conflicts: list[dict[str, Any]],
    packets: dict[str, str],
) -> list[dict[str, Any]]:
    audit_by_id = {str(row.get("record_id")): row for row in deep_audit if row.get("record_id")}
    decision_by_id = {str(row.get("record_id")): row for row in decisions if row.get("record_id")}
    conflict_by_id = {str(row.get("record_id")): row for row in conflicts if row.get("record_id")}
    rows: list[dict[str, Any]] = []
    for source in worklist:
        record_id = str(source.get("record_id") or "")
        audit = audit_by_id.get(record_id, {})
        decision = decision_by_id.get(record_id)
        conflict = conflict_by_id.get(record_id)
        status = "semantic_conflict" if conflict else ("reviewed_no_conflict" if decision else "todo")
        merged = {**source, **audit}
        mutation = merged.get("reported_mutation") or merged.get("mutation")
        row = {
            "operator_order": 0,
            "operator_status": status,
            "record_id": record_id,
            "priority": source.get("priority") or audit.get("queue_priority"),
            "review_rank": source.get("review_rank"),
            "review_bucket": source.get("review_bucket"),
            "packet_id": packets.get(record_id) or source.get("review_bucket") or "unassigned_packet",
            "uniprot_id": merged.get("uniprot_id"),
            "mutation": mutation,
            "reported_mutation": mutation,
            "reported_position": merged.get("reported_position"),
            "reported_wild_type": merged.get("reported_wild_type"),
            "reported_mutant": merged.get("reported_mutant"),
            "current_residue": merged.get("current_sequence_residue"),
            "current_sequence_residue": merged.get("current_sequence_residue"),
            "candidate_isoforms": merged.get("candidate_isoforms") or [],
            "pmid": merged.get("literature_ref"),
            "literature_ref": merged.get("literature_ref"),
            "notes": merged.get("pubmed_title"),
            "title_flag": title_flag(merged),
            "source_db": merged.get("source_db"),
            "method": merged.get("method"),
            "measurement_strength": merged.get("measurement_strength") or merged.get("queue_measurement_strength"),
            "source_lineage_group": source_lineage_group(audit),
            "audit_risk_level": audit.get("audit_risk_level"),
            "audit_recommended_decision": audit.get("audit_recommended_decision"),
            "audit_flags": audit.get("audit_flags") or [],
            "audit_reasons": audit.get("audit_reasons") or [],
            "operator_next_action": plain_next_action(status, audit),
            "existing_decision": decision,
            "semantic_conflict": conflict,
            "safe_for_model_claim": False,
            "policy": "operator navigation only; not_a_curation_decision; not_a_supervised_label",
        }
        rows.append(row)
    rows.sort(key=operator_sort_key)
    for index, row in enumerate(rows, start=1):
        row["operator_order"] = index
    return rows


def write_markdown(report: dict[str, Any], rows: list[dict[str, Any]], path: Path) -> None:
    lines = [
        "# Numbering Review Operator Queue",
        "",
        f"Generated: {report['created_at']}",
        "",
        "Navigation only. These rows are not reviewed decisions and must not be used as supervised labels.",
        "",
        "## Summary",
        "",
        f"- Queue rows: {report['queue_rows']}",
        f"- Open numbering rows: {report['open_numbering_rows']}",
        f"- Semantic conflict rows: {report['semantic_conflict_rows']}",
        f"- Deep-audit reject recommendations: {report['deep_audit_reject_recommendation_rows']}",
        "",
        "## First 50 Rows",
        "",
        "| order | status | record_id | packet | UniProt | mutation | PMID | action |",
        "|---:|---|---|---|---|---|---|---|",
    ]
    for row in rows[:50]:
        lines.append(
            "| {operator_order} | {operator_status} | {record_id} | {packet_id} | {uniprot_id} | {mutation} | {pmid} | {operator_next_action} |".format(
                **row
            )
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Build full numbering operator review queue")
    parser.add_argument("--worklist", type=Path, default=WORKLIST)
    parser.add_argument("--deep-audit", type=Path, default=DEEP_AUDIT)
    parser.add_argument("--decisions", type=Path, default=DECISIONS)
    parser.add_argument("--semantic-conflicts", type=Path, default=SEMANTIC_CONFLICTS)
    parser.add_argument("--packet-dir", type=Path, default=PACKET_DIR)
    parser.add_argument("--out-json", type=Path, default=OUT_JSON)
    parser.add_argument("--out-md", type=Path, default=OUT_MD)
    args = parser.parse_args()

    worklist = load_jsonl(args.worklist)
    deep_audit = load_jsonl(args.deep_audit)
    decisions = load_jsonl(args.decisions)
    conflicts = load_jsonl(args.semantic_conflicts)
    rows = build_rows(worklist, deep_audit, decisions, conflicts, packet_by_record(args.packet_dir))
    status_counts = Counter(str(row.get("operator_status")) for row in rows)
    report = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "local_only": True,
        "queue_rows": len(rows),
        "decision_rows": len(decisions),
        "open_numbering_rows": status_counts.get("todo", 0),
        "reviewed_no_conflict_rows": status_counts.get("reviewed_no_conflict", 0),
        "semantic_conflict_rows": status_counts.get("semantic_conflict", 0),
        "operator_status_counts": dict(status_counts),
        "review_bucket_counts": dict(Counter(str(row.get("review_bucket")) for row in rows)),
        "source_lineage_group_counts": dict(Counter(str(row.get("source_lineage_group")) for row in rows)),
        "deep_audit_reject_recommendation_rows": sum(
            1 for row in rows if row.get("audit_recommended_decision") == "reject_label"
        ),
        "rows": rows,
        "top_items": rows[:25],
        "safe_for_model_claim": False,
        "release_ready": False,
        "policy": "Navigation-only queue. Explicit human decisions are still required in numbering_curation_decisions.jsonl.",
    }
    args.out_json.parent.mkdir(parents=True, exist_ok=True)
    args.out_json.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    write_markdown(report, rows, args.out_md)
    print(json.dumps({
        "queue_rows": report["queue_rows"],
        "open_numbering_rows": report["open_numbering_rows"],
        "semantic_conflict_rows": report["semantic_conflict_rows"],
        "output_json": str(args.out_json),
        "output_md": str(args.out_md),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
