#!/usr/bin/env python3
"""Validate P718 evidence quarantine board."""
from __future__ import annotations
import json
from datetime import datetime,timezone
from pathlib import Path
from build_p700_p0_real_input_pending_build_checklist import load_json,load_jsonl
ROOT=Path(__file__).resolve().parents[1]; BOARD=ROOT/"datasets/governance/p718_p0_pending_build_evidence_quarantine_board.jsonl"; REPORT=ROOT/"reports/p718_p0_pending_build_evidence_quarantine_board_report.json"; OUT=ROOT/"reports/p718_p0_pending_build_evidence_quarantine_board_validation_report.json"
def main():
 rows=load_jsonl(BOARD); lanes=rows[:-1]; report=load_json(REPORT); failures=[]
 def f(c,x,o):
  if x: failures.append({"check":c,"observed":o})
 f("rows",len(lanes)!=5,len(lanes))
 for k in ("response_received_rows","evidence_quarantined_rows","provenance_checked_rows","integrity_checked_rows","evidence_released_rows","evidence_validated_rows","formal_decision_ready_rows"): f(k,report.get(k)!=0,report.get(k))
 for i,r in enumerate(lanes,1):
  for k in ("response_received","evidence_payload_present","evidence_quarantined","provenance_checked","integrity_checked","evidence_released","evidence_validated","formal_decision_ready"): f(f"row_{i}_{k}",r.get(k) is not False,r.get(k))
 result={"created_at":datetime.now(timezone.utc).isoformat(),"manifest_id":"P718","local_only":True,"success":not failures,"failure_count":len(failures),"failures":failures,"quarantine_rows":len(lanes),"response_received_rows":0,"evidence_quarantined_rows":0,"provenance_checked_rows":0,"integrity_checked_rows":0,"evidence_released_rows":0,"evidence_validated_rows":0,"formal_decision_ready_rows":0,"policy":"Validation only; P718 remains empty and fail-closed."}; OUT.write_text(json.dumps(result,ensure_ascii=False,indent=2,sort_keys=True)+"\n",encoding="utf-8"); print(json.dumps({"success":result["success"],"quarantine_rows":len(lanes),"evidence_quarantined_rows":0,"failures":len(failures),"output":str(OUT)},ensure_ascii=False)); return 0 if not failures else 1
if __name__=="__main__": raise SystemExit(main())
