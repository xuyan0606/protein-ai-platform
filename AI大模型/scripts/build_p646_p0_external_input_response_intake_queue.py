#!/usr/bin/env python3
"""Build a fail-closed P0 external-input response intake queue from P645 slots."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
P645_REGISTRY = AI_ROOT / "datasets" / "governance" / "p645_p0_external_input_response_slot_registry.jsonl"
P645_REPORT = AI_ROOT / "reports" / "p645_p0_external_input_response_slot_registry_report.json"
P645_VALIDATION = AI_ROOT / "reports" / "p645_p0_external_input_response_slot_registry_validation_report.json"
OUT_JSONL = AI_ROOT / "datasets" / "governance" / "p646_p0_external_input_response_intake_queue.jsonl"
OUT_REPORT = AI_ROOT / "reports" / "p646_p0_external_input_response_intake_queue_report.json"
OUT_MD = AI_ROOT / "reports" / "p0_external_input_response_intake_queue.md"

FALSE_FIELDS = (
    "training_import_allowed",
    "safe_for_training_import",
    "safe_for_model_claim",
    "customer_delivery_ready",
    "release_ready",
    "production_execution_allowed",
    "completion_ready",
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


def queue_row(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "local_only": True,
        "queue_item_id": f"p646::{row.get('plan_item_id')}",
        "response_slot_id": row.get("response_slot_id"),
        "handoff_id": row.get("handoff_id"),
        "dispatch_id": row.get("dispatch_id"),
        "packet_id": row.get("packet_id"),
        "plan_item_id": row.get("plan_item_id"),
        "priority": row.get("priority"),
        "workstream": row.get("workstream"),
        "packet_category": row.get("packet_category"),
        "required_input_type": row.get("required_input_type"),
        "response_schema": row.get("response_schema"),
        "handoff_channel": row.get("handoff_channel"),
        "dispatch_wave": row.get("dispatch_wave"),
        "dispatch_wave_name": row.get("dispatch_wave_name"),
        "dispatch_order": row.get("dispatch_order"),
        "queue_order": row.get("dispatch_order"),
        "queue_status": "open_empty_awaiting_response",
        "queue_open": True,
        "queue_empty": True,
        "queue_enqueued": True,
        "queue_dequeued": False,
        "response_received": False,
        "response_validated": False,
        "operator_acknowledged": False,
        "external_input_acknowledged": False,
        "real_input_received": False,
        "reviewed_decision_written": False,
        "formal_intake_written": False,
        "runtime_receipt_written": False,
        "training_label_written": False,
        "model_claim_allowed": False,
        "training_import_allowed": False,
        "safe_for_training_import": False,
        "safe_for_model_claim": False,
        "customer_delivery_ready": False,
        "release_ready": False,
        "production_execution_allowed": False,
        "completion_ready": False,
        "operator_next_action": row.get("operator_next_action"),
        "acceptance_condition": row.get("acceptance_condition"),
        "source_refs": row.get("source_refs") or [],
        "policy": (
            "P646 records empty response intake queue items only. It does not receive, validate, dequeue, "
            "or accept external input; does not write reviewed decisions, formal intake, runtime receipts, "
            "or training labels; and does not approve model claims, release, or production execution."
        ),
    }


def main() -> int:
    p645_report = load_json(P645_REPORT)
    p645_validation = load_json(P645_VALIDATION)
    slots = load_jsonl(P645_REGISTRY)
    rows = [queue_row(row) for row in slots]
    rows.sort(key=lambda row: (row["dispatch_wave"], row["queue_order"]))
    categories = sorted({row["packet_category"] for row in rows})

    report = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "local_only": True,
        "manifest_id": "P646",
        "source_registry": "datasets/governance/p645_p0_external_input_response_slot_registry.jsonl",
        "source_report": "reports/p645_p0_external_input_response_slot_registry_report.json",
        "source_validation_report": "reports/p645_p0_external_input_response_slot_registry_validation_report.json",
        "source_response_slot_rows": p645_report.get("response_slot_rows"),
        "source_response_slot_validation_success": p645_validation.get("success"),
        "queue_rows": len(rows),
        "open_queue_rows": sum(1 for row in rows if row["queue_open"] is True),
        "empty_queue_rows": sum(1 for row in rows if row["queue_empty"] is True),
        "enqueued_rows": sum(1 for row in rows if row["queue_enqueued"] is True),
        "dequeued_rows": sum(1 for row in rows if row["queue_dequeued"] is True),
        "queue_category_count": len(categories),
        "queue_categories": categories,
        "response_received_rows": sum(1 for row in rows if row["response_received"] is True),
        "response_validated_rows": sum(1 for row in rows if row["response_validated"] is True),
        "operator_acknowledged_rows": sum(1 for row in rows if row["operator_acknowledged"] is True),
        "external_input_acknowledged_rows": sum(1 for row in rows if row["external_input_acknowledged"] is True),
        "real_input_received_rows": sum(1 for row in rows if row["real_input_received"] is True),
        "reviewed_decision_written_rows": sum(1 for row in rows if row["reviewed_decision_written"] is True),
        "formal_intake_written_rows": sum(1 for row in rows if row["formal_intake_written"] is True),
        "runtime_receipt_written_rows": sum(1 for row in rows if row["runtime_receipt_written"] is True),
        "training_label_written_rows": sum(1 for row in rows if row["training_label_written"] is True),
        "queue_jsonl": "datasets/governance/p646_p0_external_input_response_intake_queue.jsonl",
        "queue_md": "reports/p0_external_input_response_intake_queue.md",
        "p0_unblocked": False,
        "p0_completion_ready": False,
        "training_import_allowed": False,
        "safe_for_training_import": False,
        "safe_for_model_claim": False,
        "customer_delivery_ready": False,
        "release_ready": False,
        "production_execution_allowed": False,
        "completion_ready": False,
        "policy": "P646 records an empty response intake queue only; all P0 gates remain fail-closed.",
    }

    OUT_JSONL.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSONL.write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )
    OUT_REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    lines = [
        "# P0 External Input Response Intake Queue",
        "",
        "Status: open, empty, and waiting for real response only.",
        "",
        "| Queue | Workstream | Schema | Status |",
        "| --- | --- | --- | --- |",
    ]
    for row in rows:
        lines.append(f"| {row['queue_item_id']} | {row['workstream']} | {row['response_schema']} | {row['queue_status']} |")
    lines.extend([
        "",
        "This queue does not create external input, reviewed decisions, formal intake, runtime receipts, training labels, model claims, release approval, or production authorization.",
    ])
    OUT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps({
        "manifest_id": "P646",
        "queue_rows": len(rows),
        "open_queue_rows": report["open_queue_rows"],
        "empty_queue_rows": report["empty_queue_rows"],
        "response_received_rows": 0,
        "output": str(OUT_REPORT),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
