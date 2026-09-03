#!/usr/bin/env python3
"""Validate the evaluation-only GotEnzymes2 reference benchmark cache."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
ARCHIVE = AI_ROOT / "cache" / "external" / "input_data.zip"
ZENODO_RECORD = AI_ROOT / "cache" / "external" / "gotenzymes2_zenodo_record_17196785.json"
BENCH_DIR = AI_ROOT / "cache" / "advanced_features" / "benchmarks" / "catpred_gotenzymes_predicted_reference_only"
DATASET = BENCH_DIR / "dataset.jsonl"
SPLIT = BENCH_DIR / "split_definition.json"
SCORECARD = BENCH_DIR / "scorecard.json"
METRIC = BENCH_DIR / "metric_report.json"
SOURCE_RECEIPT = BENCH_DIR / "source_receipt.json"
REPORT = AI_ROOT / "reports" / "catpred_gotenzymes_reference_benchmark_report.json"
INTAKE = AI_ROOT / "datasets" / "benchmark" / "benchmark_score_cache_intake.local.jsonl"

HEAD = "activity_risk"
BENCHMARK_NAME = "CatPred/GotEnzymes predicted reference only"
EXPECTED_ARCHIVE_SIZE = 1190270380
EXPECTED_ARCHIVE_MD5 = "5b07cf2fa8a22262312bd9c9fde047cb"
EXPECTED_SHARDS = {"bdw", "oyw", "gsc"}
FALSE_FIELDS = (
    "training_label_source",
    "ready_for_training_import",
    "safe_for_training_import",
    "ready_for_model_claim",
    "safe_for_model_claim",
    "release_ready",
)


def digest(path: Path, algorithm: str = "sha256") -> str:
    value = hashlib.new(algorithm)
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            value.update(chunk)
    return value.hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return value if isinstance(value, dict) else {}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def fail_if(condition: bool, failures: list[dict[str, Any]], check: str, observed: Any, expected: Any) -> None:
    if condition:
        failures.append({"check": check, "observed": observed, "expected": expected})


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate GotEnzymes2 reference benchmark")
    parser.add_argument("--output", type=Path, default=AI_ROOT / "reports" / "catpred_gotenzymes_reference_benchmark_validation_report.json")
    args = parser.parse_args()

    dataset = load_jsonl(DATASET)
    split = load_json(SPLIT)
    scorecard = load_json(SCORECARD)
    metric = load_json(METRIC)
    receipt = load_json(SOURCE_RECEIPT)
    report = load_json(REPORT)
    zenodo = load_json(ZENODO_RECORD)
    intake = next((row for row in load_jsonl(INTAKE) if row.get("head") == HEAD and row.get("benchmark_name") == BENCHMARK_NAME), {})
    failures: list[dict[str, Any]] = []

    fail_if(not ARCHIVE.exists(), failures, "source_archive_exists", False, True)
    if ARCHIVE.exists():
        fail_if(ARCHIVE.stat().st_size != EXPECTED_ARCHIVE_SIZE, failures, "source_archive_size", ARCHIVE.stat().st_size, EXPECTED_ARCHIVE_SIZE)
        fail_if(digest(ARCHIVE, "md5") != EXPECTED_ARCHIVE_MD5, failures, "source_archive_md5", digest(ARCHIVE, "md5"), EXPECTED_ARCHIVE_MD5)
    fail_if(zenodo.get("metadata", {}).get("license", {}).get("id") != "cc-by-4.0", failures, "zenodo_license", zenodo.get("metadata", {}).get("license"), "cc-by-4.0")
    fail_if(receipt.get("doi") != "10.5281/zenodo.17196785", failures, "receipt_doi", receipt.get("doi"), "10.5281/zenodo.17196785")
    fail_if(receipt.get("authorization_status") != "self_attested", failures, "receipt_authorization_status", receipt.get("authorization_status"), "self_attested")
    fail_if(receipt.get("verification_required") is not True, failures, "receipt_verification_required", receipt.get("verification_required"), True)
    fail_if(receipt.get("catpred_model_executed") is not False, failures, "catpred_model_executed", receipt.get("catpred_model_executed"), False)

    fail_if(len(dataset) < 100, failures, "dataset_rows_minimum", len(dataset), ">=100")
    ids = [row.get("benchmark_record_id") for row in dataset]
    fail_if(len(set(ids)) != len(ids), failures, "record_ids_unique", len(set(ids)), len(ids))
    shard_counts = Counter(str(row.get("source_shard")) for row in dataset)
    fail_if(set(shard_counts) != EXPECTED_SHARDS, failures, "source_shards", sorted(shard_counts), sorted(EXPECTED_SHARDS))
    for index, row in enumerate(dataset, start=1):
        fail_if(row.get("head") != HEAD, failures, "row_head", {"row": index, "value": row.get("head")}, HEAD)
        fail_if(row.get("benchmark_name") != BENCHMARK_NAME, failures, "row_benchmark_name", {"row": index, "value": row.get("benchmark_name")}, BENCHMARK_NAME)
        fail_if(row.get("reference_scope") != "predicted_reference_only", failures, "row_reference_scope", {"row": index, "value": row.get("reference_scope")}, "predicted_reference_only")
        fail_if(row.get("catpred_model_executed") is not False, failures, "row_catpred_model_executed", {"row": index, "value": row.get("catpred_model_executed")}, False)
        for field in FALSE_FIELDS:
            fail_if(row.get(field) is not False, failures, f"row_{field}_false", {"row": index, "value": row.get(field)}, False)
        for field in ("kcat_raw", "km_raw", "kcat_over_km_raw", "topt_raw", "tm_raw"):
            value = row.get(field)
            fail_if(not isinstance(value, (int, float)) or isinstance(value, bool), failures, f"row_{field}_numeric", {"row": index, "value": value}, "finite numeric")

    fail_if(split.get("split_strategy") != "evaluation_only_source_shard_reference_no_training", failures, "split_strategy", split.get("split_strategy"), "evaluation_only_source_shard_reference_no_training")
    fail_if(split.get("leakage_check_status") != "passed", failures, "split_leakage_check_status", split.get("leakage_check_status"), "passed")
    fail_if(split.get("test_rows") != len(dataset), failures, "split_test_rows", split.get("test_rows"), len(dataset))
    fail_if(scorecard.get("rows_scored") != len(dataset), failures, "scorecard_rows_scored", scorecard.get("rows_scored"), len(dataset))
    fail_if(metric.get("dataset_rows") != len(dataset), failures, "metric_dataset_rows", metric.get("dataset_rows"), len(dataset))
    fail_if(metric.get("ready_as_benchmark_scorecard") is not True, failures, "metric_ready_as_benchmark_scorecard", metric.get("ready_as_benchmark_scorecard"), True)
    fail_if(report.get("training_import_written_rows") != 0, failures, "training_import_written_rows", report.get("training_import_written_rows"), 0)
    for source in (split, scorecard, metric, report):
        for field in ("ready_for_model_claim", "safe_for_model_claim", "release_ready"):
            fail_if(source.get(field) is not False, failures, f"{field}_false", source.get(field), False)

    fail_if(not intake, failures, "intake_row_present", None, "present")
    if intake:
        for key, path in (
            ("dataset_sha256", DATASET),
            ("split_sha256", SPLIT),
            ("scorecard_sha256", SCORECARD),
            ("metric_sha256", METRIC),
        ):
            fail_if(str(intake.get(key) or "").lower() != digest(path), failures, f"intake_{key}", intake.get(key), digest(path))
        fail_if(intake.get("license_review_status") != "approved_for_benchmark_only", failures, "intake_license_review_status", intake.get("license_review_status"), "approved_for_benchmark_only")
        fail_if(intake.get("leakage_check_status") != "passed", failures, "intake_leakage_check_status", intake.get("leakage_check_status"), "passed")

    validation = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "local_only": True,
        "benchmark_name": BENCHMARK_NAME,
        "head": HEAD,
        "dataset_rows": len(dataset),
        "source_shard_counts": dict(sorted(shard_counts.items())),
        "success": not failures,
        "failures": failures,
        "ready_as_benchmark_scorecard": not failures,
        "training_import_written_rows": 0,
        "catpred_model_executed": False,
        "ready_for_model_claim": False,
        "safe_for_model_claim": False,
        "release_ready": False,
        "policy": "Evaluation-only GotEnzymes2 predicted-reference benchmark. It does not create KWB labels, execute CatPred, or grant model/release readiness.",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(validation, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({
        "success": validation["success"],
        "dataset_rows": validation["dataset_rows"],
        "source_shard_counts": validation["source_shard_counts"],
        "failures": len(failures),
        "output": str(args.output),
    }, ensure_ascii=False))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
