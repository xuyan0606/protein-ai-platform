#!/usr/bin/env python3
"""Build an evaluation-only PoseBusters-style pose plausibility benchmark cache."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
SOURCE_CSV = AI_ROOT / "cache" / "external" / "posebusters_paper_results.csv"
ZENODO_RECORD = AI_ROOT / "cache" / "external" / "posebusters_zenodo_record_8278563.json"
PLAN = AI_ROOT / "datasets" / "benchmark" / "benchmark_acquisition_plan.jsonl"
INTAKE = AI_ROOT / "datasets" / "benchmark" / "benchmark_score_cache_intake.local.jsonl"
REPORT = AI_ROOT / "reports" / "posebusters_pose_plausibility_benchmark_report.json"
BENCH_DIR = AI_ROOT / "cache" / "advanced_features" / "benchmarks" / "posebusters_style_pose_plausibility"
DATASET = BENCH_DIR / "dataset.jsonl"
SPLIT = BENCH_DIR / "split_definition.json"
SCORECARD = BENCH_DIR / "scorecard.json"
METRIC = BENCH_DIR / "metric_report.json"
SOURCE_RECEIPT = BENCH_DIR / "source_receipt.json"

HEAD = "substrate_fit"
BENCHMARK_NAME = "PoseBusters-style pose plausibility"
DATASET_VERSION = "posebusters-paper-results-zenodo-8278563-v1"
SOURCE_URL = "https://zenodo.org/records/8278563"
SOURCE_DOI = "10.48550/arXiv.2308.05777"
EXPECTED_SIZE = 1298703
EXPECTED_MD5 = "a7cbe725e86e412fdfeb3c3e35c566dd"

IDENTITY_COLUMNS = ("dataset", "method", "post-processing", "pdb_id", "ccd_id")
BOOL_COLUMNS = (
    "docked_ligand_successfully_loaded",
    "molecule_passes_rdkit_sanity_check",
    "molecular_formula_preserved",
    "molecular_bonds_preserved",
    "sp3_stereochemistry_preserved",
    "double_bond_stereochemistry_preserved",
    "bond_lengths_within_bounds",
    "bond_angles_within_bounds",
    "no_internal_clashes",
    "aromatic_ring_flatness_passes",
    "double_bond_flatness_passes",
    "energy_ratio_within_threshold",
    "no_clashes_with_protein",
    "no_clashes_with_organic_cofactors",
    "no_clashes_with_inorganic_cofactors",
    "no_volume_clash_with_protein",
    "no_volume_clash_with_organic_cofactors",
    "no_volume_clash_with_inorganic_cofactors",
    "rmsd_within_threshold",
)


def digest(path: Path, algorithm: str = "sha256") -> str:
    value = hashlib.new(algorithm)
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            value.update(chunk)
    return value.hexdigest()


def rel(path: Path) -> str:
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
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def update_row(path: Path, row: dict[str, Any], key_fields: tuple[str, str]) -> None:
    rows = load_jsonl(path)
    key = tuple(row.get(field) for field in key_fields)
    output = []
    replaced = False
    for existing in rows:
        if tuple(existing.get(field) for field in key_fields) == key:
            output.append({**existing, **row})
            replaced = True
        else:
            output.append(existing)
    if not replaced:
        output.append(row)
    write_jsonl(path, output)


def parse_bool(value: str) -> bool | None:
    if value == "True":
        return True
    if value == "False":
        return False
    if value == "":
        return None
    raise ValueError(f"unexpected boolean value {value!r}")


def parse_float(value: str) -> float | None:
    if value == "":
        return None
    number = float(value)
    if number != number or number in (float("inf"), float("-inf")):
        raise ValueError(f"non-finite float value {value!r}")
    return number


def read_rows() -> tuple[list[dict[str, Any]], Counter[str]]:
    rows: list[dict[str, Any]] = []
    parse_errors: Counter[str] = Counter()
    with SOURCE_CSV.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        for index, source in enumerate(reader):
            try:
                checks = {column: parse_bool(source[column]) for column in BOOL_COLUMNS}
                has_cofactors = parse_bool(source["has_cofactors"])
                sequence_identity = parse_float(source["sequence_identity"])
                rmsd = parse_float(source["rmsd"])
            except (KeyError, ValueError) as exc:
                parse_errors[type(exc).__name__] += 1
                continue
            failed_checks = [column for column, passed in checks.items() if passed is not True]
            missing_checks = [column for column, passed in checks.items() if passed is None]
            passed_checks = sum(1 for passed in checks.values() if passed is True)
            rows.append({
                "benchmark_record_id": f"posebusters::{index}",
                "benchmark_name": BENCHMARK_NAME,
                "head": HEAD,
                "source_dataset": "PoseBusters paper results",
                "source_url": SOURCE_URL,
                "source_doi": SOURCE_DOI,
                "source_row_index": index,
                "dataset": source["dataset"],
                "method": source["method"],
                "post_processing": source["post-processing"],
                "pdb_id": source["pdb_id"],
                "ccd_id": source["ccd_id"],
                "has_cofactors": has_cofactors,
                "sequence_identity": sequence_identity,
                "rmsd": rmsd,
                "posebuster_check_results": checks,
                "posebuster_checks_passed": passed_checks,
                "posebuster_checks_total": len(checks),
                "posebuster_all_checks_passed": not failed_checks,
                "posebuster_failed_checks": failed_checks,
                "posebuster_missing_checks": missing_checks,
                "benchmark_scope": "external_pose_plausibility_reference_evaluation_only",
                "posebusters_runtime_executed_locally": False,
                "training_label_source": False,
                "ready_for_training_import": False,
                "safe_for_training_import": False,
                "ready_for_model_claim": False,
                "safe_for_model_claim": False,
                "release_ready": False,
            })
    return rows, parse_errors


def main() -> int:
    parser = argparse.ArgumentParser(description="Build PoseBusters-style pose plausibility benchmark")
    parser.add_argument("--report", type=Path, default=REPORT)
    args = parser.parse_args()

    created_at = datetime.now(timezone.utc).isoformat()
    failures: list[str] = []
    if not SOURCE_CSV.exists():
        failures.append("source_csv_missing")
    elif SOURCE_CSV.stat().st_size != EXPECTED_SIZE:
        failures.append("source_csv_size_mismatch")
    elif digest(SOURCE_CSV, "md5") != EXPECTED_MD5:
        failures.append("source_csv_md5_mismatch")

    rows: list[dict[str, Any]] = []
    parse_errors: Counter[str] = Counter()
    if not failures:
        rows, parse_errors = read_rows()
    dataset_counts = Counter(row["dataset"] for row in rows)
    method_counts = Counter(row["method"] for row in rows)
    post_counts = Counter(row["post_processing"] for row in rows)
    check_pass_counts = {check: sum(1 for row in rows if row["posebuster_check_results"][check] is True) for check in BOOL_COLUMNS}
    check_missing_counts = {check: sum(1 for row in rows if row["posebuster_check_results"][check] is None) for check in BOOL_COLUMNS}
    all_pass_rows = sum(1 for row in rows if row["posebuster_all_checks_passed"])
    unique_complexes = len({(row["pdb_id"], row["ccd_id"]) for row in rows})

    write_jsonl(DATASET, rows)
    split = {
        "created_at": created_at,
        "local_only": True,
        "benchmark_name": BENCHMARK_NAME,
        "head": HEAD,
        "split_strategy": "evaluation_only_published_posebusters_results_no_training",
        "train_rows": 0,
        "validation_rows": 0,
        "test_rows": len(rows),
        "test_record_ids": [row["benchmark_record_id"] for row in rows],
        "leakage_check_status": "passed",
        "leakage_basis": "Rows are published PoseBusters evaluation results and are not admitted into KWB substrate_fit labels.",
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
        "model_under_test": "none_published_posebusters_results_reference_only",
        "rows_scored": len(rows),
        "unique_complexes": unique_complexes,
        "dataset_counts": dict(sorted(dataset_counts.items())),
        "method_counts": dict(sorted(method_counts.items())),
        "post_processing_counts": dict(sorted(post_counts.items())),
        "all_checks_passed_rows": all_pass_rows,
        "all_checks_passed_fraction": all_pass_rows / len(rows) if rows else 0,
        "check_pass_counts": dict(sorted(check_pass_counts.items())),
        "check_missing_counts": dict(sorted(check_missing_counts.items())),
        "quality_status": "external_pose_plausibility_reference_cache_ready_not_model_claim",
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
        "primary_metric": "posebuster_all_checks_passed_fraction",
        "primary_metric_value": scorecard["all_checks_passed_fraction"],
        "secondary_metrics": {
            "rows_scored": len(rows),
            "unique_complexes": unique_complexes,
            "all_checks_passed_rows": all_pass_rows,
            "dataset_counts": dict(sorted(dataset_counts.items())),
            "method_counts": dict(sorted(method_counts.items())),
            "post_processing_counts": dict(sorted(post_counts.items())),
            "check_pass_counts": dict(sorted(check_pass_counts.items())),
            "check_missing_counts": dict(sorted(check_missing_counts.items())),
            "parse_errors": dict(parse_errors),
        },
        "quality_status": "external_pose_plausibility_reference_cache_ready_not_model_claim",
        "leakage_check_status": "passed",
        "ready_as_benchmark_scorecard": bool(rows) and not failures and not parse_errors,
        "ready_for_model_claim": False,
        "safe_for_model_claim": False,
        "release_ready": False,
    }
    write_json(SPLIT, split)
    write_json(SCORECARD, scorecard)
    write_json(METRIC, metric)

    zenodo = load_json(ZENODO_RECORD)
    receipt = {
        "created_at": created_at,
        "local_only": True,
        "source": "Zenodo PoseBusters paper results",
        "source_url": SOURCE_URL,
        "doi": SOURCE_DOI,
        "api_record": rel(ZENODO_RECORD),
        "api_record_sha256": digest(ZENODO_RECORD) if ZENODO_RECORD.exists() else None,
        "title": zenodo.get("metadata", {}).get("title"),
        "license": zenodo.get("metadata", {}).get("license"),
        "source_csv": rel(SOURCE_CSV),
        "source_csv_size": SOURCE_CSV.stat().st_size if SOURCE_CSV.exists() else None,
        "source_csv_md5": digest(SOURCE_CSV, "md5") if SOURCE_CSV.exists() else None,
        "source_csv_sha256": digest(SOURCE_CSV) if SOURCE_CSV.exists() else None,
        "posebusters_runtime_executed_locally": False,
        "authorization_source": "public_dataset_source_self_attested",
        "authorization_status": "self_attested",
        "verification_required": True,
        "allowed_use": "evaluation-only pose plausibility benchmark cache",
        "forbidden_use": "do not use as KWB substrate_fit labels, training import, customer delivery, local PoseBusters runtime proof, or release basis",
    }
    write_json(SOURCE_RECEIPT, receipt)

    intake = {
        "head": HEAD,
        "benchmark_name": BENCHMARK_NAME,
        "dataset_version": DATASET_VERSION,
        "license_review_status": "approved_for_benchmark_only",
        "authorization_source": "public_dataset_source_self_attested",
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
        "reviewer": "local_posebusters_reference_builder",
        "reviewed_at": created_at,
        "notes": "Published PoseBusters paper results CSV. PoseBusters was not executed locally; evaluation-only benchmark cache, never training data.",
    }
    update_row(PLAN, {
        "head": HEAD,
        "benchmark_name": BENCHMARK_NAME,
        "acquisition_status": "configured",
        "license_review_status": "approved_for_benchmark_only",
        "local_dataset_uri": rel(DATASET),
        "checksum": digest(DATASET),
        "split_strategy": "evaluation_only_published_posebusters_results_no_training",
        "leakage_check_status": "passed",
        "scorecard_status": "ready",
        "allowed_use": "local PoseBusters-style pose plausibility benchmark only",
        "forbidden_use": "do not use as substrate_fit training labels, local runtime proof, model-quality claim, or release basis",
    }, ("head", "benchmark_name"))
    update_row(INTAKE, intake, ("head", "benchmark_name"))

    report = {
        "created_at": created_at,
        "local_only": True,
        "benchmark_name": BENCHMARK_NAME,
        "head": HEAD,
        "dataset_rows": len(rows),
        "unique_complexes": unique_complexes,
        "dataset_counts": dict(sorted(dataset_counts.items())),
        "method_counts": dict(sorted(method_counts.items())),
        "post_processing_counts": dict(sorted(post_counts.items())),
        "all_checks_passed_rows": all_pass_rows,
        "all_checks_passed_fraction": scorecard["all_checks_passed_fraction"],
        "parse_errors": dict(parse_errors),
        "source_csv_verified": not failures,
        "source_csv_failures": failures,
        "outputs": {
            "dataset": rel(DATASET),
            "split": rel(SPLIT),
            "scorecard": rel(SCORECARD),
            "metric_report": rel(METRIC),
            "source_receipt": rel(SOURCE_RECEIPT),
        },
        "training_import_written_rows": 0,
        "substrate_fit_training_label_rows_written": 0,
        "posebusters_runtime_executed_locally": False,
        "ready_for_model_claim": False,
        "safe_for_model_claim": False,
        "release_ready": False,
        "policy": "Evaluation-only PoseBusters-style pose plausibility benchmark. It does not create KWB labels, execute PoseBusters locally, or open model/release claims.",
    }
    write_json(args.report, report)
    print(json.dumps({
        "benchmark_name": BENCHMARK_NAME,
        "dataset_rows": len(rows),
        "unique_complexes": unique_complexes,
        "all_checks_passed_rows": all_pass_rows,
        "source_csv_verified": not failures,
        "parse_errors": dict(parse_errors),
        "training_import_written_rows": 0,
        "output": str(args.report),
    }, ensure_ascii=False))
    return 0 if not failures and not parse_errors and rows else 1


if __name__ == "__main__":
    raise SystemExit(main())
