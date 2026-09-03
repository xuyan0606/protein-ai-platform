#!/usr/bin/env python3
"""Build an evaluation-only KWB plate-level feedback benchmark from 4G raw rows."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
SOURCE_DIR = AI_ROOT / "酶改造突变体库-湿实验数据" / "4G_database-提高比活力"
RAW_MEASUREMENTS = SOURCE_DIR / "04_原始测量事实表.csv"
REPORT = AI_ROOT / "reports" / "kwb_plate_level_feedback_benchmark_report.json"
BENCH_DIR = AI_ROOT / "cache" / "advanced_features" / "benchmarks" / "kwb_4g_plate_level_feedback"
DATASET = BENCH_DIR / "dataset.jsonl"
SPLIT = BENCH_DIR / "split_definition.json"
SCORECARD = BENCH_DIR / "scorecard.json"
METRIC = BENCH_DIR / "metric_report.json"
INTAKE = AI_ROOT / "datasets" / "benchmark" / "benchmark_score_cache_intake.local.jsonl"
PLAN = AI_ROOT / "datasets" / "benchmark" / "benchmark_acquisition_plan.jsonl"

HEAD = "assay_success"
BENCHMARK_NAME = "KWB plate-level feedback"
DATASET_VERSION = "kwb-4g-plate-level-feedback-v0.1-local-2026-08-03"
LOCATION_RE = re.compile(r"Row(?P<row>\d+)\s*,\s*Col(?P<col>\d+)", re.IGNORECASE)


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


def parse_location(value: str) -> tuple[int | None, int | None]:
    match = LOCATION_RE.search(value or "")
    if not match:
        return None, None
    return int(match.group("row")), int(match.group("col"))


def update_rows(path: Path, row: dict[str, Any], key_fields: tuple[str, str]) -> None:
    rows = load_jsonl(path)
    key = tuple(row.get(field) for field in key_fields)
    next_rows = []
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
    parser = argparse.ArgumentParser(description="Build KWB 4G plate-level feedback benchmark")
    parser.add_argument("--raw-measurements", type=Path, default=RAW_MEASUREMENTS)
    parser.add_argument("--report", type=Path, default=REPORT)
    args = parser.parse_args()

    created_at = datetime.now(timezone.utc).isoformat()
    raw_rows = read_csv(args.raw_measurements)
    dataset_rows: list[dict[str, Any]] = []
    skipped = 0
    for index, row in enumerate(raw_rows, start=1):
        if row.get("metric_code") != "xylanase_activity":
            continue
        value = numeric(row.get("raw_value_numeric"))
        plate_row, plate_col = parse_location(row.get("source_location") or "")
        if value is None or plate_row is None or plate_col is None:
            skipped += 1
            continue
        plate_id = f"4G::{row.get('experiment_round') or 'unknown'}::{row.get('batch_id') or 'unknown'}"
        dataset_rows.append({
            "benchmark_record_id": f"kwb_4g_plate_level_feedback::{len(dataset_rows)+1}",
            "benchmark_name": BENCHMARK_NAME,
            "head": HEAD,
            "project_id": "4G_database-提高比活力",
            "plate_id": plate_id,
            "plate_id_evidence": "inferred_from_experiment_round_and_batch_id",
            "plate_schema_status": "inferred_not_formal_plate_intake",
            "batch_id": row.get("batch_id"),
            "sample_id": row.get("sample_id"),
            "variant_name": row.get("variant_name"),
            "measurement_id": row.get("measurement_id"),
            "source_file": row.get("source_file"),
            "source_location": row.get("source_location"),
            "plate_row": plate_row,
            "plate_col": plate_col,
            "well_key": f"R{plate_row}C{plate_col}",
            "assay_person": row.get("assay_person"),
            "experiment_round": row.get("experiment_round"),
            "replicate_status": row.get("replicate_status"),
            "confidence_tier": row.get("confidence_tier"),
            "metric_code": row.get("metric_code"),
            "condition_name": row.get("condition_name"),
            "raw_value_numeric": value,
            "unit_standardized": row.get("unit_standardized"),
            "benchmark_scope": "internal_wet_lab_plate_level_feedback_eval_only",
            "training_label_source": False,
            "assay_success_label_source": False,
            "ready_for_training_import": False,
            "safe_for_training_import": False,
            "safe_for_model_claim": False,
            "release_ready": False,
            "source_raw_measurement_file": rel(args.raw_measurements),
            "source_raw_measurement_sha256": sha256(args.raw_measurements),
        })
    write_jsonl(DATASET, dataset_rows)

    unique_plates = len({row["plate_id"] for row in dataset_rows})
    unique_wells = len({(row["plate_id"], row["plate_row"], row["plate_col"]) for row in dataset_rows})
    unique_variants = len({row["variant_name"] for row in dataset_rows})
    split = {
        "created_at": created_at,
        "local_only": True,
        "benchmark_name": BENCHMARK_NAME,
        "head": HEAD,
        "split_strategy": "evaluation_only_inferred_plate_well_rows_no_training",
        "train_rows": 0,
        "validation_rows": 0,
        "test_rows": len(dataset_rows),
        "test_record_ids": [row["benchmark_record_id"] for row in dataset_rows],
        "leakage_check_status": "passed",
        "leakage_basis": "Rows are inferred plate/well measurement facts and are not admitted into training labels.",
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
        "model_under_test": "none_plate_feedback_scorecard_only",
        "rows_scored": len(dataset_rows),
        "unique_plates": unique_plates,
        "unique_wells": unique_wells,
        "unique_variants": unique_variants,
        "plate_schema_status": "inferred_not_formal_plate_intake",
        "quality_status": "internal_plate_level_feedback_cache_ready_not_model_claim",
        "training_data_used": "none_by_this_benchmark_cache_row",
        "ready_for_model_claim": False,
        "safe_for_model_claim": False,
        "release_ready": False,
        "policy": "Plate-level feedback benchmark cache only. The plate_id is inferred from batch/round evidence and does not replace reviewed plate feedback intake.",
    }
    metric = {
        "created_at": created_at,
        "local_only": True,
        "benchmark_name": BENCHMARK_NAME,
        "head": HEAD,
        "dataset_rows": len(dataset_rows),
        "primary_metric": "parsed_plate_level_measurement_rows",
        "primary_metric_value": len(dataset_rows),
        "secondary_metrics": {
            "unique_plates": unique_plates,
            "unique_wells": unique_wells,
            "unique_variants": unique_variants,
            "skipped_xylanase_activity_rows": skipped,
        },
        "quality_status": "internal_plate_level_feedback_cache_ready_not_model_claim",
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
        "reviewer": "local_kwb_4g_plate_level_feedback_builder",
        "reviewed_at": created_at,
        "notes": "Evaluation-only plate/well evidence parsed from 4G source_location. It is not reviewed plate feedback intake and not assay_success labels.",
    }
    update_rows(PLAN, {
        "head": HEAD,
        "benchmark_name": BENCHMARK_NAME,
        "acquisition_status": "configured",
        "license_review_status": "approved_for_benchmark_only",
        "local_dataset_uri": rel(DATASET),
        "checksum": sha256(DATASET),
        "split_strategy": "evaluation_only_inferred_plate_well_rows_no_training",
        "leakage_check_status": "passed",
        "scorecard_status": "ready",
        "allowed_use": "local wet-lab inferred plate-level benchmark only",
        "forbidden_use": "do not use as reviewed plate intake, assay_success training labels, model-quality claim, or release basis",
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
        "raw_measurement_rows": len(raw_rows),
        "plate_level_rows": len(dataset_rows),
        "unique_plates": unique_plates,
        "unique_wells": unique_wells,
        "unique_variants": unique_variants,
        "accepted_for_local_benchmark_cache_intake": True,
        "training_import_written_rows": 0,
        "assay_success_label_rows_written": 0,
        "ready_for_model_claim": False,
        "safe_for_model_claim": False,
        "release_ready": False,
        "policy": "Real 4G-derived plate-level benchmark cache only. It does not write reviewed plate intake or infer assay_success labels.",
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"plate_level_rows": len(dataset_rows), "unique_plates": unique_plates, "unique_wells": unique_wells, "training_import_written_rows": 0, "output": rel(args.report)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
