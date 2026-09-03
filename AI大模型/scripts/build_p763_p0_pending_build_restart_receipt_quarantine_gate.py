#!/usr/bin/env python3
"""Build P763 restart-receipt quarantine gates from P762."""
from __future__ import annotations
import json
from datetime import datetime, timezone
from pathlib import Path
from build_p700_p0_real_input_pending_build_checklist import load_jsonl
ROOT=Path(__file__).resolve().parents[1]; SOURCE=ROOT/"datasets/governance/p762_p0_pending_build_restart_request_receipt_contract_gate.jsonl"; OUT=ROOT/"datasets/governance/p763_p0_pending_build_restart_receipt_quarantine_gate.jsonl"; REPORT=ROOT/"reports/p763_p0_pending_build_restart_receipt_quarantine_gate_report.json"; MD=ROOT/"reports/p763_p0_pending_build_restart_receipt_quarantine_gate.md"
FIELDS=("receipt_received","receipt_identity_verified","receipt_timestamp_verified","receipt_result_validated","receipt_provenance_validated","receipt_quarantined","receipt_released","restart_authorized","formal_decision_ready")
def main()->int:
 created=datetime.now(timezone.utc).isoformat(); src=[r for r in load_jsonl(SOURCE) if r.get("boundary")!="summary"]; rows=[]
 for i,s in enumerate(src,1):
  r={"quarantine_gate_id":f"p763::{s.get('request_gate_id')}","quarantine_gate_order":i,"created_at":created,"boundary":s.get("boundary"),"source_p762_id":s.get("request_gate_id"),"gate_status":"empty_no_receipt_to_quarantine","blocker_reason":"No restart receipt exists for identity, timestamp, result, provenance, or release validation.","operator_action":"Do not accept, release, infer, or synthesize restart receipts.","policy":"P763 is a receipt quarantine gate only; it performs no restart or decision."}; r.update({f:False for f in FIELDS}); rows.append(r)
 zero={f+"_rows":0 for f in FIELDS}; summary={"quarantine_gate_id":"p763::summary","quarantine_gate_order":len(rows)+1,"created_at":created,"boundary":"summary","quarantine_gate_rows":len(rows),**zero,"policy":"P763 remains empty and fail-closed."}; OUT.write_text("".join(json.dumps(r,ensure_ascii=False,sort_keys=True)+"\n" for r in rows+[summary]),encoding="utf-8"); report={"manifest_id":"P763","created_at":created,"local_only":True,"quarantine_gate_rows":len(rows),**zero,"artifact_jsonl":str(OUT.relative_to(ROOT)),"artifact_md":str(MD.relative_to(ROOT)),"policy":"P763 is planning-only and fail-closed."}; REPORT.write_text(json.dumps(report,ensure_ascii=False,indent=2,sort_keys=True)+"\n",encoding="utf-8"); MD.write_text(f"# P763 restart-receipt quarantine gate\n\nRows: `{len(rows)}`. Receipts released: `0`.\n",encoding="utf-8"); print(json.dumps({"manifest_id":"P763","quarantine_gate_rows":len(rows),"receipt_received_rows":0,"output":str(REPORT)},ensure_ascii=False)); return 0
if __name__=='__main__': raise SystemExit(main())
