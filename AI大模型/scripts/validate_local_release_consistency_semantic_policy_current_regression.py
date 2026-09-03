#!/usr/bin/env python3
"""Exercise stale semantic-policy report cases in an isolated fixture."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Callable


AI_ROOT = Path(__file__).resolve().parents[1]
POLICY_SCRIPT = AI_ROOT / "scripts" / "validate_local_release_consistency_semantic_policy.py"
CONTRACT_MODULE = AI_ROOT / "scripts" / "local_release_consistency_receipt_contract.py"
CURRENT_VALIDATOR = AI_ROOT / "scripts" / "validate_local_release_consistency_semantic_policy_current.py"
CANONICAL_POLICY = AI_ROOT / "reports" / "local_release_consistency_semantic_policy_validation_report.json"
CANONICAL_CURRENT = AI_ROOT / "reports" / "local_release_consistency_semantic_policy_current_validation_report.json"
OUTPUT = AI_ROOT / "reports" / "local_release_consistency_semantic_policy_current_regression_report.json"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain an object")
    return data


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    protected = [POLICY_SCRIPT, CONTRACT_MODULE, CURRENT_VALIDATOR, CANONICAL_POLICY]
    if CANONICAL_CURRENT.is_file():
        protected.append(CANONICAL_CURRENT)
    before = {str(path): sha256(path) for path in protected if path.is_file()}
    results: list[dict[str, Any]] = []

    with tempfile.TemporaryDirectory(prefix="semantic-policy-current-") as temp_name:
        root = Path(temp_name)
        policy_script = root / "policy.py"
        contract_module = root / "contract.py"
        policy_report = root / "policy.json"
        lock_path = root / "policy.lock"
        shutil.copy2(POLICY_SCRIPT, policy_script)
        shutil.copy2(CONTRACT_MODULE, contract_module)
        fixture_env = dict(os.environ)
        fixture_env["PYTHONPATH"] = str(AI_ROOT) + os.pathsep + fixture_env.get("PYTHONPATH", "")
        policy_process = subprocess.run(
            [sys.executable, str(policy_script), "--contract-module", str(contract_module), "--output", str(policy_report), "--lock-path", str(lock_path)],
            cwd=AI_ROOT,
            capture_output=True,
            text=True,
            check=False,
            env=fixture_env,
        )
        baseline_report = policy_report.read_bytes() if policy_report.is_file() else b""
        baseline_policy_script = policy_script.read_bytes()
        baseline_contract = contract_module.read_bytes()

        def run_current(output: Path) -> tuple[int, dict[str, Any]]:
            process = subprocess.run(
                [
                    sys.executable, str(CURRENT_VALIDATOR),
                    "--policy-report", str(policy_report),
                    "--policy-script", str(policy_script),
                    "--contract-module", str(contract_module),
                    "--expected-policy-output", str(policy_report),
                    "--expected-lock-path", str(lock_path),
                    "--output", str(output),
                ],
                cwd=AI_ROOT,
                capture_output=True,
                text=True,
                check=False,
            )
            return process.returncode, load_json(output)

        control_rc, control = run_current(root / "control.json")
        results.append({
            "case": "fixture_control",
            "passed": policy_process.returncode == 0 and control_rc == 0 and control.get("success") is True,
            "policy_returncode": policy_process.returncode,
            "current_returncode": control_rc,
        })

        def recorded(field: str, value: Any) -> Callable[[], None]:
            def apply() -> None:
                payload = load_json(policy_report)
                payload[field] = value
                write_json(policy_report, payload)
            return apply

        cases: list[tuple[str, Callable[[], None], str]] = [
            ("recorded_policy_script_sha_drift", recorded("policy_script_sha256", "1" * 64), "policy_script_sha256_current"),
            ("live_policy_script_sha_drift", lambda: policy_script.write_bytes(baseline_policy_script + b"\n"), "policy_script_sha256_current"),
            ("recorded_contract_sha_drift", recorded("contract_module_sha256", "2" * 64), "contract_module_sha256_current"),
            ("live_contract_sha_drift", lambda: contract_module.write_bytes(baseline_contract + b"\n"), "contract_module_sha256_current"),
            ("contract_path_drift", recorded("contract_module_path", "/tmp/forged-contract.py"), "contract_module_path_current"),
            ("policy_output_path_drift", recorded("policy_output_path", "/tmp/forged-policy.json"), "policy_output_path_canonical"),
            ("policy_lock_path_drift", recorded("policy_lock_path", "/tmp/forged-policy.lock"), "policy_lock_path_canonical"),
            ("policy_lock_acquired_drift", recorded("policy_lock_acquired", False), "policy_lock_acquired"),
            ("policy_atomic_commit_drift", recorded("policy_atomic_commit", False), "policy_atomic_commit"),
            ("policy_success_drift", recorded("success", False), "policy_success"),
            ("policy_failure_count_drift", recorded("failure_count", 1), "policy_failure_count_zero"),
            ("expected_version_drift", recorded("expected_contract_version", "drifted"), "expected_contract_version_exact"),
            ("expected_policy_sha_drift", recorded("expected_canonical_policy_sha256", "3" * 64), "expected_canonical_policy_sha256_exact"),
            ("observed_policy_sha_drift", recorded("observed_canonical_policy_sha256", "4" * 64), "observed_canonical_policy_sha256_exact"),
            ("safe_for_model_claim_drift", recorded("safe_for_model_claim", True), "safe_for_model_claim_exact"),
        ]
        for name, mutation, expected_check in cases:
            policy_report.write_bytes(baseline_report)
            policy_script.write_bytes(baseline_policy_script)
            contract_module.write_bytes(baseline_contract)
            mutation()
            returncode, report = run_current(root / f"{name}.json")
            observed_checks = [row.get("check") for row in report.get("failures") or [] if isinstance(row, dict)]
            results.append({
                "case": name,
                "passed": returncode != 0 and report.get("success") is False and expected_check in observed_checks,
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
        "mode": "local_release_consistency_semantic_policy_current_regression",
        "success": not failures,
        "isolated_fixture": True,
        "case_count": len(results),
        "passed_case_count": sum(1 for row in results if row.get("passed")),
        "failed_case_count": failed_rows,
        "real_inputs_mutated": real_inputs_mutated,
        "regression_script_path": str(regression_script),
        "regression_script_sha256": sha256(regression_script),
        "current_validator_script_path": str(CURRENT_VALIDATOR.resolve()),
        "current_validator_script_sha256": sha256(CURRENT_VALIDATOR),
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
