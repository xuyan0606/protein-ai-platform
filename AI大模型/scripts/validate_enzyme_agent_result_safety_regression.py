#!/usr/bin/env python3
"""Run positive/negative safety regressions for structured enzyme agent results."""

from __future__ import annotations

import argparse
import copy
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from validate_enzyme_agent_result_schema import validate_result_object


AI_ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = AI_ROOT / "reports" / "enzyme_agent_result_template.json"
PLAN_VALIDATION = AI_ROOT / "reports" / "enzyme_resource_retrieval_plan_validation_report.json"
CASES_OUT = AI_ROOT / "datasets" / "governance" / "enzyme_agent_result_safety_regression_cases.jsonl"
OUT = AI_ROOT / "reports" / "enzyme_agent_result_safety_regression_report.json"


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def mutate_case(base: dict[str, Any], case_id: str) -> dict[str, Any]:
    result = copy.deepcopy(base)
    result["result_id"] = f"{base.get('result_id')}_{case_id}"
    if case_id == "bad_go_recommendation_low_evidence":
        result["selected_variants"] = [
            {
                "variant": "E331Q",
                "recommendation": "go",
                "evidence_level": "draft",
                "manual_review_required": True,
                "artifact_refs": ["reports/enzyme_agent_result_template.json"],
            }
        ]
    elif case_id == "bad_selected_variant_no_manual_review":
        result["selected_variants"] = [
            {
                "variant": "E331Q",
                "recommendation": "watch",
                "evidence_level": "draft",
                "manual_review_required": False,
                "artifact_refs": ["reports/enzyme_agent_result_template.json"],
            }
        ]
    elif case_id == "bad_training_import_true":
        result["safe_for_training_import"] = True
    elif case_id == "bad_model_claim_true":
        result["safe_for_model_claim"] = True
    elif case_id == "bad_release_ready_true":
        result["release_ready"] = True
    elif case_id == "bad_missing_required_forbidden_claim":
        result["forbidden_claims"] = [claim for claim in result.get("forbidden_claims", []) if claim != "model_quality_claim"]
    elif case_id == "bad_artifact_refs_empty":
        result["artifact_refs"] = []
    elif case_id == "bad_manual_review_false":
        result["manual_review_required"] = False
    elif case_id == "bad_resource_plan_validation_false":
        result.setdefault("evidence_summary", {})["resource_plan_validation_success"] = False
    elif case_id == "bad_physics_ddg_claim":
        for row in result.get("ddg_results", []):
            if "Rosetta" in str(row.get("backend_family", "")):
                row["ready"] = True
                row["safe_for_model_claim"] = True
                row["usable_for"] = "model_quality_claim"
    else:
        raise ValueError(f"unknown regression case: {case_id}")
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate enzyme agent result safety regressions")
    parser.add_argument("--template", type=Path, default=TEMPLATE)
    parser.add_argument("--plan-validation", type=Path, default=PLAN_VALIDATION)
    parser.add_argument("--cases-output", type=Path, default=CASES_OUT)
    parser.add_argument("--output", type=Path, default=OUT)
    args = parser.parse_args()

    template = load_json(args.template)
    plan_validation = load_json(args.plan_validation)
    negative_case_ids = [
        "bad_go_recommendation_low_evidence",
        "bad_selected_variant_no_manual_review",
        "bad_training_import_true",
        "bad_model_claim_true",
        "bad_release_ready_true",
        "bad_missing_required_forbidden_claim",
        "bad_artifact_refs_empty",
        "bad_manual_review_false",
        "bad_resource_plan_validation_false",
        "bad_physics_ddg_claim",
    ]

    case_rows: list[dict[str, Any]] = []
    results: list[dict[str, Any]] = []

    positive_failures, positive_warnings, positive_metrics = validate_result_object(template, plan_validation)
    positive_passed = not positive_failures
    case_rows.append({
        "case_id": "positive_current_template",
        "expected_valid": True,
        "description": "Current fail-closed template must validate.",
        "mutations": [],
    })
    results.append({
        "case_id": "positive_current_template",
        "expected_valid": True,
        "actual_valid": positive_passed,
        "expected_outcome_met": positive_passed is True,
        "failure_checks": [failure.get("check") for failure in positive_failures],
        "warning_count": len(positive_warnings),
        "metrics": positive_metrics,
    })

    for case_id in negative_case_ids:
        mutated = mutate_case(template, case_id)
        failures, warnings, metrics = validate_result_object(mutated, plan_validation)
        actual_valid = not failures
        case_rows.append({
            "case_id": case_id,
            "expected_valid": False,
            "description": "Mutated result must be rejected by the fail-closed result validator.",
            "mutations": [case_id],
        })
        results.append({
            "case_id": case_id,
            "expected_valid": False,
            "actual_valid": actual_valid,
            "expected_outcome_met": actual_valid is False,
            "failure_checks": [failure.get("check") for failure in failures],
            "warning_count": len(warnings),
            "metrics": metrics,
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
        "safe_for_training_import": False,
        "safe_for_model_claim": False,
        "release_ready": False,
        "policy": "Regression suite proves the structured result validator rejects unsafe result mutations. It does not approve any recommendation, training import, model claim, customer delivery, or release.",
    }
    write_jsonl(args.cases_output, case_rows)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "success": report["success"],
        "case_rows": report["case_rows"],
        "actual_rejected_negative_cases": report["actual_rejected_negative_cases"],
        "failed_regression_cases": report["failed_regression_cases"],
        "output": str(args.output),
    }, ensure_ascii=False))
    return 0 if report["success"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
