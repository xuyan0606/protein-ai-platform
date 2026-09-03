#!/usr/bin/env python3
"""Run positive/negative regressions for enzyme agent execution receipt gates."""

from __future__ import annotations

import argparse
import copy
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from validate_enzyme_agent_execution_receipt_gate import validate_receipt_gate_object


AI_ROOT = Path(__file__).resolve().parents[1]
REPORT = AI_ROOT / "reports" / "enzyme_agent_execution_receipt_gate_report.json"
RECEIPTS = AI_ROOT / "datasets" / "governance" / "enzyme_agent_execution_receipts.local.jsonl"
CASES_OUT = AI_ROOT / "datasets" / "governance" / "enzyme_agent_execution_receipt_safety_regression_cases.jsonl"
OUT = AI_ROOT / "reports" / "enzyme_agent_execution_receipt_safety_regression_report.json"


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def good_receipt(action_id: str = "act_msa_conservation") -> dict[str, Any]:
    return {
        "receipt_id": f"receipt_{action_id}_regression_fixture",
        "created_at": "2026-07-31T00:00:00+00:00",
        "local_only": True,
        "trace_id": "enzyme_agent_trace_20260731_p170",
        "plan_id": "enzyme_resource_retrieval_plan_20260731_p167",
        "action_id": action_id,
        "tool_contract_id": "tool_msa_mmseqs_cache_validate",
        "execution_mode": "local_script",
        "human_confirmation_ref": "regression_fixture_only",
        "input_artifacts": ["reports/enzyme_resource_retrieval_plan_report.json"],
        "output_artifacts": ["reports/enzyme_agent_execution_receipt_gate_report.json"],
        "validator_artifacts": ["reports/enzyme_agent_execution_receipt_gate_validation_report.json"],
        "return_status": "executed_passed",
        "writes_formal_decision": False,
        "writes_training_rows": False,
        "safe_for_training_import": False,
        "safe_for_model_claim": False,
        "release_ready": False,
    }


def mutate_case(base_report: dict[str, Any], case_id: str) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    report = copy.deepcopy(base_report)
    receipts: list[dict[str, Any]] = []
    if case_id == "bad_executed_action_missing_receipt":
        report["executed_action_ids"] = ["act_msa_conservation"]
        report["executed_action_count"] = 1
        report["receipt_rows"] = 0
        report["missing_receipt_action_ids"] = ["act_msa_conservation"]
    elif case_id == "bad_unexpected_receipt_without_execution":
        receipt = good_receipt()
        receipts = [receipt]
        report["executed_action_ids"] = []
        report["executed_action_count"] = 0
        report["receipt_rows"] = 1
        report["receipt_action_ids"] = [receipt["action_id"]]
        report["unexpected_receipt_action_ids"] = [receipt["action_id"]]
    elif case_id == "bad_receipt_model_claim_true":
        receipt = good_receipt()
        receipt["safe_for_model_claim"] = True
        receipts = [receipt]
        report["executed_action_ids"] = [receipt["action_id"]]
        report["executed_action_count"] = 1
        report["receipt_rows"] = 1
        report["receipt_action_ids"] = [receipt["action_id"]]
        report["missing_receipt_action_ids"] = []
        report["unexpected_receipt_action_ids"] = []
    elif case_id == "bad_receipt_training_import_true":
        receipt = good_receipt()
        receipt["safe_for_training_import"] = True
        receipts = [receipt]
        report["executed_action_ids"] = [receipt["action_id"]]
        report["executed_action_count"] = 1
        report["receipt_rows"] = 1
        report["receipt_action_ids"] = [receipt["action_id"]]
        report["missing_receipt_action_ids"] = []
        report["unexpected_receipt_action_ids"] = []
    elif case_id == "bad_receipt_release_ready_true":
        receipt = good_receipt()
        receipt["release_ready"] = True
        receipts = [receipt]
        report["executed_action_ids"] = [receipt["action_id"]]
        report["executed_action_count"] = 1
        report["receipt_rows"] = 1
        report["receipt_action_ids"] = [receipt["action_id"]]
        report["missing_receipt_action_ids"] = []
        report["unexpected_receipt_action_ids"] = []
    elif case_id == "bad_executed_passed_without_output_artifacts":
        receipt = good_receipt()
        receipt["output_artifacts"] = []
        receipts = [receipt]
        report["executed_action_ids"] = [receipt["action_id"]]
        report["executed_action_count"] = 1
        report["receipt_rows"] = 1
        report["receipt_action_ids"] = [receipt["action_id"]]
        report["missing_receipt_action_ids"] = []
        report["unexpected_receipt_action_ids"] = []
    elif case_id == "bad_executed_passed_without_validator_artifacts":
        receipt = good_receipt()
        receipt["validator_artifacts"] = []
        receipts = [receipt]
        report["executed_action_ids"] = [receipt["action_id"]]
        report["executed_action_count"] = 1
        report["receipt_rows"] = 1
        report["receipt_action_ids"] = [receipt["action_id"]]
        report["missing_receipt_action_ids"] = []
        report["unexpected_receipt_action_ids"] = []
    elif case_id == "bad_report_safe_for_execution_claim_true":
        report["safe_for_execution_claim"] = True
    elif case_id == "bad_report_model_claim_true":
        report["safe_for_model_claim"] = True
    elif case_id == "bad_receipt_missing_required_field":
        receipt = good_receipt()
        del receipt["tool_contract_id"]
        receipts = [receipt]
        report["executed_action_ids"] = [receipt["action_id"]]
        report["executed_action_count"] = 1
        report["receipt_rows"] = 1
        report["receipt_action_ids"] = [receipt["action_id"]]
        report["missing_receipt_action_ids"] = []
        report["unexpected_receipt_action_ids"] = []
    else:
        raise ValueError(f"unknown regression case: {case_id}")
    return report, receipts


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate enzyme agent execution receipt safety regressions")
    parser.add_argument("--report", type=Path, default=REPORT)
    parser.add_argument("--receipts", type=Path, default=RECEIPTS)
    parser.add_argument("--cases-output", type=Path, default=CASES_OUT)
    parser.add_argument("--output", type=Path, default=OUT)
    args = parser.parse_args()

    base_report = load_json(args.report)
    base_receipts = load_jsonl(args.receipts)
    negative_case_ids = [
        "bad_executed_action_missing_receipt",
        "bad_unexpected_receipt_without_execution",
        "bad_receipt_model_claim_true",
        "bad_receipt_training_import_true",
        "bad_receipt_release_ready_true",
        "bad_executed_passed_without_output_artifacts",
        "bad_executed_passed_without_validator_artifacts",
        "bad_report_safe_for_execution_claim_true",
        "bad_report_model_claim_true",
        "bad_receipt_missing_required_field",
    ]

    case_rows: list[dict[str, Any]] = []
    results: list[dict[str, Any]] = []

    positive_failures = validate_receipt_gate_object(base_report, base_receipts)
    positive_passed = not positive_failures
    case_rows.append({
        "case_id": "positive_current_receipted_execution_gate",
        "expected_valid": True,
        "description": "Current receipted execution gate must validate.",
        "mutations": [],
    })
    results.append({
        "case_id": "positive_current_receipted_execution_gate",
        "expected_valid": True,
        "actual_valid": positive_passed,
        "expected_outcome_met": positive_passed is True,
        "failure_checks": [failure.get("check") for failure in positive_failures],
    })

    for case_id in negative_case_ids:
        report, receipts = mutate_case(base_report, case_id)
        failures = validate_receipt_gate_object(report, receipts)
        actual_valid = not failures
        case_rows.append({
            "case_id": case_id,
            "expected_valid": False,
            "description": "Mutated execution receipt gate state must be rejected.",
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
    report = {
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
        "policy": "Regression suite proves execution receipt validation rejects unsafe execution claims and malformed receipts. It does not execute any action or authorize training/model/release claims.",
    }
    write_jsonl(args.cases_output, case_rows)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "success": report["success"],
        "case_rows": report["case_rows"],
        "actual_rejected_negative_cases": report["actual_rejected_negative_cases"],
        "failed_regression_cases": report["failed_regression_cases"],
        "safe_for_model_claim": False,
        "output": str(args.output),
    }, ensure_ascii=False))
    return 0 if report["success"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
