#!/usr/bin/env python3
"""Validate P712 start-gate checklist."""
from __future__ import annotations
import json
from datetime import datetime,timezone
from pathlib import Path
from build_p700_p0_real_input_pending_build_checklist import load_json,load_jsonl
ROOT=Path(__file__).resolve().parents[1]; BOARD=ROOT/"datasets/governance/p712_p0_pending_build_start_gate_checklist.jsonl"; REPORT=ROOT/"reports/p712_p0_pending_build_start_gate_checklist_report.json"; OUT=ROOT/"reports/p712_p0_pending_build_start_gate_checklist_validation_report.json"
def main():
 rows=load_jsonl(BOARD); lanes=rows[:-1]; report=load_json(REPORT); failures=[]
 def f(c,x,o):
  if x: failures.append({"check":c,"observed":o})
 f("rows",len(lanes)!=5,len(lanes)); f("passed",report.get("start_gate_passed_rows")!=0,report.get("start_gate_passed_rows")); f("execution",report.get("execution_started_rows")!=0,report.get("execution_started_rows"))
 for i,r in enumerate(lanes,1):
  for k in ("input_present","evidence_present","owner_confirmed","validator_ready","authorization_present","start_gate_passed","execution_started","formal_decision_ready"): f(f"row_{i}_{k}",r.get(k) is not False,r.get(k))
  f(f"row_{i}_status",r.get("start_gate_status")!="blocked_preflight_incomplete",r.get("start_gate_status"))
 result={"created_at":datetime.now(timezone.utc).isoformat(),"manifest_id":"P712","local_only":True,"success":not failures,"failure_count":len(failures),"failures":failures,"start_gate_rows":len(lanes),"start_gate_passed_rows":0,"execution_started_rows":0,"formal_decision_ready_rows":0,"policy":"Validation only; P712 remains blocked and fail-closed."}; OUT.write_text(json.dumps(result,ensure_ascii=False,indent=2,sort_keys=True)+"\n",encoding="utf-8"); print(json.dumps({"success":result["success"],"start_gate_rows":len(lanes),"start_gate_passed_rows":0,"failures":len(failures),"output":str(OUT)},ensure_ascii=False)); return 0 if not failures else 1
if __name__=="__main__": raise SystemExit(main())
