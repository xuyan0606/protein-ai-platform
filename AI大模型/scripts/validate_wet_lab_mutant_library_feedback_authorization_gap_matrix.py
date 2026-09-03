#!/usr/bin/env python3
"""Validate wet-lab feedback authorization gap matrix fail-closed."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
WORKLIST = AI_ROOT / "datasets" / "feedback" / "wet_lab_mutant_library_feedback_authorization_worklist.jsonl"
DASHBOARD_VALIDATION = AI_ROOT / "reports" / "wet_lab_mutant_library_feedback_authorization_dashboard_validation_report.json"
AUTH_DECISIONS = AI_ROOT / "datasets" / "feedback" / "wet_lab_mutant_library_feedback_authorizations.jsonl"
AUTH_VALIDATION = AI_ROOT / "reports" / "wet_lab_mutant_library_feedback_authorization_validation_report.json"
GAP_MATRIX = AI_ROOT / "datasets" / "feedback" / "wet_lab_mutant_library_feedback_authorization_gap_matrix.jsonl"
STATUS = AI_ROOT / "datasets" / "feedback" / "wet_lab_mutant_library_feedback_authorization_gap_matrix_status.jsonl"
REPORT = AI_ROOT / "reports" / "wet_lab_mutant_library_feedback_authorization_gap_matrix_validation_report.json"

PRIORITY_ORDER = {
    "critical_tradeoff_review": 0,
    "medium_mixed_benefit_review": 1,
    "standard_multi_property_review": 2,
}

REQUIRED_REVIEW_FLAGS = [
    "source_trace_reviewed",
    "numbering_reviewed",
    "unit_condition_reviewed",
    "batch_control_reviewed",
    "replicate_policy_reviewed",
]


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def decision_by_candidate(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {
        str(row.get("feedback_candidate_id")): row
        for row in rows
        if row.get("feedback_candidate_id")
    }


def validation_by_candidate(report: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        str(row.get("feedback_candidate_id")): row
        for row in report.get("records") or []
        if isinstance(row, dict) and row.get("feedback_candidate_id")
    }


def row_sort_key(row: dict[str, Any]) -> tuple[int, str, str]:
    qc = row.get("qc_context") if isinstance(row.get("qc_context"), dict) else {}
    priority = str(qc.get("review_priority") or "")
    return (PRIORITY_ORDER.get(priority, 99), str(row.get("variant") or ""), str(row.get("metric_name") or ""))


def decision_gaps(decision: dict[str, Any] | None, validation: dict[str, Any]) -> list[str]:
    if decision is None:
        return [
            "missing_authorization_decision_row",
            "missing_authorization_decision",
            "missing_qc_decision",
            "missing_reviewer",
            "missing_reviewed_at",
            "missing_authorization_basis",
            *[f"missing_{flag}" for flag in REQUIRED_REVIEW_FLAGS],
        ]

    gaps: list[str] = []
    if decision.get("authorization_decision") not in {"approved_for_feedback_intake", "rejected", "needs_more_info"}:
        gaps.append("invalid_or_missing_authorization_decision")
    if decision.get("qc_decision") not in {"pass", "pass_with_conditions", "fail", "not_reviewed"}:
        gaps.append("invalid_or_missing_qc_decision")
    for flag in REQUIRED_REVIEW_FLAGS:
        if decision.get(flag) is not True:
            gaps.append(f"{flag}_not_true")
    for field in ["reviewer", "reviewed_at", "authorization_basis"]:
        if not decision.get(field):
            gaps.append(f"missing_{field}")
    if decision.get("allow_append_to_experiment_feedback_local") is True:
        gaps.append("direct_append_not_allowed_by_this_gate")
    gaps.extend(validation.get("errors") or [])
    return sorted(set(gaps))


def expected_gap_rows(
    worklist: list[dict[str, Any]],
    decisions: dict[str, dict[str, Any]],
    validation: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for index, work in enumerate(sorted(worklist, key=row_sort_key), start=1):
        cid = str(work.get("feedback_candidate_id") or "")
        qc_context = work.get("qc_context") if isinstance(work.get("qc_context"), dict) else {}
        decision = decisions.get(cid)
        validation_row = validation.get(cid, {})
        gaps = decision_gaps(decision, validation_row)
        rows.append({
            "authorization_gap_id": f"wetlab-mutlib-auth-gap-{cid.replace('wetlab-mutlib-', '')}",
            "execution_order": index,
            "feedback_candidate_id": cid,
            "authorization_worklist_id": work.get("authorization_worklist_id"),
            "authorization_template_id": work.get("authorization_template_id"),
            "source_project": work.get("source_project"),
            "variant": work.get("variant"),
            "metric_name": work.get("metric_name"),
            "metric_class": work.get("metric_class"),
            "outcome_candidate": work.get("outcome_candidate"),
            "vs_control_ratio": work.get("vs_control_ratio"),
            "review_priority": str(qc_context.get("review_priority") or ""),
            "conflicting_property_signal": bool(qc_context.get("conflicting_property_signal")),
            "source_file": work.get("source_file"),
            "source_row_index": work.get("source_row_index"),
            "authorization_decision_present": decision is not None,
            "authorization_valid": bool(validation_row.get("valid")),
            "authorized_for_feedback_intake": bool(validation_row.get("authorized_for_feedback_intake")),
            "gap_status": "blocked_missing_human_authorization" if gaps else "authorization_review_present_but_still_fail_closed",
            "gap_count": len(gaps),
            "missing_or_invalid_items": gaps,
        })
    return rows


def validate_gap_row(row: dict[str, Any], expected: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    for field, expected_value in expected.items():
        if row.get(field) != expected_value:
            errors.append(f"{field}_mismatch")

    if row.get("decision_input") != "datasets/feedback/wet_lab_mutant_library_feedback_authorizations.jsonl":
        errors.append("decision_input_mismatch")
    if row.get("template_input") != "datasets/feedback/wet_lab_mutant_library_feedback_authorizations.template.jsonl":
        errors.append("template_input_mismatch")
    if row.get("validator_command") != "python3 scripts/validate_wet_lab_mutant_library_feedback_authorizations.py":
        errors.append("validator_command_mismatch")
    if row.get("downstream_preflight_command") != "python3 scripts/build_wet_lab_mutant_library_feedback_preflight.py":
        errors.append("downstream_preflight_command_mismatch")
    if row.get("requires_human_input") is not True:
        errors.append("requires_human_input_not_true")
    if row.get("completion_ready") is not False:
        errors.append("completion_ready_not_false")

    policy = str(row.get("policy") or "").lower()
    for phrase in ["not an authorization", "not feedback preflight", "not a training label"]:
        if phrase not in policy:
            errors.append("policy_missing_fail_closed_language")
            break
    condition = str(row.get("completion_condition") or "").lower()
    if "valid human authorization row" not in condition or "never sufficient by itself" not in condition:
        errors.append("completion_condition_missing_fail_closed_language")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate wet-lab feedback authorization gap matrix")
    parser.add_argument("--worklist", type=Path, default=WORKLIST)
    parser.add_argument("--dashboard-validation", type=Path, default=DASHBOARD_VALIDATION)
    parser.add_argument("--authorization-decisions", type=Path, default=AUTH_DECISIONS)
    parser.add_argument("--authorization-validation", type=Path, default=AUTH_VALIDATION)
    parser.add_argument("--gap-matrix", type=Path, default=GAP_MATRIX)
    parser.add_argument("--status", type=Path, default=STATUS)
    parser.add_argument("--report", type=Path, default=REPORT)
    args = parser.parse_args()

    worklist = load_jsonl(args.worklist)
    decisions = decision_by_candidate(load_jsonl(args.authorization_decisions))
    validation = validation_by_candidate(load_json(args.authorization_validation))
    dashboard_validation = load_json(args.dashboard_validation)
    gap_matrix = load_jsonl(args.gap_matrix)

    expected_rows = expected_gap_rows(worklist, decisions, validation)
    expected_by_id = {row["feedback_candidate_id"]: row for row in expected_rows}
    seen_ids: set[str] = set()
    duplicate_ids: set[str] = set()
    status_rows: list[dict[str, Any]] = []
    errors = Counter()

    for row in gap_matrix:
        cid = str(row.get("feedback_candidate_id") or "")
        if cid in seen_ids:
            duplicate_ids.add(cid)
        seen_ids.add(cid)
        expected = expected_by_id.get(cid)
        row_errors = ["unexpected_feedback_candidate_id"] if expected is None else validate_gap_row(row, expected)
        errors.update(row_errors)
        status_rows.append({
            "authorization_gap_id": row.get("authorization_gap_id"),
            "feedback_candidate_id": cid,
            "variant": row.get("variant"),
            "metric_name": row.get("metric_name"),
            "review_priority": row.get("review_priority"),
            "gap_status": row.get("gap_status"),
            "gap_count": row.get("gap_count"),
            "valid": not row_errors,
            "completion_ready": False,
            "requires_human_input": True,
            "errors": row_errors,
            "policy": "Validated gap row only; not authorization, not feedback preflight, and not model claim readiness.",
        })

    missing_ids = sorted(set(expected_by_id) - seen_ids)
    unexpected_ids = sorted(seen_ids - set(expected_by_id))
    if missing_ids:
        errors.update({"missing_gap_row": len(missing_ids)})
    if unexpected_ids:
        errors.update({"unexpected_gap_row": len(unexpected_ids)})
    if duplicate_ids:
        errors.update({"duplicate_gap_row": len(duplicate_ids)})
        for status in status_rows:
            if status["feedback_candidate_id"] in duplicate_ids:
                status["valid"] = False
                status["errors"].append("duplicate_gap_row")

    if dashboard_validation.get("all_dashboard_rows_valid") is not True:
        errors.update({"dashboard_validation_not_ready": 1})

    valid_rows = sum(1 for row in status_rows if row["valid"])
    authorized_rows = sum(1 for row in gap_matrix if row.get("authorized_for_feedback_intake") is True)
    priority_counts = Counter(str(row.get("review_priority") or "") for row in gap_matrix)
    gap_status_counts = Counter(str(row.get("gap_status") or "") for row in gap_matrix)
    all_valid = not errors and valid_rows == len(gap_matrix) and len(gap_matrix) == len(expected_rows)

    write_jsonl(args.status, status_rows)
    report = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "local_only": True,
        "authorization_gap_rows": len(gap_matrix),
        "expected_authorization_gap_rows": len(expected_rows),
        "valid_gap_rows": valid_rows,
        "invalid_gap_rows": len(status_rows) - valid_rows,
        "missing_gap_rows": len(missing_ids),
        "unexpected_gap_rows": len(unexpected_ids),
        "duplicate_gap_rows": len(duplicate_ids),
        "dashboard_all_rows_valid": bool(dashboard_validation.get("all_dashboard_rows_valid")),
        "authorized_rows": authorized_rows,
        "blocked_missing_human_authorization_rows": gap_status_counts.get("blocked_missing_human_authorization", 0),
        "critical_tradeoff_gap_rows": priority_counts.get("critical_tradeoff_review", 0),
        "completion_ready_rows": 0,
        "requires_human_input_rows": len(status_rows),
        "ready_for_feedback_intake_rows": 0,
        "claim_eligible_rows_now": 0,
        "safe_for_model_claim": False,
        "all_gap_rows_valid": all_valid,
        "priority_counts": dict(sorted(priority_counts.items())),
        "gap_status_counts": dict(sorted(gap_status_counts.items())),
        "error_counts": dict(errors),
        "status_output": str(args.status),
        "policy": "Gap matrix validation proves missing-review accounting only; it never authorizes rows, runs preflight, appends labels, or enables model claims.",
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({
        "authorization_gap_rows": report["authorization_gap_rows"],
        "valid_gap_rows": report["valid_gap_rows"],
        "invalid_gap_rows": report["invalid_gap_rows"],
        "all_gap_rows_valid": report["all_gap_rows_valid"],
        "output": str(args.report),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
