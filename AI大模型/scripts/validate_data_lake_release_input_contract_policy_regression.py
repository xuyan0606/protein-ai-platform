#!/usr/bin/env python3
"""Prove the independent contract policy anchor rejects shared-module drift."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable


AI_ROOT = Path(__file__).resolve().parents[1]
CONTRACT_MODULE = AI_ROOT / "scripts" / "data_lake_release_input_contract.py"
VALIDATOR = AI_ROOT / "scripts" / "validate_data_lake_release_input_contract_policy.py"
OUTPUT = AI_ROOT / "reports" / "data_lake_release_input_contract_policy_regression_report.json"


def replace_exact(source: str, old: str, new: str) -> str:
    if source.count(old) != 1:
        raise RuntimeError(f"expected one replacement target: {old!r}")
    return source.replace(old, new, 1)


def main() -> int:
    source = CONTRACT_MODULE.read_text(encoding="utf-8")
    cases: list[tuple[str, Callable[[str], str], str]] = [
        (
            "contract_version_drift",
            lambda text: replace_exact(text, 'CONTRACT_VERSION = "data-lake-release-input-v1"', 'CONTRACT_VERSION = "data-lake-release-input-v2"'),
            "contract_version_exact",
        ),
        (
            "expanded_exclusion_set",
            lambda text: replace_exact(
                text,
                '    "reports/local_release_safety_guard_link_validation_report.json",\n',
                '    "reports/local_release_safety_guard_link_validation_report.json",\n    "reports/forged_release_output.json",\n',
            ),
            "contract_exclusion_paths_exact",
        ),
        (
            "removed_exclusion_path",
            lambda text: replace_exact(text, '    "reports/local_release_manifest.json",\n', ""),
            "contract_exclusion_paths_exact",
        ),
        (
            "canonical_json_drift",
            lambda text: replace_exact(text, 'separators=(",", ":")', 'separators=(", ", ": ")'),
            "test_vector_contract_sha256_exact",
        ),
    ]
    results: list[dict[str, object]] = []

    with tempfile.TemporaryDirectory(prefix="release-input-policy-") as temp_dir:
        temp_root = Path(temp_dir)
        control_report = temp_root / "control.json"
        control = subprocess.run(
            [sys.executable, str(VALIDATOR), "--contract-module", str(CONTRACT_MODULE), "--output", str(control_report)],
            cwd=AI_ROOT,
            text=True,
            capture_output=True,
            timeout=300,
        )
        control_validation = json.loads(control_report.read_text(encoding="utf-8")) if control_report.exists() else {}
        control_valid = control.returncode == 0 and control_validation.get("success") is True

        for index, (case_id, mutate, expected_check) in enumerate(cases, start=1):
            module_path = temp_root / f"case-{index}-contract.py"
            report_path = temp_root / f"case-{index}-validation.json"
            module_path.write_text(mutate(source), encoding="utf-8")
            process = subprocess.run(
                [sys.executable, str(VALIDATOR), "--contract-module", str(module_path), "--output", str(report_path)],
                cwd=AI_ROOT,
                text=True,
                capture_output=True,
                timeout=300,
            )
            validation = json.loads(report_path.read_text(encoding="utf-8")) if report_path.exists() else {}
            checks = [str(item.get("check") or "") for item in validation.get("failures") or []]
            results.append({
                "case_id": case_id,
                "tamper_rejected": process.returncode != 0 and expected_check in checks,
                "expected_check": expected_check,
                "expected_check_observed": expected_check in checks,
                "failure_count": int(validation.get("failure_count") or 0),
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
        "policy": "Only temporary contract-module copies are mutated; the canonical shared module remains unchanged.",
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
