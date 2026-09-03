#!/usr/bin/env python3
"""Build P767 next-review action gates from P766."""
from __future__ import annotations
import json
from datetime import datetime, timezone
from pathlib import Path
from build_p700_p0_real_input_pending_build_checklist import load_jsonl
ROOT=Path(__file__).resolve().parents[1]; SOURCE=ROOT/"datasets/governance/p766_p0_pending_build_terminal_consistency_rollup.jsonl"; OUT=ROOT/"datasets/governance/p767_p0_pending_build_next_review_action_gate.jsonl"; REPORT=ROOT/"reports/p767_p0_pending_build_next_review_action_gate_report.json"; MD=ROOT/"reports/p767_p0_pending_build_next_review_action_gate.md"
FIELDS=("review_scheduled","review_executed","new_real_input_received","new_evidence_detected","blocker_reassessed","restart_authorized","formal_decision_ready","production_execution_allowed")
def main()->int:
 created=datetime.now(timezone.utc).isoformat(); src=[r for r in load_jsonl(SOURCE) if r.get("boundary")!="summary"]; rows=[]
 for i,s in enumerate(src,1):
  r={"review_gate_id":f"p767::{s.get('rollup_id')}","review_gate_order":i,"created_at":created,"boundary":s.get("boundary"),"source_p766_id":s.get("rollup_id"),"gate_status":"queued_no_review_execution","blocker_reason":"No new real input or evidence exists; review remains a planning action and cannot unlock execution.","operator_action":"Record the next review only; do not execute review, infer progress, authorize restart, or write decisions.","policy":"P767 is a review-action register only; it performs no review or authorization."}; r.update({f:False for f in FIELDS}); rows.append(r)
 zero={f+"_rows":0 for f in FIELDS}; summary={"review_gate_id":"p767::summary","review_gate_order":len(rows)+1,"created_at":created,"boundary":"summary","review_gate_rows":len(rows),**zero,"policy":"P767 remains queued and fail-closed."}; OUT.write_text("".join(json.dumps(r,ensure_ascii=False,sort_keys=True)+"\n" for r in rows+[summary]),encoding="utf-8"); report={"manifest_id":"P767","created_at":created,"local_only":True,"review_gate_rows":len(rows),**zero,"artifact_jsonl":str(OUT.relative_to(ROOT)),"artifact_md":str(MD.relative_to(ROOT)),"policy":"P767 is planning-only and fail-closed."}; REPORT.write_text(json.dumps(report,ensure_ascii=False,indent=2,sort_keys=True)+"\n",encoding="utf-8"); MD.write_text(f"# P767 next-review action gate\n\nRows: `{len(rows)}`. Review executed: `0`.\n",encoding="utf-8"); print(json.dumps({"manifest_id":"P767","review_gate_rows":len(rows),"review_executed_rows":0,"output":str(REPORT)},ensure_ascii=False)); return 0
if __name__=='__main__': raise SystemExit(main())
