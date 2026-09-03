#!/usr/bin/env python3
"""Validate P755 production audit-receipt preflight gates."""
from __future__ import annotations
import json
from datetime import datetime, timezone
from pathlib import Path
from build_p700_p0_real_input_pending_build_checklist import load_json, load_jsonl
ROOT = Path(__file__).resolve().parents[1]; SOURCE = ROOT / "datasets/governance/p754_p0_pending_build_release_to_production_non_authorization_gate.jsonl"; BOARD = ROOT / "datasets/governance/p755_p0_pending_build_production_audit_receipt_preflight_gate.jsonl"; REPORT = ROOT / "reports/p755_p0_pending_build_production_audit_receipt_preflight_gate_report.json"; OUT = ROOT / "reports/p755_p0_pending_build_production_audit_receipt_preflight_gate_validation_report.json"
FIELDS = ("production_execution_requested", "production_execution_authorized", "change_record_present", "audit_receipt_contract_validated", "audit_receipt_present", "execution_result_written", "rollback_result_written", "formal_decision_ready")
def main() -> int:
    source = [r for r in load_jsonl(SOURCE) if r.get("boundary") != "summary"]; rows = load_jsonl(BOARD); gates = rows[:-1] if rows else []; summary = rows[-1] if rows else {}; report = load_json(REPORT); failures = []
    def fail(c, x, o, e):
        if x: failures.append({"check": c, "observed": o, "expected": e})
    fail("source_rows", len(source) != 5, len(source), 5); fail("audit_preflight_rows", len(gates) != 5, len(gates), 5); fail("summary", summary.get("boundary") != "summary", summary.get("boundary"), "summary"); fail("coverage", {r.get("source_p754_id") for r in gates} != {r.get("production_gate_id") for r in source}, "mismatch", "exact")
    for field in FIELDS: fail(field, report.get(f"{field}_rows") != 0, report.get(f"{field}_rows"), 0)
    for i, row in enumerate(gates, 1):
        fail(f"row_{i}_status", row.get("gate_status") != "empty_no_production_execution_to_audit", row.get("gate_status"), "empty_no_production_execution_to_audit")
        for field in FIELDS: fail(f"row_{i}_{field}", row.get(field) is not False, row.get(field), False)
    result = {"created_at": datetime.now(timezone.utc).isoformat(), "manifest_id": "P755", "local_only": True, "success": not failures, "failure_count": len(failures), "failures": failures, "audit_preflight_rows": len(gates), **{f"{field}_rows": 0 for field in FIELDS}, "policy": "Validation only; P755 keeps production execution and audit receipts blocked."}
    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8"); print(json.dumps({"success": result["success"], "audit_preflight_rows": len(gates), "audit_receipt_present_rows": 0, "failures": len(failures), "output": str(OUT)}, ensure_ascii=False)); return 0 if not failures else 1
if __name__ == "__main__": raise SystemExit(main())
