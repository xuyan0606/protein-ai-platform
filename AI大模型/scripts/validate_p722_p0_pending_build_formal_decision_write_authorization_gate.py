#!/usr/bin/env python3
"""Validate P722 formal-decision write authorization gate."""
from __future__ import annotations
import json
from datetime import datetime, timezone
from pathlib import Path

from build_p700_p0_real_input_pending_build_checklist import load_json, load_jsonl

ROOT = Path(__file__).resolve().parents[1]
BOARD = ROOT / "datasets/governance/p722_p0_pending_build_formal_decision_write_authorization_gate.jsonl"
REPORT = ROOT / "reports/p722_p0_pending_build_formal_decision_write_authorization_gate_report.json"
OUT = ROOT / "reports/p722_p0_pending_build_formal_decision_write_authorization_gate_validation_report.json"


def main() -> int:
    rows = load_jsonl(BOARD)
    lanes = rows[:-1]
    report = load_json(REPORT)
    failures = []

    def fail(check: str, condition: bool, observed: object) -> None:
        if condition:
            failures.append({"check": check, "observed": observed})

    fail("rows", len(lanes) != 5, len(lanes))
    for field in ("authorization_approved_rows", "formal_decision_write_allowed_rows", "formal_decision_written_rows", "release_ready_rows", "production_execution_allowed_rows"):
        fail(field, report.get(field) != 0, report.get(field))
    for index, row in enumerate(lanes, 1):
        fail(f"row_{index}_status", row.get("gate_status") != "blocked_authorization_prerequisites_missing", row.get("gate_status"))
        for field in ("real_input_received", "evidence_validated", "owner_acknowledged", "decision_route_executed", "authorization_approved", "formal_decision_write_allowed", "formal_decision_written", "release_ready", "production_execution_allowed"):
            fail(f"row_{index}_{field}", row.get(field) is not False, row.get(field))

    result = {
        "created_at": datetime.now(timezone.utc).isoformat(), "manifest_id": "P722", "local_only": True,
        "success": not failures, "failure_count": len(failures), "failures": failures,
        "authorization_gate_rows": len(lanes), "authorization_approved_rows": 0,
        "formal_decision_write_allowed_rows": 0, "formal_decision_written_rows": 0,
        "release_ready_rows": 0, "production_execution_allowed_rows": 0,
        "policy": "Validation only; P722 keeps formal-decision writes disabled.",
    }
    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"success": result["success"], "authorization_gate_rows": len(lanes), "formal_decision_write_allowed_rows": 0, "failures": len(failures), "output": str(OUT)}, ensure_ascii=False))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
