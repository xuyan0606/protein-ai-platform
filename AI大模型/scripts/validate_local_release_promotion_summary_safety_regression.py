#!/usr/bin/env python3
"""Prove local-release promotion summaries cannot drift from source reports."""

from __future__ import annotations

import copy
import hashlib
import json
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable


AI_ROOT = Path(__file__).resolve().parents[1]
RELEASE = AI_ROOT / "reports" / "local_release_manifest.json"
VALIDATOR = AI_ROOT / "scripts" / "validate_local_release_manifest_fail_closed_consistency.py"
OUTPUT = AI_ROOT / "reports" / "local_release_promotion_summary_safety_regression_report.json"
PROTECTED_INPUTS = [
    RELEASE,
    AI_ROOT / "reports" / "ready_to_verify_promotion_board.json",
    AI_ROOT / "reports" / "ready_to_verify_promotion_validation_report.json",
    AI_ROOT / "reports" / "ready_to_verify_promotion_safety_regression_report.json",
]


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def mutate_summary(release: dict[str, Any], field: str, value: Any) -> None:
    release.setdefault("readiness_summary", {})[field] = value


def main() -> int:
    baseline = json.loads(RELEASE.read_text(encoding="utf-8"))
    before = {str(path): sha256(path) for path in PROTECTED_INPUTS}
    cases: list[tuple[str, Callable[[dict[str, Any]], None]]] = [
        ("audit_rows_drift", lambda release: mutate_summary(release, "ready_to_verify_promotion_audit_rows", 7)),
        ("local_artifact_rows_drift", lambda release: mutate_summary(release, "ready_to_verify_promotion_local_artifact_rows", 3)),
        ("automatic_promotion_forged", lambda release: mutate_summary(release, "ready_to_verify_promotion_automatic_rows", 1)),
        ("promotion_validation_forged_false", lambda release: mutate_summary(release, "ready_to_verify_promotion_validation_success", False)),
    ]
    results: list[dict[str, Any]] = []

    with tempfile.TemporaryDirectory(prefix="release-promotion-summary-") as temp_dir:
        temp_root = Path(temp_dir)
        for index, (case_id, mutate) in enumerate(cases, start=1):
            tampered = copy.deepcopy(baseline)
            mutate(tampered)
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
            rejected = process.returncode != 0 and bool(validation.get("failures"))
            results.append({
                "case_id": case_id,
                "tamper_rejected": rejected,
                "validator_returncode": process.returncode,
                "failure_count": len(validation.get("failures") or []),
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
        "policy": "Regression mutates temporary release copies only; canonical release and promotion reports must remain byte-identical.",
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
