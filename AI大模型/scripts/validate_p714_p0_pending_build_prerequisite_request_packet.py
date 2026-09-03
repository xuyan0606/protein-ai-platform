#!/usr/bin/env python3
"""Validate P714 local request packet draft."""
from __future__ import annotations
import json
from datetime import datetime,timezone
from pathlib import Path
from build_p700_p0_real_input_pending_build_checklist import load_json,load_jsonl
ROOT=Path(__file__).resolve().parents[1]; BOARD=ROOT/"datasets/governance/p714_p0_pending_build_prerequisite_request_packet.jsonl"; REPORT=ROOT/"reports/p714_p0_pending_build_prerequisite_request_packet_report.json"; OUT=ROOT/"reports/p714_p0_pending_build_prerequisite_request_packet_validation_report.json"
def main():
 rows=load_jsonl(BOARD); lanes=rows[:-1]; report=load_json(REPORT); failures=[]
 def f(c,x,o):
  if x: failures.append({"check":c,"observed":o})
 f("rows",len(lanes)!=5,len(lanes)); f("sent",report.get("request_sent_rows")!=0,report.get("request_sent_rows")); f("response",report.get("response_received_rows")!=0,report.get("response_received_rows"))
 for i,r in enumerate(lanes,1):
  f(f"row_{i}_status",r.get("packet_status")!="draft_not_sent",r.get("packet_status")); f(f"row_{i}_sent",r.get("request_sent") is not False,r.get("request_sent")); f(f"row_{i}_response",r.get("response_received") is not False,r.get("response_received")); f(f"row_{i}_materials",not r.get("requested_materials"),r.get("requested_materials"))
 result={"created_at":datetime.now(timezone.utc).isoformat(),"manifest_id":"P714","local_only":True,"success":not failures,"failure_count":len(failures),"failures":failures,"request_packet_rows":len(lanes),"request_sent_rows":0,"response_received_rows":0,"evidence_validated_rows":0,"formal_decision_ready_rows":0,"policy":"Validation only; P714 remains draft-only and fail-closed."}; OUT.write_text(json.dumps(result,ensure_ascii=False,indent=2,sort_keys=True)+"\n",encoding="utf-8"); print(json.dumps({"success":result["success"],"request_packet_rows":len(lanes),"request_sent_rows":0,"failures":len(failures),"output":str(OUT)},ensure_ascii=False)); return 0 if not failures else 1
if __name__=="__main__": raise SystemExit(main())
