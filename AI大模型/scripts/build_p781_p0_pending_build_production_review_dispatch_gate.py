#!/usr/bin/env python3
import json
from datetime import datetime, timezone
from pathlib import Path
from build_p700_p0_real_input_pending_build_checklist import load_jsonl
ROOT=Path(__file__).resolve().parents[1]; SOURCE=ROOT/"datasets/governance/p780_p0_pending_build_production_next_review_gate.jsonl"; OUT=ROOT/"datasets/governance/p781_p0_pending_build_production_review_dispatch_gate.jsonl"; REPORT=ROOT/"reports/p781_p0_pending_build_production_review_dispatch_gate_report.json"; MD=ROOT/"reports/p781_p0_pending_build_production_review_dispatch_gate.md"
FIELDS=("dispatch_target_defined","dispatch_authorized","operator_defined","execution_window_defined","receipt_contract_defined","review_dispatched","review_executed","new_evidence_received","production_execution_allowed")
def main():
 created=datetime.now(timezone.utc).isoformat(); src=[r for r in load_jsonl(SOURCE) if r.get("boundary")!="summary"]; rows=[]
 for i,s in enumerate(src,1):
  r={"dispatch_gate_id":f"p781::{s.get('review_gate_id')}","dispatch_gate_order":i,"created_at":created,"boundary":s.get("boundary"),"source_p780_id":s.get("review_gate_id"),"gate_status":"queued_no_authorized_production_review_dispatch","blocker_reason":"Production review is queued only; target, authorization, operator, window, and receipt contract are absent.","operator_action":"Do not dispatch or execute production review and do not claim new evidence.","policy":"P781 is a dispatch-readiness gate only; it performs no dispatch or review."}; r.update({f:False for f in FIELDS}); rows.append(r)
 zero={f+"_rows":0 for f in FIELDS}; summary={"dispatch_gate_id":"p781::summary","dispatch_gate_order":len(rows)+1,"created_at":created,"boundary":"summary","dispatch_gate_rows":len(rows),**zero,"policy":"P781 remains queued and fail-closed."}; OUT.write_text("".join(json.dumps(r,ensure_ascii=False,sort_keys=True)+"\n" for r in rows+[summary]),encoding="utf-8"); report={"manifest_id":"P781","created_at":created,"local_only":True,"dispatch_gate_rows":len(rows),**zero,"artifact_jsonl":str(OUT.relative_to(ROOT)),"artifact_md":str(MD.relative_to(ROOT)),"policy":"P781 is planning-only and fail-closed."}; REPORT.write_text(json.dumps(report,ensure_ascii=False,indent=2,sort_keys=True)+"\n",encoding="utf-8"); MD.write_text(f"# P781 production review dispatch gate\n\nRows: `{len(rows)}`. Review dispatched: `0`.\n",encoding="utf-8"); print(json.dumps({"manifest_id":"P781","dispatch_gate_rows":len(rows),"review_dispatched_rows":0,"output":str(REPORT)},ensure_ascii=False)); return 0
if __name__=='__main__': raise SystemExit(main())
