#!/usr/bin/env python3
"""Validate cross-report consistency for fail-closed model-quality claims."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
OUT = AI_ROOT / "reports" / "model_claim_fail_closed_consistency_report.json"

REPORTS = {
    "safe_entry": "reports/safe_training_entrypoint_check.json",
    "repaired": "reports/repaired_supervised_table_report.json",
    "provenance": "reports/label_provenance_audit_report.json",
    "strict_msa": "reports/strict_msa_site_feature_report.json",
    "pseudo_leakage": "reports/no_pseudo_strict_training_leakage_validation_report.json",
    "model_quality": "reports/model_quality_unlock_requirements_report.json",
    "top_tier": "reports/top_tier_model_execution_board.json",
    "top_tier_receipts": "reports/top_tier_model_ready_to_verify_receipt_report.json",
    "top_tier_receipt_validation": "reports/top_tier_model_ready_to_verify_receipt_validation_report.json",
    "non_human": "reports/non_human_construction_board.json",
    "promotion_board": "reports/ready_to_verify_promotion_board.json",
    "promotion_validation": "reports/ready_to_verify_promotion_validation_report.json",
    "promotion_regression": "reports/ready_to_verify_promotion_safety_regression_report.json",
    "claim_matrix": "reports/claim_readiness_matrix.json",
    "wet_lab_unlock": "reports/wet_lab_mutant_library_unlock_status_report.json",
    "release": "reports/local_release_manifest.json",
}

ALLOWED_READY_TO_VERIFY_WITH_ZERO_STRICT_ROWS = {
    "MQ-U003",
}


def load_json(rel_path: str) -> dict[str, Any]:
    path = AI_ROOT / rel_path
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def fail_if(condition: bool, failures: list[dict[str, Any]], check: str, observed: Any, expected: Any) -> None:
    if condition:
        failures.append({"check": check, "observed": observed, "expected": expected})


def find_claim(claim_matrix: dict[str, Any], claim_id: str) -> dict[str, Any]:
    for row in claim_matrix.get("claims") or []:
        if isinstance(row, dict) and row.get("claim_id") == claim_id:
            return row
    return {}


def ready_to_verify_requirement_ids(model_quality: dict[str, Any]) -> set[str]:
    result: set[str] = set()
    for row in model_quality.get("requirements") or []:
        if isinstance(row, dict) and row.get("status") == "ready_to_verify" and row.get("requirement_id"):
            result.add(str(row["requirement_id"]))
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate fail-closed model claim consistency")
    parser.add_argument("--output", type=Path, default=OUT)
    args = parser.parse_args()

    reports = {name: load_json(rel) for name, rel in REPORTS.items()}
    failures: list[dict[str, Any]] = []
    warnings: list[str] = []

    safe_entry = reports["safe_entry"]
    repaired = reports["repaired"]
    provenance = reports["provenance"]
    strict_msa = reports["strict_msa"]
    pseudo_leakage = reports["pseudo_leakage"]
    model_quality = reports["model_quality"]
    top_tier = reports["top_tier"]
    top_tier_receipts = reports["top_tier_receipts"]
    top_tier_receipt_validation = reports["top_tier_receipt_validation"]
    non_human = reports["non_human"]
    promotion_board = reports["promotion_board"]
    promotion_validation = reports["promotion_validation"]
    promotion_regression = reports["promotion_regression"]
    claim_matrix = reports["claim_matrix"]
    wet_lab_unlock = reports["wet_lab_unlock"]
    release = reports["release"]

    strict_rows = int(repaired.get("supervised_rows") or safe_entry.get("rows") or 0)
    claim_eligible_rows = int(provenance.get("claim_eligible_rows") or 0)
    strict_msa_rows = int(strict_msa.get("feature_rows") or 0)
    model_quality_claim = find_claim(claim_matrix, "model_quality_claim")
    five_head_claim = find_claim(claim_matrix, "five_head_training_run")
    ready_requirement_ids = ready_to_verify_requirement_ids(model_quality)

    fail_if(strict_rows != int(provenance.get("strict_rows") or 0), failures, "strict_rows_match_label_provenance", provenance.get("strict_rows"), strict_rows)
    fail_if(strict_rows != int(pseudo_leakage.get("strict_rows") or 0), failures, "strict_rows_match_pseudo_leakage_guard", pseudo_leakage.get("strict_rows"), strict_rows)
    fail_if(claim_eligible_rows != int(safe_entry.get("claim_eligible_rows") or 0), failures, "claim_eligible_rows_match_safe_entry", safe_entry.get("claim_eligible_rows"), claim_eligible_rows)
    fail_if(pseudo_leakage.get("failures") not in ([], None), failures, "pseudo_strict_leakage_guard_has_no_failures", pseudo_leakage.get("failures"), [])
    fail_if(pseudo_leakage.get("safe_for_training_pipeline") is not True, failures, "pseudo_strict_leakage_guard_safe_for_pipeline", pseudo_leakage.get("safe_for_training_pipeline"), True)

    if strict_rows == 0:
        warnings.append("strict_real_source_supervised_rows_zero")
        fail_if(strict_msa_rows != 0, failures, "strict_msa_rows_zero_when_strict_rows_zero", strict_msa_rows, 0)
        fail_if(
            not ready_requirement_ids.issubset(ALLOWED_READY_TO_VERIFY_WITH_ZERO_STRICT_ROWS),
            failures,
            "model_quality_ready_to_verify_limited_when_strict_rows_zero",
            sorted(ready_requirement_ids),
            sorted(ALLOWED_READY_TO_VERIFY_WITH_ZERO_STRICT_ROWS),
        )
        fail_if(
            top_tier.get("ready_to_verify_workstreams") not in {0, 1, 2, 3},
            failures,
            "top_tier_ready_to_verify_limited_when_strict_rows_zero",
            top_tier.get("ready_to_verify_workstreams"),
            "0, 1, 2, or 3 local structure/wet-lab/PyRosetta-ddG receipts only",
        )
        fail_if(
            non_human.get("started_ready_to_verify_workstreams") not in {0, 1, 2, 3},
            failures,
            "non_human_ready_to_verify_limited_when_strict_rows_zero",
            non_human.get("started_ready_to_verify_workstreams"),
            "0, 1, 2, or 3 local engineering receipts only",
        )
        fail_if(
            wet_lab_unlock.get("ready_to_verify_gates") != 7,
            failures,
            "wet_lab_unlock_ready_gates_after_msa_block",
            wet_lab_unlock.get("ready_to_verify_gates"),
            7,
        )

    fail_if(safe_entry.get("safe_for_model_claim") is not False, failures, "safe_entry_model_claim_false", safe_entry.get("safe_for_model_claim"), False)
    fail_if(model_quality.get("model_quality_ready") is not False, failures, "model_quality_ready_false", model_quality.get("model_quality_ready"), False)
    fail_if(model_quality_claim.get("ready") is not False or model_quality_claim.get("allowed") is not False, failures, "model_quality_claim_blocked", {"ready": model_quality_claim.get("ready"), "allowed": model_quality_claim.get("allowed")}, {"ready": False, "allowed": False})
    fail_if(five_head_claim.get("ready") is not False or five_head_claim.get("allowed") is not False, failures, "five_head_training_claim_blocked", {"ready": five_head_claim.get("ready"), "allowed": five_head_claim.get("allowed")}, {"ready": False, "allowed": False})
    fail_if(top_tier.get("current_readiness", {}).get("safe_for_model_claim") is not False, failures, "top_tier_model_claim_false", top_tier.get("current_readiness", {}).get("safe_for_model_claim"), False)
    fail_if(top_tier_receipts.get("safe_for_training_import") is not False, failures, "top_tier_receipts_training_import_false", top_tier_receipts.get("safe_for_training_import"), False)
    fail_if(top_tier_receipts.get("safe_for_model_claim") is not False, failures, "top_tier_receipts_model_claim_false", top_tier_receipts.get("safe_for_model_claim"), False)
    fail_if(top_tier_receipt_validation.get("success") is not True, failures, "top_tier_receipt_validation_success", top_tier_receipt_validation.get("success"), True)
    fail_if(promotion_validation.get("success") is not True or promotion_validation.get("failure_count") != 0, failures, "promotion_validation_success", {"success": promotion_validation.get("success"), "failure_count": promotion_validation.get("failure_count")}, {"success": True, "failure_count": 0})
    fail_if(promotion_regression.get("success") is not True or promotion_regression.get("failed_rows") != 0 or promotion_regression.get("real_inputs_mutated") is not False, failures, "promotion_safety_regression_passed", {"success": promotion_regression.get("success"), "failed_rows": promotion_regression.get("failed_rows"), "real_inputs_mutated": promotion_regression.get("real_inputs_mutated")}, {"success": True, "failed_rows": 0, "real_inputs_mutated": False})
    for field in ("automatic_promotion_rows", "workstream_completion_ready_rows", "execution_ready_rows", "safe_for_training_import_rows", "safe_for_model_claim_rows", "customer_delivery_ready_rows", "release_ready_rows", "selected_variant_rows"):
        fail_if(promotion_board.get(field) != 0, failures, f"promotion_board_{field}_zero", promotion_board.get(field), 0)
    fail_if(wet_lab_unlock.get("safe_for_model_claim") is not False, failures, "wet_lab_unlock_model_claim_false", wet_lab_unlock.get("safe_for_model_claim"), False)
    fail_if(release.get("release_ready") is not False, failures, "release_ready_false", release.get("release_ready"), False)

    report = {
        "local_only": True,
        "checked_reports": REPORTS,
        "strict_rows": strict_rows,
        "claim_eligible_rows": claim_eligible_rows,
        "strict_msa_site_feature_rows": strict_msa_rows,
        "model_quality_ready_to_verify_requirements": model_quality.get("ready_to_verify_requirements"),
        "model_quality_ready_to_verify_requirement_ids": sorted(ready_requirement_ids),
        "top_tier_ready_to_verify_workstreams": top_tier.get("ready_to_verify_workstreams"),
        "non_human_ready_to_verify_workstreams": non_human.get("started_ready_to_verify_workstreams"),
        "wet_lab_unlock_ready_to_verify_gates": wet_lab_unlock.get("ready_to_verify_gates"),
        "top_tier_receipt_valid_rows": top_tier_receipt_validation.get("valid_receipt_rows"),
        "promotion_audit_rows": promotion_board.get("audit_rows"),
        "promotion_local_artifact_completion_rows": promotion_board.get("local_artifact_completion_rows"),
        "promotion_verified_blocked_rows": promotion_board.get("verified_blocked_rows"),
        "promotion_automatic_rows": promotion_board.get("automatic_promotion_rows"),
        "promotion_validation_success": promotion_validation.get("success"),
        "promotion_regression_passed_rows": promotion_regression.get("passed_rows"),
        "claim_matrix_blocked_claims": claim_matrix.get("claims_blocked"),
        "release_ready": release.get("release_ready"),
        "failures": failures,
        "warnings": warnings,
        "success": not failures,
        "safe_for_training_pipeline": not failures,
        "safe_for_model_claim": False,
        "policy": "Cross-report consistency guard. Local ready-to-verify receipts such as MQ-U003 physical ddG may exist, but training import, model-quality claims and release must remain fail-closed until real labels and formal gates pass.",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "success": report["success"],
        "strict_rows": strict_rows,
        "claim_eligible_rows": claim_eligible_rows,
        "failures": len(failures),
        "output": str(args.output),
    }, ensure_ascii=False))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
