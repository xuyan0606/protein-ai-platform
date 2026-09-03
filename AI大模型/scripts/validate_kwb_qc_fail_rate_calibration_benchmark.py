#!/usr/bin/env python3
"""Validate the evaluation-only 4G QC fail-rate calibration benchmark."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
BENCH_DIR = AI_ROOT / "cache" / "advanced_features" / "benchmarks" / "kwb_qc_fail_rate_calibration"
DATASET = BENCH_DIR / "dataset.jsonl"
SPLIT = BENCH_DIR / "split_definition.json"
SCORECARD = BENCH_DIR / "scorecard.json"
METRIC = BENCH_DIR / "metric_report.json"
REPORT = AI_ROOT / "reports" / "kwb_qc_fail_rate_calibration_benchmark_report.json"
INTAKE = AI_ROOT / "datasets" / "benchmark" / "benchmark_score_cache_intake.local.jsonl"
OUT = AI_ROOT / "reports" / "kwb_qc_fail_rate_calibration_benchmark_validation_report.json"
HEAD = "assay_success"
BENCHMARK_NAME = "QC fail-rate calibration"


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    value = json.loads(path.read_text(encoding="utf-8"))
    return value if isinstance(value, dict) else {}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def finite(value: Any) -> bool:
    try:
        return math.isfinite(float(value))
    except (TypeError, ValueError):
        return False


def fail_if(condition: bool, failures: list[dict[str, Any]], check: str, observed: Any, expected: Any) -> None:
    if condition:
        failures.append({"check": check, "observed": observed, "expected": expected})


def find_intake(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return next((row for row in rows if row.get("head") == HEAD and row.get("benchmark_name") == BENCHMARK_NAME), {})


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate KWB QC fail-rate calibration benchmark")
    parser.add_argument("--output", type=Path, default=OUT)
    args = parser.parse_args()

    dataset = load_jsonl(DATASET)
    split = load_json(SPLIT)
    scorecard = load_json(SCORECARD)
    metric = load_json(METRIC)
    report = load_json(REPORT)
    intake = find_intake(load_jsonl(INTAKE))
    failures: list[dict[str, Any]] = []

    fail_if(len(dataset) < 1, failures, "dataset_nonempty", len(dataset), ">=1")
    for index, row in enumerate(dataset, start=1):
        fail_if(row.get("head") != HEAD, failures, "row_head", {"row": index, "value": row.get("head")}, HEAD)
        fail_if(row.get("benchmark_name") != BENCHMARK_NAME, failures, "row_benchmark_name", {"row": index, "value": row.get("benchmark_name")}, BENCHMARK_NAME)
        fail_if(row.get("benchmark_scope") != "internal_wet_lab_qc_fail_rate_calibration_eval_only", failures, "row_scope", {"row": index, "value": row.get("benchmark_scope")}, "internal_wet_lab_qc_fail_rate_calibration_eval_only")
        for field in ("qc_fail_rate", "qc_insufficient_rate", "qc_nonpass_rate"):
            fail_if(not finite(row.get(field)), failures, f"row_{field}_finite", {"row": index, "value": row.get(field)}, "finite number")
        fail_if(not (0 <= float(row.get("qc_fail_rate")) <= 1), failures, "row_qc_fail_rate_range", row.get("qc_fail_rate"), "0..1")
        for field in ("training_label_source", "assay_success_label_source", "ready_for_training_import", "safe_for_training_import", "safe_for_model_claim", "release_ready"):
            fail_if(row.get(field) is not False, failures, f"row_{field}_false", {"row": index, "value": row.get(field)}, False)

    fail_if(split.get("split_strategy") != "evaluation_only_batch_grouped_no_training", failures, "split_strategy", split.get("split_strategy"), "evaluation_only_batch_grouped_no_training")
    fail_if(split.get("leakage_check_status") != "passed", failures, "split_leakage_check_status", split.get("leakage_check_status"), "passed")
    fail_if(split.get("train_rows") != 0 or split.get("validation_rows") != 0, failures, "split_no_train_validation", {"train": split.get("train_rows"), "validation": split.get("validation_rows")}, {"train": 0, "validation": 0})
    fail_if(split.get("future_training_exclusion_required") is not True, failures, "future_training_exclusion_required", split.get("future_training_exclusion_required"), True)
    fail_if(scorecard.get("quality_status") != "internal_qc_calibration_cache_ready_not_model_claim", failures, "scorecard_quality_status", scorecard.get("quality_status"), "internal_qc_calibration_cache_ready_not_model_claim")
    for field in ("aggregate_qc_fail_rate", "aggregate_qc_insufficient_rate"):
        fail_if(not finite(scorecard.get(field)), failures, f"scorecard_{field}_finite", scorecard.get(field), "finite number")
        if finite(scorecard.get(field)):
            fail_if(not 0 <= float(scorecard[field]) <= 1, failures, f"scorecard_{field}_range", scorecard[field], "0..1")
    fail_if(metric.get("ready_as_benchmark_scorecard") is not True, failures, "metric_ready_as_benchmark_scorecard", metric.get("ready_as_benchmark_scorecard"), True)
    fail_if(metric.get("dataset_rows") != len(dataset), failures, "metric_dataset_rows", metric.get("dataset_rows"), len(dataset))
    fail_if(report.get("batch_rows") != len(dataset), failures, "report_batch_rows", report.get("batch_rows"), len(dataset))
    for source in (split, scorecard, metric, report):
        for field in ("ready_for_model_claim", "safe_for_model_claim", "release_ready"):
            fail_if(source.get(field) is not False, failures, f"{field}_false", source.get(field), False)

    fail_if(not intake, failures, "intake_row_present", None, "present")
    if intake:
        expected = {
            "dataset_sha256": sha256(DATASET),
            "split_sha256": sha256(SPLIT),
            "scorecard_sha256": sha256(SCORECARD),
            "metric_sha256": sha256(METRIC),
        }
        for key, value in expected.items():
            fail_if(str(intake.get(key) or "").lower() != value, failures, f"intake_{key}", intake.get(key), value)
        fail_if(intake.get("license_review_status") != "approved_for_benchmark_only", failures, "intake_license_review_status", intake.get("license_review_status"), "approved_for_benchmark_only")
        fail_if(intake.get("leakage_check_status") != "passed", failures, "intake_leakage_check_status", intake.get("leakage_check_status"), "passed")

    validation = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "local_only": True,
        "benchmark_name": BENCHMARK_NAME,
        "dataset_rows": len(dataset),
        "raw_measurement_rows_used": int(report.get("raw_measurement_rows_used") or 0),
        "success": not failures,
        "failures": failures,
        "ready_as_benchmark_scorecard": not failures,
        "training_import_written_rows": 0,
        "assay_success_label_rows_written": 0,
        "ready_for_model_claim": False,
        "safe_for_model_claim": False,
        "release_ready": False,
        "policy": "Evaluation-only QC reliability benchmark. It does not infer assay_success labels or permit training/model/release claims.",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(validation, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"success": validation["success"], "dataset_rows": validation["dataset_rows"], "ready_as_benchmark_scorecard": validation["ready_as_benchmark_scorecard"], "failures": len(failures), "output": str(args.output)}, ensure_ascii=False))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
