#!/usr/bin/env python3
"""Validate P725 customer-delivery non-authorization guard."""
from __future__ import annotations
import json
from datetime import datetime, timezone
from pathlib import Path
from build_p700_p0_real_input_pending_build_checklist import load_json, load_jsonl

ROOT = Path(__file__).resolve().parents[1]
BOARD = ROOT / "datasets/governance/p725_p0_pending_build_customer_delivery_non_authorization_guard.jsonl"
REPORT = ROOT / "reports/p725_p0_pending_build_customer_delivery_non_authorization_guard_report.json"
OUT = ROOT / "reports/p725_p0_pending_build_customer_delivery_non_authorization_guard_validation_report.json"


def main() -> int:
    rows = load_jsonl(BOARD)
    lanes = rows[:-1]
    report = load_json(REPORT)
    failures = []

    def fail(check: str, condition: bool, observed: object) -> None:
        if condition:
            failures.append({"check": check, "observed": observed})

    fail("rows", len(lanes) != 5, len(lanes))
    for field in ("formal_decision_approved_rows", "customer_scope_confirmed_rows", "delivery_artifact_validated_rows", "customer_delivery_authorized_rows", "customer_delivery_ready_rows", "release_ready_rows", "production_execution_allowed_rows"):
        fail(field, report.get(field) != 0, report.get(field))
    for index, row in enumerate(lanes, 1):
        fail(f"row_{index}_status", row.get("guard_status") != "blocked_customer_delivery_non_authorization", row.get("guard_status"))
        for field in ("formal_decision_approved", "customer_scope_confirmed", "delivery_artifact_validated", "customer_delivery_authorized", "customer_delivery_ready", "release_ready", "production_execution_allowed"):
            fail(f"row_{index}_{field}", row.get(field) is not False, row.get(field))

    result = {
        "created_at": datetime.now(timezone.utc).isoformat(), "manifest_id": "P725", "local_only": True,
        "success": not failures, "failure_count": len(failures), "failures": failures,
        "delivery_guard_rows": len(lanes), "formal_decision_approved_rows": 0,
        "customer_scope_confirmed_rows": 0, "delivery_artifact_validated_rows": 0,
        "customer_delivery_authorized_rows": 0, "customer_delivery_ready_rows": 0,
        "release_ready_rows": 0, "production_execution_allowed_rows": 0,
        "policy": "Validation only; P725 keeps customer delivery unauthorized.",
    }
    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"success": result["success"], "delivery_guard_rows": len(lanes), "customer_delivery_authorized_rows": 0, "failures": len(failures), "output": str(OUT)}, ensure_ascii=False))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
