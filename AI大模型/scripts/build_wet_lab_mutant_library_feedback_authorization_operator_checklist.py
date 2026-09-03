#!/usr/bin/env python3
"""Build operator checklist for wet-lab feedback authorization gaps."""

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
OUTPUT = AI_ROOT / "datasets" / "feedback" / "wet_lab_mutant_library_feedback_authorization_operator_checklist.jsonl"
REPORT = AI_ROOT / "reports" / "wet_lab_mutant_library_feedback_authorization_operator_checklist_report.json"


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


def next_action_summary(row: dict[str, Any]) -> str:
    mode = review_mode(row)
    if mode == "tradeoff_review_required":
        return "Review this metric together with the other properties of the same variant before any metric-level decision."
    if mode == "positive_candidate_review_required":
        return "Verify source trace, numbering, unit/condition, batch/control, replicate/QC, then decide whether this metric can be approved."
    if mode == "negative_candidate_review_required":
        return "Verify the negative signal and decide whether to reject or retain as reviewed no-go evidence."
    return "Verify whether this watch signal should remain needs_more_info or become reviewed evidence."


def main() -> int:
    parser = argparse.ArgumentParser(description="Build wet-lab feedback authorization operator checklist")
    parser.add_argument("--gap-matrix", type=Path, default=GAP_MATRIX)
    parser.add_argument("--gap-validation", type=Path, default=GAP_VALIDATION)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    parser.add_argument("--report", type=Path, default=REPORT)
    args = parser.parse_args()

    gaps = load_jsonl(args.gap_matrix)
    validation = load_json(args.gap_validation)

    rows: list[dict[str, Any]] = []
    for gap in sorted(gaps, key=lambda row: int(row.get("execution_order") or 10**9)):
        rows.append({
            "operator_checklist_id": f"wetlab-mutlib-auth-checklist-{gap.get('feedback_candidate_id', '').replace('wetlab-mutlib-', '')}",
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
            "required_review_fields": [
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
            ],
            "missing_or_invalid_items": gap.get("missing_or_invalid_items") or [],
            "validator_command": gap.get("validator_command"),
            "downstream_preflight_command": gap.get("downstream_preflight_command"),
            "safe_pipeline_command": "python3 scripts/run_safe_training_pipeline.py",
            "next_action_summary": next_action_summary(gap),
            "checklist_status": "open_blocked_waiting_for_human_review",
            "completion_condition": "reviewed authorization row validates and downstream preflight is generated; checklist alone is never sufficient",
            "requires_human_input": True,
            "completion_ready": False,
            "policy": "Operator checklist only; not an authorization, not feedback preflight, and not a training label.",
        })

    status_counts = Counter(row["checklist_status"] for row in rows)
    mode_counts = Counter(row["review_mode"] for row in rows)
    priority_counts = Counter(str(row.get("review_priority") or "") for row in rows)
    write_jsonl(args.output, rows)
    report = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "local_only": True,
        "operator_checklist_rows": len(rows),
        "gap_rows": len(gaps),
        "gap_validation_all_rows_valid": bool(validation.get("all_gap_rows_valid")),
        "open_blocked_checklist_rows": status_counts.get("open_blocked_waiting_for_human_review", 0),
        "tradeoff_review_required_rows": mode_counts.get("tradeoff_review_required", 0),
        "positive_candidate_review_required_rows": mode_counts.get("positive_candidate_review_required", 0),
        "watch_candidate_review_required_rows": mode_counts.get("watch_candidate_review_required", 0),
        "negative_candidate_review_required_rows": mode_counts.get("negative_candidate_review_required", 0),
        "completion_ready_rows": 0,
        "requires_human_input_rows": len(rows),
        "authorized_rows": 0,
        "ready_for_feedback_intake_rows": 0,
        "claim_eligible_rows_now": 0,
        "safe_for_model_claim": False,
        "priority_counts": dict(sorted(priority_counts.items())),
        "mode_counts": dict(sorted(mode_counts.items())),
        "status_counts": dict(sorted(status_counts.items())),
        "output": str(args.output),
        "policy": "Checklist guides human review only; it never grants authorization, writes preflight, appends labels, or enables model claims.",
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({
        "operator_checklist_rows": report["operator_checklist_rows"],
        "open_blocked_checklist_rows": report["open_blocked_checklist_rows"],
        "tradeoff_review_required_rows": report["tradeoff_review_required_rows"],
        "output": str(args.report),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
