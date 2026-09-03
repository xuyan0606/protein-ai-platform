#!/usr/bin/env python3
"""Validate P769 review-receipt integrity gates."""
from __future__ import annotations
import json
from datetime import datetime, timezone
from pathlib import Path
from build_p700_p0_real_input_pending_build_checklist import load_json, load_jsonl

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "datasets/governance/p768_p0_pending_build_review_dispatch_readiness_gate.jsonl"
BOARD = ROOT / "datasets/governance/p769_p0_pending_build_review_receipt_integrity_gate.jsonl"
REPORT = ROOT / "reports/p769_p0_pending_build_review_receipt_integrity_gate_report.json"
OUT = ROOT / "reports/p769_p0_pending_build_review_receipt_integrity_gate_validation_report.json"
FIELDS = ("review_dispatched", "receipt_received", "receipt_atomic_commit_validated", "receipt_hash_verified", "receipt_provenance_validated", "receipt_schema_validated", "receipt_validated", "formal_decision_ready", "restart_authorized")

def main() -> int:
    source = [row for row in load_jsonl(SOURCE) if row.get("boundary") != "summary"]
    rows = load_jsonl(BOARD); gates = rows[:-1] if rows else []; summary = rows[-1] if rows else {}; report = load_json(REPORT); failures = []
    def fail(check, condition, observed, expected):
        if condition: failures.append({"check": check, "observed": observed, "expected": expected})
    fail("source_rows", len(source) != 5, len(source), 5); fail("integrity_gate_rows", len(gates) != 5, len(gates), 5); fail("summary", summary.get("boundary") != "summary", summary.get("boundary"), "summary")
    fail("coverage", {row.get("source_p768_id") for row in gates} != {row.get("dispatch_gate_id") for row in source}, "mismatch", "exact")
    for field in FIELDS: fail(field, report.get(f"{field}_rows") != 0, report.get(f"{field}_rows"), 0)
    for index, row in enumerate(gates, 1):
        fail(f"row_{index}_status", row.get("gate_status") != "empty_no_review_receipt_to_validate", row.get("gate_status"), "empty_no_review_receipt_to_validate")
        for field in FIELDS: fail(f"row_{index}_{field}", row.get(field) is not False, row.get(field), False)
    result = {"created_at": datetime.now(timezone.utc).isoformat(), "manifest_id": "P769", "local_only": True, "success": not failures, "failure_count": len(failures), "failures": failures, "integrity_gate_rows": len(gates), **{f"{field}_rows": 0 for field in FIELDS}, "policy": "Validation only; P769 keeps receipts and downstream gates blocked."}
    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"success": result["success"], "integrity_gate_rows": len(gates), "receipt_received_rows": 0, "failures": len(failures), "output": str(OUT)}, ensure_ascii=False)); return 0 if not failures else 1

if __name__ == "__main__": raise SystemExit(main())
