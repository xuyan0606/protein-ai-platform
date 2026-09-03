#!/usr/bin/env python3
"""Build P766 terminal consistency rollup from P765."""
from __future__ import annotations
import json
from datetime import datetime, timezone
from pathlib import Path
from build_p700_p0_real_input_pending_build_checklist import load_jsonl
ROOT=Path(__file__).resolve().parents[1]; SOURCE=ROOT/"datasets/governance/p765_p0_pending_build_restart_to_execution_non_authorization_gate.jsonl"; OUT=ROOT/"datasets/governance/p766_p0_pending_build_terminal_consistency_rollup.jsonl"; REPORT=ROOT/"reports/p766_p0_pending_build_terminal_consistency_rollup_report.json"; MD=ROOT/"reports/p766_p0_pending_build_terminal_consistency_rollup.md"
FIELDS=("execution_started","real_input_received","evidence_validated","formal_decision_ready","authorization_granted","release_ready","production_execution_allowed","audit_receipt_present","restart_authorized")
def main()->int:
 created=datetime.now(timezone.utc).isoformat(); src=[r for r in load_jsonl(SOURCE) if r.get("boundary")!="summary"]; rows=[]
 for i,s in enumerate(src,1):
  r={"rollup_id":f"p766::{s.get('execution_gate_id')}","rollup_order":i,"created_at":created,"boundary":s.get("boundary"),"source_p765_id":s.get("execution_gate_id"),"rollup_status":"terminal_consistency_blocked","blocker_reason":"All execution and authorization boundaries remain closed; no verified state transition is present.","operator_action":"Observe and revalidate only; do not infer progress or execute downstream work.","policy":"P766 is a read-only consistency rollup; it performs no execution or authorization."}; r.update({f:False for f in FIELDS}); rows.append(r)
 zero={f+"_rows":0 for f in FIELDS}; summary={"rollup_id":"p766::summary","rollup_order":len(rows)+1,"created_at":created,"boundary":"summary","rollup_rows":len(rows),**zero,"policy":"P766 remains terminal and fail-closed."}; OUT.write_text("".join(json.dumps(r,ensure_ascii=False,sort_keys=True)+"\n" for r in rows+[summary]),encoding="utf-8"); report={"manifest_id":"P766","created_at":created,"local_only":True,"rollup_rows":len(rows),**zero,"artifact_jsonl":str(OUT.relative_to(ROOT)),"artifact_md":str(MD.relative_to(ROOT)),"policy":"P766 is monitoring-only and fail-closed."}; REPORT.write_text(json.dumps(report,ensure_ascii=False,indent=2,sort_keys=True)+"\n",encoding="utf-8"); MD.write_text(f"# P766 terminal consistency rollup\n\nRows: `{len(rows)}`. Unblocked terminal states: `0`.\n",encoding="utf-8"); print(json.dumps({"manifest_id":"P766","rollup_rows":len(rows),"formal_decision_ready_rows":0,"production_execution_allowed_rows":0,"output":str(REPORT)},ensure_ascii=False)); return 0
if __name__=='__main__': raise SystemExit(main())
