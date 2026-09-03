#!/usr/bin/env python3
"""Exercise controlled release-order proof lock and recovery behavior."""

from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

from validate_enzyme_agent_controlled_release_guard_order import acquire_lock, write_json_atomic


AI_ROOT = Path(__file__).resolve().parents[1]
SIGNER = AI_ROOT / "scripts" / "validate_enzyme_agent_controlled_release_guard_order.py"
REGRESSION = AI_ROOT / "scripts" / "validate_enzyme_agent_controlled_release_guard_order_regression.py"
CURRENT = AI_ROOT / "scripts" / "validate_enzyme_agent_controlled_release_guard_order_current.py"
CURRENT_REGRESSION = AI_ROOT / "scripts" / "validate_enzyme_agent_controlled_release_guard_order_current_regression.py"
WAVE = AI_ROOT / "scripts" / "run_enzyme_agent_controlled_execution_wave.py"
OUTPUT = AI_ROOT / "reports" / "enzyme_agent_controlled_release_guard_order_atomicity_regression_report.json"
LOCK_PATH = AI_ROOT / "reports" / ".enzyme_agent_controlled_release_guard_order.lock"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain an object")
    return data


def run(command: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, cwd=AI_ROOT, capture_output=True, text=True, check=False, timeout=300)


def signer_command(output: Path, lock: Path, timeout: float = 1.0) -> list[str]:
    return [sys.executable, str(SIGNER), "--output", str(output), "--lock-path", str(lock), "--lock-timeout-seconds", str(timeout)]


def regression_command(output: Path, lock: Path, timeout: float = 1.0) -> list[str]:
    return [sys.executable, str(REGRESSION), "--output", str(output), "--lock-path", str(lock), "--lock-timeout-seconds", str(timeout)]


def current_command(validation: Path, regression: Path, output: Path, lock: Path, timeout: float = 1.0) -> list[str]:
    return [
        sys.executable,
        str(CURRENT),
        "--validation-report",
        str(validation),
        "--regression-report",
        str(regression),
        "--expected-lock-path",
        str(lock),
        "--output",
        str(output),
        "--lock-timeout-seconds",
        str(timeout),
    ]


def current_regression_command(output: Path, lock: Path, timeout: float = 1.0, fail: bool = False) -> list[str]:
    command = [
        sys.executable,
        str(CURRENT_REGRESSION),
        "--output",
        str(output),
        "--lock-path",
        str(lock),
        "--lock-timeout-seconds",
        str(timeout),
    ]
    if fail:
        command.append("--fail-before-replace")
    return command


def lock_timeout_recovery_case(
    case_id: str,
    command_factory,
    output: Path,
    lock: Path,
) -> dict[str, Any]:
    prior = b'{"sentinel":"prior-generation"}\n'
    output.write_bytes(prior)
    lock_handle = lock.open("a+")
    fcntl.flock(lock_handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    blocked = run(command_factory(output, lock, 0.0))
    blocked_preserved = output.read_bytes() == prior
    fcntl.flock(lock_handle.fileno(), fcntl.LOCK_UN)
    lock_handle.close()
    recovered = run(command_factory(output, lock, 2.0))
    recovered_report = load_json(output) if recovered.returncode == 0 and output.is_file() else {}
    return {
        "case": case_id,
        "passed": blocked.returncode != 0 and blocked_preserved and recovered.returncode == 0 and recovered_report.get("success") is True,
        "blocked_returncode": blocked.returncode,
        "blocked_output_preserved": blocked_preserved,
        "recovered_returncode": recovered.returncode,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Run release-order proof atomicity regression")
    parser.add_argument("--output", type=Path, default=OUTPUT)
    parser.add_argument("--lock-path", type=Path, default=LOCK_PATH)
    parser.add_argument("--lock-timeout-seconds", type=float, default=30.0)
    args = parser.parse_args()
    protected = [SIGNER, REGRESSION, CURRENT, CURRENT_REGRESSION, WAVE]
    before = {str(path): sha256(path) for path in protected}
    results: list[dict[str, Any]] = []

    with tempfile.TemporaryDirectory(prefix="release-guard-order-atomicity-") as temp_name:
        root = Path(temp_name)
        lock = root / "order.lock"
        validation = root / "validation.json"
        regression = root / "regression.json"
        current = root / "current.json"
        current_regression = root / "current-regression.json"

        signer_complete = run(signer_command(validation, lock))
        signer_report = load_json(validation) if validation.is_file() else {}
        results.append({
            "case": "signer_atomic_commit_complete_json",
            "passed": signer_complete.returncode == 0 and signer_report.get("success") is True and signer_report.get("atomic_commit") is True and signer_report.get("lock_acquired") is True,
            "returncode": signer_complete.returncode,
        })

        regression_complete = run(regression_command(regression, lock))
        regression_report = load_json(regression) if regression.is_file() else {}
        results.append({
            "case": "regression_atomic_commit_complete_json",
            "passed": regression_complete.returncode == 0 and regression_report.get("success") is True and regression_report.get("atomic_commit") is True and regression_report.get("lock_acquired") is True,
            "returncode": regression_complete.returncode,
        })

        current_complete = run(current_command(validation, regression, current, lock))
        current_report = load_json(current) if current.is_file() else {}
        results.append({
            "case": "current_atomic_commit_complete_json",
            "passed": current_complete.returncode == 0 and current_report.get("success") is True and current_report.get("current_atomic_commit") is True and current_report.get("current_lock_acquired") is True,
            "returncode": current_complete.returncode,
        })

        current_regression_complete = run(current_regression_command(current_regression, lock))
        current_regression_report = load_json(current_regression) if current_regression.is_file() else {}
        results.append({
            "case": "current_regression_atomic_commit_complete_json",
            "passed": current_regression_complete.returncode == 0 and current_regression_report.get("success") is True and current_regression_report.get("atomic_commit") is True and current_regression_report.get("lock_acquired") is True and current_regression_report.get("output_path") == str(current_regression.resolve()) and current_regression_report.get("lock_path") == str(lock.resolve()),
            "returncode": current_regression_complete.returncode,
        })

        prior = b'{"sentinel":"prior-current-regression"}\n'
        current_regression.write_bytes(prior)
        interrupted = run(current_regression_command(current_regression, lock, fail=True))
        residual = sorted(path.name for path in root.glob(f".{current_regression.name}.order-*"))
        results.append({
            "case": "current_regression_interrupted_replace_preserves_prior",
            "passed": interrupted.returncode != 0 and current_regression.read_bytes() == prior and residual == [],
            "returncode": interrupted.returncode,
            "prior_preserved": current_regression.read_bytes() == prior,
            "residual_temp_files": residual,
        })

        results.append(lock_timeout_recovery_case("signer_lock_timeout_and_recovery", signer_command, validation, lock))
        results.append(lock_timeout_recovery_case("regression_lock_timeout_and_recovery", regression_command, regression, lock))

        def current_factory(output: Path, lock_path: Path, timeout: float) -> list[str]:
            return current_command(validation, regression, output, lock_path, timeout)

        results.append(lock_timeout_recovery_case("current_lock_timeout_and_recovery", current_factory, current, lock))
        results.append(lock_timeout_recovery_case("current_regression_lock_timeout_and_recovery", current_regression_command, current_regression, lock))

        first = subprocess.Popen(signer_command(validation, lock, 5.0), cwd=AI_ROOT, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        second = subprocess.Popen(signer_command(validation, lock, 5.0), cwd=AI_ROOT, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        first.communicate(timeout=300)
        second.communicate(timeout=300)
        double_report = load_json(validation)
        results.append({
            "case": "double_signer_serializes",
            "passed": first.returncode == 0 and second.returncode == 0 and double_report.get("success") is True and double_report.get("atomic_commit") is True,
            "first_returncode": first.returncode,
            "second_returncode": second.returncode,
        })

        mixed_signer = subprocess.Popen(signer_command(validation, lock, 5.0), cwd=AI_ROOT, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        mixed_regression = subprocess.Popen(regression_command(regression, lock, 5.0), cwd=AI_ROOT, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        mixed_signer.communicate(timeout=300)
        mixed_regression.communicate(timeout=300)
        mixed_current = run(current_command(validation, regression, current, lock, 2.0))
        results.append({
            "case": "signer_regression_contention_serializes_to_current_pair",
            "passed": mixed_signer.returncode == 0 and mixed_regression.returncode == 0 and mixed_current.returncode == 0 and load_json(current).get("success") is True,
            "signer_returncode": mixed_signer.returncode,
            "regression_returncode": mixed_regression.returncode,
            "current_returncode": mixed_current.returncode,
        })

    after = {str(path): sha256(path) for path in protected}
    real_inputs_mutated = before != after
    failed_case_count = sum(1 for row in results if not row.get("passed"))
    failures: list[dict[str, Any]] = []
    if failed_case_count:
        failures.append({"check": "all_cases_pass", "observed": failed_case_count, "expected": 0})
    if real_inputs_mutated:
        failures.append({"check": "real_inputs_unchanged", "observed": {"before": before, "after": after}, "expected": True})
    script = Path(__file__).resolve()
    output_path = args.output.resolve()
    lock_path = args.lock_path.resolve()
    report = {
        "schema_version": 1,
        "mode": "enzyme-agent-controlled-release-guard-order-atomicity-regression-v1",
        "success": not failures,
        "isolated_fixture": True,
        "regression_script_path": str(script),
        "regression_script_sha256": sha256(script),
        "signer_script_path": str(SIGNER.resolve()),
        "signer_script_sha256": sha256(SIGNER),
        "order_regression_script_path": str(REGRESSION.resolve()),
        "order_regression_script_sha256": sha256(REGRESSION),
        "current_validator_script_path": str(CURRENT.resolve()),
        "current_validator_script_sha256": sha256(CURRENT),
        "current_regression_script_path": str(CURRENT_REGRESSION.resolve()),
        "current_regression_script_sha256": sha256(CURRENT_REGRESSION),
        "output_path": str(output_path),
        "lock_path": str(lock_path),
        "lock_acquired": True,
        "atomic_commit": True,
        "case_count": len(results),
        "passed_case_count": sum(1 for row in results if row.get("passed")),
        "failed_case_count": failed_case_count,
        "real_inputs_mutated": real_inputs_mutated,
        "failure_count": len(failures),
        "failures": failures,
        "cases": results,
        "safe_for_model_claim": False,
        "release_ready": False,
    }
    lock_handle = acquire_lock(lock_path, args.lock_timeout_seconds)
    if lock_handle is None:
        print(json.dumps({"success": False, "error": "release_guard_order_atomicity_regression_lock_timeout", "output_preserved": output_path.exists()}, ensure_ascii=False, sort_keys=True))
        return 1
    try:
        write_json_atomic(output_path, report)
    finally:
        lock_handle.close()
    print(json.dumps({"success": report["success"], "case_count": report["case_count"], "passed_case_count": report["passed_case_count"], "failure_count": report["failure_count"], "real_inputs_mutated": real_inputs_mutated, "output": str(output_path)}, ensure_ascii=False, sort_keys=True))
    return 0 if report["success"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
