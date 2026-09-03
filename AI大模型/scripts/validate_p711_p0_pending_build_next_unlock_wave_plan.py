#!/usr/bin/env python3
"""Validate P711 next-unlock wave plan."""
from __future__ import annotations
import json
from datetime import datetime,timezone
from pathlib import Path
from build_p700_p0_real_input_pending_build_checklist import load_json,load_jsonl
ROOT=Path(__file__).resolve().parents[1]; BOARD=ROOT/"datasets/governance/p711_p0_pending_build_next_unlock_wave_plan.jsonl"; REPORT=ROOT/"reports/p711_p0_pending_build_next_unlock_wave_plan_report.json"; OUT=ROOT/"reports/p711_p0_pending_build_next_unlock_wave_plan_validation_report.json"
def main():
 rows=load_jsonl(BOARD); lanes=rows[:-1]; report=load_json(REPORT); failures=[]
 def f(c,x,o):
  if x: failures.append({"check":c,"observed":o})
 f("rows",len(lanes)!=5,len(lanes)); f("queued",report.get("queued_rows")!=5,report.get("queued_rows")); f("started",report.get("wave_started_rows")!=0,report.get("wave_started_rows")); f("execution",report.get("execution_started_rows")!=0,report.get("execution_started_rows"))
 for i,r in enumerate(lanes,1):
  f(f"row_{i}_status",r.get("wave_status")!="queued_blocked_pending_input",r.get("wave_status")); f(f"row_{i}_action",not r.get("next_action"),r.get("next_action")); f(f"row_{i}_started",r.get("wave_started") is not False,r.get("wave_started")); f(f"row_{i}_input",r.get("real_input_received") is not False,r.get("real_input_received")); f(f"row_{i}_execution",r.get("execution_started") is not False,r.get("execution_started"))
 result={"created_at":datetime.now(timezone.utc).isoformat(),"manifest_id":"P711","local_only":True,"success":not failures,"failure_count":len(failures),"failures":failures,"wave_plan_rows":len(lanes),"queued_rows":5,"wave_started_rows":0,"real_input_received_rows":0,"execution_started_rows":0,"formal_decision_ready_rows":0,"policy":"Validation only; P711 remains queued and fail-closed."}; OUT.write_text(json.dumps(result,ensure_ascii=False,indent=2,sort_keys=True)+"\n",encoding="utf-8"); print(json.dumps({"success":result["success"],"wave_plan_rows":len(lanes),"queued_rows":5,"failures":len(failures),"output":str(OUT)},ensure_ascii=False)); return 0 if not failures else 1
if __name__=="__main__": raise SystemExit(main())
