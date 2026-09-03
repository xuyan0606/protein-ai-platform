#!/usr/bin/env python3
"""Validate P701 all-started planning registration."""
from __future__ import annotations
import json
from datetime import datetime, timezone
from pathlib import Path
from build_p700_p0_real_input_pending_build_checklist import load_jsonl, load_json

ROOT=Path(__file__).resolve().parents[1]
BOARD=ROOT/"datasets/governance/p701_p0_pending_build_all_started_board.jsonl"
REPORT=ROOT/"reports/p701_p0_pending_build_all_started_board_report.json"
OUT=ROOT/"reports/p701_p0_pending_build_all_started_board_validation_report.json"
FALSE_FIELDS=("execution_started","real_input_received","evidence_received","formal_decision_written","formal_decision_ready","training_import_allowed","safe_for_model_claim","customer_delivery_ready","release_ready","production_execution_allowed","p0_unblocked","p0_completion_ready")
def main():
    rows=load_jsonl(BOARD); report=load_json(REPORT); lanes=rows[:-1]; summary=rows[-1] if rows else {}; failures=[]
    def f(check, cond, obs):
        if cond: failures.append({"check":check,"observed":obs})
    f("lane_count",len(lanes)!=5,len(lanes)); f("summary",summary.get("lane")!="summary",summary.get("lane")); f("report_rows",report.get("all_started_board_rows")!=5,report.get("all_started_board_rows")); f("report_started",report.get("all_started_rows")!=5,report.get("all_started_rows")); f("report_execution",report.get("execution_started_rows")!=0,report.get("execution_started_rows"))
    for i,row in enumerate(lanes,1):
        f(f"row_{i}_started",row.get("all_started") is not True,row.get("all_started")); f(f"row_{i}_execution",row.get("execution_started") is not False,row.get("execution_started")); f(f"row_{i}_scope",not row.get("start_scope"),row.get("start_scope"))
        for field in FALSE_FIELDS: f(f"row_{i}_{field}",row.get(field) is not False,row.get(field))
    result={"created_at":datetime.now(timezone.utc).isoformat(),"manifest_id":"P701","local_only":True,"success":not failures,"failure_count":len(failures),"failures":failures,"all_started_board_rows":len(lanes),"all_started_rows":sum(r.get("all_started") is True for r in lanes),"execution_started_rows":sum(r.get("execution_started") is True for r in lanes),"real_input_received_rows":0,"formal_decision_ready_rows":0,"policy":"Validation only; P701 planning registration does not execute work."}
    result.update({f:False for f in FALSE_FIELDS}); result.update({f"{f}_rows":0 for f in FALSE_FIELDS}); OUT.write_text(json.dumps(result,ensure_ascii=False,indent=2,sort_keys=True)+"\n",encoding="utf-8"); print(json.dumps({"success":result["success"],"all_started_rows":result["all_started_rows"],"execution_started_rows":0,"failures":len(failures),"output":str(OUT)},ensure_ascii=False)); return 0 if not failures else 1
if __name__=="__main__": raise SystemExit(main())
