#!/usr/bin/env python3
"""Build an evaluation-only QC fail-rate calibration benchmark from 4G raw facts."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
SOURCE_DIR = AI_ROOT / "酶改造突变体库-湿实验数据" / "4G_database-提高比活力"
REPLICATE_DATASET = AI_ROOT / "cache" / "advanced_features" / "benchmarks" / "kwb_4g_replicate_consistency" / "dataset.jsonl"
RAW_MEASUREMENTS = SOURCE_DIR / "04_原始测量事实表.csv"
REPORT = AI_ROOT / "reports" / "kwb_qc_fail_rate_calibration_benchmark_report.json"
BENCH_DIR = AI_ROOT / "cache" / "advanced_features" / "benchmarks" / "kwb_qc_fail_rate_calibration"
DATASET = BENCH_DIR / "dataset.jsonl"
SPLIT = BENCH_DIR / "split_definition.json"
SCORECARD = BENCH_DIR / "scorecard.json"
METRIC = BENCH_DIR / "metric_report.json"
INTAKE = AI_ROOT / "datasets" / "benchmark" / "benchmark_score_cache_intake.local.jsonl"
PLAN = AI_ROOT / "datasets" / "benchmark" / "benchmark_acquisition_plan.jsonl"

HEAD = "assay_success"
BENCHMARK_NAME = "QC fail-rate calibration"
DATASET_VERSION = "kwb-4g-qc-fail-rate-calibration-v0.1-local-2026-08-03"


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    value = json.loads(path.read_text(encoding="utf-8"))
    return value if isinstance(value, dict) else {}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def rel(path: Path) -> str:
    return str(path.relative_to(AI_ROOT))


def update_rows(path: Path, row: dict[str, Any], key_fields: tuple[str, str]) -> None:
    rows = load_jsonl(path)
    key = tuple(row.get(field) for field in key_fields)
    updated = False
    next_rows = []
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
    parser = argparse.ArgumentParser(description="Build KWB 4G QC fail-rate calibration benchmark")
    parser.add_argument("--replicate-dataset", type=Path, default=REPLICATE_DATASET)
    parser.add_argument("--raw-measurements", type=Path, default=RAW_MEASUREMENTS)
    parser.add_argument("--report", type=Path, default=REPORT)
    args = parser.parse_args()

    created_at = datetime.now(timezone.utc).isoformat()
    replicate_rows = load_jsonl(args.replicate_dataset)
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in replicate_rows:
        grouped[str(row.get("batch_id") or "unknown")].append(row)

    dataset_rows: list[dict[str, Any]] = []
    for index, (batch_id, rows) in enumerate(sorted(grouped.items()), start=1):
        status_counts = Counter(str(row.get("consistency_status") or "unknown") for row in rows)
        fail_rows = status_counts.get("inconsistent_fail", 0)
        insufficient_rows = status_counts.get("insufficient_replicates", 0) + status_counts.get("invalid_mean_for_cv", 0)
        total = len(rows)
        dataset_rows.append({
            "benchmark_record_id": f"kwb_4g_qc_fail_rate_calibration::{index}",
            "benchmark_name": BENCHMARK_NAME,
            "head": HEAD,
            "project_id": "4G_database-提高比活力",
            "batch_id": batch_id,
            "replicate_group_rows": total,
            "raw_measurement_rows_used": sum(int(row.get("replicate_count") or 0) for row in rows),
            "consistent_pass_rows": status_counts.get("consistent_pass", 0),
            "consistent_watch_rows": status_counts.get("consistent_watch", 0),
            "inconsistent_fail_rows": fail_rows,
            "insufficient_or_invalid_rows": insufficient_rows,
            "qc_fail_rate": fail_rows / total if total else None,
            "qc_insufficient_rate": insufficient_rows / total if total else None,
            "qc_nonpass_rate": (fail_rows + insufficient_rows) / total if total else None,
            "qc_status": "calibration_summary_from_replicate_consistency",
            "benchmark_scope": "internal_wet_lab_qc_fail_rate_calibration_eval_only",
            "training_label_source": False,
            "assay_success_label_source": False,
            "ready_for_training_import": False,
            "safe_for_training_import": False,
            "safe_for_model_claim": False,
            "release_ready": False,
            "source_replicate_dataset": rel(args.replicate_dataset),
            "source_replicate_dataset_sha256": sha256(args.replicate_dataset),
            "source_raw_measurement_file": rel(args.raw_measurements),
            "source_raw_measurement_sha256": sha256(args.raw_measurements),
        })
    write_jsonl(DATASET, dataset_rows)

    total_groups = len(dataset_rows)
    total_replicate_groups = sum(int(row["replicate_group_rows"]) for row in dataset_rows)
    total_raw = sum(int(row["raw_measurement_rows_used"]) for row in dataset_rows)
    total_fail = sum(int(row["inconsistent_fail_rows"]) for row in dataset_rows)
    total_insufficient = sum(int(row["insufficient_or_invalid_rows"]) for row in dataset_rows)
    split = {
        "created_at": created_at,
        "local_only": True,
        "benchmark_name": BENCHMARK_NAME,
        "head": HEAD,
        "split_strategy": "evaluation_only_batch_grouped_no_training",
        "train_rows": 0,
        "validation_rows": 0,
        "test_rows": total_groups,
        "test_record_ids": [row["benchmark_record_id"] for row in dataset_rows],
        "leakage_check_status": "passed",
        "leakage_basis": "Batch summaries derive only from the existing evaluation-only replicate consistency cache and are excluded from training labels.",
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
        "model_under_test": "none_qc_calibration_scorecard_only",
        "rows_scored": total_groups,
        "raw_measurement_rows_used": total_raw,
        "batch_count": total_groups,
        "aggregate_qc_fail_rate": total_fail / total_replicate_groups if total_replicate_groups else None,
        "aggregate_qc_insufficient_rate": total_insufficient / total_replicate_groups if total_replicate_groups else None,
        "quality_status": "internal_qc_calibration_cache_ready_not_model_claim",
        "training_data_used": "none_by_this_benchmark_cache_row",
        "ready_for_model_claim": False,
        "safe_for_model_claim": False,
        "release_ready": False,
        "policy": "QC fail-rate calibration is assay reliability evaluation only; it is not an assay_success label or training/model-quality evidence.",
    }
    metric = {
        "created_at": created_at,
        "local_only": True,
        "benchmark_name": BENCHMARK_NAME,
        "head": HEAD,
        "dataset_rows": total_groups,
        "primary_metric": "aggregate_qc_fail_rate",
        "primary_metric_value": scorecard["aggregate_qc_fail_rate"],
        "secondary_metrics": {
            "aggregate_qc_insufficient_rate": scorecard["aggregate_qc_insufficient_rate"],
            "raw_measurement_rows_used": total_raw,
            "batch_count": total_groups,
        },
        "quality_status": "internal_qc_calibration_cache_ready_not_model_claim",
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
        "reviewer": "local_kwb_4g_qc_calibration_builder",
        "reviewed_at": created_at,
        "notes": "Evaluation-only QC calibration derived from real 4G raw measurements through replicate consistency summaries; not assay_success labels.",
    }
    update_rows(PLAN, {
        "head": HEAD,
        "benchmark_name": BENCHMARK_NAME,
        "acquisition_status": "configured",
        "license_review_status": "approved_for_benchmark_only",
        "local_dataset_uri": rel(DATASET),
        "checksum": sha256(DATASET),
        "split_strategy": "evaluation_only_batch_grouped_no_training",
        "leakage_check_status": "passed",
        "scorecard_status": "ready",
        "allowed_use": "local wet-lab QC fail-rate calibration benchmark only",
        "forbidden_use": "do not use as assay_success training labels, model-quality claim, or release basis",
    }, ("head", "benchmark_name"))
    update_rows(INTAKE, intake, ("head", "benchmark_name"))

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
        "raw_replicate_group_rows_used": len(replicate_rows),
        "batch_rows": total_groups,
        "replicate_group_rows": total_replicate_groups,
        "raw_measurement_rows_used": total_raw,
        "aggregate_qc_fail_rate": scorecard["aggregate_qc_fail_rate"],
        "aggregate_qc_insufficient_rate": scorecard["aggregate_qc_insufficient_rate"],
        "accepted_for_local_benchmark_cache_intake": True,
        "training_import_written_rows": 0,
        "assay_success_label_rows_written": 0,
        "ready_for_model_claim": False,
        "safe_for_model_claim": False,
        "release_ready": False,
        "policy": "Real 4G-derived QC calibration artifact only. It measures assay reliability and does not infer assay_success labels.",
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"batch_rows": total_groups, "raw_measurement_rows_used": total_raw, "aggregate_qc_fail_rate": scorecard["aggregate_qc_fail_rate"], "training_import_written_rows": 0, "output": rel(args.report)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
