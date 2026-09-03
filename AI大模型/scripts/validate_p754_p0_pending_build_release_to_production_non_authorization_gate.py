#!/usr/bin/env python3
"""Validate P754 release-to-production non-authorization gates."""
from __future__ import annotations
import json
from datetime import datetime, timezone
from pathlib import Path
from build_p700_p0_real_input_pending_build_checklist import load_json, load_jsonl
ROOT = Path(__file__).resolve().parents[1]; SOURCE = ROOT / "datasets/governance/p753_p0_pending_build_decision_to_release_nonpromotion_gate.jsonl"; BOARD = ROOT / "datasets/governance/p754_p0_pending_build_release_to_production_non_authorization_gate.jsonl"; REPORT = ROOT / "reports/p754_p0_pending_build_release_to_production_non_authorization_gate_report.json"; OUT = ROOT / "reports/p754_p0_pending_build_release_to_production_non_authorization_gate_validation_report.json"
FIELDS = ("release_approved", "customer_scope_confirmed", "production_change_reviewed", "rollback_plan_validated", "execution_receipt_contract_ready", "production_execution_requested", "production_execution_authorized", "production_execution_started")
def main() -> int:
    source = [r for r in load_jsonl(SOURCE) if r.get("boundary") != "summary"]; rows = load_jsonl(BOARD); gates = rows[:-1] if rows else []; summary = rows[-1] if rows else {}; report = load_json(REPORT); failures = []
    def fail(c, x, o, e):
        if x: failures.append({"check": c, "observed": o, "expected": e})
    fail("source_rows", len(source) != 5, len(source), 5); fail("production_gate_rows", len(gates) != 5, len(gates), 5); fail("summary", summary.get("boundary") != "summary", summary.get("boundary"), "summary"); fail("coverage", {r.get("source_p753_id") for r in gates} != {r.get("promotion_gate_id") for r in source}, "mismatch", "exact")
    for field in FIELDS: fail(field, report.get(f"{field}_rows") != 0, report.get(f"{field}_rows"), 0)
    for i, row in enumerate(gates, 1):
        fail(f"row_{i}_status", row.get("gate_status") != "empty_no_authorized_production_transition", row.get("gate_status"), "empty_no_authorized_production_transition")
        for field in FIELDS: fail(f"row_{i}_{field}", row.get(field) is not False, row.get(field), False)
    result = {"created_at": datetime.now(timezone.utc).isoformat(), "manifest_id": "P754", "local_only": True, "success": not failures, "failure_count": len(failures), "failures": failures, "production_gate_rows": len(gates), **{f"{field}_rows": 0 for field in FIELDS}, "policy": "Validation only; P754 keeps release and production execution blocked."}
    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8"); print(json.dumps({"success": result["success"], "production_gate_rows": len(gates), "production_execution_started_rows": 0, "failures": len(failures), "output": str(OUT)}, ensure_ascii=False)); return 0 if not failures else 1
if __name__ == "__main__": raise SystemExit(main())
