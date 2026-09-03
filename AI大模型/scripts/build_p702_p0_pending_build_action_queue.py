#!/usr/bin/env python3
"""Build the P702 pending-build action queue from P701 started lanes."""
from __future__ import annotations
import json
from datetime import datetime, timezone
from pathlib import Path
from build_p701_p0_pending_build_all_started_board import load_jsonl

ROOT=Path(__file__).resolve().parents[1]
SOURCE=ROOT/"datasets/governance/p701_p0_pending_build_all_started_board.jsonl"
OUT=ROOT/"datasets/governance/p702_p0_pending_build_action_queue.jsonl"
REPORT=ROOT/"reports/p702_p0_pending_build_action_queue_report.json"
MD=ROOT/"reports/p702_p0_pending_build_action_queue.md"
ACTIONS=(("structure","Define the lane artifact structure and required fields."),("evidence","Define the missing evidence intake and validation slots."),("validation","Define the validator command and completion checks."))
def main():
    created=datetime.now(timezone.utc).isoformat(); lanes=[r for r in load_jsonl(SOURCE) if r.get("lane")!="summary"]; rows=[]
    for lane in lanes:
        for kind,desc in ACTIONS:
            rows.append({"action_queue_id":f"p702::{lane.get('lane')}::{kind}","action_queue_order":len(rows)+1,"created_at":created,"lane":lane.get("lane"),"action_kind":kind,"action_description":desc,"source_p701_id":lane.get("all_started_board_id"),"action_started":True,"action_status":"started_planning_only_blocked_execution","execution_started":False,"real_input_received":False,"evidence_received":False,"formal_decision_ready":False,"blocker_reason":"Real input and independently verifiable evidence are absent.","operator_action":"Continue planning only; do not execute or authorize.","completion_condition":"External input, evidence validation, formal review, and explicit authorization are recorded.","policy":"P702 is a planning-only action queue; downstream execution and authorization remain fail-closed."})
    summary={"action_queue_id":"p702::summary","action_queue_order":len(rows)+1,"created_at":created,"lane":"summary","action_queue_rows":len(rows),"action_started_rows":len(rows),"execution_started_rows":0,"real_input_received_rows":0,"evidence_received_rows":0,"formal_decision_ready_rows":0,"policy":"P702 records planned actions only."}
    OUT.write_text("".join(json.dumps(r,ensure_ascii=False,sort_keys=True)+"\n" for r in rows+[summary]),encoding="utf-8")
    report={"manifest_id":"P702","created_at":created,"local_only":True,"action_queue_rows":len(rows),"action_started_rows":len(rows),"execution_started_rows":0,"real_input_received_rows":0,"evidence_received_rows":0,"formal_decision_ready_rows":0,"artifact_jsonl":str(OUT.relative_to(ROOT)),"artifact_md":str(MD.relative_to(ROOT)),"policy":"P702 is planning-only; no execution or authorization."}
    REPORT.write_text(json.dumps(report,ensure_ascii=False,indent=2,sort_keys=True)+"\n",encoding="utf-8"); MD.write_text(f"# P702 pending-build action queue\n\nStarted planning actions: `{len(rows)}`. Execution remains blocked.\n",encoding="utf-8")
    print(json.dumps({"manifest_id":"P702","action_queue_rows":len(rows),"action_started_rows":len(rows),"execution_started_rows":0,"output":str(REPORT)},ensure_ascii=False)); return 0
if __name__=="__main__": raise SystemExit(main())
