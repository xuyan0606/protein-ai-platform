#!/usr/bin/env python3
"""Validate the evaluation-only ATOM3D MSP stability benchmark cache."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
SOURCE_DIR = AI_ROOT / "cache" / "external" / "atom3d_msp"
ZENODO_RECORD = AI_ROOT / "cache" / "external" / "atom3d_msp_zenodo_record_4962515.json"
README = SOURCE_DIR / "README.md"
INDICES_ARCHIVE = SOURCE_DIR / "MSP-split-by-sequence-identity-30-indices.tar.gz"
SPLIT_ARCHIVE = SOURCE_DIR / "MSP-split-by-sequence-identity-30.tar.gz"
BENCH_DIR = AI_ROOT / "cache" / "advanced_features" / "benchmarks" / "atom3d_msp"
DATASET = BENCH_DIR / "dataset.jsonl"
SPLIT = BENCH_DIR / "split_definition.json"
SCORECARD = BENCH_DIR / "scorecard.json"
METRIC = BENCH_DIR / "metric_report.json"
SOURCE_RECEIPT = BENCH_DIR / "source_receipt.json"
REPORT = AI_ROOT / "reports" / "atom3d_msp_benchmark_report.json"
INTAKE = AI_ROOT / "datasets" / "benchmark" / "benchmark_score_cache_intake.local.jsonl"
OUT = AI_ROOT / "reports" / "atom3d_msp_benchmark_validation_report.json"

HEAD = "stability"
BENCHMARK_NAME = "ATOM3D MSP"
EXPECTED_MD5 = {
    INDICES_ARCHIVE: "868abd1be0d9a32cb614951f3d8297af",
    SPLIT_ARCHIVE: "6628e8efac12648d3b78bb0fc0d8860c",
    README: "1b66a04f42609c07485de669477dd5bd",
}
FALSE_FIELDS = (
    "training_label_source",
    "ready_for_training_import",
    "safe_for_training_import",
    "ready_for_model_claim",
    "safe_for_model_claim",
    "release_ready",
)


def digest(path: Path, algorithm: str = "sha256") -> str:
    h = hashlib.new(algorithm)
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
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        if isinstance(row, str):
            row = json.loads(row)
        rows.append(row)
    return rows


def fail_if(condition: bool, failures: list[dict[str, Any]], check: str, observed: Any, expected: Any) -> None:
    if condition:
        failures.append({"check": check, "observed": observed, "expected": expected})


def find_intake(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return next((row for row in rows if row.get("head") == HEAD and row.get("benchmark_name") == BENCHMARK_NAME), {})


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate ATOM3D MSP benchmark")
    parser.add_argument("--output", type=Path, default=OUT)
    args = parser.parse_args()

    dataset = load_jsonl(DATASET)
    split = load_json(SPLIT)
    scorecard = load_json(SCORECARD)
    metric = load_json(METRIC)
    receipt = load_json(SOURCE_RECEIPT)
    report = load_json(REPORT)
    zenodo = load_json(ZENODO_RECORD)
    intake = find_intake(load_jsonl(INTAKE))
    failures: list[dict[str, Any]] = []

    for path, expected_md5 in EXPECTED_MD5.items():
        fail_if(not path.exists(), failures, f"{path.name}_exists", str(path), "present")
        if path.exists():
            fail_if(digest(path, "md5") != expected_md5, failures, f"{path.name}_md5", digest(path, "md5"), expected_md5)

    fail_if(zenodo.get("doi") != "10.5281/zenodo.4962515", failures, "zenodo_doi", zenodo.get("doi"), "10.5281/zenodo.4962515")
    fail_if(zenodo.get("metadata", {}).get("license", {}).get("id") != "cc-by-4.0", failures, "zenodo_license", zenodo.get("metadata", {}).get("license"), "cc-by-4.0")
    fail_if(receipt.get("authorization_status") != "self_attested", failures, "receipt_authorization_status", receipt.get("authorization_status"), "self_attested")
    fail_if(receipt.get("verification_required") is not True, failures, "receipt_verification_required", receipt.get("verification_required"), True)

    fail_if(len(dataset) < 1000, failures, "dataset_rows_minimum", len(dataset), ">=1000")
    ids = {row.get("benchmark_record_id") for row in dataset}
    fail_if(len(ids) != len(dataset), failures, "record_ids_unique", len(ids), len(dataset))
    split_counts = dict(Counter(str(row.get("source_split")) for row in dataset))
    label_counts = dict(Counter(str(row.get("label")) for row in dataset))
    fail_if(set(split_counts) != {"train", "validation", "test"}, failures, "split_set", sorted(split_counts), ["test", "train", "validation"])
    fail_if(set(label_counts) != {"0", "1"}, failures, "label_set", sorted(label_counts), ["0", "1"])
    for idx, row in enumerate(dataset, start=1):
        fail_if(row.get("head") != HEAD, failures, "row_head", {"row": idx, "value": row.get("head")}, HEAD)
        fail_if(row.get("benchmark_name") != BENCHMARK_NAME, failures, "row_benchmark_name", {"row": idx, "value": row.get("benchmark_name")}, BENCHMARK_NAME)
        fail_if(row.get("benchmark_scope") != "external_stability_eval_only_non_training", failures, "row_scope", {"row": idx, "value": row.get("benchmark_scope")}, "external_stability_eval_only_non_training")
        for field in FALSE_FIELDS:
            fail_if(row.get(field) is not False, failures, f"row_{field}_false", {"row": idx, "value": row.get(field)}, False)

    fail_if(split.get("split_strategy") != "use_official_atom3d_msp_sequence_identity_30_split", failures, "split_strategy", split.get("split_strategy"), "use_official_atom3d_msp_sequence_identity_30_split")
    fail_if(split.get("leakage_check_status") != "passed", failures, "split_leakage_check_status", split.get("leakage_check_status"), "passed")
    fail_if(metric.get("dataset_rows") != len(dataset), failures, "metric_dataset_rows", metric.get("dataset_rows"), len(dataset))
    fail_if(metric.get("ready_as_benchmark_scorecard") is not True, failures, "metric_ready_as_benchmark_scorecard", metric.get("ready_as_benchmark_scorecard"), True)
    fail_if(scorecard.get("rows_scored") != len(dataset), failures, "scorecard_rows_scored", scorecard.get("rows_scored"), len(dataset))
    fail_if(report.get("dataset_rows") != len(dataset), failures, "report_dataset_rows", report.get("dataset_rows"), len(dataset))
    for source in (split, scorecard, metric, report):
        for field in ("ready_for_model_claim", "safe_for_model_claim", "release_ready"):
            fail_if(source.get(field) is not False, failures, f"{field}_false", source.get(field), False)
    fail_if(report.get("training_import_written_rows") != 0, failures, "training_import_written_rows", report.get("training_import_written_rows"), 0)

    fail_if(not intake, failures, "intake_row_present", None, "present")
    if intake:
        expected_hashes = {
            "dataset_sha256": digest(DATASET),
            "split_sha256": digest(SPLIT),
            "scorecard_sha256": digest(SCORECARD),
            "metric_sha256": digest(METRIC),
        }
        for key, expected in expected_hashes.items():
            fail_if(str(intake.get(key) or "").lower() != expected, failures, f"intake_{key}", intake.get(key), expected)
        fail_if(intake.get("license_review_status") != "approved_for_benchmark_only", failures, "intake_license_review_status", intake.get("license_review_status"), "approved_for_benchmark_only")
        fail_if(intake.get("leakage_check_status") != "passed", failures, "intake_leakage_check_status", intake.get("leakage_check_status"), "passed")

    validation = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "local_only": True,
        "benchmark_name": BENCHMARK_NAME,
        "head": HEAD,
        "dataset_rows": len(dataset),
        "split_counts": split_counts,
        "label_counts": label_counts,
        "success": not failures,
        "failures": failures,
        "ready_as_benchmark_scorecard": not failures,
        "training_import_written_rows": 0,
        "ready_for_model_claim": False,
        "safe_for_model_claim": False,
        "release_ready": False,
        "policy": "Evaluation-only ATOM3D MSP stability benchmark. It does not create KWB labels, model claims, or release readiness.",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(validation, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({
        "success": validation["success"],
        "dataset_rows": validation["dataset_rows"],
        "split_counts": validation["split_counts"],
        "label_counts": validation["label_counts"],
        "failures": len(failures),
        "output": str(args.output),
    }, ensure_ascii=False))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
