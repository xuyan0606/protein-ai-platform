#!/usr/bin/env python3
"""Validate P734 receipt freshness/staleness guard."""
from __future__ import annotations
import json
from datetime import datetime, timezone
from pathlib import Path
from build_p700_p0_real_input_pending_build_checklist import load_json, load_jsonl

ROOT = Path(__file__).resolve().parents[1]
BOARD = ROOT / "datasets/governance/p734_p0_pending_build_review_receipt_freshness_staleness_guard.jsonl"
REPORT = ROOT / "reports/p734_p0_pending_build_review_receipt_freshness_staleness_guard_report.json"
OUT = ROOT / "reports/p734_p0_pending_build_review_receipt_freshness_staleness_guard_validation_report.json"
FIELDS = ("receipt_fresh", "receipt_stale", "staleness_resolved", "timestamp_verified", "freshness_validated", "formal_decision_ready")

def main() -> int:
    rows = load_jsonl(BOARD); guards = rows[:-1]; report = load_json(REPORT); failures = []
    def fail(check, condition, observed):
        if condition: failures.append({"check": check, "observed": observed})
    fail("rows", len(guards) != 5, len(guards))
    for field in FIELDS: fail(field, report.get(f"{field}_rows") != 0, report.get(f"{field}_rows"))
    for i, row in enumerate(guards, 1):
        fail(f"row_{i}_status", row.get("guard_status") != "empty_no_receipt_to_age", row.get("guard_status"))
        for field in FIELDS: fail(f"row_{i}_{field}", row.get(field) is not False, row.get(field))
    result = {"created_at": datetime.now(timezone.utc).isoformat(), "manifest_id": "P734", "local_only": True,
              "success": not failures, "failure_count": len(failures), "failures": failures,
              "freshness_guard_rows": len(guards), "receipt_fresh_rows": 0, "receipt_stale_rows": 0,
              "staleness_resolved_rows": 0, "timestamp_verified_rows": 0, "freshness_validated_rows": 0,
              "formal_decision_ready_rows": 0, "policy": "Validation only; no receipt exists to age."}
    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"success": result["success"], "freshness_guard_rows": len(guards), "receipt_fresh_rows": 0, "failures": len(failures), "output": str(OUT)}, ensure_ascii=False))
    return 0 if not failures else 1

if __name__ == "__main__": raise SystemExit(main())
