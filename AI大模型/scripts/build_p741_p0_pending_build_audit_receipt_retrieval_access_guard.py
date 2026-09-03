#!/usr/bin/env python3
"""Build P741 audit receipt retrieval/access guard from P740."""
from __future__ import annotations
import json
from datetime import datetime, timezone
from pathlib import Path
from build_p700_p0_real_input_pending_build_checklist import load_jsonl

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "datasets/governance/p740_p0_pending_build_audit_receipt_retention_immutability_guard.jsonl"
OUT = ROOT / "datasets/governance/p741_p0_pending_build_audit_receipt_retrieval_access_guard.jsonl"
REPORT = ROOT / "reports/p741_p0_pending_build_audit_receipt_retrieval_access_guard_report.json"
MD = ROOT / "reports/p741_p0_pending_build_audit_receipt_retrieval_access_guard.md"
FIELDS = ("audit_receipt_present", "retrieval_requested", "access_principal_verified", "receipt_retrieved", "provenance_consistent", "retrieval_validated", "formal_decision_ready")

def main() -> int:
    created=datetime.now(timezone.utc).isoformat(); source=[r for r in load_jsonl(SOURCE) if r.get("boundary")!="summary"]; rows=[]
    for order,src in enumerate(source,1):
        row={"retrieval_guard_id":f"p741::{src.get('retention_guard_id')}","retrieval_guard_order":order,"created_at":created,"boundary":src.get("boundary"),"source_p740_id":src.get("retention_guard_id"),"guard_status":"empty_no_receipt_to_retrieve","blocker_reason":"No audit receipt exists to retrieve or access-check.","operator_action":"Do not request, expose, or fabricate access to a missing receipt.","policy":"P741 checks retrieval readiness only; it does not retrieve or disclose receipts."}; row.update({f:False for f in FIELDS}); rows.append(row)
    counts={f"{f}_rows":0 for f in FIELDS}; summary={"retrieval_guard_id":"p741::summary","retrieval_guard_order":len(rows)+1,"created_at":created,"boundary":"summary","retrieval_guard_rows":len(rows),**counts,"policy":"P741 remains empty and fail-closed."}
    OUT.write_text("".join(json.dumps(r,ensure_ascii=False,sort_keys=True)+"\n" for r in rows+[summary]),encoding="utf-8"); report={"manifest_id":"P741","created_at":created,"local_only":True,"retrieval_guard_rows":len(rows),**counts,"artifact_jsonl":str(OUT.relative_to(ROOT)),"artifact_md":str(MD.relative_to(ROOT)),"policy":"P741 is planning-only and fail-closed."}; REPORT.write_text(json.dumps(report,ensure_ascii=False,indent=2,sort_keys=True)+"\n",encoding="utf-8"); MD.write_text(f"# P741 audit receipt retrieval/access guard\n\nRows: `{len(rows)}`. Receipts retrieved: `0`.\n",encoding="utf-8"); print(json.dumps({"manifest_id":"P741","retrieval_guard_rows":len(rows),"receipt_retrieved_rows":0,"output":str(REPORT)},ensure_ascii=False)); return 0
if __name__ == "__main__": raise SystemExit(main())
