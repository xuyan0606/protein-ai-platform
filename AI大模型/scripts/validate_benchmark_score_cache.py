#!/usr/bin/env python3
"""Validate local benchmark score cache manifest."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
MANIFEST = AI_ROOT / "reports" / "benchmark_score_cache_manifest.json"
OUT = AI_ROOT / "reports" / "benchmark_score_cache_validation_report.json"

def resolve(value: Any) -> Path | None:
    if not value:
        return None
    path = Path(str(value))
    return path if path.is_absolute() else AI_ROOT / path


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def jsonl_row_count(path: Path) -> int | None:
    try:
        rows = [line for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    except OSError:
        return None
    return len(rows)


def validate_file(row: dict[str, Any], path_key: str, hash_key: str) -> list[str]:
    errors = []
    path = resolve(row.get(path_key))
    expected = str(row.get(hash_key) or "")
    if not path or not path.exists():
        errors.append(f"{path_key}_missing")
    elif expected and sha256(path) != expected.lower():
        errors.append(f"{hash_key}_mismatch")
    elif not expected:
        errors.append(f"{hash_key}_missing")
    return errors


def validate_row(row: dict[str, Any]) -> list[str]:
    errors = []
    if row.get("status") != "present":
        return ["benchmark_status_not_present"]
    if not row.get("dataset_version"):
        errors.append("dataset_version_missing")
    if row.get("leakage_check_status") != "passed":
        errors.append("leakage_check_not_passed")
    errors.extend(validate_file(row, "local_dataset_uri", "dataset_sha256"))
    errors.extend(validate_file(row, "split_definition_uri", "split_sha256"))
    errors.extend(validate_file(row, "scorecard_uri", "scorecard_sha256"))
    errors.extend(validate_file(row, "metric_report_uri", "metric_sha256"))
    dataset_path = resolve(row.get("local_dataset_uri"))
    if dataset_path and dataset_path.exists():
        dataset_rows = jsonl_row_count(dataset_path)
        if dataset_rows is None:
            errors.append("dataset_jsonl_unreadable")
        elif dataset_rows <= 0:
            errors.append("dataset_jsonl_empty")
    split_path = resolve(row.get("split_definition_uri"))
    if split_path and split_path.exists():
        split = load_json(split_path)
        if split.get("leakage_check_status") not in (None, "passed"):
            errors.append("split_leakage_check_not_passed")
    metric_path = resolve(row.get("metric_report_uri"))
    if metric_path and metric_path.exists():
        metric = load_json(metric_path)
        metric_rows = metric.get("dataset_rows")
        if isinstance(metric_rows, int) and not isinstance(metric_rows, bool) and metric_rows <= 0:
            errors.append("metric_dataset_rows_not_positive")
        if metric.get("ready_as_benchmark_scorecard") is False:
            errors.append("metric_not_ready_as_benchmark_scorecard")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate benchmark score cache")
    parser.add_argument("--manifest", type=Path, default=MANIFEST)
    parser.add_argument("--output", type=Path, default=OUT)
    args = parser.parse_args()

    manifest = load_json(args.manifest)
    rows = manifest.get("rows") if isinstance(manifest.get("rows"), list) else []
    records = []
    counts: Counter[str] = Counter()
    head_totals: defaultdict[str, int] = defaultdict(int)
    head_valid: defaultdict[str, int] = defaultdict(int)
    for row in rows:
        head = str(row.get("head") or "unknown")
        head_totals[head] += 1
        errors = validate_row(row)
        counts.update(errors)
        if not errors:
            head_valid[head] += 1
        records.append({
            "head": row.get("head"),
            "benchmark_name": row.get("benchmark_name"),
            "valid": not errors,
            "errors": errors,
        })
    valid_rows = sum(1 for row in records if row["valid"])
    head_scorecards = {
        head: {
            "expected_rows": head_totals[head],
            "valid_rows": head_valid[head],
            "ready": head_totals[head] > 0 and head_totals[head] == head_valid[head],
        }
        for head in sorted(head_totals)
    }
    ready = bool(rows) and valid_rows == len(rows) and manifest.get("status") == "ready"
    report = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "local_only": True,
        "manifest": str(args.manifest),
        "benchmark_rows": len(rows),
        "valid_rows": valid_rows,
        "invalid_rows": len(rows) - valid_rows,
        "head_scorecards": head_scorecards,
        "heads_ready": sum(1 for item in head_scorecards.values() if item["ready"]),
        "error_counts": dict(counts),
        "ready_for_model_claim": ready,
        "safe_for_model_claim": False,
        "records": records[:200],
        "policy": "Benchmark validation is an evaluation gate only. It does not supply KWB wet-lab labels or production approval.",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "ready_for_model_claim": report["ready_for_model_claim"],
        "valid_rows": report["valid_rows"],
        "invalid_rows": report["invalid_rows"],
        "heads_ready": report["heads_ready"],
        "output": str(args.output),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
