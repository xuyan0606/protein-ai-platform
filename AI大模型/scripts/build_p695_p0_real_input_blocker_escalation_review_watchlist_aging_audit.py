#!/usr/bin/env python3
"""Build a fail-closed P0 blocker escalation review watchlist aging audit from P694."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
SOURCE_JSONL = AI_ROOT / "datasets/governance/p694_p0_real_input_blocker_escalation_review_watchlist.jsonl"
SOURCE_REPORT = AI_ROOT / "reports/p694_p0_real_input_blocker_escalation_review_watchlist_report.json"
SOURCE_VALIDATION = AI_ROOT / "reports/p694_p0_real_input_blocker_escalation_review_watchlist_validation_report.json"
OUT_JSONL = AI_ROOT / "datasets/governance/p695_p0_real_input_blocker_escalation_review_watchlist_aging_audit.jsonl"
OUT_REPORT = AI_ROOT / "reports/p695_p0_real_input_blocker_escalation_review_watchlist_aging_audit_report.json"
OUT_MD = AI_ROOT / "reports/p695_p0_real_input_blocker_escalation_review_watchlist_aging_audit.md"

FALSE_FIELDS = (
    "queue_dequeued", "operator_dispatch_sent", "operator_acknowledged",
    "external_input_acknowledged", "receive_preflight_executed",
    "response_payload_present", "response_received", "response_validated",
    "real_input_received", "evidence_payload_present", "evidence_quarantined",
    "evidence_released", "evidence_promoted_to_decision", "decision_route_executed",
    "routed_to_formal_review", "formal_intake_dry_run_executed",
    "formal_intake_dry_run_passed", "formal_validator_passed",
    "reviewed_decision_written", "formal_intake_written", "runtime_receipt_written",
    "training_label_written", "aging_reviewed", "staleness_resolved",
    "escalation_reviewed", "blocker_resolved", "escalation_sent",
    "escalation_acknowledged", "closeout_ready", "completion_ready_observed",
    "completion_ready", "p0_unblocked", "training_import_allowed",
    "safe_for_training_import", "safe_for_model_claim", "customer_delivery_ready",
    "release_ready", "production_execution_allowed",
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
        "blocker_review_aging_id": f"p695::{source.get('lane')}",
        "blocker_review_aging_order": order,
        "created_at": created_at,
        "source_blocker_review_watch_id": source.get("blocker_review_watch_id"),
        "source_p694_validation_success": True,
        "blocker_review_aging_status": "open_empty_blocker_review_watchlist_aging_audit",
        "blocker_review_aging_open": True,
        "blocker_review_aging_empty": True,
        "blocker_review_aging_blocked": True,
        "p0_unblocked": False,
        "p0_completion_ready": False,
        "aging_note": (
            "P695 records that the P694 review watchlist remains open, empty, and blocked. "
            "No age review or staleness resolution has occurred."
        ),
        "policy": (
            "P695 is a local aging-audit shell only. It does not review age, resolve staleness, "
            "perform escalation review, send escalation, receive acknowledgement, resolve blockers, "
            "approve closeout, write decisions, create receipts or labels, or authorize claims, release, "
            "delivery, or production."
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
    source_rows.sort(key=lambda row: int(row.get("blocker_review_watch_order") or 0))
    aging_rows = [build_row(row, index, created_at) for index, row in enumerate(source_rows, start=1)]
    summary = {
        "blocker_review_aging_id": "p695::summary",
        "blocker_review_aging_order": len(aging_rows) + 1,
        "created_at": created_at,
        "local_only": True,
        "lane": "summary",
        "source_blocker_review_watch_rows": source_report.get("blocker_review_watch_rows"),
        "source_p694_validation_success": source_validation.get("success"),
        "blocker_review_aging_rows": len(aging_rows),
        "open_blocker_review_aging_rows": sum(row["blocker_review_aging_open"] is True for row in aging_rows),
        "empty_blocker_review_aging_rows": sum(row["blocker_review_aging_empty"] is True for row in aging_rows),
        "blocked_blocker_review_aging_rows": sum(row["blocker_review_aging_blocked"] is True for row in aging_rows),
        "blocker_review_aging_status": (
            "open_empty_blocker_review_watchlist_aging_audit"
            if aging_rows else "blocked_missing_review_watchlist"
        ),
        "p0_unblocked": False,
        "p0_completion_ready": False,
        "blocker": "P694 review watchlist remains open and empty; no aging review has been performed.",
        "policy": "P695 is a local aging-audit shell only; it does not receive or approve P0 input.",
        **zero_counts(),
        **{field: False for field in FALSE_FIELDS},
    }
    rows = aging_rows + [summary]
    OUT_JSONL.write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )
    report = {
        "created_at": created_at,
        "local_only": True,
        "manifest_id": "P695",
        "source_jsonl": str(SOURCE_JSONL.relative_to(AI_ROOT)),
        "source_report": str(SOURCE_REPORT.relative_to(AI_ROOT)),
        "source_validation_report": str(SOURCE_VALIDATION.relative_to(AI_ROOT)),
        "source_blocker_review_watch_rows": source_report.get("blocker_review_watch_rows"),
        "source_p694_validation_success": source_validation.get("success"),
        "blocker_review_aging_rows": len(aging_rows),
        "audit_rows": len(rows),
        "open_blocker_review_aging_rows": summary["open_blocker_review_aging_rows"],
        "empty_blocker_review_aging_rows": summary["empty_blocker_review_aging_rows"],
        "blocked_blocker_review_aging_rows": summary["blocked_blocker_review_aging_rows"],
        "blocker_review_aging_status": summary["blocker_review_aging_status"],
        "p0_unblocked": False,
        "p0_completion_ready": False,
        "artifact_jsonl": str(OUT_JSONL.relative_to(AI_ROOT)),
        "artifact_md": str(OUT_MD.relative_to(AI_ROOT)),
        "policy": "P695 binds source-bound aging audit rows; all review, input, resolution, and authorization gates remain fail-closed.",
        **zero_counts(),
        **{field: False for field in FALSE_FIELDS},
    }
    OUT_REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    lines = [
        "# P695 P0 real-input blocker escalation review watchlist aging audit",
        "",
        "Status: aging audit is open and empty; no aging review or staleness resolution has occurred.",
        "",
        f"- blocker_review_aging_rows: `{len(aging_rows)}`",
        f"- open_blocker_review_aging_rows: `{summary['open_blocker_review_aging_rows']}`",
        f"- empty_blocker_review_aging_rows: `{summary['empty_blocker_review_aging_rows']}`",
        f"- blocked_blocker_review_aging_rows: `{summary['blocked_blocker_review_aging_rows']}`",
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
    for row in aging_rows:
        lines.append(
            f"| {row['blocker_review_aging_order']} | {row['lane']} | "
            f"`{row['formal_target_file']}` | `{row['blocker_review_aging_status']}` |"
        )
    lines.extend([
        "",
        "This audit does not review age or resolve staleness, and it does not send escalation, acknowledge input, resolve blockers, approve closeout, execute intake, import labels, assert claims, release, or authorize production.",
    ])
    OUT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps({
        "blocker_review_aging_rows": len(aging_rows),
        "open_blocker_review_aging_rows": summary["open_blocker_review_aging_rows"],
        "empty_blocker_review_aging_rows": summary["empty_blocker_review_aging_rows"],
        "blocked_blocker_review_aging_rows": summary["blocked_blocker_review_aging_rows"],
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
