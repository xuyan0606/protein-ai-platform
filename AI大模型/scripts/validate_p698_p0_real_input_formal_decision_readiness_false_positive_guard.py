#!/usr/bin/env python3
"""Validate the P698 fail-closed formal-decision readiness guard."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
SOURCE_JSONL = AI_ROOT / "datasets/governance/p697_p0_real_input_blocker_escalation_review_evidence_missing_matrix.jsonl"
SOURCE_VALIDATION = AI_ROOT / "reports/p697_p0_real_input_blocker_escalation_review_evidence_missing_matrix_validation_report.json"
GUARD = AI_ROOT / "datasets/governance/p698_p0_real_input_formal_decision_readiness_false_positive_guard.jsonl"
REPORT = AI_ROOT / "reports/p698_p0_real_input_formal_decision_readiness_false_positive_guard_report.json"
OUT = AI_ROOT / "reports/p698_p0_real_input_formal_decision_readiness_false_positive_guard_validation_report.json"

FALSE_FIELDS = (
    "queue_dequeued", "operator_dispatch_sent", "operator_acknowledged",
    "owner_assigned", "owner_acknowledged", "external_input_acknowledged",
    "receive_preflight_executed", "response_payload_present", "response_received",
    "response_validated", "real_input_received", "evidence_payload_present",
    "evidence_received", "evidence_validated", "evidence_quarantined",
    "evidence_released", "evidence_promoted_to_decision", "decision_route_executed",
    "routed_to_formal_review", "formal_intake_dry_run_executed",
    "formal_intake_dry_run_passed", "formal_validator_passed",
    "reviewed_decision_written", "formal_intake_written", "runtime_receipt_written",
    "training_label_written", "formal_decision_ready", "false_positive_cleared",
    "aging_reviewed", "staleness_resolved", "escalation_reviewed", "escalation_sent",
    "escalation_acknowledged", "blocker_resolved", "closeout_ready",
    "completion_ready_observed", "completion_ready", "p0_unblocked",
    "p0_completion_ready", "training_import_allowed", "safe_for_training_import",
    "safe_for_model_claim", "customer_delivery_ready", "release_ready",
    "production_execution_allowed",
)


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    value = json.loads(path.read_text(encoding="utf-8"))
    return value if isinstance(value, dict) else {}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def fail_if(condition: bool, failures: list[dict[str, Any]], check: str, observed: Any, expected: Any) -> None:
    if condition:
        failures.append({"check": check, "observed": observed, "expected": expected})


def main() -> int:
    source_validation = load_json(SOURCE_VALIDATION)
    source_rows = [row for row in load_jsonl(SOURCE_JSONL) if row.get("lane") != "summary"]
    rows = load_jsonl(GUARD)
    report = load_json(REPORT)
    failures: list[dict[str, Any]] = []
    lane_rows = rows[:-1] if rows else []
    summary = rows[-1] if rows else {}

    fail_if(source_validation.get("success") is not True, failures, "p697_validation_success", source_validation.get("success"), True)
    fail_if(len(source_rows) != 5, failures, "source_evidence_missing_matrix_rows_exact", len(source_rows), 5)
    fail_if(len(lane_rows) != 5, failures, "formal_decision_guard_lane_rows_exact", len(lane_rows), 5)
    fail_if(summary.get("lane") != "summary", failures, "summary_row_present", summary.get("lane"), "summary")
    for field, expected in (
        ("audit_rows", 6),
        ("formal_decision_false_positive_guard_rows", 5),
        ("open_formal_decision_false_positive_guard_rows", 5),
        ("empty_formal_decision_false_positive_guard_rows", 5),
        ("blocked_formal_decision_false_positive_guard_rows", 5),
        ("formal_intake_dry_run_executed_rows", 0),
        ("formal_intake_dry_run_passed_rows", 0),
    ):
        fail_if(report.get(field) != expected, failures, f"report_{field}", report.get(field), expected)
    fail_if(
        report.get("formal_decision_false_positive_guard_status")
        != "open_empty_formal_decision_readiness_false_positive_guard",
        failures,
        "report_status",
        report.get("formal_decision_false_positive_guard_status"),
        "open_empty_formal_decision_readiness_false_positive_guard",
    )
    for field in FALSE_FIELDS:
        fail_if(report.get(field) is not False, failures, f"report_{field}_false", report.get(field), False)
        fail_if(report.get(f"{field}_rows") != 0, failures, f"report_{field}_rows_zero", report.get(f"{field}_rows"), 0)

    source_ids = {row.get("evidence_missing_matrix_id") for row in source_rows}
    observed_source_ids = {row.get("source_evidence_missing_matrix_id") for row in lane_rows}
    fail_if(observed_source_ids != source_ids, failures, "source_evidence_missing_matrix_ids_covered", observed_source_ids, source_ids)
    ids = [row.get("formal_decision_false_positive_guard_id") for row in lane_rows]
    fail_if(len(ids) != len(set(ids)), failures, "formal_decision_guard_ids_unique", ids, "unique")
    orders = [row.get("formal_decision_false_positive_guard_order") for row in lane_rows]
    fail_if(orders != [1, 2, 3, 4, 5], failures, "formal_decision_guard_order", orders, [1, 2, 3, 4, 5])
    for index, row in enumerate(lane_rows, start=1):
        fail_if(
            row.get("formal_decision_false_positive_guard_status")
            != "open_empty_formal_decision_readiness_false_positive_guard",
            failures,
            f"row_{index}_status",
            row.get("formal_decision_false_positive_guard_status"),
            "open_empty_formal_decision_readiness_false_positive_guard",
        )
        for field in (
            "formal_decision_false_positive_guard_open",
            "formal_decision_false_positive_guard_empty",
            "formal_decision_false_positive_guard_blocked",
        ):
            fail_if(row.get(field) is not True, failures, f"row_{index}_{field}", row.get(field), True)
        for field in (
            "formal_decision_false_positive_guard_id",
            "lane",
            "source_evidence_missing_matrix_id",
            "formal_target_file",
            "blocker_reason",
            "next_unblocking_evidence",
            "validator_command",
            "operator_action",
            "completion_condition",
            "formal_decision_false_positive_reason",
            "formal_decision_false_positive_note",
            "policy",
        ):
            fail_if(row.get(field) in (None, "", []), failures, f"row_{index}_{field}_present", row.get(field), "present")
        for field in FALSE_FIELDS:
            fail_if(row.get(field) is not False, failures, f"row_{index}_{field}_false", row.get(field), False)

    for field, expected in (
        ("formal_decision_false_positive_guard_rows", 5),
        ("open_formal_decision_false_positive_guard_rows", 5),
        ("empty_formal_decision_false_positive_guard_rows", 5),
        ("blocked_formal_decision_false_positive_guard_rows", 5),
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
        "manifest_id": "P698",
        "audit_rows": len(rows),
        "formal_decision_false_positive_guard_rows": len(lane_rows),
        "open_formal_decision_false_positive_guard_rows": sum(
            row.get("formal_decision_false_positive_guard_open") is True for row in lane_rows
        ),
        "empty_formal_decision_false_positive_guard_rows": sum(
            row.get("formal_decision_false_positive_guard_empty") is True for row in lane_rows
        ),
        "blocked_formal_decision_false_positive_guard_rows": sum(
            row.get("formal_decision_false_positive_guard_blocked") is True for row in lane_rows
        ),
        "formal_intake_dry_run_executed_rows": 0,
        "formal_intake_dry_run_passed_rows": 0,
        "policy": "Validation only. P698 confirms formal decision readiness remains guarded, empty, and fail-closed.",
    }
    for field in FALSE_FIELDS:
        result[f"{field}_rows"] = sum(row.get(field) is True for row in lane_rows)
        result[field] = False
    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({
        "success": result["success"],
        "formal_decision_false_positive_guard_rows": result["formal_decision_false_positive_guard_rows"],
        "open_formal_decision_false_positive_guard_rows": result["open_formal_decision_false_positive_guard_rows"],
        "formal_decision_ready_rows": result["formal_decision_ready_rows"],
        "false_positive_cleared_rows": result["false_positive_cleared_rows"],
        "response_received_rows": result["response_received_rows"],
        "real_input_received_rows": result["real_input_received_rows"],
        "failures": result["failure_count"],
        "output": str(OUT),
    }, ensure_ascii=False))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
