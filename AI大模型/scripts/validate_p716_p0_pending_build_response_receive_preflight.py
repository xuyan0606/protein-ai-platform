#!/usr/bin/env python3
"""Validate P716 response receive preflight."""
from __future__ import annotations
import json
from datetime import datetime,timezone
from pathlib import Path
from build_p700_p0_real_input_pending_build_checklist import load_json,load_jsonl
ROOT=Path(__file__).resolve().parents[1]; BOARD=ROOT/"datasets/governance/p716_p0_pending_build_response_receive_preflight.jsonl"; REPORT=ROOT/"reports/p716_p0_pending_build_response_receive_preflight_report.json"; OUT=ROOT/"reports/p716_p0_pending_build_response_receive_preflight_validation_report.json"
def main():
 rows=load_jsonl(BOARD); lanes=rows[:-1]; report=load_json(REPORT); failures=[]
 def f(c,x,o):
  if x: failures.append({"check":c,"observed":o})
 f("rows",len(lanes)!=5,len(lanes)); f("executed",report.get("receive_preflight_executed_rows")!=0,report.get("receive_preflight_executed_rows")); f("response",report.get("response_received_rows")!=0,report.get("response_received_rows"))
 for i,r in enumerate(lanes,1):
  for k in ("receive_channel_ready","payload_complete","source_identity_verified","duplicate_check_passed","receive_preflight_executed","response_received","evidence_validated","formal_decision_ready"): f(f"row_{i}_{k}",r.get(k) is not False,r.get(k))
 result={"created_at":datetime.now(timezone.utc).isoformat(),"manifest_id":"P716","local_only":True,"success":not failures,"failure_count":len(failures),"failures":failures,"preflight_rows":len(lanes),"receive_preflight_executed_rows":0,"response_received_rows":0,"evidence_validated_rows":0,"formal_decision_ready_rows":0,"policy":"Validation only; P716 remains unexecuted and fail-closed."}; OUT.write_text(json.dumps(result,ensure_ascii=False,indent=2,sort_keys=True)+"\n",encoding="utf-8"); print(json.dumps({"success":result["success"],"preflight_rows":len(lanes),"receive_preflight_executed_rows":0,"failures":len(failures),"output":str(OUT)},ensure_ascii=False)); return 0 if not failures else 1
if __name__=="__main__": raise SystemExit(main())
