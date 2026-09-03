#!/usr/bin/env python3
"""Validate the P488 next-unlock agent lane status gap audit."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
LANE_REPORT = AI_ROOT / "reports" / "next_unlock_agent_lane_status_report.json"
LANE_STATUS = AI_ROOT / "datasets" / "governance" / "next_unlock_agent_lane_status.jsonl"
P487_REPORT = AI_ROOT / "reports" / "p487_next_unlock_multi_agent_launch_gap_audit_report.json"
P487_VALIDATION = AI_ROOT / "reports" / "p487_next_unlock_multi_agent_launch_gap_audit_validation_report.json"
LOCAL_RELEASE = AI_ROOT / "reports" / "local_release_manifest.json"
CLAIM_MATRIX = AI_ROOT / "reports" / "claim_readiness_matrix.json"
AUDIT = AI_ROOT / "datasets" / "governance" / "p488_next_unlock_agent_lane_status_gap_audit.jsonl"
REPORT = AI_ROOT / "reports" / "p488_next_unlock_agent_lane_status_gap_audit_report.json"
OUT = AI_ROOT / "reports" / "p488_next_unlock_agent_lane_status_gap_audit_validation_report.json"


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
    lane_report = load_json(LANE_REPORT)
    p487_report = load_json(P487_REPORT)
    p487_validation = load_json(P487_VALIDATION)
    local_release = load_json(LOCAL_RELEASE)
    claim_matrix = load_json(CLAIM_MATRIX)
    lane_rows = [row for row in load_jsonl(LANE_STATUS) if isinstance(row, dict)]
    audit_rows = load_jsonl(AUDIT)
    report = load_json(REPORT)
    lane_by_id = {row.get("lane_id"): row for row in lane_rows}
    expected_rows = len(lane_rows) + 1
    started_blocked_lanes = sum(1 for row in lane_rows if row.get("lane_status") == "lane_started_blocked")
    invalid_lanes = sum(1 for row in lane_rows if row.get("lane_status") == "lane_invalid")
    lanes_with_completion_ready_items = sum(1 for row in lane_rows if int(row.get("completion_ready_items") or 0) > 0)
    total_launch_items = sum(int(row.get("launch_items") or 0) for row in lane_rows)
    validated_launch_items = sum(int(row.get("validated_launch_items") or 0) for row in lane_rows)
    invalid_launch_items = sum(int(row.get("invalid_launch_items") or 0) for row in lane_rows)
    started_items = sum(int(row.get("started_items") or 0) for row in lane_rows)
    source_completion_ready_items = sum(int(row.get("completion_ready_items") or 0) for row in lane_rows)
    requires_human_input_items = sum(int(row.get("requires_human_input_items") or 0) for row in lane_rows)
    failures: list[dict[str, Any]] = []

    fail_if(len(audit_rows) != expected_rows, failures, "audit_rows_expected", len(audit_rows), expected_rows)
    fail_if(report.get("audit_rows") != expected_rows, failures, "report_audit_rows_expected", report.get("audit_rows"), expected_rows)
    fail_if(report.get("lane_audit_rows") != len(lane_rows), failures, "lane_audit_rows_bound", report.get("lane_audit_rows"), len(lane_rows))
    fail_if(report.get("summary_audit_rows") != 1, failures, "summary_audit_rows_one", report.get("summary_audit_rows"), 1)
    fail_if(report.get("lane_rows") != lane_report.get("lane_rows"), failures, "lane_rows_bound", report.get("lane_rows"), lane_report.get("lane_rows"))
    fail_if(report.get("started_blocked_lanes") != started_blocked_lanes, failures, "started_blocked_lanes_bound", report.get("started_blocked_lanes"), started_blocked_lanes)
    fail_if(report.get("invalid_lanes") != invalid_lanes, failures, "invalid_lanes_bound", report.get("invalid_lanes"), invalid_lanes)
    fail_if(report.get("lanes_with_completion_ready_items") != lanes_with_completion_ready_items, failures, "lanes_with_completion_ready_items_bound", report.get("lanes_with_completion_ready_items"), lanes_with_completion_ready_items)
    fail_if(report.get("total_launch_items") != total_launch_items, failures, "total_launch_items_bound", report.get("total_launch_items"), total_launch_items)
    fail_if(report.get("validated_launch_items") != validated_launch_items, failures, "validated_launch_items_bound", report.get("validated_launch_items"), validated_launch_items)
    fail_if(report.get("invalid_launch_items") != invalid_launch_items, failures, "invalid_launch_items_bound", report.get("invalid_launch_items"), invalid_launch_items)
    fail_if(report.get("started_items") != started_items, failures, "started_items_bound", report.get("started_items"), started_items)
    fail_if(report.get("source_completion_ready_items") != source_completion_ready_items, failures, "source_completion_ready_items_bound", report.get("source_completion_ready_items"), source_completion_ready_items)
    fail_if(report.get("requires_human_input_items") != requires_human_input_items, failures, "requires_human_input_items_bound", report.get("requires_human_input_items"), requires_human_input_items)
    fail_if(report.get("p487_open_blocked_rows") != p487_report.get("open_blocked_rows"), failures, "p487_open_blocked_rows_bound", report.get("p487_open_blocked_rows"), p487_report.get("open_blocked_rows"))
    fail_if(report.get("p487_validation_success") is not True, failures, "p487_validation_success_true", report.get("p487_validation_success"), True)
    fail_if(p487_validation.get("success") is not True, failures, "source_p487_validation_success_true", p487_validation.get("success"), True)
    fail_if(report.get("local_release_ready") is not False, failures, "local_release_ready_false", report.get("local_release_ready"), False)
    fail_if(local_release.get("release_ready") is not False, failures, "source_local_release_ready_false", local_release.get("release_ready"), False)
    fail_if(report.get("claims_blocked") != claim_matrix.get("claims_blocked"), failures, "claims_blocked_bound", report.get("claims_blocked"), claim_matrix.get("claims_blocked"))
    fail_if(lane_report.get("online_deployment") is not False, failures, "source_online_deployment_false", lane_report.get("online_deployment"), False)
    fail_if(lane_report.get("lane_rows") != len(lane_rows), failures, "source_lane_rows_bound", lane_report.get("lane_rows"), len(lane_rows))
    fail_if(lane_report.get("started_blocked_lanes") != len(lane_rows), failures, "source_all_lanes_started_blocked", lane_report.get("started_blocked_lanes"), len(lane_rows))
    fail_if(lane_report.get("invalid_lanes") != 0, failures, "source_invalid_lanes_zero", lane_report.get("invalid_lanes"), 0)
    fail_if(lane_report.get("completion_ready_items") != 0, failures, "source_completion_ready_items_zero", lane_report.get("completion_ready_items"), 0)
    fail_if(lane_report.get("requires_human_input_items") != total_launch_items, failures, "source_human_input_matches_launch_items", lane_report.get("requires_human_input_items"), total_launch_items)
    fail_if(started_blocked_lanes != len(lane_rows), failures, "all_lane_rows_started_blocked_source", started_blocked_lanes, len(lane_rows))
    fail_if(invalid_lanes != 0, failures, "all_lane_rows_valid_source", invalid_lanes, 0)
    fail_if(source_completion_ready_items != 0, failures, "all_lane_rows_completion_ready_zero_source", source_completion_ready_items, 0)
    fail_if(requires_human_input_items != total_launch_items, failures, "all_launch_items_require_human_input_source", requires_human_input_items, total_launch_items)

    seen_lanes: list[Any] = []
    seen_types: list[Any] = []
    for idx, row in enumerate(audit_rows):
        gap_type = row.get("gap_type")
        seen_types.append(gap_type)
        fail_if(gap_type not in {"next_unlock_agent_lane_status_gap", "next_unlock_agent_lane_status_summary_gap"}, failures, "gap_type_allowed", {"index": idx, "observed": gap_type}, "allowed P488 gap type")
        for field in ("training_import_allowed", "safe_for_training_import", "safe_for_model_claim", "customer_delivery_ready", "release_ready", "production_execution_allowed", "completion_ready"):
            fail_if(row.get(field) is not False, failures, f"row_{field}_false", {"index": idx, "observed": row.get(field)}, False)
        if gap_type == "next_unlock_agent_lane_status_gap":
            lane_id = row.get("lane_id")
            seen_lanes.append(lane_id)
            source = lane_by_id.get(lane_id, {})
            fail_if(lane_id not in lane_by_id, failures, "lane_known", {"index": idx, "observed": lane_id}, sorted(lane_by_id))
            fail_if(row.get("source_lane_status") != source.get("lane_status"), failures, "lane_status_bound", {"index": idx, "observed": row.get("source_lane_status")}, source.get("lane_status"))
            fail_if(row.get("launch_items") != source.get("launch_items"), failures, "lane_launch_items_bound", {"index": idx, "observed": row.get("launch_items")}, source.get("launch_items"))
            fail_if(row.get("started_items") != source.get("started_items"), failures, "lane_started_items_bound", {"index": idx, "observed": row.get("started_items")}, source.get("started_items"))
            fail_if(row.get("requires_human_input_items") != source.get("requires_human_input_items"), failures, "lane_requires_human_input_items_bound", {"index": idx, "observed": row.get("requires_human_input_items")}, source.get("requires_human_input_items"))
            fail_if(row.get("source_completion_ready_items") != int(source.get("completion_ready_items") or 0), failures, "lane_completion_ready_items_bound", {"index": idx, "observed": row.get("source_completion_ready_items")}, int(source.get("completion_ready_items") or 0))
            fail_if(source.get("lane_status") != "lane_started_blocked", failures, "source_lane_started_blocked", {"index": idx, "observed": source.get("lane_status")}, "lane_started_blocked")
        if gap_type == "next_unlock_agent_lane_status_summary_gap":
            fail_if(row.get("lane_rows") != lane_report.get("lane_rows"), failures, "summary_lane_rows_bound", row.get("lane_rows"), lane_report.get("lane_rows"))
            fail_if(row.get("started_blocked_lanes") != started_blocked_lanes, failures, "summary_started_blocked_lanes_bound", row.get("started_blocked_lanes"), started_blocked_lanes)
            fail_if(row.get("source_completion_ready_items") != 0, failures, "summary_source_completion_ready_items_zero", row.get("source_completion_ready_items"), 0)
            fail_if(row.get("requires_human_input_items") != requires_human_input_items, failures, "summary_requires_human_input_items_bound", row.get("requires_human_input_items"), requires_human_input_items)

    fail_if(sorted(seen_lanes) != sorted(lane_by_id), failures, "lanes_exactly_covered", sorted(seen_lanes), sorted(lane_by_id))
    fail_if(seen_types.count("next_unlock_agent_lane_status_gap") != len(lane_rows), failures, "lane_gap_type_count", seen_types.count("next_unlock_agent_lane_status_gap"), len(lane_rows))
    fail_if(seen_types.count("next_unlock_agent_lane_status_summary_gap") != 1, failures, "summary_type_count", seen_types.count("next_unlock_agent_lane_status_summary_gap"), 1)
    for field in ("training_import_allowed", "safe_for_training_import", "safe_for_model_claim", "customer_delivery_ready", "release_ready", "production_execution_allowed"):
        fail_if(report.get(field) is not False, failures, f"report_{field}_false", report.get(field), False)

    result = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "local_only": True,
        "success": not failures,
        "audit_rows": len(audit_rows),
        "lane_audit_rows": len(lane_rows),
        "started_blocked_lanes": started_blocked_lanes,
        "source_completion_ready_items": source_completion_ready_items,
        "requires_human_input_items": requires_human_input_items,
        "failures": failures,
        "training_import_allowed": False,
        "safe_for_training_import": False,
        "safe_for_model_claim": False,
        "customer_delivery_ready": False,
        "release_ready": False,
        "production_execution_allowed": False,
        "policy": "Validation only. Agent lane status gaps do not authorize training, claims, delivery, release, ordering, deployment, sync, restart, or production execution.",
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "success": result["success"],
        "audit_rows": result["audit_rows"],
        "lane_audit_rows": result["lane_audit_rows"],
        "started_blocked_lanes": result["started_blocked_lanes"],
        "failures": len(failures),
        "output": str(OUT),
    }, ensure_ascii=False))
    return 0 if result["success"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
