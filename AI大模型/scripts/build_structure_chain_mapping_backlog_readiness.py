#!/usr/bin/env python3
"""Build an audit-only readiness view for the remaining structure-chain backlog."""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
WORKLIST = AI_ROOT / "datasets" / "curation" / "structure_chain_mapping_worklist.jsonl"
DECISIONS = AI_ROOT / "datasets" / "curation" / "structure_chain_mapping_decisions.jsonl"
EVIDENCE_AUDIT = AI_ROOT / "datasets" / "curation" / "structure_chain_evidence_audit.jsonl"
DBREF_AUDIT = AI_ROOT / "datasets" / "curation" / "structure_chain_dbref_evidence_audit.jsonl"
PACKETS_DIR = AI_ROOT / "datasets" / "curation" / "structure_chain_review_packets"
VALIDATION_REPORT = AI_ROOT / "reports" / "structure_chain_mapping_decision_validation_report.json"
APPLY_REPORT = AI_ROOT / "reports" / "structure_chain_mapping_apply_report.json"
REPORT_OUT = AI_ROOT / "reports" / "structure_chain_mapping_backlog_readiness_report.json"
MD_OUT = AI_ROOT / "reports" / "structure_chain_mapping_backlog_readiness.md"


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def normalize_structure_id(value: Any) -> str:
    return str(value or "").strip().upper()


def rel(path: Path | str | None) -> str | None:
    if not path:
        return None
    value = Path(path)
    try:
        return str(value.relative_to(AI_ROOT)) if value.is_absolute() else str(value)
    except ValueError:
        return str(value)


def build_packet_index(packets_dir: Path) -> dict[str, str]:
    index: dict[str, str] = {}
    if not packets_dir.exists():
        return index
    for packet_path in sorted(packets_dir.glob("*.jsonl")):
        packet_id = packet_path.stem
        for row in load_jsonl(packet_path):
            structure_id = normalize_structure_id(row.get("structure_id"))
            if structure_id:
                index[structure_id] = packet_id
    return index


def strict_evidence_by_structure(*audit_rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    strict: dict[str, dict[str, Any]] = {}
    for rows in audit_rows:
        for row in rows:
            if not row.get("strict_auto_promotable_for_chain_mapping"):
                continue
            structure_id = normalize_structure_id(row.get("structure_id"))
            if not structure_id:
                continue
            source = "dbref_interval" if row.get("dbref") else "pdb_seqadv_remark465"
            existing = strict.get(structure_id, {})
            sources = sorted(set(existing.get("strict_evidence_sources") or []) | {source})
            strict[structure_id] = {
                "structure_id": structure_id,
                "canonical_uniprot_id": row.get("canonical_uniprot_id"),
                "selected_chain_id": row.get("selected_chain_id"),
                "strict_evidence_sources": sources,
                "difference_rows": row.get("difference_rows"),
                "explained_difference_rows": row.get("explained_difference_rows"),
                "unexplained_difference_rows": row.get("unexplained_difference_rows"),
                "source_refs": row.get("source_refs") or [],
            }
    return strict


def evidence_tier(row: dict[str, Any], strict_ids: set[str]) -> str:
    structure_id = normalize_structure_id(row.get("structure_id"))
    if structure_id in strict_ids:
        return "strict_evidence_ready_for_human_decision"
    if row.get("review_bucket") == "single_chain_ca_length_close" and row.get("is_reviewed_uniprot"):
        return "single_chain_reviewed_uniprot_length_close"
    if row.get("review_bucket") == "multi_chain_needs_selection":
        return "multi_chain_selection_required"
    return "manual_review_required"


def top_queue_rows(
    remaining_rows: list[dict[str, Any]],
    strict_by_id: dict[str, dict[str, Any]],
    packet_by_id: dict[str, str],
    limit: int,
) -> list[dict[str, Any]]:
    strict_ids = set(strict_by_id)
    tier_order = {
        "strict_evidence_ready_for_human_decision": 0,
        "single_chain_reviewed_uniprot_length_close": 1,
        "multi_chain_selection_required": 2,
        "manual_review_required": 3,
    }
    sorted_rows = sorted(
        remaining_rows,
        key=lambda row: (
            tier_order.get(evidence_tier(row, strict_ids), 9),
            int(row.get("review_rank") or 999999),
            normalize_structure_id(row.get("structure_id")),
        ),
    )
    queue = []
    for row in sorted_rows[:limit]:
        structure_id = normalize_structure_id(row.get("structure_id"))
        strict = strict_by_id.get(structure_id, {})
        queue.append({
            "structure_id": structure_id,
            "canonical_uniprot_id": row.get("uniprot_id"),
            "protein_name": row.get("protein_name"),
            "review_rank": row.get("review_rank"),
            "review_bucket": row.get("review_bucket"),
            "evidence_tier": evidence_tier(row, strict_ids),
            "packet_id": packet_by_id.get(structure_id),
            "suggested_selected_chain_id": strict.get("selected_chain_id") or ((row.get("db_chain_ids") or [None])[0]),
            "strict_evidence_sources": strict.get("strict_evidence_sources") or [],
            "chain_count": row.get("chain_count"),
            "parsed_chain_ids": row.get("parsed_chain_ids") or [],
            "db_chain_ids": row.get("db_chain_ids") or [],
            "resolution": row.get("resolution"),
            "required_human_checks": row.get("required_review_checks") or [],
            "decision_input": "datasets/curation/structure_chain_mapping_decisions.jsonl",
            "policy": "review priority only; not a reviewed chain mapping decision",
        })
    return queue


def write_markdown(path: Path, report: dict[str, Any]) -> None:
    lines = [
        "# Structure Chain Mapping Backlog Readiness",
        "",
        "This report is audit-only. It does not write reviewed decisions and cannot unlock model-quality claims.",
        "",
        "## Summary",
        "",
        f"- Worklist rows: {report['worklist_rows']}",
        f"- Reviewed decision rows: {report['decision_rows']}",
        f"- Reviewed usable rows: {report['usable_for_coordinate_features']}",
        f"- Remaining unreviewed rows: {report['remaining_unreviewed_rows']}",
        f"- Strict evidence rows still awaiting human decision: {report['strict_evidence_remaining_rows']}",
        f"- Completion ready: {str(report['completion_ready']).lower()}",
        f"- Safe for model claim: {str(report['safe_for_model_claim']).lower()}",
        "",
        "## Remaining By Evidence Tier",
        "",
    ]
    for key, value in report["remaining_by_evidence_tier"].items():
        lines.append(f"- {key}: {value}")
    lines.extend(["", "## Next Review Queue", ""])
    for row in report["next_review_queue"]:
        lines.append(
            f"- {row['structure_id']} | {row['canonical_uniprot_id']} | "
            f"{row['evidence_tier']} | packet={row.get('packet_id') or 'missing'} | "
            f"chain={row.get('suggested_selected_chain_id') or 'review'}"
        )
    lines.extend([
        "",
        "## Blockers",
        "",
    ])
    for blocker in report["blockers"]:
        lines.append(f"- {blocker}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Build structure chain mapping backlog readiness report")
    parser.add_argument("--worklist", type=Path, default=WORKLIST)
    parser.add_argument("--decisions", type=Path, default=DECISIONS)
    parser.add_argument("--evidence-audit", type=Path, default=EVIDENCE_AUDIT)
    parser.add_argument("--dbref-audit", type=Path, default=DBREF_AUDIT)
    parser.add_argument("--packets-dir", type=Path, default=PACKETS_DIR)
    parser.add_argument("--validation-report", type=Path, default=VALIDATION_REPORT)
    parser.add_argument("--apply-report", type=Path, default=APPLY_REPORT)
    parser.add_argument("--report", type=Path, default=REPORT_OUT)
    parser.add_argument("--markdown", type=Path, default=MD_OUT)
    parser.add_argument("--queue-limit", type=int, default=25)
    args = parser.parse_args()

    worklist_rows = load_jsonl(args.worklist)
    decision_rows = load_jsonl(args.decisions)
    validation = load_json(args.validation_report)
    apply_report = load_json(args.apply_report)
    decided_ids = {normalize_structure_id(row.get("structure_id")) for row in decision_rows if row.get("structure_id")}
    strict_by_id = strict_evidence_by_structure(load_jsonl(args.evidence_audit), load_jsonl(args.dbref_audit))
    packet_by_id = build_packet_index(args.packets_dir)

    remaining_rows = [row for row in worklist_rows if normalize_structure_id(row.get("structure_id")) not in decided_ids]
    strict_remaining = {key: value for key, value in strict_by_id.items() if key not in decided_ids}
    strict_remaining_ids = set(strict_remaining)
    tier_counts = Counter(evidence_tier(row, strict_remaining_ids) for row in remaining_rows)
    bucket_counts = Counter(row.get("review_bucket") for row in remaining_rows)
    packet_counts = Counter(packet_by_id.get(normalize_structure_id(row.get("structure_id")), "missing_packet") for row in remaining_rows)
    missing_packet_rows = packet_counts.get("missing_packet", 0)

    validation_invalid_rows = validation.get("invalid_rows")
    usable_rows = apply_report.get("usable_for_coordinate_features") or 0
    blockers = []
    if remaining_rows:
        blockers.append("remaining_structure_chain_mapping_rows_require_reviewed_decisions")
    if validation_invalid_rows not in (0, None):
        blockers.append("structure_chain_mapping_decision_validation_has_invalid_rows")
    if missing_packet_rows:
        blockers.append("some_remaining_structure_rows_are_missing_review_packets")
    if strict_remaining:
        blockers.append("strict_evidence_candidates_still_require_explicit_human_decisions")

    report = {
        "local_only": True,
        "worklist": rel(args.worklist),
        "decision_input": rel(args.decisions),
        "validation_report": rel(args.validation_report),
        "apply_report": rel(args.apply_report),
        "worklist_rows": len(worklist_rows),
        "decision_rows": len(decision_rows),
        "valid_decision_rows": validation.get("valid_rows") or 0,
        "invalid_decision_rows": validation.get("invalid_rows") or 0,
        "reviewed_chain_mapping_rows": validation.get("reviewed_chain_mapping_rows") or 0,
        "usable_for_coordinate_features": usable_rows,
        "remaining_unreviewed_rows": len(remaining_rows),
        "remaining_by_review_bucket": dict(bucket_counts),
        "remaining_by_evidence_tier": dict(tier_counts),
        "remaining_by_packet_id": dict(packet_counts),
        "missing_packet_rows": missing_packet_rows,
        "strict_evidence_total_rows": len(strict_by_id),
        "strict_evidence_already_decided_rows": len(set(strict_by_id) & decided_ids),
        "strict_evidence_remaining_rows": len(strict_remaining),
        "strict_evidence_remaining_structure_ids": sorted(strict_remaining),
        "next_review_queue": top_queue_rows(remaining_rows, strict_remaining, packet_by_id, args.queue_limit),
        "completion_ready": len(remaining_rows) == 0 and (validation.get("invalid_rows") or 0) == 0,
        "safe_for_model_claim": False,
        "release_ready": False,
        "blockers": blockers,
        "next_actions": [
            "Review the strict_evidence_remaining_structure_ids first and append explicit set_chain_mapping or reject_structure rows only after human confirmation.",
            "Then continue packet-based review for single_chain_reviewed_uniprot_length_close rows before multi-chain selection rows.",
            "Run validate_structure_chain_mapping_decisions.py and apply_structure_chain_mapping_decisions.py after any reviewed decision edit.",
        ],
        "outputs": {
            "report": rel(args.report),
            "markdown": rel(args.markdown),
        },
        "policy": "Audit-only backlog readiness. Strict evidence prioritizes human review but does not create reviewed decisions, coordinate claims, training labels, release readiness, or model-quality claims.",
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    write_markdown(args.markdown, report)
    print(json.dumps({
        "remaining_unreviewed_rows": report["remaining_unreviewed_rows"],
        "strict_evidence_remaining_rows": report["strict_evidence_remaining_rows"],
        "missing_packet_rows": report["missing_packet_rows"],
        "completion_ready": report["completion_ready"],
        "output": str(args.report),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
