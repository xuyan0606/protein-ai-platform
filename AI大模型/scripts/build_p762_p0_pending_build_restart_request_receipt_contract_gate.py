#!/usr/bin/env python3
"""Build P762 restart-request receipt contract gates from P761."""
from __future__ import annotations
import json
from datetime import datetime, timezone
from pathlib import Path
from build_p700_p0_real_input_pending_build_checklist import load_jsonl
ROOT=Path(__file__).resolve().parents[1]; SOURCE=ROOT/"datasets/governance/p761_p0_pending_build_terminal_restart_prerequisite_gate.jsonl"; OUT=ROOT/"datasets/governance/p762_p0_pending_build_restart_request_receipt_contract_gate.jsonl"; REPORT=ROOT/"reports/p762_p0_pending_build_restart_request_receipt_contract_gate_report.json"; MD=ROOT/"reports/p762_p0_pending_build_restart_request_receipt_contract_gate.md"
FIELDS=("restart_target_defined","restart_scope_defined","authorization_window_defined","request_dispatched","receipt_contract_defined","receipt_received","receipt_validated","restart_authorized","work_restarted")
def main()->int:
 created=datetime.now(timezone.utc).isoformat(); src=[r for r in load_jsonl(SOURCE) if r.get("boundary")!="summary"]; rows=[]
 for i,s in enumerate(src,1):
  r={"request_gate_id":f"p762::{s.get('restart_gate_id')}","request_gate_order":i,"created_at":created,"boundary":s.get("boundary"),"source_p761_id":s.get("restart_gate_id"),"gate_status":"queued_no_restart_request_to_dispatch","blocker_reason":"Restart prerequisites are missing; no target, scope, authorization window, dispatch, or receipt exists.","operator_action":"Do not dispatch restart requests or accept/synthesize receipts.","policy":"P762 is a request/receipt contract gate only; it performs no dispatch or restart."}; r.update({f:False for f in FIELDS}); rows.append(r)
 zero={f+"_rows":0 for f in FIELDS}; summary={"request_gate_id":"p762::summary","request_gate_order":len(rows)+1,"created_at":created,"boundary":"summary","request_gate_rows":len(rows),**zero,"policy":"P762 remains queued and fail-closed."}; OUT.write_text("".join(json.dumps(r,ensure_ascii=False,sort_keys=True)+"\n" for r in rows+[summary]),encoding="utf-8"); report={"manifest_id":"P762","created_at":created,"local_only":True,"request_gate_rows":len(rows),**zero,"artifact_jsonl":str(OUT.relative_to(ROOT)),"artifact_md":str(MD.relative_to(ROOT)),"policy":"P762 is planning-only and fail-closed."}; REPORT.write_text(json.dumps(report,ensure_ascii=False,indent=2,sort_keys=True)+"\n",encoding="utf-8"); MD.write_text(f"# P762 restart-request receipt contract gate\n\nRows: `{len(rows)}`. Requests dispatched: `0`. Receipts received: `0`.\n",encoding="utf-8"); print(json.dumps({"manifest_id":"P762","request_gate_rows":len(rows),"request_dispatched_rows":0,"receipt_received_rows":0,"output":str(REPORT)},ensure_ascii=False)); return 0
if __name__=='__main__': raise SystemExit(main())
