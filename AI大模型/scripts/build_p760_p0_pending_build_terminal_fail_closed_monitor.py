#!/usr/bin/env python3
"""Build P760 terminal fail-closed monitor from P759."""
from __future__ import annotations
import json
from datetime import datetime, timezone
from pathlib import Path
from build_p700_p0_real_input_pending_build_checklist import load_jsonl
ROOT = Path(__file__).resolve().parents[1]; SOURCE = ROOT / "datasets/governance/p759_p0_pending_build_incident_closeout_reopen_gate.jsonl"; OUT = ROOT / "datasets/governance/p760_p0_pending_build_terminal_fail_closed_monitor.jsonl"; REPORT = ROOT / "reports/p760_p0_pending_build_terminal_fail_closed_monitor_report.json"; MD = ROOT / "reports/p760_p0_pending_build_terminal_fail_closed_monitor.md"
FIELDS = ("execution_started", "real_input_received", "evidence_validated", "formal_decision_ready", "authorization_granted", "release_ready", "production_execution_allowed", "incident_active", "restart_authorized")
def main() -> int:
    created = datetime.now(timezone.utc).isoformat(); source = [r for r in load_jsonl(SOURCE) if r.get("boundary") != "summary"]; rows = []
    for order, src in enumerate(source, 1):
        row = {"monitor_id": f"p760::{src.get('closeout_gate_id')}", "monitor_order": order, "created_at": created, "boundary": src.get("boundary"), "source_p759_id": src.get("closeout_gate_id"), "monitor_status": "terminal_blocked_under_observation", "blocker_reason": "No verified input, evidence, decision, authorization, release, production execution, or incident restart exists.", "operator_action": "Continue monitoring only; require real external evidence and explicit authorization before any transition.", "policy": "P760 is a read-only terminal monitor; it performs no execution, decision, release, or restart."}
        row.update({field: False for field in FIELDS}); rows.append(row)
    zero = {f"{field}_rows": 0 for field in FIELDS}; summary = {"monitor_id": "p760::summary", "monitor_order": len(rows) + 1, "created_at": created, "boundary": "summary", "monitor_rows": len(rows), **zero, "policy": "P760 remains terminal and fail-closed."}
    OUT.write_text("".join(json.dumps(r, ensure_ascii=False, sort_keys=True) + "\n" for r in rows + [summary]), encoding="utf-8"); report = {"manifest_id": "P760", "created_at": created, "local_only": True, "monitor_rows": len(rows), **zero, "artifact_jsonl": str(OUT.relative_to(ROOT)), "artifact_md": str(MD.relative_to(ROOT)), "policy": "P760 is monitoring-only and fail-closed."}; REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8"); MD.write_text(f"# P760 terminal fail-closed monitor\n\nRows: `{len(rows)}`. Any unlocked terminal state: `0`.\n", encoding="utf-8"); print(json.dumps({"manifest_id": "P760", "monitor_rows": len(rows), "formal_decision_ready_rows": 0, "production_execution_allowed_rows": 0, "output": str(REPORT)}, ensure_ascii=False)); return 0
if __name__ == "__main__": raise SystemExit(main())
