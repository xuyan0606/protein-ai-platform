#!/usr/bin/env python3
"""Build P740 audit receipt retention/immutability guard from P739."""
from __future__ import annotations
import json
from datetime import datetime, timezone
from pathlib import Path
from build_p700_p0_real_input_pending_build_checklist import load_jsonl

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "datasets/governance/p739_p0_pending_build_production_execution_audit_receipt_guard.jsonl"
OUT = ROOT / "datasets/governance/p740_p0_pending_build_audit_receipt_retention_immutability_guard.jsonl"
REPORT = ROOT / "reports/p740_p0_pending_build_audit_receipt_retention_immutability_guard_report.json"
MD = ROOT / "reports/p740_p0_pending_build_audit_receipt_retention_immutability_guard.md"
FIELDS = ("audit_receipt_present", "retention_policy_bound", "receipt_immutable", "provenance_retained", "retention_validated", "formal_decision_ready")

def main() -> int:
    created = datetime.now(timezone.utc).isoformat(); source = [r for r in load_jsonl(SOURCE) if r.get("boundary") != "summary"]; rows = []
    for order, src in enumerate(source, 1):
        row = {"retention_guard_id": f"p740::{src.get('audit_receipt_guard_id')}", "retention_guard_order": order, "created_at": created, "boundary": src.get("boundary"), "source_p739_id": src.get("audit_receipt_guard_id"), "guard_status": "empty_no_receipt_to_retain", "blocker_reason": "No audit receipt exists to retain, make immutable, or validate for provenance retention.", "operator_action": "Do not fabricate, mutate, or retain a receipt that does not exist.", "policy": "P740 is a retention/immutability guard only; it never creates receipts or authorizes execution."}
        row.update({f: False for f in FIELDS}); rows.append(row)
    counts={f"{f}_rows":0 for f in FIELDS}; summary={"retention_guard_id":"p740::summary","retention_guard_order":len(rows)+1,"created_at":created,"boundary":"summary","retention_guard_rows":len(rows),**counts,"policy":"P740 remains empty and fail-closed."}
    OUT.write_text("".join(json.dumps(r,ensure_ascii=False,sort_keys=True)+"\n" for r in rows+[summary]),encoding="utf-8")
    report={"manifest_id":"P740","created_at":created,"local_only":True,"retention_guard_rows":len(rows),**counts,"artifact_jsonl":str(OUT.relative_to(ROOT)),"artifact_md":str(MD.relative_to(ROOT)),"policy":"P740 is planning-only and fail-closed."}
    REPORT.write_text(json.dumps(report,ensure_ascii=False,indent=2,sort_keys=True)+"\n",encoding="utf-8"); MD.write_text(f"# P740 audit receipt retention/immutability guard\n\nRows: `{len(rows)}`. Receipts retained: `0`.\n",encoding="utf-8")
    print(json.dumps({"manifest_id":"P740","retention_guard_rows":len(rows),"audit_receipt_present_rows":0,"output":str(REPORT)},ensure_ascii=False)); return 0
if __name__ == "__main__": raise SystemExit(main())
