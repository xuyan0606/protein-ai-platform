#!/usr/bin/env python3
import json
from datetime import datetime, timezone
from pathlib import Path
from build_p700_p0_real_input_pending_build_checklist import load_json, load_jsonl
ROOT=Path(__file__).resolve().parents[1]; SOURCE=ROOT/"datasets/governance/p778_p0_pending_build_production_audit_closeout_reopen_gate.jsonl"; BOARD=ROOT/"datasets/governance/p779_p0_pending_build_terminal_production_governance_monitor.jsonl"; REPORT=ROOT/"reports/p779_p0_pending_build_terminal_production_governance_monitor_report.json"; OUT=ROOT/"reports/p779_p0_pending_build_terminal_production_governance_monitor_validation_report.json"; FIELDS=("production_execution_allowed","production_execution_started","audit_receipt_present","sensitive_data_exposed","incident_active","closeout_approved","reopen_authorized","formal_decision_ready","release_ready")
def main():
 src=[r for r in load_jsonl(SOURCE) if r.get("boundary")!="summary"]; rows=load_jsonl(BOARD); mons=rows[:-1] if rows else []; summary=rows[-1] if rows else {}; report=load_json(REPORT); failures=[]
 def fail(c,x,o,e):
  if x: failures.append({"check":c,"observed":o,"expected":e})
 fail("source_rows",len(src)!=5,len(src),5); fail("monitor_rows",len(mons)!=5,len(mons),5); fail("summary",summary.get("boundary")!="summary",summary.get("boundary"),"summary")
 for f in FIELDS: fail(f,report.get(f+"_rows")!=0,report.get(f+"_rows"),0)
 for i,r in enumerate(mons,1):
  fail(f"row_{i}_status",r.get("monitor_status")!="terminal_production_blocked_under_observation",r.get("monitor_status"),"terminal_production_blocked_under_observation")
  for f in FIELDS: fail(f"row_{i}_{f}",r.get(f) is not False,r.get(f),False)
 result={"created_at":datetime.now(timezone.utc).isoformat(),"manifest_id":"P779","local_only":True,"success":not failures,"failure_count":len(failures),"failures":failures,"monitor_rows":len(mons),**{f+"_rows":0 for f in FIELDS},"policy":"Validation only; P779 confirms terminal production fail-closed state."}; OUT.write_text(json.dumps(result,ensure_ascii=False,indent=2,sort_keys=True)+"\n",encoding="utf-8"); print(json.dumps({"success":result["success"],"monitor_rows":len(mons),"production_execution_allowed_rows":0,"failures":len(failures),"output":str(OUT)},ensure_ascii=False)); return 0 if not failures else 1
if __name__=='__main__': raise SystemExit(main())
