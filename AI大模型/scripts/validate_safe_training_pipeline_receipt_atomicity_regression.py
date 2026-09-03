#!/usr/bin/env python3
"""Prove safe-pipeline receipt locking and atomic helpers fail closed."""

from __future__ import annotations

import fcntl
import importlib.util
import json
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from types import ModuleType


AI_ROOT = Path(__file__).resolve().parents[1]
RUNNER = AI_ROOT / "scripts" / "run_safe_training_pipeline.py"
OUTPUT = AI_ROOT / "reports" / "safe_training_pipeline_receipt_atomicity_regression_report.json"


def load_runner() -> ModuleType:
    spec = importlib.util.spec_from_file_location("safe_pipeline_atomicity_runner", RUNNER)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load runner: {RUNNER}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main() -> int:
    runner = load_runner()
    results: list[dict[str, object]] = []

    contract_sha = runner.command_contract_sha256(runner.COMMANDS)
    drifted_commands = [list(command) for command in runner.COMMANDS]
    drifted_commands[0] = [*drifted_commands[0], "--contract-drift-probe"]
    contract_bound = (
        isinstance(contract_sha, str)
        and len(contract_sha) == 64
        and runner.command_contract_sha256(drifted_commands) != contract_sha
    )
    results.append({
        "case_id": "command_contract_drift_changes_sha",
        "tamper_rejected": contract_bound,
        "expected_check": "command_contract_sha256",
        "expected_check_observed": contract_bound,
    })

    with tempfile.TemporaryDirectory(prefix="safe-pipeline-receipt-") as temp_dir:
        temp_root = Path(temp_dir)
        receipt_path = temp_root / "atomic-success.json"
        success_payload = {"success": True, "sentinel": "complete"}
        runner.write_json_atomic(receipt_path, success_payload)
        atomic_success = json.loads(receipt_path.read_text(encoding="utf-8")) == success_payload
        results.append({
            "case_id": "atomic_receipt_success",
            "tamper_rejected": atomic_success,
            "expected_check": "atomic_replace",
            "expected_check_observed": atomic_success,
        })

        receipt_path = temp_root / "atomic-failure.json"
        prior_payload = {"success": True, "sentinel": "prior-complete"}
        receipt_path.write_text(json.dumps(prior_payload) + "\n", encoding="utf-8")
        failure_observed = False
        try:
            runner.write_json_atomic(
                receipt_path,
                {"success": False, "sentinel": "partial"},
                fail_before_replace=True,
            )
        except RuntimeError as exc:
            failure_observed = "simulated_safe_pipeline_receipt_failure_before_replace" in str(exc)
        prior_preserved = failure_observed and json.loads(receipt_path.read_text(encoding="utf-8")) == prior_payload
        results.append({
            "case_id": "atomic_failure_preserves_prior_receipt",
            "tamper_rejected": prior_preserved,
            "expected_check": "prior_receipt_preserved",
            "expected_check_observed": prior_preserved,
        })

        lock_path = temp_root / "held.lock"
        blocked_output = temp_root / "lock-failure-report.json"
        with lock_path.open("a+") as lock_handle:
            fcntl.flock(lock_handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            process = subprocess.run(
                [
                    sys.executable,
                    str(RUNNER),
                    "--output", str(blocked_output),
                    "--lock-path", str(lock_path),
                    "--lock-timeout-seconds", "0.05",
                ],
                cwd=AI_ROOT,
                text=True,
                capture_output=True,
                timeout=30,
            )
            fcntl.flock(lock_handle.fileno(), fcntl.LOCK_UN)
        blocked_report = json.loads(blocked_output.read_text(encoding="utf-8")) if blocked_output.is_file() else {}
        checks = [str(row.get("check") or "") for row in blocked_report.get("failures") or []]
        lock_rejected = (
            process.returncode != 0
            and blocked_report.get("lock_acquired") is False
            and blocked_report.get("steps_run") == 0
            and "safe_pipeline_lock_acquired" in checks
        )
        results.append({
            "case_id": "lock_contention_runs_no_commands",
            "tamper_rejected": lock_rejected,
            "expected_check": "safe_pipeline_lock_acquired",
            "expected_check_observed": "safe_pipeline_lock_acquired" in checks,
        })

    passed = sum(bool(row["tamper_rejected"]) for row in results)
    report = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "success": passed == len(results),
        "isolated_fixture": True,
        "case_rows": len(results),
        "passed_rows": passed,
        "failed_rows": len(results) - passed,
        "canonical_command_rows": len(runner.COMMANDS),
        "canonical_command_contract_version": runner.COMMAND_CONTRACT_VERSION,
        "canonical_command_contract_sha256": contract_sha,
        "real_inputs_mutated": False,
        "safe_for_model_claim": False,
        "release_ready": False,
        "results": results,
        "policy": "Regression uses temporary receipts and locks only; it does not execute the canonical safe pipeline.",
    }
    runner.write_json_atomic(OUTPUT, report)
    print(json.dumps({
        "success": report["success"],
        "case_rows": report["case_rows"],
        "passed_rows": report["passed_rows"],
        "failed_rows": report["failed_rows"],
        "real_inputs_mutated": report["real_inputs_mutated"],
        "output": str(OUTPUT),
    }, ensure_ascii=False))
    return 0 if report["success"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
