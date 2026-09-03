#!/usr/bin/env python3
"""Build P703 dependency board for P702 planning actions."""
from __future__ import annotations
import json
from datetime import datetime, timezone
from pathlib import Path
from build_p702_p0_pending_build_action_queue import load_jsonl
ROOT=Path(__file__).resolve().parents[1]; SOURCE=ROOT/"datasets/governance/p702_p0_pending_build_action_queue.jsonl"; OUT=ROOT/"datasets/governance/p703_p0_pending_build_dependency_board.jsonl"; REPORT=ROOT/"reports/p703_p0_pending_build_dependency_board_report.json"; MD=ROOT/"reports/p703_p0_pending_build_dependency_board.md"
def main():
    created=datetime.now(timezone.utc).isoformat(); src=[r for r in load_jsonl(SOURCE) if r.get("lane")!="summary"]; rows=[]
    for i,r in enumerate(src,1):
        kind=r.get("action_kind"); dep={"structure":"P700 checklist definition","evidence":"structure action registration","validation":"evidence action registration"}[kind]
        rows.append({"dependency_board_id":f"p703::{r.get('action_queue_id')}","dependency_board_order":i,"created_at":created,"lane":r.get("lane"),"action_kind":kind,"source_p702_action_id":r.get("action_queue_id"),"dependency_status":"blocked_pending_dependency","dependency_started":True,"dependency_satisfied":False,"prerequisite":dep,"next_unblocking_evidence":r.get("next_unblocking_evidence") or "Real input and independently verifiable evidence.","execution_started":False,"formal_decision_ready":False,"policy":"P703 is a planning dependency board only; no execution or authorization is performed."})
    summary={"dependency_board_id":"p703::summary","dependency_board_order":len(rows)+1,"created_at":created,"lane":"summary","dependency_board_rows":len(rows),"dependency_started_rows":len(rows),"dependency_satisfied_rows":0,"execution_started_rows":0,"formal_decision_ready_rows":0,"policy":"P703 records dependencies only."}
    OUT.write_text("".join(json.dumps(x,ensure_ascii=False,sort_keys=True)+"\n" for x in rows+[summary]),encoding="utf-8")
    report={"manifest_id":"P703","created_at":created,"local_only":True,"dependency_board_rows":len(rows),"dependency_started_rows":len(rows),"dependency_satisfied_rows":0,"execution_started_rows":0,"formal_decision_ready_rows":0,"artifact_jsonl":str(OUT.relative_to(ROOT)),"artifact_md":str(MD.relative_to(ROOT)),"policy":"P703 is planning-only and fail-closed."}
    REPORT.write_text(json.dumps(report,ensure_ascii=False,indent=2,sort_keys=True)+"\n",encoding="utf-8"); MD.write_text(f"# P703 pending-build dependency board\n\nDependency rows: `{len(rows)}`. Satisfied: `0`.\n",encoding="utf-8"); print(json.dumps({"manifest_id":"P703","dependency_board_rows":len(rows),"dependency_satisfied_rows":0,"output":str(REPORT)},ensure_ascii=False)); return 0
if __name__=="__main__": raise SystemExit(main())
