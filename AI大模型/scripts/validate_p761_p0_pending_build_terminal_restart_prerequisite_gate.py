#!/usr/bin/env python3
"""Validate P761 terminal restart prerequisite gates."""
from __future__ import annotations
import json
from datetime import datetime, timezone
from pathlib import Path
from build_p700_p0_real_input_pending_build_checklist import load_json, load_jsonl
ROOT=Path(__file__).resolve().parents[1]; SOURCE=ROOT/"datasets/governance/p760_p0_pending_build_terminal_fail_closed_monitor.jsonl"; BOARD=ROOT/"datasets/governance/p761_p0_pending_build_terminal_restart_prerequisite_gate.jsonl"; REPORT=ROOT/"reports/p761_p0_pending_build_terminal_restart_prerequisite_gate_report.json"; OUT=ROOT/"reports/p761_p0_pending_build_terminal_restart_prerequisite_gate_validation_report.json"; FIELDS=("real_input_received","evidence_validated","owner_confirmed","validator_passed","restart_requested","restart_authorized","work_restarted","formal_decision_ready","production_execution_allowed")
def main()->int:
 src=[r for r in load_jsonl(SOURCE) if r.get("boundary")!="summary"]; rows=load_jsonl(BOARD); gates=rows[:-1] if rows else []; summary=rows[-1] if rows else {}; report=load_json(REPORT); failures=[]
 def fail(c,x,o,e):
  if x: failures.append({"check":c,"observed":o,"expected":e})
 fail("source_rows",len(src)!=5,len(src),5); fail("restart_gate_rows",len(gates)!=5,len(gates),5); fail("summary",summary.get("boundary")!="summary",summary.get("boundary"),"summary"); fail("coverage",{r.get("source_p760_id") for r in gates}!={r.get("monitor_id") for r in src},"mismatch","exact")
 for f in FIELDS: fail(f,report.get(f+"_rows")!=0,report.get(f+"_rows"),0)
 for i,r in enumerate(gates,1):
  fail(f"row_{i}_status",r.get("gate_status")!="blocked_missing_restart_prerequisites",r.get("gate_status"),"blocked_missing_restart_prerequisites")
  for f in FIELDS: fail(f"row_{i}_{f}",r.get(f) is not False,r.get(f),False)
 result={"created_at":datetime.now(timezone.utc).isoformat(),"manifest_id":"P761","local_only":True,"success":not failures,"failure_count":len(failures),"failures":failures,"restart_gate_rows":len(gates),**{f+"_rows":0 for f in FIELDS},"policy":"Validation only; P761 keeps restart and execution blocked."}; OUT.write_text(json.dumps(result,ensure_ascii=False,indent=2,sort_keys=True)+"\n",encoding="utf-8"); print(json.dumps({"success":result["success"],"restart_gate_rows":len(gates),"restart_authorized_rows":0,"failures":len(failures),"output":str(OUT)},ensure_ascii=False)); return 0 if not failures else 1
if __name__=='__main__': raise SystemExit(main())
