#!/usr/bin/env python3
"""Validate P710 terminal blocked rollup."""
from __future__ import annotations
import json
from datetime import datetime,timezone
from pathlib import Path
from build_p700_p0_real_input_pending_build_checklist import load_json,load_jsonl
ROOT=Path(__file__).resolve().parents[1]; BOARD=ROOT/"datasets/governance/p710_p0_pending_build_terminal_blocked_rollup.jsonl"; REPORT=ROOT/"reports/p710_p0_pending_build_terminal_blocked_rollup_report.json"; OUT=ROOT/"reports/p710_p0_pending_build_terminal_blocked_rollup_validation_report.json"
def main():
 rows=load_jsonl(BOARD); lanes=rows[:-1]; report=load_json(REPORT); failures=[]
 def f(c,x,o):
  if x: failures.append({"check":c,"observed":o})
 f("rows",len(lanes)!=10,len(lanes)); f("ready",report.get("total_ready_or_progress_count")!=0,report.get("total_ready_or_progress_count")); f("execution",report.get("execution_started_rows")!=0,report.get("execution_started_rows")); f("formal",report.get("formal_decision_ready_rows")!=0,report.get("formal_decision_ready_rows"))
 for i,r in enumerate(lanes,1): f(f"row_{i}_status",r.get("terminal_status")!="blocked_pending_build",r.get("terminal_status")); f(f"row_{i}_execution",r.get("execution_started") is not False,r.get("execution_started")); f(f"row_{i}_formal",r.get("formal_decision_ready") is not False,r.get("formal_decision_ready")); f(f"row_{i}_count",not isinstance(r.get("row_count"),int),r.get("row_count"))
 result={"created_at":datetime.now(timezone.utc).isoformat(),"manifest_id":"P710","local_only":True,"success":not failures,"failure_count":len(failures),"failures":failures,"rollup_rows":len(lanes),"total_ready_or_progress_count":0,"execution_started_rows":0,"formal_decision_ready_rows":0,"policy":"Validation only; P710 confirms terminal blocked state."}; OUT.write_text(json.dumps(result,ensure_ascii=False,indent=2,sort_keys=True)+"\n",encoding="utf-8"); print(json.dumps({"success":result["success"],"rollup_rows":len(lanes),"total_ready_or_progress_count":0,"failures":len(failures),"output":str(OUT)},ensure_ascii=False)); return 0 if not failures else 1
if __name__=="__main__": raise SystemExit(main())
