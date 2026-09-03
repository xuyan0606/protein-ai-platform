#!/usr/bin/env python3
"""Validate P709 completion-observation board."""
from __future__ import annotations
import json
from datetime import datetime,timezone
from pathlib import Path
from build_p700_p0_real_input_pending_build_checklist import load_json,load_jsonl
ROOT=Path(__file__).resolve().parents[1]; BOARD=ROOT/"datasets/governance/p709_p0_pending_build_completion_observation_board.jsonl"; REPORT=ROOT/"reports/p709_p0_pending_build_completion_observation_board_report.json"; OUT=ROOT/"reports/p709_p0_pending_build_completion_observation_board_validation_report.json"
def main():
 rows=load_jsonl(BOARD); lanes=rows[:-1]; report=load_json(REPORT); failures=[]
 def f(c,x,o):
  if x: failures.append({"check":c,"observed":o})
 f("rows",len(lanes)!=15,len(lanes))
 for k in ("completion_ready_observed_rows","closeout_ready_rows","formal_review_ready_rows","completion_ready_rows","blocker_resolved_rows","execution_started_rows","formal_decision_ready_rows"): f(k,report.get(k)!=0,report.get(k))
 for i,r in enumerate(lanes,1):
  for k in ("completion_ready_observed","closeout_ready","formal_review_ready","completion_ready","blocker_resolved","execution_started","formal_decision_ready"): f(f"row_{i}_{k}",r.get(k) is not False,r.get(k))
  f(f"row_{i}_status",r.get("observation_status")!="open_incomplete_blocked",r.get("observation_status"))
 result={"created_at":datetime.now(timezone.utc).isoformat(),"manifest_id":"P709","local_only":True,"success":not failures,"failure_count":len(failures),"failures":failures,"completion_observation_rows":len(lanes),"completion_ready_observed_rows":0,"closeout_ready_rows":0,"formal_review_ready_rows":0,"completion_ready_rows":0,"blocker_resolved_rows":0,"execution_started_rows":0,"formal_decision_ready_rows":0,"policy":"Validation only; P709 remains incomplete and fail-closed."}; OUT.write_text(json.dumps(result,ensure_ascii=False,indent=2,sort_keys=True)+"\n",encoding="utf-8"); print(json.dumps({"success":result["success"],"completion_observation_rows":len(lanes),"completion_ready_rows":0,"failures":len(failures),"output":str(OUT)},ensure_ascii=False)); return 0 if not failures else 1
if __name__=="__main__": raise SystemExit(main())
