#!/usr/bin/env python3
"""Prove newly introduced high-risk release fields require explicit classification."""

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
OUTPUT = AI_ROOT / "reports" / "local_release_high_risk_coverage_safety_regression_report.json"
PROTECTED_INPUTS = [
    RELEASE,
    AI_ROOT / "reports" / "five_head_training_execution_contract_report.json",
    AI_ROOT / "reports" / "review_draft_formal_boundary_validation_report.json",
]

CASES = [
    ("unclassified_model_claim", "future_backend_safe_for_model_claim", False),
    ("unclassified_production_execution", "future_backend_production_execution_allowed", False),
    ("unclassified_formal_decision", "future_backend_formal_decision_rows", 0),
    ("unclassified_release_ready", "future_backend_release_ready", False),
]


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    baseline = json.loads(RELEASE.read_text(encoding="utf-8"))
    before = {str(path): sha256(path) for path in PROTECTED_INPUTS}
    results: list[dict[str, Any]] = []

    with tempfile.TemporaryDirectory(prefix="release-high-risk-coverage-") as temp_dir:
        temp_root = Path(temp_dir)
        for index, (case_id, field, value) in enumerate(CASES, start=1):
            tampered = copy.deepcopy(baseline)
            tampered.setdefault("readiness_summary", {})[field] = value
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
                failure.get("check") == "unclassified_high_risk_summary_fields"
                and field in (failure.get("observed") or [])
                for failure in failures
            )
            results.append({
                "case_id": case_id,
                "field": field,
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
        "policy": "Any new high-risk summary field requires explicit validator classification before it can appear in the local release manifest.",
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
