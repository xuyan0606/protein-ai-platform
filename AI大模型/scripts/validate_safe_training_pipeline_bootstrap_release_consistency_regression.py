#!/usr/bin/env python3
"""Validate safe-pipeline receipt checks are non-recursive in release guards."""

from __future__ import annotations

import importlib.util
import json
from datetime import datetime, timezone
from pathlib import Path
from types import ModuleType
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
CONSISTENCY = AI_ROOT / "scripts" / "validate_local_release_manifest_fail_closed_consistency.py"
SAFETY_LINKS = AI_ROOT / "scripts" / "validate_local_release_safety_guard_links.py"
OUT = AI_ROOT / "reports" / "safe_training_pipeline_bootstrap_release_consistency_regression_report.json"

FORBIDDEN_DIRECT_VALIDATION_LINK = "safe_training_pipeline_current_receipt_validation"
FORBIDDEN_DIRECT_SUCCESS_FIELD = "safe_training_pipeline_current_receipt_success"
FORBIDDEN_DIRECT_FAILURE_FIELD = "safe_training_pipeline_current_receipt_failures"

REQUIRED_ATOMICITY_LINK = "safe_training_pipeline_receipt_atomicity_regression"
REQUIRED_ATOMICITY_SUCCESS_FIELD = "safe_training_pipeline_receipt_atomicity_regression_success"


def load_module(path: Path, name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def check(condition: bool, check_name: str, observed: Any, expected: Any) -> dict[str, Any]:
    return {
        "check": check_name,
        "passed": condition,
        "observed": observed,
        "expected": expected,
    }


def main() -> int:
    consistency = load_module(CONSISTENCY, "release_consistency_contract")
    safety_links = load_module(SAFETY_LINKS, "release_safety_links_contract")

    consistency_success = set(consistency.REQUIRED_SUCCESS_SUMMARY_FLAGS)
    consistency_zero = set(consistency.REQUIRED_ZERO_SUMMARY_FIELDS)
    safety_required_links = dict(safety_links.REQUIRED_GUARD_LINKS)
    safety_success = set(safety_links.REQUIRED_SUMMARY_TRUE_FIELDS)

    checks = [
        check(
            FORBIDDEN_DIRECT_SUCCESS_FIELD not in consistency_success,
            "consistency_does_not_require_current_receipt_success",
            FORBIDDEN_DIRECT_SUCCESS_FIELD in consistency_success,
            False,
        ),
        check(
            FORBIDDEN_DIRECT_FAILURE_FIELD not in consistency_zero,
            "consistency_does_not_require_current_receipt_failure_count",
            FORBIDDEN_DIRECT_FAILURE_FIELD in consistency_zero,
            False,
        ),
        check(
            REQUIRED_ATOMICITY_SUCCESS_FIELD in consistency_success,
            "consistency_requires_atomicity_regression_success",
            REQUIRED_ATOMICITY_SUCCESS_FIELD in consistency_success,
            True,
        ),
        check(
            "safe_training_pipeline_current_receipt_regression_success" not in consistency_success,
            "consistency_does_not_require_current_receipt_regression_success_during_bootstrap",
            "safe_training_pipeline_current_receipt_regression_success" in consistency_success,
            False,
        ),
        check(
            "safe_training_pipeline_current_receipt_regression_failed_rows" not in consistency_zero,
            "consistency_does_not_require_current_receipt_regression_failure_count_during_bootstrap",
            "safe_training_pipeline_current_receipt_regression_failed_rows" in consistency_zero,
            False,
        ),
        check(
            FORBIDDEN_DIRECT_VALIDATION_LINK not in safety_required_links,
            "safety_links_do_not_require_current_receipt_validation_report",
            FORBIDDEN_DIRECT_VALIDATION_LINK in safety_required_links,
            False,
        ),
        check(
            FORBIDDEN_DIRECT_SUCCESS_FIELD not in safety_success,
            "safety_links_do_not_require_current_receipt_success_summary",
            FORBIDDEN_DIRECT_SUCCESS_FIELD in safety_success,
            False,
        ),
        check(
            REQUIRED_ATOMICITY_LINK in safety_required_links,
            "safety_links_require_atomicity_regression_report",
            REQUIRED_ATOMICITY_LINK in safety_required_links,
            True,
        ),
        check(
            REQUIRED_ATOMICITY_SUCCESS_FIELD in safety_success,
            "safety_links_require_atomicity_regression_success",
            REQUIRED_ATOMICITY_SUCCESS_FIELD in safety_success,
            True,
        ),
        check(
            "safe_training_pipeline_current_receipt_regression" not in safety_required_links,
            "safety_links_defer_current_receipt_regression_report",
            "safe_training_pipeline_current_receipt_regression" in safety_required_links,
            False,
        ),
        check(
            "safe_training_pipeline_current_receipt_regression_success" not in safety_success,
            "safety_links_defer_current_receipt_regression_success",
            "safe_training_pipeline_current_receipt_regression_success" in safety_success,
            False,
        ),
    ]
    failed = [row for row in checks if row["passed"] is not True]
    report = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "local_only": True,
        "success": not failed,
        "check_rows": len(checks),
        "passed_rows": len(checks) - len(failed),
        "failed_rows": len(failed),
        "failures": failed,
        "real_inputs_mutated": False,
        "safe_for_model_claim": False,
        "release_ready": False,
        "policy": "Release consistency and safety links must avoid direct dependency on the current safe-pipeline receipt validation, because the safe pipeline writes that receipt at terminal commit time. Atomicity and current-receipt regression coverage remain required.",
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "success": report["success"],
        "check_rows": report["check_rows"],
        "passed_rows": report["passed_rows"],
        "failed_rows": report["failed_rows"],
        "real_inputs_mutated": False,
        "output": str(OUT),
    }, ensure_ascii=False))
    return 0 if report["success"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
