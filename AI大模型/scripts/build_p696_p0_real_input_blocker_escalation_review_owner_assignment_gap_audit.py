#!/usr/bin/env python3
"""Build a fail-closed P0 owner-assignment gap audit from P695."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
SOURCE_JSONL = AI_ROOT / "datasets/governance/p695_p0_real_input_blocker_escalation_review_watchlist_aging_audit.jsonl"
SOURCE_REPORT = AI_ROOT / "reports/p695_p0_real_input_blocker_escalation_review_watchlist_aging_audit_report.json"
SOURCE_VALIDATION = AI_ROOT / "reports/p695_p0_real_input_blocker_escalation_review_watchlist_aging_audit_validation_report.json"
OUT_JSONL = AI_ROOT / "datasets/governance/p696_p0_real_input_blocker_escalation_review_owner_assignment_gap_audit.jsonl"
OUT_REPORT = AI_ROOT / "reports/p696_p0_real_input_blocker_escalation_review_owner_assignment_gap_audit_report.json"
OUT_MD = AI_ROOT / "reports/p696_p0_real_input_blocker_escalation_review_owner_assignment_gap_audit.md"

FALSE_FIELDS = (
    "queue_dequeued", "operator_dispatch_sent", "operator_acknowledged",
    "owner_assigned", "owner_acknowledged", "external_input_acknowledged",
    "receive_preflight_executed", "response_payload_present", "response_received",
    "response_validated", "real_input_received", "evidence_payload_present",
    "evidence_quarantined", "evidence_released", "evidence_promoted_to_decision",
    "decision_route_executed", "routed_to_formal_review", "formal_intake_dry_run_executed",
    "formal_intake_dry_run_passed", "formal_validator_passed", "reviewed_decision_written",
    "formal_intake_written", "runtime_receipt_written", "training_label_written",
    "aging_reviewed", "staleness_resolved", "escalation_reviewed", "blocker_resolved",
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
    row = dict(source)
    row.update({
        "owner_assignment_gap_id": f"p696::{source.get('lane')}",
        "owner_assignment_gap_order": order,
        "created_at": created_at,
        "source_blocker_review_aging_id": source.get("blocker_review_aging_id"),
        "source_p695_validation_success": True,
        "owner_assignment_gap_status": "open_empty_blocker_review_owner_assignment_gap",
        "owner_assignment_gap_open": True,
        "owner_assignment_gap_empty": True,
        "owner_assignment_gap_blocked": True,
        "p0_unblocked": False,
        "p0_completion_ready": False,
        "owner_assignment_note": (
            "P696 records that no owner assignment or owner acknowledgement exists for the "
            "P695 aging-audit row. This is a local gap audit, not an assignment."
        ),
        "policy": (
            "P696 is a local owner-assignment gap shell only. It does not assign an owner, "
            "request acknowledgement, review aging, resolve staleness, perform escalation review, "
            "send escalation, receive input, resolve blockers, approve closeout, write decisions, "
            "create receipts or labels, or authorize claims, release, delivery, or production."
        ),
    })
    for field in FALSE_FIELDS:
        row[field] = False
    return row


def main() -> int:
    created_at = datetime.now(timezone.utc).isoformat()
    source_report = load_json(SOURCE_REPORT)
    source_validation = load_json(SOURCE_VALIDATION)
    source_rows = [row for row in load_jsonl(SOURCE_JSONL) if row.get("lane") != "summary"]
    source_rows.sort(key=lambda row: int(row.get("blocker_review_aging_order") or 0))
    gap_rows = [build_row(row, index, created_at) for index, row in enumerate(source_rows, start=1)]
    summary = {
        "owner_assignment_gap_id": "p696::summary",
        "owner_assignment_gap_order": len(gap_rows) + 1,
        "created_at": created_at,
        "local_only": True,
        "lane": "summary",
        "source_blocker_review_aging_rows": source_report.get("blocker_review_aging_rows"),
        "source_p695_validation_success": source_validation.get("success"),
        "owner_assignment_gap_rows": len(gap_rows),
        "open_owner_assignment_gap_rows": sum(row["owner_assignment_gap_open"] is True for row in gap_rows),
        "empty_owner_assignment_gap_rows": sum(row["owner_assignment_gap_empty"] is True for row in gap_rows),
        "blocked_owner_assignment_gap_rows": sum(row["owner_assignment_gap_blocked"] is True for row in gap_rows),
        "formal_intake_dry_run_executed_rows": 0,
        "formal_intake_dry_run_passed_rows": 0,
        "owner_assignment_gap_status": (
            "open_empty_blocker_review_owner_assignment_gap"
            if gap_rows else "blocked_missing_aging_audit"
        ),
        "p0_unblocked": False,
        "p0_completion_ready": False,
        "blocker": "P695 aging audit remains open and empty; no owner assignment exists.",
        "policy": "P696 is a local owner-assignment gap shell only; it does not assign or acknowledge an owner.",
        **zero_counts(),
        **{field: False for field in FALSE_FIELDS},
    }
    rows = gap_rows + [summary]
    OUT_JSONL.write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )
    report = {
        "created_at": created_at,
        "local_only": True,
        "manifest_id": "P696",
        "source_jsonl": str(SOURCE_JSONL.relative_to(AI_ROOT)),
        "source_report": str(SOURCE_REPORT.relative_to(AI_ROOT)),
        "source_validation_report": str(SOURCE_VALIDATION.relative_to(AI_ROOT)),
        "source_blocker_review_aging_rows": source_report.get("blocker_review_aging_rows"),
        "source_p695_validation_success": source_validation.get("success"),
        "owner_assignment_gap_rows": len(gap_rows),
        "audit_rows": len(rows),
        "open_owner_assignment_gap_rows": summary["open_owner_assignment_gap_rows"],
        "empty_owner_assignment_gap_rows": summary["empty_owner_assignment_gap_rows"],
        "blocked_owner_assignment_gap_rows": summary["blocked_owner_assignment_gap_rows"],
        "formal_intake_dry_run_executed_rows": 0,
        "formal_intake_dry_run_passed_rows": 0,
        "owner_assignment_gap_status": summary["owner_assignment_gap_status"],
        "p0_unblocked": False,
        "p0_completion_ready": False,
        "artifact_jsonl": str(OUT_JSONL.relative_to(AI_ROOT)),
        "artifact_md": str(OUT_MD.relative_to(AI_ROOT)),
        "policy": "P696 binds source-bound owner-assignment gap rows; all input and authorization gates remain fail-closed.",
        **zero_counts(),
        **{field: False for field in FALSE_FIELDS},
    }
    OUT_REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    lines = [
        "# P696 P0 real-input blocker escalation review owner assignment gap audit",
        "",
        "Status: owner-assignment gap audit is open and empty; no owner has been assigned or acknowledged.",
        "",
        f"- owner_assignment_gap_rows: `{len(gap_rows)}`",
        f"- open_owner_assignment_gap_rows: `{summary['open_owner_assignment_gap_rows']}`",
        f"- empty_owner_assignment_gap_rows: `{summary['empty_owner_assignment_gap_rows']}`",
        f"- blocked_owner_assignment_gap_rows: `{summary['blocked_owner_assignment_gap_rows']}`",
        "- owner_assigned_rows: `0`",
        "- owner_acknowledged_rows: `0`",
        "- aging_reviewed_rows: `0`",
        "- staleness_resolved_rows: `0`",
        "- response_received_rows: `0`",
        "- real_input_received_rows: `0`",
        "- p0_unblocked: `false`",
        "- release_ready: `false`",
        "",
        "| Order | Lane | Formal target | Status |",
        "|---:|---|---|---|",
    ]
    for row in gap_rows:
        lines.append(
            f"| {row['owner_assignment_gap_order']} | {row['lane']} | "
            f"`{row['formal_target_file']}` | `{row['owner_assignment_gap_status']}` |"
        )
    lines.extend([
        "",
        "This audit does not assign or acknowledge an owner, and it does not review aging, resolve staleness, send escalation, receive input, resolve blockers, approve closeout, execute intake, import labels, assert claims, release, or authorize production.",
    ])
    OUT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps({
        "owner_assignment_gap_rows": len(gap_rows),
        "open_owner_assignment_gap_rows": summary["open_owner_assignment_gap_rows"],
        "empty_owner_assignment_gap_rows": summary["empty_owner_assignment_gap_rows"],
        "blocked_owner_assignment_gap_rows": summary["blocked_owner_assignment_gap_rows"],
        "owner_assigned_rows": 0,
        "owner_acknowledged_rows": 0,
        "aging_reviewed_rows": 0,
        "staleness_resolved_rows": 0,
        "response_received_rows": 0,
        "real_input_received_rows": 0,
        "p0_unblocked": False,
        "release_ready": False,
        "output": str(OUT_REPORT),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
