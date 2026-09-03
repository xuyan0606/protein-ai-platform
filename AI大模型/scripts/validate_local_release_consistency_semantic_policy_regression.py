#!/usr/bin/env python3
"""Exercise semantic policy drift only against temporary contract copies."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Callable


AI_ROOT = Path(__file__).resolve().parents[1]
CONTRACT_MODULE = AI_ROOT / "scripts" / "local_release_consistency_receipt_contract.py"
VALIDATOR = AI_ROOT / "scripts" / "validate_local_release_consistency_semantic_policy.py"
OUTPUT = AI_ROOT / "reports" / "local_release_consistency_semantic_policy_regression_report.json"


def replace_exact(source: str, old: str, new: str) -> str:
    if source.count(old) != 1:
        raise RuntimeError(f"expected one replacement target: {old!r}")
    return source.replace(old, new, 1)


def main() -> int:
    source = CONTRACT_MODULE.read_text(encoding="utf-8")
    cases: list[tuple[str, Callable[[str], str], str]] = [
        (
            "contract_version_drift",
            lambda text: replace_exact(text, 'CONTRACT_VERSION = "local-release-consistency-semantic-input-v1"', 'CONTRACT_VERSION = "local-release-consistency-semantic-input-v2"'),
            "contract_version_exact",
        ),
        (
            "expanded_release_exclusion",
            lambda text: replace_exact(text, '    "local_release_consistency_receipt_current_regression_failed_rows",\n', '    "local_release_consistency_receipt_current_regression_failed_rows",\n    "forged_future_gate",\n'),
            "release_exclusion_fields_exact",
        ),
        (
            "removed_release_exclusion",
            lambda text: replace_exact(text, '    "local_release_fail_closed_consistency_success",\n', ""),
            "release_exclusion_fields_exact",
        ),
        (
            "expanded_data_lake_semantic_exclusion",
            lambda text: replace_exact(text, '    "reports/local_release_consistency_receipt_current_validation_report.json",\n', '    "reports/local_release_consistency_receipt_current_validation_report.json",\n    "reports/forged_post_current_report.json",\n'),
            "data_lake_semantic_excluded_paths_exact",
        ),
        (
            "removed_data_lake_semantic_exclusion",
            lambda text: replace_exact(text, '    "reports/local_release_safety_guard_links_current_regression_report.json",\n', ""),
            "data_lake_semantic_excluded_paths_exact",
        ),
        (
            "release_summary_normalization_field_drift",
            lambda text: replace_exact(text, 'RELEASE_SUMMARY_NORMALIZED_FIELDS = (\n    "data_lake_live_content_integrity_release_input_contract_sha256",', 'RELEASE_SUMMARY_NORMALIZED_FIELDS = (\n    "forged_release_summary_normalized_field",\n    "data_lake_live_content_integrity_release_input_contract_sha256",'),
            "release_summary_normalized_fields_exact",
        ),
        (
            "live_normalization_field_drift",
            lambda text: replace_exact(text, 'LIVE_NORMALIZED_FIELDS = (\n    "release_input_contract_sha256",', 'LIVE_NORMALIZED_FIELDS = (\n    "forged_live_normalized_field",\n    "release_input_contract_sha256",'),
            "live_normalized_fields_exact",
        ),
        (
            "live_projection_field_drift",
            lambda text: replace_exact(text, '    "strict_verified_rows",\n', '    "strict_verified_rows",\n    "forged_live_projection_field",\n'),
            "live_projection_fields_exact",
        ),
        (
            "policy_projection_field_drift",
            lambda text: replace_exact(text, '    "expected_test_vector_sha256",\n    "safe_for_model_claim",', '    "expected_test_vector_sha256",\n    "forged_policy_projection_field",\n    "safe_for_model_claim",'),
            "contract_policy_projection_fields_exact",
        ),
        (
            "canonicalization_drift",
            lambda text: replace_exact(text, '        separators=(",", ":"),\n', '        separators=(", ", ": "),\n'),
            "shared_contract_test_vector_sha256_exact",
        ),
    ]
    results: list[dict[str, object]] = []
    with tempfile.TemporaryDirectory(prefix="local-release-semantic-policy-") as temp_dir:
        root = Path(temp_dir)
        lock_path = root / "policy.lock"
        control_output = root / "control.json"
        control = subprocess.run([sys.executable, str(VALIDATOR), "--contract-module", str(CONTRACT_MODULE), "--output", str(control_output), "--lock-path", str(lock_path)], cwd=AI_ROOT, capture_output=True, text=True, check=False)
        control_report = json.loads(control_output.read_text(encoding="utf-8")) if control_output.exists() else {}
        control_valid = control.returncode == 0 and control_report.get("success") is True
        for index, (case_id, mutate, expected_check) in enumerate(cases, start=1):
            module_path = root / f"case-{index}.py"
            output_path = root / f"case-{index}.json"
            module_path.write_text(mutate(source), encoding="utf-8")
            process = subprocess.run([sys.executable, str(VALIDATOR), "--contract-module", str(module_path), "--output", str(output_path), "--lock-path", str(lock_path)], cwd=AI_ROOT, capture_output=True, text=True, check=False)
            report = json.loads(output_path.read_text(encoding="utf-8")) if output_path.exists() else {}
            checks = [str(row.get("check") or "") for row in report.get("failures") or [] if isinstance(row, dict)]
            results.append({"case_id": case_id, "expected_check": expected_check, "tamper_rejected": process.returncode != 0 and expected_check in checks, "observed_checks": checks})
    passed = sum(bool(row["tamper_rejected"]) for row in results)
    report = {
        "schema_version": 1,
        "mode": "local_release_consistency_semantic_policy_regression",
        "success": control_valid and passed == len(results),
        "isolated_fixture": True,
        "control_valid": control_valid,
        "case_count": len(results),
        "passed_case_count": passed,
        "failed_case_count": len(results) - passed,
        "real_inputs_mutated": False,
        "failure_count": 0 if control_valid and passed == len(results) else 1,
        "failures": [] if control_valid and passed == len(results) else [{"check": "all_cases_pass", "observed": len(results) - passed, "expected": 0}],
        "cases": results,
        "safe_for_model_claim": False,
        "release_ready": False,
    }
    OUTPUT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"success": report["success"], "case_count": report["case_count"], "passed_case_count": passed, "failure_count": report["failure_count"], "real_inputs_mutated": False, "output": str(OUTPUT)}, ensure_ascii=False, sort_keys=True))
    return 0 if report["success"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
