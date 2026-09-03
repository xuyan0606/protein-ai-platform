#!/usr/bin/env python3
"""Build P757 audit-receipt access/non-leak gates from P756."""
from __future__ import annotations
import json
from datetime import datetime, timezone
from pathlib import Path
from build_p700_p0_real_input_pending_build_checklist import load_jsonl
ROOT = Path(__file__).resolve().parents[1]; SOURCE = ROOT / "datasets/governance/p756_p0_pending_build_audit_receipt_integrity_immutability_gate.jsonl"; OUT = ROOT / "datasets/governance/p757_p0_pending_build_audit_receipt_access_nonleak_gate.jsonl"; REPORT = ROOT / "reports/p757_p0_pending_build_audit_receipt_access_nonleak_gate_report.json"; MD = ROOT / "reports/p757_p0_pending_build_audit_receipt_access_nonleak_gate.md"
FIELDS = ("audit_receipt_retrieval_requested", "access_subject_verified", "access_scope_authorized", "audit_receipt_retrieved", "sensitive_data_exposed", "unauthorized_export_detected", "disclosure_approved", "formal_decision_ready")
def main() -> int:
    created = datetime.now(timezone.utc).isoformat(); source = [r for r in load_jsonl(SOURCE) if r.get("boundary") != "summary"]; rows = []
    for order, src in enumerate(source, 1):
        row = {"access_gate_id": f"p757::{src.get('integrity_gate_id')}", "access_gate_order": order, "created_at": created, "boundary": src.get("boundary"), "source_p756_id": src.get("integrity_gate_id"), "gate_status": "empty_no_receipt_to_access_or_disclose", "blocker_reason": "No authentic immutable receipt exists; retrieval, disclosure, export, and sensitive-data exposure are prohibited.", "operator_action": "Do not retrieve, expose, export, or synthesize receipt content or access approval.", "policy": "P757 is an access/non-leak gate only; it performs no retrieval or disclosure."}
        row.update({field: False for field in FIELDS}); rows.append(row)
    zero = {f"{field}_rows": 0 for field in FIELDS}; summary = {"access_gate_id": "p757::summary", "access_gate_order": len(rows) + 1, "created_at": created, "boundary": "summary", "access_gate_rows": len(rows), **zero, "policy": "P757 remains empty and fail-closed."}
    OUT.write_text("".join(json.dumps(r, ensure_ascii=False, sort_keys=True) + "\n" for r in rows + [summary]), encoding="utf-8"); report = {"manifest_id": "P757", "created_at": created, "local_only": True, "access_gate_rows": len(rows), **zero, "artifact_jsonl": str(OUT.relative_to(ROOT)), "artifact_md": str(MD.relative_to(ROOT)), "policy": "P757 is planning-only and fail-closed."}; REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8"); MD.write_text(f"# P757 audit-receipt access/non-leak gate\n\nRows: `{len(rows)}`. Sensitive data exposed: `0`.\n", encoding="utf-8"); print(json.dumps({"manifest_id": "P757", "access_gate_rows": len(rows), "sensitive_data_exposed_rows": 0, "output": str(REPORT)}, ensure_ascii=False)); return 0
if __name__ == "__main__": raise SystemExit(main())
