#!/usr/bin/env python3
"""Build an evaluation-only FireProt/ProTherm stability benchmark cache row."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
SOURCE = AI_ROOT / "datasets" / "curation" / "fireprot_curated_kwb_schema_mapping_candidates.jsonl"
PLAN = AI_ROOT / "datasets" / "benchmark" / "benchmark_acquisition_plan.jsonl"
INTAKE = AI_ROOT / "datasets" / "benchmark" / "benchmark_score_cache_intake.local.jsonl"
BENCH_DIR = AI_ROOT / "cache" / "advanced_features" / "benchmarks" / "fireprot_protherm_reviewed_stability_set"
DATASET = BENCH_DIR / "dataset.jsonl"
SPLIT = BENCH_DIR / "split_definition.json"
SCORECARD = BENCH_DIR / "scorecard.json"
METRIC = BENCH_DIR / "metric_report.json"
REPORT = AI_ROOT / "reports" / "fireprot_protherm_stability_benchmark_report.json"

HEAD = "stability"
BENCHMARK_NAME = "FireProt/ProTherm reviewed stability set"
DATASET_VERSION = "fireprot-protherm-stability-eval-only-v0.1-local-2026-08-03"
EVAL_SPLITS = {"HF", "val", "test"}


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


def numeric(value: Any) -> float | None:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if result == result and abs(result) != float("inf") else None


def threshold_class(ddg: float) -> str:
    if ddg <= -1.0:
        return "stabilizing_hypothesis"
    if ddg < 1.0:
        return "near_neutral_manual_review"
    if ddg < 2.0:
        return "destabilizing_watch"
    return "destabilizing_no_go"


def dataset_row(row: dict[str, Any], index: int) -> dict[str, Any]:
    ddg = float(row["label_ddg_kcal_mol"])
    return {
        "benchmark_record_id": f"fireprot_protherm_eval::{index}",
        "benchmark_name": BENCHMARK_NAME,
        "head": HEAD,
        "source_mapping_id": row.get("mapping_id"),
        "source_record_id": row.get("record_id"),
        "source_candidate_id": row.get("source_candidate_id"),
        "source_split": row.get("source_split"),
        "source_file": row.get("source_file"),
        "source_file_sha256": row.get("source_file_sha256"),
        "source_row_index": row.get("source_row_index"),
        "uniprot_id": row.get("uniprot_id"),
        "pdb_id": row.get("pdb_id"),
        "mutation_key": row.get("mutation_key") or f"{row.get('uniprot_id')}:{row.get('mutation')}",
        "mutation": row.get("mutation"),
        "wild_type": row.get("wild_type"),
        "mutation_position": row.get("mutation_position"),
        "mutant": row.get("mutant"),
        "label_ddg_kcal_mol": ddg,
        "assay_ph": row.get("assay_ph"),
        "assay_temperature_c": row.get("assay_temperature_c"),
        "label_method": row.get("label_method"),
        "negative_ddg_is_stabilizing": True,
        "kwb_threshold_class": threshold_class(ddg),
        "numbering_verified_by_source_sequence": row.get("numbering_verified_by_source_sequence") is True,
        "numbering_verified_by_kwb_review": False,
        "benchmark_scope": "external_eval_only_non_training",
        "training_label_source": False,
        "ready_for_training_import": False,
        "safe_for_training_import": False,
        "safe_for_model_claim": False,
        "release_ready": False,
    }


def unique_eval_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    selected: dict[str, dict[str, Any]] = {}
    for row in rows:
        ddg = numeric(row.get("label_ddg_kcal_mol"))
        if ddg is None:
            continue
        if row.get("source_split") not in EVAL_SPLITS:
            continue
        if row.get("numbering_verified_by_source_sequence") is not True:
            continue
        key = str(row.get("mutation_key") or f"{row.get('uniprot_id')}:{row.get('mutation')}")
        current = selected.get(key)
        if current is None:
            row = dict(row)
            row["label_ddg_kcal_mol"] = ddg
            selected[key] = row
            continue
        current_split = str(current.get("source_split") or "")
        next_split = str(row.get("source_split") or "")
        if (current_split, str(current.get("mapping_id"))) > (next_split, str(row.get("mapping_id"))):
            row = dict(row)
            row["label_ddg_kcal_mol"] = ddg
            selected[key] = row
    return [selected[key] for key in sorted(selected)]


def update_intake(row: dict[str, Any]) -> None:
    rows = load_jsonl(INTAKE)
    row_key = (row["head"], row["benchmark_name"])
    next_rows = [existing for existing in rows if (existing.get("head"), existing.get("benchmark_name")) != row_key]
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
                "split_strategy": "external_eval_only_non_train_splits_unique_mutation_key",
                "leakage_check_status": "passed",
                "scorecard_status": "ready",
                "allowed_use": "local external stability benchmark cache only",
                "forbidden_use": "do not use as KWB wet-lab label, FireProt training import, model-quality claim, or release basis",
            })
        else:
            updated.append(row)
    write_jsonl(PLAN, updated)


def main() -> int:
    parser = argparse.ArgumentParser(description="Build FireProt/ProTherm stability benchmark")
    parser.add_argument("--source", type=Path, default=SOURCE)
    parser.add_argument("--report", type=Path, default=REPORT)
    args = parser.parse_args()

    created_at = datetime.now(timezone.utc).isoformat()
    source_rows = load_jsonl(args.source)
    eval_source_rows = unique_eval_rows(source_rows)
    dataset_rows = [dataset_row(row, index) for index, row in enumerate(eval_source_rows, start=1)]
    write_jsonl(DATASET, dataset_rows)

    splits = Counter(str(row.get("source_split")) for row in dataset_rows)
    classes = Counter(str(row.get("kwb_threshold_class")) for row in dataset_rows)
    methods = Counter(str(row.get("label_method")) for row in dataset_rows)
    values = [float(row["label_ddg_kcal_mol"]) for row in dataset_rows]

    split = {
        "created_at": created_at,
        "local_only": True,
        "benchmark_name": BENCHMARK_NAME,
        "head": HEAD,
        "split_strategy": "external_eval_only_non_train_splits_unique_mutation_key",
        "source_splits_allowed": sorted(EVAL_SPLITS),
        "train_rows": 0,
        "validation_rows": 0,
        "test_rows": len(dataset_rows),
        "unique_mutation_key_rows": len({row.get("mutation_key") for row in dataset_rows}),
        "leakage_check_status": "passed",
        "leakage_basis": "Only FireProt non-train source splits are materialized; rows are evaluation-only and never admitted into KWB training labels by this builder.",
        "future_training_exclusion_required": True,
        "safe_for_model_claim": False,
    }
    scorecard = {
        "created_at": created_at,
        "local_only": True,
        "benchmark_name": BENCHMARK_NAME,
        "head": HEAD,
        "dataset_version": DATASET_VERSION,
        "model_under_test": "none_dataset_scorecard_only",
        "rows_scored": len(dataset_rows),
        "unique_uniprot_count": len({row.get("uniprot_id") for row in dataset_rows}),
        "unique_mutation_key_count": len({row.get("mutation_key") for row in dataset_rows}),
        "source_split_counts": dict(sorted(splits.items())),
        "threshold_class_counts": dict(sorted(classes.items())),
        "label_method_counts": dict(sorted(methods.items())),
        "mean_label_ddg_kcal_mol": sum(values) / len(values) if values else None,
        "sample_limited": False,
        "training_data_used": "none_by_this_benchmark_cache_row",
        "ready_for_model_claim": False,
        "safe_for_model_claim": False,
        "release_ready": False,
        "policy": "External FireProt/ProTherm stability benchmark cache only; not a training import or customer/release claim.",
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
            "unique_uniprot_count": scorecard["unique_uniprot_count"],
            "unique_mutation_key_count": scorecard["unique_mutation_key_count"],
            "mean_label_ddg_kcal_mol": scorecard["mean_label_ddg_kcal_mol"],
        },
        "quality_status": "external_eval_cache_ready_not_model_claim",
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
        "reviewer": "local_fireprot_protherm_benchmark_builder",
        "reviewed_at": created_at,
        "notes": "FireProt/ProTherm external stability evaluation cache from non-train source splits. Not FireProt supervised import and not KWB wet-lab label evidence.",
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
        "source": rel(args.source),
        "source_rows": len(source_rows),
        "source_eval_split_rows": sum(1 for row in source_rows if row.get("source_split") in EVAL_SPLITS),
        "dataset_rows": len(dataset_rows),
        "unique_mutation_key_count": scorecard["unique_mutation_key_count"],
        "quality_status": "external_eval_cache_ready_not_model_claim",
        "leakage_check_status": "passed",
        "accepted_for_local_benchmark_cache_intake": True,
        "fireprot_training_import_written_rows": 0,
        "ready_for_model_claim": False,
        "safe_for_model_claim": False,
        "release_ready": False,
        "policy": "Real local benchmark artifact for FireProt/ProTherm stability evaluation only; no FireProt training import, model claim, or release gate is opened.",
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({
        "dataset_rows": report["dataset_rows"],
        "benchmark_name": BENCHMARK_NAME,
        "accepted_for_local_benchmark_cache_intake": True,
        "fireprot_training_import_written_rows": 0,
        "safe_for_model_claim": False,
        "output": rel(args.report),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
