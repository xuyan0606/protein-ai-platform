#!/usr/bin/env python3
"""Validate five-head training execution remains fail-closed."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
REPORT = AI_ROOT / "reports" / "five_head_training_execution_contract_report.json"
OUT = AI_ROOT / "reports" / "five_head_training_execution_contract_validation_report.json"
MULTITASK = AI_ROOT / "reports" / "multitask_training_readiness_report.json"
THRESHOLD = AI_ROOT / "reports" / "five_head_training_threshold_report.json"
EXPECTED_HEADS = ("mutation_rank", "stability", "activity_risk", "substrate_fit", "assay_success")


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


def fail_if(condition: bool, failures: list[dict[str, Any]], check: str, observed: Any, expected: Any) -> None:
    if condition:
        failures.append({"check": check, "observed": observed, "expected": expected})


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate five-head training execution contract")
    parser.add_argument("--report", type=Path, default=REPORT)
    parser.add_argument("--output", type=Path, default=OUT)
    args = parser.parse_args()

    report = load_json(args.report)
    multitask = load_json(MULTITASK)
    threshold_report = load_json(THRESHOLD)
    failures: list[dict[str, Any]] = []
    fail_if(not report, failures, "report_present", str(args.report), "existing JSON report")
    fail_if(report.get("success") is not True, failures, "source_report_success_true", report.get("success"), True)
    fail_if(report.get("status") != "blocked", failures, "status_blocked", report.get("status"), "blocked")
    fail_if(report.get("expected_heads") != list(EXPECTED_HEADS), failures, "expected_heads_match", report.get("expected_heads"), list(EXPECTED_HEADS))

    head_rows = report.get("head_rows") if isinstance(report.get("head_rows"), dict) else {}
    multitask_heads = multitask.get("heads") if isinstance(multitask.get("heads"), dict) else {}
    threshold_heads = threshold_report.get("heads") if isinstance(threshold_report.get("heads"), dict) else {}
    fail_if(set(head_rows) != set(EXPECTED_HEADS), failures, "all_heads_present", sorted(head_rows), sorted(EXPECTED_HEADS))
    fail_if(
        set(multitask_heads) != set(EXPECTED_HEADS),
        failures,
        "multitask_all_heads_present",
        sorted(multitask_heads),
        sorted(EXPECTED_HEADS),
    )
    fail_if(
        set(threshold_heads) != set(EXPECTED_HEADS),
        failures,
        "threshold_all_heads_present",
        sorted(threshold_heads),
        sorted(EXPECTED_HEADS),
    )
    for head in EXPECTED_HEADS:
        row = head_rows.get(head) if isinstance(head_rows.get(head), dict) else {}
        multitask_row = multitask_heads.get(head) if isinstance(multitask_heads.get(head), dict) else {}
        threshold_row = threshold_heads.get(head) if isinstance(threshold_heads.get(head), dict) else {}
        threshold_values = threshold_row.get("thresholds") if isinstance(threshold_row.get("thresholds"), dict) else {}
        threshold_label_rows = as_int(threshold_row.get("label_rows"))
        threshold_minimum_samples = as_int(threshold_values.get("minimum_samples")) or 100
        fail_if(as_int(row.get("rows")) < 0, failures, f"{head}_rows_non_negative", row.get("rows"), ">=0")
        fail_if(
            as_int(row.get("rows")) != threshold_label_rows,
            failures,
            f"{head}_rows_match_threshold_label_rows",
            {"contract": row.get("rows"), "threshold": threshold_row.get("label_rows")},
            "equal",
        )
        fail_if(
            as_int(multitask_row.get("rows")) != threshold_label_rows,
            failures,
            f"{head}_multitask_rows_match_threshold_label_rows",
            {"multitask": multitask_row.get("rows"), "threshold": threshold_row.get("label_rows")},
            "equal",
        )
        fail_if(
            as_int(multitask_row.get("minimum_rows")) != threshold_minimum_samples,
            failures,
            f"{head}_multitask_minimum_rows_match_threshold_minimum_samples",
            {"multitask": multitask_row.get("minimum_rows"), "threshold": threshold_minimum_samples},
            "equal",
        )
        fail_if(row.get("ready") is not False, failures, f"{head}_ready_false", row.get("ready"), False)
        fail_if(as_int(row.get("minimum_rows")) < 100, failures, f"{head}_minimum_rows_at_least_100", row.get("minimum_rows"), ">=100")
        fail_if(as_int(row.get("minimum_replicates")) < 3, failures, f"{head}_minimum_replicates_at_least_3", row.get("minimum_replicates"), ">=3")
        fail_if(as_int(row.get("minimum_groups")) < 10, failures, f"{head}_minimum_groups_at_least_10", row.get("minimum_groups"), ">=10")
        fail_if(row.get("thresholds_met") is not False, failures, f"{head}_thresholds_met_false", row.get("thresholds_met"), False)

    training_label = report.get("training_label_import") if isinstance(report.get("training_label_import"), dict) else {}
    wetlab = report.get("wet_lab_authorization") if isinstance(report.get("wet_lab_authorization"), dict) else {}
    benchmark = report.get("benchmark_gate") if isinstance(report.get("benchmark_gate"), dict) else {}
    feature = report.get("feature_input_gate") if isinstance(report.get("feature_input_gate"), dict) else {}
    threshold = report.get("per_head_threshold_gate") if isinstance(report.get("per_head_threshold_gate"), dict) else {}

    training_import_rows = as_int(training_label.get("training_import_eligible_rows"))
    fail_if(
        training_label.get("safe_for_training_import") is not (training_import_rows > 0),
        failures,
        "training_label_safe_for_training_import_matches_training_import_rows",
        training_label.get("safe_for_training_import"),
        training_import_rows > 0,
    )
    fail_if(as_int(wetlab.get("ready_for_training_import_rows")) != 0, failures, "wetlab_ready_for_training_import_rows_zero", wetlab.get("ready_for_training_import_rows"), 0)
    fail_if(benchmark.get("ready_for_model_claim") is not False, failures, "benchmark_ready_for_model_claim_false", benchmark.get("ready_for_model_claim"), False)
    fail_if(feature.get("feature_inputs_are_labels") is not False, failures, "feature_inputs_not_labels", feature.get("feature_inputs_are_labels"), False)
    fail_if(threshold.get("report_present") is not True, failures, "threshold_report_present", threshold.get("report_present"), True)
    fail_if(threshold.get("report_consistent") is not True, failures, "threshold_report_consistent", threshold.get("report_consistent"), True)
    fail_if(
        threshold.get("multitask_threshold_parity_failures") != [],
        failures,
        "multitask_threshold_parity_failures_empty",
        threshold.get("multitask_threshold_parity_failures"),
        [],
    )
    fail_if(as_int(threshold.get("feature_rows_counted_as_labels")) != 0, failures, "threshold_feature_rows_not_labels", threshold.get("feature_rows_counted_as_labels"), 0)

    for key in ("training_execution_allowed", "model_quality_claim_allowed", "safe_for_training_import", "safe_for_model_claim", "release_ready"):
        fail_if(report.get(key) is not False, failures, f"{key}_false", report.get(key), False)

    blocked = set(report.get("blocked_reasons") or [])
    expected_training_block = (
        "training_import_eligible_rows_zero"
        if training_import_rows == 0
        else "training_import_eligible_rows_below_minimum"
    )
    for required in (
        expected_training_block,
        "per_head_sample_replicate_group_thresholds_not_met",
        "all_five_heads_missing_minimum_training_rows",
        "benchmark_ready_for_model_claim_false",
    ):
        fail_if(required not in blocked, failures, f"blocked_reason_{required}_present", sorted(blocked), required)

    validation = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "local_only": True,
        "success": not failures,
        "ready_head_count": report.get("ready_head_count"),
        "total_head_training_rows": report.get("total_head_training_rows"),
        "training_import_eligible_rows": training_label.get("training_import_eligible_rows"),
        "multitask_threshold_parity_failures": threshold.get("multitask_threshold_parity_failures"),
        "training_execution_allowed": report.get("training_execution_allowed"),
        "failures": failures,
        "safe_for_training_import": False,
        "safe_for_model_claim": False,
        "release_ready": False,
        "policy": "Fail-closed validation for five-head training execution.",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(validation, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({
        "success": validation["success"],
        "ready_head_count": validation["ready_head_count"],
        "total_head_training_rows": validation["total_head_training_rows"],
        "training_import_eligible_rows": validation["training_import_eligible_rows"],
        "training_execution_allowed": validation["training_execution_allowed"],
        "failures": len(failures),
        "output": str(args.output),
    }, ensure_ascii=False))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
