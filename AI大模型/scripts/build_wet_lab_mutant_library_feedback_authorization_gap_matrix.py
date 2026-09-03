#!/usr/bin/env python3
"""Build human authorization gap matrix for wet-lab feedback candidates."""

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
OUTPUT = AI_ROOT / "datasets" / "feedback" / "wet_lab_mutant_library_feedback_authorization_gap_matrix.jsonl"
REPORT = AI_ROOT / "reports" / "wet_lab_mutant_library_feedback_authorization_gap_matrix_report.json"

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


def main() -> int:
    parser = argparse.ArgumentParser(description="Build wet-lab feedback authorization gap matrix")
    parser.add_argument("--worklist", type=Path, default=WORKLIST)
    parser.add_argument("--dashboard-validation", type=Path, default=DASHBOARD_VALIDATION)
    parser.add_argument("--authorization-decisions", type=Path, default=AUTH_DECISIONS)
    parser.add_argument("--authorization-validation", type=Path, default=AUTH_VALIDATION)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    parser.add_argument("--report", type=Path, default=REPORT)
    args = parser.parse_args()

    worklist = sorted(load_jsonl(args.worklist), key=row_sort_key)
    decisions = decision_by_candidate(load_jsonl(args.authorization_decisions))
    validation = validation_by_candidate(load_json(args.authorization_validation))
    dashboard_validation = load_json(args.dashboard_validation)

    rows: list[dict[str, Any]] = []
    for index, work in enumerate(worklist, start=1):
        cid = str(work.get("feedback_candidate_id") or "")
        qc_context = work.get("qc_context") if isinstance(work.get("qc_context"), dict) else {}
        decision = decisions.get(cid)
        validation_row = validation.get(cid, {})
        gaps = decision_gaps(decision, validation_row)
        priority = str(qc_context.get("review_priority") or "")
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
            "review_priority": priority,
            "conflicting_property_signal": bool(qc_context.get("conflicting_property_signal")),
            "source_file": work.get("source_file"),
            "source_row_index": work.get("source_row_index"),
            "authorization_decision_present": decision is not None,
            "authorization_valid": bool(validation_row.get("valid")),
            "authorized_for_feedback_intake": bool(validation_row.get("authorized_for_feedback_intake")),
            "gap_status": "blocked_missing_human_authorization" if gaps else "authorization_review_present_but_still_fail_closed",
            "gap_count": len(gaps),
            "missing_or_invalid_items": gaps,
            "decision_input": "datasets/feedback/wet_lab_mutant_library_feedback_authorizations.jsonl",
            "template_input": "datasets/feedback/wet_lab_mutant_library_feedback_authorizations.template.jsonl",
            "validator_command": "python3 scripts/validate_wet_lab_mutant_library_feedback_authorizations.py",
            "downstream_preflight_command": "python3 scripts/build_wet_lab_mutant_library_feedback_preflight.py",
            "completion_condition": "valid human authorization row plus downstream preflight; this gap row is never sufficient by itself",
            "requires_human_input": True,
            "completion_ready": False,
            "policy": "Gap matrix only; not an authorization, not feedback preflight, and not a training label.",
        })

    gap_counts = Counter(row["gap_status"] for row in rows)
    priority_counts = Counter(row["review_priority"] for row in rows)
    variant_counts = Counter(str(row["variant"]) for row in rows)
    write_jsonl(args.output, rows)
    report = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "local_only": True,
        "authorization_gap_rows": len(rows),
        "authorization_worklist_rows": len(worklist),
        "dashboard_all_rows_valid": bool(dashboard_validation.get("all_dashboard_rows_valid")),
        "decision_present_rows": sum(1 for row in rows if row["authorization_decision_present"]),
        "authorized_rows": sum(1 for row in rows if row["authorized_for_feedback_intake"]),
        "blocked_missing_human_authorization_rows": gap_counts.get("blocked_missing_human_authorization", 0),
        "critical_tradeoff_gap_rows": priority_counts.get("critical_tradeoff_review", 0),
        "completion_ready_rows": 0,
        "requires_human_input_rows": len(rows),
        "ready_for_feedback_intake_rows": 0,
        "claim_eligible_rows_now": 0,
        "safe_for_model_claim": False,
        "priority_counts": dict(sorted(priority_counts.items())),
        "variant_counts": dict(sorted(variant_counts.items())),
        "gap_status_counts": dict(sorted(gap_counts.items())),
        "output": str(args.output),
        "policy": "Authorization gap matrix makes missing human review explicit; it never grants authorization, writes preflight, appends labels, or enables model claims.",
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({
        "authorization_gap_rows": report["authorization_gap_rows"],
        "authorized_rows": report["authorized_rows"],
        "blocked_missing_human_authorization_rows": report["blocked_missing_human_authorization_rows"],
        "output": str(args.report),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
