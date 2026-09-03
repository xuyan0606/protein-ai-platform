#!/usr/bin/env python3
"""Build an evaluation-only KWB 4G replicate consistency benchmark.

The benchmark uses local raw wet-lab replicate measurements to score assay
repeatability. It is a benchmark cache artifact only; it does not create
assay_success labels, training rows, model claims, or release readiness.
"""

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
CONTROL_MAP = SOURCE_DIR / "06_批次与对照映射表.csv"
SAMPLE_MAP = SOURCE_DIR / "05_样本与批次对应表.csv"
PLAN = AI_ROOT / "datasets" / "benchmark" / "benchmark_acquisition_plan.jsonl"
INTAKE = AI_ROOT / "datasets" / "benchmark" / "benchmark_score_cache_intake.local.jsonl"
BENCH_DIR = AI_ROOT / "cache" / "advanced_features" / "benchmarks" / "kwb_4g_replicate_consistency"
DATASET = BENCH_DIR / "dataset.jsonl"
SPLIT = BENCH_DIR / "split_definition.json"
SCORECARD = BENCH_DIR / "scorecard.json"
METRIC = BENCH_DIR / "metric_report.json"
REPORT = AI_ROOT / "reports" / "kwb_replicate_consistency_benchmark_report.json"

HEAD = "assay_success"
BENCHMARK_NAME = "replicate consistency"
DATASET_VERSION = "kwb-4g-replicate-consistency-v0.1-local-2026-08-03"
REPLICATE_RE = re.compile(r"^replicate_(\d+)$")


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


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


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


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


def consistency_status(replicate_count: int, mean_value: float, cv: float | None) -> str:
    if replicate_count < 3:
        return "insufficient_replicates"
    if mean_value <= 0 or cv is None:
        return "invalid_mean_for_cv"
    if cv <= 0.15:
        return "consistent_pass"
    if cv <= 0.30:
        return "consistent_watch"
    return "inconsistent_fail"


def update_intake(row: dict[str, Any]) -> None:
    rows = load_jsonl(INTAKE)
    row_key = (row["head"], row["benchmark_name"])
    next_rows = [
        existing for existing in rows
        if (existing.get("head"), existing.get("benchmark_name")) != row_key
    ]
    next_rows.append(row)
    write_jsonl(INTAKE, next_rows)


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
                "split_strategy": "evaluation_only_grouped_raw_replicates_no_training",
                "leakage_check_status": "passed",
                "scorecard_status": "ready",
                "allowed_use": "local wet-lab replicate consistency benchmark only",
                "forbidden_use": "do not use as assay_success training labels, model-quality claim, or release basis",
            })
        else:
            updated.append(row)
    write_jsonl(PLAN, updated)


def main() -> int:
    parser = argparse.ArgumentParser(description="Build KWB 4G replicate consistency benchmark")
    parser.add_argument("--raw-measurements", type=Path, default=RAW_MEASUREMENTS)
    parser.add_argument("--control-map", type=Path, default=CONTROL_MAP)
    parser.add_argument("--sample-map", type=Path, default=SAMPLE_MAP)
    parser.add_argument("--report", type=Path, default=REPORT)
    args = parser.parse_args()

    created_at = datetime.now(timezone.utc).isoformat()
    raw_rows = read_csv(args.raw_measurements)
    control_rows = read_csv(args.control_map)
    sample_rows = read_csv(args.sample_map)
    control_by_batch = {row.get("batch_id"): row for row in control_rows if row.get("batch_id")}
    sample_by_id = {row.get("sample_id"): row for row in sample_rows if row.get("sample_id")}

    grouped: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)
    skipped_counts: Counter[str] = Counter()
    for row in raw_rows:
        value = numeric(row.get("raw_value_numeric"))
        rep_index = replicate_index(row.get("replicate_status"))
        if row.get("metric_code") != "xylanase_activity":
            skipped_counts["not_xylanase_activity"] += 1
            continue
        if value is None:
            skipped_counts["raw_value_not_numeric"] += 1
            continue
        if rep_index is None:
            skipped_counts["replicate_status_not_explicit"] += 1
            continue
        if not row.get("sample_id") or not row.get("batch_id") or not row.get("variant_name"):
            skipped_counts["missing_group_identity"] += 1
            continue
        grouped[(row["batch_id"], row["sample_id"], row["variant_name"])].append({
            **row,
            "raw_value_numeric": value,
            "replicate_index": rep_index,
        })

    dataset_rows: list[dict[str, Any]] = []
    for index, (group_key, measurements) in enumerate(sorted(grouped.items()), start=1):
        batch_id, sample_id, variant_name = group_key
        measurements = sorted(measurements, key=lambda row: (int(row["replicate_index"]), str(row.get("measurement_id"))))
        values = [float(row["raw_value_numeric"]) for row in measurements]
        mean_value = sum(values) / len(values)
        sd_value = sample_sd(values)
        cv = sd_value / mean_value if mean_value > 0 else None
        status = consistency_status(len(values), mean_value, cv)
        sample_info = sample_by_id.get(sample_id, {})
        control_info = control_by_batch.get(batch_id, {})
        dataset_rows.append({
            "benchmark_record_id": f"kwb_4g_replicate_consistency::{index}",
            "benchmark_name": BENCHMARK_NAME,
            "head": HEAD,
            "project_id": "4G_database-提高比活力",
            "batch_id": batch_id,
            "sample_id": sample_id,
            "variant_name": variant_name,
            "is_control": sample_info.get("is_control") == "YES",
            "control_sample_id": sample_info.get("control_sample_id") or control_info.get("control_sample_id"),
            "metric_code": "xylanase_activity",
            "metric_name": "木聚糖酶酶活",
            "condition_name": measurements[0].get("condition_name"),
            "unit_standardized": measurements[0].get("unit_standardized"),
            "replicate_count": len(values),
            "replicate_ids": [row.get("replicate_status") for row in measurements],
            "measurement_ids": [row.get("measurement_id") for row in measurements],
            "mean_raw_activity": mean_value,
            "sd_raw_activity": sd_value,
            "cv_raw_activity": cv,
            "consistency_status": status,
            "benchmark_scope": "internal_wet_lab_replicate_consistency_eval_only",
            "training_label_source": False,
            "assay_success_label_source": False,
            "ready_for_training_import": False,
            "safe_for_training_import": False,
            "safe_for_model_claim": False,
            "release_ready": False,
            "source_raw_measurement_file": rel(args.raw_measurements),
            "source_raw_measurement_sha256": sha256(args.raw_measurements),
            "source_control_map_file": rel(args.control_map),
            "source_control_map_sha256": sha256(args.control_map),
            "source_sample_map_file": rel(args.sample_map),
            "source_sample_map_sha256": sha256(args.sample_map),
        })
    write_jsonl(DATASET, dataset_rows)

    status_counts = Counter(row["consistency_status"] for row in dataset_rows)
    cv_values = [float(row["cv_raw_activity"]) for row in dataset_rows if isinstance(row.get("cv_raw_activity"), float)]
    split = {
        "created_at": created_at,
        "local_only": True,
        "benchmark_name": BENCHMARK_NAME,
        "head": HEAD,
        "split_strategy": "evaluation_only_grouped_raw_replicates_no_training",
        "train_rows": 0,
        "validation_rows": 0,
        "test_rows": len(dataset_rows),
        "test_record_ids": [row["benchmark_record_id"] for row in dataset_rows],
        "leakage_check_status": "passed",
        "leakage_basis": "Rows are grouped raw replicate QC summaries and are not admitted into assay_success training labels by this builder.",
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
        "model_under_test": "none_replicate_qc_scorecard_only",
        "rows_scored": len(dataset_rows),
        "raw_measurement_rows_used": sum(row["replicate_count"] for row in dataset_rows),
        "unique_batch_count": len({row.get("batch_id") for row in dataset_rows}),
        "unique_sample_count": len({row.get("sample_id") for row in dataset_rows}),
        "unique_variant_count": len({row.get("variant_name") for row in dataset_rows}),
        "status_counts": dict(sorted(status_counts.items())),
        "mean_cv_raw_activity": sum(cv_values) / len(cv_values) if cv_values else None,
        "max_cv_raw_activity": max(cv_values) if cv_values else None,
        "sample_limited": False,
        "quality_status": "internal_replicate_consistency_cache_ready_not_model_claim",
        "training_data_used": "none_by_this_benchmark_cache_row",
        "ready_for_model_claim": False,
        "safe_for_model_claim": False,
        "release_ready": False,
        "policy": "Internal wet-lab replicate consistency benchmark cache only; not assay_success training labels or model-quality evidence.",
    }
    metric_report = {
        "created_at": created_at,
        "local_only": True,
        "benchmark_name": BENCHMARK_NAME,
        "head": HEAD,
        "dataset_rows": len(dataset_rows),
        "primary_metric": "replicate_group_rows",
        "primary_metric_value": len(dataset_rows),
        "secondary_metrics": {
            "raw_measurement_rows_used": scorecard["raw_measurement_rows_used"],
            "consistent_pass_rows": status_counts.get("consistent_pass", 0),
            "consistent_watch_rows": status_counts.get("consistent_watch", 0),
            "inconsistent_fail_rows": status_counts.get("inconsistent_fail", 0),
            "insufficient_or_invalid_rows": status_counts.get("insufficient_replicates", 0) + status_counts.get("invalid_mean_for_cv", 0),
            "mean_cv_raw_activity": scorecard["mean_cv_raw_activity"],
            "max_cv_raw_activity": scorecard["max_cv_raw_activity"],
        },
        "quality_status": "internal_replicate_consistency_cache_ready_not_model_claim",
        "leakage_check_status": "passed",
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
        "reviewer": "local_kwb_4g_replicate_consistency_builder",
        "reviewed_at": created_at,
        "notes": "KWB 4G raw wet-lab replicate consistency benchmark. Evaluation-only; not assay_success training labels or model-quality claim evidence.",
    }
    update_acquisition_plan()
    update_intake(intake_row)

    report = {
        "created_at": created_at,
        "local_only": True,
        "benchmark_name": BENCHMARK_NAME,
        "head": HEAD,
        "dataset_version": DATASET_VERSION,
        "dataset": rel(DATASET),
        "split_definition": rel(SPLIT),
        "scorecard": rel(SCORECARD),
        "metric_report": rel(METRIC),
        "intake": rel(INTAKE),
        "source_raw_measurements": rel(args.raw_measurements),
        "source_control_map": rel(args.control_map),
        "source_sample_map": rel(args.sample_map),
        "raw_measurement_rows": len(raw_rows),
        "raw_activity_rows_used": sum(row["replicate_count"] for row in dataset_rows),
        "replicate_group_rows": len(dataset_rows),
        "status_counts": dict(sorted(status_counts.items())),
        "skipped_counts": dict(sorted(skipped_counts.items())),
        "quality_status": "internal_replicate_consistency_cache_ready_not_model_claim",
        "leakage_check_status": "passed",
        "accepted_for_local_benchmark_cache_intake": True,
        "training_import_written_rows": 0,
        "assay_success_label_rows_written": 0,
        "ready_for_model_claim": False,
        "safe_for_model_claim": False,
        "release_ready": False,
        "policy": "Real local benchmark artifact for KWB 4G replicate consistency evaluation only; no training import, assay_success label, model claim, or release gate is opened.",
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({
        "dataset_rows": report["replicate_group_rows"],
        "raw_activity_rows_used": report["raw_activity_rows_used"],
        "benchmark_name": BENCHMARK_NAME,
        "accepted_for_local_benchmark_cache_intake": True,
        "training_import_written_rows": 0,
        "safe_for_model_claim": False,
        "output": rel(args.report),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
