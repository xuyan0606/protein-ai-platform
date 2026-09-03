#!/usr/bin/env python3
"""Validate the P487 next-unlock multi-agent launch gap audit."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
LAUNCH_REPORT = AI_ROOT / "reports" / "next_unlock_multi_agent_launch_board.json"
LAUNCH_BOARD = AI_ROOT / "datasets" / "governance" / "next_unlock_multi_agent_launch_board.jsonl"
LAUNCH_VALIDATION = AI_ROOT / "reports" / "next_unlock_multi_agent_launch_validation_report.json"
LAUNCH_STATUS = AI_ROOT / "datasets" / "governance" / "next_unlock_multi_agent_launch_status.jsonl"
P486_REPORT = AI_ROOT / "reports" / "p486_next_unlock_remediation_queue_gap_audit_report.json"
P486_VALIDATION = AI_ROOT / "reports" / "p486_next_unlock_remediation_queue_gap_audit_validation_report.json"
LOCAL_RELEASE = AI_ROOT / "reports" / "local_release_manifest.json"
CLAIM_MATRIX = AI_ROOT / "reports" / "claim_readiness_matrix.json"
AUDIT = AI_ROOT / "datasets" / "governance" / "p487_next_unlock_multi_agent_launch_gap_audit.jsonl"
REPORT = AI_ROOT / "reports" / "p487_next_unlock_multi_agent_launch_gap_audit_report.json"
OUT = AI_ROOT / "reports" / "p487_next_unlock_multi_agent_launch_gap_audit_validation_report.json"


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
    launch_report = load_json(LAUNCH_REPORT)
    launch_validation = load_json(LAUNCH_VALIDATION)
    p486_report = load_json(P486_REPORT)
    p486_validation = load_json(P486_VALIDATION)
    local_release = load_json(LOCAL_RELEASE)
    claim_matrix = load_json(CLAIM_MATRIX)
    launch_rows = [row for row in load_jsonl(LAUNCH_BOARD) if isinstance(row, dict)]
    status_rows = [row for row in load_jsonl(LAUNCH_STATUS) if isinstance(row, dict)]
    audit_rows = load_jsonl(AUDIT)
    report = load_json(REPORT)
    launch_by_id = {row.get("launch_id"): row for row in launch_rows}
    status_by_id = {row.get("launch_id"): row for row in status_rows}
    expected_rows = len(launch_rows) + 1
    started_rows = sum(1 for row in launch_rows if row.get("started") is True)
    open_blocked_rows = sum(1 for row in launch_rows if row.get("launch_status") == "local_agent_started_blocked")
    requires_human_input_rows = sum(1 for row in launch_rows if row.get("requires_human_input") is True)
    completion_ready_rows = sum(1 for row in launch_rows if row.get("completion_ready") is True)
    failures: list[dict[str, Any]] = []

    fail_if(len(audit_rows) != expected_rows, failures, "audit_rows_expected", len(audit_rows), expected_rows)
    fail_if(report.get("audit_rows") != expected_rows, failures, "report_audit_rows_expected", report.get("audit_rows"), expected_rows)
    fail_if(report.get("launch_audit_rows") != len(launch_rows), failures, "launch_audit_rows_bound", report.get("launch_audit_rows"), len(launch_rows))
    fail_if(report.get("summary_audit_rows") != 1, failures, "summary_audit_rows_one", report.get("summary_audit_rows"), 1)
    fail_if(report.get("launch_rows") != launch_report.get("launch_rows"), failures, "launch_rows_bound", report.get("launch_rows"), launch_report.get("launch_rows"))
    fail_if(report.get("started_rows") != started_rows, failures, "started_rows_bound", report.get("started_rows"), started_rows)
    fail_if(report.get("open_blocked_rows") != open_blocked_rows, failures, "open_blocked_rows_bound", report.get("open_blocked_rows"), open_blocked_rows)
    fail_if(report.get("ready_to_launch_rows") != launch_report.get("ready_to_launch_items"), failures, "ready_to_launch_rows_bound", report.get("ready_to_launch_rows"), launch_report.get("ready_to_launch_items"))
    fail_if(report.get("requires_human_input_rows") != requires_human_input_rows, failures, "requires_human_input_rows_bound", report.get("requires_human_input_rows"), requires_human_input_rows)
    fail_if(report.get("source_completion_ready_rows") != completion_ready_rows, failures, "source_completion_ready_rows_bound", report.get("source_completion_ready_rows"), completion_ready_rows)
    fail_if(report.get("local_agent_lanes") != launch_report.get("local_agent_lanes"), failures, "local_agent_lanes_bound", report.get("local_agent_lanes"), launch_report.get("local_agent_lanes"))
    fail_if(report.get("agent_count") != launch_report.get("agent_count"), failures, "agent_count_bound", report.get("agent_count"), launch_report.get("agent_count"))
    fail_if(report.get("parallel_groups") != launch_report.get("parallel_groups"), failures, "parallel_groups_bound", report.get("parallel_groups"), launch_report.get("parallel_groups"))
    fail_if(report.get("validated_launch_rows") != launch_validation.get("validated_launch_rows"), failures, "validated_launch_rows_bound", report.get("validated_launch_rows"), launch_validation.get("validated_launch_rows"))
    fail_if(report.get("invalid_launch_rows") != launch_validation.get("invalid_launch_rows"), failures, "invalid_launch_rows_bound", report.get("invalid_launch_rows"), launch_validation.get("invalid_launch_rows"))
    fail_if(report.get("p486_open_rows") != p486_report.get("open_rows"), failures, "p486_open_rows_bound", report.get("p486_open_rows"), p486_report.get("open_rows"))
    fail_if(report.get("p486_validation_success") is not True, failures, "p486_validation_success_true", report.get("p486_validation_success"), True)
    fail_if(p486_validation.get("success") is not True, failures, "source_p486_validation_success_true", p486_validation.get("success"), True)
    fail_if(report.get("local_release_ready") is not False, failures, "local_release_ready_false", report.get("local_release_ready"), False)
    fail_if(local_release.get("release_ready") is not False, failures, "source_local_release_ready_false", local_release.get("release_ready"), False)
    fail_if(report.get("claims_blocked") != claim_matrix.get("claims_blocked"), failures, "claims_blocked_bound", report.get("claims_blocked"), claim_matrix.get("claims_blocked"))
    fail_if(launch_report.get("online_deployment") is not False, failures, "source_online_deployment_false", launch_report.get("online_deployment"), False)
    fail_if(launch_report.get("completion_ready_items") != 0, failures, "source_completion_ready_items_zero", launch_report.get("completion_ready_items"), 0)
    fail_if(launch_validation.get("invalid_launch_rows") != 0, failures, "source_invalid_launch_rows_zero", launch_validation.get("invalid_launch_rows"), 0)
    fail_if(launch_validation.get("completion_ready_items") != 0, failures, "source_validation_completion_ready_items_zero", launch_validation.get("completion_ready_items"), 0)
    fail_if(started_rows != len(launch_rows), failures, "all_launch_rows_started_source", started_rows, len(launch_rows))
    fail_if(open_blocked_rows != len(launch_rows), failures, "all_launch_rows_started_blocked_source", open_blocked_rows, len(launch_rows))
    fail_if(requires_human_input_rows != len(launch_rows), failures, "all_launch_rows_require_human_input_source", requires_human_input_rows, len(launch_rows))
    fail_if(completion_ready_rows != 0, failures, "all_launch_rows_completion_ready_false_source", completion_ready_rows, 0)

    seen_launches: list[Any] = []
    seen_types: list[Any] = []
    for idx, row in enumerate(audit_rows):
        gap_type = row.get("gap_type")
        seen_types.append(gap_type)
        fail_if(gap_type not in {"next_unlock_multi_agent_launch_gap", "next_unlock_multi_agent_launch_summary_gap"}, failures, "gap_type_allowed", {"index": idx, "observed": gap_type}, "allowed P487 gap type")
        for field in ("training_import_allowed", "safe_for_training_import", "safe_for_model_claim", "customer_delivery_ready", "release_ready", "production_execution_allowed", "completion_ready"):
            fail_if(row.get(field) is not False, failures, f"row_{field}_false", {"index": idx, "observed": row.get(field)}, False)
        if gap_type == "next_unlock_multi_agent_launch_gap":
            launch_id = row.get("launch_id")
            seen_launches.append(launch_id)
            source = launch_by_id.get(launch_id, {})
            status = status_by_id.get(launch_id, {})
            fail_if(launch_id not in launch_by_id, failures, "launch_known", {"index": idx, "observed": launch_id}, sorted(launch_by_id))
            fail_if(row.get("remediation_id") != source.get("remediation_id"), failures, "launch_remediation_id_bound", {"index": idx, "observed": row.get("remediation_id")}, source.get("remediation_id"))
            fail_if(row.get("action_id") != source.get("action_id"), failures, "launch_action_id_bound", {"index": idx, "observed": row.get("action_id")}, source.get("action_id"))
            fail_if(row.get("workstream") != source.get("workstream"), failures, "launch_workstream_bound", {"index": idx, "observed": row.get("workstream")}, source.get("workstream"))
            fail_if(row.get("lane_id") != source.get("lane_id"), failures, "launch_lane_id_bound", {"index": idx, "observed": row.get("lane_id")}, source.get("lane_id"))
            fail_if(row.get("launch_status") != source.get("launch_status"), failures, "launch_status_bound", {"index": idx, "observed": row.get("launch_status")}, source.get("launch_status"))
            fail_if(row.get("validation_status") != status.get("validation_status"), failures, "launch_validation_status_bound", {"index": idx, "observed": row.get("validation_status")}, status.get("validation_status"))
            fail_if(row.get("source_started") != (source.get("started") is True), failures, "launch_started_bound", {"index": idx, "observed": row.get("source_started")}, source.get("started") is True)
            fail_if(row.get("requires_human_input") != (source.get("requires_human_input") is True), failures, "launch_requires_human_input_bound", {"index": idx, "observed": row.get("requires_human_input")}, source.get("requires_human_input") is True)
            fail_if(status.get("validation_status") != "launch_validated_blocked", failures, "source_launch_validated_blocked", {"index": idx, "observed": status.get("validation_status")}, "launch_validated_blocked")
        if gap_type == "next_unlock_multi_agent_launch_summary_gap":
            fail_if(row.get("launch_rows") != launch_report.get("launch_rows"), failures, "summary_launch_rows_bound", row.get("launch_rows"), launch_report.get("launch_rows"))
            fail_if(row.get("started_rows") != started_rows, failures, "summary_started_rows_bound", row.get("started_rows"), started_rows)
            fail_if(row.get("open_blocked_rows") != open_blocked_rows, failures, "summary_open_blocked_rows_bound", row.get("open_blocked_rows"), open_blocked_rows)
            fail_if(row.get("requires_human_input_rows") != requires_human_input_rows, failures, "summary_requires_human_input_rows_bound", row.get("requires_human_input_rows"), requires_human_input_rows)
            fail_if(row.get("source_completion_ready_rows") != 0, failures, "summary_source_completion_ready_rows_zero", row.get("source_completion_ready_rows"), 0)

    fail_if(sorted(seen_launches) != sorted(launch_by_id), failures, "launches_exactly_covered", sorted(seen_launches), sorted(launch_by_id))
    fail_if(seen_types.count("next_unlock_multi_agent_launch_gap") != len(launch_rows), failures, "launch_gap_type_count", seen_types.count("next_unlock_multi_agent_launch_gap"), len(launch_rows))
    fail_if(seen_types.count("next_unlock_multi_agent_launch_summary_gap") != 1, failures, "summary_type_count", seen_types.count("next_unlock_multi_agent_launch_summary_gap"), 1)
    for field in ("training_import_allowed", "safe_for_training_import", "safe_for_model_claim", "customer_delivery_ready", "release_ready", "production_execution_allowed"):
        fail_if(report.get(field) is not False, failures, f"report_{field}_false", report.get(field), False)

    result = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "local_only": True,
        "success": not failures,
        "audit_rows": len(audit_rows),
        "launch_audit_rows": len(launch_rows),
        "started_rows": started_rows,
        "open_blocked_rows": open_blocked_rows,
        "requires_human_input_rows": requires_human_input_rows,
        "source_completion_ready_rows": completion_ready_rows,
        "failures": failures,
        "training_import_allowed": False,
        "safe_for_training_import": False,
        "safe_for_model_claim": False,
        "customer_delivery_ready": False,
        "release_ready": False,
        "production_execution_allowed": False,
        "policy": "Validation only. Multi-agent launch gaps do not authorize training, claims, delivery, release, ordering, deployment, sync, restart, or production execution.",
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "success": result["success"],
        "audit_rows": result["audit_rows"],
        "launch_audit_rows": result["launch_audit_rows"],
        "open_blocked_rows": result["open_blocked_rows"],
        "failures": len(failures),
        "output": str(OUT),
    }, ensure_ascii=False))
    return 0 if result["success"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
