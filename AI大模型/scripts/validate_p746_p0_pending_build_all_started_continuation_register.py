#!/usr/bin/env python3
"""Validate P746 all-started continuation register."""
from __future__ import annotations
import json
from datetime import datetime, timezone
from pathlib import Path
from build_p700_p0_real_input_pending_build_checklist import load_json, load_jsonl
ROOT=Path(__file__).resolve().parents[1]; SOURCE=ROOT/"datasets/governance/p745_p0_pending_build_closeout_to_reopen_gate.jsonl"; BOARD=ROOT/"datasets/governance/p746_p0_pending_build_all_started_continuation_register.jsonl"; REPORT=ROOT/"reports/p746_p0_pending_build_all_started_continuation_register_report.json"; OUT=ROOT/"reports/p746_p0_pending_build_all_started_continuation_register_validation_report.json"
def main()->int:
    source=[r for r in load_jsonl(SOURCE) if r.get("boundary")!="summary"]; rows=load_jsonl(BOARD); regs=rows[:-1] if rows else []; summary=rows[-1] if rows else {}; report=load_json(REPORT); failures=[]
    def fail(c,x,o,e):
        if x: failures.append({"check":c,"observed":o,"expected":e})
    fail("source_rows",len(source)!=5,len(source),5); fail("register_rows",len(regs)!=5,len(regs),5); fail("summary",summary.get("boundary")!="summary",summary.get("boundary"),"summary"); fail("coverage",{r.get("source_p745_id") for r in regs}!={r.get("reopen_gate_id") for r in source},"mismatch","exact"); fail("all_started",sum(r.get("all_started") is True for r in regs)!=5, sum(r.get("all_started") is True for r in regs),5); fail("planning_started",sum(r.get("planning_started") is True for r in regs)!=5,sum(r.get("planning_started") is True for r in regs),5)
    for field in ("execution_started_rows","real_input_received_rows","formal_decision_ready_rows","authorization_granted_rows"): fail(field,report.get(field)!=0,report.get(field),0)
    for i,row in enumerate(regs,1):
        fail(f"row_{i}_status",row.get("register_status")!="all_started_planning_only",row.get("register_status"),"all_started_planning_only"); fail(f"row_{i}_execution",row.get("execution_started") is not False,row.get("execution_started"),False); fail(f"row_{i}_input",row.get("real_input_received") is not False,row.get("real_input_received"),False)
    result={"created_at":datetime.now(timezone.utc).isoformat(),"manifest_id":"P746","local_only":True,"success":not failures,"failure_count":len(failures),"failures":failures,"register_rows":len(regs),"all_started_rows":5,"planning_started_rows":5,"execution_started_rows":0,"real_input_received_rows":0,"formal_decision_ready_rows":0,"authorization_granted_rows":0,"policy":"Validation only; all-started is planning registration, not execution."}; OUT.write_text(json.dumps(result,ensure_ascii=False,indent=2,sort_keys=True)+"\n",encoding="utf-8"); print(json.dumps({"success":result["success"],"register_rows":len(regs),"all_started_rows":5,"execution_started_rows":0,"failures":len(failures),"output":str(OUT)},ensure_ascii=False)); return 0 if not failures else 1
if __name__=="__main__": raise SystemExit(main())
