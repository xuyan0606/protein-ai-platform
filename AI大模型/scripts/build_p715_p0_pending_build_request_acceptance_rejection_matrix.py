#!/usr/bin/env python3
"""Build P715 request acceptance/rejection matrix from P714 drafts."""
from __future__ import annotations
import json
from datetime import datetime,timezone
from pathlib import Path
from build_p700_p0_real_input_pending_build_checklist import load_jsonl
ROOT=Path(__file__).resolve().parents[1]; SOURCE=ROOT/"datasets/governance/p714_p0_pending_build_prerequisite_request_packet.jsonl"; OUT=ROOT/"datasets/governance/p715_p0_pending_build_request_acceptance_rejection_matrix.jsonl"; REPORT=ROOT/"reports/p715_p0_pending_build_request_acceptance_rejection_matrix_report.json"; MD=ROOT/"reports/p715_p0_pending_build_request_acceptance_rejection_matrix.md"
def main():
 created=datetime.now(timezone.utc).isoformat(); src=[r for r in load_jsonl(SOURCE) if r.get("lane")!="summary"]; rows=[]
 for i,r in enumerate(src,1):
  rows.append({"acceptance_matrix_id":f"p715::{r.get('request_packet_id')}","acceptance_matrix_order":i,"created_at":created,"lane":r.get("lane"),"source_p714_id":r.get("request_packet_id"),"acceptance_status":"empty_no_response","acceptance_criteria":["payload present","provenance attached","owner identified","validator passes"],"rejection_criteria":["placeholder or inferred value","missing provenance","unidentified owner","validator failure"],"response_received":False,"response_accepted":False,"response_rejected":False,"evidence_validated":False,"formal_decision_ready":False,"policy":"P715 is an acceptance/rejection matrix only; it does not receive, accept, reject, or authorize responses."})
 summary={"acceptance_matrix_id":"p715::summary","acceptance_matrix_order":len(rows)+1,"created_at":created,"lane":"summary","acceptance_matrix_rows":len(rows),"response_received_rows":0,"response_accepted_rows":0,"response_rejected_rows":0,"evidence_validated_rows":0,"formal_decision_ready_rows":0,"policy":"P715 records response handling criteria only."}
 OUT.write_text("".join(json.dumps(x,ensure_ascii=False,sort_keys=True)+"\n" for x in rows+[summary]),encoding="utf-8"); report={"manifest_id":"P715","created_at":created,"local_only":True,"acceptance_matrix_rows":len(rows),"response_received_rows":0,"response_accepted_rows":0,"response_rejected_rows":0,"evidence_validated_rows":0,"formal_decision_ready_rows":0,"artifact_jsonl":str(OUT.relative_to(ROOT)),"artifact_md":str(MD.relative_to(ROOT)),"policy":"P715 is planning-only and fail-closed."}; REPORT.write_text(json.dumps(report,ensure_ascii=False,indent=2,sort_keys=True)+"\n",encoding="utf-8"); MD.write_text(f"# P715 request acceptance/rejection matrix\n\nRows: `{len(rows)}`. Responses received: `0`.\n",encoding="utf-8"); print(json.dumps({"manifest_id":"P715","acceptance_matrix_rows":len(rows),"response_received_rows":0,"output":str(REPORT)},ensure_ascii=False)); return 0
if __name__=="__main__": raise SystemExit(main())
