#!/usr/bin/env python3
"""Build a fail-closed apply plan for wet-lab feedback intake preflight rows."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
PREFLIGHT = AI_ROOT / "datasets" / "feedback" / "wet_lab_mutant_library_feedback_preflight.jsonl"
LOCAL_FEEDBACK = AI_ROOT / "datasets" / "feedback" / "experiment_feedback.local.jsonl"
OUTPUT = AI_ROOT / "datasets" / "feedback" / "wet_lab_mutant_library_feedback_intake_apply_plan.jsonl"
REPORT = AI_ROOT / "reports" / "wet_lab_mutant_library_feedback_intake_apply_plan_report.json"


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def validate_preflight(row: dict[str, Any], existing_feedback_ids: set[str]) -> list[str]:
    errors: list[str] = []
    required = [
        "preflight_feedback_id",
        "feedback_candidate_id",
        "proposed_feedback_id",
        "project_id",
        "mutation",
        "numbering_verified",
        "assay_type",
        "assay_condition",
        "outcome",
        "source",
        "source_file",
        "source_file_sha256",
        "raw_value_numeric",
        "control_value_numeric",
        "vs_control_ratio",
    ]
    for field in required:
        if field not in row:
            errors.append(f"missing_{field}")
    if row.get("source") != "kwb_wet_lab":
        errors.append("invalid_source")
    if row.get("numbering_verified") is not True:
        errors.append("numbering_not_verified")
    if row.get("proposed_feedback_id") in existing_feedback_ids:
        errors.append("proposed_feedback_id_already_exists")
    for field in ["raw_value_numeric", "control_value_numeric", "vs_control_ratio"]:
        if not isinstance(row.get(field), (int, float)) or isinstance(row.get(field), bool):
            errors.append(f"invalid_{field}")
    if row.get("ready_for_feedback_intake") is True:
        errors.append("preflight_should_not_mark_ready_for_feedback_intake")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description="Build wet-lab feedback intake apply plan")
    parser.add_argument("--preflight", type=Path, default=PREFLIGHT)
    parser.add_argument("--local-feedback", type=Path, default=LOCAL_FEEDBACK)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    parser.add_argument("--report", type=Path, default=REPORT)
    args = parser.parse_args()

    preflight_rows = load_jsonl(args.preflight)
    feedback_rows = load_jsonl(args.local_feedback)
    existing_ids = {str(row.get("feedback_id")) for row in feedback_rows if row.get("feedback_id")}
    plan_rows = []
    errors = Counter()
    for row in preflight_rows:
        row_errors = validate_preflight(row, existing_ids)
        errors.update(row_errors)
        can_apply = not row_errors
        plan_rows.append({
            "apply_plan_id": f"wetlab-feedback-apply-plan-{row.get('feedback_candidate_id')}",
            "preflight_feedback_id": row.get("preflight_feedback_id"),
            "feedback_candidate_id": row.get("feedback_candidate_id"),
            "proposed_feedback_id": row.get("proposed_feedback_id"),
            "mutation": row.get("mutation"),
            "assay_type": row.get("assay_type"),
            "source_project": row.get("source_project"),
            "valid_preflight_row": not row_errors,
            "can_apply_to_experiment_feedback_local": False,
            "would_be_apply_ready_if_user_explicitly_authorizes": can_apply,
            "errors": row_errors,
            "remaining_blockers": [
                "explicit_user_authorization_to_append_feedback_missing",
                "separate_apply_command_not_executed",
                "post_apply_feedback_validator_not_run",
            ],
            "policy": "Apply plan only; does not append to experiment_feedback.local.jsonl.",
        })

    write_jsonl(args.output, plan_rows)
    valid_rows = sum(1 for row in plan_rows if row["valid_preflight_row"])
    report = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "local_only": True,
        "preflight": str(args.preflight),
        "local_feedback": str(args.local_feedback),
        "output": str(args.output),
        "preflight_rows": len(preflight_rows),
        "existing_feedback_rows": len(feedback_rows),
        "apply_plan_rows": len(plan_rows),
        "valid_preflight_rows": valid_rows,
        "would_be_apply_ready_if_user_explicitly_authorizes_rows": sum(
            1 for row in plan_rows if row["would_be_apply_ready_if_user_explicitly_authorizes"]
        ),
        "applied_rows": 0,
        "ready_for_training_import_rows": 0,
        "claim_eligible_rows_now": 0,
        "safe_for_model_claim": False,
        "error_counts": dict(errors),
        "policy": "This plan never writes experiment_feedback.local.jsonl; append requires explicit user authorization and a separate apply command.",
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({
        "preflight_rows": report["preflight_rows"],
        "apply_plan_rows": report["apply_plan_rows"],
        "would_be_apply_ready_if_user_explicitly_authorizes_rows": report["would_be_apply_ready_if_user_explicitly_authorizes_rows"],
        "applied_rows": report["applied_rows"],
        "output": str(args.report),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
