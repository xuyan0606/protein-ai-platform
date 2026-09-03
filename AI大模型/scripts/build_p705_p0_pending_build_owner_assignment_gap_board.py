#!/usr/bin/env python3
"""Build P705 owner-assignment gap board from P704 evidence rows."""
from __future__ import annotations
import json
from datetime import datetime,timezone
from pathlib import Path
from build_p704_p0_pending_build_unblock_evidence_matrix import load_jsonl
ROOT=Path(__file__).resolve().parents[1]; SOURCE=ROOT/"datasets/governance/p704_p0_pending_build_unblock_evidence_matrix.jsonl"; OUT=ROOT/"datasets/governance/p705_p0_pending_build_owner_assignment_gap_board.jsonl"; REPORT=ROOT/"reports/p705_p0_pending_build_owner_assignment_gap_board_report.json"; MD=ROOT/"reports/p705_p0_pending_build_owner_assignment_gap_board.md"
def main():
 created=datetime.now(timezone.utc).isoformat(); src=[r for r in load_jsonl(SOURCE) if r.get("lane")!="summary"]; rows=[]
 for i,r in enumerate(src,1):
  rows.append({"owner_gap_board_id":f"p705::{r.get('evidence_matrix_id')}","owner_gap_board_order":i,"created_at":created,"lane":r.get("lane"),"action_kind":r.get("action_kind"),"source_p704_id":r.get("evidence_matrix_id"),"owner_assignment_status":"open_empty_unassigned_blocked","owner_assigned":False,"owner_acknowledged":False,"operator_dispatched":False,"escalation_reviewed":False,"escalation_sent":False,"blocker_reason":"No approved owner or operator assignment exists while required evidence is absent.","next_action":"Assign an approved owner only after qualifying input/evidence arrives.","execution_started":False,"formal_decision_ready":False,"policy":"P705 is an assignment-gap board only; it does not dispatch, escalate, execute, or authorize."})
 summary={"owner_gap_board_id":"p705::summary","owner_gap_board_order":len(rows)+1,"created_at":created,"lane":"summary","owner_gap_board_rows":len(rows),"owner_assigned_rows":0,"owner_acknowledged_rows":0,"operator_dispatched_rows":0,"escalation_reviewed_rows":0,"escalation_sent_rows":0,"execution_started_rows":0,"formal_decision_ready_rows":0,"policy":"P705 records assignment gaps only."}
 OUT.write_text("".join(json.dumps(x,ensure_ascii=False,sort_keys=True)+"\n" for x in rows+[summary]),encoding="utf-8")
 report={"manifest_id":"P705","created_at":created,"local_only":True,"owner_gap_board_rows":len(rows),"owner_assigned_rows":0,"owner_acknowledged_rows":0,"operator_dispatched_rows":0,"escalation_reviewed_rows":0,"escalation_sent_rows":0,"execution_started_rows":0,"formal_decision_ready_rows":0,"artifact_jsonl":str(OUT.relative_to(ROOT)),"artifact_md":str(MD.relative_to(ROOT)),"policy":"P705 is planning-only and fail-closed."}
 REPORT.write_text(json.dumps(report,ensure_ascii=False,indent=2,sort_keys=True)+"\n",encoding="utf-8"); MD.write_text(f"# P705 pending-build owner assignment gap board\n\nRows: `{len(rows)}`. Owners assigned: `0`.\n",encoding="utf-8"); print(json.dumps({"manifest_id":"P705","owner_gap_board_rows":len(rows),"owner_assigned_rows":0,"output":str(REPORT)},ensure_ascii=False)); return 0
if __name__=="__main__": raise SystemExit(main())
