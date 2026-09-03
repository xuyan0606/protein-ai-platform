#!/usr/bin/env python3
"""Build P769 review-receipt integrity gates from P768."""
from __future__ import annotations
import json
from datetime import datetime, timezone
from pathlib import Path
from build_p700_p0_real_input_pending_build_checklist import load_jsonl

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "datasets/governance/p768_p0_pending_build_review_dispatch_readiness_gate.jsonl"
OUT = ROOT / "datasets/governance/p769_p0_pending_build_review_receipt_integrity_gate.jsonl"
REPORT = ROOT / "reports/p769_p0_pending_build_review_receipt_integrity_gate_report.json"
MD = ROOT / "reports/p769_p0_pending_build_review_receipt_integrity_gate.md"
FIELDS = ("review_dispatched", "receipt_received", "receipt_atomic_commit_validated", "receipt_hash_verified", "receipt_provenance_validated", "receipt_schema_validated", "receipt_validated", "formal_decision_ready", "restart_authorized")

def main() -> int:
    created = datetime.now(timezone.utc).isoformat()
    source = [row for row in load_jsonl(SOURCE) if row.get("boundary") != "summary"]
    rows = []
    for order, src in enumerate(source, 1):
        row = {
            "integrity_gate_id": f"p769::{src.get('dispatch_gate_id')}", "integrity_gate_order": order,
            "created_at": created, "boundary": src.get("boundary"), "source_p768_id": src.get("dispatch_gate_id"),
            "gate_status": "empty_no_review_receipt_to_validate",
            "blocker_reason": "No authorized review dispatch or authentic receipt exists for atomicity, integrity, provenance, or schema validation.",
            "operator_action": "Do not fabricate review receipts, validation results, or downstream authorization.",
            "policy": "P769 is a receipt-integrity gate only; it performs no receipt intake, review, or authorization.",
        }
        row.update({field: False for field in FIELDS}); rows.append(row)
    zero = {f"{field}_rows": 0 for field in FIELDS}
    summary = {"integrity_gate_id": "p769::summary", "integrity_gate_order": len(rows) + 1, "created_at": created, "boundary": "summary", "integrity_gate_rows": len(rows), **zero, "policy": "P769 remains empty and fail-closed."}
    OUT.write_text("".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows + [summary]), encoding="utf-8")
    report = {"manifest_id": "P769", "created_at": created, "local_only": True, "integrity_gate_rows": len(rows), **zero, "artifact_jsonl": str(OUT.relative_to(ROOT)), "artifact_md": str(MD.relative_to(ROOT)), "policy": "P769 is planning-only and fail-closed."}
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    MD.write_text(f"# P769 review-receipt integrity gate\n\nRows: `{len(rows)}`. Receipts received: `0`.\n", encoding="utf-8")
    print(json.dumps({"manifest_id": "P769", "integrity_gate_rows": len(rows), "receipt_received_rows": 0, "output": str(REPORT)}, ensure_ascii=False)); return 0

if __name__ == "__main__": raise SystemExit(main())
