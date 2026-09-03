#!/usr/bin/env python3
"""Build a fail-closed P0 real-input response decision routing shell from P684."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
P684_QUARANTINE = AI_ROOT / "datasets" / "governance" / "p684_p0_real_input_response_evidence_quarantine.jsonl"
P684_REPORT = AI_ROOT / "reports" / "p684_p0_real_input_response_evidence_quarantine_report.json"
P684_VALIDATION = AI_ROOT / "reports" / "p684_p0_real_input_response_evidence_quarantine_validation_report.json"
OUT_JSONL = AI_ROOT / "datasets" / "governance" / "p685_p0_real_input_response_decision_routing.jsonl"
OUT_REPORT = AI_ROOT / "reports" / "p685_p0_real_input_response_decision_routing_report.json"
OUT_MD = AI_ROOT / "reports" / "p685_p0_real_input_response_decision_routing.md"

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
    "decision_route_executed": False,
    "routed_to_formal_review": False,
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


def zero_counts() -> dict[str, int]:
    return {f"{field}_rows": 0 for field in FALSE_FLAGS}


def routing_row(row: dict[str, Any], created_at: str) -> dict[str, Any]:
    return {
        "decision_routing_id": f"p685::{row.get('lane')}",
        "decision_routing_order": row.get("evidence_quarantine_order"),
        "created_at": created_at,
        "local_only": True,
        "lane": row.get("lane"),
        "priority": row.get("priority"),
        "source_evidence_quarantine_id": row.get("evidence_quarantine_id"),
        "source_schema_contract_id": row.get("source_schema_contract_id"),
        "source_receive_preflight_id": row.get("source_receive_preflight_id"),
        "source_bundle_id": row.get("source_bundle_id"),
        "source_checklist_id": row.get("source_checklist_id"),
        "decision_routing_status": "open_empty_decision_routing",
        "decision_routing_open": True,
        "decision_routing_empty": True,
        "decision_routing_blocked": True,
        "formal_target_file": row.get("formal_target_file"),
        "source_work_file": row.get("source_work_file"),
        "template_or_reference_file": row.get("template_or_reference_file"),
        "expected_response_fields": row.get("expected_response_fields") or [],
        "response_envelope_required_fields": row.get("response_envelope_required_fields") or [],
        "validator_command": row.get("validator_command"),
        "operator_action": row.get("operator_action"),
        "completion_condition": row.get("completion_condition"),
        "routing_blocker": "No quarantined evidence has been released; decision route must remain unexecuted.",
        "policy": (
            "P685 records empty decision routing rows only. It does not execute routes, send evidence "
            "to formal review, write decisions, perform formal intake, create runtime receipts or training labels, "
            "or approve model claims, release, delivery, or production."
        ),
        **FALSE_FLAGS,
    }


def main() -> int:
    created_at = datetime.now(timezone.utc).isoformat()
    p684_report = load_json(P684_REPORT)
    p684_validation = load_json(P684_VALIDATION)
    source_rows = load_jsonl(P684_QUARANTINE)
    lane_rows = sorted(
        (row for row in source_rows if row.get("lane") != "summary"),
        key=lambda row: int(row.get("evidence_quarantine_order") or 0),
    )
    routing_rows = [routing_row(row, created_at) for row in lane_rows]
    summary = {
        "decision_routing_id": "p685::summary",
        "decision_routing_order": len(routing_rows) + 1,
        "created_at": created_at,
        "local_only": True,
        "lane": "summary",
        "source_evidence_quarantine_rows": p684_report.get("evidence_quarantine_rows"),
        "source_p684_validation_success": p684_validation.get("success"),
        "decision_routing_rows": len(routing_rows),
        "open_decision_routing_rows": sum(1 for row in routing_rows if row["decision_routing_open"] is True),
        "empty_decision_routing_rows": sum(1 for row in routing_rows if row["decision_routing_empty"] is True),
        "blocked_decision_routing_rows": sum(1 for row in routing_rows if row["decision_routing_blocked"] is True),
        "decision_routing_status": "open_empty_decision_routing" if routing_rows else "blocked_missing_source_quarantine",
        "blocker": "Decision routing is open, but no released evidence or response payload is present.",
        "policy": "P685 is a local decision-routing shell only; it does not receive or approve P0 input.",
        **zero_counts(),
        **FALSE_FLAGS,
    }
    output_rows = routing_rows + [summary]

    OUT_JSONL.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSONL.write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in output_rows),
        encoding="utf-8",
    )
    report = {
        "created_at": created_at,
        "local_only": True,
        "source_quarantine": "datasets/governance/p684_p0_real_input_response_evidence_quarantine.jsonl",
        "source_report": "reports/p684_p0_real_input_response_evidence_quarantine_report.json",
        "source_validation_report": "reports/p684_p0_real_input_response_evidence_quarantine_validation_report.json",
        "source_evidence_quarantine_rows": p684_report.get("evidence_quarantine_rows"),
        "source_p684_validation_success": p684_validation.get("success"),
        "decision_routing_rows": len(routing_rows),
        "audit_rows": len(output_rows),
        "open_decision_routing_rows": summary["open_decision_routing_rows"],
        "empty_decision_routing_rows": summary["empty_decision_routing_rows"],
        "blocked_decision_routing_rows": summary["blocked_decision_routing_rows"],
        "decision_routing_status": summary["decision_routing_status"],
        "preflight_jsonl": str(OUT_JSONL.relative_to(AI_ROOT)),
        "policy": "P685 binds empty decision routing rows; all gates remain fail-closed.",
        **zero_counts(),
        **FALSE_FLAGS,
    }
    OUT_REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    lines = [
        "# P685 P0 real-input response decision routing",
        "",
        "Status: decision routing is open and empty; no evidence has been released for routing.",
        "",
        f"- decision_routing_rows: `{len(routing_rows)}`",
        f"- open_decision_routing_rows: `{summary['open_decision_routing_rows']}`",
        "- decision_route_executed_rows: `0`",
        "- routed_to_formal_review_rows: `0`",
        "- response_received_rows: `0`",
        "- release_ready: `false`",
        "",
        "| Order | Lane | Formal target | Status |",
        "|---:|---|---|---|",
    ]
    for row in routing_rows:
        lines.append(
            f"| {row['decision_routing_order']} | {row['lane']} | `{row['formal_target_file']}` | "
            f"`{row['decision_routing_status']}` |"
        )
    lines.extend([
        "",
        "This routing shell does not route evidence, write formal decisions, import labels, assert claims, release, or authorize production.",
    ])
    OUT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps({
        "decision_routing_rows": len(routing_rows),
        "open_decision_routing_rows": summary["open_decision_routing_rows"],
        "decision_route_executed_rows": 0,
        "routed_to_formal_review_rows": 0,
        "response_received_rows": 0,
        "real_input_received_rows": 0,
        "release_ready": False,
        "output": str(OUT_REPORT),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
