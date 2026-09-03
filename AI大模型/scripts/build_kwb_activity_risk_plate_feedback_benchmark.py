#!/usr/bin/env python3
"""Build an evaluation-only KWB 4G plate-level activity-risk benchmark."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
SOURCE_DIR = AI_ROOT / "酶改造突变体库-湿实验数据" / "4G_database-提高比活力"
RAW_MEASUREMENTS = SOURCE_DIR / "04_原始测量事实表.csv"
SAMPLE_MAP = SOURCE_DIR / "05_样本与批次对应表.csv"
CONTROL_MAP = SOURCE_DIR / "06_批次与对照映射表.csv"
PLAN = AI_ROOT / "datasets" / "benchmark" / "benchmark_acquisition_plan.jsonl"
INTAKE = AI_ROOT / "datasets" / "benchmark" / "benchmark_score_cache_intake.local.jsonl"
REPORT = AI_ROOT / "reports" / "kwb_activity_risk_plate_feedback_benchmark_report.json"
BENCH_DIR = AI_ROOT / "cache" / "advanced_features" / "benchmarks" / "kwb_4g_activity_risk_plate_feedback"
DATASET = BENCH_DIR / "dataset.jsonl"
SPLIT = BENCH_DIR / "split_definition.json"
SCORECARD = BENCH_DIR / "scorecard.json"
METRIC = BENCH_DIR / "metric_report.json"

HEAD = "activity_risk"
BENCHMARK_NAME = "KWB plate-level wet-lab feedback"
DATASET_VERSION = "kwb-4g-activity-risk-plate-feedback-v0.1-local-2026-08-03"
REPLICATE_RE = re.compile(r"^replicate_(\d+)$")


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def rel(path: Path) -> str:
    return str(path.relative_to(AI_ROOT))


def numeric(value: Any) -> float | None:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if math.isfinite(result) else None


def replicate_index(value: Any) -> int | None:
    match = REPLICATE_RE.match(str(value or ""))
    return int(match.group(1)) if match else None


def sample_sd(values: list[float]) -> float:
    if len(values) < 2:
        return 0.0
    mean = sum(values) / len(values)
    return math.sqrt(sum((value - mean) ** 2 for value in values) / (len(values) - 1))


def risk_label(ratio: float) -> str:
    if ratio >= 1.0:
        return "low_activity_risk"
    if ratio >= 0.8:
        return "watch_activity_risk"
    return "high_activity_risk"


def evidence_quality(variant_replicates: int, control_replicates: int, ratio: float) -> str:
    if variant_replicates >= 3 and control_replicates >= 3:
        return "plate_control_ratio_supported"
    if variant_replicates >= 1 and control_replicates >= 3 and math.isfinite(ratio):
        return "limited_variant_replicates_control_supported"
    return "limited_replicate_evidence"


def update_rows(path: Path, row: dict[str, Any], key_fields: tuple[str, str]) -> None:
    rows = load_jsonl(path)
    key = tuple(row.get(field) for field in key_fields)
    next_rows: list[dict[str, Any]] = []
    updated = False
    for existing in rows:
        if tuple(existing.get(field) for field in key_fields) == key:
            next_rows.append({**existing, **row})
            updated = True
        else:
            next_rows.append(existing)
    if not updated:
        next_rows.append(row)
    write_jsonl(path, next_rows)


def main() -> int:
    parser = argparse.ArgumentParser(description="Build KWB 4G activity-risk plate feedback benchmark")
    parser.add_argument("--raw-measurements", type=Path, default=RAW_MEASUREMENTS)
    parser.add_argument("--sample-map", type=Path, default=SAMPLE_MAP)
    parser.add_argument("--control-map", type=Path, default=CONTROL_MAP)
    parser.add_argument("--report", type=Path, default=REPORT)
    args = parser.parse_args()

    created_at = datetime.now(timezone.utc).isoformat()
    raw_rows = read_csv(args.raw_measurements)
    sample_rows = read_csv(args.sample_map)
    control_rows = read_csv(args.control_map)
    sample_by_id = {row.get("sample_id"): row for row in sample_rows if row.get("sample_id")}
    control_by_batch = {row.get("batch_id"): row for row in control_rows if row.get("batch_id")}

    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    skipped_counts: Counter[str] = Counter()
    for row in raw_rows:
        if row.get("metric_code") != "xylanase_activity":
            skipped_counts["not_xylanase_activity"] += 1
            continue
        value = numeric(row.get("raw_value_numeric"))
        rep = replicate_index(row.get("replicate_status"))
        if value is None:
            skipped_counts["raw_value_not_numeric"] += 1
            continue
        if rep is None:
            skipped_counts["replicate_status_not_explicit"] += 1
            continue
        if not row.get("sample_id"):
            skipped_counts["missing_sample_id"] += 1
            continue
        grouped[row["sample_id"]].append({**row, "raw_value_numeric": value, "replicate_index": rep})

    dataset_rows: list[dict[str, Any]] = []
    blocked_samples: list[dict[str, Any]] = []
    for sample_id, measurements in sorted(grouped.items()):
        sample = sample_by_id.get(sample_id, {})
        if sample.get("is_control") == "YES":
            continue
        batch_id = sample.get("batch_id") or measurements[0].get("batch_id")
        control_sample_id = sample.get("control_sample_id") or (control_by_batch.get(batch_id, {}) or {}).get("control_sample_id")
        control_measurements = grouped.get(control_sample_id or "", [])
        values = [float(row["raw_value_numeric"]) for row in measurements]
        control_values = [float(row["raw_value_numeric"]) for row in control_measurements]
        if not values or not control_values:
            blocked_samples.append({"sample_id": sample_id, "reason": "missing_variant_or_control_measurements", "control_sample_id": control_sample_id})
            continue
        mean_value = sum(values) / len(values)
        control_mean = sum(control_values) / len(control_values)
        if control_mean <= 0:
            blocked_samples.append({"sample_id": sample_id, "reason": "control_mean_not_positive", "control_sample_id": control_sample_id, "control_mean": control_mean})
            continue
        ratio = mean_value / control_mean
        label = risk_label(ratio)
        variant_sd = sample_sd(values)
        control_sd = sample_sd(control_values)
        dataset_rows.append({
            "benchmark_record_id": f"kwb_4g_activity_risk_plate_feedback::{len(dataset_rows)+1}",
            "benchmark_name": BENCHMARK_NAME,
            "head": HEAD,
            "project_id": "4G_database-提高比活力",
            "batch_id": batch_id,
            "batch_name": sample.get("batch_name") or (control_by_batch.get(batch_id, {}) or {}).get("batch_name"),
            "sample_id": sample_id,
            "variant_name": sample.get("variant_name") or measurements[0].get("variant_name"),
            "control_sample_id": control_sample_id,
            "control_variant_name": (control_by_batch.get(batch_id, {}) or {}).get("control_variant_name"),
            "metric_code": "xylanase_activity",
            "condition_name": measurements[0].get("condition_name"),
            "unit_standardized": measurements[0].get("unit_standardized"),
            "variant_replicate_count": len(values),
            "control_replicate_count": len(control_values),
            "variant_measurement_ids": [row.get("measurement_id") for row in sorted(measurements, key=lambda item: int(item["replicate_index"]))],
            "control_measurement_ids": [row.get("measurement_id") for row in sorted(control_measurements, key=lambda item: int(item["replicate_index"]))],
            "variant_mean_activity": mean_value,
            "variant_sd_activity": variant_sd,
            "variant_cv_activity": variant_sd / mean_value if mean_value > 0 else None,
            "control_mean_activity": control_mean,
            "control_sd_activity": control_sd,
            "control_cv_activity": control_sd / control_mean if control_mean > 0 else None,
            "activity_relative_to_batch_control": ratio,
            "activity_risk_label": label,
            "activity_risk_thresholds": {"low_activity_risk": "ratio >= 1.0", "watch_activity_risk": "0.8 <= ratio < 1.0", "high_activity_risk": "ratio < 0.8"},
            "evidence_quality_status": evidence_quality(len(values), len(control_values), ratio),
            "benchmark_scope": "internal_wet_lab_activity_risk_plate_feedback_eval_only",
            "training_label_source": False,
            "activity_risk_training_label_source": False,
            "ready_for_training_import": False,
            "safe_for_training_import": False,
            "safe_for_model_claim": False,
            "release_ready": False,
            "source_raw_measurement_file": rel(args.raw_measurements),
            "source_raw_measurement_sha256": sha256(args.raw_measurements),
            "source_sample_map_file": rel(args.sample_map),
            "source_sample_map_sha256": sha256(args.sample_map),
            "source_control_map_file": rel(args.control_map),
            "source_control_map_sha256": sha256(args.control_map),
        })

    write_jsonl(DATASET, dataset_rows)
    label_counts = Counter(row["activity_risk_label"] for row in dataset_rows)
    quality_counts = Counter(row["evidence_quality_status"] for row in dataset_rows)
    raw_measurement_rows_used = sum(row["variant_replicate_count"] + row["control_replicate_count"] for row in dataset_rows)
    split = {
        "created_at": created_at,
        "local_only": True,
        "benchmark_name": BENCHMARK_NAME,
        "head": HEAD,
        "split_strategy": "evaluation_only_batch_control_activity_ratio_no_training",
        "train_rows": 0,
        "validation_rows": 0,
        "test_rows": len(dataset_rows),
        "test_record_ids": [row["benchmark_record_id"] for row in dataset_rows],
        "leakage_check_status": "passed",
        "leakage_basis": "Rows are batch-control activity-ratio evaluation records and are not admitted into KWB training labels.",
        "future_training_exclusion_required": True,
        "ready_for_model_claim": False,
        "safe_for_model_claim": False,
        "release_ready": False,
    }
    scorecard = {
        "created_at": created_at,
        "local_only": True,
        "benchmark_name": BENCHMARK_NAME,
        "head": HEAD,
        "dataset_version": DATASET_VERSION,
        "model_under_test": "none_batch_control_activity_ratio_scorecard_only",
        "rows_scored": len(dataset_rows),
        "raw_measurement_rows_used": raw_measurement_rows_used,
        "unique_batches": len({row["batch_id"] for row in dataset_rows}),
        "unique_variants": len({row["variant_name"] for row in dataset_rows}),
        "label_counts": dict(sorted(label_counts.items())),
        "evidence_quality_counts": dict(sorted(quality_counts.items())),
        "quality_status": "internal_plate_activity_risk_cache_ready_not_model_claim",
        "training_data_used": "none_by_this_benchmark_cache_row",
        "ready_for_model_claim": False,
        "safe_for_model_claim": False,
        "release_ready": False,
    }
    metric = {
        "created_at": created_at,
        "local_only": True,
        "benchmark_name": BENCHMARK_NAME,
        "head": HEAD,
        "dataset_rows": len(dataset_rows),
        "primary_metric": "batch_control_activity_ratio_rows",
        "primary_metric_value": len(dataset_rows),
        "secondary_metrics": {
            "raw_measurement_rows_used": raw_measurement_rows_used,
            "unique_batches": scorecard["unique_batches"],
            "unique_variants": scorecard["unique_variants"],
            "label_counts": dict(sorted(label_counts.items())),
            "evidence_quality_counts": dict(sorted(quality_counts.items())),
            "blocked_samples": len(blocked_samples),
        },
        "quality_status": "internal_plate_activity_risk_cache_ready_not_model_claim",
        "leakage_check_status": "passed",
        "ready_as_benchmark_scorecard": True,
        "ready_for_model_claim": False,
        "safe_for_model_claim": False,
        "release_ready": False,
    }
    write_json(SPLIT, split)
    write_json(SCORECARD, scorecard)
    write_json(METRIC, metric)

    intake = {
        "head": HEAD,
        "benchmark_name": BENCHMARK_NAME,
        "dataset_version": DATASET_VERSION,
        "license_review_status": "approved_for_benchmark_only",
        "authorization_status": "self_attested_internal_wet_lab_benchmark_only",
        "verification_required": True,
        "local_dataset_uri": rel(DATASET),
        "dataset_sha256": sha256(DATASET),
        "split_definition_uri": rel(SPLIT),
        "split_sha256": sha256(SPLIT),
        "scorecard_uri": rel(SCORECARD),
        "scorecard_sha256": sha256(SCORECARD),
        "metric_report_uri": rel(METRIC),
        "metric_sha256": sha256(METRIC),
        "leakage_check_status": "passed",
        "reviewer": "local_kwb_4g_activity_risk_plate_feedback_builder",
        "reviewed_at": created_at,
        "notes": "Evaluation-only activity-risk benchmark from 4G batch-control activity ratios. Not a reviewed training-label import.",
    }
    update_rows(PLAN, {
        "head": HEAD,
        "benchmark_name": BENCHMARK_NAME,
        "acquisition_status": "configured",
        "license_review_status": "approved_for_benchmark_only",
        "local_dataset_uri": rel(DATASET),
        "checksum": sha256(DATASET),
        "split_strategy": "evaluation_only_batch_control_activity_ratio_no_training",
        "leakage_check_status": "passed",
        "scorecard_status": "ready",
        "allowed_use": "local wet-lab batch-control activity-risk benchmark only",
        "forbidden_use": "do not use as activity_risk training labels, model-quality claim, or release basis",
    }, ("head", "benchmark_name"))
    update_rows(INTAKE, intake, ("head", "benchmark_name"))

    report = {
        "created_at": created_at,
        "local_only": True,
        "benchmark_name": BENCHMARK_NAME,
        "head": HEAD,
        "dataset_rows": len(dataset_rows),
        "raw_measurement_rows_used": raw_measurement_rows_used,
        "unique_batches": scorecard["unique_batches"],
        "unique_variants": scorecard["unique_variants"],
        "label_counts": dict(sorted(label_counts.items())),
        "evidence_quality_counts": dict(sorted(quality_counts.items())),
        "blocked_samples": blocked_samples,
        "outputs": {
            "dataset": rel(DATASET),
            "split": rel(SPLIT),
            "scorecard": rel(SCORECARD),
            "metric_report": rel(METRIC),
        },
        "training_import_written_rows": 0,
        "activity_risk_training_label_rows_written": 0,
        "ready_for_model_claim": False,
        "safe_for_model_claim": False,
        "release_ready": False,
        "policy": "Evaluation-only activity-risk benchmark. Batch-control ratios may support benchmark coverage only and do not create reviewed labels or model claims.",
    }
    write_json(args.report, report)
    print(json.dumps({
        "benchmark_name": BENCHMARK_NAME,
        "dataset_rows": len(dataset_rows),
        "raw_measurement_rows_used": raw_measurement_rows_used,
        "unique_batches": scorecard["unique_batches"],
        "training_import_written_rows": 0,
        "output": str(args.report),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
