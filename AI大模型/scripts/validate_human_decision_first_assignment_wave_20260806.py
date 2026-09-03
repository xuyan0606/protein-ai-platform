#!/usr/bin/env python3
"""Validate first human-decision assignment wave without approving decisions."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INPUT = ROOT / "reports" / "human_decision_first_assignment_wave_20260806.json"
DEFAULT_OUTPUT = ROOT / "reports" / "human_decision_first_assignment_wave_validation_report_20260806.json"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    package = json.loads(args.input.read_text(encoding="utf-8"))
    failures = []
    for item in package.get("assignments", []):
        assignment_id = item.get("assignment_id")
        if not item.get("target_batch_id"):
            failures.append({"assignment_id": assignment_id, "check": "target_batch_id"})
        if int(item.get("target_row_count") or 0) <= 0:
            failures.append({"assignment_id": assignment_id, "check": "target_row_count_positive"})
        if not item.get("pending_row_ids"):
            failures.append({"assignment_id": assignment_id, "check": "pending_row_ids"})
        if not item.get("minimum_required_fields"):
            failures.append({"assignment_id": assignment_id, "check": "minimum_required_fields"})
        if not item.get("validate_command"):
            failures.append({"assignment_id": assignment_id, "check": "validate_command"})
        if item.get("assigned_reviewer") not in (None, ""):
            failures.append({"assignment_id": assignment_id, "check": "assigned_reviewer_prepopulated"})
        if item.get("formal_decision_rows_written") != 0:
            failures.append({"assignment_id": assignment_id, "check": "formal_decision_rows_written"})
        if item.get("release_ready") is not False or item.get("safe_for_model_claim") is not False:
            failures.append({"assignment_id": assignment_id, "check": "release_flags"})
    report = {
        "schema_version": 1,
        "success": not failures,
        "status": "valid_pending_assignment" if not failures else "invalid",
        "assignment_count": len(package.get("assignments", [])),
        "target_rows": sum(int(item.get("target_row_count") or 0) for item in package.get("assignments", [])),
        "failure_count": len(failures),
        "failures": failures,
        "formal_decision_rows_written": 0,
        "release_ready": False,
        "safe_for_model_claim": False,
    }
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "success": report["success"],
        "status": report["status"],
        "assignment_count": report["assignment_count"],
        "target_rows": report["target_rows"],
        "failure_count": report["failure_count"],
        "output": str(args.output),
    }, ensure_ascii=False))
    return 0 if report["success"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
