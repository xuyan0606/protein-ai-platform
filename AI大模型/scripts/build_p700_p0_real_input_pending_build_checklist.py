#!/usr/bin/env python3
"""Build the P700 fail-closed pending-build checklist from P699."""
from __future__ import annotations
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from build_p699_p0_real_input_formal_decision_readiness_status_board import load_json, load_jsonl

AI_ROOT = Path(__file__).resolve().parents[1]
SOURCE = AI_ROOT / "datasets/governance/p699_p0_real_input_formal_decision_readiness_status_board.jsonl"
SOURCE_REPORT = AI_ROOT / "reports/p699_p0_real_input_formal_decision_readiness_status_board_report.json"
SOURCE_VALIDATION = AI_ROOT / "reports/p699_p0_real_input_formal_decision_readiness_status_board_validation_report.json"
OUT = AI_ROOT / "datasets/governance/p700_p0_real_input_pending_build_checklist.jsonl"
REPORT = AI_ROOT / "reports/p700_p0_real_input_pending_build_checklist_report.json"
MD = AI_ROOT / "reports/p700_p0_real_input_pending_build_checklist.md"

FALSE_FIELDS = (
    "pending_build_started", "pending_build_completed", "real_input_received",
    "evidence_received", "formal_decision_written", "formal_decision_ready",
    "training_import_allowed", "safe_for_model_claim", "customer_delivery_ready",
    "release_ready", "production_execution_allowed", "p0_unblocked", "p0_completion_ready",
)

def main() -> int:
    created = datetime.now(timezone.utc).isoformat()
    source_rows = [r for r in load_jsonl(SOURCE) if r.get("lane") != "summary"]
    source_rows.sort(key=lambda r: int(r.get("formal_decision_readiness_status_board_order") or 0))
    rows: list[dict[str, Any]] = []
    for order, source in enumerate(source_rows, 1):
        row = {
            "pending_build_checklist_id": f"p700::{source.get('lane')}",
            "pending_build_checklist_order": order,
            "created_at": created,
            "lane": source.get("lane"),
            "source_p699_status_board_id": source.get("formal_decision_readiness_status_board_id"),
            "source_p699_validation_success": True,
            "pending_build_status": "pending_open_empty_blocked",
            "pending_build_open": True,
            "pending_build_empty": True,
            "pending_build_blocked": True,
            "pending_build_item": f"Build and validate the {source.get('lane')} formal-decision readiness lane after real input arrives.",
            "blocker_reason": source.get("blocker_reason") or "Required real input and evidence are absent.",
            "next_unblocking_evidence": source.get("next_unblocking_evidence") or "Externally supplied real input and independently verifiable evidence.",
            "completion_condition": "Only after real input, evidence validation, formal review, and explicit authorization are independently recorded.",
            "operator_action": "Keep pending; do not execute, approve, label, release, deliver, or authorize.",
            "policy": "P700 is a local pending-build checklist only; all formal decision and authorization gates remain fail-closed.",
        }
        row.update({field: False for field in FALSE_FIELDS})
        rows.append(row)
    summary = {
        "pending_build_checklist_id": "p700::summary", "pending_build_checklist_order": len(rows) + 1,
        "created_at": created, "lane": "summary", "local_only": True,
        "source_p699_validation_success": load_json(SOURCE_VALIDATION).get("success"),
        "pending_build_checklist_rows": len(rows), "open_pending_build_rows": len(rows),
        "empty_pending_build_rows": len(rows), "blocked_pending_build_rows": len(rows),
        "pending_build_status": "pending_open_empty_blocked", "formal_intake_dry_run_executed_rows": 0,
        "formal_intake_dry_run_passed_rows": 0, "pending_build_ready": False, "pending_build_ready_rows": 0, "policy": "P700 records pending work only; no execution or authorization is performed.",
    }
    summary.update({field: False for field in FALSE_FIELDS})
    OUT.write_text("".join(json.dumps(r, ensure_ascii=False, sort_keys=True) + "\n" for r in rows + [summary]), encoding="utf-8")
    report = {
        "manifest_id": "P700", "created_at": created, "local_only": True,
        "source_jsonl": str(SOURCE.relative_to(AI_ROOT)), "source_report": str(SOURCE_REPORT.relative_to(AI_ROOT)),
        "source_validation_report": str(SOURCE_VALIDATION.relative_to(AI_ROOT)), "pending_build_checklist_rows": len(rows),
        "audit_rows": len(rows) + 1, "open_pending_build_rows": len(rows), "empty_pending_build_rows": len(rows),
        "blocked_pending_build_rows": len(rows), "pending_build_status": "pending_open_empty_blocked",
        "formal_intake_dry_run_executed_rows": 0, "formal_intake_dry_run_passed_rows": 0, "pending_build_ready": False, "pending_build_ready_rows": 0,
        "artifact_jsonl": str(OUT.relative_to(AI_ROOT)), "artifact_md": str(MD.relative_to(AI_ROOT)),
        "policy": "P700 is a local pending-build checklist only; formal decision and authorization remain fail-closed.",
    }
    report.update({field: False for field in FALSE_FIELDS})
    report.update({f"{field}_rows": 0 for field in FALSE_FIELDS})
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    MD.write_text(f"# P700 P0 real-input pending-build checklist\n\nStatus: pending, open, empty, and blocked.\n\n- pending_build_checklist_rows: `{len(rows)}`\n- No execution, formal decision, approval, release, delivery, or production authorization is performed.\n", encoding="utf-8")
    print(json.dumps({"manifest_id": "P700", "pending_build_checklist_rows": len(rows), "pending_build_ready_rows": 0, "output": str(REPORT)}, ensure_ascii=False))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
