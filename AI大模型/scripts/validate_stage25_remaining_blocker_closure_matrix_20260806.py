#!/usr/bin/env python3
"""Validate Stage 25 remaining blocker closure matrix."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
MATRIX = AI_ROOT / "reports" / "stage25_remaining_blocker_closure_matrix_20260806.json"
OUTPUT = AI_ROOT / "reports" / "stage25_remaining_blocker_closure_matrix_validation_20260806.json"
EXPECTED_BLOCKERS = {
    "stage25_new_paper_fulltext_source_table",
    "stage25_sqlite_apply",
    "stage25_formal_decisions",
    "stage25_foldx_runtime_receipt",
    "stage25_model_release_claim",
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
    fail_if(not MATRIX.exists(), failures, "matrix_exists", "missing", str(MATRIX))
    matrix = load_json(MATRIX) if MATRIX.exists() else {}
    blockers = matrix.get("blockers") if isinstance(matrix.get("blockers"), list) else []
    ids = {str(row.get("blocker_id")) for row in blockers if isinstance(row, dict)}
    fail_if(ids != EXPECTED_BLOCKERS, failures, "blocker_ids", sorted(ids), sorted(EXPECTED_BLOCKERS))
    fail_if(matrix.get("blocker_rows") != 5, failures, "blocker_rows", matrix.get("blocker_rows"), 5)
    fail_if(matrix.get("completion_ready_rows") != 0, failures, "completion_ready_rows_zero", matrix.get("completion_ready_rows"), 0)
    fail_if(matrix.get("machine_path_ready_rows") != 5, failures, "machine_path_ready_rows", matrix.get("machine_path_ready_rows"), 5)
    fail_if(matrix.get("external_input_required_rows") != 5, failures, "external_input_required_rows", matrix.get("external_input_required_rows"), 5)
    for index, row in enumerate(blockers, start=1):
        prefix = f"blockers[{index}]"
        fail_if(row.get("status") != "blocked", failures, f"{prefix}.status_blocked", row.get("status"), "blocked")
        fail_if(row.get("completion_ready") is not False, failures, f"{prefix}.completion_ready_false", row.get("completion_ready"), False)
        fail_if(row.get("machine_path_ready") is not True, failures, f"{prefix}.machine_path_ready_true", row.get("machine_path_ready"), True)
        fail_if(row.get("external_input_required") is not True, failures, f"{prefix}.external_input_required_true", row.get("external_input_required"), True)
        fail_if(not str(row.get("closure_condition") or "").strip(), failures, f"{prefix}.closure_condition_present", row.get("closure_condition"), "non-empty")
    for flag in ("external_sqlite_mutated", "apply_executed", "export_safe_released", "safe_for_model_claim", "release_ready"):
        fail_if(matrix.get(flag) is not False, failures, f"{flag}_false", matrix.get(flag), False)
    fail_if(matrix.get("formal_decision_rows_written") != 0, failures, "formal_decision_rows_written_zero", matrix.get("formal_decision_rows_written"), 0)
    report = {
        "schema_version": 1,
        "created_at": "2026-08-06",
        "mode": "stage25_remaining_blocker_closure_matrix_validation",
        "stage": 25,
        "matrix_valid": not failures,
        "failure_count": len(failures),
        "failures": failures,
        "blocker_rows": len(blockers),
        "completion_ready_rows": matrix.get("completion_ready_rows"),
        "machine_path_ready_rows": matrix.get("machine_path_ready_rows"),
        "external_input_required_rows": matrix.get("external_input_required_rows"),
        "external_sqlite_mutated": False,
        "formal_decision_rows_written": 0,
        "apply_executed": False,
        "export_safe_released": False,
        "safe_for_model_claim": False,
        "release_ready": False,
    }
    OUTPUT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(OUTPUT), "matrix_valid": report["matrix_valid"], "failure_count": report["failure_count"], "blocker_rows": report["blocker_rows"], "completion_ready_rows": report["completion_ready_rows"]}, ensure_ascii=False, sort_keys=True))
    return 0 if report["matrix_valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
