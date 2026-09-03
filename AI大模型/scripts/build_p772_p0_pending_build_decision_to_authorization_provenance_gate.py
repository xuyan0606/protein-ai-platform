#!/usr/bin/env python3
"""Build P772 decision-to-authorization provenance gates from P771."""
from __future__ import annotations
import json
from datetime import datetime, timezone
from pathlib import Path
from build_p700_p0_real_input_pending_build_checklist import load_jsonl
ROOT=Path(__file__).resolve().parents[1]; SOURCE=ROOT/"datasets/governance/p771_p0_pending_build_receipt_to_decision_lineage_gate.jsonl"; OUT=ROOT/"datasets/governance/p772_p0_pending_build_decision_to_authorization_provenance_gate.jsonl"; REPORT=ROOT/"reports/p772_p0_pending_build_decision_to_authorization_provenance_gate_report.json"; MD=ROOT/"reports/p772_p0_pending_build_decision_to_authorization_provenance_gate.md"
FIELDS=("decision_lineage_complete","authorization_record_present","authorizer_identity_verified","authorization_scope_verified","authorization_provenance_validated","restart_authorized","execution_authorized","formal_decision_written","production_execution_allowed")
def main():
 created=datetime.now(timezone.utc).isoformat(); src=[r for r in load_jsonl(SOURCE) if r.get("boundary")!="summary"]; rows=[]
 for i,s in enumerate(src,1):
  r={"authorization_gate_id":f"p772::{s.get('lineage_gate_id')}","authorization_gate_order":i,"created_at":created,"boundary":s.get("boundary"),"source_p771_id":s.get("lineage_gate_id"),"gate_status":"empty_no_decision_authorization_to_validate","blocker_reason":"No complete decision lineage, authorization record, verified authorizer, or scope exists.","operator_action":"Do not infer or grant authorization for restart, execution, formal decision, or production.","policy":"P772 is an authorization-provenance gate only; it grants no authorization."}; r.update({f:False for f in FIELDS}); rows.append(r)
 zero={f+"_rows":0 for f in FIELDS}; summary={"authorization_gate_id":"p772::summary","authorization_gate_order":len(rows)+1,"created_at":created,"boundary":"summary","authorization_gate_rows":len(rows),**zero,"policy":"P772 remains empty and fail-closed."}; OUT.write_text("".join(json.dumps(r,ensure_ascii=False,sort_keys=True)+"\n" for r in rows+[summary]),encoding="utf-8"); report={"manifest_id":"P772","created_at":created,"local_only":True,"authorization_gate_rows":len(rows),**zero,"artifact_jsonl":str(OUT.relative_to(ROOT)),"artifact_md":str(MD.relative_to(ROOT)),"policy":"P772 is planning-only and fail-closed."}; REPORT.write_text(json.dumps(report,ensure_ascii=False,indent=2,sort_keys=True)+"\n",encoding="utf-8"); MD.write_text(f"# P772 decision-to-authorization provenance gate\n\nRows: `{len(rows)}`. Restart authorized: `0`.\n",encoding="utf-8"); print(json.dumps({"manifest_id":"P772","authorization_gate_rows":len(rows),"restart_authorized_rows":0,"output":str(REPORT)},ensure_ascii=False)); return 0
if __name__=='__main__': raise SystemExit(main())
