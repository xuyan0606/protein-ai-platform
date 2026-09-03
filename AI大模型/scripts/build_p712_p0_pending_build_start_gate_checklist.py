#!/usr/bin/env python3
"""Build P712 start-gate checklist from P711 wave plan."""
from __future__ import annotations
import json
from datetime import datetime,timezone
from pathlib import Path
from build_p700_p0_real_input_pending_build_checklist import load_jsonl
ROOT=Path(__file__).resolve().parents[1]; SOURCE=ROOT/"datasets/governance/p711_p0_pending_build_next_unlock_wave_plan.jsonl"; OUT=ROOT/"datasets/governance/p712_p0_pending_build_start_gate_checklist.jsonl"; REPORT=ROOT/"reports/p712_p0_pending_build_start_gate_checklist_report.json"; MD=ROOT/"reports/p712_p0_pending_build_start_gate_checklist.md"
def main():
 created=datetime.now(timezone.utc).isoformat(); src=[r for r in load_jsonl(SOURCE) if r.get("lane")!="summary"]; rows=[]
 for i,r in enumerate(src,1):
  rows.append({"start_gate_id":f"p712::{r.get('wave_plan_id')}","start_gate_order":i,"created_at":created,"lane":r.get("lane"),"source_p711_id":r.get("wave_plan_id"),"start_gate_status":"blocked_preflight_incomplete","input_present":False,"evidence_present":False,"owner_confirmed":False,"validator_ready":False,"authorization_present":False,"start_gate_passed":False,"execution_started":False,"formal_decision_ready":False,"blocker_reason":"All start-gate prerequisites are absent.","stop_condition":"Do not start until every prerequisite is independently evidenced.","policy":"P712 is a preflight checklist only; it does not start execution or authorize action."})
 summary={"start_gate_id":"p712::summary","start_gate_order":len(rows)+1,"created_at":created,"lane":"summary","start_gate_rows":len(rows),"start_gate_passed_rows":0,"execution_started_rows":0,"formal_decision_ready_rows":0,"policy":"P712 records blocked preflight only."}
 OUT.write_text("".join(json.dumps(x,ensure_ascii=False,sort_keys=True)+"\n" for x in rows+[summary]),encoding="utf-8"); report={"manifest_id":"P712","created_at":created,"local_only":True,"start_gate_rows":len(rows),"start_gate_passed_rows":0,"execution_started_rows":0,"formal_decision_ready_rows":0,"artifact_jsonl":str(OUT.relative_to(ROOT)),"artifact_md":str(MD.relative_to(ROOT)),"policy":"P712 is planning-only and fail-closed."}; REPORT.write_text(json.dumps(report,ensure_ascii=False,indent=2,sort_keys=True)+"\n",encoding="utf-8"); MD.write_text(f"# P712 pending-build start-gate checklist\n\nRows: `{len(rows)}`. Passed: `0`.\n",encoding="utf-8"); print(json.dumps({"manifest_id":"P712","start_gate_rows":len(rows),"start_gate_passed_rows":0,"output":str(REPORT)},ensure_ascii=False)); return 0
if __name__=="__main__": raise SystemExit(main())
