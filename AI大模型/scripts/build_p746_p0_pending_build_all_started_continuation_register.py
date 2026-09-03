#!/usr/bin/env python3
"""Build P746 all-started continuation register from P745."""
from __future__ import annotations
import json
from datetime import datetime, timezone
from pathlib import Path
from build_p700_p0_real_input_pending_build_checklist import load_jsonl

ROOT=Path(__file__).resolve().parents[1]; SOURCE=ROOT/"datasets/governance/p745_p0_pending_build_closeout_to_reopen_gate.jsonl"; OUT=ROOT/"datasets/governance/p746_p0_pending_build_all_started_continuation_register.jsonl"; REPORT=ROOT/"reports/p746_p0_pending_build_all_started_continuation_register_report.json"; MD=ROOT/"reports/p746_p0_pending_build_all_started_continuation_register.md"
FIELDS=("all_started","planning_started","execution_started","real_input_received","formal_decision_ready","authorization_granted")
def main()->int:
    created=datetime.now(timezone.utc).isoformat(); source=[r for r in load_jsonl(SOURCE) if r.get("boundary")!="summary"]; rows=[]
    for order,src in enumerate(source,1):
        row={"register_id":f"p746::{src.get('reopen_gate_id')}","register_order":order,"created_at":created,"boundary":src.get("boundary"),"source_p745_id":src.get("reopen_gate_id"),"register_status":"all_started_planning_only","blocker_reason":"All local planning lanes are started; real input and authorization remain absent.","operator_action":"Continue local checklist construction only; do not treat all-started as execution permission.","policy":"P746 records planning start, not operational execution or authorization."}; row.update({f:False for f in FIELDS}); row["all_started"]=True; row["planning_started"]=True; rows.append(row)
    counts={f"{f}_rows":sum(r.get(f) is True for r in rows) for f in FIELDS}; counts["execution_started_rows"]=0; summary={"register_id":"p746::summary","register_order":len(rows)+1,"created_at":created,"boundary":"summary","register_rows":len(rows),"all_started_rows":len(rows),"planning_started_rows":len(rows),"execution_started_rows":0,"real_input_received_rows":0,"formal_decision_ready_rows":0,"authorization_granted_rows":0,"policy":"P746 all-started means planning registration only; execution remains false."}; OUT.write_text("".join(json.dumps(r,ensure_ascii=False,sort_keys=True)+"\n" for r in rows+[summary]),encoding="utf-8"); report={"manifest_id":"P746","created_at":created,"local_only":True,"register_rows":len(rows),"all_started_rows":len(rows),"planning_started_rows":len(rows),"execution_started_rows":0,"real_input_received_rows":0,"formal_decision_ready_rows":0,"authorization_granted_rows":0,"artifact_jsonl":str(OUT.relative_to(ROOT)),"artifact_md":str(MD.relative_to(ROOT)),"policy":"P746 is planning-only and fail-closed."}; REPORT.write_text(json.dumps(report,ensure_ascii=False,indent=2,sort_keys=True)+"\n",encoding="utf-8"); MD.write_text(f"# P746 all-started continuation register\n\nRows: `{len(rows)}`. Planning started: `{len(rows)}`. Execution started: `0`.\n",encoding="utf-8"); print(json.dumps({"manifest_id":"P746","register_rows":len(rows),"all_started_rows":len(rows),"execution_started_rows":0,"output":str(REPORT)},ensure_ascii=False)); return 0
if __name__=="__main__": raise SystemExit(main())
