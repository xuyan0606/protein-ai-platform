#!/usr/bin/env python3
"""Validate P707 escalation-readiness board."""
from __future__ import annotations
import json
from datetime import datetime,timezone
from pathlib import Path
from build_p700_p0_real_input_pending_build_checklist import load_json,load_jsonl
ROOT=Path(__file__).resolve().parents[1]; BOARD=ROOT/"datasets/governance/p707_p0_pending_build_escalation_readiness_board.jsonl"; REPORT=ROOT/"reports/p707_p0_pending_build_escalation_readiness_board_report.json"; OUT=ROOT/"reports/p707_p0_pending_build_escalation_readiness_board_validation_report.json"
def main():
 rows=load_jsonl(BOARD); lanes=rows[:-1]; report=load_json(REPORT); failures=[]
 def f(c,x,o):
  if x: failures.append({"check":c,"observed":o})
 f("rows",len(lanes)!=15,len(lanes))
 for k in ("escalation_triggered_rows","escalation_package_prepared_rows","escalation_reviewed_rows","escalation_sent_rows","escalation_acknowledged_rows","execution_started_rows","formal_decision_ready_rows"): f(k,report.get(k)!=0,report.get(k))
 for i,r in enumerate(lanes,1):
  for k in ("escalation_triggered","escalation_package_prepared","escalation_reviewed","escalation_sent","escalation_acknowledged","execution_started","formal_decision_ready"): f(f"row_{i}_{k}",r.get(k) is not False,r.get(k))
  f(f"row_{i}_status",r.get("escalation_status")!="open_unprepared_blocked",r.get("escalation_status"))
 result={"created_at":datetime.now(timezone.utc).isoformat(),"manifest_id":"P707","local_only":True,"success":not failures,"failure_count":len(failures),"failures":failures,"escalation_board_rows":len(lanes),"escalation_triggered_rows":0,"escalation_package_prepared_rows":0,"escalation_reviewed_rows":0,"escalation_sent_rows":0,"escalation_acknowledged_rows":0,"execution_started_rows":0,"formal_decision_ready_rows":0,"policy":"Validation only; P707 remains unprepared and fail-closed."}; OUT.write_text(json.dumps(result,ensure_ascii=False,indent=2,sort_keys=True)+"\n",encoding="utf-8"); print(json.dumps({"success":result["success"],"escalation_board_rows":len(lanes),"escalation_sent_rows":0,"failures":len(failures),"output":str(OUT)},ensure_ascii=False)); return 0 if not failures else 1
if __name__=="__main__": raise SystemExit(main())
