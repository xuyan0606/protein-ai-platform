#!/usr/bin/env python3
"""Validate the five-head training gap plan is source-bound and fail-closed."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
REPORT = AI_ROOT / "reports" / "five_head_training_gap_plan_report.json"
OUT = AI_ROOT / "reports" / "five_head_training_gap_plan_validation_report.json"
GAP_ACTIONS_JSONL = AI_ROOT / "datasets" / "governance" / "five_head_training_gap_actions.jsonl"
THRESHOLD = AI_ROOT / "reports" / "five_head_training_threshold_report.json"
MULTITASK_VALIDATION = AI_ROOT / "reports" / "multitask_training_readiness_validation_report.json"
CLAIM = AI_ROOT / "reports" / "claim_readiness_matrix.json"
WET_CANDIDATES = AI_ROOT / "datasets" / "feedback" / "wet_lab_mutant_library_feedback_candidates.jsonl"
WET_WORKLIST = AI_ROOT / "datasets" / "feedback" / "wet_lab_mutant_library_feedback_authorization_worklist.jsonl"
WET_AUTH = AI_ROOT / "datasets" / "feedback" / "wet_lab_mutant_library_feedback_authorizations.jsonl"
FIREPROT_MAPPING = AI_ROOT / "datasets" / "curation" / "fireprot_curated_kwb_schema_mapping_candidates.jsonl"
FIREPROT_REVIEWED = AI_ROOT / "datasets" / "curation" / "fireprot_reviewed_import_candidates.jsonl"
EXPECTED_HEADS = ("mutation_rank", "stability", "activity_risk", "substrate_fit", "assay_success")
MIN_ROWS = 100
ACTION_PARITY_FIELDS = (
    "head",
    "priority",
    "current_training_rows",
    "minimum_rows",
    "missing_to_minimum",
    "candidate_rows_observed",
    "ready_candidate_rows",
    "primary_source",
    "review_queue",
    "blocking_gate",
    "next_action",
    "notes",
    "training_unlocked",
    "safe_for_model_claim",
    "minimum_replicates",
    "minimum_groups",
    "observed_sample_count",
    "observed_replicate_count",
    "observed_group_count",
    "head_status",
    "thresholds_met",
    "policy",
)


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    value = json.loads(path.read_text(encoding="utf-8"))
    return value if isinstance(value, dict) else {}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


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
    parser = argparse.ArgumentParser(description="Validate five-head training gap plan")
    parser.add_argument("--report", type=Path, default=REPORT)
    parser.add_argument("--gap-actions-jsonl", type=Path, default=GAP_ACTIONS_JSONL)
    parser.add_argument("--output", type=Path, default=OUT)
    args = parser.parse_args()

    report = load_json(args.report)
    gap_action_rows = load_jsonl(args.gap_actions_jsonl)
    threshold = load_json(THRESHOLD)
    multitask_validation = load_json(MULTITASK_VALIDATION)
    claim = load_json(CLAIM)
    wet_candidates = load_jsonl(WET_CANDIDATES)
    wet_worklist = load_jsonl(WET_WORKLIST)
    wet_auth = load_jsonl(WET_AUTH)
    fireprot_mapping = load_jsonl(FIREPROT_MAPPING)
    fireprot_reviewed = load_jsonl(FIREPROT_REVIEWED)
    wet_numeric = [row for row in wet_candidates if row.get("numeric_training_candidate") is True]
    wet_activity = [row for row in wet_numeric if row.get("assay_type") == "activity"]
    wet_stability = [row for row in wet_numeric if row.get("assay_type") == "stability"]
    auth_approved = [
        row for row in wet_auth
        if row.get("authorization_decision") == "approved_for_feedback_intake"
    ]

    failures: list[dict[str, Any]] = []
    fail_if(not report, failures, "report_present", str(args.report), "existing JSON report")
    fail_if(report.get("status") != "blocked", failures, "status_blocked", report.get("status"), "blocked")
    fail_if(report.get("local_only") is not True, failures, "local_only_true", report.get("local_only"), True)
    for key in ("safe_for_training_import", "safe_for_model_claim", "release_ready"):
        fail_if(report.get(key) is not False, failures, f"{key}_false", report.get(key), False)
    fail_if(multitask_validation.get("success") is not True, failures, "multitask_validation_success", multitask_validation.get("success"), True)

    threshold_heads = threshold.get("heads") if isinstance(threshold.get("heads"), dict) else {}
    threshold_sources = threshold.get("source_counts") if isinstance(threshold.get("source_counts"), dict) else {}
    actions = report.get("head_gap_actions") if isinstance(report.get("head_gap_actions"), list) else []
    actions_by_head = {
        action.get("head"): action
        for action in actions
        if isinstance(action, dict)
    }
    gap_action_heads = [
        row.get("head")
        for row in gap_action_rows
        if isinstance(row, dict)
    ]
    gap_actions_by_head = {
        row.get("head"): row
        for row in gap_action_rows
        if isinstance(row, dict)
    }
    fail_if(report.get("total_heads") != len(EXPECTED_HEADS), failures, "total_heads_match_expected", report.get("total_heads"), len(EXPECTED_HEADS))
    fail_if(set(actions_by_head) != set(EXPECTED_HEADS), failures, "all_head_gap_actions_present", sorted(actions_by_head), sorted(EXPECTED_HEADS))
    fail_if(len(gap_action_rows) != len(EXPECTED_HEADS), failures, "gap_action_jsonl_rows_match_expected", len(gap_action_rows), len(EXPECTED_HEADS))
    fail_if(len(gap_action_heads) != len(set(gap_action_heads)), failures, "gap_action_jsonl_heads_unique", gap_action_heads, sorted(set(gap_action_heads)))
    fail_if(set(gap_actions_by_head) != set(EXPECTED_HEADS), failures, "gap_action_jsonl_all_heads_present", sorted(gap_actions_by_head), sorted(EXPECTED_HEADS))
    fail_if(report.get("ready_heads") != 0, failures, "ready_heads_zero", report.get("ready_heads"), 0)
    fail_if(report.get("threshold_ready_heads") != [], failures, "threshold_ready_heads_empty", report.get("threshold_ready_heads"), [])
    fail_if(sorted(report.get("blocked_heads") or []) != sorted(EXPECTED_HEADS), failures, "blocked_heads_all_expected", report.get("blocked_heads"), list(EXPECTED_HEADS))
    fail_if(report.get("claim_matrix_blocked_claims") != claim.get("claims_blocked"), failures, "claim_matrix_blocked_claims_current", report.get("claim_matrix_blocked_claims"), claim.get("claims_blocked"))

    for head in EXPECTED_HEADS:
        action = actions_by_head.get(head) if isinstance(actions_by_head.get(head), dict) else {}
        gap_action = gap_actions_by_head.get(head) if isinstance(gap_actions_by_head.get(head), dict) else {}
        for field in ACTION_PARITY_FIELDS:
            fail_if(
                gap_action.get(field) != action.get(field),
                failures,
                f"{head}_gap_action_jsonl_{field}_matches_report",
                gap_action.get(field),
                action.get(field),
            )
        threshold_head = threshold_heads.get(head) if isinstance(threshold_heads.get(head), dict) else {}
        thresholds = threshold_head.get("thresholds") if isinstance(threshold_head.get("thresholds"), dict) else {}
        metrics = threshold_head.get("label_metrics") if isinstance(threshold_head.get("label_metrics"), dict) else {}
        label_rows = as_int(threshold_head.get("label_rows"))
        minimum_rows = as_int(thresholds.get("minimum_samples")) or MIN_ROWS
        fail_if(as_int(action.get("current_training_rows")) != label_rows, failures, f"{head}_current_training_rows_match_threshold", action.get("current_training_rows"), label_rows)
        fail_if(as_int(action.get("minimum_rows")) != minimum_rows, failures, f"{head}_minimum_rows_match_threshold", action.get("minimum_rows"), minimum_rows)
        fail_if(as_int(action.get("missing_to_minimum")) != max(minimum_rows - label_rows, 0), failures, f"{head}_missing_to_minimum_current", action.get("missing_to_minimum"), max(minimum_rows - label_rows, 0))
        fail_if(as_int(action.get("candidate_rows_observed")) != as_int(threshold_head.get("candidate_rows")), failures, f"{head}_candidate_rows_match_threshold", action.get("candidate_rows_observed"), threshold_head.get("candidate_rows"))
        fail_if(as_int(action.get("minimum_replicates")) != as_int(thresholds.get("minimum_replicates")), failures, f"{head}_minimum_replicates_match_threshold", action.get("minimum_replicates"), thresholds.get("minimum_replicates"))
        fail_if(as_int(action.get("minimum_groups")) != as_int(thresholds.get("minimum_groups")), failures, f"{head}_minimum_groups_match_threshold", action.get("minimum_groups"), thresholds.get("minimum_groups"))
        fail_if(as_int(action.get("observed_sample_count")) != as_int(metrics.get("sample_count")), failures, f"{head}_sample_count_match_threshold", action.get("observed_sample_count"), metrics.get("sample_count"))
        fail_if(as_int(action.get("observed_replicate_count")) != as_int(metrics.get("replicate_count")), failures, f"{head}_replicate_count_match_threshold", action.get("observed_replicate_count"), metrics.get("replicate_count"))
        fail_if(as_int(action.get("observed_group_count")) != as_int(metrics.get("group_count")), failures, f"{head}_group_count_match_threshold", action.get("observed_group_count"), metrics.get("group_count"))
        fail_if(action.get("head_status") != threshold_head.get("status"), failures, f"{head}_status_match_threshold", action.get("head_status"), threshold_head.get("status"))
        fail_if(action.get("thresholds_met") is not (threshold_head.get("thresholds_met") is True), failures, f"{head}_thresholds_met_match_threshold", action.get("thresholds_met"), threshold_head.get("thresholds_met") is True)
        fail_if(action.get("training_unlocked") is not False, failures, f"{head}_training_unlocked_false", action.get("training_unlocked"), False)
        fail_if(action.get("safe_for_model_claim") is not False, failures, f"{head}_safe_for_model_claim_false", action.get("safe_for_model_claim"), False)
        fail_if(gap_action.get("training_unlocked") is not False, failures, f"{head}_gap_action_jsonl_training_unlocked_false", gap_action.get("training_unlocked"), False)
        fail_if(gap_action.get("safe_for_model_claim") is not False, failures, f"{head}_gap_action_jsonl_safe_for_model_claim_false", gap_action.get("safe_for_model_claim"), False)

    candidate_signals = report.get("candidate_signals") if isinstance(report.get("candidate_signals"), dict) else {}
    expected_signals = {
        "wet_lab_candidate_rows": len(wet_candidates),
        "wet_lab_numeric_candidate_rows": as_int(threshold_sources.get("numeric_feedback_rows")),
        "wet_lab_numeric_activity_rows": as_int((threshold_heads.get("activity_risk") or {}).get("candidate_rows")),
        "wet_lab_numeric_stability_rows": as_int((threshold_heads.get("stability") or {}).get("candidate_rows")),
        "wet_lab_authorization_worklist_rows": len(wet_worklist),
        "wet_lab_authorized_rows": len(auth_approved),
        "fireprot_mapping_candidate_rows": len(fireprot_mapping),
        "fireprot_reviewed_import_candidate_rows": as_int(threshold_sources.get("fireprot_reviewed_import_rows")),
        "plate_feedback_ready_for_intake_rows": as_int(threshold_sources.get("plate_training_eligible_rows")),
        "feature_rows_excluded_from_labels": as_int((threshold.get("feature_label_boundary") or {}).get("feature_rows_observed")),
    }
    for key, expected in expected_signals.items():
        fail_if(as_int(candidate_signals.get(key)) != expected, failures, f"candidate_signal_{key}_current", candidate_signals.get(key), expected)
    fail_if(candidate_signals.get("license_ready_for_training") is not False, failures, "license_ready_for_training_false", candidate_signals.get("license_ready_for_training"), False)

    validation = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "local_only": True,
        "checked_report": str(args.report),
        "checked_gap_actions_jsonl": str(args.gap_actions_jsonl),
        "expected_heads": list(EXPECTED_HEADS),
        "gap_action_jsonl_rows": len(gap_action_rows),
        "gap_action_heads": gap_action_heads,
        "expected_signals": expected_signals,
        "ready_heads": report.get("ready_heads"),
        "blocked_heads": report.get("blocked_heads"),
        "failures": failures,
        "success": not failures,
        "safe_for_training_import": False,
        "safe_for_model_claim": False,
        "release_ready": False,
        "policy": "Fail-closed validation for five-head gap planning; no labels, approvals, training, or claims are created.",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(validation, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({
        "success": validation["success"],
        "ready_heads": validation["ready_heads"],
        "blocked_heads": validation["blocked_heads"],
        "failures": len(failures),
        "output": str(args.output),
    }, ensure_ascii=False))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
