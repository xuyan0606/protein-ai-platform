#!/usr/bin/env python3
"""Validate the P683 P0 real-input response schema contract."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
P682_VALIDATION = AI_ROOT / "reports" / "p682_p0_real_input_response_receive_preflight_validation_report.json"
SOURCE_PREFLIGHT = AI_ROOT / "datasets" / "governance" / "p682_p0_real_input_response_receive_preflight.jsonl"
CONTRACT = AI_ROOT / "datasets" / "governance" / "p683_p0_real_input_response_schema_contract.jsonl"
REPORT = AI_ROOT / "reports" / "p683_p0_real_input_response_schema_contract_report.json"
OUT = AI_ROOT / "reports" / "p683_p0_real_input_response_schema_contract_validation_report.json"

FALSE_FIELDS = (
    "operator_dispatch_sent",
    "operator_acknowledged",
    "external_input_acknowledged",
    "receive_preflight_executed",
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
    p682_validation = load_json(P682_VALIDATION)
    source_rows = [row for row in load_jsonl(SOURCE_PREFLIGHT) if row.get("lane") != "summary"]
    rows = load_jsonl(CONTRACT)
    report = load_json(REPORT)
    failures: list[dict[str, Any]] = []
    lane_rows = rows[:-1] if rows else []
    summary = rows[-1] if rows else {}

    fail_if(p682_validation.get("success") is not True, failures, "p682_validation_success", p682_validation.get("success"), True)
    fail_if(len(source_rows) != 5, failures, "source_preflight_lane_rows_exact", len(source_rows), 5)
    fail_if(len(lane_rows) != 5, failures, "contract_lane_rows_exact", len(lane_rows), 5)
    fail_if(summary.get("lane") != "summary", failures, "summary_row_present", summary.get("lane"), "summary")
    fail_if(report.get("audit_rows") != 6, failures, "report_audit_rows", report.get("audit_rows"), 6)
    fail_if(report.get("schema_contract_rows") != 5, failures, "report_contract_rows", report.get("schema_contract_rows"), 5)
    fail_if(report.get("open_schema_contract_rows") != 5, failures, "report_open_rows", report.get("open_schema_contract_rows"), 5)
    fail_if(report.get("empty_schema_contract_rows") != 5, failures, "report_empty_rows", report.get("empty_schema_contract_rows"), 5)
    fail_if(report.get("blocked_schema_contract_rows") != 5, failures, "report_blocked_rows", report.get("blocked_schema_contract_rows"), 5)
    fail_if(
        report.get("schema_contract_status") != "open_empty_contract_bound_blocked",
        failures,
        "report_status",
        report.get("schema_contract_status"),
        "open_empty_contract_bound_blocked",
    )
    for field in ZERO_ROW_FIELDS:
        fail_if(report.get(field) != 0, failures, f"report_{field}_zero", report.get(field), 0)
    for field in FALSE_FIELDS:
        fail_if(report.get(field) is not False, failures, f"report_{field}_false", report.get(field), False)

    contract_ids = [row.get("schema_contract_id") for row in lane_rows]
    fail_if(len(contract_ids) != len(set(contract_ids)), failures, "schema_contract_ids_unique", contract_ids, "unique")
    source_ids = {row.get("receive_preflight_id") for row in source_rows}
    fail_if(
        {row.get("source_receive_preflight_id") for row in lane_rows} != source_ids,
        failures,
        "source_receive_preflight_ids_covered",
        {row.get("source_receive_preflight_id") for row in lane_rows},
        source_ids,
    )
    orders = [row.get("schema_contract_order") for row in lane_rows]
    fail_if(orders != sorted(orders), failures, "schema_contract_order_sorted", orders, "ascending")
    for index, row in enumerate(lane_rows, start=1):
        fail_if(row.get("schema_contract_order") != index, failures, "row_order", {"row": index, "value": row.get("schema_contract_order")}, index)
        fail_if(
            row.get("schema_contract_status") != "open_empty_contract_bound_blocked",
            failures,
            "row_status",
            {"row": index, "value": row.get("schema_contract_status")},
            "open_empty_contract_bound_blocked",
        )
        fail_if(row.get("schema_contract_open") is not True, failures, "row_open", {"row": index, "value": row.get("schema_contract_open")}, True)
        fail_if(row.get("schema_contract_empty") is not True, failures, "row_empty", {"row": index, "value": row.get("schema_contract_empty")}, True)
        fail_if(row.get("schema_contract_blocked") is not True, failures, "row_blocked", {"row": index, "value": row.get("schema_contract_blocked")}, True)
        for field in (
            "schema_contract_id",
            "lane",
            "source_receive_preflight_id",
            "source_bundle_id",
            "formal_target_file",
            "expected_response_fields",
            "response_envelope_required_fields",
            "validator_command",
            "operator_action",
            "completion_condition",
            "blocker",
            "policy",
        ):
            fail_if(row.get(field) in (None, "", []), failures, f"row_{field}_present", {"row": index, "value": row.get(field)}, "present")
        fail_if(
            row.get("expected_response_field_count") != len(row.get("expected_response_fields") or []),
            failures,
            "row_expected_field_count",
            {"row": index, "value": row.get("expected_response_field_count")},
            len(row.get("expected_response_fields") or []),
        )
        fail_if(
            row.get("response_envelope_field_count") != len(row.get("response_envelope_required_fields") or []),
            failures,
            "row_envelope_field_count",
            {"row": index, "value": row.get("response_envelope_field_count")},
            len(row.get("response_envelope_required_fields") or []),
        )
        for field in FALSE_FIELDS:
            fail_if(row.get(field) is not False, failures, f"row_{field}_false", {"row": index, "value": row.get(field)}, False)

    fail_if(summary.get("schema_contract_rows") != 5, failures, "summary_contract_rows", summary.get("schema_contract_rows"), 5)
    fail_if(summary.get("open_schema_contract_rows") != 5, failures, "summary_open_rows", summary.get("open_schema_contract_rows"), 5)
    fail_if(summary.get("empty_schema_contract_rows") != 5, failures, "summary_empty_rows", summary.get("empty_schema_contract_rows"), 5)
    fail_if(summary.get("blocked_schema_contract_rows") != 5, failures, "summary_blocked_rows", summary.get("blocked_schema_contract_rows"), 5)
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
        "manifest_id": "P683",
        "audit_rows": len(rows),
        "schema_contract_rows": len(lane_rows),
        "open_schema_contract_rows": sum(1 for row in lane_rows if row.get("schema_contract_open") is True),
        "empty_schema_contract_rows": sum(1 for row in lane_rows if row.get("schema_contract_empty") is True),
        "blocked_schema_contract_rows": sum(1 for row in lane_rows if row.get("schema_contract_blocked") is True),
        "policy": "Validation only. P683 confirms schema contracts are bound but empty and fail-closed.",
    }
    for field in FALSE_FIELDS:
        result[f"{field}_rows"] = sum(1 for row in lane_rows if row.get(field) is True)
        result[field] = False
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({
        "success": result["success"],
        "schema_contract_rows": result["schema_contract_rows"],
        "open_schema_contract_rows": result["open_schema_contract_rows"],
        "response_payload_present_rows": result["response_payload_present_rows"],
        "response_received_rows": result["response_received_rows"],
        "real_input_received_rows": result["real_input_received_rows"],
        "failures": result["failure_count"],
        "output": str(OUT),
    }, ensure_ascii=False))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
