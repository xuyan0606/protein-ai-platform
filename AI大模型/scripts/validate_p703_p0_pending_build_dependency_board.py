#!/usr/bin/env python3
"""Validate P703 planning dependency board."""
from __future__ import annotations
import json
from datetime import datetime, timezone
from pathlib import Path
from build_p700_p0_real_input_pending_build_checklist import load_json,load_jsonl
ROOT=Path(__file__).resolve().parents[1]; BOARD=ROOT/"datasets/governance/p703_p0_pending_build_dependency_board.jsonl"; REPORT=ROOT/"reports/p703_p0_pending_build_dependency_board_report.json"; OUT=ROOT/"reports/p703_p0_pending_build_dependency_board_validation_report.json"
def main():
 rows=load_jsonl(BOARD); lanes=rows[:-1]; report=load_json(REPORT); failures=[]
 def f(c,x,o):
  if x: failures.append({"check":c,"observed":o})
 f("rows",len(lanes)!=15,len(lanes)); f("started",report.get("dependency_started_rows")!=15,report.get("dependency_started_rows")); f("satisfied",report.get("dependency_satisfied_rows")!=0,report.get("dependency_satisfied_rows")); f("execution",report.get("execution_started_rows")!=0,report.get("execution_started_rows"))
 for i,r in enumerate(lanes,1): f(f"row_{i}_blocked",r.get("dependency_status")!="blocked_pending_dependency",r.get("dependency_status")); f(f"row_{i}_unsatisfied",r.get("dependency_satisfied") is not False,r.get("dependency_satisfied")); f(f"row_{i}_execution",r.get("execution_started") is not False,r.get("execution_started")); f(f"row_{i}_prerequisite",not r.get("prerequisite"),r.get("prerequisite"))
 result={"created_at":datetime.now(timezone.utc).isoformat(),"manifest_id":"P703","local_only":True,"success":not failures,"failure_count":len(failures),"failures":failures,"dependency_board_rows":len(lanes),"dependency_started_rows":sum(r.get("dependency_started") is True for r in lanes),"dependency_satisfied_rows":sum(r.get("dependency_satisfied") is True for r in lanes),"execution_started_rows":0,"formal_decision_ready_rows":0,"policy":"Validation only; P703 remains blocked and planning-only."}; OUT.write_text(json.dumps(result,ensure_ascii=False,indent=2,sort_keys=True)+"\n",encoding="utf-8"); print(json.dumps({"success":result["success"],"dependency_board_rows":len(lanes),"dependency_satisfied_rows":0,"failures":len(failures),"output":str(OUT)},ensure_ascii=False)); return 0 if not failures else 1
if __name__=="__main__": raise SystemExit(main())
