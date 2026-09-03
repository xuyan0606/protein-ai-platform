#!/usr/bin/env python3
"""Build P716 response-receive preflight from P715."""
from __future__ import annotations
import json
from datetime import datetime,timezone
from pathlib import Path
from build_p700_p0_real_input_pending_build_checklist import load_jsonl
ROOT=Path(__file__).resolve().parents[1]; SOURCE=ROOT/"datasets/governance/p715_p0_pending_build_request_acceptance_rejection_matrix.jsonl"; OUT=ROOT/"datasets/governance/p716_p0_pending_build_response_receive_preflight.jsonl"; REPORT=ROOT/"reports/p716_p0_pending_build_response_receive_preflight_report.json"; MD=ROOT/"reports/p716_p0_pending_build_response_receive_preflight.md"
def main():
 created=datetime.now(timezone.utc).isoformat(); src=[r for r in load_jsonl(SOURCE) if r.get("lane")!="summary"]; rows=[]
 for i,r in enumerate(src,1):
  rows.append({"preflight_id":f"p716::{r.get('acceptance_matrix_id')}","preflight_order":i,"created_at":created,"lane":r.get("lane"),"source_p715_id":r.get("acceptance_matrix_id"),"preflight_status":"not_executed_no_response","receive_channel_ready":False,"payload_complete":False,"source_identity_verified":False,"duplicate_check_passed":False,"receive_preflight_executed":False,"response_received":False,"evidence_validated":False,"formal_decision_ready":False,"blocker_reason":"No response exists to preflight.","policy":"P716 is a receive preflight definition only; it does not receive, mutate, or authorize input."})
 summary={"preflight_id":"p716::summary","preflight_order":len(rows)+1,"created_at":created,"lane":"summary","preflight_rows":len(rows),"receive_preflight_executed_rows":0,"response_received_rows":0,"evidence_validated_rows":0,"formal_decision_ready_rows":0,"policy":"P716 records receive preflight gaps only."}
 OUT.write_text("".join(json.dumps(x,ensure_ascii=False,sort_keys=True)+"\n" for x in rows+[summary]),encoding="utf-8"); report={"manifest_id":"P716","created_at":created,"local_only":True,"preflight_rows":len(rows),"receive_preflight_executed_rows":0,"response_received_rows":0,"evidence_validated_rows":0,"formal_decision_ready_rows":0,"artifact_jsonl":str(OUT.relative_to(ROOT)),"artifact_md":str(MD.relative_to(ROOT)),"policy":"P716 is planning-only and fail-closed."}; REPORT.write_text(json.dumps(report,ensure_ascii=False,indent=2,sort_keys=True)+"\n",encoding="utf-8"); MD.write_text(f"# P716 response receive preflight\n\nRows: `{len(rows)}`. Preflight executed: `0`.\n",encoding="utf-8"); print(json.dumps({"manifest_id":"P716","preflight_rows":len(rows),"receive_preflight_executed_rows":0,"output":str(REPORT)},ensure_ascii=False)); return 0
if __name__=="__main__": raise SystemExit(main())
