#!/usr/bin/env python3
"""Validate the P699 fail-closed formal-decision readiness status board."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from build_p698_p0_real_input_formal_decision_readiness_false_positive_guard import (
    FALSE_FIELDS as P698_FALSE_FIELDS,
    load_json,
    load_jsonl,
)


AI_ROOT = Path(__file__).resolve().parents[1]
SOURCE_JSONL = AI_ROOT / "datasets/governance/p698_p0_real_input_formal_decision_readiness_false_positive_guard.jsonl"
SOURCE_VALIDATION = AI_ROOT / "reports/p698_p0_real_input_formal_decision_readiness_false_positive_guard_validation_report.json"
BOARD = AI_ROOT / "datasets/governance/p699_p0_real_input_formal_decision_readiness_status_board.jsonl"
REPORT = AI_ROOT / "reports/p699_p0_real_input_formal_decision_readiness_status_board_report.json"
OUT = AI_ROOT / "reports/p699_p0_real_input_formal_decision_readiness_status_board_validation_report.json"

FALSE_FIELDS = tuple(P698_FALSE_FIELDS) + (
    "formal_decision_readiness_reviewed",
    "formal_decision_readiness_approved",
)


def fail_if(condition: bool, failures: list[dict[str, Any]], check: str, observed: Any, expected: Any) -> None:
    if condition:
        failures.append({"check": check, "observed": observed, "expected": expected})


def main() -> int:
    source_validation = load_json(SOURCE_VALIDATION)
    source_rows = [row for row in load_jsonl(SOURCE_JSONL) if row.get("lane") != "summary"]
    rows = load_jsonl(BOARD)
    report = load_json(REPORT)
    failures: list[dict[str, Any]] = []
    lane_rows = rows[:-1] if rows else []
    summary = rows[-1] if rows else {}

    fail_if(source_validation.get("success") is not True, failures, "p698_validation_success", source_validation.get("success"), True)
    fail_if(len(source_rows) != 5, failures, "source_formal_decision_guard_rows_exact", len(source_rows), 5)
    fail_if(len(lane_rows) != 5, failures, "status_board_lane_rows_exact", len(lane_rows), 5)
    fail_if(summary.get("lane") != "summary", failures, "summary_row_present", summary.get("lane"), "summary")
    for field, expected in (
        ("audit_rows", 6),
        ("formal_decision_readiness_status_board_rows", 5),
        ("open_formal_decision_readiness_status_board_rows", 5),
        ("empty_formal_decision_readiness_status_board_rows", 5),
        ("blocked_formal_decision_readiness_status_board_rows", 5),
        ("formal_intake_dry_run_executed_rows", 0),
        ("formal_intake_dry_run_passed_rows", 0),
    ):
        fail_if(report.get(field) != expected, failures, f"report_{field}", report.get(field), expected)
    fail_if(
        report.get("formal_decision_readiness_status")
        != "open_empty_formal_decision_readiness_status_board",
        failures,
        "report_status",
        report.get("formal_decision_readiness_status"),
        "open_empty_formal_decision_readiness_status_board",
    )
    for field in FALSE_FIELDS:
        fail_if(report.get(field) is not False, failures, f"report_{field}_false", report.get(field), False)
        fail_if(report.get(f"{field}_rows") != 0, failures, f"report_{field}_rows_zero", report.get(f"{field}_rows"), 0)

    source_ids = {row.get("formal_decision_false_positive_guard_id") for row in source_rows}
    observed_source_ids = {row.get("source_formal_decision_false_positive_guard_id") for row in lane_rows}
    fail_if(observed_source_ids != source_ids, failures, "source_guard_ids_covered", observed_source_ids, source_ids)
    ids = [row.get("formal_decision_readiness_status_board_id") for row in lane_rows]
    fail_if(len(ids) != len(set(ids)), failures, "status_board_ids_unique", ids, "unique")
    orders = [row.get("formal_decision_readiness_status_board_order") for row in lane_rows]
    fail_if(orders != [1, 2, 3, 4, 5], failures, "status_board_order", orders, [1, 2, 3, 4, 5])
    for index, row in enumerate(lane_rows, start=1):
        fail_if(
            row.get("formal_decision_readiness_status")
            != "open_empty_formal_decision_readiness_status_board",
            failures,
            f"row_{index}_status",
            row.get("formal_decision_readiness_status"),
            "open_empty_formal_decision_readiness_status_board",
        )
        for field in (
            "formal_decision_readiness_status_open",
            "formal_decision_readiness_status_empty",
            "formal_decision_readiness_status_blocked",
        ):
            fail_if(row.get(field) is not True, failures, f"row_{index}_{field}", row.get(field), True)
        for field in (
            "formal_decision_readiness_status_board_id",
            "lane",
            "source_formal_decision_false_positive_guard_id",
            "formal_target_file",
            "blocker_reason",
            "next_unblocking_evidence",
            "validator_command",
            "operator_action",
            "completion_condition",
            "formal_decision_readiness_status_note",
            "policy",
        ):
            fail_if(row.get(field) in (None, "", []), failures, f"row_{index}_{field}_present", row.get(field), "present")
        for field in FALSE_FIELDS:
            fail_if(row.get(field) is not False, failures, f"row_{index}_{field}_false", row.get(field), False)

    for field, expected in (
        ("formal_decision_readiness_status_board_rows", 5),
        ("open_formal_decision_readiness_status_board_rows", 5),
        ("empty_formal_decision_readiness_status_board_rows", 5),
        ("blocked_formal_decision_readiness_status_board_rows", 5),
    ):
        fail_if(summary.get(field) != expected, failures, f"summary_{field}", summary.get(field), expected)
    for field in FALSE_FIELDS:
        fail_if(summary.get(field) is not False, failures, f"summary_{field}_false", summary.get(field), False)
        fail_if(summary.get(f"{field}_rows") != 0, failures, f"summary_{field}_rows_zero", summary.get(f"{field}_rows"), 0)

    result = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "local_only": True,
        "success": not failures,
        "failure_count": len(failures),
        "failures": failures,
        "manifest_id": "P699",
        "audit_rows": len(rows),
        "formal_decision_readiness_status_board_rows": len(lane_rows),
        "open_formal_decision_readiness_status_board_rows": sum(
            row.get("formal_decision_readiness_status_open") is True for row in lane_rows
        ),
        "empty_formal_decision_readiness_status_board_rows": sum(
            row.get("formal_decision_readiness_status_empty") is True for row in lane_rows
        ),
        "blocked_formal_decision_readiness_status_board_rows": sum(
            row.get("formal_decision_readiness_status_blocked") is True for row in lane_rows
        ),
        "formal_intake_dry_run_executed_rows": 0,
        "formal_intake_dry_run_passed_rows": 0,
        "policy": "Validation only. P699 confirms formal decision readiness status remains open, empty, and fail-closed.",
    }
    for field in FALSE_FIELDS:
        result[f"{field}_rows"] = sum(row.get(field) is True for row in lane_rows)
        result[field] = False
    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({
        "success": result["success"],
        "formal_decision_readiness_status_board_rows": result["formal_decision_readiness_status_board_rows"],
        "open_formal_decision_readiness_status_board_rows": result["open_formal_decision_readiness_status_board_rows"],
        "formal_decision_ready_rows": result["formal_decision_ready_rows"],
        "formal_decision_readiness_reviewed_rows": result["formal_decision_readiness_reviewed_rows"],
        "formal_decision_readiness_approved_rows": result["formal_decision_readiness_approved_rows"],
        "response_received_rows": result["response_received_rows"],
        "real_input_received_rows": result["real_input_received_rows"],
        "failures": result["failure_count"],
        "output": str(OUT),
    }, ensure_ascii=False))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
