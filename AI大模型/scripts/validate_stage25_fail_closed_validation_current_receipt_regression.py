#!/usr/bin/env python3
"""Prove Stage 25 current receipt validation rejects isolated contract tampering."""

from __future__ import annotations

import copy
import json
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable


AI_ROOT = Path(__file__).resolve().parents[1]
VALIDATOR = AI_ROOT / "scripts" / "validate_stage25_fail_closed_validation_current_receipt.py"
RECEIPT = AI_ROOT / "reports" / "stage25_fail_closed_validation_run_report_20260806.json"
RUNNER = AI_ROOT / "scripts" / "run_stage25_fail_closed_validation_20260806.py"
OUTPUT = AI_ROOT / "reports" / "stage25_fail_closed_validation_current_receipt_regression_report.json"


def run_validator(receipt: Path, output: Path, expected_output: Path, expected_lock: Path) -> tuple[subprocess.CompletedProcess[str], dict[str, Any]]:
    process = subprocess.run(
        [
            sys.executable,
            str(VALIDATOR),
            "--receipt", str(receipt),
            "--runner", str(RUNNER),
            "--expected-output", str(expected_output),
            "--expected-lock-path", str(expected_lock),
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
    canonical = json.loads(RECEIPT.read_text(encoding="utf-8"))
    results: list[dict[str, Any]] = []
    with tempfile.TemporaryDirectory(prefix="stage25-current-receipt-") as temp_dir:
        temp_root = Path(temp_dir)
        fixture_receipt = temp_root / "receipt.json"
        fixture_output = temp_root / "receipt-validation.json"
        expected_output = temp_root / "canonical-output.json"
        expected_lock = temp_root / "canonical.lock"
        control = copy.deepcopy(canonical)
        control["output_path"] = str(expected_output.resolve())
        control["run_lock_path"] = str(expected_lock.resolve())
        fixture_receipt.write_text(json.dumps(control, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        control_process, control_report = run_validator(fixture_receipt, fixture_output, expected_output, expected_lock)
        control_valid = control_process.returncode == 0 and control_report.get("success") is True

        cases: list[tuple[str, Callable[[dict[str, Any]], None], str]] = [
            ("runner_sha_drift", lambda data: data.update({"runner_script_sha256": "0" * 64}), "runner_sha_current"),
            ("command_contract_sha_drift", lambda data: data.update({"command_contract_sha256": "1" * 64}), "contract_sha_current"),
            ("output_path_drift", lambda data: data.update({"output_path": str(temp_root / "forged.json")}), "output_path_canonical"),
            ("lock_path_drift", lambda data: data.update({"run_lock_path": str(temp_root / "forged.lock")}), "lock_path_canonical"),
            ("command_count_drift", lambda data: data.update({"command_count": int(data["command_count"]) - 1}), "command_count_current"),
            ("command_success_drift", lambda data: data["commands"][0].update({"success": False}), "all_command_results_success"),
        ]
        for index, (case_id, mutate, expected_check) in enumerate(cases, start=1):
            tampered = copy.deepcopy(control)
            mutate(tampered)
            receipt = temp_root / f"case-{index}-receipt.json"
            output = temp_root / f"case-{index}-validation.json"
            receipt.write_text(json.dumps(tampered, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            process, report = run_validator(receipt, output, expected_output, expected_lock)
            checks = [str(row.get("check") or "") for row in report.get("failures") or []]
            results.append({
                "case_id": case_id,
                "tamper_rejected": process.returncode != 0 and expected_check in checks,
                "expected_check": expected_check,
                "expected_check_observed": expected_check in checks,
                "failure_count": len(report.get("failures") or []),
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
        "policy": "Only temporary Stage 25 receipt copies are mutated; canonical receipt and runner remain unchanged.",
    }
    OUTPUT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"success": report["success"], "control_valid": control_valid, "case_rows": len(results), "passed_rows": passed, "failed_rows": len(results) - passed, "real_inputs_mutated": False, "output": str(OUTPUT)}, ensure_ascii=False))
    return 0 if report["success"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
