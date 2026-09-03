#!/usr/bin/env python3
"""Validate the P686 P0 real-input formal intake dry-run guard shell."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
P685_VALIDATION = AI_ROOT / "reports" / "p685_p0_real_input_response_decision_routing_validation_report.json"
SOURCE_ROUTING = AI_ROOT / "datasets" / "governance" / "p685_p0_real_input_response_decision_routing.jsonl"
GUARD = AI_ROOT / "datasets" / "governance" / "p686_p0_real_input_formal_intake_dry_run_guard.jsonl"
REPORT = AI_ROOT / "reports" / "p686_p0_real_input_formal_intake_dry_run_guard_report.json"
OUT = AI_ROOT / "reports" / "p686_p0_real_input_formal_intake_dry_run_guard_validation_report.json"

FALSE_FIELDS = (
    "operator_dispatch_sent",
    "operator_acknowledged",
    "external_input_acknowledged",
    "receive_preflight_executed",
    "response_payload_present",
    "response_received",
    "response_validated",
    "real_input_received",
    "evidence_payload_present",
    "evidence_quarantined",
    "evidence_released",
    "evidence_promoted_to_decision",
    "decision_route_executed",
    "routed_to_formal_review",
    "formal_intake_dry_run_executed",
    "formal_intake_dry_run_passed",
    "formal_validator_passed",
    "reviewed_decision_written",
    "formal_intake_written",
    "runtime_receipt_written",
    "training_label_written",
    "completion_ready",
    "p0_unblocked",
    "training_import_allowed",
    "safe_for_training_import",
    "safe_for_model_claim",
    "customer_delivery_ready",
    "release_ready",
    "production_execution_allowed",
)

ZERO_ROW_FIELDS = tuple(f"{field}_rows" for field in FALSE_FIELDS)


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
    p685_validation = load_json(P685_VALIDATION)
    source_rows = [row for row in load_jsonl(SOURCE_ROUTING) if row.get("lane") != "summary"]
    rows = load_jsonl(GUARD)
    report = load_json(REPORT)
    failures: list[dict[str, Any]] = []
    lane_rows = rows[:-1] if rows else []
    summary = rows[-1] if rows else {}

    fail_if(p685_validation.get("success") is not True, failures, "p685_validation_success", p685_validation.get("success"), True)
    fail_if(len(source_rows) != 5, failures, "source_routing_lane_rows_exact", len(source_rows), 5)
    fail_if(len(lane_rows) != 5, failures, "guard_lane_rows_exact", len(lane_rows), 5)
    fail_if(summary.get("lane") != "summary", failures, "summary_row_present", summary.get("lane"), "summary")
    fail_if(report.get("audit_rows") != 6, failures, "report_audit_rows", report.get("audit_rows"), 6)
    fail_if(report.get("formal_intake_dry_run_rows") != 5, failures, "report_guard_rows", report.get("formal_intake_dry_run_rows"), 5)
    fail_if(report.get("open_formal_intake_dry_run_rows") != 5, failures, "report_open_rows", report.get("open_formal_intake_dry_run_rows"), 5)
    fail_if(report.get("empty_formal_intake_dry_run_rows") != 5, failures, "report_empty_rows", report.get("empty_formal_intake_dry_run_rows"), 5)
    fail_if(report.get("blocked_formal_intake_dry_run_rows") != 5, failures, "report_blocked_rows", report.get("blocked_formal_intake_dry_run_rows"), 5)
    fail_if(
        report.get("formal_intake_dry_run_status") != "open_empty_formal_intake_dry_run_guard",
        failures,
        "report_status",
        report.get("formal_intake_dry_run_status"),
        "open_empty_formal_intake_dry_run_guard",
    )
    for field in ZERO_ROW_FIELDS:
        fail_if(report.get(field) != 0, failures, f"report_{field}_zero", report.get(field), 0)
    for field in FALSE_FIELDS:
        fail_if(report.get(field) is not False, failures, f"report_{field}_false", report.get(field), False)

    guard_ids = [row.get("formal_intake_dry_run_id") for row in lane_rows]
    fail_if(len(guard_ids) != len(set(guard_ids)), failures, "formal_intake_dry_run_ids_unique", guard_ids, "unique")
    source_ids = {row.get("decision_routing_id") for row in source_rows}
    fail_if(
        {row.get("source_decision_routing_id") for row in lane_rows} != source_ids,
        failures,
        "source_decision_routing_ids_covered",
        {row.get("source_decision_routing_id") for row in lane_rows},
        source_ids,
    )
    orders = [row.get("formal_intake_dry_run_order") for row in lane_rows]
    fail_if(orders != sorted(orders), failures, "formal_intake_dry_run_order_sorted", orders, "ascending")
    for index, row in enumerate(lane_rows, start=1):
        fail_if(row.get("formal_intake_dry_run_order") != index, failures, "row_order", {"row": index, "value": row.get("formal_intake_dry_run_order")}, index)
        fail_if(
            row.get("formal_intake_dry_run_status") != "open_empty_formal_intake_dry_run_guard",
            failures,
            "row_status",
            {"row": index, "value": row.get("formal_intake_dry_run_status")},
            "open_empty_formal_intake_dry_run_guard",
        )
        fail_if(row.get("formal_intake_dry_run_open") is not True, failures, "row_open", {"row": index, "value": row.get("formal_intake_dry_run_open")}, True)
        fail_if(row.get("formal_intake_dry_run_empty") is not True, failures, "row_empty", {"row": index, "value": row.get("formal_intake_dry_run_empty")}, True)
        fail_if(row.get("formal_intake_dry_run_blocked") is not True, failures, "row_blocked", {"row": index, "value": row.get("formal_intake_dry_run_blocked")}, True)
        for field in (
            "formal_intake_dry_run_id",
            "lane",
            "source_decision_routing_id",
            "formal_target_file",
            "expected_response_fields",
            "response_envelope_required_fields",
            "validator_command",
            "operator_action",
            "completion_condition",
            "dry_run_blocker",
            "policy",
        ):
            fail_if(row.get(field) in (None, "", []), failures, f"row_{field}_present", {"row": index, "value": row.get(field)}, "present")
        for field in FALSE_FIELDS:
            fail_if(row.get(field) is not False, failures, f"row_{field}_false", {"row": index, "value": row.get(field)}, False)

    fail_if(summary.get("formal_intake_dry_run_rows") != 5, failures, "summary_guard_rows", summary.get("formal_intake_dry_run_rows"), 5)
    fail_if(summary.get("open_formal_intake_dry_run_rows") != 5, failures, "summary_open_rows", summary.get("open_formal_intake_dry_run_rows"), 5)
    fail_if(summary.get("empty_formal_intake_dry_run_rows") != 5, failures, "summary_empty_rows", summary.get("empty_formal_intake_dry_run_rows"), 5)
    fail_if(summary.get("blocked_formal_intake_dry_run_rows") != 5, failures, "summary_blocked_rows", summary.get("blocked_formal_intake_dry_run_rows"), 5)
    for field in ZERO_ROW_FIELDS:
        fail_if(summary.get(field) != 0, failures, f"summary_{field}_zero", summary.get(field), 0)
    for field in FALSE_FIELDS:
        fail_if(summary.get(field) is not False, failures, f"summary_{field}_false", summary.get(field), False)

    result = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "local_only": True,
        "success": not failures,
        "failure_count": len(failures),
        "failures": failures,
        "manifest_id": "P686",
        "audit_rows": len(rows),
        "formal_intake_dry_run_rows": len(lane_rows),
        "open_formal_intake_dry_run_rows": sum(1 for row in lane_rows if row.get("formal_intake_dry_run_open") is True),
        "empty_formal_intake_dry_run_rows": sum(1 for row in lane_rows if row.get("formal_intake_dry_run_empty") is True),
        "blocked_formal_intake_dry_run_rows": sum(1 for row in lane_rows if row.get("formal_intake_dry_run_blocked") is True),
        "policy": "Validation only. P686 confirms formal intake dry-run guard rows are bound but empty and fail-closed.",
    }
    for field in FALSE_FIELDS:
        result[f"{field}_rows"] = sum(1 for row in lane_rows if row.get(field) is True)
        result[field] = False
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({
        "success": result["success"],
        "formal_intake_dry_run_rows": result["formal_intake_dry_run_rows"],
        "open_formal_intake_dry_run_rows": result["open_formal_intake_dry_run_rows"],
        "formal_intake_dry_run_executed_rows": result["formal_intake_dry_run_executed_rows"],
        "formal_intake_written_rows": result["formal_intake_written_rows"],
        "response_received_rows": result["response_received_rows"],
        "real_input_received_rows": result["real_input_received_rows"],
        "failures": result["failure_count"],
        "output": str(OUT),
    }, ensure_ascii=False))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
