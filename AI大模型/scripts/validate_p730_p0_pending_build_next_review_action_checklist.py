#!/usr/bin/env python3
"""Validate P730 next-review action checklist."""
from __future__ import annotations
import json
from datetime import datetime, timezone
from pathlib import Path
from build_p700_p0_real_input_pending_build_checklist import load_json, load_jsonl

ROOT = Path(__file__).resolve().parents[1]
BOARD = ROOT / "datasets/governance/p730_p0_pending_build_next_review_action_checklist.jsonl"
REPORT = ROOT / "reports/p730_p0_pending_build_next_review_action_checklist_report.json"
OUT = ROOT / "reports/p730_p0_pending_build_next_review_action_checklist_validation_report.json"


def main() -> int:
    rows = load_jsonl(BOARD)
    actions = rows[:-1]
    report = load_json(REPORT)
    failures = []

    def fail(check: str, condition: bool, observed: object) -> None:
        if condition:
            failures.append({"check": check, "observed": observed})

    fail("rows", len(actions) != 5, len(actions))
    fail("scheduled", report.get("review_scheduled_rows") != 5, report.get("review_scheduled_rows"))
    for field in ("review_executed_rows", "new_evidence_detected_rows", "restart_authorized_rows", "work_restarted_rows", "formal_decision_ready_rows"):
        fail(field, report.get(field) != 0, report.get(field))
    for index, row in enumerate(actions, 1):
        fail(f"row_{index}_status", row.get("review_action_status") != "queued_not_executed", row.get("review_action_status"))
        fail(f"row_{index}_scheduled", row.get("review_scheduled") is not True, row.get("review_scheduled"))
        for field in ("review_executed", "new_evidence_detected", "restart_authorized", "work_restarted", "formal_decision_ready"):
            fail(f"row_{index}_{field}", row.get(field) is not False, row.get(field))
    result = {
        "created_at": datetime.now(timezone.utc).isoformat(), "manifest_id": "P730", "local_only": True,
        "success": not failures, "failure_count": len(failures), "failures": failures,
        "next_review_rows": len(actions), "review_scheduled_rows": 5, "review_executed_rows": 0,
        "new_evidence_detected_rows": 0, "restart_authorized_rows": 0, "work_restarted_rows": 0,
        "formal_decision_ready_rows": 0, "policy": "Validation only; P730 remains queued and fail-closed.",
    }
    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"success": result["success"], "next_review_rows": len(actions), "review_executed_rows": 0, "failures": len(failures), "output": str(OUT)}, ensure_ascii=False))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
