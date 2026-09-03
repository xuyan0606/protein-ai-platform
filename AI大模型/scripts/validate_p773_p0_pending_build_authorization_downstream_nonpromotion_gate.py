#!/usr/bin/env python3
import json
from datetime import datetime, timezone
from pathlib import Path
from build_p700_p0_real_input_pending_build_checklist import load_json, load_jsonl
ROOT=Path(__file__).resolve().parents[1]; SOURCE=ROOT/"datasets/governance/p772_p0_pending_build_decision_to_authorization_provenance_gate.jsonl"; BOARD=ROOT/"datasets/governance/p773_p0_pending_build_authorization_downstream_nonpromotion_gate.jsonl"; REPORT=ROOT/"reports/p773_p0_pending_build_authorization_downstream_nonpromotion_gate_report.json"; OUT=ROOT/"reports/p773_p0_pending_build_authorization_downstream_nonpromotion_gate_validation_report.json"; FIELDS=("authorization_validated","restart_authorized","execution_authorized","model_claim_promoted","customer_delivery_promoted","release_claim_promoted","release_ready","production_execution_allowed")
def main():
 src=[r for r in load_jsonl(SOURCE) if r.get("boundary")!="summary"]; rows=load_jsonl(BOARD); gates=rows[:-1] if rows else []; summary=rows[-1] if rows else {}; report=load_json(REPORT); failures=[]
 def fail(c,x,o,e):
  if x: failures.append({"check":c,"observed":o,"expected":e})
 fail("source_rows",len(src)!=5,len(src),5); fail("nonpromotion_gate_rows",len(gates)!=5,len(gates),5); fail("summary",summary.get("boundary")!="summary",summary.get("boundary"),"summary")
 for f in FIELDS: fail(f,report.get(f+"_rows")!=0,report.get(f+"_rows"),0)
 for i,r in enumerate(gates,1):
  fail(f"row_{i}_status",r.get("gate_status")!="empty_no_validated_authorization_to_promote",r.get("gate_status"),"empty_no_validated_authorization_to_promote")
  for f in FIELDS: fail(f"row_{i}_{f}",r.get(f) is not False,r.get(f),False)
 result={"created_at":datetime.now(timezone.utc).isoformat(),"manifest_id":"P773","local_only":True,"success":not failures,"failure_count":len(failures),"failures":failures,"nonpromotion_gate_rows":len(gates),**{f+"_rows":0 for f in FIELDS},"policy":"Validation only; P773 keeps all downstream promotion blocked."}; OUT.write_text(json.dumps(result,ensure_ascii=False,indent=2,sort_keys=True)+"\n",encoding="utf-8"); print(json.dumps({"success":result["success"],"nonpromotion_gate_rows":len(gates),"release_claim_promoted_rows":0,"failures":len(failures),"output":str(OUT)},ensure_ascii=False)); return 0 if not failures else 1
if __name__=='__main__': raise SystemExit(main())
