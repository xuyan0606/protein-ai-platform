#!/usr/bin/env python3
"""Exercise semantic policy signer/current lock and atomic recovery paths."""

from __future__ import annotations

import fcntl
import hashlib
import json
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
POLICY_SCRIPT = AI_ROOT / "scripts" / "validate_local_release_consistency_semantic_policy.py"
CURRENT_VALIDATOR = AI_ROOT / "scripts" / "validate_local_release_consistency_semantic_policy_current.py"
CONTRACT_MODULE = AI_ROOT / "scripts" / "local_release_consistency_receipt_contract.py"
CANONICAL_POLICY = AI_ROOT / "reports" / "local_release_consistency_semantic_policy_validation_report.json"
CANONICAL_CURRENT = AI_ROOT / "reports" / "local_release_consistency_semantic_policy_current_validation_report.json"
OUTPUT = AI_ROOT / "reports" / "local_release_consistency_semantic_policy_atomicity_regression_report.json"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain an object")
    return data


def policy_command(output: Path, lock: Path, *, timeout: float = 1.0, fail: bool = False) -> list[str]:
    command = [
        sys.executable, str(POLICY_SCRIPT),
        "--contract-module", str(CONTRACT_MODULE),
        "--output", str(output),
        "--lock-path", str(lock),
        "--lock-timeout-seconds", str(timeout),
    ]
    if fail:
        command.append("--fail-before-replace")
    return command


def current_command(policy: Path, output: Path, lock: Path, *, timeout: float = 1.0, fail: bool = False) -> list[str]:
    command = [
        sys.executable, str(CURRENT_VALIDATOR),
        "--policy-report", str(policy),
        "--policy-script", str(POLICY_SCRIPT),
        "--contract-module", str(CONTRACT_MODULE),
        "--expected-policy-output", str(policy),
        "--expected-lock-path", str(lock),
        "--output", str(output),
        "--lock-timeout-seconds", str(timeout),
    ]
    if fail:
        command.append("--fail-before-replace")
    return command


def run(command: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, cwd=AI_ROOT, capture_output=True, text=True, check=False, timeout=300)


def main() -> int:
    protected = [POLICY_SCRIPT, CURRENT_VALIDATOR, CONTRACT_MODULE, CANONICAL_POLICY, CANONICAL_CURRENT]
    before = {str(path): sha256(path) for path in protected if path.is_file()}
    results: list[dict[str, Any]] = []
    with tempfile.TemporaryDirectory(prefix="semantic-policy-atomicity-") as temp_name:
        root = Path(temp_name)

        policy = root / "policy.json"
        lock = root / "policy.lock"
        complete = run(policy_command(policy, lock))
        complete_report = load_json(policy) if policy.is_file() else {}
        results.append({
            "case": "policy_atomic_commit_complete_json",
            "passed": complete.returncode == 0 and complete_report.get("success") is True and complete_report.get("policy_atomic_commit") is True and complete_report.get("policy_lock_acquired") is True,
            "returncode": complete.returncode,
        })

        prior_policy = b'{"sentinel":"prior-policy"}\n'
        policy.write_bytes(prior_policy)
        interrupted = run(policy_command(policy, lock, fail=True))
        policy_temps = sorted(path.name for path in root.glob(f".{policy.name}.policy-*"))
        results.append({
            "case": "policy_interrupted_replace_preserves_prior",
            "passed": interrupted.returncode != 0 and policy.read_bytes() == prior_policy and not policy_temps,
            "returncode": interrupted.returncode,
            "prior_preserved": policy.read_bytes() == prior_policy,
            "residual_temp_files": policy_temps,
        })

        policy.write_bytes(prior_policy)
        lock_handle = lock.open("a+")
        fcntl.flock(lock_handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        blocked = run(policy_command(policy, lock, timeout=0.0))
        fcntl.flock(lock_handle.fileno(), fcntl.LOCK_UN)
        lock_handle.close()
        recovered = run(policy_command(policy, lock))
        results.append({
            "case": "policy_lock_timeout_and_recovery",
            "passed": blocked.returncode != 0 and recovered.returncode == 0 and load_json(policy).get("success") is True,
            "blocked_returncode": blocked.returncode,
            "recovered_returncode": recovered.returncode,
        })

        first = subprocess.Popen(policy_command(policy, lock, timeout=5.0), cwd=AI_ROOT, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        second = subprocess.Popen(policy_command(policy, lock, timeout=5.0), cwd=AI_ROOT, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        first.communicate(timeout=300)
        second.communicate(timeout=300)
        concurrent_report = load_json(policy)
        results.append({
            "case": "double_policy_signer_serializes",
            "passed": first.returncode == 0 and second.returncode == 0 and concurrent_report.get("success") is True and concurrent_report.get("policy_atomic_commit") is True,
            "first_returncode": first.returncode,
            "second_returncode": second.returncode,
        })

        current = root / "current.json"
        current_complete = run(current_command(policy, current, lock))
        current_report = load_json(current) if current.is_file() else {}
        results.append({
            "case": "current_atomic_commit_complete_json",
            "passed": current_complete.returncode == 0 and current_report.get("success") is True and current_report.get("current_atomic_commit") is True and current_report.get("current_lock_acquired") is True,
            "returncode": current_complete.returncode,
        })

        prior_current = b'{"sentinel":"prior-current"}\n'
        current.write_bytes(prior_current)
        current_interrupted = run(current_command(policy, current, lock, fail=True))
        current_temps = sorted(path.name for path in root.glob(f".{current.name}.current-*"))
        results.append({
            "case": "current_interrupted_replace_preserves_prior",
            "passed": current_interrupted.returncode != 0 and current.read_bytes() == prior_current and not current_temps,
            "returncode": current_interrupted.returncode,
            "prior_preserved": current.read_bytes() == prior_current,
            "residual_temp_files": current_temps,
        })

        current.write_bytes(prior_current)
        lock_handle = lock.open("a+")
        fcntl.flock(lock_handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        current_blocked = run(current_command(policy, current, lock, timeout=0.0))
        fcntl.flock(lock_handle.fileno(), fcntl.LOCK_UN)
        lock_handle.close()
        current_recovered = run(current_command(policy, current, lock))
        results.append({
            "case": "current_lock_timeout_and_recovery",
            "passed": current_blocked.returncode != 0 and current_recovered.returncode == 0 and load_json(current).get("success") is True,
            "blocked_returncode": current_blocked.returncode,
            "recovered_returncode": current_recovered.returncode,
        })

    after = {str(path): sha256(path) for path in protected if path.is_file()}
    real_inputs_mutated = before != after
    failed_rows = sum(1 for row in results if not row.get("passed"))
    failures = []
    if failed_rows:
        failures.append({"check": "all_cases_pass", "observed": failed_rows, "expected": 0})
    if real_inputs_mutated:
        failures.append({"check": "real_inputs_unchanged", "observed": {"before": before, "after": after}, "expected": True})
    script = Path(__file__).resolve()
    report = {
        "schema_version": 1,
        "mode": "local_release_consistency_semantic_policy_atomicity_regression",
        "success": not failures,
        "isolated_fixture": True,
        "regression_script_path": str(script),
        "regression_script_sha256": sha256(script),
        "policy_script_path": str(POLICY_SCRIPT.resolve()),
        "policy_script_sha256": sha256(POLICY_SCRIPT),
        "current_validator_script_path": str(CURRENT_VALIDATOR.resolve()),
        "current_validator_script_sha256": sha256(CURRENT_VALIDATOR),
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
