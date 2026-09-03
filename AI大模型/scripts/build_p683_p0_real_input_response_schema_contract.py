#!/usr/bin/env python3
"""Build a fail-closed P0 real-input response schema contract from P682."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
P682_PREFLIGHT = AI_ROOT / "datasets" / "governance" / "p682_p0_real_input_response_receive_preflight.jsonl"
P682_REPORT = AI_ROOT / "reports" / "p682_p0_real_input_response_receive_preflight_report.json"
P682_VALIDATION = AI_ROOT / "reports" / "p682_p0_real_input_response_receive_preflight_validation_report.json"
OUT_JSONL = AI_ROOT / "datasets" / "governance" / "p683_p0_real_input_response_schema_contract.jsonl"
OUT_REPORT = AI_ROOT / "reports" / "p683_p0_real_input_response_schema_contract_report.json"
OUT_MD = AI_ROOT / "reports" / "p683_p0_real_input_response_schema_contract.md"

FALSE_FLAGS = {
    "operator_dispatch_sent": False,
    "operator_acknowledged": False,
    "external_input_acknowledged": False,
    "receive_preflight_executed": False,
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


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    value = json.loads(path.read_text(encoding="utf-8"))
    return value if isinstance(value, dict) else {}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def contract_row(row: dict[str, Any], created_at: str) -> dict[str, Any]:
    expected_fields = row.get("expected_response_fields") or []
    envelope_fields = row.get("response_envelope_required_fields") or []
    return {
        "schema_contract_id": f"p683::{row.get('lane')}",
        "schema_contract_order": row.get("receive_preflight_order"),
        "created_at": created_at,
        "local_only": True,
        "lane": row.get("lane"),
        "priority": row.get("priority"),
        "source_receive_preflight_id": row.get("receive_preflight_id"),
        "source_bundle_id": row.get("source_bundle_id"),
        "source_checklist_id": row.get("source_checklist_id"),
        "schema_contract_status": "open_empty_contract_bound_blocked",
        "schema_contract_open": True,
        "schema_contract_empty": True,
        "schema_contract_blocked": True,
        "formal_target_file": row.get("formal_target_file"),
        "source_work_file": row.get("source_work_file"),
        "template_or_reference_file": row.get("template_or_reference_file"),
        "expected_response_fields": expected_fields,
        "expected_response_field_count": len(expected_fields),
        "response_envelope_required_fields": envelope_fields,
        "response_envelope_field_count": len(envelope_fields),
        "validator_command": row.get("validator_command"),
        "operator_action": row.get("operator_action"),
        "completion_condition": row.get("completion_condition"),
        "blocker": "Schema contract is bound, but no response payload has been received or validated.",
        "policy": (
            "P683 binds response schema contracts only. It does not receive response payloads, "
            "execute validators, write formal targets, create runtime receipts or training labels, "
            "approve model claims, release, delivery, or production execution."
        ),
        **FALSE_FLAGS,
    }


def main() -> int:
    created_at = datetime.now(timezone.utc).isoformat()
    p682_report = load_json(P682_REPORT)
    p682_validation = load_json(P682_VALIDATION)
    source_rows = load_jsonl(P682_PREFLIGHT)
    lane_rows = sorted(
        (row for row in source_rows if row.get("lane") != "summary"),
        key=lambda row: int(row.get("receive_preflight_order") or 0),
    )
    contract_rows = [contract_row(row, created_at) for row in lane_rows]
    summary = {
        "schema_contract_id": "p683::summary",
        "schema_contract_order": len(contract_rows) + 1,
        "created_at": created_at,
        "local_only": True,
        "lane": "summary",
        "source_receive_preflight_rows": p682_report.get("receive_preflight_rows"),
        "source_p682_validation_success": p682_validation.get("success"),
        "schema_contract_rows": len(contract_rows),
        "open_schema_contract_rows": sum(1 for row in contract_rows if row["schema_contract_open"] is True),
        "empty_schema_contract_rows": sum(1 for row in contract_rows if row["schema_contract_empty"] is True),
        "blocked_schema_contract_rows": sum(1 for row in contract_rows if row["schema_contract_blocked"] is True),
        "schema_contract_status": "open_empty_contract_bound_blocked" if contract_rows else "blocked_missing_source_preflight",
        "operator_dispatch_sent_rows": 0,
        "operator_acknowledged_rows": 0,
        "external_input_acknowledged_rows": 0,
        "receive_preflight_executed_rows": 0,
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
        "training_import_allowed_rows": 0,
        "safe_for_training_import_rows": 0,
        "safe_for_model_claim_rows": 0,
        "customer_delivery_ready_rows": 0,
        "release_ready_rows": 0,
        "production_execution_allowed_rows": 0,
        "blocker": "Schema contracts are ready, but no operator response or real input is present.",
        "policy": "P683 is a local response schema contract only; it does not receive or approve P0 input.",
        **FALSE_FLAGS,
    }
    output_rows = contract_rows + [summary]

    OUT_JSONL.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSONL.write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in output_rows),
        encoding="utf-8",
    )
    report = {
        "created_at": created_at,
        "local_only": True,
        "source_preflight": "datasets/governance/p682_p0_real_input_response_receive_preflight.jsonl",
        "source_report": "reports/p682_p0_real_input_response_receive_preflight_report.json",
        "source_validation_report": "reports/p682_p0_real_input_response_receive_preflight_validation_report.json",
        "source_receive_preflight_rows": p682_report.get("receive_preflight_rows"),
        "source_p682_validation_success": p682_validation.get("success"),
        "schema_contract_rows": len(contract_rows),
        "audit_rows": len(output_rows),
        "open_schema_contract_rows": summary["open_schema_contract_rows"],
        "empty_schema_contract_rows": summary["empty_schema_contract_rows"],
        "blocked_schema_contract_rows": summary["blocked_schema_contract_rows"],
        "schema_contract_status": summary["schema_contract_status"],
        "operator_dispatch_sent_rows": 0,
        "operator_acknowledged_rows": 0,
        "external_input_acknowledged_rows": 0,
        "receive_preflight_executed_rows": 0,
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
        "training_import_allowed_rows": 0,
        "safe_for_training_import_rows": 0,
        "safe_for_model_claim_rows": 0,
        "customer_delivery_ready_rows": 0,
        "release_ready_rows": 0,
        "production_execution_allowed_rows": 0,
        "preflight_jsonl": str(OUT_JSONL.relative_to(AI_ROOT)),
        "policy": "P683 binds schema contracts for future responses; all gates remain fail-closed.",
        **FALSE_FLAGS,
    }
    OUT_REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    lines = [
        "# P683 P0 real-input response schema contract",
        "",
        "Status: schema contracts are bound, empty, and blocked until real operator responses arrive.",
        "",
        f"- schema_contract_rows: `{len(contract_rows)}`",
        f"- open_schema_contract_rows: `{summary['open_schema_contract_rows']}`",
        "- response_payload_present_rows: `0`",
        "- response_received_rows: `0`",
        "- real_input_received_rows: `0`",
        "- release_ready: `false`",
        "",
        "| Order | Lane | Field count | Envelope count | Status |",
        "|---:|---|---:|---:|---|",
    ]
    for row in contract_rows:
        lines.append(
            f"| {row['schema_contract_order']} | {row['lane']} | {row['expected_response_field_count']} | "
            f"{row['response_envelope_field_count']} | `{row['schema_contract_status']}` |"
        )
    lines.extend([
        "",
        "This contract shell does not receive input, execute validators, write formal targets, import labels, assert claims, release, or authorize production.",
    ])
    OUT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps({
        "schema_contract_rows": len(contract_rows),
        "open_schema_contract_rows": summary["open_schema_contract_rows"],
        "response_payload_present_rows": 0,
        "response_received_rows": 0,
        "real_input_received_rows": 0,
        "release_ready": False,
        "output": str(OUT_REPORT),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
