#!/usr/bin/env python3
"""Validate QC-aware wet-lab feedback authorization worklist fail-closed."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
CANDIDATES = AI_ROOT / "datasets" / "feedback" / "wet_lab_mutant_library_feedback_candidates.jsonl"
QC_MATRIX = AI_ROOT / "datasets" / "feedback" / "wet_lab_mutant_library_feedback_qc_matrix.jsonl"
AUTH_TEMPLATE = AI_ROOT / "datasets" / "feedback" / "wet_lab_mutant_library_feedback_authorizations.template.jsonl"
AUTH_REPORT = AI_ROOT / "reports" / "wet_lab_mutant_library_feedback_authorization_validation_report.json"
WORKLIST = AI_ROOT / "datasets" / "feedback" / "wet_lab_mutant_library_feedback_authorization_worklist.jsonl"
STATUS = AI_ROOT / "datasets" / "feedback" / "wet_lab_mutant_library_feedback_authorization_worklist_status.jsonl"
REPORT = AI_ROOT / "reports" / "wet_lab_mutant_library_feedback_authorization_worklist_validation_report.json"


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def qc_by_candidate(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for qc_row in rows:
        for metric in qc_row.get("metric_rows") or []:
            cid = str(metric.get("feedback_candidate_id") or "")
            if not cid:
                continue
            result[cid] = {
                "qc_matrix_id": qc_row.get("qc_matrix_id"),
                "property_call": qc_row.get("property_call"),
                "review_priority": qc_row.get("review_priority"),
                "conflicting_property_signal": bool(qc_row.get("conflicting_property_signal")),
                "variant_outcome_counts": qc_row.get("outcome_counts"),
                "variant_metric_classes": qc_row.get("metric_classes"),
                "variant_ratio_min": qc_row.get("ratio_min"),
                "variant_ratio_max": qc_row.get("ratio_max"),
                "variant_ratio_range": qc_row.get("ratio_range"),
                "metric_class": metric.get("metric_class"),
            }
    return result


def validation_records_by_candidate(report: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        str(row.get("feedback_candidate_id")): row
        for row in report.get("records") or []
        if isinstance(row, dict) and row.get("feedback_candidate_id")
    }


def numeric(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def validate_row(
    row: dict[str, Any],
    candidates_by_id: dict[str, dict[str, Any]],
    template_by_id: dict[str, dict[str, Any]],
    qc_lookup: dict[str, dict[str, Any]],
    auth_validation_by_id: dict[str, dict[str, Any]],
) -> list[str]:
    errors: list[str] = []
    required = [
        "authorization_worklist_id",
        "feedback_candidate_id",
        "authorization_template_id",
        "source_project",
        "variant",
        "mutation_set",
        "metric_name",
        "metric_class",
        "assay_type",
        "raw_value_numeric",
        "control_value_numeric",
        "vs_control_ratio",
        "outcome_candidate",
        "confidence_tier",
        "batch_id",
        "sample_id",
        "source_file",
        "source_row_index",
        "qc_context",
        "authorization_decision_present",
        "authorization_valid",
        "authorized_for_feedback_intake",
        "worklist_status",
        "required_human_actions",
        "ready_for_feedback_intake",
        "claim_eligible_now",
        "policy",
    ]
    for field in required:
        if field not in row:
            errors.append(f"missing_{field}")

    cid = str(row.get("feedback_candidate_id") or "")
    candidate = candidates_by_id.get(cid)
    if not candidate:
        errors.append("feedback_candidate_id_not_found")
        candidate = {}
    else:
        if candidate.get("numeric_training_candidate") is not True:
            errors.append("candidate_not_numeric_training_candidate")
        for field in [
            "source_project",
            "variant",
            "metric_name",
            "assay_type",
            "outcome_candidate",
            "confidence_tier",
            "batch_id",
            "sample_id",
            "source_file",
            "source_row_index",
        ]:
            if row.get(field) != candidate.get(field):
                errors.append(f"candidate_{field}_mismatch")
        if row.get("mutation_set") != candidate.get("mutation_set"):
            errors.append("candidate_mutation_set_mismatch")
        for field in ["raw_value_numeric", "control_value_numeric", "vs_control_ratio"]:
            if not numeric(row.get(field)) or row.get(field) != candidate.get(field):
                errors.append(f"candidate_{field}_mismatch")

    expected_worklist_id = f"wetlab-mutlib-auth-worklist-{cid.replace('wetlab-mutlib-', '')}" if cid else ""
    if row.get("authorization_worklist_id") != expected_worklist_id:
        errors.append("invalid_authorization_worklist_id")

    template = template_by_id.get(cid)
    if not template:
        errors.append("authorization_template_row_missing")
    elif row.get("authorization_template_id") != template.get("authorization_id"):
        errors.append("authorization_template_id_mismatch")

    qc_expected = qc_lookup.get(cid)
    qc_context = row.get("qc_context")
    if not isinstance(qc_context, dict):
        errors.append("invalid_qc_context")
        qc_context = {}
    if not qc_expected:
        errors.append("qc_context_missing_for_candidate")
    else:
        for field in [
            "qc_matrix_id",
            "property_call",
            "review_priority",
            "conflicting_property_signal",
            "variant_outcome_counts",
            "variant_metric_classes",
            "variant_ratio_min",
            "variant_ratio_max",
            "variant_ratio_range",
        ]:
            if qc_context.get(field) != qc_expected.get(field):
                errors.append(f"qc_context_{field}_mismatch")
        if row.get("metric_class") != qc_expected.get("metric_class"):
            errors.append("metric_class_mismatch")

    validation = auth_validation_by_id.get(cid, {})
    authorized = bool(validation.get("authorized_for_feedback_intake"))
    valid_auth = bool(validation.get("valid"))
    decision_present = bool(validation)
    if row.get("authorization_decision_present") is not decision_present:
        errors.append("authorization_decision_present_mismatch")
    if row.get("authorization_valid") is not valid_auth:
        errors.append("authorization_valid_mismatch")
    if row.get("authorized_for_feedback_intake") is not authorized:
        errors.append("authorized_for_feedback_intake_mismatch")

    expected_status = "authorized_ready_for_preflight" if authorized else "blocked_waiting_for_authorization"
    if decision_present and not authorized:
        expected_status = "decision_present_but_not_authorized"
    if row.get("worklist_status") != expected_status:
        errors.append("worklist_status_mismatch")

    actions = row.get("required_human_actions")
    if not isinstance(actions, list) or len(actions) < 4:
        errors.append("required_human_actions_incomplete")
    else:
        action_text = " ".join(str(action).lower() for action in actions)
        for phrase in [
            "wet_lab_mutant_library_feedback_authorizations.jsonl",
            "review source trace",
            "authorize/reject this metric row independently",
            "validate_wet_lab_mutant_library_feedback_authorizations.py",
        ]:
            if phrase.lower() not in action_text:
                errors.append("required_human_actions_missing_expected_step")
                break

    if row.get("ready_for_feedback_intake") is not False:
        errors.append("worklist_must_not_set_ready_for_feedback_intake")
    if row.get("claim_eligible_now") is not False:
        errors.append("worklist_must_not_set_claim_eligible_now")
    policy = str(row.get("policy") or "").lower()
    for phrase in ["not an authorization", "not preflight", "not a training label"]:
        if phrase not in policy:
            errors.append("policy_missing_fail_closed_language")
            break
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate wet-lab feedback authorization worklist")
    parser.add_argument("--candidates", type=Path, default=CANDIDATES)
    parser.add_argument("--qc-matrix", type=Path, default=QC_MATRIX)
    parser.add_argument("--authorization-template", type=Path, default=AUTH_TEMPLATE)
    parser.add_argument("--authorization-report", type=Path, default=AUTH_REPORT)
    parser.add_argument("--worklist", type=Path, default=WORKLIST)
    parser.add_argument("--status", type=Path, default=STATUS)
    parser.add_argument("--report", type=Path, default=REPORT)
    args = parser.parse_args()

    candidates = load_jsonl(args.candidates)
    numeric_candidates = [row for row in candidates if row.get("numeric_training_candidate") is True]
    numeric_candidate_ids = {str(row.get("feedback_candidate_id")) for row in numeric_candidates}
    candidates_by_id = {str(row.get("feedback_candidate_id")): row for row in candidates if row.get("feedback_candidate_id")}
    template_by_id = {
        str(row.get("feedback_candidate_id")): row
        for row in load_jsonl(args.authorization_template)
        if row.get("feedback_candidate_id")
    }
    qc_lookup = qc_by_candidate(load_jsonl(args.qc_matrix))
    auth_validation_by_id = validation_records_by_candidate(load_json(args.authorization_report))
    worklist = load_jsonl(args.worklist)

    errors = Counter()
    seen_ids: set[str] = set()
    duplicate_ids: set[str] = set()
    status_rows: list[dict[str, Any]] = []
    for row in worklist:
        cid = str(row.get("feedback_candidate_id") or "")
        if cid in seen_ids:
            duplicate_ids.add(cid)
        seen_ids.add(cid)
        row_errors = validate_row(row, candidates_by_id, template_by_id, qc_lookup, auth_validation_by_id)
        errors.update(row_errors)
        status_rows.append({
            "authorization_worklist_id": row.get("authorization_worklist_id"),
            "feedback_candidate_id": cid,
            "source_project": row.get("source_project"),
            "variant": row.get("variant"),
            "metric_name": row.get("metric_name"),
            "review_priority": (row.get("qc_context") or {}).get("review_priority") if isinstance(row.get("qc_context"), dict) else None,
            "worklist_status": row.get("worklist_status"),
            "valid": not row_errors,
            "completion_ready": False,
            "requires_human_input": True,
            "errors": row_errors,
            "policy": "Validated worklist row only; not authorization, not feedback intake, and not model claim readiness.",
        })

    if duplicate_ids:
        errors.update({"duplicate_feedback_candidate_id": len(duplicate_ids)})
        for status in status_rows:
            if status["feedback_candidate_id"] in duplicate_ids:
                status["valid"] = False
                status["errors"].append("duplicate_feedback_candidate_id")

    missing_ids = sorted(numeric_candidate_ids - seen_ids)
    unexpected_ids = sorted(seen_ids - numeric_candidate_ids)
    if missing_ids:
        errors.update({"missing_numeric_candidate_worklist_row": len(missing_ids)})
    if unexpected_ids:
        errors.update({"unexpected_worklist_candidate_id": len(unexpected_ids)})

    valid_rows = sum(1 for row in status_rows if row["valid"])
    authorized_rows = sum(1 for row in worklist if row.get("authorized_for_feedback_intake") is True)
    status_counts = Counter(str(row.get("worklist_status")) for row in worklist)
    priority_counts = Counter(
        str((row.get("qc_context") or {}).get("review_priority"))
        for row in worklist
        if isinstance(row.get("qc_context"), dict)
    )
    critical_rows = [
        row for row in worklist
        if isinstance(row.get("qc_context"), dict)
        and row["qc_context"].get("review_priority") == "critical_tradeoff_review"
    ]

    write_jsonl(args.status, status_rows)
    report = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "local_only": True,
        "candidate_rows": len(candidates),
        "numeric_training_candidate_rows": len(numeric_candidates),
        "authorization_worklist_rows": len(worklist),
        "valid_worklist_rows": valid_rows,
        "invalid_worklist_rows": len(status_rows) - valid_rows,
        "missing_numeric_candidate_worklist_rows": len(missing_ids),
        "unexpected_worklist_candidate_rows": len(unexpected_ids),
        "duplicate_feedback_candidate_rows": len(duplicate_ids),
        "authorized_rows": authorized_rows,
        "blocked_waiting_for_authorization_rows": status_counts.get("blocked_waiting_for_authorization", 0),
        "critical_tradeoff_worklist_rows": len(critical_rows),
        "ready_for_feedback_intake_rows": 0,
        "completion_ready_rows": 0,
        "requires_human_input_rows": len(status_rows),
        "claim_eligible_rows_now": 0,
        "safe_for_model_claim": False,
        "all_numeric_candidates_covered": not missing_ids and not unexpected_ids and not duplicate_ids,
        "all_worklist_rows_valid": valid_rows == len(status_rows) and not missing_ids and not unexpected_ids and not duplicate_ids,
        "priority_counts": dict(sorted(priority_counts.items())),
        "status_counts": dict(sorted(status_counts.items())),
        "error_counts": dict(errors),
        "missing_feedback_candidate_ids": missing_ids[:100],
        "unexpected_feedback_candidate_ids": unexpected_ids[:100],
        "status_output": str(args.status),
        "policy": "Validation proves worklist consistency only; it never authorizes rows, runs preflight, appends labels, or enables model claims.",
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({
        "authorization_worklist_rows": report["authorization_worklist_rows"],
        "valid_worklist_rows": report["valid_worklist_rows"],
        "invalid_worklist_rows": report["invalid_worklist_rows"],
        "all_numeric_candidates_covered": report["all_numeric_candidates_covered"],
        "output": str(args.report),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
