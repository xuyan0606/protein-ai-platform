#!/usr/bin/env python3
"""Validate P751 formal-decision authorization preflight gates."""
from __future__ import annotations
import json
from datetime import datetime, timezone
from pathlib import Path
from build_p700_p0_real_input_pending_build_checklist import load_json, load_jsonl
ROOT = Path(__file__).resolve().parents[1]; SOURCE = ROOT / "datasets/governance/p750_p0_pending_build_evidence_to_decision_nonpromotion_gate.jsonl"; BOARD = ROOT / "datasets/governance/p751_p0_pending_build_formal_decision_authorization_preflight_gate.jsonl"; REPORT = ROOT / "reports/p751_p0_pending_build_formal_decision_authorization_preflight_gate_report.json"; OUT = ROOT / "reports/p751_p0_pending_build_formal_decision_authorization_preflight_gate_validation_report.json"
FIELDS = ("real_input_verified", "evidence_chain_validated", "independent_review_completed", "authorizer_identity_verified", "authorization_scope_verified", "formal_decision_write_allowed", "formal_decision_written", "release_ready", "production_execution_allowed")
def main() -> int:
    source = [r for r in load_jsonl(SOURCE) if r.get("boundary") != "summary"]; rows = load_jsonl(BOARD); gates = rows[:-1] if rows else []; summary = rows[-1] if rows else {}; report = load_json(REPORT); failures = []
    def fail(c, x, o, e):
        if x: failures.append({"check": c, "observed": o, "expected": e})
    fail("source_rows", len(source) != 5, len(source), 5); fail("authorization_preflight_rows", len(gates) != 5, len(gates), 5); fail("summary", summary.get("boundary") != "summary", summary.get("boundary"), "summary"); fail("coverage", {r.get("source_p750_id") for r in gates} != {r.get("nonpromotion_gate_id") for r in source}, "mismatch", "exact")
    for field in FIELDS: fail(field, report.get(f"{field}_rows") != 0, report.get(f"{field}_rows"), 0)
    for i, row in enumerate(gates, 1):
        fail(f"row_{i}_status", row.get("gate_status") != "empty_no_authorization_preflight", row.get("gate_status"), "empty_no_authorization_preflight")
        for field in FIELDS: fail(f"row_{i}_{field}", row.get(field) is not False, row.get(field), False)
    result = {"created_at": datetime.now(timezone.utc).isoformat(), "manifest_id": "P751", "local_only": True, "success": not failures, "failure_count": len(failures), "failures": failures, "authorization_preflight_rows": len(gates), **{f"{field}_rows": 0 for field in FIELDS}, "policy": "Validation only; P751 keeps authorization and decision writes blocked."}
    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8"); print(json.dumps({"success": result["success"], "authorization_preflight_rows": len(gates), "formal_decision_write_allowed_rows": 0, "failures": len(failures), "output": str(OUT)}, ensure_ascii=False)); return 0 if not failures else 1
if __name__ == "__main__": raise SystemExit(main())
