#!/usr/bin/env python3
"""Build P722 formal-decision write authorization gate from P721."""
from __future__ import annotations
import json
from datetime import datetime, timezone
from pathlib import Path

from build_p700_p0_real_input_pending_build_checklist import load_jsonl

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "datasets/governance/p721_p0_pending_build_formal_intake_non_write_guard_audit.jsonl"
OUT = ROOT / "datasets/governance/p722_p0_pending_build_formal_decision_write_authorization_gate.jsonl"
REPORT = ROOT / "reports/p722_p0_pending_build_formal_decision_write_authorization_gate_report.json"
MD = ROOT / "reports/p722_p0_pending_build_formal_decision_write_authorization_gate.md"


def main() -> int:
    created = datetime.now(timezone.utc).isoformat()
    source_rows = [row for row in load_jsonl(SOURCE) if row.get("lane") != "summary"]
    rows = []
    for order, source in enumerate(source_rows, 1):
        rows.append({
            "authorization_gate_id": f"p722::{source.get('non_write_guard_id')}",
            "authorization_gate_order": order,
            "created_at": created,
            "lane": source.get("lane"),
            "source_p721_id": source.get("non_write_guard_id"),
            "gate_status": "blocked_authorization_prerequisites_missing",
            "real_input_received": False,
            "evidence_validated": False,
            "owner_acknowledged": False,
            "decision_route_executed": False,
            "authorization_approved": False,
            "formal_decision_write_allowed": False,
            "formal_decision_written": False,
            "release_ready": False,
            "production_execution_allowed": False,
            "blocker_reason": "No qualifying input, validated evidence, owner acknowledgement, route result, or approval exists.",
            "operator_action": "Keep formal-decision write disabled; do not create a decision or authorization artifact.",
            "policy": "P722 is an authorization gate audit only; it does not approve, write, release, or execute.",
        })
    summary = {
        "authorization_gate_id": "p722::summary",
        "authorization_gate_order": len(rows) + 1,
        "created_at": created,
        "lane": "summary",
        "authorization_gate_rows": len(rows),
        "authorization_approved_rows": 0,
        "formal_decision_write_allowed_rows": 0,
        "formal_decision_written_rows": 0,
        "release_ready_rows": 0,
        "production_execution_allowed_rows": 0,
        "policy": "P722 confirms formal-decision writes remain disabled.",
    }
    OUT.write_text("".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows + [summary]), encoding="utf-8")
    report = {
        "manifest_id": "P722", "created_at": created, "local_only": True,
        "authorization_gate_rows": len(rows), "authorization_approved_rows": 0,
        "formal_decision_write_allowed_rows": 0, "formal_decision_written_rows": 0,
        "release_ready_rows": 0, "production_execution_allowed_rows": 0,
        "artifact_jsonl": str(OUT.relative_to(ROOT)), "artifact_md": str(MD.relative_to(ROOT)),
        "policy": "P722 is planning-only and fail-closed.",
    }
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    MD.write_text(f"# P722 formal-decision write authorization gate\n\nRows: `{len(rows)}`. Writes allowed: `0`.\n", encoding="utf-8")
    print(json.dumps({"manifest_id": "P722", "authorization_gate_rows": len(rows), "formal_decision_write_allowed_rows": 0, "output": str(REPORT)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
