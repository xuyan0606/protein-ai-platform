#!/usr/bin/env python3
"""Validate P731 review-dispatch readiness."""
from __future__ import annotations
import json
from datetime import datetime, timezone
from pathlib import Path
from build_p700_p0_real_input_pending_build_checklist import load_json, load_jsonl

ROOT = Path(__file__).resolve().parents[1]
BOARD = ROOT / "datasets/governance/p731_p0_pending_build_review_dispatch_readiness.jsonl"
REPORT = ROOT / "reports/p731_p0_pending_build_review_dispatch_readiness_report.json"
OUT = ROOT / "reports/p731_p0_pending_build_review_dispatch_readiness_validation_report.json"


def main() -> int:
    rows = load_jsonl(BOARD)
    entries = rows[:-1]
    report = load_json(REPORT)
    failures = []

    def fail(check: str, condition: bool, observed: object) -> None:
        if condition:
            failures.append({"check": check, "observed": observed})

    fail("rows", len(entries) != 5, len(entries))
    for field in ("dispatch_target_defined_rows", "dispatch_authorized_rows", "execution_window_defined_rows", "review_dispatched_rows", "review_executed_rows", "formal_decision_ready_rows"):
        fail(field, report.get(field) != 0, report.get(field))
    for index, row in enumerate(entries, 1):
        fail(f"row_{index}_status", row.get("dispatch_status") != "blocked_not_ready", row.get("dispatch_status"))
        for field in ("dispatch_target_defined", "dispatch_authorized", "execution_window_defined", "review_dispatched", "review_executed", "formal_decision_ready"):
            fail(f"row_{index}_{field}", row.get(field) is not False, row.get(field))
    result = {
        "created_at": datetime.now(timezone.utc).isoformat(), "manifest_id": "P731", "local_only": True,
        "success": not failures, "failure_count": len(failures), "failures": failures,
        "dispatch_readiness_rows": len(entries), "dispatch_target_defined_rows": 0,
        "dispatch_authorized_rows": 0, "execution_window_defined_rows": 0,
        "review_dispatched_rows": 0, "review_executed_rows": 0,
        "formal_decision_ready_rows": 0, "policy": "Validation only; P731 remains blocked and undispatched.",
    }
    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"success": result["success"], "dispatch_readiness_rows": len(entries), "review_dispatched_rows": 0, "failures": len(failures), "output": str(OUT)}, ensure_ascii=False))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
