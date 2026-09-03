#!/usr/bin/env python3
"""Build P743 disclosure incident containment guard from P742."""
from __future__ import annotations
import json
from datetime import datetime, timezone
from pathlib import Path
from build_p700_p0_real_input_pending_build_checklist import load_jsonl

ROOT=Path(__file__).resolve().parents[1]; SOURCE=ROOT/"datasets/governance/p742_p0_pending_build_audit_receipt_disclosure_nonleak_guard.jsonl"; OUT=ROOT/"datasets/governance/p743_p0_pending_build_disclosure_incident_containment_guard.jsonl"; REPORT=ROOT/"reports/p743_p0_pending_build_disclosure_incident_containment_guard_report.json"; MD=ROOT/"reports/p743_p0_pending_build_disclosure_incident_containment_guard.md"
FIELDS=("disclosure_incident_detected","incident_alert_raised","access_contained","owner_notified","incident_reviewed","containment_validated","formal_decision_ready")
def main()->int:
    created=datetime.now(timezone.utc).isoformat(); source=[r for r in load_jsonl(SOURCE) if r.get("boundary")!="summary"]; rows=[]
    for order,src in enumerate(source,1):
        row={"containment_guard_id":f"p743::{src.get('disclosure_guard_id')}","containment_guard_order":order,"created_at":created,"boundary":src.get("boundary"),"source_p742_id":src.get("disclosure_guard_id"),"guard_status":"empty_no_disclosure_incident","blocker_reason":"No disclosure event exists to alert, contain, or review.","operator_action":"Do not fabricate an incident, alert, owner response, or containment result.","policy":"P743 is an incident containment guard only; it does not create incidents or authorize disclosure."}; row.update({f:False for f in FIELDS}); rows.append(row)
    counts={f"{f}_rows":0 for f in FIELDS}; summary={"containment_guard_id":"p743::summary","containment_guard_order":len(rows)+1,"created_at":created,"boundary":"summary","containment_guard_rows":len(rows),**counts,"policy":"P743 remains empty and fail-closed."}; OUT.write_text("".join(json.dumps(r,ensure_ascii=False,sort_keys=True)+"\n" for r in rows+[summary]),encoding="utf-8"); report={"manifest_id":"P743","created_at":created,"local_only":True,"containment_guard_rows":len(rows),**counts,"artifact_jsonl":str(OUT.relative_to(ROOT)),"artifact_md":str(MD.relative_to(ROOT)),"policy":"P743 is planning-only and fail-closed."}; REPORT.write_text(json.dumps(report,ensure_ascii=False,indent=2,sort_keys=True)+"\n",encoding="utf-8"); MD.write_text(f"# P743 disclosure incident containment guard\n\nRows: `{len(rows)}`. Incidents detected: `0`.\n",encoding="utf-8"); print(json.dumps({"manifest_id":"P743","containment_guard_rows":len(rows),"disclosure_incident_detected_rows":0,"output":str(REPORT)},ensure_ascii=False)); return 0
if __name__=="__main__": raise SystemExit(main())
