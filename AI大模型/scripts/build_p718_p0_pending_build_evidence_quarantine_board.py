#!/usr/bin/env python3
"""Build P718 evidence quarantine board from P717 contracts."""
from __future__ import annotations
import json
from datetime import datetime,timezone
from pathlib import Path
from build_p700_p0_real_input_pending_build_checklist import load_jsonl
ROOT=Path(__file__).resolve().parents[1]; SOURCE=ROOT/"datasets/governance/p717_p0_pending_build_response_schema_contract.jsonl"; OUT=ROOT/"datasets/governance/p718_p0_pending_build_evidence_quarantine_board.jsonl"; REPORT=ROOT/"reports/p718_p0_pending_build_evidence_quarantine_board_report.json"; MD=ROOT/"reports/p718_p0_pending_build_evidence_quarantine_board.md"
def main():
 created=datetime.now(timezone.utc).isoformat(); src=[r for r in load_jsonl(SOURCE) if r.get("lane")!="summary"]; rows=[]
 for i,r in enumerate(src,1):
  rows.append({"quarantine_id":f"p718::{r.get('schema_contract_id')}","quarantine_order":i,"created_at":created,"lane":r.get("lane"),"source_p717_id":r.get("schema_contract_id"),"quarantine_status":"empty_quarantine_waiting_response","response_received":False,"evidence_payload_present":False,"evidence_quarantined":False,"provenance_checked":False,"integrity_checked":False,"evidence_released":False,"evidence_validated":False,"formal_decision_ready":False,"blocker_reason":"No response payload exists to quarantine or inspect.","policy":"P718 is an evidence quarantine definition only; it does not receive, release, validate, or authorize evidence."})
 summary={"quarantine_id":"p718::summary","quarantine_order":len(rows)+1,"created_at":created,"lane":"summary","quarantine_rows":len(rows),"response_received_rows":0,"evidence_quarantined_rows":0,"provenance_checked_rows":0,"integrity_checked_rows":0,"evidence_released_rows":0,"evidence_validated_rows":0,"formal_decision_ready_rows":0,"policy":"P718 records quarantine gaps only."}
 OUT.write_text("".join(json.dumps(x,ensure_ascii=False,sort_keys=True)+"\n" for x in rows+[summary]),encoding="utf-8"); report={"manifest_id":"P718","created_at":created,"local_only":True,"quarantine_rows":len(rows),"response_received_rows":0,"evidence_quarantined_rows":0,"provenance_checked_rows":0,"integrity_checked_rows":0,"evidence_released_rows":0,"evidence_validated_rows":0,"formal_decision_ready_rows":0,"artifact_jsonl":str(OUT.relative_to(ROOT)),"artifact_md":str(MD.relative_to(ROOT)),"policy":"P718 is planning-only and fail-closed."}; REPORT.write_text(json.dumps(report,ensure_ascii=False,indent=2,sort_keys=True)+"\n",encoding="utf-8"); MD.write_text(f"# P718 evidence quarantine board\n\nRows: `{len(rows)}`. Quarantined: `0`; released: `0`.\n",encoding="utf-8"); print(json.dumps({"manifest_id":"P718","quarantine_rows":len(rows),"evidence_quarantined_rows":0,"output":str(REPORT)},ensure_ascii=False)); return 0
if __name__=="__main__": raise SystemExit(main())
