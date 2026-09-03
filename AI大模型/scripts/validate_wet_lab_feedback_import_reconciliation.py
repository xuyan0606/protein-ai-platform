#!/usr/bin/env python3
"""Validate wet-lab feedback import reconciliation."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
REPORT = AI_ROOT / "reports" / "wet_lab_feedback_import_reconciliation_report.json"
OUTPUT = AI_ROOT / "reports" / "wet_lab_feedback_import_reconciliation_validation_report.json"


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    value = json.loads(path.read_text(encoding="utf-8"))
    return value if isinstance(value, dict) else {}


def as_int(value: Any) -> int:
    if isinstance(value, bool):
        return int(value)
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def fail_if(condition: bool, failures: list[dict[str, Any]], check: str, observed: Any, expected: Any) -> None:
    if condition:
        failures.append({"check": check, "observed": observed, "expected": expected})


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate wet-lab feedback import reconciliation")
    parser.add_argument("--report", type=Path, default=REPORT)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    args = parser.parse_args()

    report = load_json(args.report)
    counts = report.get("counts") if isinstance(report.get("counts"), dict) else {}
    failures: list[dict[str, Any]] = []

    fail_if(not report, failures, "report_present", str(args.report), "existing JSON report")
    fail_if(bool(report.get("missing_sources")), failures, "source_reports_present", report.get("missing_sources"), [])
    fail_if(bool(report.get("consistency_failures")), failures, "no_consistency_failures", report.get("consistency_failures"), [])
    fail_if(as_int(counts.get("wetlab_authorized_rows")) != 8, failures, "wetlab_authorized_rows_current", counts.get("wetlab_authorized_rows"), 8)
    fail_if(as_int(counts.get("wetlab_preflight_rows")) != 8, failures, "wetlab_preflight_rows_current", counts.get("wetlab_preflight_rows"), 8)
    fail_if(as_int(counts.get("wetlab_apply_plan_rows")) != 8, failures, "wetlab_apply_plan_rows_current", counts.get("wetlab_apply_plan_rows"), 8)
    fail_if(as_int(counts.get("wetlab_applied_rows")) != 0, failures, "wetlab_applied_rows_zero", counts.get("wetlab_applied_rows"), 0)
    fail_if(as_int(counts.get("duplicate_safe_to_append_rows")) != 0, failures, "duplicate_safe_to_append_rows_zero", counts.get("duplicate_safe_to_append_rows"), 0)
    fail_if(as_int(counts.get("duplicate_training_import_from_apply_plan_rows")) != 0, failures, "apply_plan_training_rows_zero", counts.get("duplicate_training_import_from_apply_plan_rows"), 0)
    fail_if(as_int(counts.get("local_feedback_numeric_training_eligible_rows")) != 6, failures, "local_feedback_numeric_rows_current", counts.get("local_feedback_numeric_training_eligible_rows"), 6)
    fail_if(as_int(counts.get("semantic_numeric_training_import_eligible_rows")) != 6, failures, "semantic_numeric_rows_current", counts.get("semantic_numeric_training_import_eligible_rows"), 6)
    fail_if(as_int(counts.get("contract_training_import_eligible_rows")) != 6, failures, "contract_training_import_rows_current", counts.get("contract_training_import_eligible_rows"), 6)
    fail_if(as_int(counts.get("model_quality_training_import_eligible_rows")) != 6, failures, "model_quality_training_import_rows_current", counts.get("model_quality_training_import_eligible_rows"), 6)
    fail_if(as_int(counts.get("strict_supervised_rows")) != 0, failures, "strict_supervised_rows_zero", counts.get("strict_supervised_rows"), 0)
    fail_if(as_int(counts.get("claim_eligible_rows")) != 0, failures, "claim_eligible_rows_zero", counts.get("claim_eligible_rows"), 0)
    fail_if(report.get("safe_for_training_import") is not False, failures, "safe_for_training_import_false", report.get("safe_for_training_import"), False)
    fail_if(report.get("safe_for_model_claim") is not False, failures, "safe_for_model_claim_false", report.get("safe_for_model_claim"), False)
    fail_if(report.get("release_ready") is not False, failures, "release_ready_false", report.get("release_ready"), False)

    validation = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "local_only": True,
        "success": not failures,
        "counts": counts,
        "failures": failures,
        "safe_for_model_claim": False,
        "release_ready": False,
        "policy": (
            "This validator locks the current separation between wet-lab apply/import counters and local numeric "
            "feedback training-import counters. It must fail if append/import/model/release flags are inflated."
        ),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(validation, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "success": validation["success"],
                "wetlab_applied_rows": as_int(counts.get("wetlab_applied_rows")),
                "numeric_training_import_eligible_rows": as_int(
                    counts.get("semantic_numeric_training_import_eligible_rows")
                ),
                "failures": len(failures),
                "output": str(args.output),
            },
            ensure_ascii=False,
        )
    )
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
