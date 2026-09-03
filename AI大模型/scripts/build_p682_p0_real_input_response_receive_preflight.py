#!/usr/bin/env python3
"""Build a fail-closed P0 real-input response receive preflight from P681."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
P681_BUNDLE = AI_ROOT / "datasets" / "governance" / "p681_p0_real_input_operator_dispatch_bundle.jsonl"
P681_REPORT = AI_ROOT / "reports" / "p681_p0_real_input_operator_dispatch_bundle_report.json"
P681_VALIDATION = AI_ROOT / "reports" / "p681_p0_real_input_operator_dispatch_bundle_validation_report.json"
OUT_JSONL = AI_ROOT / "datasets" / "governance" / "p682_p0_real_input_response_receive_preflight.jsonl"
OUT_REPORT = AI_ROOT / "reports" / "p682_p0_real_input_response_receive_preflight_report.json"
OUT_MD = AI_ROOT / "reports" / "p682_p0_real_input_response_receive_preflight.md"

FALSE_FLAGS = {
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
}

RESPONSE_ENVELOPE_FIELDS = (
    "operator_identity",
    "response_received_at",
    "source_response_artifact",
    "formal_target_file",
    "expected_response_fields",
    "validator_command",
    "validation_report",
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


def preflight_row(row: dict[str, Any], created_at: str) -> dict[str, Any]:
    lane = row.get("lane")
    return {
        "receive_preflight_id": f"p682::{lane}",
        "receive_preflight_order": row.get("bundle_order"),
        "created_at": created_at,
        "local_only": True,
        "lane": lane,
        "priority": row.get("priority"),
        "source_bundle_id": row.get("bundle_id"),
        "source_bundle_order": row.get("bundle_order"),
        "source_dispatch_bundle_status": row.get("dispatch_bundle_status"),
        "source_audit_id": row.get("source_audit_id"),
        "source_checklist_id": row.get("source_checklist_id"),
        "source_freshness_audit_id": row.get("source_freshness_audit_id"),
        "response_receive_preflight_status": "open_empty_awaiting_operator_response",
        "receive_preflight_open": True,
        "receive_preflight_empty": True,
        "receive_preflight_executed": False,
        "formal_target_file": row.get("formal_target_file"),
        "source_work_file": row.get("source_work_file"),
        "template_or_reference_file": row.get("template_or_reference_file"),
        "expected_response_fields": row.get("required_fields") or [],
        "response_envelope_required_fields": list(RESPONSE_ENVELOPE_FIELDS),
        "validator_command": row.get("validator_command"),
        "operator_action": row.get("operator_action"),
        "completion_condition": row.get("completion_condition"),
        "blocker": "No operator dispatch, acknowledgement, response payload, or real input has been received.",
        "policy": (
            "P682 records empty response-receive preflight slots only. It does not send dispatch, "
            "receive or validate response payloads, write formal targets, create runtime receipts "
            "or training labels, approve model claims, release, delivery, or production execution."
        ),
        **FALSE_FLAGS,
    }


def main() -> int:
    created_at = datetime.now(timezone.utc).isoformat()
    p681_report = load_json(P681_REPORT)
    p681_validation = load_json(P681_VALIDATION)
    source_rows = load_jsonl(P681_BUNDLE)
    lane_rows = sorted(
        (row for row in source_rows if row.get("lane") != "summary"),
        key=lambda row: int(row.get("bundle_order") or 0),
    )
    preflight_rows = [preflight_row(row, created_at) for row in lane_rows]
    summary = {
        "receive_preflight_id": "p682::summary",
        "receive_preflight_order": len(preflight_rows) + 1,
        "created_at": created_at,
        "local_only": True,
        "lane": "summary",
        "source_bundle_rows": p681_report.get("bundle_rows"),
        "source_p681_validation_success": p681_validation.get("success"),
        "receive_preflight_rows": len(preflight_rows),
        "open_receive_preflight_rows": sum(1 for row in preflight_rows if row["receive_preflight_open"] is True),
        "empty_receive_preflight_rows": sum(1 for row in preflight_rows if row["receive_preflight_empty"] is True),
        "receive_preflight_executed_rows": 0,
        "response_receive_preflight_status": (
            "open_empty_awaiting_operator_response"
            if preflight_rows
            else "blocked_missing_source_bundle"
        ),
        "operator_dispatch_sent_rows": 0,
        "operator_acknowledged_rows": 0,
        "external_input_acknowledged_rows": 0,
        "response_payload_present_rows": 0,
        "response_received_rows": 0,
        "response_validated_rows": 0,
        "real_input_received_rows": 0,
        "formal_validator_passed_rows": 0,
        "reviewed_decision_written_rows": 0,
        "formal_intake_written_rows": 0,
        "runtime_receipt_written_rows": 0,
        "training_label_written_rows": 0,
        "completion_ready_rows": 0,
        "p0_unblocked_rows": 0,
        "blocker": "Response receive preflight is open, but no operator response or real input is present.",
        "policy": "P682 is a local response-receive preflight only; it does not receive or approve any P0 input.",
        **FALSE_FLAGS,
    }
    output_rows = preflight_rows + [summary]

    OUT_JSONL.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSONL.write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in output_rows),
        encoding="utf-8",
    )
    report = {
        "created_at": created_at,
        "local_only": True,
        "source_bundle": "datasets/governance/p681_p0_real_input_operator_dispatch_bundle.jsonl",
        "source_report": "reports/p681_p0_real_input_operator_dispatch_bundle_report.json",
        "source_validation_report": "reports/p681_p0_real_input_operator_dispatch_bundle_validation_report.json",
        "source_bundle_rows": p681_report.get("bundle_rows"),
        "source_p681_validation_success": p681_validation.get("success"),
        "receive_preflight_rows": len(preflight_rows),
        "audit_rows": len(output_rows),
        "open_receive_preflight_rows": summary["open_receive_preflight_rows"],
        "empty_receive_preflight_rows": summary["empty_receive_preflight_rows"],
        "receive_preflight_executed_rows": 0,
        "response_receive_preflight_status": summary["response_receive_preflight_status"],
        "operator_dispatch_sent_rows": 0,
        "operator_acknowledged_rows": 0,
        "external_input_acknowledged_rows": 0,
        "response_payload_present_rows": 0,
        "response_received_rows": 0,
        "response_validated_rows": 0,
        "real_input_received_rows": 0,
        "formal_validator_passed_rows": 0,
        "reviewed_decision_written_rows": 0,
        "formal_intake_written_rows": 0,
        "runtime_receipt_written_rows": 0,
        "training_label_written_rows": 0,
        "completion_ready_rows": 0,
        "p0_unblocked_rows": 0,
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
        "preflight_jsonl": str(OUT_JSONL.relative_to(AI_ROOT)),
        "policy": "P682 records local response-receive preflight slots; all gates remain fail-closed.",
    }
    OUT_REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    lines = [
        "# P682 P0 real-input response receive preflight",
        "",
        "Status: response receive preflight is open and empty; no operator response has been received.",
        "",
        f"- receive_preflight_rows: `{len(preflight_rows)}`",
        f"- open_receive_preflight_rows: `{summary['open_receive_preflight_rows']}`",
        "- operator_dispatch_sent_rows: `0`",
        "- operator_acknowledged_rows: `0`",
        "- response_received_rows: `0`",
        "- real_input_received_rows: `0`",
        "- completion_ready_rows: `0`",
        "- release_ready: `false`",
        "",
        "| Order | Lane | Formal target | Expected response fields | Status |",
        "|---:|---|---|---|---|",
    ]
    for row in preflight_rows:
        fields = ", ".join(str(field) for field in row["expected_response_fields"])
        lines.append(
            f"| {row['receive_preflight_order']} | {row['lane']} | `{row['formal_target_file']}` | "
            f"`{fields}` | `{row['response_receive_preflight_status']}` |"
        )
    lines.extend([
        "",
        "This preflight does not send work, receive input, write formal decisions, import labels, assert claims, release, or authorize production.",
    ])
    OUT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps({
        "receive_preflight_rows": len(preflight_rows),
        "open_receive_preflight_rows": summary["open_receive_preflight_rows"],
        "operator_dispatch_sent_rows": 0,
        "operator_acknowledged_rows": 0,
        "response_received_rows": 0,
        "real_input_received_rows": 0,
        "completion_ready_rows": 0,
        "release_ready": False,
        "output": str(OUT_REPORT),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
