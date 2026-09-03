#!/usr/bin/env python3
import json
from datetime import datetime, timezone
from pathlib import Path
from build_p700_p0_real_input_pending_build_checklist import load_json, load_jsonl
ROOT=Path(__file__).resolve().parents[1]; SOURCE=ROOT/"datasets/governance/p782_p0_pending_build_production_review_receipt_schema_gate.jsonl"; BOARD=ROOT/"datasets/governance/p783_p0_pending_build_production_review_receipt_quarantine_gate.jsonl"; REPORT=ROOT/"reports/p783_p0_pending_build_production_review_receipt_quarantine_gate_report.json"; OUT=ROOT/"reports/p783_p0_pending_build_production_review_receipt_quarantine_gate_validation_report.json"; FIELDS=("receipt_received","receipt_schema_validated","receipt_identity_verified","receipt_timestamp_verified","receipt_result_validated","receipt_provenance_validated","receipt_quarantined","receipt_released","formal_decision_ready")
def main():
 src=[r for r in load_jsonl(SOURCE) if r.get("boundary")!="summary"]; rows=load_jsonl(BOARD); gates=rows[:-1] if rows else []; summary=rows[-1] if rows else {}; report=load_json(REPORT); failures=[]
 def fail(c,x,o,e):
  if x: failures.append({"check":c,"observed":o,"expected":e})
 fail("source_rows",len(src)!=5,len(src),5); fail("quarantine_gate_rows",len(gates)!=5,len(gates),5); fail("summary",summary.get("boundary")!="summary",summary.get("boundary"),"summary")
 for f in FIELDS: fail(f,report.get(f+"_rows")!=0,report.get(f+"_rows"),0)
 for i,r in enumerate(gates,1):
  fail(f"row_{i}_status",r.get("gate_status")!="empty_no_production_review_receipt_to_quarantine",r.get("gate_status"),"empty_no_production_review_receipt_to_quarantine")
  for f in FIELDS: fail(f"row_{i}_{f}",r.get(f) is not False,r.get(f),False)
 result={"created_at":datetime.now(timezone.utc).isoformat(),"manifest_id":"P783","local_only":True,"success":not failures,"failure_count":len(failures),"failures":failures,"quarantine_gate_rows":len(gates),**{f+"_rows":0 for f in FIELDS},"policy":"Validation only; P783 keeps receipts and production gates blocked."}; OUT.write_text(json.dumps(result,ensure_ascii=False,indent=2,sort_keys=True)+"\n",encoding="utf-8"); print(json.dumps({"success":result["success"],"quarantine_gate_rows":len(gates),"receipt_released_rows":0,"failures":len(failures),"output":str(OUT)},ensure_ascii=False)); return 0 if not failures else 1
if __name__=='__main__': raise SystemExit(main())
