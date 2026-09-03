#!/usr/bin/env python3
"""Build P773 authorization downstream non-promotion gates from P772."""
from __future__ import annotations
import json
from datetime import datetime, timezone
from pathlib import Path
from build_p700_p0_real_input_pending_build_checklist import load_jsonl
ROOT=Path(__file__).resolve().parents[1]; SOURCE=ROOT/"datasets/governance/p772_p0_pending_build_decision_to_authorization_provenance_gate.jsonl"; OUT=ROOT/"datasets/governance/p773_p0_pending_build_authorization_downstream_nonpromotion_gate.jsonl"; REPORT=ROOT/"reports/p773_p0_pending_build_authorization_downstream_nonpromotion_gate_report.json"; MD=ROOT/"reports/p773_p0_pending_build_authorization_downstream_nonpromotion_gate.md"
FIELDS=("authorization_validated","restart_authorized","execution_authorized","model_claim_promoted","customer_delivery_promoted","release_claim_promoted","release_ready","production_execution_allowed")
def main():
 created=datetime.now(timezone.utc).isoformat(); src=[r for r in load_jsonl(SOURCE) if r.get("boundary")!="summary"]; rows=[]
 for i,s in enumerate(src,1):
  r={"nonpromotion_gate_id":f"p773::{s.get('authorization_gate_id')}","nonpromotion_gate_order":i,"created_at":created,"boundary":s.get("boundary"),"source_p772_id":s.get("authorization_gate_id"),"gate_status":"empty_no_validated_authorization_to_promote","blocker_reason":"No validated authorization exists; restart, execution, claims, delivery, release, and production remain prohibited.","operator_action":"Do not promote planning or draft state into downstream claims, release, delivery, or execution.","policy":"P773 is a downstream non-promotion gate only; it performs no release, delivery, or authorization."}; r.update({f:False for f in FIELDS}); rows.append(r)
 zero={f+"_rows":0 for f in FIELDS}; summary={"nonpromotion_gate_id":"p773::summary","nonpromotion_gate_order":len(rows)+1,"created_at":created,"boundary":"summary","nonpromotion_gate_rows":len(rows),**zero,"policy":"P773 remains empty and fail-closed."}; OUT.write_text("".join(json.dumps(r,ensure_ascii=False,sort_keys=True)+"\n" for r in rows+[summary]),encoding="utf-8"); report={"manifest_id":"P773","created_at":created,"local_only":True,"nonpromotion_gate_rows":len(rows),**zero,"artifact_jsonl":str(OUT.relative_to(ROOT)),"artifact_md":str(MD.relative_to(ROOT)),"policy":"P773 is planning-only and fail-closed."}; REPORT.write_text(json.dumps(report,ensure_ascii=False,indent=2,sort_keys=True)+"\n",encoding="utf-8"); MD.write_text(f"# P773 authorization downstream non-promotion gate\n\nRows: `{len(rows)}`. Release claims promoted: `0`.\n",encoding="utf-8"); print(json.dumps({"manifest_id":"P773","nonpromotion_gate_rows":len(rows),"release_claim_promoted_rows":0,"output":str(REPORT)},ensure_ascii=False)); return 0
if __name__=='__main__': raise SystemExit(main())
