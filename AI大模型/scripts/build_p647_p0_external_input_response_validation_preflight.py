#!/usr/bin/env python3
"""Build a fail-closed P0 external-input response validation preflight shell."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
P646_QUEUE = AI_ROOT / "datasets" / "governance" / "p646_p0_external_input_response_intake_queue.jsonl"
P646_REPORT = AI_ROOT / "reports" / "p646_p0_external_input_response_intake_queue_report.json"
P646_VALIDATION = AI_ROOT / "reports" / "p646_p0_external_input_response_intake_queue_validation_report.json"
OUT_JSONL = AI_ROOT / "datasets" / "governance" / "p647_p0_external_input_response_validation_preflight.jsonl"
OUT_REPORT = AI_ROOT / "reports" / "p647_p0_external_input_response_validation_preflight_report.json"
OUT_MD = AI_ROOT / "reports" / "p0_external_input_response_validation_preflight.md"


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    value = json.loads(path.read_text(encoding="utf-8"))
    return value if isinstance(value, dict) else {}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def preflight_row(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "local_only": True,
        "preflight_id": f"p647::{row.get('plan_item_id')}",
        "queue_item_id": row.get("queue_item_id"),
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
        "preflight_order": row.get("queue_order"),
        "preflight_status": "open_empty_not_executed",
        "preflight_open": True,
        "preflight_empty": True,
        "preflight_executed": False,
        "queue_dequeued": False,
        "response_received": False,
        "response_validated": False,
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
            "P647 records response validation preflight slots only. It does not execute validation, "
            "dequeue queue items, receive external input, write reviewed decisions, formal intake, "
            "runtime receipts, or training labels, and does not approve model claims, release, or production."
        ),
    }


def main() -> int:
    p646_report = load_json(P646_REPORT)
    p646_validation = load_json(P646_VALIDATION)
    queue_rows = load_jsonl(P646_QUEUE)
    rows = [preflight_row(row) for row in queue_rows]
    rows.sort(key=lambda row: (row["dispatch_wave"], row["preflight_order"]))
    schemas = sorted({row["response_schema"] for row in rows})

    report = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "local_only": True,
        "manifest_id": "P647",
        "source_queue": "datasets/governance/p646_p0_external_input_response_intake_queue.jsonl",
        "source_report": "reports/p646_p0_external_input_response_intake_queue_report.json",
        "source_validation_report": "reports/p646_p0_external_input_response_intake_queue_validation_report.json",
        "source_queue_rows": p646_report.get("queue_rows"),
        "source_queue_validation_success": p646_validation.get("success"),
        "preflight_rows": len(rows),
        "open_preflight_rows": sum(1 for row in rows if row["preflight_open"] is True),
        "empty_preflight_rows": sum(1 for row in rows if row["preflight_empty"] is True),
        "preflight_executed_rows": sum(1 for row in rows if row["preflight_executed"] is True),
        "response_schema_count": len(schemas),
        "response_schemas": schemas,
        "queue_dequeued_rows": sum(1 for row in rows if row["queue_dequeued"] is True),
        "response_received_rows": sum(1 for row in rows if row["response_received"] is True),
        "response_validated_rows": sum(1 for row in rows if row["response_validated"] is True),
        "real_input_received_rows": sum(1 for row in rows if row["real_input_received"] is True),
        "reviewed_decision_written_rows": sum(1 for row in rows if row["reviewed_decision_written"] is True),
        "formal_intake_written_rows": sum(1 for row in rows if row["formal_intake_written"] is True),
        "runtime_receipt_written_rows": sum(1 for row in rows if row["runtime_receipt_written"] is True),
        "training_label_written_rows": sum(1 for row in rows if row["training_label_written"] is True),
        "preflight_jsonl": "datasets/governance/p647_p0_external_input_response_validation_preflight.jsonl",
        "preflight_md": "reports/p0_external_input_response_validation_preflight.md",
        "p0_unblocked": False,
        "p0_completion_ready": False,
        "training_import_allowed": False,
        "safe_for_training_import": False,
        "safe_for_model_claim": False,
        "customer_delivery_ready": False,
        "release_ready": False,
        "production_execution_allowed": False,
        "completion_ready": False,
        "policy": "P647 records response-validation preflight shells only; all P0 gates remain fail-closed.",
    }

    OUT_JSONL.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSONL.write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )
    OUT_REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    lines = [
        "# P0 External Input Response Validation Preflight",
        "",
        "Status: open, empty, and not executed.",
        "",
        "| Preflight | Workstream | Schema | Status |",
        "| --- | --- | --- | --- |",
    ]
    for row in rows:
        lines.append(
            f"| {row['preflight_id']} | {row['workstream']} | {row['response_schema']} | {row['preflight_status']} |"
        )
    lines.extend([
        "",
        "This preflight shell does not execute response validation, receive external input, write reviewed decisions, formal intake, runtime receipts, training labels, model claims, release approval, or production authorization.",
    ])
    OUT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps({
        "manifest_id": "P647",
        "preflight_rows": len(rows),
        "open_preflight_rows": report["open_preflight_rows"],
        "empty_preflight_rows": report["empty_preflight_rows"],
        "preflight_executed_rows": report["preflight_executed_rows"],
        "response_received_rows": 0,
        "output": str(OUT_REPORT),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
