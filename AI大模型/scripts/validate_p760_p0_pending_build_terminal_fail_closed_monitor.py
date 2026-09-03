#!/usr/bin/env python3
"""Validate P760 terminal fail-closed monitor."""
from __future__ import annotations
import json
from datetime import datetime, timezone
from pathlib import Path
from build_p700_p0_real_input_pending_build_checklist import load_json, load_jsonl
ROOT = Path(__file__).resolve().parents[1]; SOURCE = ROOT / "datasets/governance/p759_p0_pending_build_incident_closeout_reopen_gate.jsonl"; BOARD = ROOT / "datasets/governance/p760_p0_pending_build_terminal_fail_closed_monitor.jsonl"; REPORT = ROOT / "reports/p760_p0_pending_build_terminal_fail_closed_monitor_report.json"; OUT = ROOT / "reports/p760_p0_pending_build_terminal_fail_closed_monitor_validation_report.json"
FIELDS = ("execution_started", "real_input_received", "evidence_validated", "formal_decision_ready", "authorization_granted", "release_ready", "production_execution_allowed", "incident_active", "restart_authorized")
def main() -> int:
    source = [r for r in load_jsonl(SOURCE) if r.get("boundary") != "summary"]; rows = load_jsonl(BOARD); monitors = rows[:-1] if rows else []; summary = rows[-1] if rows else {}; report = load_json(REPORT); failures = []
    def fail(c, x, o, e):
        if x: failures.append({"check": c, "observed": o, "expected": e})
    fail("source_rows", len(source) != 5, len(source), 5); fail("monitor_rows", len(monitors) != 5, len(monitors), 5); fail("summary", summary.get("boundary") != "summary", summary.get("boundary"), "summary"); fail("coverage", {r.get("source_p759_id") for r in monitors} != {r.get("closeout_gate_id") for r in source}, "mismatch", "exact")
    for field in FIELDS: fail(field, report.get(f"{field}_rows") != 0, report.get(f"{field}_rows"), 0)
    for i, row in enumerate(monitors, 1):
        fail(f"row_{i}_status", row.get("monitor_status") != "terminal_blocked_under_observation", row.get("monitor_status"), "terminal_blocked_under_observation")
        for field in FIELDS: fail(f"row_{i}_{field}", row.get(field) is not False, row.get(field), False)
    result = {"created_at": datetime.now(timezone.utc).isoformat(), "manifest_id": "P760", "local_only": True, "success": not failures, "failure_count": len(failures), "failures": failures, "monitor_rows": len(monitors), **{f"{field}_rows": 0 for field in FIELDS}, "policy": "Validation only; P760 confirms terminal fail-closed state."}
    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8"); print(json.dumps({"success": result["success"], "monitor_rows": len(monitors), "formal_decision_ready_rows": 0, "production_execution_allowed_rows": 0, "failures": len(failures), "output": str(OUT)}, ensure_ascii=False)); return 0 if not failures else 1
if __name__ == "__main__": raise SystemExit(main())
