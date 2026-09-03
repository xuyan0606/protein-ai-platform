#!/usr/bin/env python3
"""Validate Stage 25 family-specific apply transaction plans."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
PLANS = AI_ROOT / "datasets" / "governance" / "stage25_family_apply_transaction_plans_20260806.jsonl"
OUTPUT = AI_ROOT / "reports" / "stage25_family_apply_transaction_plan_validation_20260806.json"

EXPECTED_FAMILIES = {"xylanase", "lipase"}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        row = json.loads(line)
        if not isinstance(row, dict):
            raise ValueError(f"{path}:{line_number} must contain a JSON object")
        rows.append(row)
    return rows


def fail_if(condition: bool, failures: list[dict[str, Any]], check: str, observed: Any, expected: Any) -> None:
    if condition:
        failures.append({"check": check, "observed": observed, "expected": expected})


def main() -> int:
    failures: list[dict[str, Any]] = []
    fail_if(not PLANS.exists(), failures, "plans_exist", "missing", str(PLANS))
    rows = load_jsonl(PLANS) if PLANS.exists() else []
    families = {str(row.get("family")) for row in rows}
    fail_if(families != EXPECTED_FAMILIES, failures, "families", sorted(families), sorted(EXPECTED_FAMILIES))

    ready_to_apply_rows = 0
    write_operation_count = 0
    for index, row in enumerate(rows, start=1):
        prefix = f"rows[{index}]"
        fail_if(row.get("stage") != 25, failures, f"{prefix}.stage", row.get("stage"), 25)
        fail_if(row.get("status") != "blocked", failures, f"{prefix}.status_blocked", row.get("status"), "blocked")
        fail_if(not row.get("blockers"), failures, f"{prefix}.blockers_present", row.get("blockers"), "non-empty")
        fail_if(row.get("source_ready_for_sqlite_apply_rows") != 0, failures, f"{prefix}.source_ready_rows_zero", row.get("source_ready_for_sqlite_apply_rows"), 0)
        fail_if(row.get("paper_insert_count") != 0, failures, f"{prefix}.paper_insert_count_zero", row.get("paper_insert_count"), 0)
        fail_if(row.get("write_operation_count") != 0, failures, f"{prefix}.write_operation_count_zero", row.get("write_operation_count"), 0)
        fail_if(row.get("sqlite_write_sql") != [], failures, f"{prefix}.sqlite_write_sql_empty", row.get("sqlite_write_sql"), [])
        for flag in (
            "backup_required_before_apply",
            "begin_immediate_required",
            "rollback_required_on_any_failure",
        ):
            fail_if(row.get(flag) is not True, failures, f"{prefix}.{flag}_true", row.get(flag), True)
        for flag in (
            "apply_executed",
            "external_sqlite_mutated",
            "export_safe_released",
            "safe_for_model_claim",
            "release_ready",
        ):
            fail_if(row.get(flag) is not False, failures, f"{prefix}.{flag}_false", row.get(flag), False)
        fail_if(row.get("formal_decision_rows_written") != 0, failures, f"{prefix}.formal_decision_rows_written_zero", row.get("formal_decision_rows_written"), 0)
        ready_to_apply_rows += 1 if row.get("status") == "ready_to_apply" else 0
        write_operation_count += int(row.get("write_operation_count") or 0)

    report = {
        "schema_version": 1,
        "created_at": "2026-08-06",
        "mode": "stage25_family_apply_transaction_plan_validation",
        "stage": 25,
        "plans_valid": not failures,
        "failure_count": len(failures),
        "failures": failures,
        "plan_rows": len(rows),
        "ready_to_apply_rows": ready_to_apply_rows,
        "write_operation_count": write_operation_count,
        "sqlite_write_sql_count": 0,
        "external_sqlite_mutated": False,
        "formal_decision_rows_written": 0,
        "apply_executed": False,
        "export_safe_released": False,
        "release_ready": False,
        "safe_for_model_claim": False,
    }
    OUTPUT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(OUTPUT), "plans_valid": report["plans_valid"], "failure_count": report["failure_count"], "plan_rows": report["plan_rows"], "ready_to_apply_rows": report["ready_to_apply_rows"], "write_operation_count": report["write_operation_count"]}, ensure_ascii=False, sort_keys=True))
    return 0 if report["plans_valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
