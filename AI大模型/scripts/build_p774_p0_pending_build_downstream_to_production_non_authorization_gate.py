#!/usr/bin/env python3
"""Build P774 downstream-to-production non-authorization gates from P773."""
from __future__ import annotations
import json
from datetime import datetime, timezone
from pathlib import Path
from build_p700_p0_real_input_pending_build_checklist import load_jsonl
ROOT=Path(__file__).resolve().parents[1]; SOURCE=ROOT/"datasets/governance/p773_p0_pending_build_authorization_downstream_nonpromotion_gate.jsonl"; OUT=ROOT/"datasets/governance/p774_p0_pending_build_downstream_to_production_non_authorization_gate.jsonl"; REPORT=ROOT/"reports/p774_p0_pending_build_downstream_to_production_non_authorization_gate_report.json"; MD=ROOT/"reports/p774_p0_pending_build_downstream_to_production_non_authorization_gate.md"
FIELDS=("release_approved","customer_scope_confirmed","production_change_reviewed","rollback_plan_validated","execution_receipt_contract_ready","production_execution_requested","production_execution_authorized","production_execution_started","audit_receipt_present")
def main():
 created=datetime.now(timezone.utc).isoformat(); src=[r for r in load_jsonl(SOURCE) if r.get("boundary")!="summary"]; rows=[]
 for i,s in enumerate(src,1):
  r={"production_gate_id":f"p774::{s.get('nonpromotion_gate_id')}","production_gate_order":i,"created_at":created,"boundary":s.get("boundary"),"source_p773_id":s.get("nonpromotion_gate_id"),"gate_status":"empty_no_downstream_state_to_execute","blocker_reason":"No approved release, customer scope, change review, rollback plan, or execution contract exists.","operator_action":"Do not request, authorize, simulate, or start production execution.","policy":"P774 is a production non-authorization gate only; it performs no production action."}; r.update({f:False for f in FIELDS}); rows.append(r)
 zero={f+"_rows":0 for f in FIELDS}; summary={"production_gate_id":"p774::summary","production_gate_order":len(rows)+1,"created_at":created,"boundary":"summary","production_gate_rows":len(rows),**zero,"policy":"P774 remains empty and fail-closed."}; OUT.write_text("".join(json.dumps(r,ensure_ascii=False,sort_keys=True)+"\n" for r in rows+[summary]),encoding="utf-8"); report={"manifest_id":"P774","created_at":created,"local_only":True,"production_gate_rows":len(rows),**zero,"artifact_jsonl":str(OUT.relative_to(ROOT)),"artifact_md":str(MD.relative_to(ROOT)),"policy":"P774 is planning-only and fail-closed."}; REPORT.write_text(json.dumps(report,ensure_ascii=False,indent=2,sort_keys=True)+"\n",encoding="utf-8"); MD.write_text(f"# P774 downstream-to-production non-authorization gate\n\nRows: `{len(rows)}`. Production execution started: `0`.\n",encoding="utf-8"); print(json.dumps({"manifest_id":"P774","production_gate_rows":len(rows),"production_execution_started_rows":0,"output":str(REPORT)},ensure_ascii=False)); return 0
if __name__=='__main__': raise SystemExit(main())
