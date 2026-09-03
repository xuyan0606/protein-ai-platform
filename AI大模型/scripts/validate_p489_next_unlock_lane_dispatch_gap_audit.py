#!/usr/bin/env python3
"""Validate the P489 next-unlock lane dispatch gap audit."""

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
AUDIT = AI_ROOT / "datasets" / "governance" / "p489_next_unlock_lane_dispatch_gap_audit.jsonl"
REPORT = AI_ROOT / "reports" / "p489_next_unlock_lane_dispatch_gap_audit_report.json"
OUT = AI_ROOT / "reports" / "p489_next_unlock_lane_dispatch_gap_audit_validation_report.json"


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    value = json.loads(path.read_text(encoding="utf-8"))
    return value if isinstance(value, dict) else {}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def fail_if(condition: bool, failures: list[dict[str, Any]], check: str, observed: Any, expected: Any) -> None:
    if condition:
        failures.append({"check": check, "observed": observed, "expected": expected})


def main() -> int:
    dispatch_report = load_json(DISPATCH_REPORT)
    dispatch_validation = load_json(DISPATCH_VALIDATION)
    p488_report = load_json(P488_REPORT)
    p488_validation = load_json(P488_VALIDATION)
    local_release = load_json(LOCAL_RELEASE)
    claim_matrix = load_json(CLAIM_MATRIX)
    packet_rows = [row for row in load_jsonl(DISPATCH_PACKETS) if isinstance(row, dict)]
    status_rows = [row for row in load_jsonl(DISPATCH_STATUS) if isinstance(row, dict)]
    audit_rows = load_jsonl(AUDIT)
    report = load_json(REPORT)
    packet_by_id = {row.get("dispatch_packet_id"): row for row in packet_rows}
    status_by_id = {row.get("dispatch_packet_id"): row for row in status_rows}
    expected_rows = len(packet_rows) + 1
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
    failures: list[dict[str, Any]] = []

    fail_if(len(audit_rows) != expected_rows, failures, "audit_rows_expected", len(audit_rows), expected_rows)
    fail_if(report.get("audit_rows") != expected_rows, failures, "report_audit_rows_expected", report.get("audit_rows"), expected_rows)
    fail_if(report.get("dispatch_audit_rows") != len(packet_rows), failures, "dispatch_audit_rows_bound", report.get("dispatch_audit_rows"), len(packet_rows))
    fail_if(report.get("summary_audit_rows") != 1, failures, "summary_audit_rows_one", report.get("summary_audit_rows"), 1)
    fail_if(report.get("dispatch_packets") != dispatch_report.get("dispatch_packets"), failures, "dispatch_packets_bound", report.get("dispatch_packets"), dispatch_report.get("dispatch_packets"))
    fail_if(report.get("dispatch_ready_blocked_packets") != dispatch_ready_blocked_packets, failures, "dispatch_ready_blocked_packets_bound", report.get("dispatch_ready_blocked_packets"), dispatch_ready_blocked_packets)
    fail_if(report.get("invalid_dispatch_packets") != invalid_dispatch_packets, failures, "invalid_dispatch_packets_bound", report.get("invalid_dispatch_packets"), invalid_dispatch_packets)
    fail_if(report.get("dispatch_packets_missing_local_materials") != dispatch_packets_missing_local_materials, failures, "dispatch_packets_missing_local_materials_bound", report.get("dispatch_packets_missing_local_materials"), dispatch_packets_missing_local_materials)
    fail_if(report.get("total_launch_items") != total_launch_items, failures, "total_launch_items_bound", report.get("total_launch_items"), total_launch_items)
    fail_if(report.get("validated_launch_items") != validated_launch_items, failures, "validated_launch_items_bound", report.get("validated_launch_items"), validated_launch_items)
    fail_if(report.get("invalid_launch_items") != invalid_launch_items, failures, "invalid_launch_items_bound", report.get("invalid_launch_items"), invalid_launch_items)
    fail_if(report.get("source_completion_ready_items") != source_completion_ready_items, failures, "source_completion_ready_items_bound", report.get("source_completion_ready_items"), source_completion_ready_items)
    fail_if(report.get("requires_human_input_items") != requires_human_input_items, failures, "requires_human_input_items_bound", report.get("requires_human_input_items"), requires_human_input_items)
    fail_if(report.get("validated_dispatch_packets") != validated_dispatch_packets, failures, "validated_dispatch_packets_bound", report.get("validated_dispatch_packets"), validated_dispatch_packets)
    fail_if(report.get("validation_invalid_dispatch_packets") != validation_invalid_dispatch_packets, failures, "validation_invalid_dispatch_packets_bound", report.get("validation_invalid_dispatch_packets"), validation_invalid_dispatch_packets)
    fail_if(report.get("p488_started_blocked_lanes") != p488_report.get("started_blocked_lanes"), failures, "p488_started_blocked_lanes_bound", report.get("p488_started_blocked_lanes"), p488_report.get("started_blocked_lanes"))
    fail_if(report.get("p488_validation_success") is not True, failures, "p488_validation_success_true", report.get("p488_validation_success"), True)
    fail_if(p488_validation.get("success") is not True, failures, "source_p488_validation_success_true", p488_validation.get("success"), True)
    fail_if(report.get("local_release_ready") is not False, failures, "local_release_ready_false", report.get("local_release_ready"), False)
    fail_if(local_release.get("release_ready") is not False, failures, "source_local_release_ready_false", local_release.get("release_ready"), False)
    fail_if(report.get("claims_blocked") != claim_matrix.get("claims_blocked"), failures, "claims_blocked_bound", report.get("claims_blocked"), claim_matrix.get("claims_blocked"))
    fail_if(dispatch_report.get("online_deployment") is not False, failures, "source_online_deployment_false", dispatch_report.get("online_deployment"), False)
    fail_if(dispatch_report.get("dispatch_packets") != len(packet_rows), failures, "source_dispatch_packets_bound", dispatch_report.get("dispatch_packets"), len(packet_rows))
    fail_if(dispatch_report.get("dispatch_ready_blocked_packets") != len(packet_rows), failures, "source_all_dispatch_packets_ready_blocked", dispatch_report.get("dispatch_ready_blocked_packets"), len(packet_rows))
    fail_if(dispatch_report.get("invalid_dispatch_packets") != 0, failures, "source_invalid_dispatch_packets_zero", dispatch_report.get("invalid_dispatch_packets"), 0)
    fail_if(dispatch_report.get("dispatch_packets_missing_local_materials") != 0, failures, "source_missing_local_material_packets_zero", dispatch_report.get("dispatch_packets_missing_local_materials"), 0)
    fail_if(dispatch_report.get("completion_ready_items") != 0, failures, "source_completion_ready_items_zero", dispatch_report.get("completion_ready_items"), 0)
    fail_if(dispatch_validation.get("validated_dispatch_packets") != len(packet_rows), failures, "source_all_dispatch_packets_validated", dispatch_validation.get("validated_dispatch_packets"), len(packet_rows))
    fail_if(dispatch_validation.get("invalid_dispatch_packets") != 0, failures, "source_validation_invalid_dispatch_packets_zero", dispatch_validation.get("invalid_dispatch_packets"), 0)
    fail_if(dispatch_validation.get("completion_ready_items") != 0, failures, "source_validation_completion_ready_items_zero", dispatch_validation.get("completion_ready_items"), 0)
    fail_if(dispatch_ready_blocked_packets != len(packet_rows), failures, "all_packet_rows_ready_blocked_source", dispatch_ready_blocked_packets, len(packet_rows))
    fail_if(invalid_dispatch_packets != 0, failures, "all_packet_rows_valid_source", invalid_dispatch_packets, 0)
    fail_if(source_completion_ready_items != 0, failures, "all_packet_rows_completion_ready_zero_source", source_completion_ready_items, 0)
    fail_if(requires_human_input_items != total_launch_items, failures, "all_launch_items_require_human_input_source", requires_human_input_items, total_launch_items)

    seen_packets: list[Any] = []
    seen_types: list[Any] = []
    for idx, row in enumerate(audit_rows):
        gap_type = row.get("gap_type")
        seen_types.append(gap_type)
        fail_if(gap_type not in {"next_unlock_lane_dispatch_gap", "next_unlock_lane_dispatch_summary_gap"}, failures, "gap_type_allowed", {"index": idx, "observed": gap_type}, "allowed P489 gap type")
        for field in ("training_import_allowed", "safe_for_training_import", "safe_for_model_claim", "customer_delivery_ready", "release_ready", "production_execution_allowed", "completion_ready"):
            fail_if(row.get(field) is not False, failures, f"row_{field}_false", {"index": idx, "observed": row.get(field)}, False)
        if gap_type == "next_unlock_lane_dispatch_gap":
            packet_id = row.get("dispatch_packet_id")
            seen_packets.append(packet_id)
            source = packet_by_id.get(packet_id, {})
            status = status_by_id.get(packet_id, {})
            fail_if(packet_id not in packet_by_id, failures, "dispatch_packet_known", {"index": idx, "observed": packet_id}, sorted(packet_by_id))
            fail_if(row.get("lane_id") != source.get("lane_id"), failures, "packet_lane_id_bound", {"index": idx, "observed": row.get("lane_id")}, source.get("lane_id"))
            fail_if(row.get("source_dispatch_status") != source.get("dispatch_status"), failures, "packet_dispatch_status_bound", {"index": idx, "observed": row.get("source_dispatch_status")}, source.get("dispatch_status"))
            fail_if(row.get("validation_status") != status.get("validation_status"), failures, "packet_validation_status_bound", {"index": idx, "observed": row.get("validation_status")}, status.get("validation_status"))
            fail_if(row.get("launch_items") != source.get("launch_items"), failures, "packet_launch_items_bound", {"index": idx, "observed": row.get("launch_items")}, source.get("launch_items"))
            fail_if(row.get("requires_human_input_items") != source.get("requires_human_input_items"), failures, "packet_requires_human_input_items_bound", {"index": idx, "observed": row.get("requires_human_input_items")}, source.get("requires_human_input_items"))
            fail_if(row.get("source_completion_ready_items") != source.get("completion_ready_items"), failures, "packet_completion_ready_items_bound", {"index": idx, "observed": row.get("source_completion_ready_items")}, source.get("completion_ready_items"))
            fail_if(source.get("dispatch_status") != "dispatch_ready_blocked", failures, "source_dispatch_ready_blocked", {"index": idx, "observed": source.get("dispatch_status")}, "dispatch_ready_blocked")
            fail_if(status.get("validation_status") != "dispatch_validated_blocked", failures, "source_dispatch_validated_blocked", {"index": idx, "observed": status.get("validation_status")}, "dispatch_validated_blocked")
        if gap_type == "next_unlock_lane_dispatch_summary_gap":
            fail_if(row.get("dispatch_packets") != dispatch_report.get("dispatch_packets"), failures, "summary_dispatch_packets_bound", row.get("dispatch_packets"), dispatch_report.get("dispatch_packets"))
            fail_if(row.get("dispatch_ready_blocked_packets") != dispatch_ready_blocked_packets, failures, "summary_dispatch_ready_blocked_packets_bound", row.get("dispatch_ready_blocked_packets"), dispatch_ready_blocked_packets)
            fail_if(row.get("source_completion_ready_items") != 0, failures, "summary_source_completion_ready_items_zero", row.get("source_completion_ready_items"), 0)
            fail_if(row.get("requires_human_input_items") != requires_human_input_items, failures, "summary_requires_human_input_items_bound", row.get("requires_human_input_items"), requires_human_input_items)

    fail_if(sorted(seen_packets) != sorted(packet_by_id), failures, "dispatch_packets_exactly_covered", sorted(seen_packets), sorted(packet_by_id))
    fail_if(seen_types.count("next_unlock_lane_dispatch_gap") != len(packet_rows), failures, "dispatch_gap_type_count", seen_types.count("next_unlock_lane_dispatch_gap"), len(packet_rows))
    fail_if(seen_types.count("next_unlock_lane_dispatch_summary_gap") != 1, failures, "summary_type_count", seen_types.count("next_unlock_lane_dispatch_summary_gap"), 1)
    for field in ("training_import_allowed", "safe_for_training_import", "safe_for_model_claim", "customer_delivery_ready", "release_ready", "production_execution_allowed"):
        fail_if(report.get(field) is not False, failures, f"report_{field}_false", report.get(field), False)

    result = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "local_only": True,
        "success": not failures,
        "audit_rows": len(audit_rows),
        "dispatch_audit_rows": len(packet_rows),
        "dispatch_ready_blocked_packets": dispatch_ready_blocked_packets,
        "source_completion_ready_items": source_completion_ready_items,
        "requires_human_input_items": requires_human_input_items,
        "failures": failures,
        "training_import_allowed": False,
        "safe_for_training_import": False,
        "safe_for_model_claim": False,
        "customer_delivery_ready": False,
        "release_ready": False,
        "production_execution_allowed": False,
        "policy": "Validation only. Lane dispatch gaps do not authorize training, claims, delivery, release, ordering, deployment, sync, restart, or production execution.",
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "success": result["success"],
        "audit_rows": result["audit_rows"],
        "dispatch_audit_rows": result["dispatch_audit_rows"],
        "dispatch_ready_blocked_packets": result["dispatch_ready_blocked_packets"],
        "failures": len(failures),
        "output": str(OUT),
    }, ensure_ascii=False))
    return 0 if result["success"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
