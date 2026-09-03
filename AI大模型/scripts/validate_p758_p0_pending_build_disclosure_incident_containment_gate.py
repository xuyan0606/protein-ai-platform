#!/usr/bin/env python3
"""Validate P758 disclosure-incident containment gates."""
from __future__ import annotations
import json
from datetime import datetime, timezone
from pathlib import Path
from build_p700_p0_real_input_pending_build_checklist import load_json, load_jsonl
ROOT = Path(__file__).resolve().parents[1]; SOURCE = ROOT / "datasets/governance/p757_p0_pending_build_audit_receipt_access_nonleak_gate.jsonl"; BOARD = ROOT / "datasets/governance/p758_p0_pending_build_disclosure_incident_containment_gate.jsonl"; REPORT = ROOT / "reports/p758_p0_pending_build_disclosure_incident_containment_gate_report.json"; OUT = ROOT / "reports/p758_p0_pending_build_disclosure_incident_containment_gate_validation_report.json"
FIELDS = ("disclosure_incident_detected", "alert_raised", "access_contained", "owner_notified", "incident_review_completed", "remediation_validated", "formal_decision_ready", "production_execution_allowed")
def main() -> int:
    source = [r for r in load_jsonl(SOURCE) if r.get("boundary") != "summary"]; rows = load_jsonl(BOARD); gates = rows[:-1] if rows else []; summary = rows[-1] if rows else {}; report = load_json(REPORT); failures = []
    def fail(c, x, o, e):
        if x: failures.append({"check": c, "observed": o, "expected": e})
    fail("source_rows", len(source) != 5, len(source), 5); fail("containment_gate_rows", len(gates) != 5, len(gates), 5); fail("summary", summary.get("boundary") != "summary", summary.get("boundary"), "summary"); fail("coverage", {r.get("source_p757_id") for r in gates} != {r.get("access_gate_id") for r in source}, "mismatch", "exact")
    for field in FIELDS: fail(field, report.get(f"{field}_rows") != 0, report.get(f"{field}_rows"), 0)
    for i, row in enumerate(gates, 1):
        fail(f"row_{i}_status", row.get("gate_status") != "empty_no_disclosure_incident", row.get("gate_status"), "empty_no_disclosure_incident")
        for field in FIELDS: fail(f"row_{i}_{field}", row.get(field) is not False, row.get(field), False)
    result = {"created_at": datetime.now(timezone.utc).isoformat(), "manifest_id": "P758", "local_only": True, "success": not failures, "failure_count": len(failures), "failures": failures, "containment_gate_rows": len(gates), **{f"{field}_rows": 0 for field in FIELDS}, "policy": "Validation only; P758 keeps incident handling and downstream actions blocked."}
    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8"); print(json.dumps({"success": result["success"], "containment_gate_rows": len(gates), "disclosure_incident_detected_rows": 0, "failures": len(failures), "output": str(OUT)}, ensure_ascii=False)); return 0 if not failures else 1
if __name__ == "__main__": raise SystemExit(main())
