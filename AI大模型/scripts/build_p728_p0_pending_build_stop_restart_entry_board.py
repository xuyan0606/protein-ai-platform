#!/usr/bin/env python3
"""Build P728 unified stop/restart entry board from P727."""
from __future__ import annotations
import json
from datetime import datetime, timezone
from pathlib import Path
from build_p700_p0_real_input_pending_build_checklist import load_jsonl

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "datasets/governance/p727_p0_pending_build_terminal_non_authorization_rollup.jsonl"
OUT = ROOT / "datasets/governance/p728_p0_pending_build_stop_restart_entry_board.jsonl"
REPORT = ROOT / "reports/p728_p0_pending_build_stop_restart_entry_board_report.json"
MD = ROOT / "reports/p728_p0_pending_build_stop_restart_entry_board.md"


def main() -> int:
    created = datetime.now(timezone.utc).isoformat()
    source_rows = [row for row in load_jsonl(SOURCE) if row.get("boundary") != "summary"]
    rows = []
    for order, source in enumerate(source_rows, 1):
        rows.append({
            "stop_restart_id": f"p728::{source.get('terminal_rollup_id')}",
            "stop_restart_order": order,
            "created_at": created,
            "boundary": source.get("boundary"),
            "source_p727_id": source.get("terminal_rollup_id"),
            "state": "blocked_stop_required",
            "stop_condition_active": True,
            "restart_entry_defined": True,
            "restart_trigger_received": False,
            "restart_trigger_validated": False,
            "restart_authorized": False,
            "work_restarted": False,
            "formal_decision_ready": False,
            "release_ready": False,
            "production_execution_allowed": False,
            "required_restart_evidence": "Real external input, provenance-bearing evidence, owner acknowledgement, validator success, and explicit authorization.",
            "operator_action": "Stop and wait; do not restart from internal drafts, templates, or inferred signals.",
            "policy": "P728 defines a stop/restart entry only; it does not restart work or authorize downstream actions.",
        })
    summary = {
        "stop_restart_id": "p728::summary", "stop_restart_order": len(rows) + 1,
        "created_at": created, "boundary": "summary", "stop_restart_rows": len(rows),
        "stop_condition_active_rows": len(rows), "restart_trigger_received_rows": 0,
        "restart_trigger_validated_rows": 0, "restart_authorized_rows": 0,
        "work_restarted_rows": 0, "formal_decision_ready_rows": 0,
        "release_ready_rows": 0, "production_execution_allowed_rows": 0,
        "policy": "P728 confirms stop remains active until valid external evidence arrives.",
    }
    OUT.write_text("".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows + [summary]), encoding="utf-8")
    report = {
        "manifest_id": "P728", "created_at": created, "local_only": True,
        "stop_restart_rows": len(rows), "stop_condition_active_rows": len(rows),
        "restart_trigger_received_rows": 0, "restart_trigger_validated_rows": 0,
        "restart_authorized_rows": 0, "work_restarted_rows": 0,
        "formal_decision_ready_rows": 0, "release_ready_rows": 0,
        "production_execution_allowed_rows": 0, "artifact_jsonl": str(OUT.relative_to(ROOT)),
        "artifact_md": str(MD.relative_to(ROOT)), "policy": "P728 is planning-only and fail-closed.",
    }
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    MD.write_text(f"# P728 stop/restart entry board\n\nBoundaries: `{len(rows)}`. Stop active: `{len(rows)}`. Restarted: `0`.\n", encoding="utf-8")
    print(json.dumps({"manifest_id": "P728", "stop_restart_rows": len(rows), "restart_authorized_rows": 0, "output": str(REPORT)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
