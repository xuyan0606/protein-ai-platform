#!/usr/bin/env python3
"""Validate the P682 P0 real-input response receive preflight."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
P681_VALIDATION = AI_ROOT / "reports" / "p681_p0_real_input_operator_dispatch_bundle_validation_report.json"
SOURCE_BUNDLE = AI_ROOT / "datasets" / "governance" / "p681_p0_real_input_operator_dispatch_bundle.jsonl"
PREFLIGHT = AI_ROOT / "datasets" / "governance" / "p682_p0_real_input_response_receive_preflight.jsonl"
REPORT = AI_ROOT / "reports" / "p682_p0_real_input_response_receive_preflight_report.json"
OUT = AI_ROOT / "reports" / "p682_p0_real_input_response_receive_preflight_validation_report.json"

FALSE_FIELDS = (
    "operator_dispatch_sent",
    "operator_acknowledged",
    "external_input_acknowledged",
    "response_payload_present",
    "response_received",
    "response_validated",
    "real_input_received",
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

ZERO_ROW_FIELDS = (
    "receive_preflight_executed_rows",
    "operator_dispatch_sent_rows",
    "operator_acknowledged_rows",
    "external_input_acknowledged_rows",
    "response_payload_present_rows",
    "response_received_rows",
    "response_validated_rows",
    "real_input_received_rows",
    "formal_validator_passed_rows",
    "reviewed_decision_written_rows",
    "formal_intake_written_rows",
    "runtime_receipt_written_rows",
    "training_label_written_rows",
    "completion_ready_rows",
    "p0_unblocked_rows",
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
    p681_validation = load_json(P681_VALIDATION)
    source_rows = [row for row in load_jsonl(SOURCE_BUNDLE) if row.get("lane") != "summary"]
    rows = load_jsonl(PREFLIGHT)
    report = load_json(REPORT)
    failures: list[dict[str, Any]] = []
    lane_rows = rows[:-1] if rows else []
    summary = rows[-1] if rows else {}

    fail_if(p681_validation.get("success") is not True, failures, "p681_validation_success", p681_validation.get("success"), True)
    fail_if(len(source_rows) != 5, failures, "source_bundle_lane_rows_exact", len(source_rows), 5)
    fail_if(len(lane_rows) != 5, failures, "preflight_lane_rows_exact", len(lane_rows), 5)
    fail_if(summary.get("lane") != "summary", failures, "summary_row_present", summary.get("lane"), "summary")
    fail_if(report.get("audit_rows") != 6, failures, "report_audit_rows", report.get("audit_rows"), 6)
    fail_if(report.get("receive_preflight_rows") != 5, failures, "report_preflight_rows", report.get("receive_preflight_rows"), 5)
    fail_if(report.get("open_receive_preflight_rows") != 5, failures, "report_open_rows", report.get("open_receive_preflight_rows"), 5)
    fail_if(report.get("empty_receive_preflight_rows") != 5, failures, "report_empty_rows", report.get("empty_receive_preflight_rows"), 5)
    fail_if(
        report.get("response_receive_preflight_status") != "open_empty_awaiting_operator_response",
        failures,
        "report_status",
        report.get("response_receive_preflight_status"),
        "open_empty_awaiting_operator_response",
    )
    for field in ZERO_ROW_FIELDS:
        fail_if(report.get(field) != 0, failures, f"report_{field}_zero", report.get(field), 0)
    for field in FALSE_FIELDS:
        fail_if(report.get(field) is not False, failures, f"report_{field}_false", report.get(field), False)

    ids = [row.get("receive_preflight_id") for row in lane_rows]
    fail_if(len(ids) != len(set(ids)), failures, "receive_preflight_ids_unique", ids, "unique")
    source_bundle_ids = {row.get("bundle_id") for row in source_rows}
    fail_if(
        {row.get("source_bundle_id") for row in lane_rows} != source_bundle_ids,
        failures,
        "source_bundle_ids_covered",
        {row.get("source_bundle_id") for row in lane_rows},
        source_bundle_ids,
    )
    orders = [row.get("receive_preflight_order") for row in lane_rows]
    fail_if(orders != sorted(orders), failures, "receive_preflight_order_sorted", orders, "ascending")
    for index, row in enumerate(lane_rows, start=1):
        fail_if(row.get("receive_preflight_order") != index, failures, "row_order", {"row": index, "value": row.get("receive_preflight_order")}, index)
        fail_if(
            row.get("response_receive_preflight_status") != "open_empty_awaiting_operator_response",
            failures,
            "row_status",
            {"row": index, "value": row.get("response_receive_preflight_status")},
            "open_empty_awaiting_operator_response",
        )
        fail_if(row.get("receive_preflight_open") is not True, failures, "row_open", {"row": index, "value": row.get("receive_preflight_open")}, True)
        fail_if(row.get("receive_preflight_empty") is not True, failures, "row_empty", {"row": index, "value": row.get("receive_preflight_empty")}, True)
        fail_if(
            row.get("receive_preflight_executed") is not False,
            failures,
            "row_executed_false",
            {"row": index, "value": row.get("receive_preflight_executed")},
            False,
        )
        for field in (
            "receive_preflight_id",
            "lane",
            "source_bundle_id",
            "formal_target_file",
            "source_work_file",
            "template_or_reference_file",
            "expected_response_fields",
            "response_envelope_required_fields",
            "validator_command",
            "operator_action",
            "completion_condition",
            "blocker",
            "policy",
        ):
            fail_if(row.get(field) in (None, "", []), failures, f"row_{field}_present", {"row": index, "value": row.get(field)}, "present")
        for field in FALSE_FIELDS:
            fail_if(row.get(field) is not False, failures, f"row_{field}_false", {"row": index, "value": row.get(field)}, False)

    fail_if(summary.get("receive_preflight_rows") != 5, failures, "summary_preflight_rows", summary.get("receive_preflight_rows"), 5)
    fail_if(summary.get("open_receive_preflight_rows") != 5, failures, "summary_open_rows", summary.get("open_receive_preflight_rows"), 5)
    fail_if(summary.get("empty_receive_preflight_rows") != 5, failures, "summary_empty_rows", summary.get("empty_receive_preflight_rows"), 5)
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
        "manifest_id": "P682",
        "audit_rows": len(rows),
        "receive_preflight_rows": len(lane_rows),
        "open_receive_preflight_rows": sum(1 for row in lane_rows if row.get("receive_preflight_open") is True),
        "empty_receive_preflight_rows": sum(1 for row in lane_rows if row.get("receive_preflight_empty") is True),
        "receive_preflight_executed_rows": sum(1 for row in lane_rows if row.get("receive_preflight_executed") is True),
        "operator_dispatch_sent_rows": sum(1 for row in lane_rows if row.get("operator_dispatch_sent") is True),
        "operator_acknowledged_rows": sum(1 for row in lane_rows if row.get("operator_acknowledged") is True),
        "external_input_acknowledged_rows": sum(1 for row in lane_rows if row.get("external_input_acknowledged") is True),
        "response_payload_present_rows": sum(1 for row in lane_rows if row.get("response_payload_present") is True),
        "response_received_rows": sum(1 for row in lane_rows if row.get("response_received") is True),
        "response_validated_rows": sum(1 for row in lane_rows if row.get("response_validated") is True),
        "real_input_received_rows": sum(1 for row in lane_rows if row.get("real_input_received") is True),
        "formal_validator_passed_rows": sum(1 for row in lane_rows if row.get("formal_validator_passed") is True),
        "reviewed_decision_written_rows": sum(1 for row in lane_rows if row.get("reviewed_decision_written") is True),
        "formal_intake_written_rows": sum(1 for row in lane_rows if row.get("formal_intake_written") is True),
        "runtime_receipt_written_rows": sum(1 for row in lane_rows if row.get("runtime_receipt_written") is True),
        "training_label_written_rows": sum(1 for row in lane_rows if row.get("training_label_written") is True),
        "completion_ready_rows": sum(1 for row in lane_rows if row.get("completion_ready") is True),
        "p0_unblocked_rows": sum(1 for row in lane_rows if row.get("p0_unblocked") is True),
        "operator_dispatch_sent": False,
        "operator_acknowledged": False,
        "external_input_acknowledged": False,
        "response_payload_present": False,
        "response_received": False,
        "response_validated": False,
        "real_input_received": False,
        "formal_validator_passed": False,
        "reviewed_decision_written": False,
        "formal_intake_written": False,
        "runtime_receipt_written": False,
        "training_label_written": False,
        "completion_ready": False,
        "p0_unblocked": False,
        "training_import_allowed": False,
        "safe_for_training_import": False,
        "safe_for_model_claim": False,
        "customer_delivery_ready": False,
        "release_ready": False,
        "production_execution_allowed": False,
        "policy": "Validation only. P682 confirms empty response-receive preflight slots and cannot receive, approve, release, or authorize production.",
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({
        "success": result["success"],
        "receive_preflight_rows": result["receive_preflight_rows"],
        "open_receive_preflight_rows": result["open_receive_preflight_rows"],
        "response_received_rows": result["response_received_rows"],
        "real_input_received_rows": result["real_input_received_rows"],
        "failures": result["failure_count"],
        "output": str(OUT),
    }, ensure_ascii=False))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
