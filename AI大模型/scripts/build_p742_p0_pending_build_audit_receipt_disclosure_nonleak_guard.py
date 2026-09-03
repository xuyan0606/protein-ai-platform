#!/usr/bin/env python3
"""Build P742 audit receipt disclosure/non-leak guard from P741."""
from __future__ import annotations
import json
from datetime import datetime, timezone
from pathlib import Path
from build_p700_p0_real_input_pending_build_checklist import load_jsonl

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "datasets/governance/p741_p0_pending_build_audit_receipt_retrieval_access_guard.jsonl"
OUT = ROOT / "datasets/governance/p742_p0_pending_build_audit_receipt_disclosure_nonleak_guard.jsonl"
REPORT = ROOT / "reports/p742_p0_pending_build_audit_receipt_disclosure_nonleak_guard_report.json"
MD = ROOT / "reports/p742_p0_pending_build_audit_receipt_disclosure_nonleak_guard.md"
FIELDS = ("audit_receipt_present", "disclosure_requested", "access_authorized", "sensitive_data_exposed", "unauthorized_export_detected", "nonleak_validated", "formal_decision_ready")

def main() -> int:
    created=datetime.now(timezone.utc).isoformat(); source=[r for r in load_jsonl(SOURCE) if r.get("boundary")!="summary"]; rows=[]
    for order,src in enumerate(source,1):
        row={"disclosure_guard_id":f"p742::{src.get('retrieval_guard_id')}","disclosure_guard_order":order,"created_at":created,"boundary":src.get("boundary"),"source_p741_id":src.get("retrieval_guard_id"),"guard_status":"empty_no_receipt_to_disclose","blocker_reason":"No audit receipt exists to disclose, export, or inspect for sensitive-data leakage.","operator_action":"Do not disclose, export, or synthesize receipt content.","policy":"P742 is a disclosure/non-leak guard only; it does not expose or distribute receipts."}; row.update({f:False for f in FIELDS}); rows.append(row)
    counts={f"{f}_rows":0 for f in FIELDS}; summary={"disclosure_guard_id":"p742::summary","disclosure_guard_order":len(rows)+1,"created_at":created,"boundary":"summary","disclosure_guard_rows":len(rows),**counts,"policy":"P742 remains empty and fail-closed."}
    OUT.write_text("".join(json.dumps(r,ensure_ascii=False,sort_keys=True)+"\n" for r in rows+[summary]),encoding="utf-8"); report={"manifest_id":"P742","created_at":created,"local_only":True,"disclosure_guard_rows":len(rows),**counts,"artifact_jsonl":str(OUT.relative_to(ROOT)),"artifact_md":str(MD.relative_to(ROOT)),"policy":"P742 is planning-only and fail-closed."}; REPORT.write_text(json.dumps(report,ensure_ascii=False,indent=2,sort_keys=True)+"\n",encoding="utf-8"); MD.write_text(f"# P742 audit receipt disclosure/non-leak guard\n\nRows: `{len(rows)}`. Sensitive data exposed: `0`.\n",encoding="utf-8"); print(json.dumps({"manifest_id":"P742","disclosure_guard_rows":len(rows),"sensitive_data_exposed_rows":0,"output":str(REPORT)},ensure_ascii=False)); return 0
if __name__ == "__main__": raise SystemExit(main())
