#!/usr/bin/env python3
"""Build P764 receipt-to-restart non-promotion gates from P763."""
from __future__ import annotations
import json
from datetime import datetime, timezone
from pathlib import Path
from build_p700_p0_real_input_pending_build_checklist import load_jsonl
ROOT=Path(__file__).resolve().parents[1]; SOURCE=ROOT/"datasets/governance/p763_p0_pending_build_restart_receipt_quarantine_gate.jsonl"; OUT=ROOT/"datasets/governance/p764_p0_pending_build_receipt_to_restart_nonpromotion_gate.jsonl"; REPORT=ROOT/"reports/p764_p0_pending_build_receipt_to_restart_nonpromotion_gate_report.json"; MD=ROOT/"reports/p764_p0_pending_build_receipt_to_restart_nonpromotion_gate.md"
FIELDS=("receipt_released","integrity_validated","provenance_validated","scope_validated","owner_review_completed","restart_authorized","work_restarted","formal_decision_ready","production_execution_allowed")
def main()->int:
 created=datetime.now(timezone.utc).isoformat(); src=[r for r in load_jsonl(SOURCE) if r.get("boundary")!="summary"]; rows=[]
 for i,s in enumerate(src,1):
  r={"promotion_gate_id":f"p764::{s.get('quarantine_gate_id')}","promotion_gate_order":i,"created_at":created,"boundary":s.get("boundary"),"source_p763_id":s.get("quarantine_gate_id"),"gate_status":"empty_no_validated_receipt_to_promote","blocker_reason":"No quarantined receipt is present or validated for release into restart authorization.","operator_action":"Do not release receipts or infer restart authorization from planning records.","policy":"P764 is a receipt non-promotion gate only; it performs no release or restart."}; r.update({f:False for f in FIELDS}); rows.append(r)
 zero={f+"_rows":0 for f in FIELDS}; summary={"promotion_gate_id":"p764::summary","promotion_gate_order":len(rows)+1,"created_at":created,"boundary":"summary","promotion_gate_rows":len(rows),**zero,"policy":"P764 remains empty and fail-closed."}; OUT.write_text("".join(json.dumps(r,ensure_ascii=False,sort_keys=True)+"\n" for r in rows+[summary]),encoding="utf-8"); report={"manifest_id":"P764","created_at":created,"local_only":True,"promotion_gate_rows":len(rows),**zero,"artifact_jsonl":str(OUT.relative_to(ROOT)),"artifact_md":str(MD.relative_to(ROOT)),"policy":"P764 is planning-only and fail-closed."}; REPORT.write_text(json.dumps(report,ensure_ascii=False,indent=2,sort_keys=True)+"\n",encoding="utf-8"); MD.write_text(f"# P764 receipt-to-restart non-promotion gate\n\nRows: `{len(rows)}`. Receipts released: `0`.\n",encoding="utf-8"); print(json.dumps({"manifest_id":"P764","promotion_gate_rows":len(rows),"receipt_released_rows":0,"output":str(REPORT)},ensure_ascii=False)); return 0
if __name__=='__main__': raise SystemExit(main())
