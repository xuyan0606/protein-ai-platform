#!/usr/bin/env python3
"""Cross-bind Stage 25 remaining blocker closure, activation and coverage reports."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
CLOSURE = AI_ROOT / "reports" / "stage25_remaining_blocker_closure_matrix_20260806.json"
ACTIVATION = AI_ROOT / "reports" / "stage25_blocker_activation_map_20260806.json"
COVERAGE = AI_ROOT / "reports" / "stage25_latest_blocker_coverage_audit_20260806.json"
OUT = AI_ROOT / "reports" / "stage25_remaining_blocker_cross_binding_validation_report.json"
EXPECTED_BLOCKERS = {
    "stage25_new_paper_fulltext_source_table",
    "stage25_sqlite_apply",
    "stage25_formal_decisions",
    "stage25_foldx_runtime_receipt",
    "stage25_model_release_claim",
}
FALSE_FLAGS = (
    "external_sqlite_mutated",
    "apply_executed",
    "export_safe_released",
    "safe_for_model_claim",
    "release_ready",
)


def load_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return data


def fail_if(condition: bool, failures: list[dict[str, Any]], check: str, observed: Any, expected: Any) -> None:
    if condition:
        failures.append({"check": check, "observed": observed, "expected": expected})


def rows_by_blocker(rows: Any, source: str, failures: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    if not isinstance(rows, list):
        failures.append({"check": f"{source}_rows_list", "observed": type(rows).__name__, "expected": "list"})
        return {}
    result: dict[str, dict[str, Any]] = {}
    duplicate_ids: list[str] = []
    for row in rows:
        if not isinstance(row, dict):
            failures.append({"check": f"{source}_row_object", "observed": row, "expected": "dict"})
            continue
        blocker_id = str(row.get("blocker_id"))
        if blocker_id in result:
            duplicate_ids.append(blocker_id)
        result[blocker_id] = row
    fail_if(bool(duplicate_ids), failures, f"{source}_duplicate_blocker_ids", sorted(set(duplicate_ids)), [])
    return result


def build_report(closure_path: Path, activation_path: Path, coverage_path: Path) -> dict[str, Any]:
    failures: list[dict[str, Any]] = []
    for label, path in (("closure", closure_path), ("activation", activation_path), ("coverage", coverage_path)):
        fail_if(not path.exists(), failures, f"{label}_report_exists", "missing", str(path))

    closure = load_json(closure_path) if closure_path.exists() else {}
    activation = load_json(activation_path) if activation_path.exists() else {}
    coverage = load_json(coverage_path) if coverage_path.exists() else {}

    closure_rows = rows_by_blocker(closure.get("blockers"), "closure", failures)
    activation_rows = rows_by_blocker(activation.get("activations"), "activation", failures)
    coverage_rows = rows_by_blocker(coverage.get("rows"), "coverage", failures)

    closure_ids = set(closure_rows)
    activation_ids = set(activation_rows)
    coverage_ids = set(coverage_rows)
    shared_ids = closure_ids & activation_ids & coverage_ids

    fail_if(closure.get("mode") != "stage25_remaining_blocker_closure_matrix", failures, "closure_mode", closure.get("mode"), "stage25_remaining_blocker_closure_matrix")
    fail_if(activation.get("mode") != "stage25_blocker_activation_map", failures, "activation_mode", activation.get("mode"), "stage25_blocker_activation_map")
    fail_if(coverage.get("mode") != "stage25_latest_blocker_coverage_audit", failures, "coverage_mode", coverage.get("mode"), "stage25_latest_blocker_coverage_audit")

    fail_if(closure_ids != EXPECTED_BLOCKERS, failures, "closure_blocker_ids_exact", sorted(closure_ids), sorted(EXPECTED_BLOCKERS))
    fail_if(activation_ids != EXPECTED_BLOCKERS, failures, "activation_blocker_ids_exact", sorted(activation_ids), sorted(EXPECTED_BLOCKERS))
    fail_if(coverage_ids != EXPECTED_BLOCKERS, failures, "coverage_blocker_ids_exact", sorted(coverage_ids), sorted(EXPECTED_BLOCKERS))
    fail_if(not (closure_ids == activation_ids == coverage_ids), failures, "blocker_id_sets_match", {
        "closure": sorted(closure_ids),
        "activation": sorted(activation_ids),
        "coverage": sorted(coverage_ids),
    }, sorted(EXPECTED_BLOCKERS))

    fail_if(closure.get("blocker_rows") != 5, failures, "closure_blocker_rows", closure.get("blocker_rows"), 5)
    fail_if(activation.get("activation_rows") != 5, failures, "activation_rows", activation.get("activation_rows"), 5)
    fail_if(coverage.get("blocker_rows") != 5, failures, "coverage_blocker_rows", coverage.get("blocker_rows"), 5)
    fail_if(closure.get("completion_ready_rows") != 0, failures, "closure_completion_ready_rows_zero", closure.get("completion_ready_rows"), 0)
    fail_if(activation.get("activation_completion_ready_rows") != 0, failures, "activation_completion_ready_rows_zero", activation.get("activation_completion_ready_rows"), 0)
    fail_if(coverage.get("uncovered_blockers") != [], failures, "coverage_uncovered_blockers_empty", coverage.get("uncovered_blockers"), [])

    exact_current_receipt_rows = 0
    exact_closure_condition_rows = 0
    coverage_complete_rows = 0
    blocked_status_rows = 0
    for blocker_id in sorted(EXPECTED_BLOCKERS):
        c_row = closure_rows.get(blocker_id) or {}
        a_row = activation_rows.get(blocker_id) or {}
        v_row = coverage_rows.get(blocker_id) or {}
        prefix = f"blocker[{blocker_id}]"

        c_status = c_row.get("status")
        v_status = v_row.get("status")
        if c_status == "blocked" and v_status == "blocked":
            blocked_status_rows += 1
        fail_if(c_status != "blocked", failures, f"{prefix}.closure_status_blocked", c_status, "blocked")
        fail_if(v_status != "blocked", failures, f"{prefix}.coverage_status_blocked", v_status, "blocked")
        fail_if(c_row.get("completion_ready") is not False, failures, f"{prefix}.closure_completion_ready_false", c_row.get("completion_ready"), False)
        fail_if(a_row.get("current_completion_ready") is not False, failures, f"{prefix}.activation_current_completion_ready_false", a_row.get("current_completion_ready"), False)
        if v_row.get("coverage_complete") is True:
            coverage_complete_rows += 1
        fail_if(v_row.get("coverage_complete") is not True, failures, f"{prefix}.coverage_complete_true", v_row.get("coverage_complete"), True)

        if c_row.get("current_receipt") == v_row.get("current_receipt"):
            exact_current_receipt_rows += 1
        fail_if(c_row.get("current_receipt") != v_row.get("current_receipt"), failures, f"{prefix}.current_receipt_exact", v_row.get("current_receipt"), c_row.get("current_receipt"))
        if c_row.get("closure_condition") == v_row.get("closure_condition"):
            exact_closure_condition_rows += 1
        fail_if(c_row.get("closure_condition") != v_row.get("closure_condition"), failures, f"{prefix}.closure_condition_exact", v_row.get("closure_condition"), c_row.get("closure_condition"))

    for label, report in (("closure", closure), ("activation", activation), ("coverage", coverage)):
        for flag in FALSE_FLAGS:
            fail_if(report.get(flag) is not False, failures, f"{label}.{flag}_false", report.get(flag), False)
        fail_if(report.get("formal_decision_rows_written") != 0, failures, f"{label}.formal_decision_rows_written_zero", report.get("formal_decision_rows_written"), 0)

    return {
        "schema_version": 1,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "local_only": True,
        "mode": "stage25_remaining_blocker_cross_binding_validation",
        "stage": 25,
        "success": not failures,
        "cross_binding_valid": not failures,
        "failure_count": len(failures),
        "failures": failures,
        "expected_blocker_rows": len(EXPECTED_BLOCKERS),
        "shared_blocker_rows": len(shared_ids),
        "shared_blocker_ids": sorted(shared_ids),
        "closure_blocker_rows": len(closure_rows),
        "activation_blocker_rows": len(activation_rows),
        "coverage_blocker_rows": len(coverage_rows),
        "closure_completion_ready_rows": closure.get("completion_ready_rows"),
        "activation_completion_ready_rows": activation.get("activation_completion_ready_rows"),
        "coverage_complete_rows": coverage_complete_rows,
        "blocked_status_rows": blocked_status_rows,
        "exact_current_receipt_rows": exact_current_receipt_rows,
        "exact_closure_condition_rows": exact_closure_condition_rows,
        "uncovered_blockers": coverage.get("uncovered_blockers"),
        "external_sqlite_mutated": False,
        "formal_decision_rows_written": 0,
        "apply_executed": False,
        "export_safe_released": False,
        "safe_for_model_claim": False,
        "release_ready": False,
        "policy": "The five remaining Stage 25 blockers must stay identically represented across closure matrix, activation map and coverage audit before any release or model claim can open.",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate Stage 25 remaining blocker cross-binding")
    parser.add_argument("--closure", type=Path, default=CLOSURE)
    parser.add_argument("--activation", type=Path, default=ACTIVATION)
    parser.add_argument("--coverage", type=Path, default=COVERAGE)
    parser.add_argument("--output", type=Path, default=OUT)
    args = parser.parse_args()

    report = build_report(args.closure, args.activation, args.coverage)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "success": report["success"],
        "failure_count": report["failure_count"],
        "shared_blocker_rows": report["shared_blocker_rows"],
        "coverage_complete_rows": report["coverage_complete_rows"],
        "output": str(args.output),
    }, ensure_ascii=False, sort_keys=True))
    return 0 if report["success"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
