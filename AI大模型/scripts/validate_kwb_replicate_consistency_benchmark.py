#!/usr/bin/env python3
"""Validate KWB 4G replicate consistency benchmark artifacts."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
BENCH_DIR = AI_ROOT / "cache" / "advanced_features" / "benchmarks" / "kwb_4g_replicate_consistency"
DATASET = BENCH_DIR / "dataset.jsonl"
SPLIT = BENCH_DIR / "split_definition.json"
SCORECARD = BENCH_DIR / "scorecard.json"
METRIC = BENCH_DIR / "metric_report.json"
INTAKE = AI_ROOT / "datasets" / "benchmark" / "benchmark_score_cache_intake.local.jsonl"
REPORT = AI_ROOT / "reports" / "kwb_replicate_consistency_benchmark_report.json"
OUT = AI_ROOT / "reports" / "kwb_replicate_consistency_benchmark_validation_report.json"

HEAD = "assay_success"
BENCHMARK_NAME = "replicate consistency"
MIN_EXPECTED_ROWS = 10
MIN_EXPECTED_RAW_MEASUREMENTS = 100
ALLOWED_STATUSES = {
    "consistent_pass",
    "consistent_watch",
    "inconsistent_fail",
    "insufficient_replicates",
    "invalid_mean_for_cv",
}


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    value = json.loads(path.read_text(encoding="utf-8"))
    return value if isinstance(value, dict) else {}


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


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def rel(path: Path) -> str:
    return str(path.relative_to(AI_ROOT))


def as_float(value: Any) -> float | None:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if math.isfinite(result) else None


def fail_if(condition: bool, failures: list[dict[str, Any]], check: str, observed: Any, expected: Any) -> None:
    if condition:
        failures.append({"check": check, "observed": observed, "expected": expected})


def find_intake_row(rows: list[dict[str, Any]]) -> dict[str, Any]:
    for row in rows:
        if row.get("head") == HEAD and row.get("benchmark_name") == BENCHMARK_NAME:
            return row
    return {}


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate KWB 4G replicate consistency benchmark")
    parser.add_argument("--output", type=Path, default=OUT)
    args = parser.parse_args()

    dataset_rows = load_jsonl(DATASET)
    split = load_json(SPLIT)
    scorecard = load_json(SCORECARD)
    metric = load_json(METRIC)
    report = load_json(REPORT)
    intake_row = find_intake_row(load_jsonl(INTAKE))
    failures: list[dict[str, Any]] = []

    fail_if(len(dataset_rows) < MIN_EXPECTED_ROWS, failures, "dataset_rows_minimum", len(dataset_rows), f">={MIN_EXPECTED_ROWS}")
    fail_if(
        len({row.get("benchmark_record_id") for row in dataset_rows}) != len(dataset_rows),
        failures,
        "benchmark_record_ids_unique",
        len({row.get("benchmark_record_id") for row in dataset_rows}),
        len(dataset_rows),
    )
    raw_measurement_total = 0
    for idx, row in enumerate(dataset_rows, start=1):
        raw_measurement_total += int(row.get("replicate_count") or 0)
        fail_if(row.get("head") != HEAD, failures, "row_head", {"row": idx, "value": row.get("head")}, HEAD)
        fail_if(row.get("benchmark_name") != BENCHMARK_NAME, failures, "row_benchmark_name", {"row": idx, "value": row.get("benchmark_name")}, BENCHMARK_NAME)
        fail_if(row.get("benchmark_scope") != "internal_wet_lab_replicate_consistency_eval_only", failures, "row_scope", {"row": idx, "value": row.get("benchmark_scope")}, "internal_wet_lab_replicate_consistency_eval_only")
        fail_if(row.get("consistency_status") not in ALLOWED_STATUSES, failures, "row_consistency_status_allowed", {"row": idx, "value": row.get("consistency_status")}, sorted(ALLOWED_STATUSES))
        fail_if(int(row.get("replicate_count") or 0) < 1, failures, "row_replicate_count_positive", {"row": idx, "value": row.get("replicate_count")}, ">=1")
        fail_if(not isinstance(row.get("measurement_ids"), list) or len(row.get("measurement_ids") or []) != int(row.get("replicate_count") or 0), failures, "row_measurement_ids_match_replicates", {"row": idx, "measurement_ids": row.get("measurement_ids"), "replicate_count": row.get("replicate_count")}, "same length")
        fail_if(as_float(row.get("mean_raw_activity")) is None, failures, "row_mean_numeric", {"row": idx, "value": row.get("mean_raw_activity")}, "finite float")
        fail_if(as_float(row.get("sd_raw_activity")) is None, failures, "row_sd_numeric", {"row": idx, "value": row.get("sd_raw_activity")}, "finite float")
        if row.get("consistency_status") not in {"invalid_mean_for_cv", "insufficient_replicates"}:
            fail_if(as_float(row.get("cv_raw_activity")) is None, failures, "row_cv_numeric_when_valid_mean", {"row": idx, "value": row.get("cv_raw_activity")}, "finite float")
        for field in ("training_label_source", "assay_success_label_source", "ready_for_training_import", "safe_for_training_import", "safe_for_model_claim", "release_ready"):
            fail_if(row.get(field) is not False, failures, f"row_{field}_false", {"row": idx, "value": row.get(field)}, False)

    fail_if(raw_measurement_total < MIN_EXPECTED_RAW_MEASUREMENTS, failures, "raw_measurement_rows_used_minimum", raw_measurement_total, f">={MIN_EXPECTED_RAW_MEASUREMENTS}")
    fail_if(split.get("split_strategy") != "evaluation_only_grouped_raw_replicates_no_training", failures, "split_strategy", split.get("split_strategy"), "evaluation_only_grouped_raw_replicates_no_training")
    fail_if(split.get("leakage_check_status") != "passed", failures, "split_leakage_check_passed", split.get("leakage_check_status"), "passed")
    fail_if(split.get("train_rows") != 0, failures, "split_train_rows_zero", split.get("train_rows"), 0)
    fail_if(split.get("future_training_exclusion_required") is not True, failures, "future_training_exclusion_required", split.get("future_training_exclusion_required"), True)
    fail_if(scorecard.get("quality_status") != "internal_replicate_consistency_cache_ready_not_model_claim", failures, "scorecard_quality_status", scorecard.get("quality_status"), "internal_replicate_consistency_cache_ready_not_model_claim")
    fail_if(metric.get("quality_status") != "internal_replicate_consistency_cache_ready_not_model_claim", failures, "metric_quality_status", metric.get("quality_status"), "internal_replicate_consistency_cache_ready_not_model_claim")
    fail_if(metric.get("dataset_rows") != len(dataset_rows), failures, "metric_dataset_rows_match", metric.get("dataset_rows"), len(dataset_rows))
    fail_if(report.get("replicate_group_rows") != len(dataset_rows), failures, "report_dataset_rows_match", report.get("replicate_group_rows"), len(dataset_rows))
    fail_if(report.get("raw_activity_rows_used") != raw_measurement_total, failures, "report_raw_activity_rows_match", report.get("raw_activity_rows_used"), raw_measurement_total)
    fail_if(report.get("accepted_for_local_benchmark_cache_intake") is not True, failures, "report_accepted_for_intake_true", report.get("accepted_for_local_benchmark_cache_intake"), True)
    for source in (split, scorecard, metric, report):
        for field in ("ready_for_model_claim", "safe_for_model_claim", "release_ready"):
            fail_if(source.get(field) is not False, failures, f"{source.get('benchmark_name', 'report')}_{field}_false", source.get(field), False)

    fail_if(not intake_row, failures, "intake_row_present", None, "present")
    if intake_row:
        expected_hashes = {
            "dataset_sha256": sha256(DATASET),
            "split_sha256": sha256(SPLIT),
            "scorecard_sha256": sha256(SCORECARD),
            "metric_sha256": sha256(METRIC),
        }
        for key, expected in expected_hashes.items():
            fail_if(str(intake_row.get(key) or "").lower() != expected, failures, f"intake_{key}_matches", intake_row.get(key), expected)
        fail_if(intake_row.get("license_review_status") != "approved_for_benchmark_only", failures, "intake_license_review_status", intake_row.get("license_review_status"), "approved_for_benchmark_only")
        fail_if(intake_row.get("leakage_check_status") != "passed", failures, "intake_leakage_check_status", intake_row.get("leakage_check_status"), "passed")

    validation = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "local_only": True,
        "benchmark_name": BENCHMARK_NAME,
        "dataset": rel(DATASET),
        "split_definition": rel(SPLIT),
        "scorecard": rel(SCORECARD),
        "metric_report": rel(METRIC),
        "dataset_rows": len(dataset_rows),
        "raw_measurement_rows_used": raw_measurement_total,
        "quality_status": metric.get("quality_status"),
        "intake_row_present": bool(intake_row),
        "success": not failures,
        "failures": failures,
        "ready_for_model_claim": False,
        "safe_for_model_claim": False,
        "release_ready": False,
        "policy": "Evaluation-only replicate consistency benchmark. It validates local benchmark plumbing and assay repeatability summaries, not assay_success training labels or model quality.",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(validation, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({
        "success": validation["success"],
        "dataset_rows": validation["dataset_rows"],
        "raw_measurement_rows_used": validation["raw_measurement_rows_used"],
        "quality_status": validation["quality_status"],
        "failures": len(failures),
        "output": rel(args.output),
    }, ensure_ascii=False))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
