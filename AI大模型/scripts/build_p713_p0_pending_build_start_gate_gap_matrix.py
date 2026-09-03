#!/usr/bin/env python3
"""Build P713 start-gate gap matrix from P712."""
from __future__ import annotations
import json
from datetime import datetime,timezone
from pathlib import Path
from build_p700_p0_real_input_pending_build_checklist import load_jsonl
ROOT=Path(__file__).resolve().parents[1]; SOURCE=ROOT/"datasets/governance/p712_p0_pending_build_start_gate_checklist.jsonl"; OUT=ROOT/"datasets/governance/p713_p0_pending_build_start_gate_gap_matrix.jsonl"; REPORT=ROOT/"reports/p713_p0_pending_build_start_gate_gap_matrix_report.json"; MD=ROOT/"reports/p713_p0_pending_build_start_gate_gap_matrix.md"
def main():
 created=datetime.now(timezone.utc).isoformat(); src=[r for r in load_jsonl(SOURCE) if r.get("lane")!="summary"]; rows=[]
 for i,r in enumerate(src,1):
  rows.append({"gap_matrix_id":f"p713::{r.get('start_gate_id')}","gap_matrix_order":i,"created_at":created,"lane":r.get("lane"),"source_p712_id":r.get("start_gate_id"),"gap_status":"open_all_prerequisites_missing","missing_input":True,"missing_evidence":True,"missing_owner":True,"missing_validator":True,"missing_authorization":True,"start_gate_passed":False,"execution_started":False,"formal_decision_ready":False,"blocker_reason":"All five start-gate prerequisites are missing.","operator_action":"Do not start; wait for independently verifiable prerequisites.","policy":"P713 is a gap matrix only; it does not create prerequisites or authorize execution."})
 summary={"gap_matrix_id":"p713::summary","gap_matrix_order":len(rows)+1,"created_at":created,"lane":"summary","gap_matrix_rows":len(rows),"all_prerequisites_missing_rows":len(rows),"start_gate_passed_rows":0,"execution_started_rows":0,"formal_decision_ready_rows":0,"policy":"P713 records missing prerequisites only."}
 OUT.write_text("".join(json.dumps(x,ensure_ascii=False,sort_keys=True)+"\n" for x in rows+[summary]),encoding="utf-8"); report={"manifest_id":"P713","created_at":created,"local_only":True,"gap_matrix_rows":len(rows),"all_prerequisites_missing_rows":len(rows),"start_gate_passed_rows":0,"execution_started_rows":0,"formal_decision_ready_rows":0,"artifact_jsonl":str(OUT.relative_to(ROOT)),"artifact_md":str(MD.relative_to(ROOT)),"policy":"P713 is planning-only and fail-closed."}; REPORT.write_text(json.dumps(report,ensure_ascii=False,indent=2,sort_keys=True)+"\n",encoding="utf-8"); MD.write_text(f"# P713 start-gate gap matrix\n\nRows: `{len(rows)}`. All five prerequisites missing in every row.\n",encoding="utf-8"); print(json.dumps({"manifest_id":"P713","gap_matrix_rows":len(rows),"all_prerequisites_missing_rows":len(rows),"output":str(REPORT)},ensure_ascii=False)); return 0
if __name__=="__main__": raise SystemExit(main())
