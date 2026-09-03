#!/usr/bin/env python3
"""Build P707 escalation-readiness board from P706 aging audit."""
from __future__ import annotations
import json
from datetime import datetime,timezone
from pathlib import Path
from build_p706_p0_pending_build_aging_staleness_audit import load_jsonl
ROOT=Path(__file__).resolve().parents[1]; SOURCE=ROOT/"datasets/governance/p706_p0_pending_build_aging_staleness_audit.jsonl"; OUT=ROOT/"datasets/governance/p707_p0_pending_build_escalation_readiness_board.jsonl"; REPORT=ROOT/"reports/p707_p0_pending_build_escalation_readiness_board_report.json"; MD=ROOT/"reports/p707_p0_pending_build_escalation_readiness_board.md"
def main():
 created=datetime.now(timezone.utc).isoformat(); src=[r for r in load_jsonl(SOURCE) if r.get("lane")!="summary"]; rows=[]
 for i,r in enumerate(src,1):
  rows.append({"escalation_board_id":f"p707::{r.get('aging_audit_id')}","escalation_board_order":i,"created_at":created,"lane":r.get("lane"),"action_kind":r.get("action_kind"),"source_p706_id":r.get("aging_audit_id"),"escalation_status":"open_unprepared_blocked","escalation_triggered":False,"escalation_package_prepared":False,"escalation_reviewed":False,"escalation_sent":False,"escalation_acknowledged":False,"blocker_reason":"No qualifying evidence or approved owner exists to trigger an escalation.","next_unblocking_evidence":"Approved owner, real evidence receipt, and a reviewed escalation package.","execution_started":False,"formal_decision_ready":False,"policy":"P707 is an escalation-readiness board only; it does not send, acknowledge, execute, or authorize."})
 summary={"escalation_board_id":"p707::summary","escalation_board_order":len(rows)+1,"created_at":created,"lane":"summary","escalation_board_rows":len(rows),"escalation_triggered_rows":0,"escalation_package_prepared_rows":0,"escalation_reviewed_rows":0,"escalation_sent_rows":0,"escalation_acknowledged_rows":0,"execution_started_rows":0,"formal_decision_ready_rows":0,"policy":"P707 records escalation gaps only."}
 OUT.write_text("".join(json.dumps(x,ensure_ascii=False,sort_keys=True)+"\n" for x in rows+[summary]),encoding="utf-8")
 report={"manifest_id":"P707","created_at":created,"local_only":True,"escalation_board_rows":len(rows),"escalation_triggered_rows":0,"escalation_package_prepared_rows":0,"escalation_reviewed_rows":0,"escalation_sent_rows":0,"escalation_acknowledged_rows":0,"execution_started_rows":0,"formal_decision_ready_rows":0,"artifact_jsonl":str(OUT.relative_to(ROOT)),"artifact_md":str(MD.relative_to(ROOT)),"policy":"P707 is planning-only and fail-closed."}
 REPORT.write_text(json.dumps(report,ensure_ascii=False,indent=2,sort_keys=True)+"\n",encoding="utf-8"); MD.write_text(f"# P707 pending-build escalation readiness board\n\nRows: `{len(rows)}`. Escalations sent: `0`.\n",encoding="utf-8"); print(json.dumps({"manifest_id":"P707","escalation_board_rows":len(rows),"escalation_sent_rows":0,"output":str(REPORT)},ensure_ascii=False)); return 0
if __name__=="__main__": raise SystemExit(main())
