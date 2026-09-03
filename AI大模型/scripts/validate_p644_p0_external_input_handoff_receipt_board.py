#!/usr/bin/env python3
"""Validate P644 P0 handoff receipt board remains local-only and fail-closed."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
P643_VALIDATION = AI_ROOT / "reports" / "p643_p0_external_input_dispatch_board_validation_report.json"
SOURCE_BOARD = AI_ROOT / "datasets" / "governance" / "p643_p0_external_input_dispatch_board.jsonl"
BOARD = AI_ROOT / "datasets" / "governance" / "p644_p0_external_input_handoff_receipt_board.jsonl"
REPORT = AI_ROOT / "reports" / "p644_p0_external_input_handoff_receipt_board_report.json"
OUT = AI_ROOT / "reports" / "p644_p0_external_input_handoff_receipt_board_validation_report.json"

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
    "handoff_sent_rows",
    "operator_acknowledged_rows",
    "external_input_acknowledged_rows",
    "real_input_received_rows",
    "reviewed_decision_written_rows",
    "formal_intake_written_rows",
    "runtime_receipt_written_rows",
)

EXPECTED_CHANNELS = {
    "curation_review_channel",
    "feedback_review_channel",
    "governance_review_channel",
    "technical_gate_review_channel",
}


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
    p643_validation = load_json(P643_VALIDATION)
    source_rows = load_jsonl(SOURCE_BOARD)
    report = load_json(REPORT)
    rows = load_jsonl(BOARD)
    failures: list[dict[str, Any]] = []

    def check(condition: bool, name: str, observed: Any, expected: Any) -> None:
        if condition:
            failures.append({"check": name, "observed": observed, "expected": expected})

    check(p643_validation.get("success") is not True, "source_p643_validation_success", p643_validation.get("success"), True)
    check(len(rows) != len(source_rows), "handoff_rows_match_p643", len(rows), len(source_rows))
    check(report.get("handoff_rows") != len(rows), "report_handoff_rows_bound", report.get("handoff_rows"), len(rows))
    check(report.get("prepared_handoff_rows") != len(rows), "all_handoffs_prepared", report.get("prepared_handoff_rows"), len(rows))
    check(report.get("open_blocked_handoff_rows") != len(rows), "all_handoffs_open_blocked", report.get("open_blocked_handoff_rows"), len(rows))
    check(report.get("handoff_channel_count") != len(EXPECTED_CHANNELS), "handoff_channel_count", report.get("handoff_channel_count"), len(EXPECTED_CHANNELS))
    check(set((report.get("channel_counts") or {}).keys()) != EXPECTED_CHANNELS, "expected_channels_present", set((report.get("channel_counts") or {}).keys()), EXPECTED_CHANNELS)
    for field in ZERO_ROW_FIELDS:
        check(report.get(field) != 0, f"{field}_zero", report.get(field), 0)
    check(report.get("p0_unblocked") is not False, "p0_unblocked_false", report.get("p0_unblocked"), False)
    check(report.get("p0_completion_ready") is not False, "p0_completion_ready_false", report.get("p0_completion_ready"), False)
    for field in FALSE_FIELDS:
        check(report.get(field) is not False, f"report_{field}_false", report.get(field), False)

    handoff_ids = [row.get("handoff_id") for row in rows]
    check(len(handoff_ids) != len(set(handoff_ids)), "handoff_ids_unique", handoff_ids, "unique")
    dispatch_ids = {row.get("dispatch_id") for row in source_rows}
    check({row.get("dispatch_id") for row in rows} != dispatch_ids, "dispatch_ids_exactly_covered", {row.get("dispatch_id") for row in rows}, dispatch_ids)
    orders = [row.get("dispatch_order") for row in rows]
    check(orders != sorted(orders), "handoff_order_sorted", orders, "ascending")
    for idx, row in enumerate(rows):
        check(row.get("handoff_status") != "prepared_not_sent_open_blocked", f"row_status_{idx}", row.get("handoff_status"), "prepared_not_sent_open_blocked")
        check(row.get("handoff_prepared") is not True, f"row_handoff_prepared_{idx}", row.get("handoff_prepared"), True)
        check(row.get("source_dispatch_status") != "open_blocked_awaiting_external_input", f"source_dispatch_status_{idx}", row.get("source_dispatch_status"), "open_blocked_awaiting_external_input")
        check(row.get("source_dispatch_ready") is not True, f"source_dispatch_ready_{idx}", row.get("source_dispatch_ready"), True)
        check(row.get("handoff_sent") is not False, f"row_handoff_sent_false_{idx}", row.get("handoff_sent"), False)
        check(row.get("operator_acknowledged") is not False, f"row_operator_ack_false_{idx}", row.get("operator_acknowledged"), False)
        check(row.get("external_input_acknowledged") is not False, f"row_external_ack_false_{idx}", row.get("external_input_acknowledged"), False)
        check(row.get("real_input_received") is not False, f"row_real_input_false_{idx}", row.get("real_input_received"), False)
        check(row.get("reviewed_decision_written") is not False, f"row_decision_false_{idx}", row.get("reviewed_decision_written"), False)
        check(row.get("formal_intake_written") is not False, f"row_intake_false_{idx}", row.get("formal_intake_written"), False)
        check(row.get("runtime_receipt_written") is not False, f"row_runtime_false_{idx}", row.get("runtime_receipt_written"), False)
        for field in FALSE_FIELDS:
            check(row.get(field) is not False, f"row_{field}_{idx}", row.get(field), False)

    result = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "local_only": True,
        "success": not failures,
        "manifest_id": "P644",
        "handoff_rows": len(rows),
        "prepared_handoff_rows": sum(1 for row in rows if row.get("handoff_prepared") is True),
        "open_blocked_handoff_rows": sum(1 for row in rows if row.get("handoff_status") == "prepared_not_sent_open_blocked"),
        "handoff_channel_count": len({row.get("handoff_channel") for row in rows}),
        "handoff_sent_rows": sum(1 for row in rows if row.get("handoff_sent") is True),
        "operator_acknowledged_rows": sum(1 for row in rows if row.get("operator_acknowledged") is True),
        "external_input_acknowledged_rows": sum(1 for row in rows if row.get("external_input_acknowledged") is True),
        "real_input_received_rows": sum(1 for row in rows if row.get("real_input_received") is True),
        "reviewed_decision_written_rows": sum(1 for row in rows if row.get("reviewed_decision_written") is True),
        "formal_intake_written_rows": sum(1 for row in rows if row.get("formal_intake_written") is True),
        "runtime_receipt_written_rows": sum(1 for row in rows if row.get("runtime_receipt_written") is True),
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
        "policy": "P644 validates local handoff preparation only; it does not send or approve any P0 input.",
    }
    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "success": result["success"],
        "handoff_rows": result["handoff_rows"],
        "prepared_handoff_rows": result["prepared_handoff_rows"],
        "handoff_sent_rows": result["handoff_sent_rows"],
        "failures": len(failures),
        "output": str(OUT),
    }, ensure_ascii=False))
    return 0 if result["success"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
