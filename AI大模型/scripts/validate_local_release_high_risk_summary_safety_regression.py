#!/usr/bin/env python3
"""Prove high-risk local-release summary fields remain fail-closed."""

from __future__ import annotations

import copy
import hashlib
import json
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
RELEASE = AI_ROOT / "reports" / "local_release_manifest.json"
VALIDATOR = AI_ROOT / "scripts" / "validate_local_release_manifest_fail_closed_consistency.py"
OUTPUT = AI_ROOT / "reports" / "local_release_high_risk_summary_safety_regression_report.json"
PROTECTED_INPUTS = [
    RELEASE,
    AI_ROOT / "reports" / "model_artifact_claim_guard_report.json",
    AI_ROOT / "reports" / "five_head_training_execution_contract_report.json",
    AI_ROOT / "reports" / "active_stage_execution_matrix_report.json",
]

CASES = [
    {
        "case_id": "model_claim_forged_true",
        "field": "advanced_model_safe_for_model_claim",
        "value": True,
        "expected_check": "summary_false_risk_field",
    },
    {
        "case_id": "production_execution_forged_true",
        "field": "active_stage_execution_matrix_production_execution_allowed",
        "value": True,
        "expected_check": "summary_false_risk_field",
    },
    {
        "case_id": "selected_variant_forged",
        "field": "enzyme_agent_result_selected_variants",
        "value": 1,
        "expected_check": "summary_zero_risk_field",
    },
    {
        "case_id": "production_artifact_forged",
        "field": "model_artifact_claim_guard_production_artifacts",
        "value": 1,
        "expected_check": "summary_zero_risk_field",
    },
]


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    baseline = json.loads(RELEASE.read_text(encoding="utf-8"))
    before = {str(path): sha256(path) for path in PROTECTED_INPUTS}
    results: list[dict[str, Any]] = []

    with tempfile.TemporaryDirectory(prefix="release-high-risk-summary-") as temp_dir:
        temp_root = Path(temp_dir)
        for index, case in enumerate(CASES, start=1):
            tampered = copy.deepcopy(baseline)
            tampered.setdefault("readiness_summary", {})[case["field"]] = case["value"]
            release_path = temp_root / f"case-{index}.json"
            report_path = temp_root / f"case-{index}-validation.json"
            release_path.write_text(json.dumps(tampered, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            process = subprocess.run(
                [sys.executable, str(VALIDATOR), "--release", str(release_path), "--output", str(report_path)],
                cwd=AI_ROOT,
                text=True,
                capture_output=True,
                timeout=120,
            )
            validation = json.loads(report_path.read_text(encoding="utf-8")) if report_path.exists() else {}
            failures = validation.get("failures") or []
            exact_failure = any(
                failure.get("check") == case["expected_check"] and failure.get("field") == case["field"]
                for failure in failures
            )
            results.append({
                "case_id": case["case_id"],
                "field": case["field"],
                "tamper_rejected": process.returncode != 0 and exact_failure,
                "validator_returncode": process.returncode,
                "failure_count": len(failures),
                "expected_check_observed": exact_failure,
            })

    after = {str(path): sha256(path) for path in PROTECTED_INPUTS}
    real_inputs_mutated = before != after
    passed = sum(row["tamper_rejected"] for row in results)
    report = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "success": passed == len(results) and not real_inputs_mutated,
        "case_rows": len(results),
        "passed_rows": passed,
        "failed_rows": len(results) - passed,
        "real_inputs_mutated": real_inputs_mutated,
        "results": results,
        "safe_for_model_claim": False,
        "release_ready": False,
        "policy": "Regression mutates temporary release copies only; canonical release and high-risk source reports remain byte-identical.",
    }
    OUTPUT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
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
