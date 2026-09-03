#!/usr/bin/env python3
"""Build P708 blocker-resolution readiness board from P707."""
from __future__ import annotations
import json
from datetime import datetime,timezone
from pathlib import Path
from build_p707_p0_pending_build_escalation_readiness_board import load_jsonl
ROOT=Path(__file__).resolve().parents[1]; SOURCE=ROOT/"datasets/governance/p707_p0_pending_build_escalation_readiness_board.jsonl"; OUT=ROOT/"datasets/governance/p708_p0_pending_build_blocker_resolution_readiness_board.jsonl"; REPORT=ROOT/"reports/p708_p0_pending_build_blocker_resolution_readiness_board_report.json"; MD=ROOT/"reports/p708_p0_pending_build_blocker_resolution_readiness_board.md"
def main():
 created=datetime.now(timezone.utc).isoformat(); src=[r for r in load_jsonl(SOURCE) if r.get("lane")!="summary"]; rows=[]
 for i,r in enumerate(src,1):
  rows.append({"resolution_board_id":f"p708::{r.get('escalation_board_id')}","resolution_board_order":i,"created_at":created,"lane":r.get("lane"),"action_kind":r.get("action_kind"),"source_p707_id":r.get("escalation_board_id"),"resolution_status":"open_unresolved_blocked","evidence_ready":False,"owner_ready":False,"escalation_ready":False,"blocker_resolved":False,"closeout_ready":False,"completion_ready":False,"execution_started":False,"formal_decision_ready":False,"blocker_reason":"Evidence, owner, and escalation prerequisites remain unsatisfied.","next_unblocking_evidence":"Validated external input, approved owner acknowledgement, and reviewed escalation outcome.","policy":"P708 is a readiness assessment only; it does not resolve blockers or authorize downstream actions."})
 summary={"resolution_board_id":"p708::summary","resolution_board_order":len(rows)+1,"created_at":created,"lane":"summary","resolution_board_rows":len(rows),"evidence_ready_rows":0,"owner_ready_rows":0,"escalation_ready_rows":0,"blocker_resolved_rows":0,"closeout_ready_rows":0,"completion_ready_rows":0,"execution_started_rows":0,"formal_decision_ready_rows":0,"policy":"P708 records unresolved blockers only."}
 OUT.write_text("".join(json.dumps(x,ensure_ascii=False,sort_keys=True)+"\n" for x in rows+[summary]),encoding="utf-8")
 report={"manifest_id":"P708","created_at":created,"local_only":True,"resolution_board_rows":len(rows),"evidence_ready_rows":0,"owner_ready_rows":0,"escalation_ready_rows":0,"blocker_resolved_rows":0,"closeout_ready_rows":0,"completion_ready_rows":0,"execution_started_rows":0,"formal_decision_ready_rows":0,"artifact_jsonl":str(OUT.relative_to(ROOT)),"artifact_md":str(MD.relative_to(ROOT)),"policy":"P708 is planning-only and fail-closed."}
 REPORT.write_text(json.dumps(report,ensure_ascii=False,indent=2,sort_keys=True)+"\n",encoding="utf-8"); MD.write_text(f"# P708 blocker-resolution readiness board\n\nRows: `{len(rows)}`. Blockers resolved: `0`.\n",encoding="utf-8"); print(json.dumps({"manifest_id":"P708","resolution_board_rows":len(rows),"blocker_resolved_rows":0,"output":str(REPORT)},ensure_ascii=False)); return 0
if __name__=="__main__": raise SystemExit(main())
