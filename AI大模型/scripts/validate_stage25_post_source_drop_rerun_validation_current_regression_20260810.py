#!/usr/bin/env python3
"""Exercise isolated stale-validation cases for the post-source receipt."""

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
BUILDER = AI_ROOT / "scripts" / "build_stage25_post_source_drop_rerun_receipt_20260806.py"
VALIDATOR = AI_ROOT / "scripts" / "validate_stage25_post_source_drop_rerun_receipt_20260806.py"
CURRENT_VALIDATOR = AI_ROOT / "scripts" / "validate_stage25_post_source_drop_rerun_validation_current_20260810.py"
CANONICAL_RECEIPT = AI_ROOT / "reports" / "stage25_post_source_drop_rerun_receipt_20260806.json"
CANONICAL_VALIDATION = AI_ROOT / "reports" / "stage25_post_source_drop_rerun_receipt_validation_20260806.json"
OUTPUT = AI_ROOT / "reports" / "stage25_post_source_drop_rerun_validation_current_regression_20260810.json"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain an object")
    return data


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def run_current(
    validation: Path,
    receipt: Path,
    validator: Path,
    lock_path: Path,
    output: Path,
) -> tuple[int, dict[str, Any]]:
    process = subprocess.run(
        [
            sys.executable,
            str(CURRENT_VALIDATOR),
            "--validation",
            str(validation),
            "--receipt",
            str(receipt),
            "--validator",
            str(validator),
            "--expected-validation-output",
            str(validation),
            "--expected-lock-path",
            str(lock_path),
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
    protected = [BUILDER, VALIDATOR, CURRENT_VALIDATOR, CANONICAL_RECEIPT, CANONICAL_VALIDATION]
    before = {str(path): sha256(path) for path in protected if path.is_file()}
    case_results: list[dict[str, Any]] = []

    with tempfile.TemporaryDirectory(prefix="stage25-post-source-validation-current-") as temp_name:
        fixture_root = Path(temp_name) / "AI大模型"
        scripts = fixture_root / "scripts"
        reports = fixture_root / "reports"
        scripts.mkdir(parents=True)
        reports.mkdir(parents=True)
        fixture_builder = scripts / BUILDER.name
        fixture_validator = scripts / VALIDATOR.name
        fixture_receipt = reports / CANONICAL_RECEIPT.name
        fixture_validation = reports / CANONICAL_VALIDATION.name
        fixture_lock = reports / ".stage25_post_source_drop_rerun_receipt.lock"
        shutil.copy2(BUILDER, fixture_builder)
        shutil.copy2(VALIDATOR, fixture_validator)

        build = subprocess.run([sys.executable, str(fixture_builder)], cwd=fixture_root, capture_output=True, text=True, check=False)
        validate = subprocess.run([sys.executable, str(fixture_validator)], cwd=fixture_root, capture_output=True, text=True, check=False)
        if build.returncode != 0 or validate.returncode != 0:
            case_results.append({
                "case": "fixture_control",
                "passed": False,
                "reason": {"builder_returncode": build.returncode, "validator_returncode": validate.returncode, "builder_stderr": build.stderr[-500:], "validator_stderr": validate.stderr[-500:]},
            })
        else:
            baseline_receipt = fixture_receipt.read_bytes()
            baseline_validation = fixture_validation.read_bytes()
            baseline_validator = fixture_validator.read_bytes()
            control_output = reports / "control_current.json"
            returncode, control = run_current(fixture_validation, fixture_receipt, fixture_validator, fixture_lock, control_output)
            case_results.append({
                "case": "fixture_control",
                "passed": returncode == 0 and control.get("success") is True and control.get("failure_count") == 0,
                "returncode": returncode,
                "failure_count": control.get("failure_count"),
            })

            def recorded(field: str, value: Any) -> Callable[[], None]:
                def apply() -> None:
                    data = load_json(fixture_validation)
                    data[field] = value
                    write_json(fixture_validation, data)
                return apply

            cases: list[tuple[str, Callable[[], None], str]] = [
                ("recorded_receipt_sha_drift", recorded("receipt_sha256", "0" * 64), "receipt_sha256_current"),
                ("live_receipt_sha_drift", lambda: write_json(fixture_receipt, {**load_json(fixture_receipt), "tampered_after_validation": True}), "receipt_sha256_current"),
                ("recorded_validator_sha_drift", recorded("validator_script_sha256", "1" * 64), "validator_script_sha256_current"),
                ("live_validator_sha_drift", lambda: fixture_validator.write_bytes(baseline_validator + b"\n"), "validator_script_sha256_current"),
                ("receipt_path_drift", recorded("receipt_path", "/tmp/non-canonical-receipt.json"), "receipt_path_current"),
                ("validator_path_drift", recorded("validator_script_path", "/tmp/non-canonical-validator.py"), "validator_script_path_current"),
                ("validation_output_path_drift", recorded("validation_output_path", "/tmp/non-canonical-validation.json"), "validation_output_path_canonical"),
                ("validation_lock_path_drift", recorded("validation_lock_path", "/tmp/non-canonical-validation.lock"), "validation_lock_path_canonical"),
                ("validation_atomic_commit_drift", recorded("validation_atomic_commit", False), "validation_atomic_commit"),
                ("validation_success_drift", recorded("success", False), "validation_success"),
            ]

            for name, mutation, expected_check in cases:
                fixture_receipt.write_bytes(baseline_receipt)
                fixture_validation.write_bytes(baseline_validation)
                fixture_validator.write_bytes(baseline_validator)
                mutation()
                case_output = reports / f"{name}_current.json"
                returncode, report = run_current(fixture_validation, fixture_receipt, fixture_validator, fixture_lock, case_output)
                observed_checks = [row.get("check") for row in report.get("failures", []) if isinstance(row, dict)]
                case_results.append({
                    "case": name,
                    "passed": returncode != 0 and report.get("success") is False and expected_check in observed_checks,
                    "returncode": returncode,
                    "expected_check": expected_check,
                    "observed_checks": observed_checks,
                })

    after = {str(path): sha256(path) for path in protected if path.is_file()}
    real_inputs_mutated = before != after
    failed_rows = sum(1 for row in case_results if not row.get("passed"))
    failures = []
    if failed_rows:
        failures.append({"check": "all_cases_pass", "observed": failed_rows, "expected": 0})
    if real_inputs_mutated:
        failures.append({"check": "real_inputs_unchanged", "observed": {"before": before, "after": after}, "expected": True})

    regression_script = Path(__file__).resolve()
    report = {
        "schema_version": 1,
        "mode": "stage25_post_source_drop_rerun_validation_current_regression",
        "success": not failures,
        "isolated_fixture": True,
        "regression_script_path": str(regression_script),
        "regression_script_sha256": sha256(regression_script),
        "case_count": len(case_results),
        "passed_case_count": sum(1 for row in case_results if row.get("passed")),
        "failed_case_count": failed_rows,
        "real_inputs_mutated": real_inputs_mutated,
        "failure_count": len(failures),
        "failures": failures,
        "cases": case_results,
        "safe_for_model_claim": False,
        "release_ready": False,
    }
    OUTPUT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"success": report["success"], "case_count": report["case_count"], "passed_case_count": report["passed_case_count"], "failure_count": report["failure_count"], "real_inputs_mutated": real_inputs_mutated, "output": str(OUTPUT)}, ensure_ascii=False, sort_keys=True))
    return 0 if report["success"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
