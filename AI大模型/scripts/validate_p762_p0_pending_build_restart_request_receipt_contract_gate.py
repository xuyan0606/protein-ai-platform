#!/usr/bin/env python3
import json
from datetime import datetime, timezone
from pathlib import Path
from build_p700_p0_real_input_pending_build_checklist import load_json, load_jsonl
ROOT=Path(__file__).resolve().parents[1]; SOURCE=ROOT/"datasets/governance/p761_p0_pending_build_terminal_restart_prerequisite_gate.jsonl"; BOARD=ROOT/"datasets/governance/p762_p0_pending_build_restart_request_receipt_contract_gate.jsonl"; REPORT=ROOT/"reports/p762_p0_pending_build_restart_request_receipt_contract_gate_report.json"; OUT=ROOT/"reports/p762_p0_pending_build_restart_request_receipt_contract_gate_validation_report.json"
FIELDS=("restart_target_defined","restart_scope_defined","authorization_window_defined","request_dispatched","receipt_contract_defined","receipt_received","receipt_validated","restart_authorized","work_restarted")
def main():
 src=[r for r in load_jsonl(SOURCE) if r.get("boundary")!="summary"]; rows=load_jsonl(BOARD); gates=rows[:-1] if rows else []; summary=rows[-1] if rows else {}; report=load_json(REPORT); failures=[]
 def fail(c,x,o,e):
  if x: failures.append({"check":c,"observed":o,"expected":e})
 fail("source_rows",len(src)!=5,len(src),5); fail("request_gate_rows",len(gates)!=5,len(gates),5); fail("summary",summary.get("boundary")!="summary",summary.get("boundary"),"summary")
 for f in FIELDS: fail(f,report.get(f+"_rows")!=0,report.get(f+"_rows"),0)
 for i,r in enumerate(gates,1):
  fail(f"row_{i}_status",r.get("gate_status")!="queued_no_restart_request_to_dispatch",r.get("gate_status"),"queued_no_restart_request_to_dispatch")
  for f in FIELDS: fail(f"row_{i}_{f}",r.get(f) is not False,r.get(f),False)
 result={"created_at":datetime.now(timezone.utc).isoformat(),"manifest_id":"P762","local_only":True,"success":not failures,"failure_count":len(failures),"failures":failures,"request_gate_rows":len(gates),**{f+"_rows":0 for f in FIELDS},"policy":"Validation only; P762 keeps dispatch, receipt, and restart blocked."}; OUT.write_text(json.dumps(result,ensure_ascii=False,indent=2,sort_keys=True)+"\n",encoding="utf-8"); print(json.dumps({"success":result["success"],"request_gate_rows":len(gates),"request_dispatched_rows":0,"receipt_received_rows":0,"failures":len(failures),"output":str(OUT)},ensure_ascii=False)); return 0 if not failures else 1
if __name__=='__main__': raise SystemExit(main())
