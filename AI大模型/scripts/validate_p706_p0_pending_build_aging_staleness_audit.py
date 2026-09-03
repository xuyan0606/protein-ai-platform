#!/usr/bin/env python3
"""Validate P706 aging/staleness audit."""
from __future__ import annotations
import json
from datetime import datetime,timezone
from pathlib import Path
from build_p700_p0_real_input_pending_build_checklist import load_json,load_jsonl
ROOT=Path(__file__).resolve().parents[1]; BOARD=ROOT/"datasets/governance/p706_p0_pending_build_aging_staleness_audit.jsonl"; REPORT=ROOT/"reports/p706_p0_pending_build_aging_staleness_audit_report.json"; OUT=ROOT/"reports/p706_p0_pending_build_aging_staleness_audit_validation_report.json"
def main():
 rows=load_jsonl(BOARD); lanes=rows[:-1]; report=load_json(REPORT); failures=[]
 def f(c,x,o):
  if x: failures.append({"check":c,"observed":o})
 f("rows",len(lanes)!=15,len(lanes))
 for k in ("aging_reviewed_rows","staleness_resolved_rows","escalation_reviewed_rows","escalation_sent_rows","execution_started_rows","formal_decision_ready_rows"): f(k,report.get(k)!=0,report.get(k))
 for i,r in enumerate(lanes,1):
  for k in ("aging_reviewed","staleness_resolved","escalation_reviewed","escalation_sent","execution_started","formal_decision_ready"): f(f"row_{i}_{k}",r.get(k) is not False,r.get(k))
  f(f"row_{i}_status",r.get("aging_status")!="open_unreviewed_stale_unresolved",r.get("aging_status"))
 result={"created_at":datetime.now(timezone.utc).isoformat(),"manifest_id":"P706","local_only":True,"success":not failures,"failure_count":len(failures),"failures":failures,"aging_audit_rows":len(lanes),"aging_reviewed_rows":0,"staleness_resolved_rows":0,"escalation_reviewed_rows":0,"escalation_sent_rows":0,"execution_started_rows":0,"formal_decision_ready_rows":0,"policy":"Validation only; P706 remains unreviewed and fail-closed."}; OUT.write_text(json.dumps(result,ensure_ascii=False,indent=2,sort_keys=True)+"\n",encoding="utf-8"); print(json.dumps({"success":result["success"],"aging_audit_rows":len(lanes),"aging_reviewed_rows":0,"failures":len(failures),"output":str(OUT)},ensure_ascii=False)); return 0 if not failures else 1
if __name__=="__main__": raise SystemExit(main())
