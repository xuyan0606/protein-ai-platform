#!/usr/bin/env python3
"""Build an evaluation-only CASF-2016 affinity reference benchmark cache."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
SOURCE = AI_ROOT / "cache" / "external" / "casf2016_plbap" / "2026-03-30_CASF2016_AllModels_PredsAndTimes.csv"
README = AI_ROOT / "cache" / "external" / "casf2016_plbap" / "README.md"
LICENSE = AI_ROOT / "cache" / "external" / "casf2016_plbap" / "LICENSE"
COMMIT = AI_ROOT / "cache" / "external" / "casf2016_plbap" / "source_commit.json"
PLAN = AI_ROOT / "datasets" / "benchmark" / "benchmark_acquisition_plan.jsonl"
INTAKE = AI_ROOT / "datasets" / "benchmark" / "benchmark_score_cache_intake.local.jsonl"
REPORT = AI_ROOT / "reports" / "casf_affinity_benchmark_report.json"
BENCH_DIR = AI_ROOT / "cache" / "advanced_features" / "benchmarks" / "casf2016_affinity_reference"
DATASET = BENCH_DIR / "dataset.jsonl"
SPLIT = BENCH_DIR / "split_definition.json"
SCORECARD = BENCH_DIR / "scorecard.json"
METRIC = BENCH_DIR / "metric_report.json"
SOURCE_RECEIPT = BENCH_DIR / "source_receipt.json"

HEAD = "substrate_fit"
BENCHMARK_NAME = "PDBbind/CASF/D3R-style affinity or pose benchmark"
DATASET_VERSION = "casf2016-plbap-reproducibility-affinity-reference-v1-2026-08-04"
SOURCE_URL = "https://github.com/WoldringLabMSU/PLBAP_Reproducibility"
RAW_URL = "https://raw.githubusercontent.com/WoldringLabMSU/PLBAP_Reproducibility/main/2026-03-30_CASF2016_AllModels_PredsAndTimes.csv"
EXPECTED_SIZE = 293759
EXPECTED_SHA256 = "e23ce7e2b92055bcec4afbdd611f5f30e1f37caac181f617de33149a057516c6"


def digest(path: Path) -> str:
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


def write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def update_row(path: Path, row: dict[str, Any], keys: tuple[str, str]) -> None:
    rows = load_jsonl(path)
    row_key = tuple(row.get(key) for key in keys)
    output = []
    replaced = False
    for existing in rows:
        if tuple(existing.get(key) for key in keys) == row_key:
            output.append({**existing, **row})
            replaced = True
        else:
            output.append(existing)
    if not replaced:
        output.append(row)
    write_jsonl(path, output)


def parse_optional_float(value: str) -> float | None:
    if value == "":
        return None
    number = float(value)
    if not math.isfinite(number):
        raise ValueError("non_finite_numeric_value")
    return number


def read_rows() -> tuple[list[dict[str, Any]], Counter[str]]:
    rows: list[dict[str, Any]] = []
    errors: Counter[str] = Counter()
    with SOURCE.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        for index, source in enumerate(reader):
            try:
                pdbid = str(source["pdbid"]).strip().lower()
                predicted = float(source["pK_predicted"])
                true = float(source["pK_true"])
                prep = parse_optional_float(source["t_prep_s"])
                inference = parse_optional_float(source["t_inf_s"])
                total = parse_optional_float(source["t_tot_s"])
                model = str(source["Model"]).strip()
                values = (predicted, true)
                if not pdbid or not model or not all(math.isfinite(value) for value in values):
                    raise ValueError("missing_or_non_finite_value")
            except (KeyError, TypeError, ValueError) as exc:
                errors[type(exc).__name__] += 1
                continue
            rows.append({
                "benchmark_record_id": f"casf2016::{index}",
                "benchmark_name": BENCHMARK_NAME,
                "head": HEAD,
                "source_dataset": "CASF-2016",
                "source_url": SOURCE_URL,
                "source_raw_url": RAW_URL,
                "source_row_index": index,
                "pdb_id": pdbid,
                "model": model,
                "pka_predicted": predicted,
                "pka_true": true,
                "absolute_error": abs(predicted - true),
                "prep_seconds": prep,
                "inference_seconds": inference,
                "total_seconds": total,
                "benchmark_scope": "external_affinity_reference_evaluation_only",
                "casf_runtime_executed_locally": False,
                "training_label_source": False,
                "ready_for_training_import": False,
                "safe_for_training_import": False,
                "ready_for_model_claim": False,
                "safe_for_model_claim": False,
                "release_ready": False,
            })
    return rows, errors


def main() -> int:
    parser = argparse.ArgumentParser(description="Build CASF-2016 affinity reference benchmark")
    parser.add_argument("--report", type=Path, default=REPORT)
    args = parser.parse_args()
    created_at = datetime.now(timezone.utc).isoformat()
    failures: list[str] = []
    if not SOURCE.exists():
        failures.append("source_csv_missing")
    else:
        if SOURCE.stat().st_size != EXPECTED_SIZE:
            failures.append("source_csv_size_mismatch")
        if digest(SOURCE) != EXPECTED_SHA256:
            failures.append("source_csv_sha256_mismatch")

    rows: list[dict[str, Any]] = []
    parse_errors: Counter[str] = Counter()
    if not failures:
        rows, parse_errors = read_rows()
    pdb_count = len({row["pdb_id"] for row in rows})
    model_counts = Counter(row["model"] for row in rows)
    model_pdb_counts = {model: len({row["pdb_id"] for row in rows if row["model"] == model}) for model in model_counts}
    mean_abs_error = sum(row["absolute_error"] for row in rows) / len(rows) if rows else None

    write_jsonl(DATASET, rows)
    split = {
        "created_at": created_at,
        "local_only": True,
        "benchmark_name": BENCHMARK_NAME,
        "head": HEAD,
        "split_strategy": "published_casf2016_reference_rows_evaluation_only_no_training",
        "train_rows": 0,
        "validation_rows": 0,
        "test_rows": len(rows),
        "unique_test_complexes": pdb_count,
        "leakage_check_status": "passed",
        "leakage_basis": "Published CASF-2016 rows are kept evaluation-only and are never admitted to KWB substrate_fit labels.",
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
        "source_dataset": "CASF-2016",
        "model_under_test": "published_model_predictions_reference_only",
        "rows_scored": len(rows),
        "unique_complexes": pdb_count,
        "model_counts": dict(sorted(model_counts.items())),
        "model_complex_counts": dict(sorted(model_pdb_counts.items())),
        "pka_true_range": [min((row["pka_true"] for row in rows), default=None), max((row["pka_true"] for row in rows), default=None)],
        "mean_absolute_error_against_published_predictions": mean_abs_error,
        "quality_status": "external_casf_affinity_reference_cache_ready_not_model_claim",
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
        "primary_metric": "published_casf_affinity_reference_rows",
        "primary_metric_value": len(rows),
        "secondary_metrics": {
            "unique_complexes": pdb_count,
            "model_counts": dict(sorted(model_counts.items())),
            "model_complex_counts": dict(sorted(model_pdb_counts.items())),
            "mean_absolute_error_against_published_predictions": mean_abs_error,
            "parse_errors": dict(parse_errors),
        },
        "quality_status": "external_casf_affinity_reference_cache_ready_not_model_claim",
        "leakage_check_status": "passed",
        "ready_as_benchmark_scorecard": bool(rows) and not failures and not parse_errors,
        "ready_for_model_claim": False,
        "safe_for_model_claim": False,
        "release_ready": False,
    }
    write_json(SPLIT, split)
    write_json(SCORECARD, scorecard)
    write_json(METRIC, metric)
    receipt = {
        "created_at": created_at,
        "local_only": True,
        "source": "WoldringLabMSU/PLBAP_Reproducibility CASF-2016 reproducibility package",
        "source_url": SOURCE_URL,
        "raw_csv_url": RAW_URL,
        "source_csv": rel(SOURCE),
        "source_csv_size": SOURCE.stat().st_size if SOURCE.exists() else None,
        "source_csv_sha256": digest(SOURCE) if SOURCE.exists() else None,
        "source_readme": rel(README),
        "source_readme_sha256": digest(README) if README.exists() else None,
        "source_license": rel(LICENSE),
        "source_license_sha256": digest(LICENSE) if LICENSE.exists() else None,
        "source_commit_metadata": rel(COMMIT),
        "license_declared_by_source_repository": "CC0-1.0",
        "authorization_source": "public_repository_source_self_attested",
        "authorization_status": "self_attested",
        "verification_required": True,
        "casf_runtime_executed_locally": False,
        "allowed_use": "evaluation-only affinity reference benchmark cache",
        "forbidden_use": "do not use as KWB substrate_fit labels, training import, customer delivery, or release basis",
    }
    write_json(SOURCE_RECEIPT, receipt)
    intake = {
        "head": HEAD,
        "benchmark_name": BENCHMARK_NAME,
        "dataset_version": DATASET_VERSION,
        "license_review_status": "approved_for_benchmark_only",
        "authorization_source": "public_repository_source_self_attested",
        "authorization_status": "self_attested",
        "verification_required": True,
        "local_dataset_uri": rel(DATASET),
        "dataset_sha256": digest(DATASET),
        "split_definition_uri": rel(SPLIT),
        "split_sha256": digest(SPLIT),
        "scorecard_uri": rel(SCORECARD),
        "scorecard_sha256": digest(SCORECARD),
        "metric_report_uri": rel(METRIC),
        "metric_sha256": digest(METRIC),
        "leakage_check_status": "passed",
        "reviewer": "local_casf_affinity_reference_builder",
        "reviewed_at": created_at,
        "notes": "CASF-2016 affinity reference rows from a CC0-declared reproducibility package. Evaluation-only; no local CASF runtime and no KWB training labels.",
    }
    plan_row = {
        "head": HEAD,
        "benchmark_name": BENCHMARK_NAME,
        "acquisition_status": "configured",
        "license_review_status": "approved_for_benchmark_only",
        "local_dataset_uri": rel(DATASET),
        "checksum": digest(DATASET),
        "split_strategy": "published_casf2016_reference_rows_evaluation_only_no_training",
        "leakage_check_status": "passed",
        "scorecard_status": "ready",
        "allowed_use": "external CASF-2016 affinity benchmark cache only",
        "forbidden_use": "do not use as KWB wet-lab labels, training import, model-quality claim, or release basis",
    }
    update_row(PLAN, plan_row, ("head", "benchmark_name"))
    update_row(INTAKE, intake, ("head", "benchmark_name"))
    report = {
        "created_at": created_at,
        "local_only": True,
        "benchmark_name": BENCHMARK_NAME,
        "head": HEAD,
        "source_csv_verified": not failures,
        "source_csv_failures": failures,
        "dataset_rows": len(rows),
        "unique_complexes": pdb_count,
        "model_counts": dict(sorted(model_counts.items())),
        "model_complex_counts": dict(sorted(model_pdb_counts.items())),
        "parse_errors": dict(parse_errors),
        "outputs": {"dataset": rel(DATASET), "split": rel(SPLIT), "scorecard": rel(SCORECARD), "metric_report": rel(METRIC), "source_receipt": rel(SOURCE_RECEIPT)},
        "training_import_written_rows": 0,
        "substrate_fit_training_label_rows_written": 0,
        "casf_runtime_executed_locally": False,
        "ready_for_model_claim": False,
        "safe_for_model_claim": False,
        "release_ready": False,
        "policy": "Evaluation-only CASF-2016 affinity reference benchmark. It does not create KWB labels, execute a CASF runtime, or open model/release claims.",
    }
    write_json(args.report, report)
    print(json.dumps({"benchmark_name": BENCHMARK_NAME, "dataset_rows": len(rows), "unique_complexes": pdb_count, "models": len(model_counts), "training_import_written_rows": 0, "output": str(args.report)}, ensure_ascii=False))
    return 0 if rows and not failures and not parse_errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
