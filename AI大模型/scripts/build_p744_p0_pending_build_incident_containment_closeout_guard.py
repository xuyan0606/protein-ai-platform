#!/usr/bin/env python3
"""Build P744 incident containment closeout guard from P743."""
from __future__ import annotations
import json
from datetime import datetime, timezone
from pathlib import Path
from build_p700_p0_real_input_pending_build_checklist import load_jsonl

ROOT=Path(__file__).resolve().parents[1]; SOURCE=ROOT/"datasets/governance/p743_p0_pending_build_disclosure_incident_containment_guard.jsonl"; OUT=ROOT/"datasets/governance/p744_p0_pending_build_incident_containment_closeout_guard.jsonl"; REPORT=ROOT/"reports/p744_p0_pending_build_incident_containment_closeout_guard_report.json"; MD=ROOT/"reports/p744_p0_pending_build_incident_containment_closeout_guard.md"
FIELDS=("incident_present","containment_complete","evidence_archived","residual_risk_assessed","closeout_reviewed","closeout_approved","formal_decision_ready")
def main()->int:
    created=datetime.now(timezone.utc).isoformat(); source=[r for r in load_jsonl(SOURCE) if r.get("boundary")!="summary"]; rows=[]
    for order,src in enumerate(source,1):
        row={"closeout_guard_id":f"p744::{src.get('containment_guard_id')}","closeout_guard_order":order,"created_at":created,"boundary":src.get("boundary"),"source_p743_id":src.get("containment_guard_id"),"guard_status":"empty_no_incident_to_close","blocker_reason":"No containment incident exists to archive, assess, review, or close.","operator_action":"Do not fabricate closeout evidence, approval, or residual-risk status.","policy":"P744 is a closeout guard only; it never closes incidents or grants authorization."}; row.update({f:False for f in FIELDS}); rows.append(row)
    counts={f"{f}_rows":0 for f in FIELDS}; summary={"closeout_guard_id":"p744::summary","closeout_guard_order":len(rows)+1,"created_at":created,"boundary":"summary","closeout_guard_rows":len(rows),**counts,"policy":"P744 remains empty and fail-closed."}; OUT.write_text("".join(json.dumps(r,ensure_ascii=False,sort_keys=True)+"\n" for r in rows+[summary]),encoding="utf-8"); report={"manifest_id":"P744","created_at":created,"local_only":True,"closeout_guard_rows":len(rows),**counts,"artifact_jsonl":str(OUT.relative_to(ROOT)),"artifact_md":str(MD.relative_to(ROOT)),"policy":"P744 is planning-only and fail-closed."}; REPORT.write_text(json.dumps(report,ensure_ascii=False,indent=2,sort_keys=True)+"\n",encoding="utf-8"); MD.write_text(f"# P744 incident containment closeout guard\n\nRows: `{len(rows)}`. Incidents closed: `0`.\n",encoding="utf-8"); print(json.dumps({"manifest_id":"P744","closeout_guard_rows":len(rows),"closeout_approved_rows":0,"output":str(REPORT)},ensure_ascii=False)); return 0
if __name__=="__main__": raise SystemExit(main())
