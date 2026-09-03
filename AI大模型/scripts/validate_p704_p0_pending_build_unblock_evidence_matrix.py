#!/usr/bin/env python3
"""Validate P704 evidence-gap matrix."""
from __future__ import annotations
import json
from datetime import datetime,timezone
from pathlib import Path
from build_p700_p0_real_input_pending_build_checklist import load_json,load_jsonl
ROOT=Path(__file__).resolve().parents[1]; BOARD=ROOT/"datasets/governance/p704_p0_pending_build_unblock_evidence_matrix.jsonl"; REPORT=ROOT/"reports/p704_p0_pending_build_unblock_evidence_matrix_report.json"; OUT=ROOT/"reports/p704_p0_pending_build_unblock_evidence_matrix_validation_report.json"
def main():
 rows=load_jsonl(BOARD); lanes=rows[:-1]; report=load_json(REPORT); failures=[]
 def f(c,x,o):
  if x: failures.append({"check":c,"observed":o})
 f("rows",len(lanes)!=15,len(lanes));
 for key in ("evidence_requested_rows","evidence_received_rows","evidence_validated_rows","dependency_unblocked_rows","execution_allowed_rows"): f(key,report.get(key)!=0,report.get(key))
 for i,r in enumerate(lanes,1):
  for key in ("evidence_requested","evidence_received","evidence_validated","dependency_unblocked","execution_allowed"): f(f"row_{i}_{key}",r.get(key) is not False,r.get(key))
  f(f"row_{i}_required",not r.get("required_unblocking_evidence"),r.get("required_unblocking_evidence"))
 result={"created_at":datetime.now(timezone.utc).isoformat(),"manifest_id":"P704","local_only":True,"success":not failures,"failure_count":len(failures),"failures":failures,"evidence_matrix_rows":len(lanes),"evidence_requested_rows":0,"evidence_received_rows":0,"evidence_validated_rows":0,"dependency_unblocked_rows":0,"execution_allowed_rows":0,"policy":"Validation only; P704 remains empty and fail-closed."}; OUT.write_text(json.dumps(result,ensure_ascii=False,indent=2,sort_keys=True)+"\n",encoding="utf-8"); print(json.dumps({"success":result["success"],"evidence_matrix_rows":len(lanes),"evidence_received_rows":0,"failures":len(failures),"output":str(OUT)},ensure_ascii=False)); return 0 if not failures else 1
if __name__=="__main__": raise SystemExit(main())
