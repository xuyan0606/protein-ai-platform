#!/usr/bin/env python3
"""Prove local release binds contract-policy evidence to the current module."""

from __future__ import annotations

import copy
import hashlib
import json
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

try:
    from validate_local_release_live_integrity_binding_regression import prepare_control_fixture
except ModuleNotFoundError:
    from scripts.validate_local_release_live_integrity_binding_regression import prepare_control_fixture


AI_ROOT = Path(__file__).resolve().parents[1]
RELEASE = AI_ROOT / "reports" / "local_release_manifest.json"
DATA_LAKE = AI_ROOT / "reports" / "data_lake_manifest.json"
LIVE_INTEGRITY = AI_ROOT / "reports" / "data_lake_live_content_integrity_validation_report.json"
CONTRACT_POLICY = AI_ROOT / "reports" / "data_lake_release_input_contract_policy_validation_report.json"
CONTRACT_MODULE = AI_ROOT / "scripts" / "data_lake_release_input_contract.py"
VALIDATOR = AI_ROOT / "scripts" / "validate_local_release_manifest_fail_closed_consistency.py"
OUTPUT = AI_ROOT / "reports" / "local_release_contract_policy_binding_regression_report.json"


def prepare_policy_fixture(release: dict[str, Any], policy: dict[str, Any]) -> None:
    policy["success"] = True
    policy["failure_count"] = 0
    policy["failures"] = []
    policy["contract_module_path"] = str(CONTRACT_MODULE.resolve())
    policy["contract_module_sha256"] = hashlib.sha256(CONTRACT_MODULE.read_bytes()).hexdigest()
    summary = release.setdefault("readiness_summary", {})
    summary.update({
        "release_input_contract_policy_success": True,
        "release_input_contract_policy_failures": 0,
        "release_input_contract_policy_module_path": policy.get("contract_module_path"),
        "release_input_contract_policy_module_sha256": policy.get("contract_module_sha256"),
        "release_input_contract_policy_expected_version": policy.get("expected_contract_version"),
        "release_input_contract_policy_expected_excluded_paths": policy.get("expected_excluded_paths"),
        "release_input_contract_policy_expected_test_vector_sha256": policy.get("expected_test_vector_sha256"),
        "local_release_contract_policy_binding_regression_success": True,
        "local_release_contract_policy_binding_regression_failed_rows": 0,
    })


def main() -> int:
    baseline_release = json.loads(RELEASE.read_text(encoding="utf-8"))
    baseline_data_lake = json.loads(DATA_LAKE.read_text(encoding="utf-8"))
    baseline_live = json.loads(LIVE_INTEGRITY.read_text(encoding="utf-8"))
    baseline_policy = json.loads(CONTRACT_POLICY.read_text(encoding="utf-8"))

    def stale_module_sha(release: dict[str, Any], policy: dict[str, Any]) -> None:
        policy["contract_module_sha256"] = "0" * 64

    def summary_module_sha_drift(release: dict[str, Any], policy: dict[str, Any]) -> None:
        release.setdefault("readiness_summary", {})["release_input_contract_policy_module_sha256"] = "f" * 64

    def noncanonical_module_path(release: dict[str, Any], policy: dict[str, Any]) -> None:
        policy["contract_module_path"] = "/tmp/forged-contract-module.py"

    def test_vector_policy_drift(release: dict[str, Any], policy: dict[str, Any]) -> None:
        policy["expected_test_vector_sha256"] = "0" * 64

    cases: list[tuple[str, Callable[[dict[str, Any], dict[str, Any]], None], str]] = [
        ("stale_policy_module_sha", stale_module_sha, "contract_policy_module_sha256_current"),
        ("release_summary_module_sha_drift", summary_module_sha_drift, "contract_policy_summary_matches_report"),
        ("noncanonical_policy_module_path", noncanonical_module_path, "contract_policy_module_path_canonical"),
        ("policy_test_vector_sha_drift", test_vector_policy_drift, "contract_policy_test_vector_sha256_exact"),
    ]
    results: list[dict[str, Any]] = []

    with tempfile.TemporaryDirectory(prefix="release-contract-policy-binding-") as temp_dir:
        temp_root = Path(temp_dir)
        data_lake_path = temp_root / "data-lake.json"
        data_lake_path.write_text(json.dumps(baseline_data_lake, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        prepare_control_fixture(baseline_release, baseline_data_lake, baseline_live, data_lake_path)
        prepare_policy_fixture(baseline_release, baseline_policy)

        def run_validation(index: str, release: dict[str, Any], policy: dict[str, Any]) -> tuple[subprocess.CompletedProcess[str], dict[str, Any]]:
            release_path = temp_root / f"{index}-release.json"
            live_path = temp_root / f"{index}-live.json"
            policy_path = temp_root / f"{index}-policy.json"
            report_path = temp_root / f"{index}-validation.json"
            release_path.write_text(json.dumps(release, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            live_path.write_text(json.dumps(baseline_live, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            policy_path.write_text(json.dumps(policy, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            process = subprocess.run(
                [
                    sys.executable,
                    str(VALIDATOR),
                    "--release", str(release_path),
                    "--data-lake", str(data_lake_path),
                    "--live-integrity", str(live_path),
                    "--contract-policy", str(policy_path),
                    "--output", str(report_path),
                ],
                cwd=AI_ROOT,
                text=True,
                capture_output=True,
                timeout=300,
            )
            validation = json.loads(report_path.read_text(encoding="utf-8")) if report_path.exists() else {}
            return process, validation

        control, control_validation = run_validation("control", baseline_release, baseline_policy)
        control_valid = control.returncode == 0 and control_validation.get("success") is True
        for index, (case_id, mutate, expected_check) in enumerate(cases, start=1):
            release = copy.deepcopy(baseline_release)
            policy = copy.deepcopy(baseline_policy)
            mutate(release, policy)
            process, validation = run_validation(f"case-{index}", release, policy)
            checks = [str(item.get("check") or "") for item in validation.get("failures") or []]
            results.append({
                "case_id": case_id,
                "tamper_rejected": process.returncode != 0 and expected_check in checks,
                "expected_check": expected_check,
                "expected_check_observed": expected_check in checks,
                "failure_count": len(validation.get("failures") or []),
            })

    passed = sum(row["tamper_rejected"] for row in results)
    report = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "success": control_valid and passed == len(results),
        "isolated_fixture": True,
        "control_valid": control_valid,
        "case_rows": len(results),
        "passed_rows": passed,
        "failed_rows": len(results) - passed,
        "real_inputs_mutated": False,
        "results": results,
        "safe_for_model_claim": False,
        "release_ready": False,
        "policy": "Temporary policy/release fixtures only; canonical module and reports remain unchanged.",
    }
    OUTPUT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "success": report["success"],
        "control_valid": report["control_valid"],
        "case_rows": report["case_rows"],
        "passed_rows": report["passed_rows"],
        "failed_rows": report["failed_rows"],
        "real_inputs_mutated": report["real_inputs_mutated"],
        "output": str(OUTPUT),
    }, ensure_ascii=False))
    return 0 if report["success"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
