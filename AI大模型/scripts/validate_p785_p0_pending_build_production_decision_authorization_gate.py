#!/usr/bin/env python3
import json
from datetime import datetime, timezone
from pathlib import Path
from build_p700_p0_real_input_pending_build_checklist import load_json, load_jsonl
ROOT=Path(__file__).resolve().parents[1]; SOURCE=ROOT/"datasets/governance/p784_p0_pending_build_production_receipt_decision_lineage_gate.jsonl"; BOARD=ROOT/"datasets/governance/p785_p0_pending_build_production_decision_authorization_gate.jsonl"; REPORT=ROOT/"reports/p785_p0_pending_build_production_decision_authorization_gate_report.json"; OUT=ROOT/"reports/p785_p0_pending_build_production_decision_authorization_gate_validation_report.json"; FIELDS=("lineage_complete","authorization_record_present","authorizer_identity_verified","authorization_scope_verified","authorization_provenance_validated","production_authorized","execution_authorized","formal_decision_ready","release_ready")
def main():
 src=[r for r in load_jsonl(SOURCE) if r.get("boundary")!="summary"]; rows=load_jsonl(BOARD); gates=rows[:-1] if rows else []; summary=rows[-1] if rows else {}; report=load_json(REPORT); failures=[]
 def fail(c,x,o,e):
  if x: failures.append({"check":c,"observed":o,"expected":e})
 fail("source_rows",len(src)!=5,len(src),5); fail("authorization_gate_rows",len(gates)!=5,len(gates),5); fail("summary",summary.get("boundary")!="summary",summary.get("boundary"),"summary")
 for f in FIELDS: fail(f,report.get(f+"_rows")!=0,report.get(f+"_rows"),0)
 for i,r in enumerate(gates,1):
  fail(f"row_{i}_status",r.get("gate_status")!="empty_no_production_lineage_authorization",r.get("gate_status"),"empty_no_production_lineage_authorization")
  for f in FIELDS: fail(f"row_{i}_{f}",r.get(f) is not False,r.get(f),False)
 result={"created_at":datetime.now(timezone.utc).isoformat(),"manifest_id":"P785","local_only":True,"success":not failures,"failure_count":len(failures),"failures":failures,"authorization_gate_rows":len(gates),**{f+"_rows":0 for f in FIELDS},"policy":"Validation only; P785 keeps production authorization and release blocked."}; OUT.write_text(json.dumps(result,ensure_ascii=False,indent=2,sort_keys=True)+"\n",encoding="utf-8"); print(json.dumps({"success":result["success"],"authorization_gate_rows":len(gates),"production_authorized_rows":0,"failures":len(failures),"output":str(OUT)},ensure_ascii=False)); return 0 if not failures else 1
if __name__=='__main__': raise SystemExit(main())
