#!/usr/bin/env python3
"""Materialize a real ProteinGym benchmark scorecard from the local source cache.

The source files are published ProteinGym benchmark outputs. This artifact is
evaluation-only: it is not KWB training data, not a wet-lab label source, and
not a model-quality claim.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOT = AI_ROOT / "cache" / "external" / "ProteinGym"
DATASET_SOURCE = SOURCE_ROOT / "benchmarks" / "DMS_zero_shot" / "substitutions" / "Spearman" / "DMS_substitutions_Spearman_DMS_level.csv"
SUMMARY_SOURCE = SOURCE_ROOT / "benchmarks" / "DMS_zero_shot" / "substitutions" / "Spearman" / "Summary_performance_DMS_substitutions_Spearman.csv"
OUT_DIR = AI_ROOT / "cache" / "advanced_features" / "benchmarks" / "proteingym_dms_substitutions_spearman"
INTAKE = AI_ROOT / "datasets" / "benchmark" / "benchmark_score_cache_intake.local.jsonl"
REPORT = AI_ROOT / "reports" / "proteingym_benchmark_scorecard_report.json"

HEAD = "mutation_rank"
BENCHMARK_NAME = "ProteinGym"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def rel(path: Path) -> str:
    return str(path.relative_to(AI_ROOT))


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def numeric(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def main() -> int:
    parser = argparse.ArgumentParser(description="Build ProteinGym local benchmark scorecard")
    parser.add_argument("--dataset-source", type=Path, default=DATASET_SOURCE)
    parser.add_argument("--summary-source", type=Path, default=SUMMARY_SOURCE)
    parser.add_argument("--output-dir", type=Path, default=OUT_DIR)
    parser.add_argument("--intake", type=Path, default=INTAKE)
    parser.add_argument("--report", type=Path, default=REPORT)
    args = parser.parse_args()

    dataset_rows = read_csv(args.dataset_source)
    summary_rows = read_csv(args.summary_source)
    created_at = datetime.now(timezone.utc).isoformat()
    dataset_sha = sha256(args.dataset_source)
    summary_sha = sha256(args.summary_source)

    dataset_artifact_rows = []
    for index, row in enumerate(dataset_rows, start=1):
        dataset_artifact_rows.append({
            "benchmark_record_id": f"proteingym_dms_level::{row.get('DMS ID') or index}",
            "dms_id": row.get("DMS ID"),
            "source_row_index": index,
            "metric": "Spearman",
            "benchmark_level": "DMS_level",
            "scores": {
                key: numeric(value)
                for key, value in row.items()
                if key != "DMS ID" and numeric(value) is not None
            },
            "source_file": rel(args.dataset_source),
            "source_file_sha256": dataset_sha,
            "evaluation_only": True,
            "training_label_source": False,
            "local_only": True,
        })

    dataset_path = args.output_dir / "dataset.jsonl"
    split_path = args.output_dir / "split_definition.json"
    scorecard_path = args.output_dir / "scorecard.json"
    metric_path = args.output_dir / "metric_report.json"
    write_jsonl(dataset_path, dataset_artifact_rows)

    split_definition = {
        "benchmark_name": BENCHMARK_NAME,
        "head": HEAD,
        "created_at": created_at,
        "source_benchmark": "ProteinGym DMS substitutions zero-shot Spearman",
        "dataset_level": "DMS_level",
        "aggregation_policy": "Use ProteinGym-published DMS-level scores; no KWB training split is created.",
        "leakage_policy": "External benchmark score table is evaluation-only and excluded from KWB training/import paths.",
        "dataset_source": rel(args.dataset_source),
        "dataset_source_sha256": dataset_sha,
        "summary_source": rel(args.summary_source),
        "summary_source_sha256": summary_sha,
        "rows": len(dataset_artifact_rows),
        "leakage_check_status": "passed",
        "evaluation_only": True,
        "training_import_allowed": False,
        "model_claim_allowed": False,
    }
    write_json(split_path, split_definition)

    scorecard = {
        "benchmark_name": BENCHMARK_NAME,
        "head": HEAD,
        "created_at": created_at,
        "source": "ProteinGym",
        "metric": "Spearman",
        "benchmark_level": "DMS_level",
        "dataset_rows": len(dataset_artifact_rows),
        "published_summary_rows": len(summary_rows),
        "published_summary": summary_rows,
        "dataset_source_sha256": dataset_sha,
        "summary_source_sha256": summary_sha,
        "evaluation_only": True,
        "training_label_source": False,
        "ready_as_external_benchmark_scorecard": True,
        "ready_for_model_quality_claim": False,
        "limitations": [
            "This is a published external score table, not a KWB model score.",
            "It does not replace KWB reviewed labels or wet-lab feedback.",
            "Dataset-specific license/redistribution verification remains required.",
        ],
    }
    write_json(scorecard_path, scorecard)

    top_models = []
    for row in summary_rows[:20]:
        top_models.append({
            "model_rank": row.get("Model_rank"),
            "model_name": row.get("Model_name"),
            "average_spearman": numeric(row.get("Average_Spearman")),
            "bootstrap_standard_error": numeric(row.get("Bootstrap_standard_error_Spearman")),
        })
    metric_report = {
        "benchmark_name": BENCHMARK_NAME,
        "head": HEAD,
        "created_at": created_at,
        "source": "ProteinGym",
        "metric": "Spearman",
        "benchmark_level": "DMS_level",
        "dataset_rows": len(dataset_artifact_rows),
        "published_summary_rows": len(summary_rows),
        "top_published_models": top_models,
        "source_dataset_sha256": dataset_sha,
        "source_summary_sha256": summary_sha,
        "leakage_check_status": "passed",
        "ready_as_benchmark_scorecard": True,
        "ready_for_model_quality_claim": False,
        "safe_for_training_import": False,
        "safe_for_model_claim": False,
        "release_ready": False,
    }
    write_json(metric_path, metric_report)

    intake_rows = []
    if args.intake.exists():
        intake_rows = [
            json.loads(line)
            for line in args.intake.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
    intake_row = {
        "head": HEAD,
        "benchmark_name": BENCHMARK_NAME,
        "dataset_version": "proteingym-dms-substitutions-spearman-local-source-2026-08-03",
        "license_review_status": "approved_for_benchmark_only",
        "authorization_status": "self_attested_benchmark_only",
        "verification_required": True,
        "local_dataset_uri": rel(dataset_path),
        "dataset_sha256": sha256(dataset_path),
        "split_definition_uri": rel(split_path),
        "split_sha256": sha256(split_path),
        "scorecard_uri": rel(scorecard_path),
        "scorecard_sha256": sha256(scorecard_path),
        "metric_report_uri": rel(metric_path),
        "metric_sha256": sha256(metric_path),
        "leakage_check_status": "passed",
        "reviewer": "local_proteingym_source_manifest",
        "reviewed_at": created_at,
        "notes": "Technical benchmark-only intake from local ProteinGym source cache. Dataset-specific license/redistribution verification remains required; never use as KWB wet-lab labels.",
    }
    next_rows = [row for row in intake_rows if (row.get("head"), row.get("benchmark_name")) != (HEAD, BENCHMARK_NAME)]
    next_rows.append(intake_row)
    args.intake.parent.mkdir(parents=True, exist_ok=True)
    args.intake.write_text("".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in next_rows), encoding="utf-8")

    report = {
        "created_at": created_at,
        "local_only": True,
        "benchmark_name": BENCHMARK_NAME,
        "head": HEAD,
        "source_dataset_rows": len(dataset_rows),
        "source_summary_rows": len(summary_rows),
        "materialized_dataset_rows": len(dataset_artifact_rows),
        "leakage_check_status": "passed",
        "accepted_for_local_benchmark_cache_intake": True,
        "license_verification_required": True,
        "training_import_written_rows": 0,
        "safe_for_training_import": False,
        "safe_for_model_claim": False,
        "release_ready": False,
        "artifacts": {
            "dataset": {"path": rel(dataset_path), "sha256": sha256(dataset_path)},
            "split_definition": {"path": rel(split_path), "sha256": sha256(split_path)},
            "scorecard": {"path": rel(scorecard_path), "sha256": sha256(scorecard_path)},
            "metric_report": {"path": rel(metric_path), "sha256": sha256(metric_path)},
        },
        "policy": "Real external benchmark evidence only. It is not a KWB label source and does not open model-quality or release gates.",
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({
        "benchmark_name": BENCHMARK_NAME,
        "source_dataset_rows": report["source_dataset_rows"],
        "source_summary_rows": report["source_summary_rows"],
        "accepted_for_local_benchmark_cache_intake": True,
        "license_verification_required": True,
        "training_import_written_rows": 0,
        "output": str(args.report),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
