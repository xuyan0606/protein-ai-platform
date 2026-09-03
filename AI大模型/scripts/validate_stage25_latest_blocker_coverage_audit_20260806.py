#!/usr/bin/env python3
"""Validate latest Stage 25 blocker coverage audit."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
AUDIT = AI_ROOT / "reports" / "stage25_latest_blocker_coverage_audit_20260806.json"
OUTPUT = AI_ROOT / "reports" / "stage25_latest_blocker_coverage_audit_validation_20260806.json"


def load_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise SystemExit(f"{path} must contain a JSON object")
    return data


def fail_if(condition: bool, failures: list[dict[str, Any]], check: str, observed: Any, expected: Any) -> None:
    if condition:
        failures.append({"check": check, "observed": observed, "expected": expected})


def main() -> int:
    failures: list[dict[str, Any]] = []
    fail_if(not AUDIT.exists(), failures, "audit_exists", "missing", str(AUDIT))
    audit = load_json(AUDIT) if AUDIT.exists() else {}
    rows = audit.get("rows") if isinstance(audit.get("rows"), list) else []

    fail_if(audit.get("mode") != "stage25_latest_blocker_coverage_audit", failures, "mode", audit.get("mode"), "stage25_latest_blocker_coverage_audit")
    fail_if(audit.get("blocker_rows") != 5, failures, "blocker_rows", audit.get("blocker_rows"), 5)
    fail_if(len(rows) != 5, failures, "rows_len", len(rows), 5)
    for field in (
        "covered_by_current_receipt_rows",
        "covered_by_overall_index_rows",
        "covered_by_handoff_manifest_rows",
        "covered_by_operator_docs_rows",
        "covered_by_runner_or_rerun_rows",
    ):
        fail_if(audit.get(field) != 5, failures, field, audit.get(field), 5)
    fail_if(audit.get("uncovered_blockers") != [], failures, "uncovered_blockers_empty", audit.get("uncovered_blockers"), [])
    expected_overall_term_count = 0
    matched_overall_term_count = 0
    missing_overall_term_count = 0
    expected_runner_term_count = 0
    matched_runner_term_count = 0
    missing_runner_term_count = 0
    expected_doc_term_count = 0
    matched_doc_term_count = 0
    missing_doc_term_count = 0
    for index, row in enumerate(rows, start=1):
        prefix = f"rows[{index}]"
        fail_if(row.get("status") != "blocked", failures, f"{prefix}.status_blocked", row.get("status"), "blocked")
        fail_if(row.get("coverage_complete") is not True, failures, f"{prefix}.coverage_complete", row.get("coverage_complete"), True)
        fail_if(not row.get("closure_condition"), failures, f"{prefix}.closure_condition", row.get("closure_condition"), "non-empty")
        for field in ("overall", "runner", "doc"):
            expected = row.get(f"expected_{field}_terms")
            matched = row.get(f"matched_{field}_terms")
            missing = row.get(f"missing_{field}_terms")
            fail_if(not isinstance(expected, list) or not expected, failures, f"{prefix}.expected_{field}_terms", expected, "non-empty list")
            fail_if(matched != expected, failures, f"{prefix}.matched_{field}_terms", matched, expected)
            fail_if(missing != [], failures, f"{prefix}.missing_{field}_terms_empty", missing, [])
            if field == "overall":
                expected_overall_term_count += len(expected) if isinstance(expected, list) else 0
                matched_overall_term_count += len(matched) if isinstance(matched, list) else 0
                missing_overall_term_count += len(missing) if isinstance(missing, list) else 0
            elif field == "runner":
                expected_runner_term_count += len(expected) if isinstance(expected, list) else 0
                matched_runner_term_count += len(matched) if isinstance(matched, list) else 0
                missing_runner_term_count += len(missing) if isinstance(missing, list) else 0
            elif field == "doc":
                expected_doc_term_count += len(expected) if isinstance(expected, list) else 0
                matched_doc_term_count += len(matched) if isinstance(matched, list) else 0
                missing_doc_term_count += len(missing) if isinstance(missing, list) else 0
        for field in ("covered_by_current_receipt", "covered_by_overall_index", "covered_by_handoff_manifest", "covered_by_operator_docs", "covered_by_runner_or_rerun"):
            fail_if(row.get(field) is not True, failures, f"{prefix}.{field}", row.get(field), True)
    for flag in ("external_sqlite_mutated", "apply_executed", "export_safe_released", "safe_for_model_claim", "release_ready"):
        fail_if(audit.get(flag) is not False, failures, f"{flag}_false", audit.get(flag), False)
    fail_if(audit.get("formal_decision_rows_written") != 0, failures, "formal_decision_rows_written_zero", audit.get("formal_decision_rows_written"), 0)

    validation = {
        "schema_version": 1,
        "created_at": "2026-08-06",
        "mode": "stage25_latest_blocker_coverage_audit_validation",
        "stage": 25,
        "audit_valid": not failures,
        "failure_count": len(failures),
        "failures": failures,
        "blocker_rows": len(rows),
        "covered_by_current_receipt_rows": audit.get("covered_by_current_receipt_rows"),
        "covered_by_overall_index_rows": audit.get("covered_by_overall_index_rows"),
        "covered_by_handoff_manifest_rows": audit.get("covered_by_handoff_manifest_rows"),
        "covered_by_operator_docs_rows": audit.get("covered_by_operator_docs_rows"),
        "covered_by_runner_or_rerun_rows": audit.get("covered_by_runner_or_rerun_rows"),
        "expected_overall_term_count": expected_overall_term_count,
        "matched_overall_term_count": matched_overall_term_count,
        "missing_overall_term_count": missing_overall_term_count,
        "expected_runner_term_count": expected_runner_term_count,
        "matched_runner_term_count": matched_runner_term_count,
        "missing_runner_term_count": missing_runner_term_count,
        "expected_doc_term_count": expected_doc_term_count,
        "matched_doc_term_count": matched_doc_term_count,
        "missing_doc_term_count": missing_doc_term_count,
        "uncovered_blockers": audit.get("uncovered_blockers"),
        "external_sqlite_mutated": False,
        "formal_decision_rows_written": 0,
        "apply_executed": False,
        "export_safe_released": False,
        "safe_for_model_claim": False,
        "release_ready": False,
    }
    OUTPUT.write_text(json.dumps(validation, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "output": str(OUTPUT),
        "audit_valid": validation["audit_valid"],
        "failure_count": validation["failure_count"],
        "blocker_rows": validation["blocker_rows"],
    }, ensure_ascii=False, sort_keys=True))
    return 0 if validation["audit_valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
