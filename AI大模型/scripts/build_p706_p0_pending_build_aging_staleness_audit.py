#!/usr/bin/env python3
"""Build P706 aging/staleness audit from P705 assignment gaps."""
from __future__ import annotations
import json
from datetime import datetime,timezone
from pathlib import Path
from build_p705_p0_pending_build_owner_assignment_gap_board import load_jsonl
ROOT=Path(__file__).resolve().parents[1]; SOURCE=ROOT/"datasets/governance/p705_p0_pending_build_owner_assignment_gap_board.jsonl"; OUT=ROOT/"datasets/governance/p706_p0_pending_build_aging_staleness_audit.jsonl"; REPORT=ROOT/"reports/p706_p0_pending_build_aging_staleness_audit_report.json"; MD=ROOT/"reports/p706_p0_pending_build_aging_staleness_audit.md"
def main():
 created=datetime.now(timezone.utc).isoformat(); src=[r for r in load_jsonl(SOURCE) if r.get("lane")!="summary"]; rows=[]
 for i,r in enumerate(src,1):
  rows.append({"aging_audit_id":f"p706::{r.get('owner_gap_board_id')}","aging_audit_order":i,"created_at":created,"lane":r.get("lane"),"action_kind":r.get("action_kind"),"source_p705_id":r.get("owner_gap_board_id"),"aging_status":"open_unreviewed_stale_unresolved","aging_reviewed":False,"staleness_resolved":False,"escalation_reviewed":False,"escalation_sent":False,"blocker_reason":"Owner assignment and qualifying evidence remain absent; aging cannot close the blocker.","next_review_condition":"Approved owner plus real evidence receipt and validator result.","execution_started":False,"formal_decision_ready":False,"policy":"P706 is an aging/staleness audit only; it does not assign, escalate, execute, or authorize."})
 summary={"aging_audit_id":"p706::summary","aging_audit_order":len(rows)+1,"created_at":created,"lane":"summary","aging_audit_rows":len(rows),"aging_reviewed_rows":0,"staleness_resolved_rows":0,"escalation_reviewed_rows":0,"escalation_sent_rows":0,"execution_started_rows":0,"formal_decision_ready_rows":0,"policy":"P706 records aging gaps only."}
 OUT.write_text("".join(json.dumps(x,ensure_ascii=False,sort_keys=True)+"\n" for x in rows+[summary]),encoding="utf-8")
 report={"manifest_id":"P706","created_at":created,"local_only":True,"aging_audit_rows":len(rows),"aging_reviewed_rows":0,"staleness_resolved_rows":0,"escalation_reviewed_rows":0,"escalation_sent_rows":0,"execution_started_rows":0,"formal_decision_ready_rows":0,"artifact_jsonl":str(OUT.relative_to(ROOT)),"artifact_md":str(MD.relative_to(ROOT)),"policy":"P706 is planning-only and fail-closed."}
 REPORT.write_text(json.dumps(report,ensure_ascii=False,indent=2,sort_keys=True)+"\n",encoding="utf-8"); MD.write_text(f"# P706 pending-build aging/staleness audit\n\nRows: `{len(rows)}`. Aging reviewed: `0`; staleness resolved: `0`.\n",encoding="utf-8"); print(json.dumps({"manifest_id":"P706","aging_audit_rows":len(rows),"aging_reviewed_rows":0,"output":str(REPORT)},ensure_ascii=False)); return 0
if __name__=="__main__": raise SystemExit(main())
