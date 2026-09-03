#!/usr/bin/env python3
"""Validate the five-head sample gap queue without opening any capability gate."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INPUT = AI_ROOT / "datasets" / "governance" / "five_head_training_sample_gap_queue.jsonl"
DEFAULT_REPORT = AI_ROOT / "reports" / "five_head_training_sample_gap_queue_validation_report.json"
DEFAULT_QUEUE_REPORT = AI_ROOT / "reports" / "five_head_training_sample_gap_queue_report.json"
THRESHOLD_REPORT = AI_ROOT / "reports" / "five_head_training_threshold_report.json"
EXPECTED_HEADS = (
    "mutation_rank",
    "stability",
    "activity_risk",
    "substrate_fit",
    "assay_success",
)
ALLOWED_TRAINING_ELIGIBLE_POOLS = {
    ("activity_risk", "activity_risk_formal_label_decisions"),
}
INPUTS = {
    "wet_lab_candidates": AI_ROOT / "datasets" / "feedback" / "wet_lab_mutant_library_feedback_candidates.jsonl",
    "wet_lab_authorization_gap_actions": AI_ROOT / "datasets" / "feedback" / "wet_lab_head_authorization_gap_actions.jsonl",
    "activity_risk_formal_label_decisions": AI_ROOT / "datasets" / "feedback" / "activity_risk_label_replicate_decisions.jsonl",
    "fireprot_mapping_candidates": AI_ROOT / "datasets" / "curation" / "fireprot_curated_kwb_schema_mapping_candidates.jsonl",
    "fireprot_reviewed_import_candidates": AI_ROOT / "datasets" / "curation" / "fireprot_reviewed_import_candidates.jsonl",
    "validated_feature_index": AI_ROOT / "datasets" / "features" / "validated_feature_index.jsonl",
}


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return value if isinstance(value, dict) else {}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            rows.append(value)
    return rows


def as_int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def non_null(value: Any) -> bool:
    return value is not None and value != ""


def candidate_metric(rows: list[dict[str, Any]]) -> dict[str, Any]:
    def first(row: dict[str, Any], keys: tuple[str, ...]) -> Any:
        for key in keys:
            if non_null(row.get(key)):
                return row[key]
        return None

    groups = {
        str(value)
        for value in (first(row, ("group_id", "variant_id", "mutation", "variant", "record_id")) for row in rows)
        if non_null(value)
    }
    replicates = {
        str(value)
        for value in (first(row, ("replicate", "replicate_id", "replicate_index")) for row in rows)
        if non_null(value)
    }
    return {
        "rows": len(rows),
        "unique_groups": len(groups),
        "unique_explicit_replicates": len(replicates),
        "rows_with_explicit_replicate": sum(
            1 for row in rows if non_null(first(row, ("replicate", "replicate_id", "replicate_index")))
        ),
    }


def fail_if(condition: bool, failures: list[dict[str, Any]], check: str, observed: Any, expected: Any) -> None:
    if condition:
        failures.append({"check": check, "observed": observed, "expected": expected})


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate five-head training sample gap queue")
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--queue-report", type=Path, default=DEFAULT_QUEUE_REPORT)
    parser.add_argument("--output", type=Path, default=DEFAULT_REPORT)
    args = parser.parse_args()

    rows = load_jsonl(args.input)
    queue_report = load_json(args.queue_report)
    threshold = load_json(THRESHOLD_REPORT)
    wet_candidates = load_jsonl(INPUTS["wet_lab_candidates"])
    auth_gap = load_jsonl(INPUTS["wet_lab_authorization_gap_actions"])
    activity_decisions = load_jsonl(INPUTS["activity_risk_formal_label_decisions"])
    fireprot_mapping = load_jsonl(INPUTS["fireprot_mapping_candidates"])
    fireprot_reviewed = load_jsonl(INPUTS["fireprot_reviewed_import_candidates"])
    features = load_jsonl(INPUTS["validated_feature_index"])
    threshold_heads = threshold.get("heads") if isinstance(threshold.get("heads"), dict) else {}
    failures: list[dict[str, Any]] = []
    expected_pool_rows = {
        ("mutation_rank", "reviewed_numbering"): [],
        ("mutation_rank", "real_supervised_labels"): [],
        ("stability", "fireprot_mapping_candidates"): list(fireprot_mapping),
        ("stability", "fireprot_reviewed_import"): list(fireprot_reviewed),
        ("stability", "kwb_wet_lab_stability"): [
            row for row in wet_candidates if row.get("assay_type") == "stability"
        ],
        ("activity_risk", "kwb_wet_lab_activity_numeric"): [
            row for row in wet_candidates
            if row.get("assay_type") == "activity"
            and row.get("numeric_training_candidate") is True
            and non_null(row.get("activity_relative_to_wt"))
        ],
        ("activity_risk", "activity_authorization_gap"): [
            row for row in auth_gap if row.get("expected_authorization_head") == "activity_risk_head"
        ],
        ("activity_risk", "activity_risk_formal_label_decisions"): list(activity_decisions),
        ("substrate_fit", "substrate_specific_assays"): [],
        ("assay_success", "plate_well_feedback"): [],
    }
    fail_if(len(rows) != len(EXPECTED_HEADS), failures, "queue_row_count", len(rows), len(EXPECTED_HEADS))
    fail_if(
        {row.get("head") for row in rows} != set(EXPECTED_HEADS),
        failures,
        "queue_heads",
        sorted(str(row.get("head")) for row in rows),
        sorted(EXPECTED_HEADS),
    )
    for row in rows:
        head = row.get("head")
        threshold_head = threshold_heads.get(head) if isinstance(threshold_heads.get(head), dict) else {}
        label_metrics = threshold_head.get("label_metrics") if isinstance(threshold_head.get("label_metrics"), dict) else {}
        thresholds = threshold_head.get("thresholds") if isinstance(threshold_head.get("thresholds"), dict) else {}
        expected = {
            "current_label_rows": as_int(threshold_head.get("label_rows")),
            "current_group_count": as_int(label_metrics.get("group_count")),
            "current_replicate_count": as_int(label_metrics.get("replicate_count")),
            "current_replicate_observation_count": as_int(label_metrics.get("replicate_observation_count")),
            "minimum_label_rows": as_int(thresholds.get("minimum_samples")) or 100,
            "minimum_groups": as_int(thresholds.get("minimum_groups")) or 10,
            "minimum_replicates": as_int(thresholds.get("minimum_replicates")) or 3,
        }
        for key, value in expected.items():
            fail_if(row.get(key) != value, failures, f"{head}_{key}_matches_threshold", row.get(key), value)
        fail_if(
            row.get("missing_label_rows_to_minimum") != max(expected["minimum_label_rows"] - expected["current_label_rows"], 0),
            failures,
            f"{head}_missing_label_rows_formula",
            row.get("missing_label_rows_to_minimum"),
            max(expected["minimum_label_rows"] - expected["current_label_rows"], 0),
        )
        fail_if(
            row.get("missing_groups_to_minimum") != max(expected["minimum_groups"] - expected["current_group_count"], 0),
            failures,
            f"{head}_missing_groups_formula",
            row.get("missing_groups_to_minimum"),
            max(expected["minimum_groups"] - expected["current_group_count"], 0),
        )
        fail_if(
            row.get("missing_replicates_to_minimum") != max(expected["minimum_replicates"] - expected["current_replicate_count"], 0),
            failures,
            f"{head}_missing_replicates_formula",
            row.get("missing_replicates_to_minimum"),
            max(expected["minimum_replicates"] - expected["current_replicate_count"], 0),
        )
        fail_if(row.get("status") != "blocked", failures, f"{head}_status_blocked", row.get("status"), "blocked")
        fail_if(row.get("training_import_written_rows") != 0, failures, f"{head}_training_import_zero", row.get("training_import_written_rows"), 0)
        fail_if(row.get("safe_for_training_import") is not False, failures, f"{head}_safe_for_training_import_false", row.get("safe_for_training_import"), False)
        fail_if(row.get("safe_for_model_claim") is not False, failures, f"{head}_safe_for_model_claim_false", row.get("safe_for_model_claim"), False)
        fail_if(row.get("release_ready") is not False, failures, f"{head}_release_ready_false", row.get("release_ready"), False)
        fail_if(not row.get("human_or_external_blockers"), failures, f"{head}_blockers_present", row.get("human_or_external_blockers"), "non-empty")
        fail_if(not row.get("forbidden_actions"), failures, f"{head}_forbidden_actions_present", row.get("forbidden_actions"), "non-empty")
        for pool in row.get("candidate_source_pools") or []:
            pool_name = pool.get("pool")
            allows_formal_labels = (head, pool_name) in ALLOWED_TRAINING_ELIGIBLE_POOLS
            expected_rows = expected_pool_rows.get((head, pool_name))
            expected_rows = expected_rows if isinstance(expected_rows, list) else []
            expected_metrics = candidate_metric(expected_rows)
            fail_if(
                as_int(pool.get("observed_rows")) != len(expected_rows),
                failures,
                f"{head}_{pool_name}_pool_observed_rows_match_source",
                pool.get("observed_rows"),
                len(expected_rows),
            )
            fail_if(
                as_int(pool.get("selected_rows_for_head")) != len(expected_rows),
                failures,
                f"{head}_{pool_name}_pool_selected_rows_match_source",
                pool.get("selected_rows_for_head"),
                len(expected_rows),
            )
            for metric_key, expected_metric in expected_metrics.items():
                observed_metrics = pool.get("sample_metrics") if isinstance(pool.get("sample_metrics"), dict) else {}
                fail_if(
                    as_int(observed_metrics.get(metric_key)) != expected_metric,
                    failures,
                    f"{head}_{pool_name}_pool_sample_metric_{metric_key}_match_source",
                    observed_metrics.get(metric_key),
                    expected_metric,
                )
            fail_if(
                (pool.get("selection_is_training_eligible") is True) != allows_formal_labels,
                failures,
                f"{head}_{pool_name}_pool_training_eligible_scope",
                pool.get("selection_is_training_eligible"),
                allows_formal_labels,
            )
            fail_if(as_int(pool.get("training_import_written_rows")) != 0, failures, f"{head}_pool_training_import_zero", pool.get("training_import_written_rows"), 0)
            expected_formal_rows = as_int(pool.get("observed_rows")) if allows_formal_labels else 0
            fail_if(
                as_int(pool.get("formal_decision_written_rows")) != expected_formal_rows,
                failures,
                f"{head}_{pool_name}_pool_formal_decision_scope",
                pool.get("formal_decision_written_rows"),
                expected_formal_rows,
            )

    expected_totals = {
        "queue_rows": len(rows),
        "current_label_rows": sum(as_int(row.get("current_label_rows")) for row in rows),
        "current_group_count_total": sum(as_int(row.get("current_group_count")) for row in rows),
        "current_replicate_count_total": sum(as_int(row.get("current_replicate_count")) for row in rows),
        "missing_label_rows_total": sum(as_int(row.get("missing_label_rows_to_minimum")) for row in rows),
        "missing_groups_total": sum(as_int(row.get("missing_groups_to_minimum")) for row in rows),
        "missing_replicates_total": sum(as_int(row.get("missing_replicates_to_minimum")) for row in rows),
        "candidate_source_pool_rows": sum(
            as_int(pool.get("observed_rows"))
            for row in rows
            for pool in (row.get("candidate_source_pools") or [])
            if isinstance(pool, dict)
        ),
        "feature_rows_observed": len(features),
        "feature_rows_counted_as_labels": 0,
        "training_import_written_rows": 0,
        "observed_formal_decision_rows": sum(
            as_int(pool.get("formal_decision_written_rows"))
            for row in rows
            for pool in (row.get("candidate_source_pools") or [])
            if isinstance(pool, dict)
        ),
        "formal_decision_written_rows": 0,
        "model_or_release_flags_changed_rows": 0,
    }
    fail_if(not queue_report, failures, "queue_report_present", str(args.queue_report), "existing JSON report")
    fail_if(queue_report.get("status") != "blocked", failures, "queue_report_status_blocked", queue_report.get("status"), "blocked")
    fail_if(queue_report.get("local_only") is not True, failures, "queue_report_local_only_true", queue_report.get("local_only"), True)
    for key, expected_value in expected_totals.items():
        fail_if(
            as_int(queue_report.get(key)) != expected_value,
            failures,
            f"queue_report_{key}_matches_queue",
            queue_report.get(key),
            expected_value,
        )
    fail_if(
        sorted(queue_report.get("expected_heads") or []) != sorted(EXPECTED_HEADS),
        failures,
        "queue_report_expected_heads_match",
        queue_report.get("expected_heads"),
        list(EXPECTED_HEADS),
    )
    fail_if(
        sorted(queue_report.get("heads_with_current_labels") or []) != sorted(row.get("head") for row in rows if as_int(row.get("current_label_rows")) > 0),
        failures,
        "queue_report_heads_with_current_labels_match",
        queue_report.get("heads_with_current_labels"),
        [row.get("head") for row in rows if as_int(row.get("current_label_rows")) > 0],
    )
    fail_if(
        sorted(queue_report.get("blocked_heads") or []) != sorted(EXPECTED_HEADS),
        failures,
        "queue_report_blocked_heads_all_expected",
        queue_report.get("blocked_heads"),
        list(EXPECTED_HEADS),
    )
    for key in ("safe_for_training_import", "safe_for_model_claim", "release_ready"):
        fail_if(queue_report.get(key) is not False, failures, f"queue_report_{key}_false", queue_report.get(key), False)

    report = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "local_only": True,
        "success": not failures,
        "queue_rows": len(rows),
        "checked_queue_report": str(args.queue_report),
        "expected_totals": expected_totals,
        "validation_passed_rows": len(rows) - len({failure.get("check") for failure in failures if isinstance(failure, dict)}),
        "failures": failures,
        "training_import_written_rows": 0,
        "formal_decision_written_rows": 0,
        "safe_for_training_import": False,
        "safe_for_model_claim": False,
        "release_ready": False,
        "policy": "Fail-closed queue validation. This artifact quantifies gaps and cannot promote candidates into labels or training rows.",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({
        "success": report["success"],
        "queue_rows": report["queue_rows"],
        "failures": len(failures),
        "training_import_written_rows": 0,
        "safe_for_model_claim": False,
        "output": str(args.output),
    }, ensure_ascii=False))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
