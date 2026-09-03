#!/usr/bin/env python3
"""Run regressions for enzyme agent execution eligibility matrix gates."""

from __future__ import annotations

import argparse
import copy
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from validate_enzyme_agent_execution_eligibility_matrix import validate_eligibility_matrix_object


AI_ROOT = Path(__file__).resolve().parents[1]
MATRIX = AI_ROOT / "datasets" / "governance" / "enzyme_agent_execution_eligibility_matrix.jsonl"
REPORT = AI_ROOT / "reports" / "enzyme_agent_execution_eligibility_matrix_report.json"
PLAN = AI_ROOT / "reports" / "enzyme_resource_retrieval_plan_report.json"
CASES_OUT = AI_ROOT / "datasets" / "governance" / "enzyme_agent_execution_eligibility_safety_regression_cases.jsonl"
OUT = AI_ROOT / "reports" / "enzyme_agent_execution_eligibility_safety_regression_report.json"


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def first_row(matrix: list[dict[str, Any]], classification: str | None = None) -> dict[str, Any]:
    for row in matrix:
        if classification is None or row.get("classification") == classification:
            return row
    raise ValueError(f"no matrix row for classification={classification}")


def mutate_case(
    base_matrix: list[dict[str, Any]],
    base_report: dict[str, Any],
    case_id: str,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    matrix = copy.deepcopy(base_matrix)
    report = copy.deepcopy(base_report)
    if case_id == "bad_report_allowed_rows_positive":
        report["current_execution_allowed_rows"] = (report.get("current_execution_allowed_rows") or 0) + 1
    elif case_id == "bad_row_current_execution_allowed_true":
        row = first_row(matrix, "blocked_requires_human_decision")
        row["current_execution_allowed"] = True
        row["receipt_status"] = "executed_passed"
        row["receipt_present"] = True
    elif case_id == "bad_row_executed_in_current_trace_true":
        row = first_row(matrix, "executable_after_user_confirmation")
        row["executed_in_current_trace"] = True
        row["receipt_present"] = False
    elif case_id == "bad_row_receipt_present_true":
        row = first_row(matrix, "executable_after_user_confirmation")
        row["current_execution_allowed"] = True
        row["receipt_present"] = True
        row["receipt_status"] = "executed_failed"
    elif case_id == "bad_row_model_claim_true":
        first_row(matrix)["safe_for_model_claim"] = True
    elif case_id == "bad_row_training_import_true":
        first_row(matrix)["safe_for_training_import"] = True
    elif case_id == "bad_row_release_ready_true":
        first_row(matrix)["release_ready"] = True
    elif case_id == "bad_row_writes_training_rows_true":
        first_row(matrix)["writes_training_rows"] = True
    elif case_id == "bad_executable_missing_confirmation_reason":
        row = first_row(matrix, "executable_after_user_confirmation")
        row["blocked_reasons"] = [reason for reason in row.get("blocked_reasons", []) if reason != "requires_explicit_user_confirmation"]
    elif case_id == "bad_blocked_missing_human_reason":
        row = first_row(matrix, "blocked_requires_human_decision")
        row["blocked_reasons"] = [reason for reason in row.get("blocked_reasons", []) if reason != "blocked_requires_human_decision"]
    elif case_id == "bad_forbidden_missing_forbidden_reason":
        row = first_row(matrix, "forbidden_for_current_request")
        row["blocked_reasons"] = [reason for reason in row.get("blocked_reasons", []) if reason != "forbidden_for_current_request"]
    elif case_id == "bad_report_safe_for_execution_claim_true":
        report["safe_for_execution_claim"] = True
    elif case_id == "bad_receipt_regression_failed_cases_positive":
        report["receipt_safety_regression_failed_cases"] = 1
    else:
        raise ValueError(f"unknown regression case: {case_id}")
    return matrix, report


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate enzyme agent execution eligibility safety regressions")
    parser.add_argument("--matrix", type=Path, default=MATRIX)
    parser.add_argument("--report", type=Path, default=REPORT)
    parser.add_argument("--plan", type=Path, default=PLAN)
    parser.add_argument("--cases-output", type=Path, default=CASES_OUT)
    parser.add_argument("--output", type=Path, default=OUT)
    args = parser.parse_args()

    matrix = load_jsonl(args.matrix)
    report = load_json(args.report)
    plan = load_json(args.plan)
    negative_case_ids = [
        "bad_report_allowed_rows_positive",
        "bad_row_current_execution_allowed_true",
        "bad_row_executed_in_current_trace_true",
        "bad_row_receipt_present_true",
        "bad_row_model_claim_true",
        "bad_row_training_import_true",
        "bad_row_release_ready_true",
        "bad_row_writes_training_rows_true",
        "bad_executable_missing_confirmation_reason",
        "bad_blocked_missing_human_reason",
        "bad_forbidden_missing_forbidden_reason",
        "bad_report_safe_for_execution_claim_true",
        "bad_receipt_regression_failed_cases_positive",
    ]

    case_rows: list[dict[str, Any]] = []
    results: list[dict[str, Any]] = []

    positive_failures = validate_eligibility_matrix_object(matrix, report, plan)
    positive_passed = not positive_failures
    case_rows.append({
        "case_id": "positive_current_receipted_eligibility_matrix",
        "expected_valid": True,
        "description": "Current eligibility matrix with authorized receipted local execution must validate.",
        "mutations": [],
    })
    results.append({
        "case_id": "positive_current_receipted_eligibility_matrix",
        "expected_valid": True,
        "actual_valid": positive_passed,
        "expected_outcome_met": positive_passed is True,
        "failure_checks": [failure.get("check") for failure in positive_failures],
    })

    for case_id in negative_case_ids:
        mutated_matrix, mutated_report = mutate_case(matrix, report, case_id)
        failures = validate_eligibility_matrix_object(mutated_matrix, mutated_report, plan)
        actual_valid = not failures
        case_rows.append({
            "case_id": case_id,
            "expected_valid": False,
            "description": "Mutated execution eligibility state must be rejected.",
            "mutations": [case_id],
        })
        results.append({
            "case_id": case_id,
            "expected_valid": False,
            "actual_valid": actual_valid,
            "expected_outcome_met": actual_valid is False,
            "failure_checks": [failure.get("check") for failure in failures],
        })

    failed_regressions = [row for row in results if not row["expected_outcome_met"]]
    report_out = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "local_only": True,
        "case_rows": len(results),
        "positive_cases": 1,
        "negative_cases": len(negative_case_ids),
        "expected_rejected_negative_cases": len(negative_case_ids),
        "actual_rejected_negative_cases": sum(1 for row in results if row["expected_valid"] is False and row["actual_valid"] is False),
        "failed_regression_cases": len(failed_regressions),
        "success": not failed_regressions,
        "cases": results,
        "cases_artifact": str(args.cases_output.relative_to(AI_ROOT)),
        "safe_for_execution_claim": False,
        "safe_for_training_import": False,
        "safe_for_model_claim": False,
        "release_ready": False,
        "policy": "Regression suite proves execution eligibility validation rejects unsafe eligibility changes after the receipted execution wave. It does not execute any action or authorize training/model/release claims.",
    }
    write_jsonl(args.cases_output, case_rows)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report_out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "success": report_out["success"],
        "case_rows": report_out["case_rows"],
        "actual_rejected_negative_cases": report_out["actual_rejected_negative_cases"],
        "failed_regression_cases": report_out["failed_regression_cases"],
        "safe_for_model_claim": False,
        "output": str(args.output),
    }, ensure_ascii=False))
    return 0 if report_out["success"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
