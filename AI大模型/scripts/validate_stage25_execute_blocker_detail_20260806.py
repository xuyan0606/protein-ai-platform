#!/usr/bin/env python3
"""Validate Stage 25 execute-request blocker detail report."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
DETAIL = AI_ROOT / "reports" / "stage25_execute_blocker_detail_20260806.json"
OUTPUT = AI_ROOT / "reports" / "stage25_execute_blocker_detail_validation_20260806.json"
EXPECTED_CHECKS = {
    "approved_for_family_importer": 4,
    "human_review_status": 4,
    "intake_approval": 4,
    "paper_pdf": 4,
    "payload_draft": 4,
    "source_locators": 4,
}


def load_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return data


def fail_if(condition: bool, failures: list[dict[str, Any]], check: str, observed: Any, expected: Any) -> None:
    if condition:
        failures.append({"check": check, "observed": observed, "expected": expected})


def main() -> int:
    failures: list[dict[str, Any]] = []
    fail_if(not DETAIL.exists(), failures, "detail_exists", "missing", str(DETAIL))
    detail = load_json(DETAIL) if DETAIL.exists() else {}
    rows = detail.get("proposal_blocker_rows") if isinstance(detail.get("proposal_blocker_rows"), list) else []

    fail_if(detail.get("mode") != "stage25_execute_blocker_detail", failures, "mode", detail.get("mode"), "stage25_execute_blocker_detail")
    fail_if(detail.get("execute_requested") is not True, failures, "execute_requested_true", detail.get("execute_requested"), True)
    fail_if(detail.get("executor_status") != "blocked", failures, "executor_status_blocked", detail.get("executor_status"), "blocked")
    fail_if(detail.get("executor_failure_count") != 24, failures, "executor_failure_count", detail.get("executor_failure_count"), 24)
    fail_if(detail.get("failure_check_counts") != EXPECTED_CHECKS, failures, "failure_check_counts", detail.get("failure_check_counts"), EXPECTED_CHECKS)
    fail_if(len(rows) != 4, failures, "proposal_blocker_rows", len(rows), 4)
    for index, row in enumerate(rows, start=1):
        prefix = f"proposal_blocker_rows[{index}]"
        fail_if(row.get("blocker_count") != 6, failures, f"{prefix}.blocker_count", row.get("blocker_count"), 6)
    fail_if(detail.get("db_before_integrity_ok_count") != 3, failures, "db_before_integrity_ok_count", detail.get("db_before_integrity_ok_count"), 3)
    fail_if(detail.get("backup_count") != 0, failures, "backup_count_zero", detail.get("backup_count"), 0)
    fail_if(detail.get("apply_result_count") != 0, failures, "apply_result_count_zero", detail.get("apply_result_count"), 0)
    fail_if(detail.get("after_present") is not False, failures, "after_present_false", detail.get("after_present"), False)

    for flag in ("external_sqlite_mutated", "apply_executed", "export_safe_released", "safe_for_model_claim", "release_ready"):
        fail_if(detail.get(flag) is not False, failures, f"{flag}_false", detail.get(flag), False)
    fail_if(detail.get("formal_decision_rows_written") != 0, failures, "formal_decision_rows_written_zero", detail.get("formal_decision_rows_written"), 0)

    validation = {
        "schema_version": 1,
        "created_at": "2026-08-06",
        "mode": "stage25_execute_blocker_detail_validation",
        "stage": 25,
        "detail_valid": not failures,
        "failure_count": len(failures),
        "failures": failures,
        "execute_requested": detail.get("execute_requested"),
        "executor_failure_count": detail.get("executor_failure_count"),
        "proposal_blocker_rows": len(rows),
        "external_sqlite_mutated": False,
        "formal_decision_rows_written": 0,
        "apply_executed": False,
        "export_safe_released": False,
        "safe_for_model_claim": False,
        "release_ready": False,
    }
    OUTPUT.write_text(json.dumps(validation, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(OUTPUT), "detail_valid": validation["detail_valid"], "failure_count": validation["failure_count"], "executor_failure_count": validation["executor_failure_count"]}, ensure_ascii=False, sort_keys=True))
    return 0 if validation["detail_valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
