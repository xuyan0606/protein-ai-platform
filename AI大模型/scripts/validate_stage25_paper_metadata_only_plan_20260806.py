#!/usr/bin/env python3
"""Validate the metadata-only Stage 25 paper plan without writing SQLite."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
ENZYME_DB_ROOT = AI_ROOT.parents[1] / "酶数据库"
PLAN = ENZYME_DB_ROOT / "stage25_paper_metadata_only_plan_20260806.json"
OUTPUT = AI_ROOT / "reports" / "stage25_paper_metadata_only_plan_validation_20260806.json"


def load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def fail_if(condition: bool, failures: list[dict[str, Any]], check: str, observed: Any, expected: Any) -> None:
    if condition:
        failures.append({"check": check, "observed": observed, "expected": expected})


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate metadata-only paper plan")
    parser.add_argument("--plan", type=Path, default=PLAN)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    args = parser.parse_args()
    plan = load(args.plan)
    rows = plan.get("papers") if isinstance(plan.get("papers"), list) else []
    failures: list[dict[str, Any]] = []
    fail_if(not plan, failures, "plan_exists", str(args.plan), "JSON plan")
    fail_if(plan.get("mode") != "metadata-only-paper-intake-plan", failures, "mode", plan.get("mode"), "metadata-only-paper-intake-plan")
    fail_if(plan.get("plan_status") != "ready_for_metadata_review", failures, "plan_status", plan.get("plan_status"), "ready_for_metadata_review")
    fail_if(plan.get("plan_ready") is not True, failures, "plan_ready", plan.get("plan_ready"), True)
    fail_if(len(rows) != 4, failures, "paper_row_count", len(rows), 4)
    stable_ids = [str(row.get("stable_proposal_id")) for row in rows if isinstance(row, dict)]
    fail_if(len(set(stable_ids)) != 4, failures, "unique_stable_proposal_rows", len(set(stable_ids)), 4)
    fail_if(plan.get("planned_metadata_review_rows") != 4, failures, "planned_metadata_review_rows", plan.get("planned_metadata_review_rows"), 4)
    fail_if(plan.get("ready_for_metadata_review_rows") != 4, failures, "ready_for_metadata_review_rows", plan.get("ready_for_metadata_review_rows"), 4)
    new_identity_rows = plan.get("new_identity_review_rows")
    existing_identity_rows = plan.get("existing_identity_review_rows")
    conflicting_duplicate_rows = plan.get("conflicting_duplicate_rows")
    fail_if(type(new_identity_rows) is not int or new_identity_rows < 0, failures, "new_identity_review_rows_nonnegative_int", new_identity_rows, ">=0 int")
    fail_if(type(existing_identity_rows) is not int or existing_identity_rows < 0, failures, "existing_identity_review_rows_nonnegative_int", existing_identity_rows, ">=0 int")
    fail_if(conflicting_duplicate_rows != 0, failures, "conflicting_duplicate_rows_zero", conflicting_duplicate_rows, 0)
    if type(new_identity_rows) is int and type(existing_identity_rows) is int:
        fail_if(new_identity_rows + existing_identity_rows != len(rows), failures, "metadata_review_disposition_decomposition", [new_identity_rows, existing_identity_rows], len(rows))
    fail_if(plan.get("paper_insert_count") != 0, failures, "paper_insert_count_zero", plan.get("paper_insert_count"), 0)
    fail_if(plan.get("ready_for_sqlite_apply_rows") != 0, failures, "ready_for_sqlite_apply_rows_zero", plan.get("ready_for_sqlite_apply_rows"), 0)
    fail_if(plan.get("write_operation_count") != 0, failures, "write_operation_count_zero", plan.get("write_operation_count"), 0)
    fail_if(plan.get("failure_count") != 0 or plan.get("failures") != [], failures, "failures_empty", [plan.get("failure_count"), plan.get("failures")], [0, []])
    fail_if(plan.get("sqlite_write_sql") != [], failures, "sqlite_write_sql_empty", plan.get("sqlite_write_sql"), [])
    fail_if(plan.get("formal_decision_rows_written") != 0, failures, "formal_decision_rows_written_zero", plan.get("formal_decision_rows_written"), 0)
    for row in rows:
        key = row.get("stable_proposal_id")
        fail_if(not key, failures, "stable_proposal_id_present", row, "non-empty")
        fail_if(row.get("source_evidence_level") != "metadata_only", failures, f"{key}.source_evidence_level", row.get("source_evidence_level"), "metadata_only")
        fail_if(row.get("identity_closed") is not True, failures, f"{key}.identity_closed", row.get("identity_closed"), True)
        fail_if(row.get("metadata_plan_ready") is not True, failures, f"{key}.metadata_plan_ready", row.get("metadata_plan_ready"), True)
        disposition = row.get("duplicate_disposition")
        fail_if(disposition not in {"new_identity_not_found", "already_present_exact_identity"}, failures, f"{key}.duplicate_disposition", disposition, "new or exact existing identity")
        duplicate_rows = (row.get("duplicate_check") or {}).get("rows") or []
        if disposition == "new_identity_not_found":
            fail_if(duplicate_rows != [], failures, f"{key}.new_identity_duplicate_rows_empty", duplicate_rows, [])
            fail_if(row.get("existing_identity_exact") is not False, failures, f"{key}.new_identity_exact_false", row.get("existing_identity_exact"), False)
            fail_if(row.get("metadata_review_action") != "review_new_candidate", failures, f"{key}.new_identity_review_action", row.get("metadata_review_action"), "review_new_candidate")
        elif disposition == "already_present_exact_identity":
            fail_if(len(duplicate_rows) != 1, failures, f"{key}.existing_identity_duplicate_rows", len(duplicate_rows), 1)
            fail_if(row.get("existing_identity_exact") is not True, failures, f"{key}.existing_identity_exact_true", row.get("existing_identity_exact"), True)
            fail_if(row.get("metadata_review_action") != "review_existing_record", failures, f"{key}.existing_identity_review_action", row.get("metadata_review_action"), "review_existing_record")
        fail_if(row.get("variant_payload") is not None, failures, f"{key}.variant_payload_null", row.get("variant_payload"), None)
        fail_if(row.get("measurement_payload") is not None, failures, f"{key}.measurement_payload_null", row.get("measurement_payload"), None)
        fail_if(row.get("apply_allowed") is not False, failures, f"{key}.apply_allowed_false", row.get("apply_allowed"), False)
        mapping = row.get("target_mapping") or {}
        fail_if(mapping.get("target_table") != "papers", failures, f"{key}.target_table", mapping.get("target_table"), "papers")
        fail_if(len(mapping.get("columns") or []) != len(mapping.get("values") or []), failures, f"{key}.mapping_arity", [len(mapping.get("columns") or []), len(mapping.get("values") or [])], "equal")
    for field in ("apply_allowed", "apply_executed", "external_sqlite_mutated", "export_safe_released", "safe_for_model_claim", "release_ready"):
        fail_if(plan.get(field) is not False, failures, f"{field}_false", plan.get(field), False)
    validation = {
        "schema_version": 1,
        "stage": 25,
        "mode": "stage25_paper_metadata_only_plan_validation",
        "plan_valid": not failures,
        "plan_ready": plan.get("plan_ready") is True and not failures,
        "paper_rows": len(rows),
        "unique_stable_proposal_rows": len(set(stable_ids)),
        "planned_metadata_review_rows": plan.get("planned_metadata_review_rows"),
        "ready_for_metadata_review_rows": plan.get("ready_for_metadata_review_rows"),
        "new_identity_review_rows": new_identity_rows,
        "existing_identity_review_rows": existing_identity_rows,
        "conflicting_duplicate_rows": conflicting_duplicate_rows,
        "paper_insert_count": plan.get("paper_insert_count"),
        "ready_for_sqlite_apply_rows": plan.get("ready_for_sqlite_apply_rows"),
        "write_operation_count": plan.get("write_operation_count"),
        "variant_rows": 0,
        "measurement_rows": 0,
        "sqlite_write_sql_count": len(plan.get("sqlite_write_sql") or []),
        "failure_count": len(failures),
        "failures": failures,
        "apply_executed": False,
        "external_sqlite_mutated": False,
        "formal_decision_rows_written": 0,
        "safe_for_model_claim": False,
        "release_ready": False,
        "policy": "Metadata-only plan validator; metadata review readiness is not full-text, variant, measurement, benchmark, model, customer, or release readiness.",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(validation, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(args.output), "plan_valid": validation["plan_valid"], "plan_ready": validation["plan_ready"], "paper_rows": validation["paper_rows"], "failure_count": validation["failure_count"]}, ensure_ascii=False, sort_keys=True))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
