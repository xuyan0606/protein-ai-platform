#!/usr/bin/env python3
"""Validate enzyme agent execution eligibility matrix."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
MATRIX = AI_ROOT / "datasets" / "governance" / "enzyme_agent_execution_eligibility_matrix.jsonl"
REPORT = AI_ROOT / "reports" / "enzyme_agent_execution_eligibility_matrix_report.json"
PLAN = AI_ROOT / "reports" / "enzyme_resource_retrieval_plan_report.json"
OUT = AI_ROOT / "reports" / "enzyme_agent_execution_eligibility_matrix_validation_report.json"

REQUIRED_CLASSIFICATIONS = {
    "recommended_read_only",
    "executable_after_user_confirmation",
    "blocked_requires_human_decision",
    "forbidden_for_current_request",
}

ALLOWED_EXECUTION_STATUS = {"blocked_current_request", "executed_passed", "executed_failed", "blocked", "skipped"}


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def fail_if(condition: bool, failures: list[dict[str, Any]], check: str, observed: Any, expected: Any) -> None:
    if condition:
        failures.append({"check": check, "observed": observed, "expected": expected})


def validate_eligibility_matrix_object(
    matrix: list[dict[str, Any]],
    report: dict[str, Any],
    plan: dict[str, Any],
) -> list[dict[str, Any]]:
    plan_actions = {row.get("action_id"): row for row in plan.get("actions") or []}
    matrix_actions = {row.get("action_id"): row for row in matrix}
    failures: list[dict[str, Any]] = []

    fail_if(report.get("action_rows") != len(matrix), failures, "report_action_rows_match_matrix", report.get("action_rows"), len(matrix))
    fail_if(set(matrix_actions) != set(plan_actions), failures, "matrix_actions_match_plan", sorted(matrix_actions), sorted(plan_actions))
    fail_if(report.get("current_execution_allowed_rows") != sum(1 for row in matrix if row.get("current_execution_allowed") is True), failures, "current_execution_allowed_rows_match_matrix", report.get("current_execution_allowed_rows"), "sum matrix current_execution_allowed")
    fail_if(report.get("executed_in_current_trace_rows") != sum(1 for row in matrix if row.get("executed_in_current_trace") is True), failures, "executed_in_current_trace_rows_match_matrix", report.get("executed_in_current_trace_rows"), "sum matrix executed_in_current_trace")
    fail_if(report.get("receipt_present_rows") != sum(1 for row in matrix if row.get("receipt_present") is True), failures, "receipt_present_rows_match_matrix", report.get("receipt_present_rows"), "sum matrix receipt_present")
    fail_if(report.get("executed_with_receipt_rows") != sum(1 for row in matrix if row.get("executed_with_receipt") is True), failures, "executed_with_receipt_rows_match_matrix", report.get("executed_with_receipt_rows"), "sum matrix executed_with_receipt")
    fail_if(report.get("receipt_gate_validation_success") is not True, failures, "receipt_gate_validation_success_true", report.get("receipt_gate_validation_success"), True)
    fail_if(report.get("receipt_safety_regression_success") is not True, failures, "receipt_safety_regression_success_true", report.get("receipt_safety_regression_success"), True)
    fail_if(report.get("receipt_safety_regression_failed_cases") not in (0, None), failures, "receipt_safety_regression_failed_cases_zero", report.get("receipt_safety_regression_failed_cases"), 0)
    fail_if(report.get("safe_for_execution_claim") is not False, failures, "safe_for_execution_claim_false", report.get("safe_for_execution_claim"), False)
    fail_if(report.get("safe_for_training_import") is not False, failures, "report_training_import_false", report.get("safe_for_training_import"), False)
    fail_if(report.get("safe_for_model_claim") is not False, failures, "report_model_claim_false", report.get("safe_for_model_claim"), False)
    fail_if(report.get("release_ready") is not False, failures, "report_release_ready_false", report.get("release_ready"), False)

    observed_classifications = {row.get("classification") for row in matrix}
    fail_if(observed_classifications != REQUIRED_CLASSIFICATIONS, failures, "required_classifications_present", sorted(observed_classifications), sorted(REQUIRED_CLASSIFICATIONS))

    for row in matrix:
        action_id = row.get("action_id")
        plan_action = plan_actions.get(action_id) or {}
        fail_if(row.get("classification") != plan_action.get("classification"), failures, "row_classification_matches_plan", {"action_id": action_id, "observed": row.get("classification")}, plan_action.get("classification"))
        fail_if(row.get("execution_status") not in ALLOWED_EXECUTION_STATUS, failures, "row_execution_status_allowed", {"action_id": action_id, "observed": row.get("execution_status")}, sorted(ALLOWED_EXECUTION_STATUS))
        if row.get("current_execution_allowed") is True:
            fail_if(row.get("classification") not in {"recommended_read_only", "executable_after_user_confirmation"}, failures, "row_current_execution_allowed_only_low_risk_classes", {"action_id": action_id, "observed": row.get("classification")}, ["recommended_read_only", "executable_after_user_confirmation"])
            fail_if(row.get("receipt_present") is not True, failures, "row_current_execution_allowed_requires_receipt", {"action_id": action_id, "observed": row.get("receipt_present")}, True)
            fail_if(row.get("receipt_status") != "executed_passed", failures, "row_current_execution_allowed_requires_passed_receipt", {"action_id": action_id, "observed": row.get("receipt_status")}, "executed_passed")
        fail_if(row.get("safe_for_training_import") is not False, failures, "row_training_import_false", {"action_id": action_id, "observed": row.get("safe_for_training_import")}, False)
        fail_if(row.get("safe_for_model_claim") is not False, failures, "row_model_claim_false", {"action_id": action_id, "observed": row.get("safe_for_model_claim")}, False)
        fail_if(row.get("release_ready") is not False, failures, "row_release_ready_false", {"action_id": action_id, "observed": row.get("release_ready")}, False)
        if row.get("executed_in_current_trace") is True:
            fail_if(row.get("receipt_present") is not True, failures, "row_executed_requires_receipt", {"action_id": action_id, "observed": row.get("receipt_present")}, True)
            fail_if(row.get("receipt_status") not in {"executed_passed", "executed_failed", "blocked"}, failures, "row_executed_requires_terminal_receipt_status", {"action_id": action_id, "observed": row.get("receipt_status")}, ["executed_passed", "executed_failed", "blocked"])
        fail_if(row.get("writes_training_rows") is not False, failures, "row_writes_training_rows_false", {"action_id": action_id, "observed": row.get("writes_training_rows")}, False)
        blocked_reasons = row.get("blocked_reasons") or []
        fail_if(not blocked_reasons, failures, "row_blocked_reasons_nonempty", {"action_id": action_id, "observed": blocked_reasons}, "nonempty")
        if row.get("classification") == "executable_after_user_confirmation":
            fail_if("requires_explicit_user_confirmation" not in blocked_reasons, failures, "executable_requires_confirmation_reason", {"action_id": action_id, "observed": blocked_reasons}, "requires_explicit_user_confirmation")
            fail_if(row.get("human_confirmation_required") is not True, failures, "executable_human_confirmation_required_true", {"action_id": action_id, "observed": row.get("human_confirmation_required")}, True)
        if row.get("classification") == "blocked_requires_human_decision":
            fail_if("blocked_requires_human_decision" not in blocked_reasons, failures, "blocked_human_decision_reason", {"action_id": action_id, "observed": blocked_reasons}, "blocked_requires_human_decision")
        if row.get("classification") == "forbidden_for_current_request":
            fail_if("forbidden_for_current_request" not in blocked_reasons, failures, "forbidden_reason", {"action_id": action_id, "observed": blocked_reasons}, "forbidden_for_current_request")
            fail_if(row.get("current_execution_allowed") is not False, failures, "forbidden_current_execution_allowed_false", {"action_id": action_id, "observed": row.get("current_execution_allowed")}, False)

    return failures


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate enzyme agent execution eligibility matrix")
    parser.add_argument("--matrix", type=Path, default=MATRIX)
    parser.add_argument("--report", type=Path, default=REPORT)
    parser.add_argument("--plan", type=Path, default=PLAN)
    parser.add_argument("--output", type=Path, default=OUT)
    args = parser.parse_args()

    matrix = load_jsonl(args.matrix)
    report = load_json(args.report)
    plan = load_json(args.plan)
    failures = validate_eligibility_matrix_object(matrix, report, plan)

    validation = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "local_only": True,
        "success": not failures,
        "action_rows": len(matrix),
        "current_execution_allowed_rows": report.get("current_execution_allowed_rows"),
        "executed_in_current_trace_rows": report.get("executed_in_current_trace_rows"),
        "receipt_present_rows": report.get("receipt_present_rows"),
        "failures": failures,
        "safe_for_execution_claim": False,
        "safe_for_training_import": False,
        "safe_for_model_claim": False,
        "release_ready": False,
        "policy": "Eligibility validation confirms receipted local execution state and keeps training/model/release claims fail-closed. It does not create formal decisions, authorize training imports, customer delivery, or release.",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(validation, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "success": validation["success"],
        "action_rows": validation["action_rows"],
        "current_execution_allowed_rows": validation["current_execution_allowed_rows"],
        "failures": len(failures),
        "safe_for_model_claim": False,
        "output": str(args.output),
    }, ensure_ascii=False))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
