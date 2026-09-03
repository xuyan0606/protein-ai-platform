#!/usr/bin/env python3
"""Validate the evaluation-only KWB 4G activity-risk plate feedback benchmark."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
BENCH_DIR = AI_ROOT / "cache" / "advanced_features" / "benchmarks" / "kwb_4g_activity_risk_plate_feedback"
DATASET = BENCH_DIR / "dataset.jsonl"
SPLIT = BENCH_DIR / "split_definition.json"
SCORECARD = BENCH_DIR / "scorecard.json"
METRIC = BENCH_DIR / "metric_report.json"
REPORT = AI_ROOT / "reports" / "kwb_activity_risk_plate_feedback_benchmark_report.json"
INTAKE = AI_ROOT / "datasets" / "benchmark" / "benchmark_score_cache_intake.local.jsonl"
OUT = AI_ROOT / "reports" / "kwb_activity_risk_plate_feedback_benchmark_validation_report.json"

HEAD = "activity_risk"
BENCHMARK_NAME = "KWB plate-level wet-lab feedback"
ALLOWED_LABELS = {"low_activity_risk", "watch_activity_risk", "high_activity_risk"}
FALSE_FIELDS = (
    "training_label_source",
    "activity_risk_training_label_source",
    "ready_for_training_import",
    "safe_for_training_import",
    "safe_for_model_claim",
    "release_ready",
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


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def finite_number(value: Any) -> bool:
    try:
        return math.isfinite(float(value))
    except (TypeError, ValueError):
        return False


def fail_if(condition: bool, failures: list[dict[str, Any]], check: str, observed: Any, expected: Any) -> None:
    if condition:
        failures.append({"check": check, "observed": observed, "expected": expected})


def find_intake(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return next((row for row in rows if row.get("head") == HEAD and row.get("benchmark_name") == BENCHMARK_NAME), {})


def expected_label(ratio: float) -> str:
    if ratio >= 1.0:
        return "low_activity_risk"
    if ratio >= 0.8:
        return "watch_activity_risk"
    return "high_activity_risk"


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate KWB activity-risk plate feedback benchmark")
    parser.add_argument("--output", type=Path, default=OUT)
    args = parser.parse_args()

    dataset = load_jsonl(DATASET)
    split = load_json(SPLIT)
    scorecard = load_json(SCORECARD)
    metric = load_json(METRIC)
    report = load_json(REPORT)
    intake = find_intake(load_jsonl(INTAKE))
    failures: list[dict[str, Any]] = []

    fail_if(len(dataset) < 10, failures, "dataset_rows_minimum", len(dataset), ">=10")
    ids = {row.get("benchmark_record_id") for row in dataset}
    fail_if(len(ids) != len(dataset), failures, "record_ids_unique", len(ids), len(dataset))
    labels = Counter()
    for idx, row in enumerate(dataset, start=1):
        fail_if(row.get("head") != HEAD, failures, "row_head", {"row": idx, "value": row.get("head")}, HEAD)
        fail_if(row.get("benchmark_name") != BENCHMARK_NAME, failures, "row_benchmark_name", {"row": idx, "value": row.get("benchmark_name")}, BENCHMARK_NAME)
        fail_if(row.get("benchmark_scope") != "internal_wet_lab_activity_risk_plate_feedback_eval_only", failures, "row_scope", {"row": idx, "value": row.get("benchmark_scope")}, "internal_wet_lab_activity_risk_plate_feedback_eval_only")
        fail_if(not row.get("sample_id") or not row.get("control_sample_id"), failures, "row_sample_and_control_present", {"row": idx, "sample": row.get("sample_id"), "control": row.get("control_sample_id")}, "both present")
        fail_if(row.get("sample_id") == row.get("control_sample_id"), failures, "row_control_differs_from_variant", {"row": idx, "sample": row.get("sample_id")}, "different control")
        fail_if(not isinstance(row.get("variant_replicate_count"), int) or row.get("variant_replicate_count") <= 0, failures, "row_variant_replicates_positive", {"row": idx, "value": row.get("variant_replicate_count")}, "positive int")
        fail_if(not isinstance(row.get("control_replicate_count"), int) or row.get("control_replicate_count") <= 0, failures, "row_control_replicates_positive", {"row": idx, "value": row.get("control_replicate_count")}, "positive int")
        fail_if(not finite_number(row.get("variant_mean_activity")) or float(row.get("variant_mean_activity")) < 0, failures, "row_variant_mean_finite_nonnegative", {"row": idx, "value": row.get("variant_mean_activity")}, "finite non-negative")
        fail_if(not finite_number(row.get("control_mean_activity")) or float(row.get("control_mean_activity")) <= 0, failures, "row_control_mean_finite_positive", {"row": idx, "value": row.get("control_mean_activity")}, "finite positive")
        fail_if(not finite_number(row.get("activity_relative_to_batch_control")) or float(row.get("activity_relative_to_batch_control")) < 0, failures, "row_activity_ratio_finite_nonnegative", {"row": idx, "value": row.get("activity_relative_to_batch_control")}, "finite non-negative")
        if finite_number(row.get("activity_relative_to_batch_control")):
            ratio = float(row["activity_relative_to_batch_control"])
            fail_if(row.get("activity_risk_label") != expected_label(ratio), failures, "row_activity_risk_label_matches_ratio", {"row": idx, "label": row.get("activity_risk_label"), "ratio": ratio}, expected_label(ratio))
        fail_if(row.get("activity_risk_label") not in ALLOWED_LABELS, failures, "row_activity_risk_label_allowed", {"row": idx, "value": row.get("activity_risk_label")}, sorted(ALLOWED_LABELS))
        labels.update([str(row.get("activity_risk_label"))])
        for field in FALSE_FIELDS:
            fail_if(row.get(field) is not False, failures, f"row_{field}_false", {"row": idx, "value": row.get(field)}, False)

    fail_if(split.get("split_strategy") != "evaluation_only_batch_control_activity_ratio_no_training", failures, "split_strategy", split.get("split_strategy"), "evaluation_only_batch_control_activity_ratio_no_training")
    fail_if(split.get("leakage_check_status") != "passed", failures, "split_leakage_check_status", split.get("leakage_check_status"), "passed")
    fail_if(split.get("train_rows") != 0 or split.get("validation_rows") != 0, failures, "split_no_training_rows", {"train": split.get("train_rows"), "validation": split.get("validation_rows")}, {"train": 0, "validation": 0})
    fail_if(metric.get("ready_as_benchmark_scorecard") is not True, failures, "metric_ready_as_benchmark_scorecard", metric.get("ready_as_benchmark_scorecard"), True)
    fail_if(metric.get("dataset_rows") != len(dataset), failures, "metric_dataset_rows", metric.get("dataset_rows"), len(dataset))
    fail_if(scorecard.get("rows_scored") != len(dataset), failures, "scorecard_rows_scored", scorecard.get("rows_scored"), len(dataset))
    fail_if(report.get("dataset_rows") != len(dataset), failures, "report_dataset_rows", report.get("dataset_rows"), len(dataset))
    fail_if(set(labels) - ALLOWED_LABELS, failures, "label_counts_allowed", sorted(labels), sorted(ALLOWED_LABELS))
    fail_if(len(labels) < 2, failures, "label_diversity_minimum", dict(labels), "at least 2 activity_risk labels")
    for source in (split, scorecard, metric, report):
        for field in ("ready_for_model_claim", "safe_for_model_claim", "release_ready"):
            fail_if(source.get(field) is not False, failures, f"{field}_false", source.get(field), False)

    fail_if(not intake, failures, "intake_row_present", None, "present")
    if intake:
        expected_hashes = {
            "dataset_sha256": sha256(DATASET),
            "split_sha256": sha256(SPLIT),
            "scorecard_sha256": sha256(SCORECARD),
            "metric_sha256": sha256(METRIC),
        }
        for key, expected in expected_hashes.items():
            fail_if(str(intake.get(key) or "").lower() != expected, failures, f"intake_{key}", intake.get(key), expected)
        fail_if(intake.get("license_review_status") != "approved_for_benchmark_only", failures, "intake_license_review_status", intake.get("license_review_status"), "approved_for_benchmark_only")
        fail_if(intake.get("leakage_check_status") != "passed", failures, "intake_leakage_check_status", intake.get("leakage_check_status"), "passed")

    validation = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "local_only": True,
        "benchmark_name": BENCHMARK_NAME,
        "head": HEAD,
        "dataset_rows": len(dataset),
        "label_counts": dict(sorted(labels.items())),
        "success": not failures,
        "failures": failures,
        "ready_as_benchmark_scorecard": not failures,
        "training_import_written_rows": 0,
        "activity_risk_training_label_rows_written": 0,
        "ready_for_model_claim": False,
        "safe_for_model_claim": False,
        "release_ready": False,
        "policy": "Evaluation-only batch-control activity-ratio benchmark. It does not create training labels, model claims, or release readiness.",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(validation, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({
        "success": validation["success"],
        "dataset_rows": validation["dataset_rows"],
        "label_counts": validation["label_counts"],
        "failures": len(failures),
        "output": str(args.output),
    }, ensure_ascii=False))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
