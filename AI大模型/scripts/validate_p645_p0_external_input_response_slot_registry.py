#!/usr/bin/env python3
"""Validate P645 response slot registry remains empty and fail-closed."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
P644_VALIDATION = AI_ROOT / "reports" / "p644_p0_external_input_handoff_receipt_board_validation_report.json"
SOURCE_BOARD = AI_ROOT / "datasets" / "governance" / "p644_p0_external_input_handoff_receipt_board.jsonl"
REGISTRY = AI_ROOT / "datasets" / "governance" / "p645_p0_external_input_response_slot_registry.jsonl"
REPORT = AI_ROOT / "reports" / "p645_p0_external_input_response_slot_registry_report.json"
OUT = AI_ROOT / "reports" / "p645_p0_external_input_response_slot_registry_validation_report.json"

FALSE_FIELDS = (
    "training_import_allowed",
    "safe_for_training_import",
    "safe_for_model_claim",
    "customer_delivery_ready",
    "release_ready",
    "production_execution_allowed",
    "completion_ready",
)

ZERO_ROW_FIELDS = (
    "response_received_rows",
    "response_validated_rows",
    "operator_acknowledged_rows",
    "external_input_acknowledged_rows",
    "real_input_received_rows",
    "reviewed_decision_written_rows",
    "formal_intake_written_rows",
    "runtime_receipt_written_rows",
    "training_label_written_rows",
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


def main() -> int:
    p644_validation = load_json(P644_VALIDATION)
    source_rows = load_jsonl(SOURCE_BOARD)
    report = load_json(REPORT)
    rows = load_jsonl(REGISTRY)
    failures: list[dict[str, Any]] = []

    def check(condition: bool, name: str, observed: Any, expected: Any) -> None:
        if condition:
            failures.append({"check": name, "observed": observed, "expected": expected})

    check(p644_validation.get("success") is not True, "source_p644_validation_success", p644_validation.get("success"), True)
    check(len(rows) != len(source_rows), "response_slot_rows_match_p644", len(rows), len(source_rows))
    check(report.get("response_slot_rows") != len(rows), "report_response_slot_rows_bound", report.get("response_slot_rows"), len(rows))
    check(report.get("open_response_slot_rows") != len(rows), "all_response_slots_open", report.get("open_response_slot_rows"), len(rows))
    check(report.get("empty_response_slot_rows") != len(rows), "all_response_slots_empty", report.get("empty_response_slot_rows"), len(rows))
    check(int(report.get("response_schema_count") or 0) < 4, "response_schema_count_min", report.get("response_schema_count"), ">=4")
    for field in ZERO_ROW_FIELDS:
        check(report.get(field) != 0, f"{field}_zero", report.get(field), 0)
    check(report.get("p0_unblocked") is not False, "p0_unblocked_false", report.get("p0_unblocked"), False)
    check(report.get("p0_completion_ready") is not False, "p0_completion_ready_false", report.get("p0_completion_ready"), False)
    for field in FALSE_FIELDS:
        check(report.get(field) is not False, f"report_{field}_false", report.get(field), False)

    slot_ids = [row.get("response_slot_id") for row in rows]
    check(len(slot_ids) != len(set(slot_ids)), "response_slot_ids_unique", slot_ids, "unique")
    handoff_ids = {row.get("handoff_id") for row in source_rows}
    check({row.get("handoff_id") for row in rows} != handoff_ids, "handoff_ids_exactly_covered", {row.get("handoff_id") for row in rows}, handoff_ids)
    orders = [row.get("dispatch_order") for row in rows]
    check(orders != sorted(orders), "response_slot_order_sorted", orders, "ascending")
    for idx, row in enumerate(rows):
        check(row.get("response_slot_status") != "open_empty_awaiting_real_input", f"row_status_{idx}", row.get("response_slot_status"), "open_empty_awaiting_real_input")
        check(row.get("response_slot_open") is not True, f"row_slot_open_{idx}", row.get("response_slot_open"), True)
        check(row.get("response_slot_empty") is not True, f"row_slot_empty_{idx}", row.get("response_slot_empty"), True)
        check(row.get("source_handoff_status") != "prepared_not_sent_open_blocked", f"source_handoff_status_{idx}", row.get("source_handoff_status"), "prepared_not_sent_open_blocked")
        check(row.get("source_handoff_prepared") is not True, f"source_handoff_prepared_{idx}", row.get("source_handoff_prepared"), True)
        check(row.get("response_received") is not False, f"row_response_received_false_{idx}", row.get("response_received"), False)
        check(row.get("response_validated") is not False, f"row_response_validated_false_{idx}", row.get("response_validated"), False)
        check(row.get("operator_acknowledged") is not False, f"row_operator_ack_false_{idx}", row.get("operator_acknowledged"), False)
        check(row.get("external_input_acknowledged") is not False, f"row_external_ack_false_{idx}", row.get("external_input_acknowledged"), False)
        check(row.get("real_input_received") is not False, f"row_real_input_false_{idx}", row.get("real_input_received"), False)
        check(row.get("reviewed_decision_written") is not False, f"row_decision_false_{idx}", row.get("reviewed_decision_written"), False)
        check(row.get("formal_intake_written") is not False, f"row_intake_false_{idx}", row.get("formal_intake_written"), False)
        check(row.get("runtime_receipt_written") is not False, f"row_runtime_false_{idx}", row.get("runtime_receipt_written"), False)
        check(row.get("training_label_written") is not False, f"row_training_label_false_{idx}", row.get("training_label_written"), False)
        for field in FALSE_FIELDS:
            check(row.get(field) is not False, f"row_{field}_{idx}", row.get(field), False)

    result = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "local_only": True,
        "success": not failures,
        "manifest_id": "P645",
        "response_slot_rows": len(rows),
        "open_response_slot_rows": sum(1 for row in rows if row.get("response_slot_open") is True),
        "empty_response_slot_rows": sum(1 for row in rows if row.get("response_slot_empty") is True),
        "response_schema_count": len({row.get("response_schema") for row in rows}),
        "response_received_rows": sum(1 for row in rows if row.get("response_received") is True),
        "response_validated_rows": sum(1 for row in rows if row.get("response_validated") is True),
        "operator_acknowledged_rows": sum(1 for row in rows if row.get("operator_acknowledged") is True),
        "external_input_acknowledged_rows": sum(1 for row in rows if row.get("external_input_acknowledged") is True),
        "real_input_received_rows": sum(1 for row in rows if row.get("real_input_received") is True),
        "reviewed_decision_written_rows": sum(1 for row in rows if row.get("reviewed_decision_written") is True),
        "formal_intake_written_rows": sum(1 for row in rows if row.get("formal_intake_written") is True),
        "runtime_receipt_written_rows": sum(1 for row in rows if row.get("runtime_receipt_written") is True),
        "training_label_written_rows": sum(1 for row in rows if row.get("training_label_written") is True),
        "p0_unblocked": False,
        "p0_completion_ready": False,
        "failures": failures,
        "training_import_allowed": False,
        "safe_for_training_import": False,
        "safe_for_model_claim": False,
        "customer_delivery_ready": False,
        "release_ready": False,
        "production_execution_allowed": False,
        "completion_ready": False,
        "policy": "P645 validates empty response slots only; it does not receive or approve any P0 input.",
    }
    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "success": result["success"],
        "response_slot_rows": result["response_slot_rows"],
        "open_response_slot_rows": result["open_response_slot_rows"],
        "response_received_rows": result["response_received_rows"],
        "failures": len(failures),
        "output": str(OUT),
    }, ensure_ascii=False))
    return 0 if result["success"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
