#!/usr/bin/env python3
"""Validate fail-closed structured enzyme agent result outputs."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
RESULT = AI_ROOT / "reports" / "enzyme_agent_result_template.json"
PLAN_VALIDATION = AI_ROOT / "reports" / "enzyme_resource_retrieval_plan_validation_report.json"
OUT = AI_ROOT / "reports" / "enzyme_agent_result_validation_report.json"

REQUIRED_TOP_LEVEL = {
    "result_id",
    "created_at",
    "local_only",
    "source_plan_id",
    "request_class",
    "selected_variants",
    "property_predictions",
    "ddg_results",
    "evidence_summary",
    "manual_review_required",
    "experimental_plan",
    "forbidden_claims",
    "artifact_refs",
    "safe_for_training_import",
    "safe_for_model_claim",
    "release_ready",
}

REQUIRED_EVIDENCE = {
    "reviewed_numbering_rows",
    "claim_eligible_training_rows",
    "strict_msa_site_feature_rows",
    "wet_lab_authorization_rows",
    "resource_plan_validation_success",
}

REQUIRED_FORBIDDEN_CLAIMS = {
    "model_quality_claim",
    "customer_delivery",
    "approved_for_ordering",
    "release_ready",
    "training_import",
    "safe_for_model_claim",
}


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def fail_if(condition: bool, failures: list[dict[str, Any]], check: str, observed: Any, expected: Any) -> None:
    if condition:
        failures.append({"check": check, "observed": observed, "expected": expected})


def validate_result_object(
    result: dict[str, Any],
    plan_validation: dict[str, Any],
    ai_root: Path = AI_ROOT,
) -> tuple[list[dict[str, Any]], list[str], dict[str, Any]]:
    failures: list[dict[str, Any]] = []
    warnings: list[str] = []

    missing_top = sorted(REQUIRED_TOP_LEVEL - set(result))
    if missing_top:
        failures.append({"check": "required_top_level_keys_present", "observed_missing": missing_top, "expected": sorted(REQUIRED_TOP_LEVEL)})

    evidence = result.get("evidence_summary") or {}
    missing_evidence = sorted(REQUIRED_EVIDENCE - set(evidence))
    if missing_evidence:
        failures.append({"check": "required_evidence_keys_present", "observed_missing": missing_evidence, "expected": sorted(REQUIRED_EVIDENCE)})

    fail_if(result.get("local_only") is not True, failures, "local_only_true", result.get("local_only"), True)
    fail_if(result.get("manual_review_required") is not True, failures, "manual_review_required_true", result.get("manual_review_required"), True)
    fail_if(result.get("safe_for_training_import") is not False, failures, "safe_for_training_import_false", result.get("safe_for_training_import"), False)
    fail_if(result.get("safe_for_model_claim") is not False, failures, "safe_for_model_claim_false", result.get("safe_for_model_claim"), False)
    fail_if(result.get("release_ready") is not False, failures, "release_ready_false", result.get("release_ready"), False)
    fail_if(evidence.get("resource_plan_validation_success") is not True, failures, "resource_plan_validation_success_true", evidence.get("resource_plan_validation_success"), True)
    fail_if(plan_validation.get("success") is not True, failures, "source_plan_validation_report_success_true", plan_validation.get("success"), True)
    fail_if(plan_validation.get("safe_for_execution") is not False, failures, "source_plan_safe_for_execution_false", plan_validation.get("safe_for_execution"), False)
    fail_if(plan_validation.get("safe_for_model_claim") is not False, failures, "source_plan_safe_for_model_claim_false", plan_validation.get("safe_for_model_claim"), False)

    for field in ["selected_variants", "property_predictions", "ddg_results", "forbidden_claims", "artifact_refs"]:
        fail_if(not isinstance(result.get(field), list), failures, f"{field}_is_list", type(result.get(field)).__name__, "list")
    fail_if(not isinstance(evidence, dict), failures, "evidence_summary_is_object", type(evidence).__name__, "dict")
    fail_if(not isinstance(result.get("experimental_plan"), dict), failures, "experimental_plan_is_object", type(result.get("experimental_plan")).__name__, "dict")

    artifact_refs = result.get("artifact_refs") if isinstance(result.get("artifact_refs"), list) else []
    fail_if(len(artifact_refs) == 0, failures, "artifact_refs_nonempty", len(artifact_refs), ">0")
    for rel in artifact_refs:
        if not isinstance(rel, str):
            failures.append({"check": "artifact_ref_string", "observed": rel, "expected": "string path"})
            continue
        if not (ai_root / rel).exists():
            failures.append({"check": "artifact_ref_exists", "observed": rel, "expected": "existing local artifact"})

    forbidden_claims = set(result.get("forbidden_claims") or [])
    missing_forbidden = sorted(REQUIRED_FORBIDDEN_CLAIMS - forbidden_claims)
    if missing_forbidden:
        failures.append({"check": "required_forbidden_claims_present", "observed_missing": missing_forbidden, "expected": sorted(REQUIRED_FORBIDDEN_CLAIMS)})

    claim_eligible_rows = int(evidence.get("claim_eligible_training_rows") or 0)
    reviewed_numbering_rows = int(evidence.get("reviewed_numbering_rows") or 0)
    wet_lab_authorization_rows = int(evidence.get("wet_lab_authorization_rows") or 0)
    strict_msa_rows = int(evidence.get("strict_msa_site_feature_rows") or 0)
    if claim_eligible_rows == 0:
        warnings.append("claim_eligible_training_rows_zero")
    if strict_msa_rows == 0:
        warnings.append("strict_msa_site_feature_rows_zero")

    for idx, variant in enumerate(result.get("selected_variants") or []):
        if not isinstance(variant, dict):
            failures.append({"check": "selected_variant_object", "index": idx, "observed": type(variant).__name__, "expected": "object"})
            continue
        fail_if(variant.get("manual_review_required") is not True, failures, "selected_variant_manual_review_required_true", {"index": idx, "observed": variant.get("manual_review_required")}, True)
        recommendation = variant.get("recommendation")
        if recommendation == "go":
            if claim_eligible_rows < 100 or reviewed_numbering_rows < 75 or wet_lab_authorization_rows == 0:
                failures.append({
                    "check": "go_recommendation_requires_reviewed_training_and_authorization_gates",
                    "index": idx,
                    "observed": {
                        "claim_eligible_training_rows": claim_eligible_rows,
                        "reviewed_numbering_rows": reviewed_numbering_rows,
                        "wet_lab_authorization_rows": wet_lab_authorization_rows,
                    },
                    "expected": {
                        "claim_eligible_training_rows": ">=100",
                        "reviewed_numbering_rows": ">=75",
                        "wet_lab_authorization_rows": ">0",
                    },
                })

    for idx, ddg_result in enumerate(result.get("ddg_results") or []):
        if not isinstance(ddg_result, dict):
            failures.append({"check": "ddg_result_object", "index": idx, "observed": type(ddg_result).__name__, "expected": "object"})
            continue
        backend = str(ddg_result.get("backend_family") or "")
        if "Rosetta" in backend or "FoldX" in backend or "PyRosetta" in backend:
            if ddg_result.get("safe_for_model_claim") is not False:
                failures.append({"check": "physics_ddg_safe_for_model_claim_false", "index": idx, "backend_family": backend, "observed": ddg_result.get("safe_for_model_claim"), "expected": False})
            if ddg_result.get("ready") is True and ddg_result.get("usable_for") not in {
                "local_noncommercial_runtime_feature_manual_review_only",
                "manual_review_support_only",
            }:
                failures.append({
                    "check": "physics_ddg_ready_requires_manual_review_only_use",
                    "index": idx,
                    "backend_family": backend,
                    "observed": ddg_result.get("usable_for"),
                    "expected": "local_noncommercial_runtime_feature_manual_review_only",
                })

    metrics = {
        "selected_variant_rows": len(result.get("selected_variants") or []),
        "property_prediction_rows": len(result.get("property_predictions") or []),
        "ddg_result_rows": len(result.get("ddg_results") or []),
        "artifact_ref_count": len(artifact_refs),
        "reviewed_numbering_rows": reviewed_numbering_rows,
        "claim_eligible_training_rows": claim_eligible_rows,
        "strict_msa_site_feature_rows": strict_msa_rows,
        "wet_lab_authorization_rows": wet_lab_authorization_rows,
    }
    return failures, warnings, metrics


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate enzyme agent result schema and safety gates")
    parser.add_argument("--result", type=Path, default=RESULT)
    parser.add_argument("--plan-validation", type=Path, default=PLAN_VALIDATION)
    parser.add_argument("--output", type=Path, default=OUT)
    args = parser.parse_args()

    result = load_json(args.result)
    plan_validation = load_json(args.plan_validation)
    failures, warnings, metrics = validate_result_object(result, plan_validation)

    report = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "local_only": True,
        "success": not failures,
        "result_id": result.get("result_id"),
        **metrics,
        "failures": failures,
        "warnings": warnings,
        "safe_for_training_import": False,
        "safe_for_model_claim": False,
        "release_ready": False,
        "policy": "Structured enzyme agent result validation is fail-closed. Passing this validator only proves the result is safely blocked; it does not approve recommendations, training import, model claims, ordering, or release.",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "success": report["success"],
        "selected_variant_rows": report["selected_variant_rows"],
        "failures": len(failures),
        "safe_for_model_claim": False,
        "output": str(args.output),
    }, ensure_ascii=False))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
