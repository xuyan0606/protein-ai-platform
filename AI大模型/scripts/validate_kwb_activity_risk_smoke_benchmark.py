#!/usr/bin/env python3
"""Validate KWB activity_risk smoke benchmark artifacts."""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
BENCH_DIR = AI_ROOT / "cache" / "advanced_features" / "benchmarks" / "kwb_activity_numeric_feedback_smoke"
DATASET = BENCH_DIR / "dataset.jsonl"
SPLIT = BENCH_DIR / "split_definition.json"
SCORECARD = BENCH_DIR / "scorecard.json"
METRIC = BENCH_DIR / "metric_report.json"
INTAKE = AI_ROOT / "datasets" / "benchmark" / "benchmark_score_cache_intake.local.jsonl"
REPORT = AI_ROOT / "reports" / "kwb_activity_risk_smoke_benchmark_report.json"
OUT = AI_ROOT / "reports" / "kwb_activity_risk_smoke_benchmark_validation_report.json"

HEAD = "activity_risk"
BENCHMARK_NAME = "KWB activity numeric feedback smoke"
EXPECTED_ROWS = 6


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    value = json.loads(path.read_text(encoding="utf-8"))
    return value if isinstance(value, dict) else {}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        value = json.loads(line)
        if not isinstance(value, dict):
            raise ValueError(f"{path}:{line_number}: row must be a JSON object")
        rows.append(value)
    return rows


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def rel(path: Path) -> str:
    return str(path.relative_to(AI_ROOT))


def fail_if(condition: bool, failures: list[dict[str, Any]], check: str, observed: Any, expected: Any) -> None:
    if condition:
        failures.append({"check": check, "observed": observed, "expected": expected})


def find_intake_row(rows: list[dict[str, Any]]) -> dict[str, Any]:
    for row in rows:
        if row.get("head") == HEAD and row.get("benchmark_name") == BENCHMARK_NAME:
            return row
    return {}


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate KWB activity_risk smoke benchmark")
    parser.add_argument("--output", type=Path, default=OUT)
    args = parser.parse_args()

    dataset_rows = load_jsonl(DATASET)
    split = load_json(SPLIT)
    scorecard = load_json(SCORECARD)
    metric = load_json(METRIC)
    intake_row = find_intake_row(load_jsonl(INTAKE))
    report = load_json(REPORT)
    failures: list[dict[str, Any]] = []

    fail_if(len(dataset_rows) != EXPECTED_ROWS, failures, "dataset_rows", len(dataset_rows), EXPECTED_ROWS)
    fail_if(len({row.get("feedback_id") for row in dataset_rows}) != len(dataset_rows), failures, "feedback_ids_unique", len({row.get("feedback_id") for row in dataset_rows}), len(dataset_rows))
    for idx, row in enumerate(dataset_rows, start=1):
        fail_if(row.get("benchmark_scope") != "internal_smoke_only", failures, "row_scope_internal_smoke_only", {"row": idx, "value": row.get("benchmark_scope")}, "internal_smoke_only")
        fail_if(row.get("sample_limited") is not True, failures, "row_sample_limited_true", {"row": idx, "value": row.get("sample_limited")}, True)
        fail_if(row.get("training_label_source") is not False, failures, "row_training_label_source_false", {"row": idx, "value": row.get("training_label_source")}, False)
        for field in ("safe_for_training_import", "safe_for_model_claim", "release_ready"):
            fail_if(row.get(field) is not False, failures, f"row_{field}_false", {"row": idx, "value": row.get(field)}, False)

    fail_if(split.get("split_strategy") != "evaluation_only_all_rows_no_training", failures, "split_strategy", split.get("split_strategy"), "evaluation_only_all_rows_no_training")
    fail_if(split.get("leakage_check_status") != "passed", failures, "split_leakage_check_passed", split.get("leakage_check_status"), "passed")
    fail_if(split.get("future_training_exclusion_required") is not True, failures, "future_training_exclusion_required", split.get("future_training_exclusion_required"), True)
    fail_if(scorecard.get("benchmark_scope") != "internal_smoke_only", failures, "scorecard_scope", scorecard.get("benchmark_scope"), "internal_smoke_only")
    fail_if(scorecard.get("sample_limited") is not True, failures, "scorecard_sample_limited", scorecard.get("sample_limited"), True)
    fail_if(scorecard.get("safe_for_model_claim") is not False, failures, "scorecard_safe_for_model_claim_false", scorecard.get("safe_for_model_claim"), False)
    fail_if(metric.get("quality_status") != "sample_limited_internal_smoke_only", failures, "metric_quality_status", metric.get("quality_status"), "sample_limited_internal_smoke_only")
    fail_if(metric.get("ready_for_model_claim") is not False, failures, "metric_ready_for_model_claim_false", metric.get("ready_for_model_claim"), False)

    fail_if(not intake_row, failures, "intake_row_present", None, "present")
    if intake_row:
        expected_hashes = {
            "dataset_sha256": sha256(DATASET),
            "split_sha256": sha256(SPLIT),
            "scorecard_sha256": sha256(SCORECARD),
            "metric_sha256": sha256(METRIC),
        }
        for key, expected in expected_hashes.items():
            fail_if(str(intake_row.get(key) or "").lower() != expected, failures, f"intake_{key}_matches", intake_row.get(key), expected)
        fail_if(intake_row.get("license_review_status") != "approved_for_benchmark_only", failures, "intake_license_review_status", intake_row.get("license_review_status"), "approved_for_benchmark_only")
        fail_if(intake_row.get("leakage_check_status") != "passed", failures, "intake_leakage_check_status", intake_row.get("leakage_check_status"), "passed")

    for field in ("ready_for_model_claim", "safe_for_model_claim", "release_ready"):
        fail_if(report.get(field) is not False, failures, f"report_{field}_false", report.get(field), False)
    fail_if(report.get("accepted_for_local_benchmark_cache_intake") is not True, failures, "report_accepted_for_intake_true", report.get("accepted_for_local_benchmark_cache_intake"), True)

    validation = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "local_only": True,
        "benchmark_name": BENCHMARK_NAME,
        "dataset": rel(DATASET),
        "split_definition": rel(SPLIT),
        "scorecard": rel(SCORECARD),
        "metric_report": rel(METRIC),
        "dataset_rows": len(dataset_rows),
        "quality_status": metric.get("quality_status"),
        "intake_row_present": bool(intake_row),
        "success": not failures,
        "failures": failures,
        "ready_for_model_claim": False,
        "safe_for_model_claim": False,
        "release_ready": False,
        "policy": "Sample-limited smoke benchmark only. It can validate benchmark plumbing, not model quality.",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(validation, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({
        "success": validation["success"],
        "dataset_rows": validation["dataset_rows"],
        "quality_status": validation["quality_status"],
        "failures": len(failures),
        "output": rel(args.output),
    }, ensure_ascii=False))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
