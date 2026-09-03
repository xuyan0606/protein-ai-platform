#!/usr/bin/env python3
"""Validate wet-lab feedback authorization operator checklist fail-closed."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
GAP_MATRIX = AI_ROOT / "datasets" / "feedback" / "wet_lab_mutant_library_feedback_authorization_gap_matrix.jsonl"
GAP_VALIDATION = AI_ROOT / "reports" / "wet_lab_mutant_library_feedback_authorization_gap_matrix_validation_report.json"
CHECKLIST = AI_ROOT / "datasets" / "feedback" / "wet_lab_mutant_library_feedback_authorization_operator_checklist.jsonl"
STATUS = AI_ROOT / "datasets" / "feedback" / "wet_lab_mutant_library_feedback_authorization_operator_checklist_status.jsonl"
REPORT = AI_ROOT / "reports" / "wet_lab_mutant_library_feedback_authorization_operator_checklist_validation_report.json"

REQUIRED_REVIEW_FIELDS = [
    "authorization_decision",
    "qc_decision",
    "source_trace_reviewed",
    "numbering_reviewed",
    "unit_condition_reviewed",
    "batch_control_reviewed",
    "replicate_policy_reviewed",
    "reviewer",
    "reviewed_at",
    "authorization_basis",
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


def review_mode(row: dict[str, Any]) -> str:
    priority = str(row.get("review_priority") or "")
    outcome = str(row.get("outcome_candidate") or "")
    if priority == "critical_tradeoff_review":
        return "tradeoff_review_required"
    if outcome == "go":
        return "positive_candidate_review_required"
    if outcome == "no_go":
        return "negative_candidate_review_required"
    return "watch_candidate_review_required"


def validate_row(row: dict[str, Any], gap: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    expected_id = f"wetlab-mutlib-auth-checklist-{str(gap.get('feedback_candidate_id') or '').replace('wetlab-mutlib-', '')}"
    expected_fields = {
        "operator_checklist_id": expected_id,
        "execution_order": gap.get("execution_order"),
        "feedback_candidate_id": gap.get("feedback_candidate_id"),
        "authorization_gap_id": gap.get("authorization_gap_id"),
        "authorization_template_id": gap.get("authorization_template_id"),
        "source_project": gap.get("source_project"),
        "variant": gap.get("variant"),
        "metric_name": gap.get("metric_name"),
        "metric_class": gap.get("metric_class"),
        "outcome_candidate": gap.get("outcome_candidate"),
        "vs_control_ratio": gap.get("vs_control_ratio"),
        "review_priority": gap.get("review_priority"),
        "review_mode": review_mode(gap),
        "conflicting_property_signal": bool(gap.get("conflicting_property_signal")),
        "source_file": gap.get("source_file"),
        "source_row_index": gap.get("source_row_index"),
        "open_first": gap.get("template_input"),
        "write_reviewed_decision_to": gap.get("decision_input"),
        "missing_or_invalid_items": gap.get("missing_or_invalid_items") or [],
        "validator_command": gap.get("validator_command"),
        "downstream_preflight_command": gap.get("downstream_preflight_command"),
        "safe_pipeline_command": "python3 scripts/run_safe_training_pipeline.py",
        "checklist_status": "open_blocked_waiting_for_human_review",
        "requires_human_input": True,
        "completion_ready": False,
    }
    for field, expected in expected_fields.items():
        if row.get(field) != expected:
            errors.append(f"{field}_mismatch")

    if row.get("required_review_fields") != REQUIRED_REVIEW_FIELDS:
        errors.append("required_review_fields_mismatch")
    summary = str(row.get("next_action_summary") or "")
    if review_mode(gap) == "tradeoff_review_required" and "together with the other properties" not in summary:
        errors.append("tradeoff_next_action_summary_missing_context")
    if review_mode(gap) == "positive_candidate_review_required" and "Verify source trace" not in summary:
        errors.append("positive_next_action_summary_missing_review_steps")
    if review_mode(gap) == "watch_candidate_review_required" and "watch signal" not in summary:
        errors.append("watch_next_action_summary_missing_context")
    if review_mode(gap) == "negative_candidate_review_required" and "negative signal" not in summary:
        errors.append("negative_next_action_summary_missing_context")

    condition = str(row.get("completion_condition") or "").lower()
    if "reviewed authorization row validates" not in condition or "checklist alone is never sufficient" not in condition:
        errors.append("completion_condition_missing_fail_closed_language")
    policy = str(row.get("policy") or "").lower()
    for phrase in ["not an authorization", "not feedback preflight", "not a training label"]:
        if phrase not in policy:
            errors.append("policy_missing_fail_closed_language")
            break
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate wet-lab feedback authorization operator checklist")
    parser.add_argument("--gap-matrix", type=Path, default=GAP_MATRIX)
    parser.add_argument("--gap-validation", type=Path, default=GAP_VALIDATION)
    parser.add_argument("--checklist", type=Path, default=CHECKLIST)
    parser.add_argument("--status", type=Path, default=STATUS)
    parser.add_argument("--report", type=Path, default=REPORT)
    args = parser.parse_args()

    gaps = load_jsonl(args.gap_matrix)
    gap_validation = load_json(args.gap_validation)
    checklist = load_jsonl(args.checklist)
    gaps_by_id = {str(row.get("feedback_candidate_id")): row for row in gaps}

    seen_ids: set[str] = set()
    duplicate_ids: set[str] = set()
    status_rows: list[dict[str, Any]] = []
    errors = Counter()

    for row in checklist:
        cid = str(row.get("feedback_candidate_id") or "")
        if cid in seen_ids:
            duplicate_ids.add(cid)
        seen_ids.add(cid)
        gap = gaps_by_id.get(cid)
        row_errors = ["unexpected_feedback_candidate_id"] if gap is None else validate_row(row, gap)
        errors.update(row_errors)
        status_rows.append({
            "operator_checklist_id": row.get("operator_checklist_id"),
            "feedback_candidate_id": cid,
            "authorization_gap_id": row.get("authorization_gap_id"),
            "variant": row.get("variant"),
            "metric_name": row.get("metric_name"),
            "review_mode": row.get("review_mode"),
            "checklist_status": row.get("checklist_status"),
            "valid": not row_errors,
            "completion_ready": False,
            "requires_human_input": True,
            "errors": row_errors,
            "policy": "Validated checklist row only; not authorization, not feedback preflight, and not model claim readiness.",
        })

    missing_ids = sorted(set(gaps_by_id) - seen_ids)
    unexpected_ids = sorted(seen_ids - set(gaps_by_id))
    if missing_ids:
        errors.update({"missing_checklist_row": len(missing_ids)})
    if unexpected_ids:
        errors.update({"unexpected_checklist_row": len(unexpected_ids)})
    if duplicate_ids:
        errors.update({"duplicate_checklist_row": len(duplicate_ids)})
        for status in status_rows:
            if status["feedback_candidate_id"] in duplicate_ids:
                status["valid"] = False
                status["errors"].append("duplicate_checklist_row")
    if gap_validation.get("all_gap_rows_valid") is not True:
        errors.update({"gap_validation_not_ready": 1})

    valid_rows = sum(1 for row in status_rows if row["valid"])
    status_counts = Counter(str(row.get("checklist_status") or "") for row in checklist)
    mode_counts = Counter(str(row.get("review_mode") or "") for row in checklist)
    all_valid = not errors and valid_rows == len(checklist) and len(checklist) == len(gaps)

    write_jsonl(args.status, status_rows)
    report = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "local_only": True,
        "operator_checklist_rows": len(checklist),
        "expected_operator_checklist_rows": len(gaps),
        "valid_checklist_rows": valid_rows,
        "invalid_checklist_rows": len(status_rows) - valid_rows,
        "missing_checklist_rows": len(missing_ids),
        "unexpected_checklist_rows": len(unexpected_ids),
        "duplicate_checklist_rows": len(duplicate_ids),
        "gap_validation_all_rows_valid": bool(gap_validation.get("all_gap_rows_valid")),
        "open_blocked_checklist_rows": status_counts.get("open_blocked_waiting_for_human_review", 0),
        "tradeoff_review_required_rows": mode_counts.get("tradeoff_review_required", 0),
        "positive_candidate_review_required_rows": mode_counts.get("positive_candidate_review_required", 0),
        "watch_candidate_review_required_rows": mode_counts.get("watch_candidate_review_required", 0),
        "negative_candidate_review_required_rows": mode_counts.get("negative_candidate_review_required", 0),
        "completion_ready_rows": 0,
        "requires_human_input_rows": len(status_rows),
        "authorized_rows": 0,
        "ready_for_feedback_intake_rows": 0,
        "claim_eligible_rows_now": 0,
        "safe_for_model_claim": False,
        "all_checklist_rows_valid": all_valid,
        "mode_counts": dict(sorted(mode_counts.items())),
        "status_counts": dict(sorted(status_counts.items())),
        "error_counts": dict(errors),
        "status_output": str(args.status),
        "policy": "Checklist validation proves operator guidance consistency only; it never authorizes rows, runs preflight, appends labels, or enables model claims.",
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({
        "operator_checklist_rows": report["operator_checklist_rows"],
        "valid_checklist_rows": report["valid_checklist_rows"],
        "invalid_checklist_rows": report["invalid_checklist_rows"],
        "all_checklist_rows_valid": report["all_checklist_rows_valid"],
        "output": str(args.report),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
