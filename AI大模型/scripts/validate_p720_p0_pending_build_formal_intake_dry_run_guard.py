#!/usr/bin/env python3
"""Validate P720 formal-intake dry-run guard."""
from __future__ import annotations
import json
from datetime import datetime,timezone
from pathlib import Path
from build_p700_p0_real_input_pending_build_checklist import load_json,load_jsonl
ROOT=Path(__file__).resolve().parents[1]; BOARD=ROOT/"datasets/governance/p720_p0_pending_build_formal_intake_dry_run_guard.jsonl"; REPORT=ROOT/"reports/p720_p0_pending_build_formal_intake_dry_run_guard_report.json"; OUT=ROOT/"reports/p720_p0_pending_build_formal_intake_dry_run_guard_validation_report.json"
def main():
 rows=load_jsonl(BOARD); lanes=rows[:-1]; report=load_json(REPORT); failures=[]
 def f(c,x,o):
  if x: failures.append({"check":c,"observed":o})
 f("rows",len(lanes)!=5,len(lanes))
 for k in ("formal_intake_dry_run_executed_rows","formal_intake_dry_run_passed_rows","formal_intake_written_rows","formal_decision_ready_rows"): f(k,report.get(k)!=0,report.get(k))
 for i,r in enumerate(lanes,1):
  for k in ("required_real_input","required_evidence_release","required_route_execution","required_validator_pass"): f(f"row_{i}_{k}",r.get(k) is not True,r.get(k))
  for k in ("formal_intake_dry_run_executed","formal_intake_dry_run_passed","formal_intake_written","formal_decision_ready"): f(f"row_{i}_{k}",r.get(k) is not False,r.get(k))
 result={"created_at":datetime.now(timezone.utc).isoformat(),"manifest_id":"P720","local_only":True,"success":not failures,"failure_count":len(failures),"failures":failures,"intake_guard_rows":len(lanes),"formal_intake_dry_run_executed_rows":0,"formal_intake_dry_run_passed_rows":0,"formal_intake_written_rows":0,"formal_decision_ready_rows":0,"policy":"Validation only; P720 remains blocked and fail-closed."}; OUT.write_text(json.dumps(result,ensure_ascii=False,indent=2,sort_keys=True)+"\n",encoding="utf-8"); print(json.dumps({"success":result["success"],"intake_guard_rows":len(lanes),"formal_intake_dry_run_executed_rows":0,"failures":len(failures),"output":str(OUT)},ensure_ascii=False)); return 0 if not failures else 1
if __name__=="__main__": raise SystemExit(main())
