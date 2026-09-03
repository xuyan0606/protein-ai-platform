#!/usr/bin/env python3
"""Isolated tamper regression for current controlled release-guard order proofs."""

from __future__ import annotations

import argparse
import copy
import json
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from validate_enzyme_agent_controlled_release_guard_order import LOCK_PATH, acquire_lock, sha256, write_json_atomic
from validate_enzyme_agent_controlled_release_guard_order_current import (
    REGRESSION_SCRIPT,
    VALIDATOR_SCRIPT,
    WAVE_SCRIPT,
    validate_order_proofs_current,
)


AI_ROOT = Path(__file__).resolve().parents[1]
OUTPUT = AI_ROOT / "reports" / "enzyme_agent_controlled_release_guard_order_current_regression_report.json"
CURRENT_VALIDATOR = AI_ROOT / "scripts" / "validate_enzyme_agent_controlled_release_guard_order_current.py"


def run(command: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, cwd=AI_ROOT, text=True, capture_output=True, check=False)


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def evaluate_case(
    case_id: str,
    validation: dict[str, Any],
    regression: dict[str, Any],
    *,
    validation_path: Path,
    regression_path: Path,
    validator_path: Path,
    regression_script_path: Path,
    wave_path: Path,
    lock_path: Path,
    expected_valid: bool,
) -> dict[str, Any]:
    failures, _ = validate_order_proofs_current(
        validation,
        regression,
        validation_report_path=validation_path,
        regression_report_path=regression_path,
        validator_script_path=validator_path,
        regression_script_path=regression_script_path,
        wave_script_path=wave_path,
        expected_lock_path=lock_path,
    )
    observed_valid = not failures
    return {
        "case_id": case_id,
        "expected_valid": expected_valid,
        "observed_valid": observed_valid,
        "passed": observed_valid == expected_valid,
        "failure_checks": [row.get("check") for row in failures],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Run release-guard order current tamper regression")
    parser.add_argument("--output", type=Path, default=OUTPUT)
    parser.add_argument("--lock-path", type=Path, default=LOCK_PATH)
    parser.add_argument("--lock-timeout-seconds", type=float, default=30.0)
    parser.add_argument("--fail-before-replace", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()
    output_path = args.output.resolve()
    canonical_paths = [VALIDATOR_SCRIPT, REGRESSION_SCRIPT, WAVE_SCRIPT]
    before = {str(path): sha256(path) for path in canonical_paths}

    with tempfile.TemporaryDirectory(prefix="release-guard-order-current-") as temp_dir:
        temp = Path(temp_dir)
        validation_path = temp / "validation.json"
        regression_path = temp / "regression.json"
        fixture_lock = temp / "order.lock"
        signer = run([sys.executable, str(VALIDATOR_SCRIPT), "--output", str(validation_path), "--lock-path", str(fixture_lock)])
        regression_run = run([sys.executable, str(REGRESSION_SCRIPT), "--output", str(regression_path), "--lock-path", str(fixture_lock)])
        if signer.returncode != 0 or regression_run.returncode != 0:
            print(json.dumps({"success": False, "error": "fixture_generation_failed", "signer_stderr": signer.stderr, "regression_stderr": regression_run.stderr}, ensure_ascii=False, sort_keys=True))
            return 1
        control_validation = load_json(validation_path)
        control_regression = load_json(regression_path)
        common = {
            "validation_path": validation_path,
            "regression_path": regression_path,
            "validator_path": VALIDATOR_SCRIPT,
            "regression_script_path": REGRESSION_SCRIPT,
            "wave_path": WAVE_SCRIPT,
            "lock_path": fixture_lock,
        }
        cases = [evaluate_case("control_current", control_validation, control_regression, expected_valid=True, **common)]

        mutations = [
            ("validation_success_drift", "validation", "success", False),
            ("validation_validator_sha_drift", "validation", "validator_script_sha256", "0" * 64),
            ("validation_wave_sha_drift", "validation", "wave_script_sha256", "0" * 64),
            ("validation_output_path_drift", "validation", "output_path", str(temp / "forged.json")),
            ("validation_lock_path_drift", "validation", "lock_path", str(temp / "forged.lock")),
            ("validation_atomic_commit_drift", "validation", "atomic_commit", False),
            ("validation_contract_sha_drift", "validation", "observed_action_contract_sha256", "0" * 64),
            ("regression_failed_rows_drift", "regression", "failed_rows", 1),
            ("regression_script_sha_drift", "regression", "regression_script_sha256", "0" * 64),
            ("regression_output_path_drift", "regression", "output_path", str(temp / "forged-regression.json")),
            ("regression_atomic_commit_drift", "regression", "atomic_commit", False),
        ]
        for case_id, target, field, value in mutations:
            validation = copy.deepcopy(control_validation)
            regression = copy.deepcopy(control_regression)
            (validation if target == "validation" else regression)[field] = value
            cases.append(evaluate_case(case_id, validation, regression, expected_valid=False, **common))

        wave_copy = temp / "wave.py"
        shutil.copy2(WAVE_SCRIPT, wave_copy)
        wave_validation = copy.deepcopy(control_validation)
        wave_regression = copy.deepcopy(control_regression)
        for report in (wave_validation, wave_regression):
            report["wave_script_path"] = str(wave_copy.resolve())
            report["wave_script_sha256"] = sha256(wave_copy)
        wave_copy.write_text(wave_copy.read_text(encoding="utf-8") + "\n# isolated drift\n", encoding="utf-8")
        cases.append(evaluate_case("live_wave_script_sha_drift", wave_validation, wave_regression, expected_valid=False, **{**common, "wave_path": wave_copy}))

        validator_copy = temp / "validator.py"
        shutil.copy2(VALIDATOR_SCRIPT, validator_copy)
        validator_validation = copy.deepcopy(control_validation)
        validator_regression = copy.deepcopy(control_regression)
        for report in (validator_validation, validator_regression):
            report["validator_script_path"] = str(validator_copy.resolve())
            report["validator_script_sha256"] = sha256(validator_copy)
        validator_copy.write_text(validator_copy.read_text(encoding="utf-8") + "\n# isolated drift\n", encoding="utf-8")
        cases.append(evaluate_case("live_validator_script_sha_drift", validator_validation, validator_regression, expected_valid=False, **{**common, "validator_path": validator_copy}))

        atomic_specs = [
            (
                "signer_interrupted_replace_preserves_prior",
                temp / "atomic-signer.json",
                [sys.executable, str(VALIDATOR_SCRIPT), "--output", str(temp / "atomic-signer.json"), "--lock-path", str(temp / "atomic-signer.lock"), "--fail-before-replace"],
                ".atomic-signer.json.order-*",
            ),
            (
                "regression_interrupted_replace_preserves_prior",
                temp / "atomic-regression.json",
                [sys.executable, str(REGRESSION_SCRIPT), "--output", str(temp / "atomic-regression.json"), "--lock-path", str(temp / "atomic-regression.lock"), "--fail-before-replace"],
                ".atomic-regression.json.order-*",
            ),
            (
                "current_interrupted_replace_preserves_prior",
                temp / "atomic-current.json",
                [
                    sys.executable,
                    str(CURRENT_VALIDATOR),
                    "--validation-report",
                    str(validation_path),
                    "--regression-report",
                    str(regression_path),
                    "--expected-lock-path",
                    str(fixture_lock),
                    "--output",
                    str(temp / "atomic-current.json"),
                    "--fail-before-replace",
                ],
                ".atomic-current.json.current-*",
            ),
        ]
        prior_bytes = b'{"prior_generation":true}\n'
        for case_id, atomic_output, command, temp_pattern in atomic_specs:
            atomic_output.write_bytes(prior_bytes)
            process = run(command)
            prior_preserved = atomic_output.read_bytes() == prior_bytes
            temp_residue = sorted(path.name for path in atomic_output.parent.glob(temp_pattern))
            passed = process.returncode != 0 and prior_preserved and temp_residue == []
            cases.append({
                "case_id": case_id,
                "expected_valid": False,
                "observed_valid": process.returncode == 0,
                "passed": passed,
                "prior_output_preserved": prior_preserved,
                "temp_residue": temp_residue,
            })

    after = {str(path): sha256(path) for path in canonical_paths}
    passed_case_count = sum(1 for case in cases if case["passed"])
    failed_case_count = len(cases) - passed_case_count
    regression_script = Path(__file__).resolve()
    report = {
        "schema_version": 1,
        "mode": "enzyme-agent-controlled-release-guard-order-current-regression-v1",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "success": failed_case_count == 0 and before == after,
        "regression_script_path": str(regression_script),
        "regression_script_sha256": sha256(regression_script),
        "current_validator_script_path": str(CURRENT_VALIDATOR.resolve()),
        "current_validator_script_sha256": sha256(CURRENT_VALIDATOR),
        "output_path": str(output_path),
        "lock_path": str(args.lock_path.resolve()),
        "lock_acquired": True,
        "atomic_commit": True,
        "case_count": len(cases),
        "passed_case_count": passed_case_count,
        "failed_case_count": failed_case_count,
        "isolated_fixture": True,
        "real_inputs_mutated": before != after,
        "cases": cases,
        "safe_for_model_claim": False,
        "release_ready": False,
    }
    lock_path = args.lock_path.resolve()
    lock_handle = acquire_lock(lock_path, args.lock_timeout_seconds)
    if lock_handle is None:
        print(json.dumps({"success": False, "error": "release_guard_order_current_regression_lock_timeout", "output_preserved": output_path.exists()}, ensure_ascii=False, sort_keys=True))
        return 1
    try:
        write_json_atomic(output_path, report, fail_before_replace=args.fail_before_replace)
    except Exception as exc:
        print(json.dumps({"success": False, "error": f"release_guard_order_current_regression_commit_failed:{type(exc).__name__}:{exc}", "output": str(output_path)}, ensure_ascii=False, sort_keys=True))
        return 1
    finally:
        lock_handle.close()
    print(json.dumps({"success": report["success"], "case_count": report["case_count"], "passed_case_count": report["passed_case_count"], "failure_count": report["failed_case_count"], "real_inputs_mutated": report["real_inputs_mutated"], "output": str(output_path)}, ensure_ascii=False, sort_keys=True))
    return 0 if report["success"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
