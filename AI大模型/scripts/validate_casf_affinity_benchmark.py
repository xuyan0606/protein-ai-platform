#!/usr/bin/env python3
"""Validate the evaluation-only CASF-2016 affinity reference cache."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
SOURCE = AI_ROOT / "cache" / "external" / "casf2016_plbap" / "2026-03-30_CASF2016_AllModels_PredsAndTimes.csv"
LICENSE = AI_ROOT / "cache" / "external" / "casf2016_plbap" / "LICENSE"
BENCH_DIR = AI_ROOT / "cache" / "advanced_features" / "benchmarks" / "casf2016_affinity_reference"
DATASET = BENCH_DIR / "dataset.jsonl"
SPLIT = BENCH_DIR / "split_definition.json"
SCORECARD = BENCH_DIR / "scorecard.json"
METRIC = BENCH_DIR / "metric_report.json"
RECEIPT = BENCH_DIR / "source_receipt.json"
REPORT = AI_ROOT / "reports" / "casf_affinity_benchmark_report.json"
INTAKE = AI_ROOT / "datasets" / "benchmark" / "benchmark_score_cache_intake.local.jsonl"
HEAD = "substrate_fit"
BENCHMARK_NAME = "PDBbind/CASF/D3R-style affinity or pose benchmark"
EXPECTED_SIZE = 293759
EXPECTED_SHA256 = "e23ce7e2b92055bcec4afbdd611f5f30e1f37caac181f617de33149a057516c6"
FALSE_FIELDS = ("training_label_source", "ready_for_training_import", "safe_for_training_import", "ready_for_model_claim", "safe_for_model_claim", "release_ready")


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    value = json.loads(path.read_text(encoding="utf-8"))
    return value if isinstance(value, dict) else {}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def fail_if(condition: bool, failures: list[dict[str, Any]], check: str, observed: Any, expected: Any) -> None:
    if condition:
        failures.append({"check": check, "observed": observed, "expected": expected})


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate CASF-2016 affinity reference benchmark")
    parser.add_argument("--output", type=Path, default=AI_ROOT / "reports" / "casf_affinity_benchmark_validation_report.json")
    args = parser.parse_args()
    dataset = load_jsonl(DATASET)
    split = load_json(SPLIT)
    scorecard = load_json(SCORECARD)
    metric = load_json(METRIC)
    receipt = load_json(RECEIPT)
    report = load_json(REPORT)
    intake = next((row for row in load_jsonl(INTAKE) if row.get("head") == HEAD and row.get("benchmark_name") == BENCHMARK_NAME), {})
    failures: list[dict[str, Any]] = []
    fail_if(not SOURCE.exists(), failures, "source_exists", False, True)
    if SOURCE.exists():
        fail_if(SOURCE.stat().st_size != EXPECTED_SIZE, failures, "source_size", SOURCE.stat().st_size, EXPECTED_SIZE)
        fail_if(digest(SOURCE) != EXPECTED_SHA256, failures, "source_sha256", digest(SOURCE), EXPECTED_SHA256)
    fail_if(not LICENSE.exists(), failures, "license_exists", False, True)
    if LICENSE.exists():
        fail_if("CC0" not in LICENSE.read_text(encoding="utf-8"), failures, "license_declares_cc0", False, True)
    fail_if(len(dataset) < 4000, failures, "dataset_rows_minimum", len(dataset), ">=4000")
    ids = [row.get("benchmark_record_id") for row in dataset]
    fail_if(len(ids) != len(set(ids)), failures, "record_ids_unique", len(set(ids)), len(ids))
    pdb_ids = {row.get("pdb_id") for row in dataset}
    models = Counter(str(row.get("model")) for row in dataset)
    fail_if(len(pdb_ids) != 285, failures, "unique_complexes", len(pdb_ids), 285)
    fail_if(len(models) != 16, failures, "model_count", len(models), 16)
    for index, row in enumerate(dataset, start=1):
        fail_if(row.get("head") != HEAD, failures, "row_head", {"row": index, "value": row.get("head")}, HEAD)
        fail_if(row.get("benchmark_name") != BENCHMARK_NAME, failures, "row_benchmark_name", {"row": index, "value": row.get("benchmark_name")}, BENCHMARK_NAME)
        for field in FALSE_FIELDS:
            fail_if(row.get(field) is not False, failures, f"row_{field}_false", {"row": index, "value": row.get(field)}, False)
        for field in ("pka_predicted", "pka_true", "absolute_error"):
            value = row.get(field)
            fail_if(not isinstance(value, (int, float)) or isinstance(value, bool), failures, f"row_{field}_finite", {"row": index, "value": value}, "finite numeric")
        for field in ("prep_seconds", "inference_seconds", "total_seconds"):
            value = row.get(field)
            fail_if(value is not None and (not isinstance(value, (int, float)) or isinstance(value, bool)), failures, f"row_{field}_optional_numeric", {"row": index, "value": value}, "null or finite numeric")
    fail_if(split.get("split_strategy") != "published_casf2016_reference_rows_evaluation_only_no_training", failures, "split_strategy", split.get("split_strategy"), "published_casf2016_reference_rows_evaluation_only_no_training")
    fail_if(split.get("leakage_check_status") != "passed", failures, "split_leakage", split.get("leakage_check_status"), "passed")
    fail_if(split.get("test_rows") != len(dataset), failures, "split_test_rows", split.get("test_rows"), len(dataset))
    fail_if(scorecard.get("rows_scored") != len(dataset), failures, "scorecard_rows", scorecard.get("rows_scored"), len(dataset))
    fail_if(metric.get("dataset_rows") != len(dataset), failures, "metric_rows", metric.get("dataset_rows"), len(dataset))
    fail_if(metric.get("ready_as_benchmark_scorecard") is not True, failures, "metric_ready", metric.get("ready_as_benchmark_scorecard"), True)
    fail_if(report.get("training_import_written_rows") != 0, failures, "training_import_written_rows", report.get("training_import_written_rows"), 0)
    fail_if(receipt.get("casf_runtime_executed_locally") is not False, failures, "casf_runtime_executed_locally", receipt.get("casf_runtime_executed_locally"), False)
    for source in (split, scorecard, metric, report):
        for field in ("ready_for_model_claim", "safe_for_model_claim", "release_ready"):
            fail_if(source.get(field) is not False, failures, f"{field}_false", source.get(field), False)
    fail_if(not intake, failures, "intake_present", None, "present")
    if intake:
        for key, path in (("dataset_sha256", DATASET), ("split_sha256", SPLIT), ("scorecard_sha256", SCORECARD), ("metric_sha256", METRIC)):
            fail_if(str(intake.get(key) or "").lower() != digest(path), failures, f"intake_{key}", intake.get(key), digest(path))
        fail_if(intake.get("license_review_status") != "approved_for_benchmark_only", failures, "intake_license", intake.get("license_review_status"), "approved_for_benchmark_only")
        fail_if(intake.get("leakage_check_status") != "passed", failures, "intake_leakage", intake.get("leakage_check_status"), "passed")
    validation = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "local_only": True,
        "benchmark_name": BENCHMARK_NAME,
        "head": HEAD,
        "dataset_rows": len(dataset),
        "unique_complexes": len(pdb_ids),
        "model_counts": dict(sorted(models.items())),
        "success": not failures,
        "failures": failures,
        "ready_as_benchmark_scorecard": not failures,
        "training_import_written_rows": 0,
        "casf_runtime_executed_locally": False,
        "ready_for_model_claim": False,
        "safe_for_model_claim": False,
        "release_ready": False,
        "policy": "Evaluation-only CASF-2016 affinity reference benchmark. It does not create KWB labels, execute a CASF runtime, or grant model/release readiness.",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(validation, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"success": validation["success"], "dataset_rows": len(dataset), "unique_complexes": len(pdb_ids), "models": len(models), "failures": len(failures), "output": str(args.output)}, ensure_ascii=False))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
