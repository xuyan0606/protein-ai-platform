#!/usr/bin/env python3
"""Validate P723 release-claim non-promotion guard."""
from __future__ import annotations
import json
from datetime import datetime, timezone
from pathlib import Path

from build_p700_p0_real_input_pending_build_checklist import load_json, load_jsonl

ROOT = Path(__file__).resolve().parents[1]
BOARD = ROOT / "datasets/governance/p723_p0_pending_build_release_claim_non_promotion_guard.jsonl"
REPORT = ROOT / "reports/p723_p0_pending_build_release_claim_non_promotion_guard_report.json"
OUT = ROOT / "reports/p723_p0_pending_build_release_claim_non_promotion_guard_validation_report.json"


def main() -> int:
    rows = load_jsonl(BOARD)
    lanes = rows[:-1]
    report = load_json(REPORT)
    failures = []

    def fail(check: str, condition: bool, observed: object) -> None:
        if condition:
            failures.append({"check": check, "observed": observed})

    fail("rows", len(lanes) != 5, len(lanes))
    for field in ("formal_decision_approved_rows", "claim_promoted_rows", "release_ready_rows", "production_execution_allowed_rows"):
        fail(field, report.get(field) != 0, report.get(field))
    for index, row in enumerate(lanes, 1):
        fail(f"row_{index}_status", row.get("guard_status") != "blocked_claim_non_promotion", row.get("guard_status"))
        for field in ("formal_decision_approved", "model_claim_allowed", "customer_delivery_allowed", "release_claim_allowed", "production_claim_allowed", "claim_promoted", "release_ready", "production_execution_allowed"):
            fail(f"row_{index}_{field}", row.get(field) is not False, row.get(field))

    result = {
        "created_at": datetime.now(timezone.utc).isoformat(), "manifest_id": "P723", "local_only": True,
        "success": not failures, "failure_count": len(failures), "failures": failures,
        "non_promotion_guard_rows": len(lanes), "formal_decision_approved_rows": 0,
        "claim_promoted_rows": 0, "release_ready_rows": 0, "production_execution_allowed_rows": 0,
        "policy": "Validation only; P723 keeps all downstream claims blocked.",
    }
    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"success": result["success"], "non_promotion_guard_rows": len(lanes), "claim_promoted_rows": 0, "failures": len(failures), "output": str(OUT)}, ensure_ascii=False))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
