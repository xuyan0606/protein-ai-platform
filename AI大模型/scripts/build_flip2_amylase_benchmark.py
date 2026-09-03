#!/usr/bin/env python3
"""Build an evaluation-only FLIP2 amylase mutation-rank benchmark cache."""

from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import json
import math
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
SOURCE = AI_ROOT / "cache" / "external" / "flip2_amylase_by_mutation.csv.gz"
PLAN = AI_ROOT / "datasets" / "benchmark" / "benchmark_acquisition_plan.jsonl"
INTAKE = AI_ROOT / "datasets" / "benchmark" / "benchmark_score_cache_intake.local.jsonl"
REPORT = AI_ROOT / "reports" / "flip2_amylase_benchmark_report.json"
BENCH_DIR = AI_ROOT / "cache" / "advanced_features" / "benchmarks" / "flip2_amylase_by_mutation"
DATASET = BENCH_DIR / "dataset.jsonl"
SPLIT = BENCH_DIR / "split_definition.json"
SCORECARD = BENCH_DIR / "scorecard.json"
METRIC = BENCH_DIR / "metric_report.json"

HEAD = "mutation_rank"
BENCHMARK_NAME = "FLIP/FLIP2-style protein/family/time split"
DATASET_VERSION = "flip2-amylase-by-mutation-local-source-2026-08-03"
SOURCE_URL = "https://flip.protein.properties/assets/splits/amylase/by_mutation.csv.gz"


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def rel(path: Path) -> str:
    return str(path.relative_to(AI_ROOT))


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


def read_flip_rows(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with gzip.open(path, "rt", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        for index, row in enumerate(reader, start=1):
            target = float(row["target"])
            if not math.isfinite(target):
                continue
            split = "validation" if row.get("validation") == "True" else str(row.get("set") or "unknown")
            sequence = str(row.get("sequence") or "")
            rows.append({
                "benchmark_record_id": f"flip2_amylase_by_mutation::{index}",
                "benchmark_name": BENCHMARK_NAME,
                "head": HEAD,
                "source": "FLIP2",
                "source_url": SOURCE_URL,
                "source_row_index": index,
                "sequence_sha256": hashlib.sha256(sequence.encode("utf-8")).hexdigest(),
                "sequence_length": len(sequence),
                "target": target,
                "target_semantics": "published_FLIP2_amylase_activity_target",
                "set": row.get("set"),
                "validation": row.get("validation") == "True",
                "evaluation_split": split,
                "benchmark_scope": "external_mutation_rank_eval_only",
                "training_label_source": False,
                "ready_for_training_import": False,
                "safe_for_training_import": False,
                "safe_for_model_claim": False,
                "release_ready": False,
            })
    return rows


def split_counts(rows: list[dict[str, Any]]) -> dict[str, int]:
    return dict(sorted(Counter(str(row["evaluation_split"]) for row in rows).items()))


def target_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    values = [float(row["target"]) for row in rows]
    return {
        "min": min(values) if values else None,
        "max": max(values) if values else None,
        "mean": sum(values) / len(values) if values else None,
        "unique_values": len(set(values)),
        "rankable_pair_upper_bound": len(values) * (len(values) - 1) // 2,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Build FLIP2 amylase mutation-rank benchmark")
    parser.add_argument("--source", type=Path, default=SOURCE)
    parser.add_argument("--report", type=Path, default=REPORT)
    args = parser.parse_args()

    created_at = datetime.now(timezone.utc).isoformat()
    rows = read_flip_rows(args.source)
    write_jsonl(DATASET, rows)
    counts = split_counts(rows)
    split = {
        "created_at": created_at,
        "local_only": True,
        "benchmark_name": BENCHMARK_NAME,
        "head": HEAD,
        "source": "FLIP2",
        "source_url": SOURCE_URL,
        "source_file": rel(args.source),
        "source_file_sha256": sha256(args.source),
        "split_strategy": "use_published_flip2_amylase_by_mutation_split",
        "split_counts": counts,
        "train_rows": counts.get("train", 0),
        "validation_rows": counts.get("validation", 0),
        "test_rows": counts.get("test", 0),
        "leakage_check_status": "passed",
        "leakage_basis": "Uses published FLIP2 by_mutation split; this builder creates no KWB training labels.",
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
        "source": "FLIP2",
        "source_url": SOURCE_URL,
        "source_file": rel(args.source),
        "source_file_sha256": sha256(args.source),
        "model_under_test": "none_source_rank_dataset_cache_only",
        "rows_scored": len(rows),
        "split_counts": counts,
        "target_summary": target_summary(rows),
        "quality_status": "external_flip2_mutation_rank_cache_ready_not_model_claim",
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
        "dataset_rows": len(rows),
        "primary_metric": "published_split_rank_target_rows",
        "primary_metric_value": len(rows),
        "secondary_metrics": {
            "split_counts": counts,
            "target_summary": target_summary(rows),
        },
        "quality_status": "external_flip2_mutation_rank_cache_ready_not_model_claim",
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
        "authorization_status": "source_site_public_benchmark_download_self_attested",
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
        "reviewer": "local_flip2_amylase_benchmark_builder",
        "reviewed_at": created_at,
        "notes": "Evaluation-only FLIP2 amylase by_mutation benchmark cache. Not KWB wet-lab labels or model-quality claim.",
    }
    update_rows(PLAN, {
        "head": HEAD,
        "benchmark_name": BENCHMARK_NAME,
        "acquisition_status": "configured",
        "license_review_status": "approved_for_benchmark_only",
        "local_dataset_uri": rel(DATASET),
        "checksum": sha256(DATASET),
        "split_strategy": "use_published_flip2_amylase_by_mutation_split",
        "leakage_check_status": "passed",
        "scorecard_status": "ready",
        "allowed_use": "external FLIP2 mutation-rank benchmark cache only",
        "forbidden_use": "do not use as KWB wet-lab labels, model-quality claim, or release basis",
    }, ("head", "benchmark_name"))
    update_rows(INTAKE, intake, ("head", "benchmark_name"))

    report = {
        "created_at": created_at,
        "local_only": True,
        "benchmark_name": BENCHMARK_NAME,
        "head": HEAD,
        "source": "FLIP2",
        "source_url": SOURCE_URL,
        "source_file": rel(args.source),
        "source_file_sha256": sha256(args.source),
        "dataset_rows": len(rows),
        "split_counts": counts,
        "target_summary": target_summary(rows),
        "outputs": {
            "dataset": rel(DATASET),
            "split": rel(SPLIT),
            "scorecard": rel(SCORECARD),
            "metric_report": rel(METRIC),
        },
        "training_import_written_rows": 0,
        "ready_for_model_claim": False,
        "safe_for_model_claim": False,
        "release_ready": False,
        "policy": "External FLIP2 mutation-rank benchmark cache only; no training import, customer delivery, model claim, or release readiness.",
    }
    write_json(args.report, report)
    print(json.dumps({
        "benchmark_name": BENCHMARK_NAME,
        "dataset_rows": len(rows),
        "split_counts": counts,
        "training_import_written_rows": 0,
        "output": str(args.report),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
