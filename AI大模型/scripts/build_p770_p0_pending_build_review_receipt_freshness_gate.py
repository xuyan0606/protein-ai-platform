#!/usr/bin/env python3
"""Build P770 review-receipt freshness gates from P769."""
from __future__ import annotations
import json
from datetime import datetime, timezone
from pathlib import Path
from build_p700_p0_real_input_pending_build_checklist import load_jsonl

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "datasets/governance/p769_p0_pending_build_review_receipt_integrity_gate.jsonl"
OUT = ROOT / "datasets/governance/p770_p0_pending_build_review_receipt_freshness_gate.jsonl"
REPORT = ROOT / "reports/p770_p0_pending_build_review_receipt_freshness_gate_report.json"
MD = ROOT / "reports/p770_p0_pending_build_review_receipt_freshness_gate.md"
FIELDS = ("receipt_present", "receipt_timestamp_verified", "receipt_fresh", "receipt_stale", "staleness_resolved", "freshness_validated", "formal_decision_ready", "restart_authorized", "execution_started")

def main() -> int:
    created = datetime.now(timezone.utc).isoformat(); source = [row for row in load_jsonl(SOURCE) if row.get("boundary") != "summary"]; rows = []
    for order, src in enumerate(source, 1):
        row = {"freshness_gate_id": f"p770::{src.get('integrity_gate_id')}", "freshness_gate_order": order, "created_at": created, "boundary": src.get("boundary"), "source_p769_id": src.get("integrity_gate_id"), "gate_status": "empty_no_receipt_to_assess_freshness", "blocker_reason": "No authentic receipt or verified timestamp exists; freshness, staleness, and downstream use remain blocked.", "operator_action": "Do not assume freshness, resolve staleness, or use an absent receipt for decisions or restart.", "policy": "P770 is a receipt-freshness gate only; it performs no validation, decision, or execution."}
        row.update({field: False for field in FIELDS}); rows.append(row)
    zero = {f"{field}_rows": 0 for field in FIELDS}; summary = {"freshness_gate_id": "p770::summary", "freshness_gate_order": len(rows) + 1, "created_at": created, "boundary": "summary", "freshness_gate_rows": len(rows), **zero, "policy": "P770 remains empty and fail-closed."}
    OUT.write_text("".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows + [summary]), encoding="utf-8")
    report = {"manifest_id": "P770", "created_at": created, "local_only": True, "freshness_gate_rows": len(rows), **zero, "artifact_jsonl": str(OUT.relative_to(ROOT)), "artifact_md": str(MD.relative_to(ROOT)), "policy": "P770 is planning-only and fail-closed."}
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8"); MD.write_text(f"# P770 review-receipt freshness gate\n\nRows: `{len(rows)}`. Fresh receipts: `0`.\n", encoding="utf-8")
    print(json.dumps({"manifest_id": "P770", "freshness_gate_rows": len(rows), "receipt_fresh_rows": 0, "output": str(REPORT)}, ensure_ascii=False)); return 0
if __name__ == "__main__": raise SystemExit(main())
