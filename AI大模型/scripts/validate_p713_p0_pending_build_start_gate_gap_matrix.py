#!/usr/bin/env python3
"""Validate P713 start-gate gap matrix."""
from __future__ import annotations
import json
from datetime import datetime,timezone
from pathlib import Path
from build_p700_p0_real_input_pending_build_checklist import load_json,load_jsonl
ROOT=Path(__file__).resolve().parents[1]; BOARD=ROOT/"datasets/governance/p713_p0_pending_build_start_gate_gap_matrix.jsonl"; REPORT=ROOT/"reports/p713_p0_pending_build_start_gate_gap_matrix_report.json"; OUT=ROOT/"reports/p713_p0_pending_build_start_gate_gap_matrix_validation_report.json"
def main():
 rows=load_jsonl(BOARD); lanes=rows[:-1]; report=load_json(REPORT); failures=[]
 def f(c,x,o):
  if x: failures.append({"check":c,"observed":o})
 f("rows",len(lanes)!=5,len(lanes)); f("missing",report.get("all_prerequisites_missing_rows")!=5,report.get("all_prerequisites_missing_rows")); f("passed",report.get("start_gate_passed_rows")!=0,report.get("start_gate_passed_rows"))
 for i,r in enumerate(lanes,1):
  for k in ("missing_input","missing_evidence","missing_owner","missing_validator","missing_authorization"): f(f"row_{i}_{k}",r.get(k) is not True,r.get(k))
  for k in ("start_gate_passed","execution_started","formal_decision_ready"): f(f"row_{i}_{k}",r.get(k) is not False,r.get(k))
 result={"created_at":datetime.now(timezone.utc).isoformat(),"manifest_id":"P713","local_only":True,"success":not failures,"failure_count":len(failures),"failures":failures,"gap_matrix_rows":len(lanes),"all_prerequisites_missing_rows":5,"start_gate_passed_rows":0,"execution_started_rows":0,"formal_decision_ready_rows":0,"policy":"Validation only; P713 confirms all prerequisites remain missing."}; OUT.write_text(json.dumps(result,ensure_ascii=False,indent=2,sort_keys=True)+"\n",encoding="utf-8"); print(json.dumps({"success":result["success"],"gap_matrix_rows":len(lanes),"all_prerequisites_missing_rows":5,"failures":len(failures),"output":str(OUT)},ensure_ascii=False)); return 0 if not failures else 1
if __name__=="__main__": raise SystemExit(main())
