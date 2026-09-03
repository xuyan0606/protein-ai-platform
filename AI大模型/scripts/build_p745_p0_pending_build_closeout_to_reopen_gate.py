#!/usr/bin/env python3
"""Build P745 closeout-to-reopen gate from P744."""
from __future__ import annotations
import json
from datetime import datetime, timezone
from pathlib import Path
from build_p700_p0_real_input_pending_build_checklist import load_jsonl

ROOT=Path(__file__).resolve().parents[1]; SOURCE=ROOT/"datasets/governance/p744_p0_pending_build_incident_containment_closeout_guard.jsonl"; OUT=ROOT/"datasets/governance/p745_p0_pending_build_closeout_to_reopen_gate.jsonl"; REPORT=ROOT/"reports/p745_p0_pending_build_closeout_to_reopen_gate_report.json"; MD=ROOT/"reports/p745_p0_pending_build_closeout_to_reopen_gate.md"
FIELDS=("incident_closed","reopen_requested","new_evidence_present","reopen_reason_reviewed","reopen_authorized","reopen_gate_validated","formal_decision_ready")
def main()->int:
    created=datetime.now(timezone.utc).isoformat(); source=[r for r in load_jsonl(SOURCE) if r.get("boundary")!="summary"]; rows=[]
    for order,src in enumerate(source,1):
        row={"reopen_gate_id":f"p745::{src.get('closeout_guard_id')}","reopen_gate_order":order,"created_at":created,"boundary":src.get("boundary"),"source_p744_id":src.get("closeout_guard_id"),"gate_status":"empty_no_closed_incident_to_reopen","blocker_reason":"No incident was closed, so no reopen request or new evidence exists.","operator_action":"Do not reopen or synthesize evidence for a nonexistent closed incident.","policy":"P745 is a reopen gate only; it does not reopen incidents or grant authorization."}; row.update({f:False for f in FIELDS}); rows.append(row)
    counts={f"{f}_rows":0 for f in FIELDS}; summary={"reopen_gate_id":"p745::summary","reopen_gate_order":len(rows)+1,"created_at":created,"boundary":"summary","reopen_gate_rows":len(rows),**counts,"policy":"P745 remains empty and fail-closed."}; OUT.write_text("".join(json.dumps(r,ensure_ascii=False,sort_keys=True)+"\n" for r in rows+[summary]),encoding="utf-8"); report={"manifest_id":"P745","created_at":created,"local_only":True,"reopen_gate_rows":len(rows),**counts,"artifact_jsonl":str(OUT.relative_to(ROOT)),"artifact_md":str(MD.relative_to(ROOT)),"policy":"P745 is planning-only and fail-closed."}; REPORT.write_text(json.dumps(report,ensure_ascii=False,indent=2,sort_keys=True)+"\n",encoding="utf-8"); MD.write_text(f"# P745 closeout-to-reopen gate\n\nRows: `{len(rows)}`. Reopens authorized: `0`.\n",encoding="utf-8"); print(json.dumps({"manifest_id":"P745","reopen_gate_rows":len(rows),"reopen_authorized_rows":0,"output":str(REPORT)},ensure_ascii=False)); return 0
if __name__=="__main__": raise SystemExit(main())
