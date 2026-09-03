#!/usr/bin/env python3
import json
from datetime import datetime, timezone
from pathlib import Path
from build_p700_p0_real_input_pending_build_checklist import load_json, load_jsonl

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "datasets/governance/p795_p0_pending_build_risk_acceptance_residual_risk_decision_gate.jsonl"
BOARD = ROOT / "datasets/governance/p796_p0_pending_build_control_implementation_verification_gate.jsonl"
REPORT = ROOT / "reports/p796_p0_pending_build_control_implementation_verification_gate_report.json"
OUT = ROOT / "reports/p796_p0_pending_build_control_implementation_verification_gate_validation_report.json"
FIELDS = ("control_defined", "control_owner_verified", "control_implemented", "implementation_evidence_present", "control_effectiveness_validated", "monitoring_configured", "exception_approved", "formal_decision_ready", "release_ready", "production_execution_allowed")

def main():
    source_rows = [r for r in load_jsonl(SOURCE) if r.get("boundary") != "summary"]
    rows = load_jsonl(BOARD)
    gates, summary = rows[:-1] if rows else [], rows[-1] if rows else {}
    report, failures = load_json(REPORT), []
    def fail(check, condition, observed, expected):
        if condition:
            failures.append({"check": check, "observed": observed, "expected": expected})
    fail("source_rows", len(source_rows) != 5, len(source_rows), 5)
    fail("control_gate_rows", len(gates) != 5, len(gates), 5)
    fail("summary", summary.get("boundary") != "summary", summary.get("boundary"), "summary")
    for field in FIELDS:
        fail(field, report.get(field + "_rows") != 0, report.get(field + "_rows"), 0)
    for i, row in enumerate(gates, 1):
        fail(f"row_{i}_status", row.get("gate_status") != "empty_no_verified_control_implementation", row.get("gate_status"), "empty_no_verified_control_implementation")
        for field in FIELDS:
            fail(f"row_{i}_{field}", row.get(field) is not False, row.get(field), False)
    result = {"created_at": datetime.now(timezone.utc).isoformat(), "manifest_id": "P796", "local_only": True, "success": not failures, "failure_count": len(failures), "failures": failures, "control_gate_rows": len(gates), **{field + "_rows": 0 for field in FIELDS}, "policy": "Validation only; P796 keeps control, release, and production gates blocked."}
    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"success": result["success"], "control_gate_rows": len(gates), "control_effectiveness_validated_rows": 0, "production_execution_allowed_rows": 0, "failures": len(failures), "output": str(OUT)}, ensure_ascii=False))
    return 0 if not failures else 1

if __name__ == "__main__":
    raise SystemExit(main())
