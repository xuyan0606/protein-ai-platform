#!/usr/bin/env python3
"""Validate P705 owner-assignment gap board."""
from __future__ import annotations
import json
from datetime import datetime,timezone
from pathlib import Path
from build_p700_p0_real_input_pending_build_checklist import load_json,load_jsonl
ROOT=Path(__file__).resolve().parents[1]; BOARD=ROOT/"datasets/governance/p705_p0_pending_build_owner_assignment_gap_board.jsonl"; REPORT=ROOT/"reports/p705_p0_pending_build_owner_assignment_gap_board_report.json"; OUT=ROOT/"reports/p705_p0_pending_build_owner_assignment_gap_board_validation_report.json"
def main():
 rows=load_jsonl(BOARD); lanes=rows[:-1]; report=load_json(REPORT); failures=[]
 def f(c,x,o):
  if x: failures.append({"check":c,"observed":o})
 f("rows",len(lanes)!=15,len(lanes))
 for key in ("owner_assigned_rows","owner_acknowledged_rows","operator_dispatched_rows","escalation_reviewed_rows","escalation_sent_rows","execution_started_rows","formal_decision_ready_rows"): f(key,report.get(key)!=0,report.get(key))
 for i,r in enumerate(lanes,1):
  for key in ("owner_assigned","owner_acknowledged","operator_dispatched","escalation_reviewed","escalation_sent","execution_started","formal_decision_ready"): f(f"row_{i}_{key}",r.get(key) is not False,r.get(key))
  f(f"row_{i}_status",r.get("owner_assignment_status")!="open_empty_unassigned_blocked",r.get("owner_assignment_status"))
 result={"created_at":datetime.now(timezone.utc).isoformat(),"manifest_id":"P705","local_only":True,"success":not failures,"failure_count":len(failures),"failures":failures,"owner_gap_board_rows":len(lanes),"owner_assigned_rows":0,"owner_acknowledged_rows":0,"operator_dispatched_rows":0,"escalation_reviewed_rows":0,"escalation_sent_rows":0,"execution_started_rows":0,"formal_decision_ready_rows":0,"policy":"Validation only; P705 remains unassigned and fail-closed."}; OUT.write_text(json.dumps(result,ensure_ascii=False,indent=2,sort_keys=True)+"\n",encoding="utf-8"); print(json.dumps({"success":result["success"],"owner_gap_board_rows":len(lanes),"owner_assigned_rows":0,"failures":len(failures),"output":str(OUT)},ensure_ascii=False)); return 0 if not failures else 1
if __name__=="__main__": raise SystemExit(main())
