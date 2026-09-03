#!/usr/bin/env python3
"""Build P739 production-execution audit receipt guard from P738."""
from __future__ import annotations
import json
from datetime import datetime, timezone
from pathlib import Path
from build_p700_p0_real_input_pending_build_checklist import load_jsonl

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "datasets/governance/p738_p0_pending_build_nonpromotion_to_production_execution_guard.jsonl"
OUT = ROOT / "datasets/governance/p739_p0_pending_build_production_execution_audit_receipt_guard.jsonl"
REPORT = ROOT / "reports/p739_p0_pending_build_production_execution_audit_receipt_guard_report.json"
MD = ROOT / "reports/p739_p0_pending_build_production_execution_audit_receipt_guard.md"
FIELDS = ("execution_requested", "audit_receipt_present", "rollback_plan_present", "execution_result_recorded", "audit_receipt_validated", "production_execution_allowed")

def main() -> int:
    created = datetime.now(timezone.utc).isoformat(); source = [r for r in load_jsonl(SOURCE) if r.get("boundary") != "summary"]; rows = []
    for order, src in enumerate(source, 1):
        row = {"audit_receipt_guard_id": f"p739::{src.get('execution_guard_id')}", "audit_receipt_guard_order": order, "created_at": created, "boundary": src.get("boundary"), "source_p738_id": src.get("execution_guard_id"), "guard_status": "empty_no_execution_to_audit", "blocker_reason": "No production execution was requested, so no audit receipt or result exists.", "operator_action": "Do not create an audit receipt or execution result for an action that did not occur.", "policy": "P739 audits execution evidence only; it never initiates or authorizes production execution."}
        row.update({f: False for f in FIELDS}); rows.append(row)
    counts = {f"{f}_rows": 0 for f in FIELDS}; summary = {"audit_receipt_guard_id":"p739::summary","audit_receipt_guard_order":len(rows)+1,"created_at":created,"boundary":"summary","audit_receipt_guard_rows":len(rows),**counts,"policy":"P739 remains empty and fail-closed."}
    OUT.write_text("".join(json.dumps(r,ensure_ascii=False,sort_keys=True)+"\n" for r in rows+[summary]),encoding="utf-8")
    report={"manifest_id":"P739","created_at":created,"local_only":True,"audit_receipt_guard_rows":len(rows),**counts,"artifact_jsonl":str(OUT.relative_to(ROOT)),"artifact_md":str(MD.relative_to(ROOT)),"policy":"P739 is planning-only and fail-closed."}
    REPORT.write_text(json.dumps(report,ensure_ascii=False,indent=2,sort_keys=True)+"\n",encoding="utf-8"); MD.write_text(f"# P739 production execution audit receipt guard\n\nRows: `{len(rows)}`. Audit receipts present: `0`.\n",encoding="utf-8")
    print(json.dumps({"manifest_id":"P739","audit_receipt_guard_rows":len(rows),"audit_receipt_present_rows":0,"output":str(REPORT)},ensure_ascii=False)); return 0
if __name__ == "__main__": raise SystemExit(main())
