#!/usr/bin/env python3
"""Validate P717 response schema contract."""
from __future__ import annotations
import json
from datetime import datetime,timezone
from pathlib import Path
from build_p700_p0_real_input_pending_build_checklist import load_json,load_jsonl
ROOT=Path(__file__).resolve().parents[1]; BOARD=ROOT/"datasets/governance/p717_p0_pending_build_response_schema_contract.jsonl"; REPORT=ROOT/"reports/p717_p0_pending_build_response_schema_contract_report.json"; OUT=ROOT/"reports/p717_p0_pending_build_response_schema_contract_validation_report.json"
def main():
 rows=load_jsonl(BOARD); lanes=rows[:-1]; report=load_json(REPORT); failures=[]
 def f(c,x,o):
  if x: failures.append({"check":c,"observed":o})
 f("rows",len(lanes)!=5,len(lanes)); f("validated",report.get("schema_validated_rows")!=0,report.get("schema_validated_rows")); f("response",report.get("response_received_rows")!=0,report.get("response_received_rows"))
 for i,r in enumerate(lanes,1):
  f(f"row_{i}_status",r.get("contract_status")!="defined_unpopulated",r.get("contract_status")); f(f"row_{i}_fields",len(r.get("required_fields") or [])!=7,r.get("required_fields")); f(f"row_{i}_validated",r.get("schema_validated") is not False,r.get("schema_validated")); f(f"row_{i}_response",r.get("response_received") is not False,r.get("response_received"))
 result={"created_at":datetime.now(timezone.utc).isoformat(),"manifest_id":"P717","local_only":True,"success":not failures,"failure_count":len(failures),"failures":failures,"schema_contract_rows":len(lanes),"schema_validated_rows":0,"response_received_rows":0,"evidence_validated_rows":0,"formal_decision_ready_rows":0,"policy":"Validation only; P717 remains defined but unpopulated and fail-closed."}; OUT.write_text(json.dumps(result,ensure_ascii=False,indent=2,sort_keys=True)+"\n",encoding="utf-8"); print(json.dumps({"success":result["success"],"schema_contract_rows":len(lanes),"schema_validated_rows":0,"failures":len(failures),"output":str(OUT)},ensure_ascii=False)); return 0 if not failures else 1
if __name__=="__main__": raise SystemExit(main())
