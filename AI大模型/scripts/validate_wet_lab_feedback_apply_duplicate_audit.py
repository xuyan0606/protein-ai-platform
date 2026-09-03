#!/usr/bin/env python3
"""Validate the wet-lab feedback apply duplicate audit."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
AUDIT = AI_ROOT / "datasets" / "feedback" / "wet_lab_feedback_apply_duplicate_audit.jsonl"
REPORT = AI_ROOT / "reports" / "wet_lab_feedback_apply_duplicate_audit_report.json"
OUTPUT = AI_ROOT / "reports" / "wet_lab_feedback_apply_duplicate_audit_validation_report.json"
PREFLIGHT = AI_ROOT / "datasets" / "feedback" / "wet_lab_mutant_library_feedback_preflight.jsonl"
APPLY_PLAN = AI_ROOT / "datasets" / "feedback" / "wet_lab_mutant_library_feedback_intake_apply_plan.jsonl"
LOCAL_FEEDBACK = AI_ROOT / "datasets" / "feedback" / "experiment_feedback.local.jsonl"


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    value = json.loads(path.read_text(encoding="utf-8"))
    return value if isinstance(value, dict) else {}


def load_jsonl(path: Path) -> tuple[list[dict[str, Any]], int]:
    rows: list[dict[str, Any]] = []
    invalid = 0
    if not path.exists():
        return rows, invalid
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError:
            invalid += 1
            continue
        if not isinstance(value, dict):
            invalid += 1
            continue
        rows.append(value)
    return rows, invalid


def as_int(value: Any) -> int:
    if isinstance(value, bool):
        return int(value)
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def fail_if(condition: bool, failures: list[dict[str, Any]], check: str, observed: Any, expected: Any) -> None:
    if condition:
        failures.append({"check": check, "observed": observed, "expected": expected})


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate wet-lab feedback apply duplicate audit")
    parser.add_argument("--audit", type=Path, default=AUDIT)
    parser.add_argument("--report", type=Path, default=REPORT)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    args = parser.parse_args()

    audit_rows, audit_invalid = load_jsonl(args.audit)
    preflight_rows, preflight_invalid = load_jsonl(PREFLIGHT)
    apply_plan_rows, apply_plan_invalid = load_jsonl(APPLY_PLAN)
    feedback_rows, feedback_invalid = load_jsonl(LOCAL_FEEDBACK)
    report = load_json(args.report)
    failures: list[dict[str, Any]] = []

    represented = [row for row in audit_rows if row.get("already_represented_in_experiment_feedback_local") is True]
    stability_new = [
        row
        for row in audit_rows
        if row.get("stability_retention_percent_candidate") is True
        and row.get("already_represented_in_experiment_feedback_local") is not True
    ]
    unrepresented_activity = [
        row
        for row in audit_rows
        if row.get("activity_training_label_candidate") is True
        and row.get("already_represented_in_experiment_feedback_local") is not True
    ]

    fail_if(not report, failures, "audit_report_present", str(args.report), "existing JSON report")
    fail_if(not args.audit.exists(), failures, "audit_jsonl_present", str(args.audit), "existing JSONL audit")
    fail_if(audit_invalid != 0, failures, "audit_jsonl_valid", audit_invalid, 0)
    fail_if(preflight_invalid != 0, failures, "preflight_jsonl_valid", preflight_invalid, 0)
    fail_if(apply_plan_invalid != 0, failures, "apply_plan_jsonl_valid", apply_plan_invalid, 0)
    fail_if(feedback_invalid != 0, failures, "local_feedback_jsonl_valid", feedback_invalid, 0)

    fail_if(len(audit_rows) != len(preflight_rows), failures, "audit_rows_match_preflight", len(audit_rows), len(preflight_rows))
    fail_if(as_int(report.get("preflight_rows")) != len(preflight_rows), failures, "report_preflight_rows", report.get("preflight_rows"), len(preflight_rows))
    fail_if(as_int(report.get("apply_plan_rows")) != len(apply_plan_rows), failures, "report_apply_plan_rows", report.get("apply_plan_rows"), len(apply_plan_rows))
    fail_if(as_int(report.get("existing_feedback_rows")) != len(feedback_rows), failures, "report_existing_feedback_rows", report.get("existing_feedback_rows"), len(feedback_rows))
    fail_if(as_int(report.get("already_represented_rows")) != len(represented), failures, "report_already_represented_rows", report.get("already_represented_rows"), len(represented))
    fail_if(as_int(report.get("new_feedback_only_rows")) != len(stability_new), failures, "report_new_feedback_only_rows", report.get("new_feedback_only_rows"), len(stability_new))
    fail_if(as_int(report.get("unrepresented_activity_candidate_rows")) != len(unrepresented_activity), failures, "report_unrepresented_activity_candidate_rows", report.get("unrepresented_activity_candidate_rows"), len(unrepresented_activity))

    fail_if(bool(unrepresented_activity), failures, "no_unrepresented_activity_rows_to_append", [row.get("feedback_candidate_id") for row in unrepresented_activity], [])
    fail_if(as_int(report.get("safe_to_append_rows")) != 0, failures, "safe_to_append_rows_zero", report.get("safe_to_append_rows"), 0)
    fail_if(as_int(report.get("safe_to_append_as_training_label_rows")) != 0, failures, "safe_to_append_as_training_label_rows_zero", report.get("safe_to_append_as_training_label_rows"), 0)
    fail_if(as_int(report.get("training_import_eligible_from_apply_plan_rows")) != 0, failures, "apply_plan_training_import_rows_zero", report.get("training_import_eligible_from_apply_plan_rows"), 0)
    fail_if(as_int(report.get("claim_eligible_rows_now")) != 0, failures, "claim_eligible_rows_now_zero", report.get("claim_eligible_rows_now"), 0)
    fail_if(report.get("safe_for_model_claim") is not False, failures, "safe_for_model_claim_false", report.get("safe_for_model_claim"), False)
    fail_if(report.get("release_ready") is not False, failures, "release_ready_false", report.get("release_ready"), False)

    unsafe_rows = [
        row.get("feedback_candidate_id")
        for row in audit_rows
        if row.get("safe_to_append_to_experiment_feedback_local") is True
        or row.get("safe_to_append_as_training_label") is True
        or row.get("training_import_eligible_from_apply_plan") is True
    ]
    fail_if(bool(unsafe_rows), failures, "no_row_allows_append_or_training_import", unsafe_rows, [])

    represented_without_match = [
        row.get("feedback_candidate_id")
        for row in represented
        if not row.get("existing_candidate_id_matches") and not row.get("existing_canonical_feedback_id_matches")
    ]
    fail_if(bool(represented_without_match), failures, "represented_rows_have_match_evidence", represented_without_match, [])

    validation = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "local_only": True,
        "success": not failures,
        "audit_rows": len(audit_rows),
        "preflight_rows": len(preflight_rows),
        "apply_plan_rows": len(apply_plan_rows),
        "existing_feedback_rows": len(feedback_rows),
        "already_represented_rows": len(represented),
        "new_feedback_only_rows": len(stability_new),
        "unrepresented_activity_candidate_rows": len(unrepresented_activity),
        "safe_to_append_rows": as_int(report.get("safe_to_append_rows")),
        "training_import_eligible_from_apply_plan_rows": as_int(
            report.get("training_import_eligible_from_apply_plan_rows")
        ),
        "failures": failures,
        "safe_for_model_claim": False,
        "release_ready": False,
        "policy": (
            "A passing duplicate audit does not append feedback. It proves current apply-plan rows are either "
            "already represented or remain feedback-only, and that no row can enter training import through "
            "the apply-plan path."
        ),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(validation, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "success": validation["success"],
                "already_represented_rows": validation["already_represented_rows"],
                "new_feedback_only_rows": validation["new_feedback_only_rows"],
                "safe_to_append_rows": validation["safe_to_append_rows"],
                "failures": len(failures),
                "output": str(args.output),
            },
            ensure_ascii=False,
        )
    )
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
