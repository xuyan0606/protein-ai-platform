#!/usr/bin/env python3
"""Build a source-bound audit of next-unlock lane dispatch gaps."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
DISPATCH_REPORT = AI_ROOT / "reports" / "next_unlock_lane_dispatch_packet_report.json"
DISPATCH_PACKETS = AI_ROOT / "datasets" / "governance" / "next_unlock_lane_dispatch_packets.jsonl"
DISPATCH_VALIDATION = AI_ROOT / "reports" / "next_unlock_lane_dispatch_validation_report.json"
DISPATCH_STATUS = AI_ROOT / "datasets" / "governance" / "next_unlock_lane_dispatch_status.jsonl"
P488_REPORT = AI_ROOT / "reports" / "p488_next_unlock_agent_lane_status_gap_audit_report.json"
P488_VALIDATION = AI_ROOT / "reports" / "p488_next_unlock_agent_lane_status_gap_audit_validation_report.json"
LOCAL_RELEASE = AI_ROOT / "reports" / "local_release_manifest.json"
CLAIM_MATRIX = AI_ROOT / "reports" / "claim_readiness_matrix.json"
OUT_JSONL = AI_ROOT / "datasets" / "governance" / "p489_next_unlock_lane_dispatch_gap_audit.jsonl"
OUT_REPORT = AI_ROOT / "reports" / "p489_next_unlock_lane_dispatch_gap_audit_report.json"


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    value = json.loads(path.read_text(encoding="utf-8"))
    return value if isinstance(value, dict) else {}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def base(audit_id: str, gap_type: str, source_state: dict[str, Any], blocker: str) -> dict[str, Any]:
    return {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "local_only": True,
        "audit_id": audit_id,
        "gap_type": gap_type,
        "source_report": "reports/next_unlock_lane_dispatch_packet_report.json",
        "source_jsonl": "datasets/governance/next_unlock_lane_dispatch_packets.jsonl",
        "source_state": source_state,
        "blocker": blocker,
        "training_import_allowed": False,
        "safe_for_training_import": False,
        "safe_for_model_claim": False,
        "customer_delivery_ready": False,
        "release_ready": False,
        "production_execution_allowed": False,
        "policy": "Lane dispatch gap audit only; dispatch-ready blocked packets are local file coordination artifacts and do not create reviewed decisions, approvals, training data, model claims, customer delivery authorization, release approval, deployment, sync, restart, or production execution.",
    }


def main() -> int:
    dispatch_report = load_json(DISPATCH_REPORT)
    dispatch_validation = load_json(DISPATCH_VALIDATION)
    p488_report = load_json(P488_REPORT)
    p488_validation = load_json(P488_VALIDATION)
    local_release = load_json(LOCAL_RELEASE)
    claim_matrix = load_json(CLAIM_MATRIX)
    packet_rows = [row for row in load_jsonl(DISPATCH_PACKETS) if isinstance(row, dict)]
    status_rows = [row for row in load_jsonl(DISPATCH_STATUS) if isinstance(row, dict)]
    status_by_packet = {row.get("dispatch_packet_id"): row for row in status_rows}
    rows: list[dict[str, Any]] = []

    for packet in packet_rows:
        packet_id = packet.get("dispatch_packet_id")
        status = status_by_packet.get(packet_id, {})
        action_sequence = packet.get("action_sequence") or []
        rows.append(base(
            f"p489-next-unlock-lane-dispatch::{packet_id}",
            "next_unlock_lane_dispatch_gap",
            {
                "dispatch_packet_id": packet_id,
                "lane_id": packet.get("lane_id"),
                "source_dispatch_status": packet.get("dispatch_status"),
                "validation_status": status.get("validation_status"),
                "lane_status": packet.get("lane_status"),
                "dispatch_scope": packet.get("dispatch_scope"),
                "launch_items": packet.get("launch_items"),
                "validated_launch_items": packet.get("validated_launch_items"),
                "invalid_launch_items": packet.get("invalid_launch_items"),
                "source_completion_ready_items": packet.get("completion_ready_items"),
                "requires_human_input_items": packet.get("requires_human_input_items"),
                "missing_local_materials": packet.get("missing_local_materials") or [],
                "action_ids": [item.get("action_id") for item in action_sequence],
                "workstreams": [item.get("workstream") for item in action_sequence],
                "operator_open_first": packet.get("operator_open_first") or [],
                "next_evidence_artifacts": packet.get("next_evidence_artifacts") or [],
                "validation_failed_checks": status.get("failed_checks") or [],
            },
            "dispatch packet remains ready-blocked and requires human input before any completion or authorization",
        ) | {
            "dispatch_packet_id": packet_id,
            "lane_id": packet.get("lane_id"),
            "source_dispatch_status": packet.get("dispatch_status"),
            "validation_status": status.get("validation_status"),
            "launch_items": packet.get("launch_items"),
            "requires_human_input_items": packet.get("requires_human_input_items"),
            "source_completion_ready_items": packet.get("completion_ready_items"),
            "completion_ready": False,
        })

    dispatch_ready_blocked_packets = sum(1 for row in packet_rows if row.get("dispatch_status") == "dispatch_ready_blocked")
    invalid_dispatch_packets = sum(1 for row in packet_rows if row.get("dispatch_status") == "dispatch_invalid")
    dispatch_packets_missing_local_materials = sum(1 for row in packet_rows if row.get("missing_local_materials"))
    total_launch_items = sum(int(row.get("launch_items") or 0) for row in packet_rows)
    validated_launch_items = sum(int(row.get("validated_launch_items") or 0) for row in packet_rows)
    invalid_launch_items = sum(int(row.get("invalid_launch_items") or 0) for row in packet_rows)
    source_completion_ready_items = sum(int(row.get("completion_ready_items") or 0) for row in packet_rows)
    requires_human_input_items = sum(int(row.get("requires_human_input_items") or 0) for row in packet_rows)
    validated_dispatch_packets = sum(1 for row in status_rows if row.get("validation_status") == "dispatch_validated_blocked")
    validation_invalid_dispatch_packets = sum(1 for row in status_rows if row.get("validation_status") == "dispatch_invalid")
    rows.append(base(
        "p489-next-unlock-lane-dispatch-summary",
        "next_unlock_lane_dispatch_summary_gap",
        {
            "dispatch_packets": dispatch_report.get("dispatch_packets"),
            "dispatch_ready_blocked_packets": dispatch_report.get("dispatch_ready_blocked_packets"),
            "invalid_dispatch_packets": dispatch_report.get("invalid_dispatch_packets"),
            "dispatch_packets_missing_local_materials": dispatch_report.get("dispatch_packets_missing_local_materials"),
            "total_launch_items": dispatch_report.get("total_launch_items"),
            "validated_launch_items": dispatch_report.get("validated_launch_items"),
            "invalid_launch_items": dispatch_report.get("invalid_launch_items"),
            "source_completion_ready_items": dispatch_report.get("completion_ready_items"),
            "requires_human_input_items": dispatch_report.get("requires_human_input_items"),
            "validated_dispatch_packets": dispatch_validation.get("validated_dispatch_packets"),
            "validation_invalid_dispatch_packets": dispatch_validation.get("invalid_dispatch_packets"),
            "missing_local_material_packets": dispatch_validation.get("missing_local_material_packets"),
            "p488_started_blocked_lanes": p488_report.get("started_blocked_lanes"),
            "p488_validation_success": p488_validation.get("success"),
            "local_release_ready": local_release.get("release_ready"),
            "claims_blocked": claim_matrix.get("claims_blocked"),
        },
        "lane dispatch remains a local coordination packet set and does not close any next-unlock gap",
    ) | {
        "dispatch_packets": dispatch_report.get("dispatch_packets"),
        "dispatch_ready_blocked_packets": dispatch_ready_blocked_packets,
        "invalid_dispatch_packets": invalid_dispatch_packets,
        "dispatch_packets_missing_local_materials": dispatch_packets_missing_local_materials,
        "total_launch_items": total_launch_items,
        "validated_launch_items": validated_launch_items,
        "invalid_launch_items": invalid_launch_items,
        "source_completion_ready_items": source_completion_ready_items,
        "requires_human_input_items": requires_human_input_items,
        "validated_dispatch_packets": validated_dispatch_packets,
        "validation_invalid_dispatch_packets": validation_invalid_dispatch_packets,
        "completion_ready": False,
    })

    report = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "local_only": True,
        "audit_rows": len(rows),
        "dispatch_audit_rows": len(packet_rows),
        "summary_audit_rows": 1,
        "dispatch_packets": dispatch_report.get("dispatch_packets"),
        "dispatch_ready_blocked_packets": dispatch_ready_blocked_packets,
        "invalid_dispatch_packets": invalid_dispatch_packets,
        "dispatch_packets_missing_local_materials": dispatch_packets_missing_local_materials,
        "total_launch_items": total_launch_items,
        "validated_launch_items": validated_launch_items,
        "invalid_launch_items": invalid_launch_items,
        "source_completion_ready_items": source_completion_ready_items,
        "requires_human_input_items": requires_human_input_items,
        "validated_dispatch_packets": validated_dispatch_packets,
        "validation_invalid_dispatch_packets": validation_invalid_dispatch_packets,
        "p488_started_blocked_lanes": p488_report.get("started_blocked_lanes"),
        "p488_validation_success": p488_validation.get("success"),
        "local_release_ready": local_release.get("release_ready"),
        "claims_blocked": claim_matrix.get("claims_blocked"),
        "training_import_allowed": False,
        "safe_for_training_import": False,
        "safe_for_model_claim": False,
        "customer_delivery_ready": False,
        "release_ready": False,
        "production_execution_allowed": False,
        "audit_jsonl": "datasets/governance/p489_next_unlock_lane_dispatch_gap_audit.jsonl",
        "policy": "P489 audit only. Lane dispatch packets are not reviewed decisions, approvals, training imports, model claims, customer delivery authorization, release approval, deployment, sync, restart, or production execution.",
    }
    write_jsonl(OUT_JSONL, rows)
    OUT_REPORT.parent.mkdir(parents=True, exist_ok=True)
    OUT_REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "audit_rows": report["audit_rows"],
        "dispatch_audit_rows": report["dispatch_audit_rows"],
        "dispatch_ready_blocked_packets": report["dispatch_ready_blocked_packets"],
        "source_completion_ready_items": report["source_completion_ready_items"],
        "output": str(OUT_REPORT),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
