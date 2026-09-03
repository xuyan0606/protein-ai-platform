#!/usr/bin/env python3
"""Validate P728 stop/restart entry board."""
from __future__ import annotations
import json
from datetime import datetime, timezone
from pathlib import Path
from build_p700_p0_real_input_pending_build_checklist import load_json, load_jsonl

ROOT = Path(__file__).resolve().parents[1]
BOARD = ROOT / "datasets/governance/p728_p0_pending_build_stop_restart_entry_board.jsonl"
REPORT = ROOT / "reports/p728_p0_pending_build_stop_restart_entry_board_report.json"
OUT = ROOT / "reports/p728_p0_pending_build_stop_restart_entry_board_validation_report.json"


def main() -> int:
    rows = load_jsonl(BOARD)
    boundaries = rows[:-1]
    report = load_json(REPORT)
    failures = []

    def fail(check: str, condition: bool, observed: object) -> None:
        if condition:
            failures.append({"check": check, "observed": observed})

    fail("rows", len(boundaries) != 5, len(boundaries))
    fail("stop_active", report.get("stop_condition_active_rows") != 5, report.get("stop_condition_active_rows"))
    for field in ("restart_trigger_received_rows", "restart_trigger_validated_rows", "restart_authorized_rows", "work_restarted_rows", "formal_decision_ready_rows", "release_ready_rows", "production_execution_allowed_rows"):
        fail(field, report.get(field) != 0, report.get(field))
    for index, row in enumerate(boundaries, 1):
        fail(f"row_{index}_state", row.get("state") != "blocked_stop_required", row.get("state"))
        fail(f"row_{index}_stop", row.get("stop_condition_active") is not True, row.get("stop_condition_active"))
        for field in ("restart_trigger_received", "restart_trigger_validated", "restart_authorized", "work_restarted", "formal_decision_ready", "release_ready", "production_execution_allowed"):
            fail(f"row_{index}_{field}", row.get(field) is not False, row.get(field))
    result = {
        "created_at": datetime.now(timezone.utc).isoformat(), "manifest_id": "P728", "local_only": True,
        "success": not failures, "failure_count": len(failures), "failures": failures,
        "stop_restart_rows": len(boundaries), "stop_condition_active_rows": 5,
        "restart_trigger_received_rows": 0, "restart_trigger_validated_rows": 0,
        "restart_authorized_rows": 0, "work_restarted_rows": 0,
        "formal_decision_ready_rows": 0, "release_ready_rows": 0,
        "production_execution_allowed_rows": 0,
        "policy": "Validation only; P728 keeps stop active and restart disabled.",
    }
    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"success": result["success"], "stop_restart_rows": len(boundaries), "restart_authorized_rows": 0, "failures": len(failures), "output": str(OUT)}, ensure_ascii=False))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
