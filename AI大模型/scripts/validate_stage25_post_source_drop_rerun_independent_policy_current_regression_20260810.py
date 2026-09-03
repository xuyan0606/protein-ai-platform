#!/usr/bin/env python3
"""Exercise isolated stale independent-policy report cases."""

from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Callable


AI_ROOT = Path(__file__).resolve().parents[1]
POLICY_SCRIPT = AI_ROOT / "scripts" / "validate_stage25_post_source_drop_rerun_independent_policy_20260810.py"
CURRENT_VALIDATOR = AI_ROOT / "scripts" / "validate_stage25_post_source_drop_rerun_independent_policy_current_20260810.py"
BUILDER = AI_ROOT / "scripts" / "build_stage25_post_source_drop_rerun_receipt_20260806.py"
VALIDATOR = AI_ROOT / "scripts" / "validate_stage25_post_source_drop_rerun_receipt_20260806.py"
RECEIPT = AI_ROOT / "reports" / "stage25_post_source_drop_rerun_receipt_20260806.json"
VALIDATION = AI_ROOT / "reports" / "stage25_post_source_drop_rerun_receipt_validation_20260806.json"
CANONICAL_POLICY_REPORT = AI_ROOT / "reports" / "stage25_post_source_drop_rerun_independent_policy_validation_20260810.json"
CANONICAL_CURRENT_REPORT = AI_ROOT / "reports" / "stage25_post_source_drop_rerun_independent_policy_current_20260810.json"
LOCK_PATH = AI_ROOT / "reports" / ".stage25_post_source_drop_rerun_receipt.lock"
OUTPUT = AI_ROOT / "reports" / "stage25_post_source_drop_rerun_independent_policy_current_regression_20260810.json"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain an object")
    return data


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def run_current(policy_report: Path, policy_script: Path, output: Path) -> tuple[int, dict[str, Any]]:
    process = subprocess.run(
        [
            sys.executable,
            str(CURRENT_VALIDATOR),
            "--policy-report",
            str(policy_report),
            "--policy-script",
            str(policy_script),
            "--builder",
            str(BUILDER),
            "--validator",
            str(VALIDATOR),
            "--receipt",
            str(RECEIPT),
            "--validation",
            str(VALIDATION),
            "--expected-policy-output",
            str(policy_report),
            "--expected-lock-path",
            str(LOCK_PATH),
            "--output",
            str(output),
        ],
        cwd=AI_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    return process.returncode, load_json(output)


def main() -> int:
    protected = [POLICY_SCRIPT, CURRENT_VALIDATOR, BUILDER, VALIDATOR, RECEIPT, VALIDATION, CANONICAL_POLICY_REPORT]
    if CANONICAL_CURRENT_REPORT.is_file():
        protected.append(CANONICAL_CURRENT_REPORT)
    before = {str(path): sha256(path) for path in protected if path.is_file()}
    results: list[dict[str, Any]] = []

    with tempfile.TemporaryDirectory(prefix="stage25-post-source-policy-current-") as temp_name:
        temp_root = Path(temp_name)
        policy_script = temp_root / POLICY_SCRIPT.name
        policy_report = temp_root / "policy.json"
        shutil.copy2(POLICY_SCRIPT, policy_script)
        policy_process = subprocess.run(
            [
                sys.executable,
                str(policy_script),
                "--builder",
                str(BUILDER),
                "--validator",
                str(VALIDATOR),
                "--receipt",
                str(RECEIPT),
                "--validation",
                str(VALIDATION),
                "--output",
                str(policy_report),
            ],
            cwd=AI_ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        baseline_policy = policy_report.read_bytes() if policy_report.is_file() else b""
        baseline_script = policy_script.read_bytes()
        control_output = temp_root / "control-current.json"
        control_rc, control = run_current(policy_report, policy_script, control_output)
        results.append({
            "case": "fixture_control",
            "passed": policy_process.returncode == 0 and control_rc == 0 and control.get("success") is True,
            "policy_returncode": policy_process.returncode,
            "current_returncode": control_rc,
            "failure_count": control.get("failure_count"),
        })

        def recorded(field: str, value: Any) -> Callable[[], None]:
            def apply() -> None:
                data = load_json(policy_report)
                data[field] = value
                write_json(policy_report, data)
            return apply

        cases: list[tuple[str, Callable[[], None], str]] = [
            ("policy_version_drift", recorded("policy_version", "stage25-post-source-drop-independent-policy-v2"), "policy_version_exact"),
            ("expected_command_rows_drift", recorded("expected_command_rows", 63), "command_rows_exact"),
            ("expected_command_vector_drift", recorded("expected_command_test_vector_sha256", "0" * 64), "command_vector_sha256_exact"),
            ("observed_builder_vector_drift", recorded("observed_builder_command_test_vector_sha256", "1" * 64), "builder_command_vector_current"),
            ("observed_receipt_vector_drift", recorded("observed_receipt_command_test_vector_sha256", "2" * 64), "receipt_command_vector_current"),
            ("recorded_policy_script_sha_drift", recorded("policy_script_sha256", "3" * 64), "policy_script_sha256_current"),
            ("live_policy_script_sha_drift", lambda: policy_script.write_bytes(baseline_script + b"\n"), "policy_script_sha256_current"),
            ("builder_sha_drift", recorded("builder_sha256", "4" * 64), "builder_sha256_current"),
            ("validator_sha_drift", recorded("validator_sha256", "5" * 64), "validator_sha256_current"),
            ("receipt_sha_drift", recorded("receipt_sha256", "6" * 64), "receipt_sha256_current"),
            ("validation_sha_drift", recorded("validation_sha256", "7" * 64), "validation_sha256_current"),
            ("policy_output_path_drift", recorded("policy_output_path", "/tmp/non-canonical-policy.json"), "policy_output_path_canonical"),
            ("policy_lock_path_drift", recorded("policy_lock_path", "/tmp/non-canonical-policy.lock"), "policy_lock_path_canonical"),
            ("policy_atomic_commit_drift", recorded("policy_atomic_commit", False), "policy_atomic_commit"),
            ("policy_success_drift", recorded("success", False), "policy_success"),
        ]

        for name, mutation, expected_check in cases:
            policy_report.write_bytes(baseline_policy)
            policy_script.write_bytes(baseline_script)
            mutation()
            case_output = temp_root / f"{name}-current.json"
            returncode, report = run_current(policy_report, policy_script, case_output)
            observed_checks = [row.get("check") for row in report.get("failures", []) if isinstance(row, dict)]
            results.append({
                "case": name,
                "passed": returncode != 0 and report.get("success") is False and expected_check in observed_checks,
                "returncode": returncode,
                "expected_check": expected_check,
                "observed_checks": observed_checks,
            })

    after = {str(path): sha256(path) for path in protected if path.is_file()}
    real_inputs_mutated = before != after
    failed_rows = sum(1 for row in results if not row.get("passed"))
    failures = []
    if failed_rows:
        failures.append({"check": "all_cases_pass", "observed": failed_rows, "expected": 0})
    if real_inputs_mutated:
        failures.append({"check": "real_inputs_unchanged", "observed": {"before": before, "after": after}, "expected": True})

    regression_script = Path(__file__).resolve()
    report = {
        "schema_version": 1,
        "mode": "stage25_post_source_drop_rerun_independent_policy_current_regression",
        "success": not failures,
        "isolated_fixture": True,
        "regression_script_path": str(regression_script),
        "regression_script_sha256": sha256(regression_script),
        "case_count": len(results),
        "passed_case_count": sum(1 for row in results if row.get("passed")),
        "failed_case_count": failed_rows,
        "real_inputs_mutated": real_inputs_mutated,
        "failure_count": len(failures),
        "failures": failures,
        "cases": results,
        "safe_for_model_claim": False,
        "release_ready": False,
    }
    OUTPUT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"success": report["success"], "case_count": report["case_count"], "passed_case_count": report["passed_case_count"], "failure_count": report["failure_count"], "real_inputs_mutated": real_inputs_mutated, "output": str(OUTPUT)}, ensure_ascii=False, sort_keys=True))
    return 0 if report["success"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
