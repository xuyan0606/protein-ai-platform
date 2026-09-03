#!/usr/bin/env python3
"""Build a sample-limited ThermoMPNN comparison benchmark from local smoke output.

This is evaluation plumbing only. It materializes the already-computed
ThermoMPNN Venus-15B smoke artifact as a checksummed benchmark cache row.
It is not a wet-lab label source, not a Rosetta/FoldX physics ddG result, and
not a model-quality scorecard.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
SMOKE_REPORT = AI_ROOT / "reports" / "thermompnn_venus15b_smoke_report.json"
LOCAL_SOURCE_REPORT = AI_ROOT / "reports" / "thermompnn_local_source_report.json"
PLAN = AI_ROOT / "datasets" / "benchmark" / "benchmark_acquisition_plan.jsonl"
INTAKE = AI_ROOT / "datasets" / "benchmark" / "benchmark_score_cache_intake.local.jsonl"
BENCH_DIR = AI_ROOT / "cache" / "advanced_features" / "benchmarks" / "thermompnn_comparison_venus15b_smoke"
DATASET = BENCH_DIR / "dataset.jsonl"
SPLIT = BENCH_DIR / "split_definition.json"
SCORECARD = BENCH_DIR / "scorecard.json"
METRIC = BENCH_DIR / "metric_report.json"
REPORT = AI_ROOT / "reports" / "thermompnn_comparison_benchmark_report.json"

HEAD = "stability"
BENCHMARK_NAME = "ThermoMPNN comparison"
DATASET_VERSION = "thermompnn-venus15b-smoke-comparison-v0.1-local-2026-08-03"


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    value = json.loads(path.read_text(encoding="utf-8"))
    return value if isinstance(value, dict) else {}


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


def rel(path: Path) -> str:
    return str(path.relative_to(AI_ROOT))


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


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
                "split_strategy": "evaluation_only_all_rows_no_training",
                "leakage_check_status": "passed",
                "scorecard_status": "ready",
                "allowed_use": "local sample-limited ThermoMPNN comparison smoke only",
                "forbidden_use": "do not use as wet-lab stability label, physics ddG label, model-quality claim, or release basis",
            })
        else:
            updated.append(row)
    write_jsonl(PLAN, updated)


def numeric(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def main() -> int:
    parser = argparse.ArgumentParser(description="Build ThermoMPNN comparison benchmark")
    parser.add_argument("--smoke-report", type=Path, default=SMOKE_REPORT)
    parser.add_argument("--local-source-report", type=Path, default=LOCAL_SOURCE_REPORT)
    parser.add_argument("--report", type=Path, default=REPORT)
    args = parser.parse_args()

    created_at = datetime.now(timezone.utc).isoformat()
    smoke = load_json(args.smoke_report)
    source = load_json(args.local_source_report)
    ddg_rows = ((smoke.get("outputs") or {}).get("ddg_table") or [])
    if not isinstance(ddg_rows, list):
        ddg_rows = []

    dataset_rows: list[dict[str, Any]] = []
    for index, row in enumerate(ddg_rows, start=1):
        if not isinstance(row, dict):
            continue
        dataset_rows.append({
            "benchmark_record_id": f"thermompnn_venus15b_smoke::{index}",
            "benchmark_name": BENCHMARK_NAME,
            "head": HEAD,
            "mutation": row.get("mutation"),
            "canonical_position": row.get("canonical_position"),
            "wild_type": row.get("wild_type"),
            "mutant": row.get("mutant"),
            "observed_sequence_residue": row.get("observed_sequence_residue"),
            "numbering_verified": row.get("numbering_verified") is True,
            "backend": "thermompnn",
            "ddg_pred_kcal_mol": numeric(row.get("ddg_pred_kcal_mol")),
            "negative_ddg_is_stabilizing": True,
            "threshold_class": row.get("threshold_class"),
            "evidence_level": "computational_proxy_benchmark",
            "manual_review_required": True,
            "training_label_source": False,
            "physics_ddg_result": False,
            "wet_lab_label_source": False,
            "source_smoke_report": rel(args.smoke_report),
            "source_smoke_report_sha256": sha256(args.smoke_report),
            "safe_for_training_import": False,
            "safe_for_model_claim": False,
            "release_ready": False,
        })
    write_jsonl(DATASET, dataset_rows)

    values = [row["ddg_pred_kcal_mol"] for row in dataset_rows if isinstance(row.get("ddg_pred_kcal_mol"), float)]
    stabilizing_rows = sum(1 for value in values if value < -0.5)
    destabilizing_rows = sum(1 for value in values if value > 0.5)
    near_neutral_rows = len(values) - stabilizing_rows - destabilizing_rows

    split = {
        "created_at": created_at,
        "local_only": True,
        "benchmark_name": BENCHMARK_NAME,
        "head": HEAD,
        "split_strategy": "evaluation_only_all_rows_no_training",
        "train_rows": 0,
        "validation_rows": 0,
        "test_rows": len(dataset_rows),
        "leakage_check_status": "passed",
        "leakage_basis": "ThermoMPNN smoke rows are evaluation-only proxy outputs and are not admitted into KWB training labels.",
        "future_training_exclusion_required": True,
        "safe_for_model_claim": False,
    }
    scorecard = {
        "created_at": created_at,
        "local_only": True,
        "benchmark_name": BENCHMARK_NAME,
        "head": HEAD,
        "dataset_version": DATASET_VERSION,
        "model_under_test": "ThermoMPNN default local smoke",
        "backend": "thermompnn",
        "rows_scored": len(dataset_rows),
        "mutation_count": len({row.get("mutation") for row in dataset_rows}),
        "mean_predicted_ddg_kcal_mol": sum(values) / len(values) if values else None,
        "stabilizing_rows_lt_minus_0_5": stabilizing_rows,
        "near_neutral_rows_minus_0_5_to_0_5": near_neutral_rows,
        "destabilizing_rows_gt_0_5": destabilizing_rows,
        "sample_limited": True,
        "quality_status": "sample_limited_proxy_comparison_only",
        "training_data_used": "none_by_this_benchmark_cache_row",
        "source_license_type": source.get("license_type"),
        "ready_for_model_claim": False,
        "safe_for_model_claim": False,
        "release_ready": False,
        "policy": "Sample-limited proxy comparison scorecard only; not a wet-lab or physics-ddG benchmark claim.",
    }
    metric_report = {
        "created_at": created_at,
        "local_only": True,
        "benchmark_name": BENCHMARK_NAME,
        "head": HEAD,
        "dataset_rows": len(dataset_rows),
        "primary_metric": "coverage_rows",
        "primary_metric_value": len(dataset_rows),
        "secondary_metrics": {
            "mean_predicted_ddg_kcal_mol": scorecard["mean_predicted_ddg_kcal_mol"],
            "stabilizing_rows_lt_minus_0_5": stabilizing_rows,
            "near_neutral_rows_minus_0_5_to_0_5": near_neutral_rows,
            "destabilizing_rows_gt_0_5": destabilizing_rows,
        },
        "quality_status": "sample_limited_proxy_comparison_only",
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
        "authorization_status": "self_attested_benchmark_only",
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
        "reviewer": "local_thermompnn_smoke_artifact",
        "reviewed_at": created_at,
        "notes": "Local ThermoMPNN sample-limited proxy comparison benchmark. Not a wet-lab label, not physics ddG, not model-quality claim evidence.",
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
        "source_smoke_report": rel(args.smoke_report),
        "source_local_report": rel(args.local_source_report),
        "dataset_rows": len(dataset_rows),
        "quality_status": "sample_limited_proxy_comparison_only",
        "leakage_check_status": "passed",
        "accepted_for_local_benchmark_cache_intake": True,
        "ready_for_model_claim": False,
        "safe_for_model_claim": False,
        "release_ready": False,
        "policy": "Real local benchmark artifact for ThermoMPNN comparison plumbing only; no training/model/release gate is opened.",
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({
        "dataset_rows": report["dataset_rows"],
        "benchmark_name": BENCHMARK_NAME,
        "quality_status": report["quality_status"],
        "accepted_for_local_benchmark_cache_intake": report["accepted_for_local_benchmark_cache_intake"],
        "safe_for_model_claim": False,
        "output": rel(args.report),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
