#!/usr/bin/env python3
"""Validate P647 response validation preflight remains empty and fail-closed."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
P646_VALIDATION = AI_ROOT / "reports" / "p646_p0_external_input_response_intake_queue_validation_report.json"
SOURCE_QUEUE = AI_ROOT / "datasets" / "governance" / "p646_p0_external_input_response_intake_queue.jsonl"
PREFLIGHT = AI_ROOT / "datasets" / "governance" / "p647_p0_external_input_response_validation_preflight.jsonl"
REPORT = AI_ROOT / "reports" / "p647_p0_external_input_response_validation_preflight_report.json"
OUT = AI_ROOT / "reports" / "p647_p0_external_input_response_validation_preflight_validation_report.json"

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
    "preflight_executed_rows",
    "queue_dequeued_rows",
    "response_received_rows",
    "response_validated_rows",
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
    p646_validation = load_json(P646_VALIDATION)
    source_rows = load_jsonl(SOURCE_QUEUE)
    report = load_json(REPORT)
    rows = load_jsonl(PREFLIGHT)
    failures: list[dict[str, Any]] = []

    def check(condition: bool, name: str, observed: Any, expected: Any) -> None:
        if condition:
            failures.append({"check": name, "observed": observed, "expected": expected})

    check(p646_validation.get("success") is not True, "source_p646_validation_success", p646_validation.get("success"), True)
    check(len(rows) != len(source_rows), "preflight_rows_match_p646", len(rows), len(source_rows))
    check(report.get("preflight_rows") != len(rows), "report_preflight_rows_bound", report.get("preflight_rows"), len(rows))
    check(report.get("open_preflight_rows") != len(rows), "all_preflight_rows_open", report.get("open_preflight_rows"), len(rows))
    check(report.get("empty_preflight_rows") != len(rows), "all_preflight_rows_empty", report.get("empty_preflight_rows"), len(rows))
    for field in ZERO_ROW_FIELDS:
        check(report.get(field) != 0, f"{field}_zero", report.get(field), 0)
    check(report.get("p0_unblocked") is not False, "p0_unblocked_false", report.get("p0_unblocked"), False)
    check(report.get("p0_completion_ready") is not False, "p0_completion_ready_false", report.get("p0_completion_ready"), False)
    for field in FALSE_FIELDS:
        check(report.get(field) is not False, f"report_{field}_false", report.get(field), False)

    preflight_ids = [row.get("preflight_id") for row in rows]
    check(len(preflight_ids) != len(set(preflight_ids)), "preflight_ids_unique", preflight_ids, "unique")
    queue_ids = {row.get("queue_item_id") for row in source_rows}
    check(
        {row.get("queue_item_id") for row in rows} != queue_ids,
        "queue_item_ids_exactly_covered",
        {row.get("queue_item_id") for row in rows},
        queue_ids,
    )
    orders = [row.get("preflight_order") for row in rows]
    check(orders != sorted(orders), "preflight_order_sorted", orders, "ascending")
    for idx, row in enumerate(rows):
        check(
            row.get("preflight_status") != "open_empty_not_executed",
            f"row_status_{idx}",
            row.get("preflight_status"),
            "open_empty_not_executed",
        )
        check(row.get("preflight_open") is not True, f"row_preflight_open_{idx}", row.get("preflight_open"), True)
        check(row.get("preflight_empty") is not True, f"row_preflight_empty_{idx}", row.get("preflight_empty"), True)
        check(row.get("preflight_executed") is not False, f"row_preflight_executed_false_{idx}", row.get("preflight_executed"), False)
        check(row.get("queue_dequeued") is not False, f"row_queue_dequeued_false_{idx}", row.get("queue_dequeued"), False)
        check(row.get("response_received") is not False, f"row_response_received_false_{idx}", row.get("response_received"), False)
        check(row.get("response_validated") is not False, f"row_response_validated_false_{idx}", row.get("response_validated"), False)
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
        "manifest_id": "P647",
        "preflight_rows": len(rows),
        "open_preflight_rows": sum(1 for row in rows if row.get("preflight_open") is True),
        "empty_preflight_rows": sum(1 for row in rows if row.get("preflight_empty") is True),
        "preflight_executed_rows": sum(1 for row in rows if row.get("preflight_executed") is True),
        "queue_dequeued_rows": sum(1 for row in rows if row.get("queue_dequeued") is True),
        "response_received_rows": sum(1 for row in rows if row.get("response_received") is True),
        "response_validated_rows": sum(1 for row in rows if row.get("response_validated") is True),
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
        "policy": "P647 validates empty response preflight shells only; it does not receive or approve any P0 input.",
    }
    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "success": result["success"],
        "preflight_rows": result["preflight_rows"],
        "open_preflight_rows": result["open_preflight_rows"],
        "preflight_executed_rows": result["preflight_executed_rows"],
        "response_received_rows": result["response_received_rows"],
        "failures": len(failures),
        "output": str(OUT),
    }, ensure_ascii=False))
    return 0 if result["success"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
