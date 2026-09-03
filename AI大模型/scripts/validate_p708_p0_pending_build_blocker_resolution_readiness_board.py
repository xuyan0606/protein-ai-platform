#!/usr/bin/env python3
"""Validate P708 blocker-resolution readiness board."""
from __future__ import annotations
import json
from datetime import datetime,timezone
from pathlib import Path
from build_p700_p0_real_input_pending_build_checklist import load_json,load_jsonl
ROOT=Path(__file__).resolve().parents[1]; BOARD=ROOT/"datasets/governance/p708_p0_pending_build_blocker_resolution_readiness_board.jsonl"; REPORT=ROOT/"reports/p708_p0_pending_build_blocker_resolution_readiness_board_report.json"; OUT=ROOT/"reports/p708_p0_pending_build_blocker_resolution_readiness_board_validation_report.json"
def main():
 rows=load_jsonl(BOARD); lanes=rows[:-1]; report=load_json(REPORT); failures=[]
 def f(c,x,o):
  if x: failures.append({"check":c,"observed":o})
 f("rows",len(lanes)!=15,len(lanes))
 for k in ("evidence_ready_rows","owner_ready_rows","escalation_ready_rows","blocker_resolved_rows","closeout_ready_rows","completion_ready_rows","execution_started_rows","formal_decision_ready_rows"): f(k,report.get(k)!=0,report.get(k))
 for i,r in enumerate(lanes,1):
  for k in ("evidence_ready","owner_ready","escalation_ready","blocker_resolved","closeout_ready","completion_ready","execution_started","formal_decision_ready"): f(f"row_{i}_{k}",r.get(k) is not False,r.get(k))
  f(f"row_{i}_status",r.get("resolution_status")!="open_unresolved_blocked",r.get("resolution_status"))
 result={"created_at":datetime.now(timezone.utc).isoformat(),"manifest_id":"P708","local_only":True,"success":not failures,"failure_count":len(failures),"failures":failures,"resolution_board_rows":len(lanes),"evidence_ready_rows":0,"owner_ready_rows":0,"escalation_ready_rows":0,"blocker_resolved_rows":0,"closeout_ready_rows":0,"completion_ready_rows":0,"execution_started_rows":0,"formal_decision_ready_rows":0,"policy":"Validation only; P708 remains unresolved and fail-closed."}; OUT.write_text(json.dumps(result,ensure_ascii=False,indent=2,sort_keys=True)+"\n",encoding="utf-8"); print(json.dumps({"success":result["success"],"resolution_board_rows":len(lanes),"blocker_resolved_rows":0,"failures":len(failures),"output":str(OUT)},ensure_ascii=False)); return 0 if not failures else 1
if __name__=="__main__": raise SystemExit(main())
