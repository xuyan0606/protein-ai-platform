#!/usr/bin/env python3
"""Build P778 production-audit closeout/reopen gates from P777."""
from __future__ import annotations
import json
from datetime import datetime, timezone
from pathlib import Path
from build_p700_p0_real_input_pending_build_checklist import load_jsonl
ROOT=Path(__file__).resolve().parents[1]; SOURCE=ROOT/"datasets/governance/p777_p0_pending_build_production_audit_incident_containment_gate.jsonl"; OUT=ROOT/"datasets/governance/p778_p0_pending_build_production_audit_closeout_reopen_gate.jsonl"; REPORT=ROOT/"reports/p778_p0_pending_build_production_audit_closeout_reopen_gate_report.json"; MD=ROOT/"reports/p778_p0_pending_build_production_audit_closeout_reopen_gate.md"
FIELDS=("incident_present","evidence_archived","residual_risk_assessed","owner_approval_present","closeout_approved","reopen_requested","reopen_authorized","formal_decision_ready","production_execution_allowed")
def main():
 created=datetime.now(timezone.utc).isoformat(); src=[r for r in load_jsonl(SOURCE) if r.get("boundary")!="summary"]; rows=[]
 for i,s in enumerate(src,1):
  r={"closeout_gate_id":f"p778::{s.get('containment_gate_id')}","closeout_gate_order":i,"created_at":created,"boundary":s.get("boundary"),"source_p777_id":s.get("containment_gate_id"),"gate_status":"empty_no_production_audit_incident_to_close_or_reopen","blocker_reason":"No incident, archived evidence, risk assessment, approval, or reopen request exists.","operator_action":"Do not close, reopen, or infer production authorization from an empty incident record.","policy":"P778 is a closeout/reopen gate only; it performs no incident closure, restart, or execution."}; r.update({f:False for f in FIELDS}); rows.append(r)
 zero={f+"_rows":0 for f in FIELDS}; summary={"closeout_gate_id":"p778::summary","closeout_gate_order":len(rows)+1,"created_at":created,"boundary":"summary","closeout_gate_rows":len(rows),**zero,"policy":"P778 remains empty and fail-closed."}; OUT.write_text("".join(json.dumps(r,ensure_ascii=False,sort_keys=True)+"\n" for r in rows+[summary]),encoding="utf-8"); report={"manifest_id":"P778","created_at":created,"local_only":True,"closeout_gate_rows":len(rows),**zero,"artifact_jsonl":str(OUT.relative_to(ROOT)),"artifact_md":str(MD.relative_to(ROOT)),"policy":"P778 is planning-only and fail-closed."}; REPORT.write_text(json.dumps(report,ensure_ascii=False,indent=2,sort_keys=True)+"\n",encoding="utf-8"); MD.write_text(f"# P778 production-audit closeout/reopen gate\n\nRows: `{len(rows)}`. Closeout approved: `0`. Reopen authorized: `0`.\n",encoding="utf-8"); print(json.dumps({"manifest_id":"P778","closeout_gate_rows":len(rows),"closeout_approved_rows":0,"reopen_authorized_rows":0,"output":str(REPORT)},ensure_ascii=False)); return 0
if __name__=='__main__': raise SystemExit(main())
