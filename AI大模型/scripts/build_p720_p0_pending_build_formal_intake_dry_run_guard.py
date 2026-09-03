#!/usr/bin/env python3
"""Build P720 formal-intake dry-run guard from P719."""
from __future__ import annotations
import json
from datetime import datetime,timezone
from pathlib import Path
from build_p700_p0_real_input_pending_build_checklist import load_jsonl
ROOT=Path(__file__).resolve().parents[1]; SOURCE=ROOT/"datasets/governance/p719_p0_pending_build_decision_routing_readiness.jsonl"; OUT=ROOT/"datasets/governance/p720_p0_pending_build_formal_intake_dry_run_guard.jsonl"; REPORT=ROOT/"reports/p720_p0_pending_build_formal_intake_dry_run_guard_report.json"; MD=ROOT/"reports/p720_p0_pending_build_formal_intake_dry_run_guard.md"
def main():
 created=datetime.now(timezone.utc).isoformat(); src=[r for r in load_jsonl(SOURCE) if r.get("lane")!="summary"]; rows=[]
 for i,r in enumerate(src,1):
  rows.append({"intake_guard_id":f"p720::{r.get('routing_readiness_id')}","intake_guard_order":i,"created_at":created,"lane":r.get("lane"),"source_p719_id":r.get("routing_readiness_id"),"guard_status":"blocked_prerequisites_missing","required_real_input":True,"required_evidence_release":True,"required_route_execution":True,"required_validator_pass":True,"formal_intake_dry_run_executed":False,"formal_intake_dry_run_passed":False,"formal_intake_written":False,"formal_decision_ready":False,"blocker_reason":"Formal intake prerequisites are not satisfied.","policy":"P720 is a dry-run guard only; it does not perform intake, write records, or authorize decisions."})
 summary={"intake_guard_id":"p720::summary","intake_guard_order":len(rows)+1,"created_at":created,"lane":"summary","intake_guard_rows":len(rows),"formal_intake_dry_run_executed_rows":0,"formal_intake_dry_run_passed_rows":0,"formal_intake_written_rows":0,"formal_decision_ready_rows":0,"policy":"P720 records formal-intake guard gaps only."}
 OUT.write_text("".join(json.dumps(x,ensure_ascii=False,sort_keys=True)+"\n" for x in rows+[summary]),encoding="utf-8"); report={"manifest_id":"P720","created_at":created,"local_only":True,"intake_guard_rows":len(rows),"formal_intake_dry_run_executed_rows":0,"formal_intake_dry_run_passed_rows":0,"formal_intake_written_rows":0,"formal_decision_ready_rows":0,"artifact_jsonl":str(OUT.relative_to(ROOT)),"artifact_md":str(MD.relative_to(ROOT)),"policy":"P720 is planning-only and fail-closed."}; REPORT.write_text(json.dumps(report,ensure_ascii=False,indent=2,sort_keys=True)+"\n",encoding="utf-8"); MD.write_text(f"# P720 formal intake dry-run guard\n\nRows: `{len(rows)}`. Dry-run executed/passed: `0/0`.\n",encoding="utf-8"); print(json.dumps({"manifest_id":"P720","intake_guard_rows":len(rows),"formal_intake_dry_run_executed_rows":0,"output":str(REPORT)},ensure_ascii=False)); return 0
if __name__=="__main__": raise SystemExit(main())
