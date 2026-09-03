#!/usr/bin/env python3
"""Build P776 production-audit access/non-leak gates from P775."""
from __future__ import annotations
import json
from datetime import datetime, timezone
from pathlib import Path
from build_p700_p0_real_input_pending_build_checklist import load_jsonl
ROOT=Path(__file__).resolve().parents[1]; SOURCE=ROOT/"datasets/governance/p775_p0_pending_build_production_audit_retention_gate.jsonl"; OUT=ROOT/"datasets/governance/p776_p0_pending_build_production_audit_access_nonleak_gate.jsonl"; REPORT=ROOT/"reports/p776_p0_pending_build_production_audit_access_nonleak_gate_report.json"; MD=ROOT/"reports/p776_p0_pending_build_production_audit_access_nonleak_gate.md"
FIELDS=("audit_receipt_present","retrieval_requested","access_subject_verified","access_scope_authorized","receipt_retrieved","sensitive_data_exposed","unauthorized_export_detected","disclosure_approved","formal_decision_ready")
def main():
 created=datetime.now(timezone.utc).isoformat(); src=[r for r in load_jsonl(SOURCE) if r.get("boundary")!="summary"]; rows=[]
 for i,s in enumerate(src,1):
  r={"access_gate_id":f"p776::{s.get('audit_gate_id')}","access_gate_order":i,"created_at":created,"boundary":s.get("boundary"),"source_p775_id":s.get("audit_gate_id"),"gate_status":"empty_no_production_receipt_to_access","blocker_reason":"No authentic retained production audit receipt exists for retrieval, disclosure, or export.","operator_action":"Do not retrieve, disclose, export, or synthesize receipt content or access authorization.","policy":"P776 is an audit-access non-leak gate only; it performs no retrieval or disclosure."}; r.update({f:False for f in FIELDS}); rows.append(r)
 zero={f+"_rows":0 for f in FIELDS}; summary={"access_gate_id":"p776::summary","access_gate_order":len(rows)+1,"created_at":created,"boundary":"summary","access_gate_rows":len(rows),**zero,"policy":"P776 remains empty and fail-closed."}; OUT.write_text("".join(json.dumps(r,ensure_ascii=False,sort_keys=True)+"\n" for r in rows+[summary]),encoding="utf-8"); report={"manifest_id":"P776","created_at":created,"local_only":True,"access_gate_rows":len(rows),**zero,"artifact_jsonl":str(OUT.relative_to(ROOT)),"artifact_md":str(MD.relative_to(ROOT)),"policy":"P776 is planning-only and fail-closed."}; REPORT.write_text(json.dumps(report,ensure_ascii=False,indent=2,sort_keys=True)+"\n",encoding="utf-8"); MD.write_text(f"# P776 production-audit access/non-leak gate\n\nRows: `{len(rows)}`. Sensitive data exposed: `0`.\n",encoding="utf-8"); print(json.dumps({"manifest_id":"P776","access_gate_rows":len(rows),"sensitive_data_exposed_rows":0,"output":str(REPORT)},ensure_ascii=False)); return 0
if __name__=='__main__': raise SystemExit(main())
