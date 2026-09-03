#!/usr/bin/env python3
"""Build P709 completion-observation board from P708."""
from __future__ import annotations
import json
from datetime import datetime,timezone
from pathlib import Path
from build_p708_p0_pending_build_blocker_resolution_readiness_board import load_jsonl
ROOT=Path(__file__).resolve().parents[1]; SOURCE=ROOT/"datasets/governance/p708_p0_pending_build_blocker_resolution_readiness_board.jsonl"; OUT=ROOT/"datasets/governance/p709_p0_pending_build_completion_observation_board.jsonl"; REPORT=ROOT/"reports/p709_p0_pending_build_completion_observation_board_report.json"; MD=ROOT/"reports/p709_p0_pending_build_completion_observation_board.md"
def main():
 created=datetime.now(timezone.utc).isoformat(); src=[r for r in load_jsonl(SOURCE) if r.get("lane")!="summary"]; rows=[]
 for i,r in enumerate(src,1):
  rows.append({"completion_observation_id":f"p709::{r.get('resolution_board_id')}","completion_observation_order":i,"created_at":created,"lane":r.get("lane"),"action_kind":r.get("action_kind"),"source_p708_id":r.get("resolution_board_id"),"observation_status":"open_incomplete_blocked","completion_ready_observed":False,"closeout_ready":False,"formal_review_ready":False,"completion_ready":False,"blocker_resolved":False,"execution_started":False,"formal_decision_ready":False,"blocker_reason":"Required evidence, ownership, escalation outcome, and resolution are not complete.","next_unblocking_evidence":"All prerequisites independently evidenced and reviewed.","policy":"P709 observes completion readiness only; it does not close, approve, execute, or authorize."})
 summary={"completion_observation_id":"p709::summary","completion_observation_order":len(rows)+1,"created_at":created,"lane":"summary","completion_observation_rows":len(rows),"completion_ready_observed_rows":0,"closeout_ready_rows":0,"formal_review_ready_rows":0,"completion_ready_rows":0,"blocker_resolved_rows":0,"execution_started_rows":0,"formal_decision_ready_rows":0,"policy":"P709 records incomplete completion observations only."}
 OUT.write_text("".join(json.dumps(x,ensure_ascii=False,sort_keys=True)+"\n" for x in rows+[summary]),encoding="utf-8")
 report={"manifest_id":"P709","created_at":created,"local_only":True,"completion_observation_rows":len(rows),"completion_ready_observed_rows":0,"closeout_ready_rows":0,"formal_review_ready_rows":0,"completion_ready_rows":0,"blocker_resolved_rows":0,"execution_started_rows":0,"formal_decision_ready_rows":0,"artifact_jsonl":str(OUT.relative_to(ROOT)),"artifact_md":str(MD.relative_to(ROOT)),"policy":"P709 is planning-only and fail-closed."}
 REPORT.write_text(json.dumps(report,ensure_ascii=False,indent=2,sort_keys=True)+"\n",encoding="utf-8"); MD.write_text(f"# P709 completion observation board\n\nRows: `{len(rows)}`. Completion-ready observed: `0`.\n",encoding="utf-8"); print(json.dumps({"manifest_id":"P709","completion_observation_rows":len(rows),"completion_ready_rows":0,"output":str(REPORT)},ensure_ascii=False)); return 0
if __name__=="__main__": raise SystemExit(main())
