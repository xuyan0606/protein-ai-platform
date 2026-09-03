#!/usr/bin/env python3
import json
from datetime import datetime, timezone
from pathlib import Path
from build_p700_p0_real_input_pending_build_checklist import load_json, load_jsonl
ROOT=Path(__file__).resolve().parents[1]; SOURCE=ROOT/"datasets/governance/p787_p0_pending_build_production_execution_audit_integrity_gate.jsonl"; BOARD=ROOT/"datasets/governance/p788_p0_pending_build_production_audit_retention_immutability_gate.jsonl"; REPORT=ROOT/"reports/p788_p0_pending_build_production_audit_retention_immutability_gate_report.json"; OUT=ROOT/"reports/p788_p0_pending_build_production_audit_retention_immutability_gate_validation_report.json"; FIELDS=("audit_receipt_present","receipt_integrity_validated","retention_policy_validated","receipt_immutable","provenance_retained","receipt_retrievable","execution_result_attested","formal_decision_ready","production_execution_allowed")
def main():
 src=[r for r in load_jsonl(SOURCE) if r.get("boundary")!="summary"]; rows=load_jsonl(BOARD); gates=rows[:-1] if rows else []; summary=rows[-1] if rows else {}; report=load_json(REPORT); failures=[]
 def fail(c,x,o,e):
  if x: failures.append({"check":c,"observed":o,"expected":e})
 fail("source_rows",len(src)!=5,len(src),5); fail("retention_gate_rows",len(gates)!=5,len(gates),5); fail("summary",summary.get("boundary")!="summary",summary.get("boundary"),"summary")
 for f in FIELDS: fail(f,report.get(f+"_rows")!=0,report.get(f+"_rows"),0)
 for i,r in enumerate(gates,1):
  fail(f"row_{i}_status",r.get("gate_status")!="empty_no_receipt_to_retain_or_immutabilize",r.get("gate_status"),"empty_no_receipt_to_retain_or_immutabilize")
  for f in FIELDS: fail(f"row_{i}_{f}",r.get(f) is not False,r.get(f),False)
 result={"created_at":datetime.now(timezone.utc).isoformat(),"manifest_id":"P788","local_only":True,"success":not failures,"failure_count":len(failures),"failures":failures,"retention_gate_rows":len(gates),**{f+"_rows":0 for f in FIELDS},"policy":"Validation only; P788 keeps audit retention and production gates blocked."}; OUT.write_text(json.dumps(result,ensure_ascii=False,indent=2,sort_keys=True)+"\n",encoding="utf-8"); print(json.dumps({"success":result["success"],"retention_gate_rows":len(gates),"receipt_immutable_rows":0,"failures":len(failures),"output":str(OUT)},ensure_ascii=False)); return 0 if not failures else 1
if __name__=='__main__': raise SystemExit(main())
