#!/usr/bin/env python3
import json
from datetime import datetime, timezone
from pathlib import Path
from build_p700_p0_real_input_pending_build_checklist import load_jsonl

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "datasets/governance/p788_p0_pending_build_production_audit_retention_immutability_gate.jsonl"
OUT = ROOT / "datasets/governance/p789_p0_pending_build_production_audit_receipt_access_disclosure_non_leak_gate.jsonl"
REPORT = ROOT / "reports/p789_p0_pending_build_production_audit_receipt_access_disclosure_non_leak_gate_report.json"
MD = ROOT / "reports/p789_p0_pending_build_production_audit_receipt_access_disclosure_non_leak_gate.md"
FIELDS = ("receipt_immutable", "retrieval_requested", "access_subject_verified", "access_scope_authorized", "receipt_retrieved", "sensitive_data_exposed", "unauthorized_export_detected", "disclosure_approved", "formal_decision_ready", "production_execution_allowed")

def main():
    created = datetime.now(timezone.utc).isoformat()
    source_rows = [r for r in load_jsonl(SOURCE) if r.get("boundary") != "summary"]
    rows = []
    for i, source in enumerate(source_rows, 1):
        row = {"access_gate_id": f"p789::{source.get('retention_gate_id')}", "access_gate_order": i, "created_at": created, "boundary": source.get("boundary"), "source_p788_id": source.get("retention_gate_id"), "gate_status": "empty_no_immutable_receipt_to_retrieve_or_disclose", "blocker_reason": "No immutable production audit receipt exists for authorized retrieval, scoped access, export, or disclosure.", "operator_action": "Do not retrieve, export, disclose, or attest production audit receipts.", "policy": "P789 is an access/disclosure non-leak gate only; it performs no receipt retrieval or disclosure."}
        row.update({field: False for field in FIELDS})
        rows.append(row)
    zero = {field + "_rows": 0 for field in FIELDS}
    summary = {"access_gate_id": "p789::summary", "access_gate_order": len(rows) + 1, "created_at": created, "boundary": "summary", "access_gate_rows": len(rows), **zero, "policy": "P789 remains empty and fail-closed."}
    OUT.write_text("".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows + [summary]), encoding="utf-8")
    report = {"manifest_id": "P789", "created_at": created, "local_only": True, "access_gate_rows": len(rows), **zero, "artifact_jsonl": str(OUT.relative_to(ROOT)), "artifact_md": str(MD.relative_to(ROOT)), "policy": "P789 is planning-only and fail-closed."}
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    MD.write_text(f"# P789 production audit receipt access/disclosure non-leak gate\n\nRows: `{len(rows)}`. Retrieved receipts: `0`. Unauthorized exports: `0`.\n", encoding="utf-8")
    print(json.dumps({"manifest_id": "P789", "access_gate_rows": len(rows), "receipt_retrieved_rows": 0, "unauthorized_export_detected_rows": 0, "output": str(REPORT)}, ensure_ascii=False))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
