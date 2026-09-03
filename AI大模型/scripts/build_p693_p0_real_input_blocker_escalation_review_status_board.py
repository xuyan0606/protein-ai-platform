#!/usr/bin/env python3
"""Build a fail-closed P0 real-input blocker escalation review status board from P692."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
SOURCE_JSONL = AI_ROOT / "datasets/governance/p692_p0_real_input_blocker_escalation_review_queue.jsonl"
SOURCE_REPORT = AI_ROOT / "reports/p692_p0_real_input_blocker_escalation_review_queue_report.json"
SOURCE_VALIDATION = AI_ROOT / "reports/p692_p0_real_input_blocker_escalation_review_queue_validation_report.json"
OUT_JSONL = AI_ROOT / "datasets/governance/p693_p0_real_input_blocker_escalation_review_status_board.jsonl"
OUT_REPORT = AI_ROOT / "reports/p693_p0_real_input_blocker_escalation_review_status_board_report.json"
OUT_MD = AI_ROOT / "reports/p693_p0_real_input_blocker_escalation_review_status_board.md"

FALSE_FIELDS = (
    "queue_dequeued", "operator_dispatch_sent", "operator_acknowledged",
    "external_input_acknowledged", "receive_preflight_executed",
    "response_payload_present", "response_received", "response_validated",
    "real_input_received", "evidence_payload_present", "evidence_quarantined",
    "evidence_released", "evidence_promoted_to_decision", "decision_route_executed",
    "routed_to_formal_review", "formal_intake_dry_run_executed",
    "formal_intake_dry_run_passed", "formal_validator_passed",
    "reviewed_decision_written", "formal_intake_written", "runtime_receipt_written",
    "training_label_written", "escalation_reviewed", "blocker_resolved",
    "escalation_sent", "escalation_acknowledged", "closeout_ready",
    "completion_ready_observed", "completion_ready", "p0_unblocked",
    "training_import_allowed", "safe_for_training_import", "safe_for_model_claim",
    "customer_delivery_ready", "release_ready", "production_execution_allowed",
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


def zero_counts() -> dict[str, int]:
    return {f"{field}_rows": 0 for field in FALSE_FIELDS}


def build_row(source: dict[str, Any], order: int, created_at: str) -> dict[str, Any]:
    return {
        "blocker_review_status_id": f"p693::{source.get('lane')}",
        "blocker_review_status_order": order,
        "created_at": created_at,
        "local_only": True,
        "lane": source.get("lane"),
        "priority": source.get("priority"),
        "source_blocker_review_id": source.get("blocker_review_id"),
        "source_blocker_watch_id": source.get("source_blocker_watch_id"),
        "source_blocker_status_id": source.get("source_blocker_status_id"),
        "source_blocker_escalation_id": source.get("source_blocker_escalation_id"),
        "source_blocker_ledger_id": source.get("source_blocker_ledger_id"),
        "source_closeout_gate_id": source.get("source_closeout_gate_id"),
        "source_formal_intake_dry_run_id": source.get("source_formal_intake_dry_run_id"),
        "source_decision_routing_id": source.get("source_decision_routing_id"),
        "source_evidence_quarantine_id": source.get("source_evidence_quarantine_id"),
        "source_schema_contract_id": source.get("source_schema_contract_id"),
        "source_receive_preflight_id": source.get("source_receive_preflight_id"),
        "source_bundle_id": source.get("source_bundle_id"),
        "source_checklist_id": source.get("source_checklist_id"),
        "blocker_review_status": "open_empty_blocker_escalation_review_status_board",
        "blocker_review_status_open": True,
        "blocker_review_status_empty": True,
        "blocker_review_status_blocked": True,
        "source_blocker_review_status": source.get("blocker_review_status"),
        "formal_target_file": source.get("formal_target_file"),
        "source_work_file": source.get("source_work_file"),
        "template_or_reference_file": source.get("template_or_reference_file"),
        "expected_response_fields": source.get("expected_response_fields") or [],
        "response_envelope_required_fields": source.get("response_envelope_required_fields") or [],
        "validator_command": source.get("validator_command"),
        "operator_action": source.get("operator_action"),
        "completion_condition": source.get("completion_condition"),
        "blocker_reason": source.get("blocker_reason"),
        "escalation_candidate_reason": source.get("escalation_candidate_reason"),
        "next_unblocking_evidence": source.get("next_unblocking_evidence"),
        "status_note": (
            "P693 observes the P692 review queue as still open, empty, and blocked. No escalation review, "
            "dispatch, acknowledgement, blocker resolution, or closeout approval has occurred."
        ),
        "policy": (
            "P693 is a local blocker escalation review status board only. It does not perform review, send "
            "escalation, receive acknowledgement, resolve blockers, approve closeout, write decisions, "
            "create runtime receipts or training labels, or authorize claims, release, delivery, or production."
        ),
        **{field: False for field in FALSE_FIELDS},
    }


def main() -> int:
    created_at = datetime.now(timezone.utc).isoformat()
    source_report = load_json(SOURCE_REPORT)
    source_validation = load_json(SOURCE_VALIDATION)
    source_rows = [row for row in load_jsonl(SOURCE_JSONL) if row.get("lane") != "summary"]
    source_rows.sort(key=lambda row: int(row.get("blocker_review_order") or 0))
    status_rows = [build_row(row, index, created_at) for index, row in enumerate(source_rows, start=1)]
    summary = {
        "blocker_review_status_id": "p693::summary",
        "blocker_review_status_order": len(status_rows) + 1,
        "created_at": created_at,
        "local_only": True,
        "lane": "summary",
        "source_blocker_review_rows": source_report.get("blocker_review_rows"),
        "source_p692_validation_success": source_validation.get("success"),
        "blocker_review_status_rows": len(status_rows),
        "open_blocker_review_status_rows": sum(row["blocker_review_status_open"] is True for row in status_rows),
        "empty_blocker_review_status_rows": sum(row["blocker_review_status_empty"] is True for row in status_rows),
        "blocked_blocker_review_status_rows": sum(row["blocker_review_status_blocked"] is True for row in status_rows),
        "blocker_review_status": "open_empty_blocker_escalation_review_status_board" if status_rows else "blocked_missing_review_queue",
        "blocker": "P692 review queue remains open and empty; no escalation review has been performed.",
        "policy": "P693 is a local review status board shell only; it does not receive or approve P0 input.",
        **zero_counts(),
        **{field: False for field in FALSE_FIELDS},
    }
    rows = status_rows + [summary]
    OUT_JSONL.write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )
    report = {
        "created_at": created_at,
        "local_only": True,
        "manifest_id": "P693",
        "source_jsonl": str(SOURCE_JSONL.relative_to(AI_ROOT)),
        "source_report": str(SOURCE_REPORT.relative_to(AI_ROOT)),
        "source_validation_report": str(SOURCE_VALIDATION.relative_to(AI_ROOT)),
        "source_blocker_review_rows": source_report.get("blocker_review_rows"),
        "source_p692_validation_success": source_validation.get("success"),
        "blocker_review_status_rows": len(status_rows),
        "audit_rows": len(rows),
        "open_blocker_review_status_rows": summary["open_blocker_review_status_rows"],
        "empty_blocker_review_status_rows": summary["empty_blocker_review_status_rows"],
        "blocked_blocker_review_status_rows": summary["blocked_blocker_review_status_rows"],
        "blocker_review_status": summary["blocker_review_status"],
        "artifact_jsonl": str(OUT_JSONL.relative_to(AI_ROOT)),
        "artifact_md": str(OUT_MD.relative_to(AI_ROOT)),
        "policy": "P693 binds empty blocker escalation review status rows; all review, escalation, input, and authorization gates remain fail-closed.",
        **zero_counts(),
        **{field: False for field in FALSE_FIELDS},
    }
    OUT_REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    lines = [
        "# P693 P0 real-input blocker escalation review status board",
        "",
        "Status: blocker escalation review status board is open and empty; no review has been performed.",
        "",
        f"- blocker_review_status_rows: `{len(status_rows)}`",
        f"- open_blocker_review_status_rows: `{summary['open_blocker_review_status_rows']}`",
        f"- empty_blocker_review_status_rows: `{summary['empty_blocker_review_status_rows']}`",
        f"- blocked_blocker_review_status_rows: `{summary['blocked_blocker_review_status_rows']}`",
        "- escalation_reviewed_rows: `0`",
        "- escalation_sent_rows: `0`",
        "- escalation_acknowledged_rows: `0`",
        "- blocker_resolved_rows: `0`",
        "- closeout_ready_rows: `0`",
        "- p0_unblocked: `false`",
        "- release_ready: `false`",
        "",
        "| Order | Lane | Formal target | Status |",
        "|---:|---|---|---|",
    ]
    for row in status_rows:
        lines.append(
            f"| {row['blocker_review_status_order']} | {row['lane']} | `{row['formal_target_file']}` | "
            f"`{row['blocker_review_status']}` |"
        )
    lines.extend([
        "",
        "This status board does not perform review or send escalation, acknowledge escalation, resolve blockers, approve closeout, execute intake, import labels, assert claims, release, or authorize production.",
    ])
    OUT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps({
        "blocker_review_status_rows": len(status_rows),
        "open_blocker_review_status_rows": summary["open_blocker_review_status_rows"],
        "empty_blocker_review_status_rows": summary["empty_blocker_review_status_rows"],
        "blocked_blocker_review_status_rows": summary["blocked_blocker_review_status_rows"],
        "escalation_reviewed_rows": 0,
        "escalation_sent_rows": 0,
        "escalation_acknowledged_rows": 0,
        "blocker_resolved_rows": 0,
        "closeout_ready_rows": 0,
        "response_received_rows": 0,
        "real_input_received_rows": 0,
        "p0_unblocked": False,
        "release_ready": False,
        "output": str(OUT_REPORT),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
