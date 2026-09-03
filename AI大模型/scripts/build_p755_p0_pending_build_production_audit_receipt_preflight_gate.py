#!/usr/bin/env python3
"""Build P755 production audit-receipt preflight gates from P754."""
from __future__ import annotations
import json
from datetime import datetime, timezone
from pathlib import Path
from build_p700_p0_real_input_pending_build_checklist import load_jsonl
ROOT = Path(__file__).resolve().parents[1]; SOURCE = ROOT / "datasets/governance/p754_p0_pending_build_release_to_production_non_authorization_gate.jsonl"; OUT = ROOT / "datasets/governance/p755_p0_pending_build_production_audit_receipt_preflight_gate.jsonl"; REPORT = ROOT / "reports/p755_p0_pending_build_production_audit_receipt_preflight_gate_report.json"; MD = ROOT / "reports/p755_p0_pending_build_production_audit_receipt_preflight_gate.md"
FIELDS = ("production_execution_requested", "production_execution_authorized", "change_record_present", "audit_receipt_contract_validated", "audit_receipt_present", "execution_result_written", "rollback_result_written", "formal_decision_ready")
def main() -> int:
    created = datetime.now(timezone.utc).isoformat(); source = [r for r in load_jsonl(SOURCE) if r.get("boundary") != "summary"]; rows = []
    for order, src in enumerate(source, 1):
        row = {"audit_preflight_id": f"p755::{src.get('production_gate_id')}", "audit_preflight_order": order, "created_at": created, "boundary": src.get("boundary"), "source_p754_id": src.get("production_gate_id"), "gate_status": "empty_no_production_execution_to_audit", "blocker_reason": "No authorized production execution or change record exists; no audit receipt or execution result may be fabricated.", "operator_action": "Do not execute, synthesize, backfill, or attest production results or audit receipts.", "policy": "P755 is an audit-receipt preflight gate only; it performs no production action or attestation."}
        row.update({field: False for field in FIELDS}); rows.append(row)
    zero = {f"{field}_rows": 0 for field in FIELDS}; summary = {"audit_preflight_id": "p755::summary", "audit_preflight_order": len(rows) + 1, "created_at": created, "boundary": "summary", "audit_preflight_rows": len(rows), **zero, "policy": "P755 remains empty and fail-closed."}
    OUT.write_text("".join(json.dumps(r, ensure_ascii=False, sort_keys=True) + "\n" for r in rows + [summary]), encoding="utf-8"); report = {"manifest_id": "P755", "created_at": created, "local_only": True, "audit_preflight_rows": len(rows), **zero, "artifact_jsonl": str(OUT.relative_to(ROOT)), "artifact_md": str(MD.relative_to(ROOT)), "policy": "P755 is planning-only and fail-closed."}; REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8"); MD.write_text(f"# P755 production audit-receipt preflight gate\n\nRows: `{len(rows)}`. Audit receipts present: `0`.\n", encoding="utf-8"); print(json.dumps({"manifest_id": "P755", "audit_preflight_rows": len(rows), "audit_receipt_present_rows": 0, "output": str(REPORT)}, ensure_ascii=False)); return 0
if __name__ == "__main__": raise SystemExit(main())
