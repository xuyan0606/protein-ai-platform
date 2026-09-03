#!/usr/bin/env python3
"""Build P717 response schema contract from P716 preflight."""
from __future__ import annotations
import json
from datetime import datetime,timezone
from pathlib import Path
from build_p700_p0_real_input_pending_build_checklist import load_jsonl
ROOT=Path(__file__).resolve().parents[1]; SOURCE=ROOT/"datasets/governance/p716_p0_pending_build_response_receive_preflight.jsonl"; OUT=ROOT/"datasets/governance/p717_p0_pending_build_response_schema_contract.jsonl"; REPORT=ROOT/"reports/p717_p0_pending_build_response_schema_contract_report.json"; MD=ROOT/"reports/p717_p0_pending_build_response_schema_contract.md"
FIELDS=("response_id","lane","payload","source_identity","provenance","received_at","owner_id")
def main():
 created=datetime.now(timezone.utc).isoformat(); src=[r for r in load_jsonl(SOURCE) if r.get("lane")!="summary"]; rows=[]
 for i,r in enumerate(src,1):
  rows.append({"schema_contract_id":f"p717::{r.get('preflight_id')}","schema_contract_order":i,"created_at":created,"lane":r.get("lane"),"source_p716_id":r.get("preflight_id"),"contract_status":"defined_unpopulated","required_fields":list(FIELDS),"field_types":{"response_id":"string","lane":"string","payload":"object","source_identity":"string","provenance":"object","received_at":"timestamp","owner_id":"string"},"schema_validated":False,"response_received":False,"evidence_validated":False,"formal_decision_ready":False,"rejection_rule":"Reject missing, mismatched, unverifiable, or inferred fields.","policy":"P717 defines a response contract only; it does not receive, validate, or authorize a response."})
 summary={"schema_contract_id":"p717::summary","schema_contract_order":len(rows)+1,"created_at":created,"lane":"summary","schema_contract_rows":len(rows),"schema_validated_rows":0,"response_received_rows":0,"evidence_validated_rows":0,"formal_decision_ready_rows":0,"policy":"P717 records schema definitions only."}
 OUT.write_text("".join(json.dumps(x,ensure_ascii=False,sort_keys=True)+"\n" for x in rows+[summary]),encoding="utf-8"); report={"manifest_id":"P717","created_at":created,"local_only":True,"schema_contract_rows":len(rows),"schema_validated_rows":0,"response_received_rows":0,"evidence_validated_rows":0,"formal_decision_ready_rows":0,"artifact_jsonl":str(OUT.relative_to(ROOT)),"artifact_md":str(MD.relative_to(ROOT)),"policy":"P717 is planning-only and fail-closed."}; REPORT.write_text(json.dumps(report,ensure_ascii=False,indent=2,sort_keys=True)+"\n",encoding="utf-8"); MD.write_text(f"# P717 response schema contract\n\nContracts: `{len(rows)}`. Validated: `0`.\n",encoding="utf-8"); print(json.dumps({"manifest_id":"P717","schema_contract_rows":len(rows),"schema_validated_rows":0,"output":str(REPORT)},ensure_ascii=False)); return 0
if __name__=="__main__": raise SystemExit(main())
