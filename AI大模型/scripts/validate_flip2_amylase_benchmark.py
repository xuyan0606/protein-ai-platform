#!/usr/bin/env python3
"""Validate the evaluation-only FLIP2 amylase mutation-rank benchmark cache."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
SOURCE = AI_ROOT / "cache" / "external" / "flip2_amylase_by_mutation.csv.gz"
BENCH_DIR = AI_ROOT / "cache" / "advanced_features" / "benchmarks" / "flip2_amylase_by_mutation"
DATASET = BENCH_DIR / "dataset.jsonl"
SPLIT = BENCH_DIR / "split_definition.json"
SCORECARD = BENCH_DIR / "scorecard.json"
METRIC = BENCH_DIR / "metric_report.json"
REPORT = AI_ROOT / "reports" / "flip2_amylase_benchmark_report.json"
INTAKE = AI_ROOT / "datasets" / "benchmark" / "benchmark_score_cache_intake.local.jsonl"
OUT = AI_ROOT / "reports" / "flip2_amylase_benchmark_validation_report.json"

HEAD = "mutation_rank"
BENCHMARK_NAME = "FLIP/FLIP2-style protein/family/time split"
FALSE_FIELDS = ("training_label_source", "ready_for_training_import", "safe_for_training_import", "safe_for_model_claim", "release_ready")


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


def gzip_readable(path: Path) -> bool:
    try:
        with gzip.open(path, "rt", encoding="utf-8") as handle:
            handle.readline()
        return True
    except OSError:
        return False


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate FLIP2 amylase benchmark")
    parser.add_argument("--output", type=Path, default=OUT)
    args = parser.parse_args()

    dataset = load_jsonl(DATASET)
    split = load_json(SPLIT)
    scorecard = load_json(SCORECARD)
    metric = load_json(METRIC)
    report = load_json(REPORT)
    intake = find_intake(load_jsonl(INTAKE))
    failures: list[dict[str, Any]] = []

    fail_if(not SOURCE.exists(), failures, "source_exists", str(SOURCE), "present")
    if SOURCE.exists():
        fail_if(not gzip_readable(SOURCE), failures, "source_gzip_readable", False, True)
    fail_if(len(dataset) < 1000, failures, "dataset_rows_minimum", len(dataset), ">=1000")
    ids = {row.get("benchmark_record_id") for row in dataset}
    fail_if(len(ids) != len(dataset), failures, "record_ids_unique", len(ids), len(dataset))
    splits = {str(row.get("evaluation_split")) for row in dataset}
    fail_if("train" not in splits or "test" not in splits, failures, "train_test_splits_present", sorted(splits), "contains train and test")
    for idx, row in enumerate(dataset, start=1):
        fail_if(row.get("head") != HEAD, failures, "row_head", {"row": idx, "value": row.get("head")}, HEAD)
        fail_if(row.get("benchmark_name") != BENCHMARK_NAME, failures, "row_benchmark_name", {"row": idx, "value": row.get("benchmark_name")}, BENCHMARK_NAME)
        fail_if(row.get("benchmark_scope") != "external_mutation_rank_eval_only", failures, "row_scope", {"row": idx, "value": row.get("benchmark_scope")}, "external_mutation_rank_eval_only")
        fail_if(not isinstance(row.get("sequence_length"), int) or row.get("sequence_length") <= 0, failures, "row_sequence_length_positive", {"row": idx, "value": row.get("sequence_length")}, "positive int")
        fail_if(not finite(row.get("target")), failures, "row_target_finite", {"row": idx, "value": row.get("target")}, "finite target")
        fail_if(row.get("evaluation_split") not in {"train", "test", "validation"}, failures, "row_evaluation_split_allowed", {"row": idx, "value": row.get("evaluation_split")}, "train/test/validation")
        for field in FALSE_FIELDS:
            fail_if(row.get(field) is not False, failures, f"row_{field}_false", {"row": idx, "value": row.get(field)}, False)

    fail_if(split.get("split_strategy") != "use_published_flip2_amylase_by_mutation_split", failures, "split_strategy", split.get("split_strategy"), "use_published_flip2_amylase_by_mutation_split")
    fail_if(split.get("leakage_check_status") != "passed", failures, "split_leakage_check_status", split.get("leakage_check_status"), "passed")
    fail_if(split.get("train_rows", 0) <= 0 or split.get("test_rows", 0) <= 0, failures, "split_train_test_rows_positive", {"train": split.get("train_rows"), "test": split.get("test_rows")}, "positive train/test")
    fail_if(metric.get("ready_as_benchmark_scorecard") is not True, failures, "metric_ready_as_benchmark_scorecard", metric.get("ready_as_benchmark_scorecard"), True)
    fail_if(metric.get("dataset_rows") != len(dataset), failures, "metric_dataset_rows", metric.get("dataset_rows"), len(dataset))
    fail_if(scorecard.get("rows_scored") != len(dataset), failures, "scorecard_rows_scored", scorecard.get("rows_scored"), len(dataset))
    fail_if(report.get("dataset_rows") != len(dataset), failures, "report_dataset_rows", report.get("dataset_rows"), len(dataset))
    if SOURCE.exists():
        fail_if(report.get("source_file_sha256") != sha256(SOURCE), failures, "report_source_sha256", report.get("source_file_sha256"), sha256(SOURCE))
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
        "split_counts": split.get("split_counts"),
        "success": not failures,
        "failures": failures,
        "ready_as_benchmark_scorecard": not failures,
        "training_import_written_rows": 0,
        "ready_for_model_claim": False,
        "safe_for_model_claim": False,
        "release_ready": False,
        "policy": "Evaluation-only FLIP2 amylase mutation-rank benchmark. It does not create KWB labels, model claims, or release readiness.",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(validation, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({
        "success": validation["success"],
        "dataset_rows": validation["dataset_rows"],
        "split_counts": validation["split_counts"],
        "failures": len(failures),
        "output": str(args.output),
    }, ensure_ascii=False))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
