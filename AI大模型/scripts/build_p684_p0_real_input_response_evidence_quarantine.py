#!/usr/bin/env python3
"""Build a fail-closed P0 real-input response evidence quarantine from P683."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
P683_CONTRACT = AI_ROOT / "datasets" / "governance" / "p683_p0_real_input_response_schema_contract.jsonl"
P683_REPORT = AI_ROOT / "reports" / "p683_p0_real_input_response_schema_contract_report.json"
P683_VALIDATION = AI_ROOT / "reports" / "p683_p0_real_input_response_schema_contract_validation_report.json"
OUT_JSONL = AI_ROOT / "datasets" / "governance" / "p684_p0_real_input_response_evidence_quarantine.jsonl"
OUT_REPORT = AI_ROOT / "reports" / "p684_p0_real_input_response_evidence_quarantine_report.json"
OUT_MD = AI_ROOT / "reports" / "p684_p0_real_input_response_evidence_quarantine.md"

FALSE_FLAGS = {
    "operator_dispatch_sent": False,
    "operator_acknowledged": False,
    "external_input_acknowledged": False,
    "receive_preflight_executed": False,
    "response_payload_present": False,
    "response_received": False,
    "response_validated": False,
    "real_input_received": False,
    "evidence_payload_present": False,
    "evidence_quarantined": False,
    "evidence_released": False,
    "evidence_promoted_to_decision": False,
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


def quarantine_row(row: dict[str, Any], created_at: str) -> dict[str, Any]:
    expected_fields = row.get("expected_response_fields") or []
    envelope_fields = row.get("response_envelope_required_fields") or []
    return {
        "evidence_quarantine_id": f"p684::{row.get('lane')}",
        "evidence_quarantine_order": row.get("schema_contract_order"),
        "created_at": created_at,
        "local_only": True,
        "lane": row.get("lane"),
        "priority": row.get("priority"),
        "source_schema_contract_id": row.get("schema_contract_id"),
        "source_receive_preflight_id": row.get("source_receive_preflight_id"),
        "source_bundle_id": row.get("source_bundle_id"),
        "source_checklist_id": row.get("source_checklist_id"),
        "evidence_quarantine_status": "open_empty_evidence_quarantine",
        "evidence_quarantine_open": True,
        "evidence_quarantine_empty": True,
        "evidence_quarantine_blocked": True,
        "formal_target_file": row.get("formal_target_file"),
        "source_work_file": row.get("source_work_file"),
        "template_or_reference_file": row.get("template_or_reference_file"),
        "expected_response_fields": expected_fields,
        "response_envelope_required_fields": envelope_fields,
        "validator_command": row.get("validator_command"),
        "operator_action": row.get("operator_action"),
        "completion_condition": row.get("completion_condition"),
        "quarantine_reason": "No response payload has been received; nothing is eligible for release or promotion.",
        "policy": (
            "P684 records empty evidence quarantine rows only. It does not receive, validate, "
            "release, or promote evidence; does not write reviewed decisions, formal intake, "
            "runtime receipts, or training labels; and does not approve model claims, release, or production."
        ),
        **FALSE_FLAGS,
    }


def main() -> int:
    created_at = datetime.now(timezone.utc).isoformat()
    p683_report = load_json(P683_REPORT)
    p683_validation = load_json(P683_VALIDATION)
    source_rows = load_jsonl(P683_CONTRACT)
    lane_rows = sorted(
        (row for row in source_rows if row.get("lane") != "summary"),
        key=lambda row: int(row.get("schema_contract_order") or 0),
    )
    quarantine_rows = [quarantine_row(row, created_at) for row in lane_rows]
    summary = {
        "evidence_quarantine_id": "p684::summary",
        "evidence_quarantine_order": len(quarantine_rows) + 1,
        "created_at": created_at,
        "local_only": True,
        "lane": "summary",
        "source_schema_contract_rows": p683_report.get("schema_contract_rows"),
        "source_p683_validation_success": p683_validation.get("success"),
        "evidence_quarantine_rows": len(quarantine_rows),
        "open_evidence_quarantine_rows": sum(1 for row in quarantine_rows if row["evidence_quarantine_open"] is True),
        "empty_evidence_quarantine_rows": sum(1 for row in quarantine_rows if row["evidence_quarantine_empty"] is True),
        "blocked_evidence_quarantine_rows": sum(1 for row in quarantine_rows if row["evidence_quarantine_blocked"] is True),
        "evidence_quarantine_status": "open_empty_evidence_quarantine" if quarantine_rows else "blocked_missing_source_contract",
        "operator_dispatch_sent_rows": 0,
        "operator_acknowledged_rows": 0,
        "external_input_acknowledged_rows": 0,
        "receive_preflight_executed_rows": 0,
        "response_payload_present_rows": 0,
        "response_received_rows": 0,
        "response_validated_rows": 0,
        "real_input_received_rows": 0,
        "evidence_payload_present_rows": 0,
        "evidence_quarantined_rows": 0,
        "evidence_released_rows": 0,
        "evidence_promoted_to_decision_rows": 0,
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
        "blocker": "Evidence quarantine is open, but no response payload or real input is present.",
        "policy": "P684 is a local evidence quarantine only; it does not receive or approve P0 input.",
        **FALSE_FLAGS,
    }
    output_rows = quarantine_rows + [summary]

    OUT_JSONL.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSONL.write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in output_rows),
        encoding="utf-8",
    )
    report = {
        "created_at": created_at,
        "local_only": True,
        "source_contract": "datasets/governance/p683_p0_real_input_response_schema_contract.jsonl",
        "source_report": "reports/p683_p0_real_input_response_schema_contract_report.json",
        "source_validation_report": "reports/p683_p0_real_input_response_schema_contract_validation_report.json",
        "source_schema_contract_rows": p683_report.get("schema_contract_rows"),
        "source_p683_validation_success": p683_validation.get("success"),
        "evidence_quarantine_rows": len(quarantine_rows),
        "audit_rows": len(output_rows),
        "open_evidence_quarantine_rows": summary["open_evidence_quarantine_rows"],
        "empty_evidence_quarantine_rows": summary["empty_evidence_quarantine_rows"],
        "blocked_evidence_quarantine_rows": summary["blocked_evidence_quarantine_rows"],
        "evidence_quarantine_status": summary["evidence_quarantine_status"],
        "operator_dispatch_sent_rows": 0,
        "operator_acknowledged_rows": 0,
        "external_input_acknowledged_rows": 0,
        "receive_preflight_executed_rows": 0,
        "response_payload_present_rows": 0,
        "response_received_rows": 0,
        "response_validated_rows": 0,
        "real_input_received_rows": 0,
        "evidence_payload_present_rows": 0,
        "evidence_quarantined_rows": 0,
        "evidence_released_rows": 0,
        "evidence_promoted_to_decision_rows": 0,
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
        "policy": "P684 binds empty evidence quarantine rows; all gates remain fail-closed.",
        **FALSE_FLAGS,
    }
    OUT_REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    lines = [
        "# P684 P0 real-input response evidence quarantine",
        "",
        "Status: evidence quarantine is open and empty; no response payload has been received.",
        "",
        f"- evidence_quarantine_rows: `{len(quarantine_rows)}`",
        f"- open_evidence_quarantine_rows: `{summary['open_evidence_quarantine_rows']}`",
        "- evidence_payload_present_rows: `0`",
        "- evidence_quarantined_rows: `0`",
        "- response_received_rows: `0`",
        "- release_ready: `false`",
        "",
        "| Order | Lane | Formal target | Status |",
        "|---:|---|---|---|",
    ]
    for row in quarantine_rows:
        lines.append(
            f"| {row['evidence_quarantine_order']} | {row['lane']} | `{row['formal_target_file']}` | "
            f"`{row['evidence_quarantine_status']}` |"
        )
    lines.extend([
        "",
        "This quarantine shell does not release evidence, write formal decisions, import labels, assert claims, release, or authorize production.",
    ])
    OUT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps({
        "evidence_quarantine_rows": len(quarantine_rows),
        "open_evidence_quarantine_rows": summary["open_evidence_quarantine_rows"],
        "evidence_payload_present_rows": 0,
        "response_received_rows": 0,
        "real_input_received_rows": 0,
        "release_ready": False,
        "output": str(OUT_REPORT),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
