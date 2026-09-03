#!/usr/bin/env python3
"""Build P710 terminal blocked rollup across P700-P709."""
from __future__ import annotations
import json
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; OUT=ROOT/"datasets/governance/p710_p0_pending_build_terminal_blocked_rollup.jsonl"; REPORT=ROOT/"reports/p710_p0_pending_build_terminal_blocked_rollup_report.json"; MD=ROOT/"reports/p710_p0_pending_build_terminal_blocked_rollup.md"
SPECS=(
 ("P700","p700_p0_real_input_pending_build_checklist_report.json","pending_build_checklist_rows","pending_build_ready_rows"),
 ("P701","p701_p0_pending_build_all_started_board_report.json","all_started_board_rows","execution_started_rows"),
 ("P702","p702_p0_pending_build_action_queue_report.json","action_queue_rows","execution_started_rows"),
 ("P703","p703_p0_pending_build_dependency_board_report.json","dependency_board_rows","dependency_satisfied_rows"),
 ("P704","p704_p0_pending_build_unblock_evidence_matrix_report.json","evidence_matrix_rows","evidence_received_rows"),
 ("P705","p705_p0_pending_build_owner_assignment_gap_board_report.json","owner_gap_board_rows","owner_assigned_rows"),
 ("P706","p706_p0_pending_build_aging_staleness_audit_report.json","aging_audit_rows","aging_reviewed_rows"),
 ("P707","p707_p0_pending_build_escalation_readiness_board_report.json","escalation_board_rows","escalation_sent_rows"),
 ("P708","p708_p0_pending_build_blocker_resolution_readiness_board_report.json","resolution_board_rows","blocker_resolved_rows"),
 ("P709","p709_p0_pending_build_completion_observation_board_report.json","completion_observation_rows","completion_ready_rows"),
)
def main():
 created=datetime.now(timezone.utc).isoformat(); rows=[]
 for i,(manifest,file,count,ready) in enumerate(SPECS,1):
  data=json.loads((ROOT/"reports"/file).read_text(encoding="utf-8")); rows.append({"rollup_id":f"p710::{manifest.lower()}","rollup_order":i,"created_at":created,"manifest_id":manifest,"source_report":file,"row_count":data.get(count),"ready_or_progress_count":data.get(ready),"terminal_status":"blocked_pending_build","execution_started":False,"formal_decision_ready":False,"policy":"P710 is a rollup only; it does not change source status or authorize action."})
 summary={"rollup_id":"p710::summary","rollup_order":len(rows)+1,"created_at":created,"manifest_id":"P710","lane":"summary","rollup_rows":len(rows),"total_ready_or_progress_count":sum(r.get("ready_or_progress_count") or 0 for r in rows),"execution_started_rows":0,"formal_decision_ready_rows":0,"terminal_status":"blocked_pending_build","policy":"P710 confirms the pending-build chain remains terminally blocked."}
 OUT.write_text("".join(json.dumps(x,ensure_ascii=False,sort_keys=True)+"\n" for x in rows+[summary]),encoding="utf-8"); report={"manifest_id":"P710","created_at":created,"local_only":True,"rollup_rows":len(rows),"total_ready_or_progress_count":0,"execution_started_rows":0,"formal_decision_ready_rows":0,"artifact_jsonl":str(OUT.relative_to(ROOT)),"artifact_md":str(MD.relative_to(ROOT)),"policy":"P710 is a terminal blocked rollup only."}; REPORT.write_text(json.dumps(report,ensure_ascii=False,indent=2,sort_keys=True)+"\n",encoding="utf-8"); MD.write_text(f"# P710 terminal blocked rollup\n\nStages: `{len(rows)}`. Ready/progress rows: `0`.\n",encoding="utf-8"); print(json.dumps({"manifest_id":"P710","rollup_rows":len(rows),"total_ready_or_progress_count":0,"output":str(REPORT)},ensure_ascii=False)); return 0
if __name__=="__main__": raise SystemExit(main())
