#!/usr/bin/env python3
"""Build fail-closed operator packets for structure-feature hard gates."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
GAP_REPORT = AI_ROOT / "reports" / "structure_feature_head_gap_plan_report.json"
OUT = AI_ROOT / "reports" / "structure_feature_hard_gate_operator_packet_report.json"
MD_OUT = AI_ROOT / "reports" / "structure_feature_hard_gate_operator_packets.md"
JSONL_OUT = AI_ROOT / "datasets" / "governance" / "structure_feature_hard_gate_operator_packets.jsonl"

POLICY = (
    "Fail-closed structure-feature operator packets only. They do not write chain mapping "
    "decisions, approve coordinate claims, import labels, train models, unlock model claims, "
    "deploy services, sync production, or release artifacts."
)


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )


def as_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def strict_candidate_packet(row: dict[str, Any], order: int) -> dict[str, Any]:
    return {
        "packet_id": f"structure-feature-hard-gate-{row.get('structure_id')}",
        "execution_order": order,
        "workstream": "structure_feature_expansion",
        "packet_type": "strict_evidence_chain_mapping_review",
        "priority": row.get("priority") or "P0",
        "status": "open_blocked_waiting_for_human_review",
        "structure_id": row.get("structure_id"),
        "canonical_uniprot_id": row.get("canonical_uniprot_id"),
        "protein_name": row.get("protein_name"),
        "review_rank": row.get("review_rank"),
        "review_bucket": row.get("review_bucket"),
        "source_packet_id": row.get("packet_id"),
        "suggested_selected_chain_id": row.get("suggested_selected_chain_id"),
        "strict_evidence_sources": row.get("strict_evidence_sources") or [],
        "chain_count": row.get("chain_count"),
        "parsed_chain_ids": row.get("parsed_chain_ids") or [],
        "db_chain_ids": row.get("db_chain_ids") or [],
        "resolution": row.get("resolution"),
        "decision_input_after_human_review": row.get("decision_input") or "datasets/curation/structure_chain_mapping_decisions.jsonl",
        "required_human_checks": row.get("required_human_checks") or [],
        "allowed_human_decisions": ["set_chain_mapping", "reject_structure", "needs_more_info"],
        "post_decision_commands": [
            "python3 scripts/validate_structure_chain_mapping_decisions.py",
            "python3 scripts/apply_structure_chain_mapping_decisions.py",
            "python3 scripts/build_reviewed_structure_graph_features.py",
            "python3 scripts/validate_reviewed_structure_graph_features.py",
            "python3 scripts/build_structure_feature_head_gap_plan.py",
            "python3 scripts/build_structure_feature_hard_gate_operator_packets.py",
            "python3 scripts/run_safe_training_pipeline.py",
        ],
        "completion_condition": (
            "Only after a human confirms the biological chain, residue numbering, missing residues, insertion "
            "codes, engineered tags, ligands and hetero residues may an explicit chain-mapping decision be appended."
        ),
        "decision_written_by_packet": False,
        "coordinate_claim_allowed": False,
        "training_label_written_by_packet": False,
        "model_claim_allowed": False,
        "release_ready": False,
        "requires_human_input": True,
        "policy": POLICY,
    }


def head_gap_packet(row: dict[str, Any], order: int) -> dict[str, Any]:
    return {
        "packet_id": f"structure-feature-head-gap-{row.get('head')}",
        "execution_order": order,
        "workstream": "structure_feature_head_capacity",
        "packet_type": "head_effective_feature_gap",
        "priority": row.get("priority") or "P0",
        "status": "open_blocked",
        "head": row.get("head"),
        "current_label_rows": as_int(row.get("current_label_rows")),
        "minimum_rows": as_int(row.get("minimum_rows")),
        "effective_training_rows_with_structure_features": as_int(row.get("effective_training_rows_with_structure_features")),
        "effective_gap_to_minimum": as_int(row.get("effective_gap_to_minimum")),
        "chain_mapping_backlog_rows": as_int(row.get("chain_mapping_backlog_rows")),
        "next_strict_chain_candidate_rows": as_int(row.get("next_strict_chain_candidate_rows")),
        "blocking_gate": row.get("blocking_gate"),
        "blockers": row.get("blockers") or [],
        "next_action": row.get("next_action"),
        "completion_condition": "Effective feature gap can close only after reviewed labels and reviewed chain mappings both meet the per-head minimum.",
        "decision_written_by_packet": False,
        "coordinate_claim_allowed": False,
        "training_label_written_by_packet": False,
        "model_claim_allowed": False,
        "release_ready": False,
        "requires_human_input": True,
        "policy": POLICY,
    }


def write_markdown(report: dict[str, Any], path: Path) -> None:
    lines = [
        "# Structure Feature Hard-Gate Operator Packets",
        "",
        f"Generated: {report['created_at']}",
        "",
        "These packets organize structure-chain review and head-capacity blockers. They do not write decisions.",
        "",
        "## Summary",
        "",
        f"- Packet rows: {report['packet_rows']}",
        f"- Strict candidate packets: {report['strict_candidate_packet_rows']}",
        f"- Head gap packets: {report['head_gap_packet_rows']}",
        f"- Completion ready rows: {report['completion_ready_rows']}",
        f"- Safe for model claim: {str(report['safe_for_model_claim']).lower()}",
        "",
        "## Strict Candidates",
        "",
        "| order | structure | UniProt | suggested chain | source packet | checks |",
        "|---:|---|---|---|---|---:|",
    ]
    for row in report["top_strict_candidate_packets"]:
        lines.append(
            f"| {row['execution_order']} | {row['structure_id']} | {row['canonical_uniprot_id']} | "
            f"{row['suggested_selected_chain_id']} | {row['source_packet_id']} | {len(row['required_human_checks'])} |"
        )
    lines.extend(["", "## Policy", "", report["policy"]])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Build structure-feature hard-gate operator packets")
    parser.add_argument("--gap-report", type=Path, default=GAP_REPORT)
    parser.add_argument("--output", type=Path, default=OUT)
    parser.add_argument("--markdown", type=Path, default=MD_OUT)
    parser.add_argument("--jsonl", type=Path, default=JSONL_OUT)
    args = parser.parse_args()

    gap = load_json(args.gap_report)
    strict_candidates = [
        row for row in gap.get("strict_evidence_chain_candidates") or []
        if isinstance(row, dict)
    ]
    head_rows = [row for row in gap.get("head_readiness") or [] if isinstance(row, dict)]
    packets: list[dict[str, Any]] = []
    for row in strict_candidates:
        packets.append(strict_candidate_packet(row, len(packets) + 1))
    for row in head_rows:
        packets.append(head_gap_packet(row, len(packets) + 1))

    write_jsonl(args.jsonl, packets)
    packet_types = Counter(str(row.get("packet_type")) for row in packets)
    report = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "local_only": True,
        "status": "blocked",
        "source_gap_report": str(args.gap_report),
        "jsonl": str(args.jsonl),
        "packet_rows": len(packets),
        "strict_candidate_packet_rows": packet_types.get("strict_evidence_chain_mapping_review", 0),
        "head_gap_packet_rows": packet_types.get("head_effective_feature_gap", 0),
        "completion_ready_rows": 0,
        "decision_written_rows": 0,
        "coordinate_claim_allowed_rows": 0,
        "training_label_written_rows": 0,
        "requires_human_input_rows": len(packets),
        "structure_ids": [row.get("structure_id") for row in packets if row.get("structure_id")],
        "packet_type_counts": dict(sorted(packet_types.items())),
        "top_strict_candidate_packets": [row for row in packets if row.get("packet_type") == "strict_evidence_chain_mapping_review"],
        "safe_for_training_import": False,
        "safe_for_model_claim": False,
        "release_ready": False,
        "policy": POLICY,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    write_markdown(report, args.markdown)
    print(json.dumps({
        "status": report["status"],
        "packet_rows": report["packet_rows"],
        "strict_candidate_packet_rows": report["strict_candidate_packet_rows"],
        "head_gap_packet_rows": report["head_gap_packet_rows"],
        "completion_ready_rows": report["completion_ready_rows"],
        "safe_for_model_claim": report["safe_for_model_claim"],
        "output": str(args.output),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
