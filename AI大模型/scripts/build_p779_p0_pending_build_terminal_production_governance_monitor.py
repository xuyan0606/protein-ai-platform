#!/usr/bin/env python3
"""Build P779 terminal production-governance monitor from P778."""
from __future__ import annotations
import json
from datetime import datetime, timezone
from pathlib import Path
from build_p700_p0_real_input_pending_build_checklist import load_jsonl
ROOT=Path(__file__).resolve().parents[1]; SOURCE=ROOT/"datasets/governance/p778_p0_pending_build_production_audit_closeout_reopen_gate.jsonl"; OUT=ROOT/"datasets/governance/p779_p0_pending_build_terminal_production_governance_monitor.jsonl"; REPORT=ROOT/"reports/p779_p0_pending_build_terminal_production_governance_monitor_report.json"; MD=ROOT/"reports/p779_p0_pending_build_terminal_production_governance_monitor.md"
FIELDS=("production_execution_allowed","production_execution_started","audit_receipt_present","sensitive_data_exposed","incident_active","closeout_approved","reopen_authorized","formal_decision_ready","release_ready")
def main():
 created=datetime.now(timezone.utc).isoformat(); src=[r for r in load_jsonl(SOURCE) if r.get("boundary")!="summary"]; rows=[]
 for i,s in enumerate(src,1):
  r={"monitor_id":f"p779::{s.get('closeout_gate_id')}","monitor_order":i,"created_at":created,"boundary":s.get("boundary"),"source_p778_id":s.get("closeout_gate_id"),"monitor_status":"terminal_production_blocked_under_observation","blocker_reason":"No production execution, audit receipt, disclosure incident, closeout, reopen, formal decision, or release state is unlocked.","operator_action":"Monitor only; do not infer progress, authorize transitions, or execute production work.","policy":"P779 is a read-only production-governance monitor; it performs no execution or authorization."}; r.update({f:False for f in FIELDS}); rows.append(r)
 zero={f+"_rows":0 for f in FIELDS}; summary={"monitor_id":"p779::summary","monitor_order":len(rows)+1,"created_at":created,"boundary":"summary","monitor_rows":len(rows),**zero,"policy":"P779 remains terminal and fail-closed."}; OUT.write_text("".join(json.dumps(r,ensure_ascii=False,sort_keys=True)+"\n" for r in rows+[summary]),encoding="utf-8"); report={"manifest_id":"P779","created_at":created,"local_only":True,"monitor_rows":len(rows),**zero,"artifact_jsonl":str(OUT.relative_to(ROOT)),"artifact_md":str(MD.relative_to(ROOT)),"policy":"P779 is monitoring-only and fail-closed."}; REPORT.write_text(json.dumps(report,ensure_ascii=False,indent=2,sort_keys=True)+"\n",encoding="utf-8"); MD.write_text(f"# P779 terminal production-governance monitor\n\nRows: `{len(rows)}`. Unblocked production states: `0`.\n",encoding="utf-8"); print(json.dumps({"manifest_id":"P779","monitor_rows":len(rows),"production_execution_allowed_rows":0,"output":str(REPORT)},ensure_ascii=False)); return 0
if __name__=='__main__': raise SystemExit(main())
