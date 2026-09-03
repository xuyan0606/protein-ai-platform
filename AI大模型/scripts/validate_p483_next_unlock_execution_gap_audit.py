#!/usr/bin/env python3
"""Validate the P483 next-unlock execution gap audit."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
PLAN = AI_ROOT / "reports" / "next_unlock_plan.json"
BOARD = AI_ROOT / "reports" / "next_unlock_execution_board.json"
VALIDATION = AI_ROOT / "reports" / "next_unlock_execution_validation_report.json"
ACTIONS = AI_ROOT / "datasets" / "governance" / "next_unlock_actions.jsonl"
COMPLETION_STATUS = AI_ROOT / "datasets" / "governance" / "next_unlock_completion_status.jsonl"
LOCAL_RELEASE = AI_ROOT / "reports" / "local_release_manifest.json"
CLAIM_MATRIX = AI_ROOT / "reports" / "claim_readiness_matrix.json"
AUDIT = AI_ROOT / "datasets" / "governance" / "p483_next_unlock_execution_gap_audit.jsonl"
REPORT = AI_ROOT / "reports" / "p483_next_unlock_execution_gap_audit_report.json"
OUT = AI_ROOT / "reports" / "p483_next_unlock_execution_gap_audit_validation_report.json"


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
    plan = load_json(PLAN)
    board = load_json(BOARD)
    validation = load_json(VALIDATION)
    local_release = load_json(LOCAL_RELEASE)
    claim_matrix = load_json(CLAIM_MATRIX)
    actions = [row for row in load_jsonl(ACTIONS) if isinstance(row, dict)]
    completion_rows = [row for row in load_jsonl(COMPLETION_STATUS) if isinstance(row, dict)]
    audit_rows = load_jsonl(AUDIT)
    report = load_json(REPORT)
    stage_rows = [row for row in validation.get("stage_summary") or [] if isinstance(row, dict)]
    completion_by_action = {row.get("action_id"): row for row in completion_rows}
    stages_by_id = {row.get("stage_id"): row for row in stage_rows}
    board_stages_by_id = {row.get("stage_id"): row for row in board.get("stages") or [] if isinstance(row, dict)}
    expected_rows = len(actions) + len(stage_rows) + 1
    blocked_action_rows = int(validation.get("blocked_actions") or 0)
    stage_completion_ready_count = int(validation.get("completion_ready_stage_count") or 0)
    blocked_stage_rows = max(0, len(stage_rows) - stage_completion_ready_count)
    failures: list[dict[str, Any]] = []

    fail_if(len(audit_rows) != expected_rows, failures, "audit_rows_expected", len(audit_rows), expected_rows)
    fail_if(report.get("audit_rows") != expected_rows, failures, "report_audit_rows_expected", report.get("audit_rows"), expected_rows)
    fail_if(report.get("action_audit_rows") != len(actions), failures, "action_audit_rows_bound", report.get("action_audit_rows"), len(actions))
    fail_if(report.get("stage_audit_rows") != len(stage_rows), failures, "stage_audit_rows_bound", report.get("stage_audit_rows"), len(stage_rows))
    fail_if(report.get("summary_audit_rows") != 1, failures, "summary_audit_rows_one", report.get("summary_audit_rows"), 1)
    fail_if(report.get("blocked_action_rows") != blocked_action_rows, failures, "blocked_action_rows_bound", report.get("blocked_action_rows"), blocked_action_rows)
    fail_if(report.get("blocked_stage_rows") != blocked_stage_rows, failures, "blocked_stage_rows_bound", report.get("blocked_stage_rows"), blocked_stage_rows)
    fail_if(report.get("blocked_gap_rows") != blocked_action_rows + blocked_stage_rows, failures, "blocked_gap_rows_bound", report.get("blocked_gap_rows"), blocked_action_rows + blocked_stage_rows)
    fail_if(report.get("plan_action_rows") != plan.get("action_rows"), failures, "plan_action_rows_bound", report.get("plan_action_rows"), plan.get("action_rows"))
    fail_if(report.get("board_total_actions") != board.get("total_actions"), failures, "board_total_actions_bound", report.get("board_total_actions"), board.get("total_actions"))
    fail_if(report.get("board_started_actions") != board.get("started_actions"), failures, "board_started_actions_bound", report.get("board_started_actions"), board.get("started_actions"))
    fail_if(report.get("board_completion_ready_actions") != board.get("completion_ready_actions"), failures, "board_completion_ready_actions_bound", report.get("board_completion_ready_actions"), board.get("completion_ready_actions"))
    fail_if(report.get("validation_completion_ready_actions") != validation.get("completion_ready_actions"), failures, "validation_completion_ready_actions_bound", report.get("validation_completion_ready_actions"), validation.get("completion_ready_actions"))
    fail_if(report.get("validation_blocked_actions") != validation.get("blocked_actions"), failures, "validation_blocked_actions_bound", report.get("validation_blocked_actions"), validation.get("blocked_actions"))
    fail_if(report.get("stage_count") != validation.get("stage_count"), failures, "stage_count_bound", report.get("stage_count"), validation.get("stage_count"))
    fail_if(report.get("validation_completion_ready_stage_count") != validation.get("completion_ready_stage_count"), failures, "validation_completion_ready_stage_count_bound", report.get("validation_completion_ready_stage_count"), validation.get("completion_ready_stage_count"))
    fail_if(report.get("plan_blocked_unlocks") != plan.get("blocked_unlocks"), failures, "plan_blocked_unlocks_bound", report.get("plan_blocked_unlocks"), plan.get("blocked_unlocks"))
    fail_if(report.get("local_release_ready") is not False, failures, "local_release_ready_false", report.get("local_release_ready"), False)
    fail_if(local_release.get("release_ready") is not False, failures, "source_local_release_ready_false", local_release.get("release_ready"), False)
    fail_if(report.get("claims_blocked") != claim_matrix.get("claims_blocked"), failures, "claims_blocked_bound", report.get("claims_blocked"), claim_matrix.get("claims_blocked"))
    fail_if(validation.get("total_actions") != len(actions), failures, "source_total_actions_bound", validation.get("total_actions"), len(actions))
    fail_if(validation.get("started_actions") != len(actions), failures, "source_started_actions_all", validation.get("started_actions"), len(actions))

    seen_actions: list[Any] = []
    seen_stages: list[Any] = []
    seen_types: list[Any] = []
    action_ids = {row.get("action_id") for row in actions}
    for idx, row in enumerate(audit_rows):
        gap_type = row.get("gap_type")
        seen_types.append(gap_type)
        fail_if(gap_type not in {"next_unlock_action_execution_gap", "next_unlock_stage_execution_gap", "next_unlock_execution_summary_gap"}, failures, "gap_type_allowed", {"index": idx, "observed": gap_type}, "allowed P483 gap type")
        for field in ("training_import_allowed", "safe_for_training_import", "safe_for_model_claim", "customer_delivery_ready", "release_ready", "production_execution_allowed", "completion_ready"):
            fail_if(row.get(field) is not False, failures, f"row_{field}_false", {"index": idx, "observed": row.get(field)}, False)
        if gap_type == "next_unlock_action_execution_gap":
            action_id = row.get("action_id")
            seen_actions.append(action_id)
            source = completion_by_action.get(action_id, {})
            fail_if(action_id not in action_ids, failures, "action_known", {"index": idx, "observed": action_id}, sorted(action_ids))
            fail_if(row.get("stage_id") != source.get("stage_id"), failures, "action_stage_id_bound", {"index": idx, "observed": row.get("stage_id")}, source.get("stage_id"))
            fail_if(row.get("workstream") != source.get("workstream"), failures, "action_workstream_bound", {"index": idx, "observed": row.get("workstream")}, source.get("workstream"))
            fail_if(row.get("source_status") != source.get("status"), failures, "action_status_bound", {"index": idx, "observed": row.get("source_status")}, source.get("status"))
            fail_if(row.get("source_completion_ready") != (source.get("completion_ready") is True), failures, "action_source_completion_ready_bound", {"index": idx, "observed": row.get("source_completion_ready")}, source.get("completion_ready") is True)
            fail_if(row.get("failed_check_count") != len(source.get("failed_checks") or []), failures, "action_failed_check_count_bound", {"index": idx, "observed": row.get("failed_check_count")}, len(source.get("failed_checks") or []))
        if gap_type == "next_unlock_stage_execution_gap":
            stage_id = row.get("stage_id")
            seen_stages.append(stage_id)
            source = stages_by_id.get(stage_id, {})
            board_stage = board_stages_by_id.get(stage_id, {})
            fail_if(stage_id not in stages_by_id, failures, "stage_known", {"index": idx, "observed": stage_id}, sorted(stages_by_id))
            fail_if(row.get("stage_order") != source.get("stage_order"), failures, "stage_order_bound", {"index": idx, "observed": row.get("stage_order")}, source.get("stage_order"))
            fail_if(row.get("source_completion_ready") != (source.get("completion_ready") is True), failures, "stage_source_completion_ready_bound", {"index": idx, "observed": row.get("source_completion_ready")}, source.get("completion_ready") is True)
            fail_if(row.get("source_blocked_actions") != source.get("blocked_actions"), failures, "stage_blocked_actions_bound", {"index": idx, "observed": row.get("source_blocked_actions")}, source.get("blocked_actions"))
            fail_if(board_stage.get("completion_ready") is not False, failures, "board_stage_completion_ready_false", {"stage": stage_id, "observed": board_stage.get("completion_ready")}, False)
        if gap_type == "next_unlock_execution_summary_gap":
            fail_if(row.get("source_completion_ready_actions") != validation.get("completion_ready_actions"), failures, "summary_completion_ready_actions_bound", row.get("source_completion_ready_actions"), validation.get("completion_ready_actions"))
            fail_if(row.get("blocked_action_rows") != blocked_action_rows, failures, "summary_blocked_action_rows_bound", row.get("blocked_action_rows"), blocked_action_rows)
            fail_if(row.get("source_completion_ready_stage_count") != stage_completion_ready_count, failures, "summary_stage_ready_count_bound", row.get("source_completion_ready_stage_count"), stage_completion_ready_count)
            fail_if(row.get("blocked_stage_rows") != blocked_stage_rows, failures, "summary_blocked_stage_rows_bound", row.get("blocked_stage_rows"), blocked_stage_rows)

    fail_if(sorted(seen_actions) != sorted(action_ids), failures, "actions_exactly_covered", sorted(seen_actions), sorted(action_ids))
    fail_if(sorted(seen_stages) != sorted(stages_by_id), failures, "stages_exactly_covered", sorted(seen_stages), sorted(stages_by_id))
    fail_if(seen_types.count("next_unlock_action_execution_gap") != len(actions), failures, "action_gap_type_count", seen_types.count("next_unlock_action_execution_gap"), len(actions))
    fail_if(seen_types.count("next_unlock_stage_execution_gap") != len(stage_rows), failures, "stage_gap_type_count", seen_types.count("next_unlock_stage_execution_gap"), len(stage_rows))
    fail_if(seen_types.count("next_unlock_execution_summary_gap") != 1, failures, "summary_type_count", seen_types.count("next_unlock_execution_summary_gap"), 1)
    for field in ("training_import_allowed", "safe_for_training_import", "safe_for_model_claim", "customer_delivery_ready", "release_ready", "production_execution_allowed"):
        fail_if(report.get(field) is not False, failures, f"report_{field}_false", report.get(field), False)

    result = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "local_only": True,
        "success": not failures,
        "audit_rows": len(audit_rows),
        "action_audit_rows": len(actions),
        "stage_audit_rows": len(stage_rows),
        "blocked_action_rows": blocked_action_rows,
        "blocked_stage_rows": blocked_stage_rows,
        "blocked_gap_rows": blocked_action_rows + blocked_stage_rows,
        "validation_completion_ready_actions": validation.get("completion_ready_actions"),
        "validation_completion_ready_stage_count": validation.get("completion_ready_stage_count"),
        "failures": failures,
        "training_import_allowed": False,
        "safe_for_training_import": False,
        "safe_for_model_claim": False,
        "customer_delivery_ready": False,
        "release_ready": False,
        "production_execution_allowed": False,
        "policy": "Validation only. Next-unlock execution gaps do not authorize training, claims, delivery, release, ordering, or production execution.",
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "success": result["success"],
        "audit_rows": result["audit_rows"],
        "action_audit_rows": result["action_audit_rows"],
        "stage_audit_rows": result["stage_audit_rows"],
        "blocked_gap_rows": result["blocked_gap_rows"],
        "failures": len(failures),
        "output": str(OUT),
    }, ensure_ascii=False))
    return 0 if result["success"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
