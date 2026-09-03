#!/usr/bin/env python3
"""Build a fail-closed P0 external-input response slot registry from P644 handoffs."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
P644_BOARD = AI_ROOT / "datasets" / "governance" / "p644_p0_external_input_handoff_receipt_board.jsonl"
P644_REPORT = AI_ROOT / "reports" / "p644_p0_external_input_handoff_receipt_board_report.json"
P644_VALIDATION = AI_ROOT / "reports" / "p644_p0_external_input_handoff_receipt_board_validation_report.json"
OUT_JSONL = AI_ROOT / "datasets" / "governance" / "p645_p0_external_input_response_slot_registry.jsonl"
OUT_REPORT = AI_ROOT / "reports" / "p645_p0_external_input_response_slot_registry_report.json"
OUT_MD = AI_ROOT / "reports" / "p0_external_input_response_slot_registry.md"

FALSE_FIELDS = (
    "training_import_allowed",
    "safe_for_training_import",
    "safe_for_model_claim",
    "customer_delivery_ready",
    "release_ready",
    "production_execution_allowed",
    "completion_ready",
)

RESPONSE_SCHEMA_BY_CATEGORY = {
    "human_review": "reviewed_decision_response",
    "wet_lab_feedback": "feedback_source_or_plate_qc_response",
    "legal_license": "license_or_runtime_scope_response",
    "governance_decision": "governance_decision_response",
    "runtime_receipt": "runtime_receipt_response",
    "benchmark_review": "benchmark_scorecard_response",
    "training_readiness": "training_readiness_response",
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


def response_row(row: dict[str, Any]) -> dict[str, Any]:
    category = str(row.get("packet_category") or "")
    return {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "local_only": True,
        "response_slot_id": f"p645::{row.get('plan_item_id')}",
        "handoff_id": row.get("handoff_id"),
        "dispatch_id": row.get("dispatch_id"),
        "packet_id": row.get("packet_id"),
        "plan_item_id": row.get("plan_item_id"),
        "priority": row.get("priority"),
        "workstream": row.get("workstream"),
        "packet_category": category,
        "required_input_type": row.get("required_input_type"),
        "handoff_channel": row.get("handoff_channel"),
        "dispatch_wave": row.get("dispatch_wave"),
        "dispatch_wave_name": row.get("dispatch_wave_name"),
        "dispatch_order": row.get("dispatch_order"),
        "response_schema": RESPONSE_SCHEMA_BY_CATEGORY.get(category, "generic_external_input_response"),
        "response_slot_status": "open_empty_awaiting_real_input",
        "source_handoff_status": row.get("handoff_status"),
        "source_handoff_prepared": row.get("handoff_prepared"),
        "response_slot_open": True,
        "response_slot_empty": True,
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
            "P645 creates empty response slots only. It does not receive, validate, or accept external input; "
            "does not write reviewed decisions, formal intake, runtime receipts, or training labels; "
            "and does not approve model claims, release, or production execution."
        ),
    }


def main() -> int:
    p644_report = load_json(P644_REPORT)
    p644_validation = load_json(P644_VALIDATION)
    handoff_rows = load_jsonl(P644_BOARD)
    rows = [response_row(row) for row in handoff_rows]
    rows.sort(key=lambda row: (row["dispatch_wave"], row["dispatch_order"]))
    schema_counts: dict[str, int] = {}
    for row in rows:
        schema = str(row["response_schema"])
        schema_counts[schema] = schema_counts.get(schema, 0) + 1

    report = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "local_only": True,
        "manifest_id": "P645",
        "source_board": "datasets/governance/p644_p0_external_input_handoff_receipt_board.jsonl",
        "source_report": "reports/p644_p0_external_input_handoff_receipt_board_report.json",
        "source_validation_report": "reports/p644_p0_external_input_handoff_receipt_board_validation_report.json",
        "source_handoff_rows": p644_report.get("handoff_rows"),
        "source_handoff_validation_success": p644_validation.get("success"),
        "response_slot_rows": len(rows),
        "open_response_slot_rows": sum(1 for row in rows if row["response_slot_open"] is True),
        "empty_response_slot_rows": sum(1 for row in rows if row["response_slot_empty"] is True),
        "response_schema_count": len({row["response_schema"] for row in rows}),
        "schema_counts": schema_counts,
        "response_received_rows": sum(1 for row in rows if row["response_received"] is True),
        "response_validated_rows": sum(1 for row in rows if row["response_validated"] is True),
        "operator_acknowledged_rows": sum(1 for row in rows if row["operator_acknowledged"] is True),
        "external_input_acknowledged_rows": sum(1 for row in rows if row["external_input_acknowledged"] is True),
        "real_input_received_rows": sum(1 for row in rows if row["real_input_received"] is True),
        "reviewed_decision_written_rows": sum(1 for row in rows if row["reviewed_decision_written"] is True),
        "formal_intake_written_rows": sum(1 for row in rows if row["formal_intake_written"] is True),
        "runtime_receipt_written_rows": sum(1 for row in rows if row["runtime_receipt_written"] is True),
        "training_label_written_rows": sum(1 for row in rows if row["training_label_written"] is True),
        "response_slot_jsonl": "datasets/governance/p645_p0_external_input_response_slot_registry.jsonl",
        "response_slot_registry_md": "reports/p0_external_input_response_slot_registry.md",
        "p0_unblocked": False,
        "p0_completion_ready": False,
        "training_import_allowed": False,
        "safe_for_training_import": False,
        "safe_for_model_claim": False,
        "customer_delivery_ready": False,
        "release_ready": False,
        "production_execution_allowed": False,
        "completion_ready": False,
        "policy": "P645 records empty response slots only; all P0 gates remain fail-closed.",
    }

    OUT_JSONL.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSONL.write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )
    OUT_REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    lines = [
        "# P0 External Input Response Slot Registry",
        "",
        "Status: response slots are open and empty; no response has been received or validated.",
        "",
        "| Slot | Workstream | Response schema | Status |",
        "| --- | --- | --- | --- |",
    ]
    for row in rows:
        lines.append(f"| {row['response_slot_id']} | {row['workstream']} | {row['response_schema']} | {row['response_slot_status']} |")
    lines.extend([
        "",
        "This registry does not create external input, reviewed decisions, formal intake, runtime receipts, training labels, model claims, release approval, or production authorization.",
    ])
    OUT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps({
        "manifest_id": "P645",
        "response_slot_rows": len(rows),
        "open_response_slot_rows": report["open_response_slot_rows"],
        "empty_response_slot_rows": report["empty_response_slot_rows"],
        "response_received_rows": 0,
        "output": str(OUT_REPORT),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
