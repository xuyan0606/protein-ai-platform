#!/usr/bin/env python3
"""Build P704 unblock-evidence matrix from P703 dependencies."""
from __future__ import annotations
import json
from datetime import datetime,timezone
from pathlib import Path
from build_p703_p0_pending_build_dependency_board import load_jsonl
ROOT=Path(__file__).resolve().parents[1]; SOURCE=ROOT/"datasets/governance/p703_p0_pending_build_dependency_board.jsonl"; OUT=ROOT/"datasets/governance/p704_p0_pending_build_unblock_evidence_matrix.jsonl"; REPORT=ROOT/"reports/p704_p0_pending_build_unblock_evidence_matrix_report.json"; MD=ROOT/"reports/p704_p0_pending_build_unblock_evidence_matrix.md"
EVIDENCE={"structure":"Approved artifact schema and target-file definition","evidence":"Real operator/external input plus provenance-bearing evidence","validation":"Validator output proving required fields and provenance"}
def main():
 created=datetime.now(timezone.utc).isoformat(); src=[r for r in load_jsonl(SOURCE) if r.get("lane")!="summary"]; rows=[]
 for i,r in enumerate(src,1):
  kind=r.get("action_kind"); rows.append({"evidence_matrix_id":f"p704::{r.get('source_p702_action_id')}","evidence_matrix_order":i,"created_at":created,"lane":r.get("lane"),"action_kind":kind,"source_p703_dependency_id":r.get("dependency_board_id"),"required_unblocking_evidence":EVIDENCE.get(kind),"evidence_requested":False,"evidence_received":False,"evidence_validated":False,"dependency_unblocked":False,"execution_allowed":False,"blocker_reason":"No qualifying external input or evidence receipt exists.","operator_action":"Keep evidence slot empty; do not infer, fabricate, or authorize.","policy":"P704 is a local evidence-gap matrix only; no intake, validation, execution, or authorization is performed."})
 summary={"evidence_matrix_id":"p704::summary","evidence_matrix_order":len(rows)+1,"created_at":created,"lane":"summary","evidence_matrix_rows":len(rows),"evidence_requested_rows":0,"evidence_received_rows":0,"evidence_validated_rows":0,"dependency_unblocked_rows":0,"execution_allowed_rows":0,"policy":"P704 records evidence gaps only."}
 OUT.write_text("".join(json.dumps(x,ensure_ascii=False,sort_keys=True)+"\n" for x in rows+[summary]),encoding="utf-8")
 report={"manifest_id":"P704","created_at":created,"local_only":True,"evidence_matrix_rows":len(rows),"evidence_requested_rows":0,"evidence_received_rows":0,"evidence_validated_rows":0,"dependency_unblocked_rows":0,"execution_allowed_rows":0,"artifact_jsonl":str(OUT.relative_to(ROOT)),"artifact_md":str(MD.relative_to(ROOT)),"policy":"P704 is planning-only and fail-closed."}
 REPORT.write_text(json.dumps(report,ensure_ascii=False,indent=2,sort_keys=True)+"\n",encoding="utf-8"); MD.write_text(f"# P704 pending-build unblock evidence matrix\n\nRows: `{len(rows)}`. Evidence received/validated: `0`.\n",encoding="utf-8"); print(json.dumps({"manifest_id":"P704","evidence_matrix_rows":len(rows),"evidence_received_rows":0,"dependency_unblocked_rows":0,"output":str(REPORT)},ensure_ascii=False)); return 0
if __name__=="__main__": raise SystemExit(main())
