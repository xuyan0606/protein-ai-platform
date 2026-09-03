#!/usr/bin/env python3
"""Validate P726 production-execution non-authorization guard."""
from __future__ import annotations
import json
from datetime import datetime, timezone
from pathlib import Path
from build_p700_p0_real_input_pending_build_checklist import load_json, load_jsonl

ROOT = Path(__file__).resolve().parents[1]
BOARD = ROOT / "datasets/governance/p726_p0_pending_build_production_execution_non_authorization_guard.jsonl"
REPORT = ROOT / "reports/p726_p0_pending_build_production_execution_non_authorization_guard_report.json"
OUT = ROOT / "reports/p726_p0_pending_build_production_execution_non_authorization_guard_validation_report.json"


def main() -> int:
    rows = load_jsonl(BOARD)
    lanes = rows[:-1]
    report = load_json(REPORT)
    failures = []

    def fail(check: str, condition: bool, observed: object) -> None:
        if condition:
            failures.append({"check": check, "observed": observed})

    fail("rows", len(lanes) != 5, len(lanes))
    for field in ("formal_decision_approved_rows", "release_approved_rows", "customer_scope_confirmed_rows", "production_change_reviewed_rows", "production_execution_authorized_rows", "production_execution_started_rows", "production_execution_allowed_rows", "release_ready_rows"):
        fail(field, report.get(field) != 0, report.get(field))
    for index, row in enumerate(lanes, 1):
        fail(f"row_{index}_status", row.get("guard_status") != "blocked_production_execution_non_authorization", row.get("guard_status"))
        for field in ("formal_decision_approved", "release_approved", "customer_scope_confirmed", "production_change_reviewed", "production_execution_authorized", "production_execution_started", "production_execution_allowed", "release_ready"):
            fail(f"row_{index}_{field}", row.get(field) is not False, row.get(field))

    result = {
        "created_at": datetime.now(timezone.utc).isoformat(), "manifest_id": "P726", "local_only": True,
        "success": not failures, "failure_count": len(failures), "failures": failures,
        "production_guard_rows": len(lanes), "formal_decision_approved_rows": 0,
        "release_approved_rows": 0, "customer_scope_confirmed_rows": 0,
        "production_change_reviewed_rows": 0, "production_execution_authorized_rows": 0,
        "production_execution_started_rows": 0, "production_execution_allowed_rows": 0,
        "release_ready_rows": 0, "policy": "Validation only; P726 keeps production execution unauthorized.",
    }
    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"success": result["success"], "production_guard_rows": len(lanes), "production_execution_authorized_rows": 0, "failures": len(failures), "output": str(OUT)}, ensure_ascii=False))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
