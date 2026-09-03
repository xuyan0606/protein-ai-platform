#!/usr/bin/env python3
"""Validate P721 formal-intake non-write guard audit."""
from __future__ import annotations
import json
from datetime import datetime, timezone
from pathlib import Path

from build_p700_p0_real_input_pending_build_checklist import load_json, load_jsonl

ROOT = Path(__file__).resolve().parents[1]
BOARD = ROOT / "datasets/governance/p721_p0_pending_build_formal_intake_non_write_guard_audit.jsonl"
REPORT = ROOT / "reports/p721_p0_pending_build_formal_intake_non_write_guard_audit_report.json"
OUT = ROOT / "reports/p721_p0_pending_build_formal_intake_non_write_guard_audit_validation_report.json"


def main() -> int:
    rows = load_jsonl(BOARD)
    lanes = rows[:-1]
    report = load_json(REPORT)
    failures = []

    def fail(check: str, condition: bool, observed: object) -> None:
        if condition:
            failures.append({"check": check, "observed": observed})

    fail("rows", len(lanes) != 5, len(lanes))
    for field in (
        "formal_intake_dry_run_executed_rows",
        "formal_intake_written_rows",
        "runtime_receipt_written_rows",
        "training_label_written_rows",
        "reviewed_decision_written_rows",
        "formal_decision_ready_rows",
    ):
        fail(field, report.get(field) != 0, report.get(field))
    for index, row in enumerate(lanes, 1):
        fail(f"row_{index}_status", row.get("guard_status") != "open_non_write_fail_closed", row.get("guard_status"))
        for field in (
            "formal_intake_dry_run_executed",
            "formal_intake_written",
            "runtime_receipt_written",
            "training_label_written",
            "reviewed_decision_written",
            "formal_decision_ready",
        ):
            fail(f"row_{index}_{field}", row.get(field) is not False, row.get(field))

    result = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "manifest_id": "P721",
        "local_only": True,
        "success": not failures,
        "failure_count": len(failures),
        "failures": failures,
        "non_write_guard_rows": len(lanes),
        "formal_intake_dry_run_executed_rows": 0,
        "formal_intake_written_rows": 0,
        "runtime_receipt_written_rows": 0,
        "training_label_written_rows": 0,
        "reviewed_decision_written_rows": 0,
        "formal_decision_ready_rows": 0,
        "policy": "Validation only; P721 confirms all formal-intake writes remain blocked.",
    }
    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"success": result["success"], "non_write_guard_rows": len(lanes), "formal_intake_written_rows": 0, "failures": len(failures), "output": str(OUT)}, ensure_ascii=False))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
