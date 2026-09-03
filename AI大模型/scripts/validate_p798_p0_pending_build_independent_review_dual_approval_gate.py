#!/usr/bin/env python3
import json
from datetime import datetime, timezone
from pathlib import Path
from build_p700_p0_real_input_pending_build_checklist import load_json, load_jsonl

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "datasets/governance/p797_p0_pending_build_control_exception_remediation_closure_gate.jsonl"
BOARD = ROOT / "datasets/governance/p798_p0_pending_build_independent_review_dual_approval_gate.jsonl"
REPORT = ROOT / "reports/p798_p0_pending_build_independent_review_dual_approval_gate_report.json"
OUT = ROOT / "reports/p798_p0_pending_build_independent_review_dual_approval_gate_validation_report.json"
FIELDS = ("review_scope_defined", "independent_reviewer_verified", "review_evidence_present", "conflict_check_passed", "first_approval_present", "second_approval_present", "dual_approval_validated", "formal_decision_ready", "release_ready", "production_execution_allowed")

def main():
    source_rows = [r for r in load_jsonl(SOURCE) if r.get("boundary") != "summary"]
    rows = load_jsonl(BOARD)
    gates, summary = rows[:-1] if rows else [], rows[-1] if rows else {}
    report, failures = load_json(REPORT), []
    def fail(check, condition, observed, expected):
        if condition:
            failures.append({"check": check, "observed": observed, "expected": expected})
    fail("source_rows", len(source_rows) != 5, len(source_rows), 5)
    fail("review_gate_rows", len(gates) != 5, len(gates), 5)
    fail("summary", summary.get("boundary") != "summary", summary.get("boundary"), "summary")
    for field in FIELDS:
        fail(field, report.get(field + "_rows") != 0, report.get(field + "_rows"), 0)
    for i, row in enumerate(gates, 1):
        fail(f"row_{i}_status", row.get("gate_status") != "empty_no_independent_review_or_dual_approval", row.get("gate_status"), "empty_no_independent_review_or_dual_approval")
        for field in FIELDS:
            fail(f"row_{i}_{field}", row.get(field) is not False, row.get(field), False)
    result = {"created_at": datetime.now(timezone.utc).isoformat(), "manifest_id": "P798", "local_only": True, "success": not failures, "failure_count": len(failures), "failures": failures, "review_gate_rows": len(gates), **{field + "_rows": 0 for field in FIELDS}, "policy": "Validation only; P798 keeps review, approval, release, and production gates blocked."}
    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"success": result["success"], "review_gate_rows": len(gates), "dual_approval_validated_rows": 0, "formal_decision_ready_rows": 0, "failures": len(failures), "output": str(OUT)}, ensure_ascii=False))
    return 0 if not failures else 1

if __name__ == "__main__":
    raise SystemExit(main())
