#!/usr/bin/env python3
import json
from datetime import datetime, timezone
from pathlib import Path
from build_p700_p0_real_input_pending_build_checklist import load_json, load_jsonl
ROOT=Path(__file__).resolve().parents[1]; SOURCE=ROOT/"datasets/governance/p767_p0_pending_build_next_review_action_gate.jsonl"; BOARD=ROOT/"datasets/governance/p768_p0_pending_build_review_dispatch_readiness_gate.jsonl"; REPORT=ROOT/"reports/p768_p0_pending_build_review_dispatch_readiness_gate_report.json"; OUT=ROOT/"reports/p768_p0_pending_build_review_dispatch_readiness_gate_validation_report.json"; FIELDS=("dispatch_target_defined","dispatch_authorized","operator_defined","execution_window_defined","receipt_contract_defined","review_dispatched","review_executed","new_evidence_received","formal_decision_ready")
def main():
 src=[r for r in load_jsonl(SOURCE) if r.get("boundary")!="summary"]; rows=load_jsonl(BOARD); regs=rows[:-1] if rows else []; summary=rows[-1] if rows else {}; report=load_json(REPORT); failures=[]
 def fail(c,x,o,e):
  if x: failures.append({"check":c,"observed":o,"expected":e})
 fail("source_rows",len(src)!=5,len(src),5); fail("dispatch_gate_rows",len(regs)!=5,len(regs),5); fail("summary",summary.get("boundary")!="summary",summary.get("boundary"),"summary")
 for f in FIELDS: fail(f,report.get(f+"_rows")!=0,report.get(f+"_rows"),0)
 for i,r in enumerate(regs,1):
  fail(f"row_{i}_status",r.get("gate_status")!="queued_no_authorized_review_dispatch",r.get("gate_status"),"queued_no_authorized_review_dispatch")
  for f in FIELDS: fail(f"row_{i}_{f}",r.get(f) is not False,r.get(f),False)
 result={"created_at":datetime.now(timezone.utc).isoformat(),"manifest_id":"P768","local_only":True,"success":not failures,"failure_count":len(failures),"failures":failures,"dispatch_gate_rows":len(regs),**{f+"_rows":0 for f in FIELDS},"policy":"Validation only; P768 keeps dispatch and review blocked."}; OUT.write_text(json.dumps(result,ensure_ascii=False,indent=2,sort_keys=True)+"\n",encoding="utf-8"); print(json.dumps({"success":result["success"],"dispatch_gate_rows":len(regs),"review_dispatched_rows":0,"failures":len(failures),"output":str(OUT)},ensure_ascii=False)); return 0 if not failures else 1
if __name__=='__main__': raise SystemExit(main())
