#!/usr/bin/env python3
"""Build P719 decision-routing readiness from P718 quarantine rows."""
from __future__ import annotations
import json
from datetime import datetime,timezone
from pathlib import Path
from build_p700_p0_real_input_pending_build_checklist import load_jsonl
ROOT=Path(__file__).resolve().parents[1]; SOURCE=ROOT/"datasets/governance/p718_p0_pending_build_evidence_quarantine_board.jsonl"; OUT=ROOT/"datasets/governance/p719_p0_pending_build_decision_routing_readiness.jsonl"; REPORT=ROOT/"reports/p719_p0_pending_build_decision_routing_readiness_report.json"; MD=ROOT/"reports/p719_p0_pending_build_decision_routing_readiness.md"
ROUTES=("formal_review","evidence_adjudication","closeout_review")
def main():
 created=datetime.now(timezone.utc).isoformat(); src=[r for r in load_jsonl(SOURCE) if r.get("lane")!="summary"]; rows=[]
 for i,r in enumerate(src,1):
  rows.append({"routing_readiness_id":f"p719::{r.get('quarantine_id')}","routing_readiness_order":i,"created_at":created,"lane":r.get("lane"),"source_p718_id":r.get("quarantine_id"),"routing_status":"not_routable_quarantine_empty","candidate_routes":list(ROUTES),"evidence_released":False,"route_selected":False,"decision_route_executed":False,"routed_to_formal_review":False,"formal_decision_ready":False,"blocker_reason":"Evidence has not been received, quarantined, validated, or released.","policy":"P719 prepares route definitions only; it does not select, execute, or authorize a decision route."})
 summary={"routing_readiness_id":"p719::summary","routing_readiness_order":len(rows)+1,"created_at":created,"lane":"summary","routing_readiness_rows":len(rows),"route_selected_rows":0,"decision_route_executed_rows":0,"routed_to_formal_review_rows":0,"formal_decision_ready_rows":0,"policy":"P719 records unroutable states only."}
 OUT.write_text("".join(json.dumps(x,ensure_ascii=False,sort_keys=True)+"\n" for x in rows+[summary]),encoding="utf-8"); report={"manifest_id":"P719","created_at":created,"local_only":True,"routing_readiness_rows":len(rows),"route_selected_rows":0,"decision_route_executed_rows":0,"routed_to_formal_review_rows":0,"formal_decision_ready_rows":0,"artifact_jsonl":str(OUT.relative_to(ROOT)),"artifact_md":str(MD.relative_to(ROOT)),"policy":"P719 is planning-only and fail-closed."}; REPORT.write_text(json.dumps(report,ensure_ascii=False,indent=2,sort_keys=True)+"\n",encoding="utf-8"); MD.write_text(f"# P719 decision-routing readiness\n\nRows: `{len(rows)}`. Routes selected: `0`.\n",encoding="utf-8"); print(json.dumps({"manifest_id":"P719","routing_readiness_rows":len(rows),"route_selected_rows":0,"output":str(REPORT)},ensure_ascii=False)); return 0
if __name__=="__main__": raise SystemExit(main())
