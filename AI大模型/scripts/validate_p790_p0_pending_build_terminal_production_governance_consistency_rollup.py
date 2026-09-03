#!/usr/bin/env python3
import json
from datetime import datetime, timezone
from pathlib import Path
from build_p700_p0_real_input_pending_build_checklist import load_json, load_jsonl

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "datasets/governance/p789_p0_pending_build_production_audit_receipt_access_disclosure_non_leak_gate.jsonl"
BOARD = ROOT / "datasets/governance/p790_p0_pending_build_terminal_production_governance_consistency_rollup.jsonl"
REPORT = ROOT / "reports/p790_p0_pending_build_terminal_production_governance_consistency_rollup_report.json"
OUT = ROOT / "reports/p790_p0_pending_build_terminal_production_governance_consistency_rollup_validation_report.json"
FIELDS = ("real_input_received", "evidence_validated", "formal_decision_ready", "authorization_granted", "release_ready", "customer_delivery_ready", "production_execution_allowed", "audit_receipt_present", "receipt_retrieved", "disclosure_approved", "terminal_unblocked")

def main():
    source_rows = [r for r in load_jsonl(SOURCE) if r.get("boundary") != "summary"]
    rows = load_jsonl(BOARD)
    gates, summary = rows[:-1] if rows else [], rows[-1] if rows else {}
    report, failures = load_json(REPORT), []
    def fail(check, condition, observed, expected):
        if condition:
            failures.append({"check": check, "observed": observed, "expected": expected})
    fail("source_rows", len(source_rows) != 5, len(source_rows), 5)
    fail("rollup_rows", len(gates) != 5, len(gates), 5)
    fail("summary", summary.get("boundary") != "summary", summary.get("boundary"), "summary")
    for field in FIELDS:
        fail(field, report.get(field + "_rows") != 0, report.get(field + "_rows"), 0)
    for i, row in enumerate(gates, 1):
        fail(f"row_{i}_status", row.get("rollup_status") != "terminal_governance_blocked", row.get("rollup_status"), "terminal_governance_blocked")
        for field in FIELDS:
            fail(f"row_{i}_{field}", row.get(field) is not False, row.get(field), False)
    result = {"created_at": datetime.now(timezone.utc).isoformat(), "manifest_id": "P790", "local_only": True, "success": not failures, "failure_count": len(failures), "failures": failures, "rollup_rows": len(gates), **{field + "_rows": 0 for field in FIELDS}, "policy": "Validation only; P790 confirms terminal production governance remains fail-closed."}
    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"success": result["success"], "rollup_rows": len(gates), "terminal_unblocked_rows": 0, "production_execution_allowed_rows": 0, "failures": len(failures), "output": str(OUT)}, ensure_ascii=False))
    return 0 if not failures else 1

if __name__ == "__main__":
    raise SystemExit(main())
