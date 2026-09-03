#!/usr/bin/env python3
"""Validate P702 planning-only action queue."""
from __future__ import annotations
import json
from datetime import datetime, timezone
from pathlib import Path
from build_p700_p0_real_input_pending_build_checklist import load_json, load_jsonl
ROOT=Path(__file__).resolve().parents[1]; BOARD=ROOT/"datasets/governance/p702_p0_pending_build_action_queue.jsonl"; REPORT=ROOT/"reports/p702_p0_pending_build_action_queue_report.json"; OUT=ROOT/"reports/p702_p0_pending_build_action_queue_validation_report.json"
def main():
    rows=load_jsonl(BOARD); report=load_json(REPORT); lanes=rows[:-1]; failures=[]
    def f(c,x,o):
        if x: failures.append({"check":c,"observed":o})
    f("row_count",len(lanes)!=15,len(lanes)); f("report_rows",report.get("action_queue_rows")!=15,report.get("action_queue_rows")); f("started_rows",report.get("action_started_rows")!=15,report.get("action_started_rows")); f("execution_rows",report.get("execution_started_rows")!=0,report.get("execution_started_rows"))
    ids=[r.get("action_queue_id") for r in lanes]; f("unique_ids",len(ids)!=len(set(ids)),ids)
    for i,r in enumerate(lanes,1):
        f(f"row_{i}_started",r.get("action_started") is not True,r.get("action_started")); f(f"row_{i}_execution",r.get("execution_started") is not False,r.get("execution_started")); f(f"row_{i}_description",not r.get("action_description"),r.get("action_description")); f(f"row_{i}_policy",not r.get("policy"),r.get("policy"))
    result={"created_at":datetime.now(timezone.utc).isoformat(),"manifest_id":"P702","local_only":True,"success":not failures,"failure_count":len(failures),"failures":failures,"action_queue_rows":len(lanes),"action_started_rows":sum(r.get("action_started") is True for r in lanes),"execution_started_rows":sum(r.get("execution_started") is True for r in lanes),"real_input_received_rows":0,"evidence_received_rows":0,"formal_decision_ready_rows":0,"policy":"Validation only; P702 remains planning-only and fail-closed."}
    OUT.write_text(json.dumps(result,ensure_ascii=False,indent=2,sort_keys=True)+"\n",encoding="utf-8"); print(json.dumps({"success":result["success"],"action_queue_rows":result["action_queue_rows"],"action_started_rows":result["action_started_rows"],"execution_started_rows":0,"failures":len(failures),"output":str(OUT)},ensure_ascii=False)); return 0 if not failures else 1
if __name__=="__main__": raise SystemExit(main())
