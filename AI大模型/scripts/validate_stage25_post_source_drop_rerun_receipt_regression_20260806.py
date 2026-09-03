#!/usr/bin/env python3
"""Run isolated current-binding tamper cases for the post-source receipt."""

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
CANONICAL_RECEIPT = AI_ROOT / "reports" / "stage25_post_source_drop_rerun_receipt_20260806.json"
CANONICAL_VALIDATION = AI_ROOT / "reports" / "stage25_post_source_drop_rerun_receipt_validation_20260806.json"
OUTPUT = AI_ROOT / "reports" / "stage25_post_source_drop_rerun_receipt_regression_20260806.json"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain an object")
    return data


def run_validator(
    receipt: Path,
    builder: Path,
    expected_output: Path,
    expected_lock: Path,
    output: Path,
) -> tuple[int, dict[str, Any]]:
    result = subprocess.run(
        [
            sys.executable,
            str(VALIDATOR),
            "--receipt",
            str(receipt),
            "--builder",
            str(builder),
            "--expected-output",
            str(expected_output),
            "--expected-lock-path",
            str(expected_lock),
            "--output",
            str(output),
        ],
        cwd=AI_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    return result.returncode, load_json(output)


def mutate(path: Path, mutation: Callable[[dict[str, Any]], None]) -> None:
    data = load_json(path)
    mutation(data)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    protected = [CANONICAL_RECEIPT, CANONICAL_VALIDATION, BUILDER]
    before = {str(path): sha256(path) for path in protected if path.is_file()}
    cases: list[tuple[str, Callable[[dict[str, Any]], None], str]] = [
        ("builder_sha_drift", lambda data: data.update({"builder_script_sha256": "0" * 64}), "builder_script_sha256_current"),
        ("command_contract_sha_drift", lambda data: data.update({"command_contract_sha256": "1" * 64}), "receipt_command_contract_sha256"),
        ("output_path_drift", lambda data: data.update({"output_path": "/tmp/non-canonical-receipt.json"}), "output_path_canonical"),
        ("lock_path_drift", lambda data: data.update({"lock_path": "/tmp/non-canonical-receipt.lock"}), "lock_path_canonical"),
        ("command_rows_drift", lambda data: data.update({"command_rows": 0}), "command_rows"),
        ("command_entry_drift", lambda data: data["commands"][0].update({"name": "tampered_command"}), "commands_exact_contract"),
        ("lock_acquired_drift", lambda data: data.update({"lock_acquired": False}), "lock_acquired_true"),
        ("atomic_commit_drift", lambda data: data.update({"receipt_atomic_commit": False}), "receipt_atomic_commit_true"),
    ]
    case_results: list[dict[str, Any]] = []

    with tempfile.TemporaryDirectory(prefix="stage25-post-source-receipt-") as temp_name:
        fixture_root = Path(temp_name) / "AI大模型"
        fixture_scripts = fixture_root / "scripts"
        fixture_reports = fixture_root / "reports"
        fixture_scripts.mkdir(parents=True)
        fixture_reports.mkdir(parents=True)
        fixture_builder = fixture_scripts / BUILDER.name
        shutil.copy2(BUILDER, fixture_builder)
        fixture_receipt = fixture_reports / CANONICAL_RECEIPT.name
        fixture_lock = fixture_reports / ".stage25_post_source_drop_rerun_receipt.lock"
        fixture_validation = fixture_reports / CANONICAL_VALIDATION.name

        built = subprocess.run(
            [sys.executable, str(fixture_builder)],
            cwd=fixture_root,
            capture_output=True,
            text=True,
            check=False,
        )
        if built.returncode != 0:
            case_results.append({"case": "fixture_control", "passed": False, "reason": built.stderr[-1000:]})
        else:
            control_returncode, control_report = run_validator(
                fixture_receipt,
                fixture_builder,
                fixture_receipt,
                fixture_lock,
                fixture_validation,
            )
            control_passed = control_returncode == 0 and control_report.get("receipt_valid") is True and control_report.get("failure_count") == 0
            case_results.append({
                "case": "fixture_control",
                "passed": control_passed,
                "returncode": control_returncode,
                "failure_count": control_report.get("failure_count"),
            })

            for name, mutation, expected_check in cases:
                case_receipt = fixture_reports / f"{name}.json"
                case_output = fixture_reports / f"{name}_validation.json"
                shutil.copy2(fixture_receipt, case_receipt)
                mutate(case_receipt, mutation)
                returncode, report = run_validator(
                    case_receipt,
                    fixture_builder,
                    case_receipt,
                    fixture_lock,
                    case_output,
                )
                observed_checks = [row.get("check") for row in report.get("failures", []) if isinstance(row, dict)]
                passed = returncode != 0 and report.get("receipt_valid") is False and expected_check in observed_checks
                case_results.append({
                    "case": name,
                    "passed": passed,
                    "returncode": returncode,
                    "failure_count": report.get("failure_count"),
                    "expected_check": expected_check,
                    "observed_checks": observed_checks,
                })

    after = {str(path): sha256(path) for path in protected if path.is_file()}
    real_inputs_mutated = before != after
    failures = []
    if not case_results or any(not row.get("passed") for row in case_results):
        failures.append({"check": "all_cases_pass", "observed": case_results, "expected": True})
    if real_inputs_mutated:
        failures.append({"check": "real_inputs_unchanged", "observed": {"before": before, "after": after}, "expected": True})

    report = {
        "schema_version": 1,
        "mode": "stage25_post_source_drop_rerun_receipt_regression",
        "success": not failures,
        "isolated_fixture": True,
        "real_inputs_mutated": real_inputs_mutated,
        "case_count": len(case_results),
        "passed_case_count": sum(1 for row in case_results if row.get("passed")),
        "failure_count": len(failures),
        "failures": failures,
        "cases": case_results,
        "safe_for_model_claim": False,
        "release_ready": False,
    }
    OUTPUT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(OUTPUT), "case_count": report["case_count"], "passed_case_count": report["passed_case_count"], "failure_count": report["failure_count"], "real_inputs_mutated": real_inputs_mutated}, ensure_ascii=False, sort_keys=True))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
