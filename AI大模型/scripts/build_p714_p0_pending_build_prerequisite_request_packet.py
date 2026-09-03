#!/usr/bin/env python3
"""Build P714 local prerequisite-request packet draft from P713 gaps."""
from __future__ import annotations
import json
from datetime import datetime,timezone
from pathlib import Path
from build_p700_p0_real_input_pending_build_checklist import load_jsonl
ROOT=Path(__file__).resolve().parents[1]; OUT=ROOT/"datasets/governance/p714_p0_pending_build_prerequisite_request_packet.jsonl"; REPORT=ROOT/"reports/p714_p0_pending_build_prerequisite_request_packet_report.json"; MD=ROOT/"reports/p714_p0_pending_build_prerequisite_request_packet.md"
LANES=("plate_feedback","strict_holdout","substrate_identity","numbering_curation","governance")
def main():
 created=datetime.now(timezone.utc).isoformat(); rows=[]
 for i,lane in enumerate(LANES,1):
  rows.append({"request_packet_id":f"p714::{lane}","request_order":i,"created_at":created,"lane":lane,"packet_status":"draft_not_sent","request_target":"approved external/operator source to be designated","requested_materials":["real input payload","provenance/evidence attachment","owner identity and acknowledgement","validator result"],"request_sent":False,"response_received":False,"evidence_validated":False,"owner_acknowledged":False,"formal_decision_ready":False,"rejection_condition":"Reject placeholders, inferred values, unverifiable provenance, or authorization claims.","policy":"P714 is a local request-packet draft only; it does not contact sources, receive responses, or authorize action."})
 summary={"request_packet_id":"p714::summary","request_order":len(rows)+1,"created_at":created,"lane":"summary","request_packet_rows":len(rows),"request_sent_rows":0,"response_received_rows":0,"evidence_validated_rows":0,"formal_decision_ready_rows":0,"policy":"P714 records request drafts only."}
 OUT.write_text("".join(json.dumps(x,ensure_ascii=False,sort_keys=True)+"\n" for x in rows+[summary]),encoding="utf-8"); report={"manifest_id":"P714","created_at":created,"local_only":True,"request_packet_rows":len(rows),"request_sent_rows":0,"response_received_rows":0,"evidence_validated_rows":0,"formal_decision_ready_rows":0,"artifact_jsonl":str(OUT.relative_to(ROOT)),"artifact_md":str(MD.relative_to(ROOT)),"policy":"P714 is draft-only and fail-closed."}; REPORT.write_text(json.dumps(report,ensure_ascii=False,indent=2,sort_keys=True)+"\n",encoding="utf-8"); MD.write_text(f"# P714 prerequisite request packet draft\n\nDraft packets: `{len(rows)}`. Sent: `0`.\n",encoding="utf-8"); print(json.dumps({"manifest_id":"P714","request_packet_rows":len(rows),"request_sent_rows":0,"output":str(REPORT)},ensure_ascii=False)); return 0
if __name__=="__main__": raise SystemExit(main())
