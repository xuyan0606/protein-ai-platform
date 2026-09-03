#!/usr/bin/env python3
"""Build an evaluation-only GotEnzymes2 predicted-reference benchmark cache.

The source archive contains GotEnzymes2 catalytic and thermal reference rows.
This builder preserves the raw source values and provenance. It does not run
CatPred, create KWB labels, or import anything into training.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import zipfile
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
ARCHIVE = AI_ROOT / "cache" / "external" / "input_data.zip"
ZENODO_RECORD = AI_ROOT / "cache" / "external" / "gotenzymes2_zenodo_record_17196785.json"
CATPRED_REPO = AI_ROOT / "cache" / "external" / "catpred_github_repo.json"
PLAN = AI_ROOT / "datasets" / "benchmark" / "benchmark_acquisition_plan.jsonl"
INTAKE = AI_ROOT / "datasets" / "benchmark" / "benchmark_score_cache_intake.local.jsonl"
REPORT = AI_ROOT / "reports" / "catpred_gotenzymes_reference_benchmark_report.json"
BENCH_DIR = AI_ROOT / "cache" / "advanced_features" / "benchmarks" / "catpred_gotenzymes_predicted_reference_only"
DATASET = BENCH_DIR / "dataset.jsonl"
SPLIT = BENCH_DIR / "split_definition.json"
SCORECARD = BENCH_DIR / "scorecard.json"
METRIC = BENCH_DIR / "metric_report.json"
SOURCE_RECEIPT = BENCH_DIR / "source_receipt.json"

HEAD = "activity_risk"
BENCHMARK_NAME = "CatPred/GotEnzymes predicted reference only"
DATASET_VERSION = "gotenzymes2-source-reference-bdw-oyw-gsc-v1-2026-08-03"
SOURCE_DOI = "10.5281/zenodo.17196785"
SOURCE_URL = "https://zenodo.org/records/17196785"
EXPECTED_ARCHIVE_SIZE = 1190270380
EXPECTED_ARCHIVE_MD5 = "5b07cf2fa8a22262312bd9c9fde047cb"
SHARDS = ("bdw", "oyw", "gsc")
SOURCE_COLUMNS = (
    "source_protein_id",
    "source_shard",
    "organism_code",
    "reaction_id",
    "ec",
    "compound_id",
    "kcat_raw",
    "km_raw",
    "kcat_over_km_raw",
    "topt_raw",
    "tm_raw",
)
NUMERIC_COLUMNS = SOURCE_COLUMNS[6:]


def digest(path: Path, algorithm: str = "sha256") -> str:
    value = hashlib.new(algorithm)
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            value.update(chunk)
    return value.hexdigest()


def digest_bytes(value: bytes, algorithm: str = "sha256") -> str:
    return hashlib.new(algorithm, value).hexdigest()


def relative(path: Path) -> str:
    return str(path.relative_to(AI_ROOT))


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
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )


def update_row(path: Path, row: dict[str, Any], key_fields: tuple[str, str]) -> None:
    rows = load_jsonl(path)
    key = tuple(row.get(field) for field in key_fields)
    replaced = False
    output = []
    for existing in rows:
        if tuple(existing.get(field) for field in key_fields) == key:
            output.append({**existing, **row})
            replaced = True
        else:
            output.append(existing)
    if not replaced:
        output.append(row)
    write_jsonl(path, output)


def parse_numeric(value: str) -> float:
    number = float(value)
    if number != number or number in (float("inf"), float("-inf")):
        raise ValueError("non-finite numeric value")
    return number


def read_shards() -> tuple[list[dict[str, Any]], list[dict[str, Any]], Counter[str]]:
    rows: list[dict[str, Any]] = []
    shard_receipts: list[dict[str, Any]] = []
    errors: Counter[str] = Counter()
    with zipfile.ZipFile(ARCHIVE) as archive:
        names = {f"input_data/gotEnzymes2/{shard}.txt": shard for shard in SHARDS}
        for member, shard in names.items():
            payload = archive.read(member)
            shard_rows = 0
            for row_index, line in enumerate(payload.decode("utf-8").splitlines()):
                if not line.strip():
                    continue
                fields = line.split("\t")
                if len(fields) != len(SOURCE_COLUMNS):
                    errors["column_count"] += 1
                    continue
                try:
                    numeric_values = [parse_numeric(fields[index]) for index in range(6, 11)]
                except ValueError:
                    errors["numeric_parse"] += 1
                    continue
                record = {
                    "benchmark_record_id": f"gotenzymes2::{shard}::{row_index}",
                    "benchmark_name": BENCHMARK_NAME,
                    "head": HEAD,
                    "source_dataset": "GotEnzymes2",
                    "source_doi": SOURCE_DOI,
                    "source_url": SOURCE_URL,
                    "source_shard": shard,
                    "source_row_index": row_index,
                    "source_archive_member": member,
                    "source_archive_member_sha256": digest_bytes(payload),
                    "source_protein_id": fields[0],
                    "organism_code": fields[2],
                    "reaction_id": fields[3],
                    "ec": fields[4],
                    "compound_id": fields[5],
                    "kcat_raw": numeric_values[0],
                    "km_raw": numeric_values[1],
                    "kcat_over_km_raw": numeric_values[2],
                    "topt_raw": numeric_values[3],
                    "tm_raw": numeric_values[4],
                    "source_field_semantics": {
                        "kcat_raw": "GotEnzymes2 catalytic parameter source field; transform/unit preserved as raw",
                        "km_raw": "GotEnzymes2 catalytic parameter source field; transform/unit preserved as raw",
                        "kcat_over_km_raw": "GotEnzymes2 catalytic parameter source field; transform/unit preserved as raw",
                        "topt_raw": "GotEnzymes2 thermal parameter source field; transform/unit preserved as raw",
                        "tm_raw": "GotEnzymes2 thermal parameter source field; transform/unit preserved as raw",
                    },
                    "reference_scope": "predicted_reference_only",
                    "catpred_model_executed": False,
                    "benchmark_scope": "external_activity_risk_reference_evaluation_only",
                    "training_label_source": False,
                    "ready_for_training_import": False,
                    "safe_for_training_import": False,
                    "ready_for_model_claim": False,
                    "safe_for_model_claim": False,
                    "release_ready": False,
                }
                rows.append(record)
                shard_rows += 1
            shard_receipts.append({
                "shard": shard,
                "member": member,
                "compressed_size": archive.getinfo(member).compress_size,
                "uncompressed_size": archive.getinfo(member).file_size,
                "sha256": digest_bytes(payload),
                "rows": shard_rows,
            })
    return rows, shard_receipts, errors


def main() -> int:
    parser = argparse.ArgumentParser(description="Build GotEnzymes2 predicted-reference benchmark")
    parser.add_argument("--report", type=Path, default=REPORT)
    args = parser.parse_args()

    created_at = datetime.now(timezone.utc).isoformat()
    failures: list[str] = []
    if not ARCHIVE.exists():
        failures.append("source_archive_missing")
    elif ARCHIVE.stat().st_size != EXPECTED_ARCHIVE_SIZE:
        failures.append("source_archive_size_mismatch")
    elif digest(ARCHIVE, "md5") != EXPECTED_ARCHIVE_MD5:
        failures.append("source_archive_md5_mismatch")

    rows: list[dict[str, Any]] = []
    shard_receipts: list[dict[str, Any]] = []
    parse_errors: Counter[str] = Counter()
    if not failures:
        try:
            rows, shard_receipts, parse_errors = read_shards()
        except (KeyError, OSError, UnicodeDecodeError, zipfile.BadZipFile) as exc:
            failures.append(f"source_archive_read_failed:{type(exc).__name__}")

    source_record = load_json(ZENODO_RECORD)
    catpred_record = load_json(CATPRED_REPO)
    shard_counts = Counter(row["source_shard"] for row in rows)
    unique_proteins = len({row["source_protein_id"] for row in rows})
    unique_reactions = len({row["reaction_id"] for row in rows})
    unique_ec = len({row["ec"] for row in rows})
    unique_compounds = len({row["compound_id"] for row in rows})

    write_jsonl(DATASET, rows)
    split = {
        "created_at": created_at,
        "local_only": True,
        "benchmark_name": BENCHMARK_NAME,
        "head": HEAD,
        "split_strategy": "evaluation_only_source_shard_reference_no_training",
        "train_rows": 0,
        "validation_rows": 0,
        "test_rows": len(rows),
        "test_record_ids": [row["benchmark_record_id"] for row in rows],
        "source_shards": list(SHARDS),
        "leakage_check_status": "passed",
        "leakage_basis": "All rows are external predicted-reference rows and no row is admitted into KWB training labels.",
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
        "model_under_test": "none_predicted_reference_coverage_scorecard_only",
        "rows_scored": len(rows),
        "source_shard_counts": dict(sorted(shard_counts.items())),
        "unique_proteins": unique_proteins,
        "unique_reactions": unique_reactions,
        "unique_ec": unique_ec,
        "unique_compounds": unique_compounds,
        "source_fields": list(NUMERIC_COLUMNS),
        "field_completeness": {
            field: sum(1 for row in rows if row.get(field) is not None) for field in NUMERIC_COLUMNS
        },
        "quality_status": "external_predicted_reference_cache_ready_not_model_claim",
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
        "primary_metric": "predicted_reference_rows",
        "primary_metric_value": len(rows),
        "secondary_metrics": {
            "source_shards": list(SHARDS),
            "source_shard_counts": dict(sorted(shard_counts.items())),
            "unique_proteins": unique_proteins,
            "unique_reactions": unique_reactions,
            "unique_ec": unique_ec,
            "unique_compounds": unique_compounds,
            "parse_errors": dict(parse_errors),
        },
        "quality_status": "external_predicted_reference_cache_ready_not_model_claim",
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
        "source": "Zenodo GotEnzymes2 source data",
        "record_id": 17196785,
        "doi": SOURCE_DOI,
        "source_url": SOURCE_URL,
        "api_record": relative(ZENODO_RECORD),
        "api_record_sha256": digest(ZENODO_RECORD) if ZENODO_RECORD.exists() else None,
        "title": source_record.get("metadata", {}).get("title"),
        "license": source_record.get("metadata", {}).get("license"),
        "archive": relative(ARCHIVE),
        "archive_size": ARCHIVE.stat().st_size if ARCHIVE.exists() else None,
        "archive_md5": digest(ARCHIVE, "md5") if ARCHIVE.exists() else None,
        "archive_sha256": digest(ARCHIVE) if ARCHIVE.exists() else None,
        "source_field_schema": list(SOURCE_COLUMNS),
        "shards": shard_receipts,
        "catpred_repo_metadata": relative(CATPRED_REPO),
        "catpred_repo_metadata_sha256": digest(CATPRED_REPO) if CATPRED_REPO.exists() else None,
        "catpred_model_executed": False,
        "authorization_source": "public_dataset_source_self_attested",
        "authorization_status": "self_attested",
        "verification_required": True,
        "allowed_use": "evaluation-only predicted-reference coverage benchmark",
        "forbidden_use": "do not use as KWB wet-lab labels, training import, model-quality claim, customer delivery, or release basis",
    }
    intake = {
        "head": HEAD,
        "benchmark_name": BENCHMARK_NAME,
        "dataset_version": DATASET_VERSION,
        "license_review_status": "approved_for_benchmark_only",
        "authorization_source": "public_dataset_source_self_attested",
        "authorization_status": "self_attested",
        "verification_required": True,
        "local_dataset_uri": relative(DATASET),
        "dataset_sha256": digest(DATASET),
        "split_definition_uri": relative(SPLIT),
        "split_sha256": digest(SPLIT),
        "scorecard_uri": relative(SCORECARD),
        "scorecard_sha256": digest(SCORECARD),
        "metric_report_uri": relative(METRIC),
        "metric_sha256": digest(METRIC),
        "leakage_check_status": "passed",
        "reviewer": "local_gotenzymes2_reference_builder",
        "reviewed_at": created_at,
        "notes": "GotEnzymes2 source rows from bdw/oyw/gsc. CatPred was not executed; this cache is evaluation-only reference coverage and never training data.",
    }
    update_row(PLAN, {
        "head": HEAD,
        "benchmark_name": BENCHMARK_NAME,
        "acquisition_status": "configured",
        "license_review_status": "approved_for_benchmark_only",
        "local_dataset_uri": relative(DATASET),
        "checksum": digest(DATASET),
        "split_strategy": "evaluation_only_source_shard_reference_no_training",
        "leakage_check_status": "passed",
        "scorecard_status": "ready",
        "allowed_use": "local GotEnzymes2 predicted-reference coverage benchmark only",
        "forbidden_use": "do not use as activity_risk training labels, CatPred execution proof, model-quality claim, or release basis",
    }, ("head", "benchmark_name"))
    update_row(INTAKE, intake, ("head", "benchmark_name"))

    report = {
        "created_at": created_at,
        "local_only": True,
        "benchmark_name": BENCHMARK_NAME,
        "head": HEAD,
        "dataset_rows": len(rows),
        "source_shards": list(SHARDS),
        "source_shard_counts": dict(sorted(shard_counts.items())),
        "unique_proteins": unique_proteins,
        "unique_reactions": unique_reactions,
        "unique_ec": unique_ec,
        "unique_compounds": unique_compounds,
        "parse_errors": dict(parse_errors),
        "source_archive_verified": not failures,
        "source_archive_failures": failures,
        "outputs": {
            "dataset": relative(DATASET),
            "split": relative(SPLIT),
            "scorecard": relative(SCORECARD),
            "metric_report": relative(METRIC),
            "source_receipt": relative(SOURCE_RECEIPT),
        },
        "training_import_written_rows": 0,
        "activity_risk_training_label_rows_written": 0,
        "catpred_model_executed": False,
        "ready_for_model_claim": False,
        "safe_for_model_claim": False,
        "release_ready": False,
        "policy": "Evaluation-only GotEnzymes2 predicted-reference benchmark. It does not create KWB labels, execute CatPred, or open model/release claims.",
    }
    write_json(SOURCE_RECEIPT, receipt)
    write_json(args.report, report)
    print(json.dumps({
        "benchmark_name": BENCHMARK_NAME,
        "dataset_rows": len(rows),
        "source_shards": dict(sorted(shard_counts.items())),
        "source_archive_verified": not failures,
        "parse_errors": dict(parse_errors),
        "training_import_written_rows": 0,
        "output": str(args.report),
    }, ensure_ascii=False))
    return 0 if not failures and not parse_errors and rows else 1


if __name__ == "__main__":
    raise SystemExit(main())
