#!/usr/bin/env python3
"""Prove safe-pipeline current receipt validation rejects stale/tampered evidence."""

from __future__ import annotations

import copy
import json
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path


AI_ROOT = Path(__file__).resolve().parents[1]
RECEIPT = AI_ROOT / "reports" / "safe_training_pipeline_run.json"
RUNNER = AI_ROOT / "scripts" / "run_safe_training_pipeline.py"
LOCK_PATH = AI_ROOT / "reports" / ".safe_training_pipeline.lock"
VALIDATOR = AI_ROOT / "scripts" / "validate_safe_training_pipeline_current_receipt.py"
OUTPUT = AI_ROOT / "reports" / "safe_training_pipeline_current_receipt_regression_report.json"


def run_validator(receipt: Path, output: Path) -> tuple[subprocess.CompletedProcess[str], dict]:
    process = subprocess.run(
        [
            sys.executable,
            str(VALIDATOR),
            "--receipt", str(receipt),
            "--runner", str(RUNNER),
            "--expected-output", str(RECEIPT),
            "--expected-lock-path", str(LOCK_PATH),
            "--output", str(output),
        ],
        cwd=AI_ROOT,
        text=True,
        capture_output=True,
        timeout=300,
    )
    report = json.loads(output.read_text(encoding="utf-8")) if output.is_file() else {}
    return process, report


def main() -> int:
    baseline = json.loads(RECEIPT.read_text(encoding="utf-8"))
    results: list[dict[str, object]] = []
    with tempfile.TemporaryDirectory(prefix="safe-pipeline-current-") as temp_dir:
        temp_root = Path(temp_dir)
        control_output = temp_root / "control-validation.json"
        control_process, control_report = run_validator(RECEIPT, control_output)
        control_valid = control_process.returncode == 0 and control_report.get("success") is True

        cases = [
            ("stale_runner_sha", lambda data: data.update({"runner_script_sha256": "0" * 64}), "runner_script_sha_current"),
            ("stale_command_contract_sha", lambda data: data.update({"command_contract_sha256": "1" * 64}), "command_contract_sha_current"),
            ("output_path_drift", lambda data: data.update({"output_path": "/tmp/forged-safe-pipeline.json"}), "receipt_output_path_canonical"),
            ("lock_path_drift", lambda data: data.update({"lock_path": "/tmp/forged-safe-pipeline.lock"}), "receipt_lock_path_canonical"),
            ("step_count_drift", lambda data: data.update({"steps_run": int(data["steps_run"]) - 1}), "steps_run_current"),
            ("nonzero_step_returncode", lambda data: data["steps"][0].update({"returncode": 1}), "all_step_returncodes_zero"),
        ]
        for index, (case_id, mutate, expected_check) in enumerate(cases, start=1):
            tampered = copy.deepcopy(baseline)
            mutate(tampered)
            receipt_path = temp_root / f"case-{index}-receipt.json"
            output_path = temp_root / f"case-{index}-validation.json"
            receipt_path.write_text(json.dumps(tampered, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            process, report = run_validator(receipt_path, output_path)
            checks = [str(row.get("check") or "") for row in report.get("failures") or []]
            results.append({
                "case_id": case_id,
                "tamper_rejected": process.returncode != 0 and expected_check in checks,
                "expected_check": expected_check,
                "expected_check_observed": expected_check in checks,
                "failure_count": int(report.get("failure_count") or 0),
            })

    passed = sum(bool(row["tamper_rejected"]) for row in results)
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
        "policy": "Only temporary receipt copies are modified; the canonical runner and receipt remain unchanged.",
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
