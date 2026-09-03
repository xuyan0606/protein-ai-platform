#!/usr/bin/env python3
"""Validate P757 audit-receipt access/non-leak gates."""
from __future__ import annotations
import json
from datetime import datetime, timezone
from pathlib import Path
from build_p700_p0_real_input_pending_build_checklist import load_json, load_jsonl
ROOT = Path(__file__).resolve().parents[1]; SOURCE = ROOT / "datasets/governance/p756_p0_pending_build_audit_receipt_integrity_immutability_gate.jsonl"; BOARD = ROOT / "datasets/governance/p757_p0_pending_build_audit_receipt_access_nonleak_gate.jsonl"; REPORT = ROOT / "reports/p757_p0_pending_build_audit_receipt_access_nonleak_gate_report.json"; OUT = ROOT / "reports/p757_p0_pending_build_audit_receipt_access_nonleak_gate_validation_report.json"
FIELDS = ("audit_receipt_retrieval_requested", "access_subject_verified", "access_scope_authorized", "audit_receipt_retrieved", "sensitive_data_exposed", "unauthorized_export_detected", "disclosure_approved", "formal_decision_ready")
def main() -> int:
    source = [r for r in load_jsonl(SOURCE) if r.get("boundary") != "summary"]; rows = load_jsonl(BOARD); gates = rows[:-1] if rows else []; summary = rows[-1] if rows else {}; report = load_json(REPORT); failures = []
    def fail(c, x, o, e):
        if x: failures.append({"check": c, "observed": o, "expected": e})
    fail("source_rows", len(source) != 5, len(source), 5); fail("access_gate_rows", len(gates) != 5, len(gates), 5); fail("summary", summary.get("boundary") != "summary", summary.get("boundary"), "summary"); fail("coverage", {r.get("source_p756_id") for r in gates} != {r.get("integrity_gate_id") for r in source}, "mismatch", "exact")
    for field in FIELDS: fail(field, report.get(f"{field}_rows") != 0, report.get(f"{field}_rows"), 0)
    for i, row in enumerate(gates, 1):
        fail(f"row_{i}_status", row.get("gate_status") != "empty_no_receipt_to_access_or_disclose", row.get("gate_status"), "empty_no_receipt_to_access_or_disclose")
        for field in FIELDS: fail(f"row_{i}_{field}", row.get(field) is not False, row.get(field), False)
    result = {"created_at": datetime.now(timezone.utc).isoformat(), "manifest_id": "P757", "local_only": True, "success": not failures, "failure_count": len(failures), "failures": failures, "access_gate_rows": len(gates), **{f"{field}_rows": 0 for field in FIELDS}, "policy": "Validation only; P757 keeps retrieval, disclosure, and downstream decisions blocked."}
    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8"); print(json.dumps({"success": result["success"], "access_gate_rows": len(gates), "sensitive_data_exposed_rows": 0, "failures": len(failures), "output": str(OUT)}, ensure_ascii=False)); return 0 if not failures else 1
if __name__ == "__main__": raise SystemExit(main())
