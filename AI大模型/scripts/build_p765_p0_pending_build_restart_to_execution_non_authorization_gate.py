#!/usr/bin/env python3
"""Build P765 restart-to-execution non-authorization gates from P764."""
from __future__ import annotations
import json
from datetime import datetime, timezone
from pathlib import Path
from build_p700_p0_real_input_pending_build_checklist import load_jsonl
ROOT=Path(__file__).resolve().parents[1]; SOURCE=ROOT/"datasets/governance/p764_p0_pending_build_receipt_to_restart_nonpromotion_gate.jsonl"; OUT=ROOT/"datasets/governance/p765_p0_pending_build_restart_to_execution_non_authorization_gate.jsonl"; REPORT=ROOT/"reports/p765_p0_pending_build_restart_to_execution_non_authorization_gate_report.json"; MD=ROOT/"reports/p765_p0_pending_build_restart_to_execution_non_authorization_gate.md"
FIELDS=("restart_authorized","execution_window_defined","operator_confirmed","start_receipt_contract_ready","execution_start_requested","execution_started","real_input_received","formal_decision_ready","production_execution_allowed")
def main()->int:
 created=datetime.now(timezone.utc).isoformat(); src=[r for r in load_jsonl(SOURCE) if r.get("boundary")!="summary"]; rows=[]
 for i,s in enumerate(src,1):
  r={"execution_gate_id":f"p765::{s.get('promotion_gate_id')}","execution_gate_order":i,"created_at":created,"boundary":s.get("boundary"),"source_p764_id":s.get("promotion_gate_id"),"gate_status":"empty_no_authorized_restart_to_execute","blocker_reason":"No validated restart authorization, execution window, operator confirmation, or start receipt contract exists.","operator_action":"Do not request, start, or simulate execution for any model, data, inference, or evaluation workflow.","policy":"P765 is an execution non-authorization gate only; it performs no restart or execution."}; r.update({f:False for f in FIELDS}); rows.append(r)
 zero={f+"_rows":0 for f in FIELDS}; summary={"execution_gate_id":"p765::summary","execution_gate_order":len(rows)+1,"created_at":created,"boundary":"summary","execution_gate_rows":len(rows),**zero,"policy":"P765 remains empty and fail-closed."}; OUT.write_text("".join(json.dumps(r,ensure_ascii=False,sort_keys=True)+"\n" for r in rows+[summary]),encoding="utf-8"); report={"manifest_id":"P765","created_at":created,"local_only":True,"execution_gate_rows":len(rows),**zero,"artifact_jsonl":str(OUT.relative_to(ROOT)),"artifact_md":str(MD.relative_to(ROOT)),"policy":"P765 is planning-only and fail-closed."}; REPORT.write_text(json.dumps(report,ensure_ascii=False,indent=2,sort_keys=True)+"\n",encoding="utf-8"); MD.write_text(f"# P765 restart-to-execution non-authorization gate\n\nRows: `{len(rows)}`. Execution started: `0`.\n",encoding="utf-8"); print(json.dumps({"manifest_id":"P765","execution_gate_rows":len(rows),"execution_started_rows":0,"output":str(REPORT)},ensure_ascii=False)); return 0
if __name__=='__main__': raise SystemExit(main())
