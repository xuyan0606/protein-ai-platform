#!/usr/bin/env python3
"""Build the P698 fail-closed formal-decision readiness false-positive guard."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
SOURCE_JSONL = AI_ROOT / "datasets/governance/p697_p0_real_input_blocker_escalation_review_evidence_missing_matrix.jsonl"
SOURCE_REPORT = AI_ROOT / "reports/p697_p0_real_input_blocker_escalation_review_evidence_missing_matrix_report.json"
SOURCE_VALIDATION = AI_ROOT / "reports/p697_p0_real_input_blocker_escalation_review_evidence_missing_matrix_validation_report.json"
OUT_JSONL = AI_ROOT / "datasets/governance/p698_p0_real_input_formal_decision_readiness_false_positive_guard.jsonl"
OUT_REPORT = AI_ROOT / "reports/p698_p0_real_input_formal_decision_readiness_false_positive_guard_report.json"
OUT_MD = AI_ROOT / "reports/p698_p0_real_input_formal_decision_readiness_false_positive_guard.md"

FALSE_FIELDS = (
    "queue_dequeued",
    "operator_dispatch_sent",
    "operator_acknowledged",
    "owner_assigned",
    "owner_acknowledged",
    "external_input_acknowledged",
    "receive_preflight_executed",
    "response_payload_present",
    "response_received",
    "response_validated",
    "real_input_received",
    "evidence_payload_present",
    "evidence_received",
    "evidence_validated",
    "evidence_quarantined",
    "evidence_released",
    "evidence_promoted_to_decision",
    "decision_route_executed",
    "routed_to_formal_review",
    "formal_intake_dry_run_executed",
    "formal_intake_dry_run_passed",
    "formal_validator_passed",
    "reviewed_decision_written",
    "formal_intake_written",
    "runtime_receipt_written",
    "training_label_written",
    "formal_decision_ready",
    "false_positive_cleared",
    "aging_reviewed",
    "staleness_resolved",
    "escalation_reviewed",
    "escalation_sent",
    "escalation_acknowledged",
    "blocker_resolved",
    "closeout_ready",
    "completion_ready_observed",
    "completion_ready",
    "p0_unblocked",
    "p0_completion_ready",
    "training_import_allowed",
    "safe_for_training_import",
    "safe_for_model_claim",
    "customer_delivery_ready",
    "release_ready",
    "production_execution_allowed",
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
        "formal_decision_false_positive_guard_id": f"p698::{source.get('lane')}",
        "formal_decision_false_positive_guard_order": order,
        "created_at": created_at,
        "source_evidence_missing_matrix_id": source.get("evidence_missing_matrix_id"),
        "source_p697_validation_success": True,
        "formal_decision_false_positive_guard_status": (
            "open_empty_formal_decision_readiness_false_positive_guard"
        ),
        "formal_decision_false_positive_guard_open": True,
        "formal_decision_false_positive_guard_empty": True,
        "formal_decision_false_positive_guard_blocked": True,
        "formal_decision_false_positive_reason": (
            "No validated real input or evidence exists; formal decision readiness must not be "
            "inferred from empty control-plane artifacts."
        ),
        "formal_decision_false_positive_note": (
            "P698 records a readiness false-positive guard only. It does not write a formal "
            "decision, perform intake, create a runtime receipt, or clear any gate."
        ),
        "policy": (
            "P698 is a local fail-closed formal-decision readiness guard. It does not receive "
            "responses or evidence, perform review, write formal intake or decisions, create "
            "receipts or labels, resolve blockers, approve closeout, or authorize training, "
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
    source_rows.sort(key=lambda row: int(row.get("evidence_missing_matrix_order") or 0))
    guard_rows = [build_row(row, index, created_at) for index, row in enumerate(source_rows, start=1)]
    summary = {
        "formal_decision_false_positive_guard_id": "p698::summary",
        "formal_decision_false_positive_guard_order": len(guard_rows) + 1,
        "created_at": created_at,
        "local_only": True,
        "lane": "summary",
        "source_evidence_missing_matrix_rows": source_report.get("evidence_missing_matrix_rows"),
        "source_p697_validation_success": source_validation.get("success"),
        "formal_decision_false_positive_guard_rows": len(guard_rows),
        "open_formal_decision_false_positive_guard_rows": len(guard_rows),
        "empty_formal_decision_false_positive_guard_rows": len(guard_rows),
        "blocked_formal_decision_false_positive_guard_rows": len(guard_rows),
        "formal_decision_false_positive_guard_status": (
            "open_empty_formal_decision_readiness_false_positive_guard"
        ),
        "formal_intake_dry_run_executed_rows": 0,
        "formal_intake_dry_run_passed_rows": 0,
        "p0_unblocked": False,
        "p0_completion_ready": False,
        "blocker": (
            "P697 evidence-missing matrix remains open and empty; formal decision readiness "
            "cannot be inferred."
        ),
        "policy": "P698 is a local false-positive guard only; all formal decision and authorization gates remain fail-closed.",
        **zero_counts(),
        **{field: False for field in FALSE_FIELDS},
    }
    rows = guard_rows + [summary]
    OUT_JSONL.write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )
    report = {
        "created_at": created_at,
        "local_only": True,
        "manifest_id": "P698",
        "source_jsonl": str(SOURCE_JSONL.relative_to(AI_ROOT)),
        "source_report": str(SOURCE_REPORT.relative_to(AI_ROOT)),
        "source_validation_report": str(SOURCE_VALIDATION.relative_to(AI_ROOT)),
        "source_evidence_missing_matrix_rows": source_report.get("evidence_missing_matrix_rows"),
        "source_p697_validation_success": source_validation.get("success"),
        "formal_decision_false_positive_guard_rows": len(guard_rows),
        "audit_rows": len(rows),
        "open_formal_decision_false_positive_guard_rows": len(guard_rows),
        "empty_formal_decision_false_positive_guard_rows": len(guard_rows),
        "blocked_formal_decision_false_positive_guard_rows": len(guard_rows),
        "formal_decision_false_positive_guard_status": (
            "open_empty_formal_decision_readiness_false_positive_guard"
        ),
        "formal_intake_dry_run_executed_rows": 0,
        "formal_intake_dry_run_passed_rows": 0,
        "p0_unblocked": False,
        "p0_completion_ready": False,
        "artifact_jsonl": str(OUT_JSONL.relative_to(AI_ROOT)),
        "artifact_md": str(OUT_MD.relative_to(AI_ROOT)),
        "policy": "P698 binds source-bound readiness guard rows; formal decision and authorization gates remain fail-closed.",
        **zero_counts(),
        **{field: False for field in FALSE_FIELDS},
    }
    OUT_REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    lines = [
        "# P698 P0 real-input formal decision readiness false-positive guard",
        "",
        "Status: formal decision readiness remains open, empty, and blocked; no formal decision is ready.",
        "",
        f"- formal_decision_false_positive_guard_rows: `{len(guard_rows)}`",
        f"- open_formal_decision_false_positive_guard_rows: `{len(guard_rows)}`",
        f"- empty_formal_decision_false_positive_guard_rows: `{len(guard_rows)}`",
        f"- blocked_formal_decision_false_positive_guard_rows: `{len(guard_rows)}`",
        "",
        "This artifact is a local guard only. It is not a formal decision, acknowledgement, formal intake, runtime receipt, training label, release approval, or production authorization.",
    ]
    OUT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps({
        "manifest_id": "P698",
        "formal_decision_false_positive_guard_rows": len(guard_rows),
        "open_formal_decision_false_positive_guard_rows": len(guard_rows),
        "empty_formal_decision_false_positive_guard_rows": len(guard_rows),
        "response_received_rows": 0,
        "formal_decision_ready_rows": 0,
        "output": str(OUT_REPORT),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
