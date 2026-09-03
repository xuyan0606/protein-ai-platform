#!/usr/bin/env python3
"""Validate P719 decision-routing readiness."""
from __future__ import annotations
import json
from datetime import datetime,timezone
from pathlib import Path
from build_p700_p0_real_input_pending_build_checklist import load_json,load_jsonl
ROOT=Path(__file__).resolve().parents[1]; BOARD=ROOT/"datasets/governance/p719_p0_pending_build_decision_routing_readiness.jsonl"; REPORT=ROOT/"reports/p719_p0_pending_build_decision_routing_readiness_report.json"; OUT=ROOT/"reports/p719_p0_pending_build_decision_routing_readiness_validation_report.json"
def main():
 rows=load_jsonl(BOARD); lanes=rows[:-1]; report=load_json(REPORT); failures=[]
 def f(c,x,o):
  if x: failures.append({"check":c,"observed":o})
 f("rows",len(lanes)!=5,len(lanes))
 for k in ("route_selected_rows","decision_route_executed_rows","routed_to_formal_review_rows","formal_decision_ready_rows"): f(k,report.get(k)!=0,report.get(k))
 for i,r in enumerate(lanes,1):
  f(f"row_{i}_status",r.get("routing_status")!="not_routable_quarantine_empty",r.get("routing_status")); f(f"row_{i}_routes",len(r.get("candidate_routes") or [])!=3,r.get("candidate_routes"));
  for k in ("evidence_released","route_selected","decision_route_executed","routed_to_formal_review","formal_decision_ready"): f(f"row_{i}_{k}",r.get(k) is not False,r.get(k))
 result={"created_at":datetime.now(timezone.utc).isoformat(),"manifest_id":"P719","local_only":True,"success":not failures,"failure_count":len(failures),"failures":failures,"routing_readiness_rows":len(lanes),"route_selected_rows":0,"decision_route_executed_rows":0,"routed_to_formal_review_rows":0,"formal_decision_ready_rows":0,"policy":"Validation only; P719 remains unroutable and fail-closed."}; OUT.write_text(json.dumps(result,ensure_ascii=False,indent=2,sort_keys=True)+"\n",encoding="utf-8"); print(json.dumps({"success":result["success"],"routing_readiness_rows":len(lanes),"route_selected_rows":0,"failures":len(failures),"output":str(OUT)},ensure_ascii=False)); return 0 if not failures else 1
if __name__=="__main__": raise SystemExit(main())
