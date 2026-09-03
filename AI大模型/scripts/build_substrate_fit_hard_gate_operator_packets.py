#!/usr/bin/env python3
"""Build fail-closed operator packets for substrate-fit label/source hard gates."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
GAP_REPORT = AI_ROOT / "reports" / "substrate_fit_label_gap_plan_report.json"
OUT = AI_ROOT / "reports" / "substrate_fit_hard_gate_operator_packet_report.json"
MD_OUT = AI_ROOT / "reports" / "substrate_fit_hard_gate_operator_packets.md"
JSONL_OUT = AI_ROOT / "datasets" / "governance" / "substrate_fit_hard_gate_operator_packets.jsonl"

POLICY = (
    "Fail-closed substrate-fit operator packets only. They do not define an approved schema, "
    "approve external sources, convert activity/benchmark/proxy rows into labels, write training "
    "rows, train models, unlock model claims, deploy services, sync production, or release artifacts."
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


def action_packet(row: dict[str, Any], order: int) -> dict[str, Any]:
    action_id = str(row.get("action_id") or f"substrate-action-{order:03d}")
    return {
        "packet_id": f"substrate-fit-hard-gate-{action_id}",
        "execution_order": order,
        "workstream": "substrate_fit_label_source",
        "packet_type": "substrate_fit_action",
        "priority": row.get("priority") or "P0",
        "status": "open_blocked",
        "source_action_id": action_id,
        "action": row.get("action"),
        "owner_lane": row.get("owner_lane"),
        "blocked_by": row.get("blocked_by"),
        "current_training_rows": as_int(row.get("current_training_rows")),
        "minimum_rows": as_int(row.get("minimum_rows")),
        "ready_candidate_rows": as_int(row.get("ready_candidate_rows")),
        "missing_to_minimum": as_int(row.get("missing_to_minimum")),
        "required_human_checks": [
            "confirm substrate identity is explicit, not inferred from generic activity",
            "confirm assay condition, unit, raw value semantics, QC and lineage",
            "confirm numbering/source/license gates before any label import",
            "confirm this action remains separate from model claim or release approval",
        ],
        "allowed_human_decisions": ["approve_schema_or_source_for_next_review", "reject_source_for_substrate_fit", "needs_more_info"],
        "completion_condition": "Only a separate reviewed schema/source decision can move this packet forward; this packet itself is not approval.",
        "schema_or_source_approved_by_packet": False,
        "training_label_written_by_packet": False,
        "model_claim_allowed": False,
        "release_ready": False,
        "requires_human_input": True,
        "policy": POLICY,
    }


def source_packet(row: dict[str, Any], order: int) -> dict[str, Any]:
    source_id = str(row.get("source_id") or f"source-{order:03d}")
    return {
        "packet_id": f"substrate-fit-source-review-{source_id}",
        "execution_order": order,
        "workstream": "substrate_fit_source_review",
        "packet_type": "candidate_source_review",
        "priority": "P0" if as_int(row.get("ready_candidate_rows")) == 0 else "P1",
        "status": "open_blocked",
        "source_id": source_id,
        "artifact": row.get("artifact"),
        "observed_rows": as_int(row.get("observed_rows") or row.get("expected_benchmark_entries") or row.get("relevant_feature_families")),
        "candidate_rows": as_int(row.get("candidate_rows")),
        "ready_candidate_rows": as_int(row.get("ready_candidate_rows")),
        "source_status": row.get("status"),
        "blocker": row.get("blocker"),
        "required_evidence_before_label_use": [
            "explicit substrate identity",
            "assay_type=substrate_fit or approved mapping semantics",
            "reviewed provenance and source terms",
            "QC and unit/condition metadata",
            "numbering verified for variant-linked rows",
            "human-reviewed decision before training import",
        ],
        "forbidden_shortcuts": [
            "generic_activity_as_substrate_fit",
            "benchmark_dataset_as_training_label",
            "affinity_or_pose_prediction_as_ground_truth",
            "context_only_feedback_as_label",
        ],
        "completion_condition": "Ready candidate rows remain zero until an approved source/schema decision and reviewed substrate-specific rows exist.",
        "source_approved_by_packet": False,
        "training_label_written_by_packet": False,
        "model_claim_allowed": False,
        "release_ready": False,
        "requires_human_input": True,
        "policy": POLICY,
    }


def write_markdown(report: dict[str, Any], path: Path) -> None:
    lines = [
        "# Substrate-Fit Hard-Gate Operator Packets",
        "",
        f"Generated: {report['created_at']}",
        "",
        "These packets organize substrate_fit label/source review. They do not approve schema, source, or labels.",
        "",
        "## Summary",
        "",
        f"- Packet rows: {report['packet_rows']}",
        f"- Action packets: {report['action_packet_rows']}",
        f"- Source packets: {report['source_packet_rows']}",
        f"- Ready candidate rows: {report['ready_candidate_rows']}",
        f"- Completion ready rows: {report['completion_ready_rows']}",
        f"- Safe for model claim: {str(report['safe_for_model_claim']).lower()}",
        "",
        "## Sources",
        "",
        "| source | artifact | observed | candidates | ready | blocker |",
        "|---|---|---:|---:|---:|---|",
    ]
    for row in report["source_packets"]:
        lines.append(
            f"| {row['source_id']} | {row['artifact']} | {row['observed_rows']} | "
            f"{row['candidate_rows']} | {row['ready_candidate_rows']} | {row['blocker']} |"
        )
    lines.extend(["", "## Policy", "", report["policy"]])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Build substrate-fit hard-gate operator packets")
    parser.add_argument("--gap-report", type=Path, default=GAP_REPORT)
    parser.add_argument("--output", type=Path, default=OUT)
    parser.add_argument("--markdown", type=Path, default=MD_OUT)
    parser.add_argument("--jsonl", type=Path, default=JSONL_OUT)
    args = parser.parse_args()

    gap = load_json(args.gap_report)
    actions = [row for row in gap.get("actions") or [] if isinstance(row, dict)]
    sources = [row for row in gap.get("candidate_sources") or [] if isinstance(row, dict)]
    packets: list[dict[str, Any]] = []
    for row in actions:
        packets.append(action_packet(row, len(packets) + 1))
    for row in sources:
        packets.append(source_packet(row, len(packets) + 1))

    write_jsonl(args.jsonl, packets)
    packet_types = Counter(str(row.get("packet_type")) for row in packets)
    source_packets = [row for row in packets if row.get("packet_type") == "candidate_source_review"]
    report = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "local_only": True,
        "status": "blocked",
        "source_gap_report": str(args.gap_report),
        "jsonl": str(args.jsonl),
        "packet_rows": len(packets),
        "action_packet_rows": packet_types.get("substrate_fit_action", 0),
        "source_packet_rows": packet_types.get("candidate_source_review", 0),
        "ready_candidate_rows": sum(as_int(row.get("ready_candidate_rows")) for row in packets),
        "completion_ready_rows": 0,
        "schema_or_source_approved_rows": 0,
        "training_label_written_rows": 0,
        "requires_human_input_rows": len(packets),
        "packet_type_counts": dict(sorted(packet_types.items())),
        "source_packets": source_packets,
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
        "action_packet_rows": report["action_packet_rows"],
        "source_packet_rows": report["source_packet_rows"],
        "ready_candidate_rows": report["ready_candidate_rows"],
        "completion_ready_rows": report["completion_ready_rows"],
        "safe_for_model_claim": report["safe_for_model_claim"],
        "output": str(args.output),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
