#!/usr/bin/env python3
"""Build P775 production audit-retention gates from P774."""
from __future__ import annotations
import json
from datetime import datetime, timezone
from pathlib import Path
from build_p700_p0_real_input_pending_build_checklist import load_jsonl
ROOT=Path(__file__).resolve().parents[1]; SOURCE=ROOT/"datasets/governance/p774_p0_pending_build_downstream_to_production_non_authorization_gate.jsonl"; OUT=ROOT/"datasets/governance/p775_p0_pending_build_production_audit_retention_gate.jsonl"; REPORT=ROOT/"reports/p775_p0_pending_build_production_audit_retention_gate_report.json"; MD=ROOT/"reports/p775_p0_pending_build_production_audit_retention_gate.md"
FIELDS=("production_execution_started","production_execution_authorized","change_record_present","audit_receipt_present","audit_receipt_integrity_validated","retention_policy_validated","receipt_immutable","execution_result_attested","formal_decision_ready")
def main():
 created=datetime.now(timezone.utc).isoformat(); src=[r for r in load_jsonl(SOURCE) if r.get("boundary")!="summary"]; rows=[]
 for i,s in enumerate(src,1):
  r={"audit_gate_id":f"p775::{s.get('production_gate_id')}","audit_gate_order":i,"created_at":created,"boundary":s.get("boundary"),"source_p774_id":s.get("production_gate_id"),"gate_status":"empty_no_execution_receipt_to_retain","blocker_reason":"No authorized production execution, change record, or authentic audit receipt exists for retention or attestation.","operator_action":"Do not create, backfill, retain, or attest execution records without a real receipt.","policy":"P775 is an audit-retention gate only; it performs no production action or attestation."}; r.update({f:False for f in FIELDS}); rows.append(r)
 zero={f+"_rows":0 for f in FIELDS}; summary={"audit_gate_id":"p775::summary","audit_gate_order":len(rows)+1,"created_at":created,"boundary":"summary","audit_gate_rows":len(rows),**zero,"policy":"P775 remains empty and fail-closed."}; OUT.write_text("".join(json.dumps(r,ensure_ascii=False,sort_keys=True)+"\n" for r in rows+[summary]),encoding="utf-8"); report={"manifest_id":"P775","created_at":created,"local_only":True,"audit_gate_rows":len(rows),**zero,"artifact_jsonl":str(OUT.relative_to(ROOT)),"artifact_md":str(MD.relative_to(ROOT)),"policy":"P775 is planning-only and fail-closed."}; REPORT.write_text(json.dumps(report,ensure_ascii=False,indent=2,sort_keys=True)+"\n",encoding="utf-8"); MD.write_text(f"# P775 production audit-retention gate\n\nRows: `{len(rows)}`. Audit receipts retained: `0`.\n",encoding="utf-8"); print(json.dumps({"manifest_id":"P775","audit_gate_rows":len(rows),"audit_receipt_present_rows":0,"output":str(REPORT)},ensure_ascii=False)); return 0
if __name__=='__main__': raise SystemExit(main())
