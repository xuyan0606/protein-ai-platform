#!/usr/bin/env python3
"""Prove safe-pipeline terminal defer receipts cannot cross execution modes."""

from __future__ import annotations

import copy
import json
import os
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
VALIDATOR = AI_ROOT / "scripts" / "validate_local_release_safety_guard_links.py"
CONSISTENCY = AI_ROOT / "reports" / "local_release_manifest_fail_closed_consistency_validation_report.json"
OUTPUT = AI_ROOT / "reports" / "local_release_terminal_defer_mode_regression_report.json"


def run_validator(receipt: Path, output: Path, *, deferred: bool) -> tuple[subprocess.CompletedProcess[str], dict[str, Any]]:
    environment = os.environ.copy()
    if deferred:
        environment["KWB_DEFER_SAFE_PIPELINE_TERMINAL"] = "1"
    else:
        environment.pop("KWB_DEFER_SAFE_PIPELINE_TERMINAL", None)
    process = subprocess.run(
        [sys.executable, str(VALIDATOR), "--consistency-receipt", str(receipt), "--mode-check-only", "--output", str(output)],
        cwd=AI_ROOT,
        text=True,
        capture_output=True,
        timeout=300,
        env=environment,
    )
    report = json.loads(output.read_text(encoding="utf-8")) if output.is_file() else {}
    return process, report


def normalized_receipt(source: dict[str, Any]) -> dict[str, Any]:
    receipt = copy.deepcopy(source)
    receipt["success"] = True
    receipt["failures"] = []
    receipt["safe_for_training_pipeline"] = True
    receipt["safe_for_model_claim"] = False
    receipt["release_ready"] = False
    return receipt


def main() -> int:
    canonical = json.loads(CONSISTENCY.read_text(encoding="utf-8"))
    results: list[dict[str, Any]] = []
    with tempfile.TemporaryDirectory(prefix="local-release-terminal-defer-") as temp_dir:
        temp_root = Path(temp_dir)
        control_path = temp_root / "control-receipt.json"
        control = normalized_receipt(canonical)
        control["safe_pipeline_terminal_deferred"] = False
        control_path.write_text(json.dumps(control, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        control_process, control_report = run_validator(control_path, temp_root / "control-output.json", deferred=False)
        control_valid = control_process.returncode == 0 and control_report.get("success") is True

        cases = (
            ("deferred_receipt_in_normal_mode", True, False),
            ("strict_receipt_in_deferred_mode", False, True),
            ("missing_receipt_mode_in_normal_mode", None, False),
            ("forged_receipt_mode_in_normal_mode", "false", False),
        )
        for index, (case_id, mode, deferred) in enumerate(cases, start=1):
            receipt = normalized_receipt(canonical)
            if mode is None:
                receipt.pop("safe_pipeline_terminal_deferred", None)
            else:
                receipt["safe_pipeline_terminal_deferred"] = mode
            receipt_path = temp_root / f"case-{index}-receipt.json"
            output_path = temp_root / f"case-{index}-output.json"
            receipt_path.write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            process, report = run_validator(receipt_path, output_path, deferred=deferred)
            checks = [str(item.get("check") or "") for item in report.get("failures") or []]
            results.append({
                "case_id": case_id,
                "tamper_rejected": process.returncode != 0 and "safe_pipeline_terminal_mode_exact" in checks,
                "expected_check": "safe_pipeline_terminal_mode_exact",
                "expected_check_observed": "safe_pipeline_terminal_mode_exact" in checks,
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
        "policy": "Only temporary consistency receipt copies are altered; a deferred receipt is valid only inside the safe runner terminal window.",
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
