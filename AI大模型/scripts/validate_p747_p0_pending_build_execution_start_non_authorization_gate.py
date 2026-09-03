#!/usr/bin/env python3
"""Validate P747 execution-start non-authorization gates."""
from __future__ import annotations
import json
from datetime import datetime, timezone
from pathlib import Path
from build_p700_p0_real_input_pending_build_checklist import load_json, load_jsonl

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "datasets/governance/p746_p0_pending_build_all_started_continuation_register.jsonl"
BOARD = ROOT / "datasets/governance/p747_p0_pending_build_execution_start_non_authorization_gate.jsonl"
REPORT = ROOT / "reports/p747_p0_pending_build_execution_start_non_authorization_gate_report.json"
OUT = ROOT / "reports/p747_p0_pending_build_execution_start_non_authorization_gate_validation_report.json"
FIELDS = ("execution_start_requested", "execution_start_authorized", "execution_started", "real_input_received", "evidence_validated", "formal_decision_ready", "release_ready", "production_execution_allowed")

def main() -> int:
    source = [r for r in load_jsonl(SOURCE) if r.get("boundary") != "summary"]
    rows = load_jsonl(BOARD); gates = rows[:-1] if rows else []; summary = rows[-1] if rows else {}
    report = load_json(REPORT); failures = []
    def fail(check, condition, observed, expected):
        if condition: failures.append({"check": check, "observed": observed, "expected": expected})
    fail("source_rows", len(source) != 5, len(source), 5)
    fail("gate_rows", len(gates) != 5, len(gates), 5)
    fail("summary", summary.get("boundary") != "summary", summary.get("boundary"), "summary")
    fail("coverage", {r.get("source_p746_id") for r in gates} != {r.get("register_id") for r in source}, "mismatch", "exact")
    for field in FIELDS:
        fail(field, report.get(f"{field}_rows") != 0, report.get(f"{field}_rows"), 0)
    for i, row in enumerate(gates, 1):
        fail(f"row_{i}_status", row.get("gate_status") != "planning_started_execution_blocked", row.get("gate_status"), "planning_started_execution_blocked")
        for field in FIELDS:
            fail(f"row_{i}_{field}", row.get(field) is not False, row.get(field), False)
    result = {"created_at": datetime.now(timezone.utc).isoformat(), "manifest_id": "P747", "local_only": True,
              "success": not failures, "failure_count": len(failures), "failures": failures,
              "execution_gate_rows": len(gates), **{f"{field}_rows": 0 for field in FIELDS},
              "policy": "Validation only; P747 keeps execution and authorization blocked."}
    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"success": result["success"], "execution_gate_rows": len(gates), "execution_started_rows": 0, "failures": len(failures), "output": str(OUT)}, ensure_ascii=False))
    return 0 if not failures else 1

if __name__ == "__main__":
    raise SystemExit(main())
