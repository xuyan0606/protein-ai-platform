#!/usr/bin/env python3
"""Validate the five-head sample/replicate/group threshold report."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
REPORT = AI_ROOT / "reports" / "five_head_training_threshold_report.json"
OUT = AI_ROOT / "reports" / "five_head_training_threshold_validation_report.json"
EXPECTED_HEADS = (
    "mutation_rank",
    "stability",
    "activity_risk",
    "substrate_fit",
    "assay_success",
)


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    value = json.loads(path.read_text(encoding="utf-8"))
    return value if isinstance(value, dict) else {}


def as_int(value: Any) -> int:
    if isinstance(value, bool):
        return int(value)
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def fail_if(
    condition: bool,
    failures: list[dict[str, Any]],
    check: str,
    observed: Any,
    expected: Any,
) -> None:
    if condition:
        failures.append({"check": check, "observed": observed, "expected": expected})


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate five-head threshold report")
    parser.add_argument("--report", type=Path, default=REPORT)
    parser.add_argument("--output", type=Path, default=OUT)
    args = parser.parse_args()

    report = load_json(args.report)
    failures: list[dict[str, Any]] = []
    fail_if(not report, failures, "report_present", str(args.report), "existing JSON report")
    fail_if(report.get("status") != "blocked", failures, "status_blocked", report.get("status"), "blocked")
    fail_if(
        report.get("expected_heads") != list(EXPECTED_HEADS),
        failures,
        "expected_heads_match",
        report.get("expected_heads"),
        list(EXPECTED_HEADS),
    )
    fail_if(
        report.get("training_execution_allowed") is not False,
        failures,
        "training_execution_allowed_false",
        report.get("training_execution_allowed"),
        False,
    )
    for key in ("safe_for_training_import", "safe_for_model_claim", "release_ready"):
        fail_if(report.get(key) is not False, failures, f"{key}_false", report.get(key), False)

    source_counts = report.get("source_counts") if isinstance(report.get("source_counts"), dict) else {}
    source_report_counts = report.get("source_report_counts") if isinstance(report.get("source_report_counts"), dict) else {}
    for key in (
        "numeric_feedback_rows",
        "strict_supervised_rows",
        "fireprot_reviewed_import_rows",
        "plate_training_eligible_rows",
        "activity_risk_training_import_label_rows",
    ):
        fail_if(
            as_int(source_counts.get(key)) != as_int(source_report_counts.get(key)),
            failures,
            f"{key}_matches_source_report",
            {"jsonl": source_counts.get(key), "report": source_report_counts.get(key)},
            "equal",
        )

    boundary = report.get("feature_label_boundary") if isinstance(report.get("feature_label_boundary"), dict) else {}
    fail_if(
        as_int(boundary.get("feature_rows_counted_as_labels")) != 0,
        failures,
        "feature_rows_counted_as_labels_zero",
        boundary.get("feature_rows_counted_as_labels"),
        0,
    )
    fail_if(
        boundary.get("feature_inputs_are_labels") is not False,
        failures,
        "feature_inputs_are_not_labels",
        boundary.get("feature_inputs_are_labels"),
        False,
    )
    fail_if(bool(report.get("source_consistency_failures")), failures, "source_consistency_failures_empty", report.get("source_consistency_failures"), [])
    fail_if(any(report.get("parse_errors", {}).values()), failures, "source_parse_errors_empty", report.get("parse_errors"), {})

    heads = report.get("heads") if isinstance(report.get("heads"), dict) else {}
    fail_if(set(heads) != set(EXPECTED_HEADS), failures, "all_heads_present", sorted(heads), sorted(EXPECTED_HEADS))
    computed_blocked_heads: list[str] = []
    computed_zero_label_heads: list[str] = []
    computed_below_threshold_heads: list[str] = []
    for head in EXPECTED_HEADS:
        item = heads.get(head) if isinstance(heads.get(head), dict) else {}
        label_rows = as_int(item.get("label_rows"))
        candidate_rows = as_int(item.get("candidate_rows"))
        metrics = item.get("label_metrics") if isinstance(item.get("label_metrics"), dict) else {}
        checks = item.get("threshold_checks") if isinstance(item.get("threshold_checks"), dict) else {}
        thresholds = item.get("thresholds") if isinstance(item.get("thresholds"), dict) else {}
        missing_label_fields = (
            item.get("missing_required_fields_in_label_rows")
            if isinstance(item.get("missing_required_fields_in_label_rows"), dict)
            else {}
        )
        if label_rows > 0:
            fail_if(
                any(as_int(count) > 0 for count in missing_label_fields.values()),
                failures,
                f"{head}_label_rows_have_required_fields",
                missing_label_fields,
                "all zero",
            )
        computed = {
            "minimum_samples": as_int(metrics.get("sample_count")) >= as_int(thresholds.get("minimum_samples")),
            "minimum_replicates": as_int(metrics.get("replicate_count")) >= as_int(thresholds.get("minimum_replicates")),
            "minimum_groups": as_int(metrics.get("group_count")) >= as_int(thresholds.get("minimum_groups")),
        }
        for check_name, expected_met in computed.items():
            check = checks.get(check_name) if isinstance(checks.get(check_name), dict) else {}
            fail_if(
                check.get("met") is not expected_met,
                failures,
                f"{head}_{check_name}_consistent",
                check.get("met"),
                expected_met,
            )
        expected_thresholds_met = bool(computed) and all(computed.values())
        fail_if(
            item.get("thresholds_met") is not expected_thresholds_met,
            failures,
            f"{head}_thresholds_met_consistent",
            item.get("thresholds_met"),
            expected_thresholds_met,
        )
        fail_if(item.get("trainable") is not False, failures, f"{head}_trainable_false", item.get("trainable"), False)
        fail_if(item.get("training_allowed") is not False, failures, f"{head}_training_allowed_false", item.get("training_allowed"), False)
        if not (item.get("thresholds_met") is True and label_rows > 0):
            computed_blocked_heads.append(head)
        if label_rows == 0:
            computed_zero_label_heads.append(head)
        if label_rows > 0 and item.get("thresholds_met") is not True:
            computed_below_threshold_heads.append(head)
        if candidate_rows > 0:
            fail_if(
                item.get("status") != "candidate_only" and label_rows == 0,
                failures,
                f"{head}_candidate_status",
                item.get("status"),
                "candidate_only",
            )

    fail_if(report.get("trainable_heads") != [], failures, "trainable_heads_empty", report.get("trainable_heads"), [])
    fail_if(as_int(report.get("ready_head_count")) != 0, failures, "ready_head_count_zero", report.get("ready_head_count"), 0)
    fail_if(
        sorted(report.get("blocked_heads") or []) != sorted(computed_blocked_heads),
        failures,
        "blocked_heads_match_non_ready_heads",
        report.get("blocked_heads"),
        computed_blocked_heads,
    )
    fail_if(
        sorted(report.get("zero_label_heads") or []) != sorted(computed_zero_label_heads),
        failures,
        "zero_label_heads_match_zero_label_rows",
        report.get("zero_label_heads"),
        computed_zero_label_heads,
    )
    fail_if(
        sorted(report.get("below_threshold_heads") or []) != sorted(computed_below_threshold_heads),
        failures,
        "below_threshold_heads_match_label_rows_below_threshold",
        report.get("below_threshold_heads"),
        computed_below_threshold_heads,
    )

    validation = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "local_only": True,
        "checked_report": str(args.report),
        "source_counts": source_counts,
        "candidate_heads": report.get("candidate_heads"),
        "blocked_heads": report.get("blocked_heads"),
        "threshold_ready_heads": report.get("threshold_ready_heads"),
        "zero_label_heads": report.get("zero_label_heads"),
        "below_threshold_heads": report.get("below_threshold_heads"),
        "ready_head_count": report.get("ready_head_count"),
        "training_execution_allowed": report.get("training_execution_allowed"),
        "failures": failures,
        "success": not failures,
        "safe_for_training_import": False,
        "safe_for_model_claim": False,
        "release_ready": False,
        "policy": (
            "Fail-closed validation. Candidate rows, numeric feedback, and feature rows "
            "cannot satisfy a head label threshold without the explicit head label contract."
        ),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(validation, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({
        "success": validation["success"],
        "source_counts": source_counts,
        "candidate_heads": validation["candidate_heads"],
        "blocked_heads": validation["blocked_heads"],
        "below_threshold_heads": validation["below_threshold_heads"],
        "training_execution_allowed": False,
        "failures": len(failures),
        "output": str(args.output),
    }, ensure_ascii=False))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
