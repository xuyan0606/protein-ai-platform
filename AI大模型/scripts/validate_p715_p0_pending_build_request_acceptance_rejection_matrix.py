#!/usr/bin/env python3
"""Validate P715 request acceptance/rejection matrix."""
from __future__ import annotations
import json
from datetime import datetime,timezone
from pathlib import Path
from build_p700_p0_real_input_pending_build_checklist import load_json,load_jsonl
ROOT=Path(__file__).resolve().parents[1]; BOARD=ROOT/"datasets/governance/p715_p0_pending_build_request_acceptance_rejection_matrix.jsonl"; REPORT=ROOT/"reports/p715_p0_pending_build_request_acceptance_rejection_matrix_report.json"; OUT=ROOT/"reports/p715_p0_pending_build_request_acceptance_rejection_matrix_validation_report.json"
def main():
 rows=load_jsonl(BOARD); lanes=rows[:-1]; report=load_json(REPORT); failures=[]
 def f(c,x,o):
  if x: failures.append({"check":c,"observed":o})
 f("rows",len(lanes)!=5,len(lanes))
 for k in ("response_received_rows","response_accepted_rows","response_rejected_rows","evidence_validated_rows","formal_decision_ready_rows"): f(k,report.get(k)!=0,report.get(k))
 for i,r in enumerate(lanes,1):
  f(f"row_{i}_status",r.get("acceptance_status")!="empty_no_response",r.get("acceptance_status")); f(f"row_{i}_received",r.get("response_received") is not False,r.get("response_received")); f(f"row_{i}_accepted",r.get("response_accepted") is not False,r.get("response_accepted")); f(f"row_{i}_rejected",r.get("response_rejected") is not False,r.get("response_rejected")); f(f"row_{i}_criteria",not r.get("acceptance_criteria") or not r.get("rejection_criteria"),r.get("acceptance_criteria"))
 result={"created_at":datetime.now(timezone.utc).isoformat(),"manifest_id":"P715","local_only":True,"success":not failures,"failure_count":len(failures),"failures":failures,"acceptance_matrix_rows":len(lanes),"response_received_rows":0,"response_accepted_rows":0,"response_rejected_rows":0,"evidence_validated_rows":0,"formal_decision_ready_rows":0,"policy":"Validation only; P715 remains empty and fail-closed."}; OUT.write_text(json.dumps(result,ensure_ascii=False,indent=2,sort_keys=True)+"\n",encoding="utf-8"); print(json.dumps({"success":result["success"],"acceptance_matrix_rows":len(lanes),"response_received_rows":0,"failures":len(failures),"output":str(OUT)},ensure_ascii=False)); return 0 if not failures else 1
if __name__=="__main__": raise SystemExit(main())
