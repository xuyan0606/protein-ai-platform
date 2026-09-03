#!/usr/bin/env python3
"""Build P761 terminal restart prerequisite gates from P760."""
from __future__ import annotations
import json
from datetime import datetime, timezone
from pathlib import Path
from build_p700_p0_real_input_pending_build_checklist import load_jsonl
ROOT=Path(__file__).resolve().parents[1]; SOURCE=ROOT/"datasets/governance/p760_p0_pending_build_terminal_fail_closed_monitor.jsonl"; OUT=ROOT/"datasets/governance/p761_p0_pending_build_terminal_restart_prerequisite_gate.jsonl"; REPORT=ROOT/"reports/p761_p0_pending_build_terminal_restart_prerequisite_gate_report.json"; MD=ROOT/"reports/p761_p0_pending_build_terminal_restart_prerequisite_gate.md"
FIELDS=("real_input_received","evidence_validated","owner_confirmed","validator_passed","restart_requested","restart_authorized","work_restarted","formal_decision_ready","production_execution_allowed")
def main()->int:
    created=datetime.now(timezone.utc).isoformat(); src=[r for r in load_jsonl(SOURCE) if r.get("boundary")!="summary"]; rows=[]
    for i,s in enumerate(src,1):
        r={"restart_gate_id":f"p761::{s.get('monitor_id')}","restart_gate_order":i,"created_at":created,"boundary":s.get("boundary"),"source_p760_id":s.get("monitor_id"),"gate_status":"blocked_missing_restart_prerequisites","blocker_reason":"Real input, evidence, owner confirmation, validator success, and explicit authorization are absent.","operator_action":"Keep work stopped; do not request, authorize, or restart any workflow.","policy":"P761 is a prerequisite register only; it performs no restart or execution."}; r.update({f:False for f in FIELDS}); rows.append(r)
    zero={f+"_rows":0 for f in FIELDS}; summary={"restart_gate_id":"p761::summary","restart_gate_order":len(rows)+1,"created_at":created,"boundary":"summary","restart_gate_rows":len(rows),**zero,"policy":"P761 remains blocked and fail-closed."}; OUT.write_text("".join(json.dumps(r,ensure_ascii=False,sort_keys=True)+"\n" for r in rows+[summary]),encoding="utf-8"); report={"manifest_id":"P761","created_at":created,"local_only":True,"restart_gate_rows":len(rows),**zero,"artifact_jsonl":str(OUT.relative_to(ROOT)),"artifact_md":str(MD.relative_to(ROOT)),"policy":"P761 is planning-only and fail-closed."}; REPORT.write_text(json.dumps(report,ensure_ascii=False,indent=2,sort_keys=True)+"\n",encoding="utf-8"); MD.write_text(f"# P761 terminal restart prerequisite gate\n\nRows: `{len(rows)}`. Restart authorized: `0`.\n",encoding="utf-8"); print(json.dumps({"manifest_id":"P761","restart_gate_rows":len(rows),"restart_authorized_rows":0,"output":str(REPORT)},ensure_ascii=False)); return 0
if __name__=='__main__': raise SystemExit(main())
