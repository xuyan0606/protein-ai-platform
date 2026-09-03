#!/usr/bin/env python3
"""Build a fail-closed P0 evidence-missing matrix from P696."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
SOURCE_JSONL = AI_ROOT / "datasets/governance/p696_p0_real_input_blocker_escalation_review_owner_assignment_gap_audit.jsonl"
SOURCE_REPORT = AI_ROOT / "reports/p696_p0_real_input_blocker_escalation_review_owner_assignment_gap_audit_report.json"
SOURCE_VALIDATION = AI_ROOT / "reports/p696_p0_real_input_blocker_escalation_review_owner_assignment_gap_audit_validation_report.json"
OUT_JSONL = AI_ROOT / "datasets/governance/p697_p0_real_input_blocker_escalation_review_evidence_missing_matrix.jsonl"
OUT_REPORT = AI_ROOT / "reports/p697_p0_real_input_blocker_escalation_review_evidence_missing_matrix_report.json"
OUT_MD = AI_ROOT / "reports/p697_p0_real_input_blocker_escalation_review_evidence_missing_matrix.md"

FALSE_FIELDS = (
    "queue_dequeued", "operator_dispatch_sent", "operator_acknowledged",
    "owner_assigned", "owner_acknowledged", "external_input_acknowledged",
    "receive_preflight_executed", "response_payload_present", "response_received",
    "response_validated", "real_input_received", "evidence_payload_present",
    "evidence_received", "evidence_validated", "evidence_quarantined",
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
        "evidence_missing_matrix_id": f"p697::{source.get('lane')}",
        "evidence_missing_matrix_order": order,
        "created_at": created_at,
        "source_owner_assignment_gap_id": source.get("owner_assignment_gap_id"),
        "source_p696_validation_success": True,
        "evidence_missing_matrix_status": "open_empty_evidence_missing_matrix",
        "evidence_missing_matrix_open": True,
        "evidence_missing_matrix_empty": True,
        "evidence_missing_matrix_blocked": True,
        "p0_unblocked": False,
        "p0_completion_ready": False,
        "evidence_missing_reason": (
            "No real owner assignment or acknowledgement exists; required evidence has not been "
            "received and cannot be validated or promoted."
        ),
        "evidence_missing_note": (
            "P697 records missing evidence prerequisites only. It does not receive, validate, "
            "quarantine, release, or promote evidence."
        ),
        "policy": (
            "P697 is a local evidence-missing matrix only. It does not assign owners, receive or "
            "validate evidence, perform escalation review, send escalation, receive input, resolve "
            "blockers, approve closeout, write decisions, create receipts or labels, or authorize "
            "claims, release, delivery, or production."
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
    source_rows.sort(key=lambda row: int(row.get("owner_assignment_gap_order") or 0))
    matrix_rows = [build_row(row, index, created_at) for index, row in enumerate(source_rows, start=1)]
    summary = {
        "evidence_missing_matrix_id": "p697::summary",
        "evidence_missing_matrix_order": len(matrix_rows) + 1,
        "created_at": created_at,
        "local_only": True,
        "lane": "summary",
        "source_owner_assignment_gap_rows": source_report.get("owner_assignment_gap_rows"),
        "source_p696_validation_success": source_validation.get("success"),
        "evidence_missing_matrix_rows": len(matrix_rows),
        "open_evidence_missing_matrix_rows": sum(row["evidence_missing_matrix_open"] is True for row in matrix_rows),
        "empty_evidence_missing_matrix_rows": sum(row["evidence_missing_matrix_empty"] is True for row in matrix_rows),
        "blocked_evidence_missing_matrix_rows": sum(row["evidence_missing_matrix_blocked"] is True for row in matrix_rows),
        "formal_intake_dry_run_executed_rows": 0,
        "formal_intake_dry_run_passed_rows": 0,
        "evidence_missing_matrix_status": (
            "open_empty_evidence_missing_matrix" if matrix_rows else "blocked_missing_owner_assignment_gap_audit"
        ),
        "p0_unblocked": False,
        "p0_completion_ready": False,
        "blocker": "P696 owner-assignment gap remains open and empty; required evidence is not available.",
        "policy": "P697 is a local evidence-missing matrix only; it does not receive or validate P0 evidence.",
        **zero_counts(),
        **{field: False for field in FALSE_FIELDS},
    }
    rows = matrix_rows + [summary]
    OUT_JSONL.write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )
    report = {
        "created_at": created_at,
        "local_only": True,
        "manifest_id": "P697",
        "source_jsonl": str(SOURCE_JSONL.relative_to(AI_ROOT)),
        "source_report": str(SOURCE_REPORT.relative_to(AI_ROOT)),
        "source_validation_report": str(SOURCE_VALIDATION.relative_to(AI_ROOT)),
        "source_owner_assignment_gap_rows": source_report.get("owner_assignment_gap_rows"),
        "source_p696_validation_success": source_validation.get("success"),
        "evidence_missing_matrix_rows": len(matrix_rows),
        "audit_rows": len(rows),
        "open_evidence_missing_matrix_rows": summary["open_evidence_missing_matrix_rows"],
        "empty_evidence_missing_matrix_rows": summary["empty_evidence_missing_matrix_rows"],
        "blocked_evidence_missing_matrix_rows": summary["blocked_evidence_missing_matrix_rows"],
        "formal_intake_dry_run_executed_rows": 0,
        "formal_intake_dry_run_passed_rows": 0,
        "evidence_missing_matrix_status": summary["evidence_missing_matrix_status"],
        "p0_unblocked": False,
        "p0_completion_ready": False,
        "artifact_jsonl": str(OUT_JSONL.relative_to(AI_ROOT)),
        "artifact_md": str(OUT_MD.relative_to(AI_ROOT)),
        "policy": "P697 binds source-bound evidence-missing rows; all evidence, input, and authorization gates remain fail-closed.",
        **zero_counts(),
        **{field: False for field in FALSE_FIELDS},
    }
    OUT_REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    lines = [
        "# P697 P0 real-input blocker escalation review evidence missing matrix",
        "",
        "Status: evidence-missing matrix is open and empty; no evidence has been received or validated.",
        "",
        f"- evidence_missing_matrix_rows: `{len(matrix_rows)}`",
        f"- open_evidence_missing_matrix_rows: `{summary['open_evidence_missing_matrix_rows']}`",
        f"- empty_evidence_missing_matrix_rows: `{summary['empty_evidence_missing_matrix_rows']}`",
        f"- blocked_evidence_missing_matrix_rows: `{summary['blocked_evidence_missing_matrix_rows']}`",
        "- evidence_received_rows: `0`",
        "- evidence_validated_rows: `0`",
        "- evidence_released_rows: `0`",
        "- evidence_promoted_to_decision_rows: `0`",
        "- response_received_rows: `0`",
        "- real_input_received_rows: `0`",
        "- p0_unblocked: `false`",
        "- release_ready: `false`",
        "",
        "| Order | Lane | Formal target | Status |",
        "|---:|---|---|---|",
    ]
    for row in matrix_rows:
        lines.append(
            f"| {row['evidence_missing_matrix_order']} | {row['lane']} | "
            f"`{row['formal_target_file']}` | `{row['evidence_missing_matrix_status']}` |"
        )
    lines.extend([
        "",
        "This matrix does not receive or validate evidence, release evidence, promote decisions, send escalation, acknowledge input, resolve blockers, approve closeout, execute intake, import labels, assert claims, release, or authorize production.",
    ])
    OUT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps({
        "evidence_missing_matrix_rows": len(matrix_rows),
        "open_evidence_missing_matrix_rows": summary["open_evidence_missing_matrix_rows"],
        "empty_evidence_missing_matrix_rows": summary["empty_evidence_missing_matrix_rows"],
        "blocked_evidence_missing_matrix_rows": summary["blocked_evidence_missing_matrix_rows"],
        "evidence_received_rows": 0,
        "evidence_validated_rows": 0,
        "response_received_rows": 0,
        "real_input_received_rows": 0,
        "p0_unblocked": False,
        "release_ready": False,
        "output": str(OUT_REPORT),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
