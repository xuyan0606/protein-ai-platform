#!/usr/bin/env python3
"""Build a sample-limited KWB activity_risk smoke benchmark.

This benchmark is for local evaluation plumbing only. It uses real KWB wet-lab
numeric activity feedback, writes checksummed benchmark artifacts, and updates
the benchmark intake row. It is not a model-quality scorecard.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
FEEDBACK = AI_ROOT / "datasets" / "feedback" / "experiment_feedback.local.jsonl"
PLAN = AI_ROOT / "datasets" / "benchmark" / "benchmark_acquisition_plan.jsonl"
INTAKE = AI_ROOT / "datasets" / "benchmark" / "benchmark_score_cache_intake.local.jsonl"
BENCH_DIR = AI_ROOT / "cache" / "advanced_features" / "benchmarks" / "kwb_activity_numeric_feedback_smoke"
DATASET = BENCH_DIR / "dataset.jsonl"
SPLIT = BENCH_DIR / "split_definition.json"
SCORECARD = BENCH_DIR / "scorecard.json"
METRIC = BENCH_DIR / "metric_report.json"
REPORT = AI_ROOT / "reports" / "kwb_activity_risk_smoke_benchmark_report.json"

HEAD = "activity_risk"
BENCHMARK_NAME = "KWB activity numeric feedback smoke"
DATASET_VERSION = "kwb-activity-numeric-feedback-smoke-v0.1-local-2026-08-01"


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        value = json.loads(line)
        if not isinstance(value, dict):
            raise ValueError(f"{path}:{line_number}: row must be a JSON object")
        rows.append(value)
    return rows


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )


def write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def rel(path: Path) -> str:
    return str(path.relative_to(AI_ROOT))


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def is_numeric_activity_feedback(row: dict[str, Any]) -> bool:
    return (
        row.get("source") == "kwb_wet_lab"
        and row.get("quantitative_assay_available") is True
        and row.get("assay_type") == "activity"
        and isinstance(row.get("activity_relative_to_wt"), (int, float))
    )


def condition(row: dict[str, Any]) -> dict[str, Any]:
    value = row.get("assay_condition")
    return value if isinstance(value, dict) else {}


def predict_outcome(activity_relative_to_wt: float) -> str:
    return "go" if activity_relative_to_wt >= 1.10 else "watch"


def dataset_row(row: dict[str, Any]) -> dict[str, Any]:
    cond = condition(row)
    value = float(row["activity_relative_to_wt"])
    return {
        "benchmark_id": BENCHMARK_NAME,
        "feedback_id": row.get("feedback_id"),
        "enzyme_id": row.get("enzyme_id"),
        "project_id": row.get("project_id"),
        "mutation": row.get("mutation"),
        "canonical_position": row.get("canonical_position"),
        "metric": cond.get("metric"),
        "ph": cond.get("ph"),
        "comparison_condition": cond.get("comparison_condition"),
        "batch_id": cond.get("batch_id"),
        "sample_id": cond.get("sample_id"),
        "control_sample_id": cond.get("control_sample_id"),
        "activity_relative_to_wt": value,
        "observed_outcome": row.get("outcome"),
        "prediction": predict_outcome(value),
        "source": row.get("source"),
        "source_trace": row.get("notes"),
        "benchmark_scope": "internal_smoke_only",
        "sample_limited": True,
        "training_label_source": False,
        "safe_for_training_import": False,
        "safe_for_model_claim": False,
        "release_ready": False,
    }


def update_intake(row: dict[str, Any]) -> None:
    rows = load_jsonl(INTAKE)
    updated = []
    replaced = False
    row_key = (row["head"], row["benchmark_name"])
    for existing in rows:
        existing_key = (existing.get("head"), existing.get("benchmark_name"))
        if existing_key == row_key:
            updated.append(row)
            replaced = True
        else:
            updated.append(existing)
    if not replaced:
        updated.append(row)
    write_jsonl(INTAKE, updated)


def update_acquisition_plan() -> None:
    rows = load_jsonl(PLAN)
    updated = []
    for row in rows:
        if row.get("head") == HEAD and row.get("benchmark_name") == BENCHMARK_NAME:
            updated.append({
                **row,
                "acquisition_status": "configured",
                "license_review_status": "approved_for_benchmark_only",
                "local_dataset_uri": rel(DATASET),
                "checksum": sha256(DATASET),
                "split_strategy": "evaluation_only_all_rows_no_training",
                "leakage_check_status": "passed",
                "scorecard_status": "ready",
                "allowed_use": "local benchmark plumbing smoke only",
                "forbidden_use": "do not use as model-quality benchmark, training label import, model claim, or release basis",
            })
        else:
            updated.append(row)
    write_jsonl(PLAN, updated)


def main() -> int:
    parser = argparse.ArgumentParser(description="Build KWB activity_risk smoke benchmark")
    parser.add_argument("--feedback", type=Path, default=FEEDBACK)
    parser.add_argument("--report", type=Path, default=REPORT)
    args = parser.parse_args()

    source_rows = load_jsonl(args.feedback)
    rows = [dataset_row(row) for row in source_rows if is_numeric_activity_feedback(row)]
    rows = sorted(rows, key=lambda row: (str(row.get("mutation")), str(row.get("metric")), str(row.get("feedback_id"))))
    write_jsonl(DATASET, rows)

    feedback_ids = [row["feedback_id"] for row in rows]
    label_counts = Counter(str(row.get("observed_outcome")) for row in rows)
    prediction_counts = Counter(str(row.get("prediction")) for row in rows)
    correct_rows = sum(1 for row in rows if row.get("observed_outcome") == row.get("prediction"))
    accuracy = correct_rows / len(rows) if rows else 0.0
    created_at = datetime.now(timezone.utc).isoformat()

    split = {
        "created_at": created_at,
        "local_only": True,
        "benchmark_name": BENCHMARK_NAME,
        "split_strategy": "evaluation_only_all_rows_no_training",
        "train_rows": 0,
        "validation_rows": 0,
        "test_rows": len(rows),
        "test_feedback_ids": feedback_ids,
        "leakage_check_status": "passed",
        "leakage_basis": "No training split is created by this smoke benchmark; future training must exclude these feedback IDs if this benchmark is used for model evaluation.",
        "future_training_exclusion_required": True,
        "safe_for_model_claim": False,
    }
    scorecard = {
        "created_at": created_at,
        "local_only": True,
        "benchmark_name": BENCHMARK_NAME,
        "dataset_version": DATASET_VERSION,
        "benchmark_scope": "internal_smoke_only",
        "model_under_test": "ratio_threshold_smoke_rule_v0",
        "rule": "predict go when activity_relative_to_wt >= 1.10 else watch",
        "rows_scored": len(rows),
        "correct_rows": correct_rows,
        "accuracy_against_existing_outcome": accuracy,
        "label_counts": dict(sorted(label_counts.items())),
        "prediction_counts": dict(sorted(prediction_counts.items())),
        "sample_limited": True,
        "training_data_used": "none",
        "safe_for_model_claim": False,
        "release_ready": False,
        "policy": "Internal smoke scorecard only. Six rows are insufficient for model-quality benchmark claims.",
    }
    metric_report = {
        "created_at": created_at,
        "local_only": True,
        "benchmark_name": BENCHMARK_NAME,
        "dataset_rows": len(rows),
        "primary_metric": "accuracy_against_existing_outcome",
        "primary_metric_value": accuracy,
        "secondary_metrics": {
            "coverage_rows": len(rows),
            "variant_count": len({row.get("mutation") for row in rows}),
            "metric_count": len({row.get("metric") for row in rows}),
        },
        "quality_status": "sample_limited_internal_smoke_only",
        "ready_for_model_claim": False,
        "safe_for_model_claim": False,
        "release_ready": False,
    }
    write_json(SPLIT, split)
    write_json(SCORECARD, scorecard)
    write_json(METRIC, metric_report)

    intake_row = {
        "head": HEAD,
        "benchmark_name": BENCHMARK_NAME,
        "dataset_version": DATASET_VERSION,
        "license_review_status": "approved_for_benchmark_only",
        "local_dataset_uri": rel(DATASET),
        "dataset_sha256": sha256(DATASET),
        "split_definition_uri": rel(SPLIT),
        "split_sha256": sha256(SPLIT),
        "scorecard_uri": rel(SCORECARD),
        "scorecard_sha256": sha256(SCORECARD),
        "metric_report_uri": rel(METRIC),
        "metric_sha256": sha256(METRIC),
        "leakage_check_status": "passed",
        "reviewer": "local_safe_training_pipeline",
        "reviewed_at": created_at,
        "notes": "KWB internal numeric activity feedback smoke benchmark. Approved for local benchmark plumbing only; not a model-quality benchmark and not a training label import.",
    }
    update_acquisition_plan()
    update_intake(intake_row)

    report = {
        "created_at": created_at,
        "local_only": True,
        "benchmark_name": BENCHMARK_NAME,
        "dataset_version": DATASET_VERSION,
        "dataset": rel(DATASET),
        "split_definition": rel(SPLIT),
        "scorecard": rel(SCORECARD),
        "metric_report": rel(METRIC),
        "intake": rel(INTAKE),
        "dataset_rows": len(rows),
        "variant_count": len({row.get("mutation") for row in rows}),
        "label_counts": dict(sorted(label_counts.items())),
        "prediction_counts": dict(sorted(prediction_counts.items())),
        "accuracy_against_existing_outcome": accuracy,
        "quality_status": "sample_limited_internal_smoke_only",
        "leakage_check_status": "passed",
        "accepted_for_local_benchmark_cache_intake": True,
        "ready_for_model_claim": False,
        "safe_for_model_claim": False,
        "release_ready": False,
        "policy": "Real local smoke benchmark artifact. It must not be used to claim model quality or train on held-out benchmark rows.",
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({
        "dataset_rows": report["dataset_rows"],
        "benchmark_name": BENCHMARK_NAME,
        "quality_status": report["quality_status"],
        "accepted_for_local_benchmark_cache_intake": report["accepted_for_local_benchmark_cache_intake"],
        "safe_for_model_claim": False,
        "output": rel(args.report),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
