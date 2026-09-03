#!/usr/bin/env python3
import json
from datetime import datetime, timezone
from pathlib import Path
from build_p700_p0_real_input_pending_build_checklist import load_json, load_jsonl
ROOT=Path(__file__).resolve().parents[1]; SOURCE=ROOT/"datasets/governance/p773_p0_pending_build_authorization_downstream_nonpromotion_gate.jsonl"; BOARD=ROOT/"datasets/governance/p774_p0_pending_build_downstream_to_production_non_authorization_gate.jsonl"; REPORT=ROOT/"reports/p774_p0_pending_build_downstream_to_production_non_authorization_gate_report.json"; OUT=ROOT/"reports/p774_p0_pending_build_downstream_to_production_non_authorization_gate_validation_report.json"; FIELDS=("release_approved","customer_scope_confirmed","production_change_reviewed","rollback_plan_validated","execution_receipt_contract_ready","production_execution_requested","production_execution_authorized","production_execution_started","audit_receipt_present")
def main():
 src=[r for r in load_jsonl(SOURCE) if r.get("boundary")!="summary"]; rows=load_jsonl(BOARD); gates=rows[:-1] if rows else []; summary=rows[-1] if rows else {}; report=load_json(REPORT); failures=[]
 def fail(c,x,o,e):
  if x: failures.append({"check":c,"observed":o,"expected":e})
 fail("source_rows",len(src)!=5,len(src),5); fail("production_gate_rows",len(gates)!=5,len(gates),5); fail("summary",summary.get("boundary")!="summary",summary.get("boundary"),"summary")
 for f in FIELDS: fail(f,report.get(f+"_rows")!=0,report.get(f+"_rows"),0)
 for i,r in enumerate(gates,1):
  fail(f"row_{i}_status",r.get("gate_status")!="empty_no_downstream_state_to_execute",r.get("gate_status"),"empty_no_downstream_state_to_execute")
  for f in FIELDS: fail(f"row_{i}_{f}",r.get(f) is not False,r.get(f),False)
 result={"created_at":datetime.now(timezone.utc).isoformat(),"manifest_id":"P774","local_only":True,"success":not failures,"failure_count":len(failures),"failures":failures,"production_gate_rows":len(gates),**{f+"_rows":0 for f in FIELDS},"policy":"Validation only; P774 keeps production execution blocked."}; OUT.write_text(json.dumps(result,ensure_ascii=False,indent=2,sort_keys=True)+"\n",encoding="utf-8"); print(json.dumps({"success":result["success"],"production_gate_rows":len(gates),"production_execution_started_rows":0,"failures":len(failures),"output":str(OUT)},ensure_ascii=False)); return 0 if not failures else 1
if __name__=='__main__': raise SystemExit(main())
