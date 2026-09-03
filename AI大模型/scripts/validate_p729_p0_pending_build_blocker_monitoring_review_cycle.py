#!/usr/bin/env python3
"""Validate P729 blocker monitoring/review cycle."""
from __future__ import annotations
import json
from datetime import datetime, timezone
from pathlib import Path
from build_p700_p0_real_input_pending_build_checklist import load_json, load_jsonl

ROOT = Path(__file__).resolve().parents[1]
BOARD = ROOT / "datasets/governance/p729_p0_pending_build_blocker_monitoring_review_cycle.jsonl"
REPORT = ROOT / "reports/p729_p0_pending_build_blocker_monitoring_review_cycle_report.json"
OUT = ROOT / "reports/p729_p0_pending_build_blocker_monitoring_review_cycle_validation_report.json"


def main() -> int:
    rows = load_jsonl(BOARD)
    boundaries = rows[:-1]
    report = load_json(REPORT)
    failures = []

    def fail(check: str, condition: bool, observed: object) -> None:
        if condition:
            failures.append({"check": check, "observed": observed})

    fail("rows", len(boundaries) != 5, len(boundaries))
    fail("cycle_defined", report.get("review_cycle_defined_rows") != 5, report.get("review_cycle_defined_rows"))
    for field in ("review_due_rows", "review_executed_rows", "staleness_reassessed_rows", "new_evidence_detected_rows", "restart_trigger_validated_rows", "restart_authorized_rows", "work_restarted_rows", "formal_decision_ready_rows"):
        fail(field, report.get(field) != 0, report.get(field))
    for index, row in enumerate(boundaries, 1):
        fail(f"row_{index}_status", row.get("monitoring_status") != "blocked_pending_periodic_review", row.get("monitoring_status"))
        fail(f"row_{index}_cycle", row.get("review_cycle_defined") is not True, row.get("review_cycle_defined"))
        for field in ("review_due", "review_executed", "staleness_reassessed", "new_evidence_detected", "restart_trigger_validated", "restart_authorized", "work_restarted", "formal_decision_ready"):
            fail(f"row_{index}_{field}", row.get(field) is not False, row.get(field))
    result = {
        "created_at": datetime.now(timezone.utc).isoformat(), "manifest_id": "P729", "local_only": True,
        "success": not failures, "failure_count": len(failures), "failures": failures,
        "monitoring_rows": len(boundaries), "review_cycle_defined_rows": 5,
        "review_due_rows": 0, "review_executed_rows": 0, "staleness_reassessed_rows": 0,
        "new_evidence_detected_rows": 0, "restart_trigger_validated_rows": 0,
        "restart_authorized_rows": 0, "work_restarted_rows": 0, "formal_decision_ready_rows": 0,
        "policy": "Validation only; P729 keeps periodic review pending and restart disabled.",
    }
    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"success": result["success"], "monitoring_rows": len(boundaries), "review_executed_rows": 0, "failures": len(failures), "output": str(OUT)}, ensure_ascii=False))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
