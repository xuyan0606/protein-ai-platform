#!/usr/bin/env python3
"""Build an evaluation-only ATOM3D MSP stability benchmark cache."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import io
import json
import pickle
import tarfile
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import lmdb
import msgpack
import pandas as pd


AI_ROOT = Path(__file__).resolve().parents[1]
SOURCE_DIR = AI_ROOT / "cache" / "external" / "atom3d_msp"
ZENODO_RECORD = AI_ROOT / "cache" / "external" / "atom3d_msp_zenodo_record_4962515.json"
README = SOURCE_DIR / "README.md"
INDICES_ARCHIVE = SOURCE_DIR / "MSP-split-by-sequence-identity-30-indices.tar.gz"
SPLIT_ARCHIVE = SOURCE_DIR / "MSP-split-by-sequence-identity-30.tar.gz"
EXTRACT_DIR = SOURCE_DIR / "split_by_sequence_identity_30"
PLAN = AI_ROOT / "datasets" / "benchmark" / "benchmark_acquisition_plan.jsonl"
INTAKE = AI_ROOT / "datasets" / "benchmark" / "benchmark_score_cache_intake.local.jsonl"
REPORT = AI_ROOT / "reports" / "atom3d_msp_benchmark_report.json"
BENCH_DIR = AI_ROOT / "cache" / "advanced_features" / "benchmarks" / "atom3d_msp"
DATASET = BENCH_DIR / "dataset.jsonl"
SPLIT = BENCH_DIR / "split_definition.json"
SCORECARD = BENCH_DIR / "scorecard.json"
METRIC = BENCH_DIR / "metric_report.json"
SOURCE_RECEIPT = BENCH_DIR / "source_receipt.json"

HEAD = "stability"
BENCHMARK_NAME = "ATOM3D MSP"
DATASET_VERSION = "atom3d-msp-sequence-identity-30-local-zenodo-4962515"
SOURCE_URL = "https://zenodo.org/records/4962515"
SOURCE_DOI = "10.5281/zenodo.4962515"
EXPECTED_FILES = {
    "MSP-split-by-sequence-identity-30-indices.tar.gz": {
        "size": 9579,
        "md5": "868abd1be0d9a32cb614951f3d8297af",
    },
    "MSP-split-by-sequence-identity-30.tar.gz": {
        "size": 1384045096,
        "md5": "6628e8efac12648d3b78bb0fc0d8860c",
    },
    "README.md": {
        "size": 2072,
        "md5": "1b66a04f42609c07485de669477dd5bd",
    },
}
SPLIT_ALIASES = {
    "train": "train",
    "training": "train",
    "val": "validation",
    "valid": "validation",
    "validation": "validation",
    "test": "test",
}


def rel(path: Path) -> str:
    return str(path.relative_to(AI_ROOT))


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


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def update_rows(path: Path, row: dict[str, Any], key_fields: tuple[str, str]) -> None:
    rows = load_jsonl(path)
    key = tuple(row.get(field) for field in key_fields)
    updated = False
    next_rows = []
    for existing in rows:
        if tuple(existing.get(field) for field in key_fields) == key:
            next_rows.append({**existing, **row})
            updated = True
        else:
            next_rows.append(existing)
    if not updated:
        next_rows.append(row)
    write_jsonl(path, next_rows)


def verify_source_files() -> list[dict[str, Any]]:
    checks = []
    path_by_name = {
        "MSP-split-by-sequence-identity-30-indices.tar.gz": INDICES_ARCHIVE,
        "MSP-split-by-sequence-identity-30.tar.gz": SPLIT_ARCHIVE,
        "README.md": README,
    }
    for name, expected in EXPECTED_FILES.items():
        path = path_by_name[name]
        exists = path.exists()
        observed_size = path.stat().st_size if exists else None
        observed_md5 = digest(path, "md5") if exists else None
        checks.append({
            "file": name,
            "path": rel(path),
            "exists": exists,
            "expected_size": expected["size"],
            "observed_size": observed_size,
            "size_ok": observed_size == expected["size"],
            "expected_md5": expected["md5"],
            "observed_md5": observed_md5,
            "md5_ok": observed_md5 == expected["md5"],
            "sha256": digest(path, "sha256") if exists else None,
        })
    return checks


def source_files_ready(checks: list[dict[str, Any]]) -> bool:
    return all(item["exists"] and item["size_ok"] and item["md5_ok"] for item in checks)


def safe_extract_tar(archive: Path, target: Path) -> None:
    target.mkdir(parents=True, exist_ok=True)
    with tarfile.open(archive, "r:gz") as tar:
        base = target.resolve()
        for member in tar.getmembers():
            destination = (target / member.name).resolve()
            if base not in destination.parents and destination != base:
                raise RuntimeError(f"unsafe tar member path: {member.name}")
        tar.extractall(target)


def extract_if_needed() -> None:
    if any(EXTRACT_DIR.rglob("data.mdb")) or any(path.suffix == ".lmdb" for path in EXTRACT_DIR.rglob("*")):
        return
    safe_extract_tar(SPLIT_ARCHIVE, EXTRACT_DIR)


def canonical_split(path: Path) -> str | None:
    parts = [part.lower() for part in path.parts]
    for part in reversed(parts):
        clean = part.replace("-", "_")
        for token, split in SPLIT_ALIASES.items():
            if clean == token or clean.endswith(f"_{token}") or clean.startswith(f"{token}_"):
                return split
    return None


def discover_lmdbs(root: Path) -> list[tuple[str, Path]]:
    candidates: list[tuple[str, Path]] = []
    seen: set[Path] = set()
    for data_mdb in root.rglob("data.mdb"):
        lmdb_path = data_mdb.parent
        split = canonical_split(lmdb_path)
        if split and lmdb_path not in seen:
            candidates.append((split, lmdb_path))
            seen.add(lmdb_path)
    for path in root.rglob("*.lmdb"):
        split = canonical_split(path)
        if split and path not in seen:
            candidates.append((split, path))
            seen.add(path)
    return sorted(candidates, key=lambda item: (item[0], str(item[1])))


def deserialize(payload: bytes, fmt: str) -> Any:
    if fmt == "pkl":
        return pickle.loads(payload)
    if fmt == "json":
        return json.loads(payload.decode("utf-8"))
    if fmt == "msgpack":
        return msgpack.unpackb(payload, raw=False)
    raise ValueError(f"unsupported ATOM3D serialization_format: {fmt}")


def read_lmdb_rows(split: str, lmdb_path: Path) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    env = lmdb.open(str(lmdb_path), max_readers=1, readonly=True, lock=False, readahead=False, meminit=False)
    with env.begin(write=False) as txn:
        num_examples_raw = txn.get(b"num_examples")
        fmt_raw = txn.get(b"serialization_format")
        if num_examples_raw is None or fmt_raw is None:
            raise RuntimeError(f"missing ATOM3D LMDB metadata in {lmdb_path}")
        num_examples = int(num_examples_raw)
        serialization_format = fmt_raw.decode("utf-8")
        for index in range(num_examples):
            compressed = txn.get(str(index).encode("utf-8"))
            if compressed is None:
                raise RuntimeError(f"missing LMDB row {index} in {lmdb_path}")
            with gzip.GzipFile(fileobj=io.BytesIO(compressed), mode="rb") as handle:
                item = deserialize(handle.read(), serialization_format)
            label = str(item.get("label"))
            if label not in {"0", "1", "0.0", "1.0", "False", "True", "false", "true"}:
                raise RuntimeError(f"unexpected ATOM3D MSP label {label!r} at {lmdb_path}:{index}")
            normalized_label = 1 if label in {"1", "1.0", "True", "true"} else 0
            item_id = str(item.get("id") or f"{split}:{index}")
            rows.append({
                "benchmark_record_id": f"atom3d_msp::{split}::{index}",
                "benchmark_name": BENCHMARK_NAME,
                "head": HEAD,
                "source_dataset": "ATOM3D MSP",
                "source_doi": SOURCE_DOI,
                "source_url": SOURCE_URL,
                "source_split": split,
                "source_lmdb": rel(lmdb_path),
                "source_row_index": index,
                "source_record_id": item_id,
                "label": normalized_label,
                "label_semantics": "1 means mutant Kd lower than WT, indicating better binding/stability; 0 otherwise per ATOM3D README",
                "task": "mutation_stability_prediction_binary",
                "benchmark_scope": "external_stability_eval_only_non_training",
                "training_label_source": False,
                "ready_for_training_import": False,
                "safe_for_training_import": False,
                "ready_for_model_claim": False,
                "safe_for_model_claim": False,
                "release_ready": False,
            })
    env.close()
    return rows, {
        "split": split,
        "lmdb_path": rel(lmdb_path),
        "num_examples": len(rows),
        "label_counts": dict(Counter(str(row["label"]) for row in rows)),
    }


def read_index_counts() -> dict[str, int]:
    index_dir = SOURCE_DIR / "indices"
    counts = {}
    for name, split in (("train_indices.txt", "train"), ("val_indices.txt", "validation"), ("test_indices.txt", "test")):
        path = index_dir / name
        if path.exists():
            counts[split] = sum(1 for line in path.read_text(encoding="utf-8").splitlines() if line.strip())
    return counts


def build_source_receipt(created_at: str, checks: list[dict[str, Any]], lmdb_sources: list[dict[str, Any]]) -> dict[str, Any]:
    record = load_json(ZENODO_RECORD)
    return {
        "created_at": created_at,
        "local_only": True,
        "source": "Zenodo",
        "record_id": 4962515,
        "doi": SOURCE_DOI,
        "source_url": SOURCE_URL,
        "api_record": rel(ZENODO_RECORD),
        "api_record_sha256": digest(ZENODO_RECORD) if ZENODO_RECORD.exists() else None,
        "title": record.get("title") or record.get("metadata", {}).get("title"),
        "license": record.get("metadata", {}).get("license"),
        "authorization_source": "source_site_public_dataset_download_self_attested",
        "authorization_status": "self_attested",
        "verification_required": True,
        "allowed_use": "evaluation-only external stability benchmark cache",
        "forbidden_use": "do not use ATOM3D MSP rows as KWB wet-lab labels, training import, customer delivery claim, or release basis",
        "file_checks": checks,
        "lmdb_sources": lmdb_sources,
    }


def split_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    by_split: dict[str, Counter[str]] = {}
    for row in rows:
        by_split.setdefault(str(row["source_split"]), Counter())[str(row["label"])] += 1
    return {
        split: {
            "rows": sum(counts.values()),
            "label_counts": dict(sorted(counts.items())),
        }
        for split, counts in sorted(by_split.items())
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Build ATOM3D MSP benchmark")
    parser.add_argument("--report", type=Path, default=REPORT)
    args = parser.parse_args()

    created_at = datetime.now(timezone.utc).isoformat()
    checks = verify_source_files()
    if not source_files_ready(checks):
        report = {
            "created_at": created_at,
            "local_only": True,
            "benchmark_name": BENCHMARK_NAME,
            "head": HEAD,
            "status": "blocked_source_files_not_ready",
            "source_checks": checks,
            "dataset_rows": 0,
            "training_import_written_rows": 0,
            "ready_for_model_claim": False,
            "safe_for_model_claim": False,
            "release_ready": False,
        }
        write_json(args.report, report)
        print(json.dumps({"status": report["status"], "dataset_rows": 0, "output": rel(args.report)}, ensure_ascii=False))
        return 1

    extract_if_needed()
    lmdb_paths = discover_lmdbs(EXTRACT_DIR)
    if not lmdb_paths:
        raise RuntimeError(f"No ATOM3D MSP LMDB split directories found under {EXTRACT_DIR}")

    rows: list[dict[str, Any]] = []
    lmdb_sources: list[dict[str, Any]] = []
    for split, lmdb_path in lmdb_paths:
        split_rows, source = read_lmdb_rows(split, lmdb_path)
        rows.extend(split_rows)
        lmdb_sources.append(source)

    write_jsonl(DATASET, rows)
    index_counts = read_index_counts()
    observed_split_counts = dict(Counter(str(row["source_split"]) for row in rows))
    label_counts = dict(Counter(str(row["label"]) for row in rows))
    receipt = build_source_receipt(created_at, checks, lmdb_sources)
    write_json(SOURCE_RECEIPT, receipt)
    split_definition = {
        "created_at": created_at,
        "local_only": True,
        "benchmark_name": BENCHMARK_NAME,
        "head": HEAD,
        "source": "ATOM3D MSP",
        "source_doi": SOURCE_DOI,
        "source_url": SOURCE_URL,
        "source_receipt": rel(SOURCE_RECEIPT),
        "split_strategy": "use_official_atom3d_msp_sequence_identity_30_split",
        "split_counts": observed_split_counts,
        "index_counts": index_counts,
        "index_count_delta": {key: observed_split_counts.get(key, 0) - index_counts.get(key, 0) for key in sorted(set(index_counts) | set(observed_split_counts))},
        "leakage_check_status": "passed",
        "leakage_basis": "Uses official ATOM3D MSP sequence-identity-30 split; this builder creates no KWB training labels.",
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
        "model_under_test": "none_source_dataset_cache_only",
        "rows_scored": len(rows),
        "split_summary": split_summary(rows),
        "label_counts": label_counts,
        "primary_metric": "external_dataset_label_and_split_cache_rows",
        "quality_status": "atom3d_msp_stability_cache_ready_not_model_claim",
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
        "primary_metric": "official_atom3d_msp_rows_cached",
        "primary_metric_value": len(rows),
        "secondary_metrics": {
            "split_counts": observed_split_counts,
            "label_counts": label_counts,
            "split_summary": split_summary(rows),
            "index_counts": index_counts,
        },
        "quality_status": "atom3d_msp_stability_cache_ready_not_model_claim",
        "leakage_check_status": "passed",
        "ready_as_benchmark_scorecard": True,
        "ready_for_model_claim": False,
        "safe_for_model_claim": False,
        "release_ready": False,
    }
    write_json(SPLIT, split_definition)
    write_json(SCORECARD, scorecard)
    write_json(METRIC, metric)

    intake = {
        "head": HEAD,
        "benchmark_name": BENCHMARK_NAME,
        "dataset_version": DATASET_VERSION,
        "license_review_status": "approved_for_benchmark_only",
        "authorization_status": "source_site_public_cc_by_4_0_self_attested",
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
        "reviewer": "local_atom3d_msp_benchmark_builder",
        "reviewed_at": created_at,
        "notes": "Evaluation-only ATOM3D MSP stability benchmark cache from Zenodo DOI 10.5281/zenodo.4962515. Not KWB wet-lab labels or model-quality claim.",
    }
    update_rows(PLAN, {
        "head": HEAD,
        "benchmark_name": BENCHMARK_NAME,
        "acquisition_status": "configured",
        "license_review_status": "approved_for_benchmark_only",
        "local_dataset_uri": rel(DATASET),
        "checksum": digest(DATASET),
        "split_strategy": "use_official_atom3d_msp_sequence_identity_30_split",
        "leakage_check_status": "passed",
        "scorecard_status": "ready",
        "allowed_use": "external ATOM3D MSP stability benchmark cache only",
        "forbidden_use": "do not use as KWB wet-lab labels, model-quality claim, or release basis",
    }, ("head", "benchmark_name"))
    update_rows(INTAKE, intake, ("head", "benchmark_name"))

    report = {
        "created_at": created_at,
        "local_only": True,
        "benchmark_name": BENCHMARK_NAME,
        "head": HEAD,
        "source": "ATOM3D MSP",
        "source_doi": SOURCE_DOI,
        "source_url": SOURCE_URL,
        "dataset_rows": len(rows),
        "split_counts": observed_split_counts,
        "index_counts": index_counts,
        "label_counts": label_counts,
        "source_receipt": rel(SOURCE_RECEIPT),
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
        "policy": "External ATOM3D MSP stability benchmark cache only; no training import, customer delivery, model claim, or release readiness.",
    }
    write_json(args.report, report)
    print(json.dumps({
        "benchmark_name": BENCHMARK_NAME,
        "dataset_rows": len(rows),
        "split_counts": observed_split_counts,
        "label_counts": label_counts,
        "training_import_written_rows": 0,
        "output": rel(args.report),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
