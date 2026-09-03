#!/usr/bin/env python3
"""Build a fail-closed benchmark coverage dashboard and gap queue.

This script turns benchmark score cache validation gaps into head-level queue
items. It is read-only with respect to benchmark intake, training labels, model
claim gates, and release gates.
"""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
MANIFEST = AI_ROOT / "reports" / "benchmark_score_cache_manifest.json"
VALIDATION_REPORT = AI_ROOT / "reports" / "benchmark_score_cache_validation_report.json"
MATRIX_REPORT = AI_ROOT / "reports" / "benchmark_matrix_report.json"
ACQUISITION_PLAN = AI_ROOT / "datasets" / "benchmark" / "benchmark_acquisition_plan.jsonl"
DASHBOARD_OUT = AI_ROOT / "reports" / "benchmark_coverage_dashboard.json"
GAP_QUEUE_OUT = AI_ROOT / "datasets" / "benchmark" / "benchmark_gap_queue.jsonl"

HEAD_ORDER = (
    "mutation_rank",
    "stability",
    "activity_risk",
    "substrate_fit",
    "assay_success",
)

REQUIRED_CACHE_ARTIFACTS = (
    "local_dataset_uri",
    "dataset_sha256",
    "split_definition_uri",
    "split_sha256",
    "scorecard_uri",
    "scorecard_sha256",
    "metric_report_uri",
    "metric_sha256",
)

POLICY = (
    "Benchmark coverage dashboard only. Benchmark artifacts are evaluation gates, not KWB training "
    "labels. Missing or invalid benchmark cache rows must be resolved through the existing benchmark "
    "acquisition, license review, scorecard, leakage-check, intake, and validation workflow. This "
    "dashboard never grants a model claim, training import, intake approval, or release readiness."
)


def relative(path: Path) -> str:
    try:
        return str(path.relative_to(AI_ROOT))
    except ValueError:
        return str(path)


def load_json(path: Path, input_errors: list[str]) -> dict[str, Any]:
    if not path.exists():
        input_errors.append(f"missing_input:{relative(path)}")
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        input_errors.append(f"invalid_json:{relative(path)}")
        return {}
    if not isinstance(data, dict):
        input_errors.append(f"invalid_json_object:{relative(path)}")
        return {}
    return data


def load_jsonl(path: Path, input_errors: list[str]) -> list[dict[str, Any]]:
    if not path.exists():
        input_errors.append(f"missing_input:{relative(path)}")
        return []

    rows: list[dict[str, Any]] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            input_errors.append(f"invalid_jsonl:{relative(path)}:{line_number}")
            continue
        if not isinstance(row, dict):
            input_errors.append(f"invalid_jsonl_object:{relative(path)}:{line_number}")
            continue
        rows.append(row)
    return rows


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )


def slug(value: str) -> str:
    normalized = re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_")
    return normalized or "benchmark"


def index_by_key(
    rows: list[dict[str, Any]],
    source_name: str,
    input_errors: list[str],
) -> dict[tuple[str, str], dict[str, Any]]:
    indexed: dict[tuple[str, str], dict[str, Any]] = {}
    for row in rows:
        head = row.get("head")
        benchmark_name = row.get("benchmark_name")
        if not isinstance(head, str) or not isinstance(benchmark_name, str):
            input_errors.append(f"invalid_{source_name}_identity")
            continue
        key = (head, benchmark_name)
        if key in indexed:
            input_errors.append(f"duplicate_{source_name}_row:{head}:{benchmark_name}")
            continue
        indexed[key] = row
    return indexed


def matrix_rows_by_head(matrix: dict[str, Any], input_errors: list[str]) -> dict[str, dict[str, Any]]:
    rows = matrix.get("heads")
    if not isinstance(rows, list):
        input_errors.append("matrix_heads_missing_or_invalid")
        return {}

    by_head: dict[str, dict[str, Any]] = {}
    for row in rows:
        if not isinstance(row, dict) or not isinstance(row.get("head"), str):
            input_errors.append("matrix_head_row_invalid")
            continue
        head = row["head"]
        if head in by_head:
            input_errors.append(f"duplicate_matrix_head:{head}")
            continue
        by_head[head] = row
    return by_head


def list_records(report: dict[str, Any], key: str, input_errors: list[str], source_name: str) -> list[dict[str, Any]]:
    value = report.get(key)
    if not isinstance(value, list):
        input_errors.append(f"{source_name}_{key}_missing_or_invalid")
        return []
    rows = [row for row in value if isinstance(row, dict)]
    if len(rows) != len(value):
        input_errors.append(f"{source_name}_{key}_contains_non_object")
    return rows


def missing_cache_artifacts(manifest_row: dict[str, Any] | None) -> list[str]:
    if not manifest_row or manifest_row.get("status") != "present":
        return list(REQUIRED_CACHE_ARTIFACTS)
    return [key for key in REQUIRED_CACHE_ARTIFACTS if not manifest_row.get(key)]


def build_benchmark_gap_item(
    head: str,
    benchmark_name: str,
    plan_row: dict[str, Any] | None,
    manifest_row: dict[str, Any] | None,
    validation_row: dict[str, Any] | None,
) -> dict[str, Any]:
    validation_errors = validation_row.get("errors") if validation_row else ["cache_validation_record_missing"]
    if not isinstance(validation_errors, list):
        validation_errors = ["cache_validation_errors_invalid"]
    validation_errors = [str(error) for error in validation_errors]
    valid = bool(validation_row and validation_row.get("valid") is True and not validation_errors)
    manifest_status = str(manifest_row.get("status") or "missing") if manifest_row else "missing"
    acquisition_status = str(plan_row.get("acquisition_status") or "not_planned") if plan_row else "not_planned"
    license_status = str(plan_row.get("license_review_status") or "not_reviewed") if plan_row else "not_reviewed"
    scorecard_status = str(plan_row.get("scorecard_status") or "not_ready") if plan_row else "not_ready"
    leakage_status = str(plan_row.get("leakage_check_status") or "not_run") if plan_row else "not_run"

    missing_requirements: list[str] = []
    if acquisition_status != "configured":
        missing_requirements.append("configured_acquisition_plan_row")
    if manifest_status != "present":
        missing_requirements.append("present_benchmark_score_cache_manifest_row")
    if license_status not in {
        "approved_for_benchmark_only",
        "approved_for_model_evaluation",
        "approved_for_training",
    }:
        missing_requirements.append("license_review_approval")
    if leakage_status != "passed":
        missing_requirements.append("leakage_check_passed")
    if scorecard_status != "ready":
        missing_requirements.append("scorecard_ready")
    if not valid:
        missing_requirements.append("valid_benchmark_score_cache_validation")

    return {
        "gap_id": f"benchmark_gap::{head}::{slug(benchmark_name)}",
        "head": head,
        "benchmark_name": benchmark_name,
        "priority": "P0",
        "status": "open_blocked",
        "gap_type": "benchmark_score_cache_invalid_or_missing",
        "cache_validation_valid": valid,
        "cache_validation_errors": validation_errors,
        "manifest_status": manifest_status,
        "acquisition_status": acquisition_status,
        "license_review_status": license_status,
        "leakage_check_status": leakage_status,
        "scorecard_status": scorecard_status,
        "missing_cache_artifacts": missing_cache_artifacts(manifest_row),
        "missing_requirements": missing_requirements,
        "operator_next_action": (
            "Resolve through existing benchmark acquisition/cache intake workflow, then rerun "
            "benchmark score cache validation and this dashboard."
        ),
        "required_artifacts": list(REQUIRED_CACHE_ARTIFACTS),
        "allowed_use": "benchmark evaluation coverage tracking only",
        "forbidden_use": (
            "Do not use benchmark rows as training labels, do not bypass benchmark intake, "
            "do not open model claims, and do not release."
        ),
        "safe_for_training_import": False,
        "benchmark_metric_claim_allowed": False,
        "safe_for_model_claim": False,
        "release_ready": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Build benchmark coverage dashboard")
    parser.add_argument("--manifest", type=Path, default=MANIFEST)
    parser.add_argument("--validation-report", type=Path, default=VALIDATION_REPORT)
    parser.add_argument("--matrix-report", type=Path, default=MATRIX_REPORT)
    parser.add_argument("--acquisition-plan", type=Path, default=ACQUISITION_PLAN)
    parser.add_argument("--dashboard", type=Path, default=DASHBOARD_OUT)
    parser.add_argument("--gap-queue", type=Path, default=GAP_QUEUE_OUT)
    args = parser.parse_args()

    input_errors: list[str] = []
    manifest = load_json(args.manifest, input_errors)
    validation = load_json(args.validation_report, input_errors)
    matrix = load_json(args.matrix_report, input_errors)
    acquisition_rows = load_jsonl(args.acquisition_plan, input_errors)

    matrix_by_head = matrix_rows_by_head(matrix, input_errors)
    plan_by_key = index_by_key(acquisition_rows, "acquisition_plan", input_errors)
    manifest_by_key = index_by_key(
        list_records(manifest, "rows", input_errors, "cache_manifest"),
        "cache_manifest",
        input_errors,
    )
    validation_by_key = index_by_key(
        list_records(validation, "records", input_errors, "cache_validation"),
        "cache_validation",
        input_errors,
    )

    for head in HEAD_ORDER:
        if head not in matrix_by_head:
            input_errors.append(f"missing_matrix_head:{head}")
    for head in sorted(set(matrix_by_head) - set(HEAD_ORDER)):
        input_errors.append(f"unexpected_matrix_head:{head}")

    heads: list[dict[str, Any]] = []
    gap_queue: list[dict[str, Any]] = []
    total_expected = 0
    total_valid = 0
    total_missing = 0
    total_error_counts: Counter[str] = Counter()

    for head in HEAD_ORDER:
        matrix_row = matrix_by_head.get(head, {})
        required = matrix_row.get("required_benchmarks")
        if not isinstance(required, list) or not all(isinstance(item, str) for item in required):
            input_errors.append(f"required_benchmarks_missing_or_invalid:{head}")
            required = []
        required = list(required)

        head_error_counts: Counter[str] = Counter()
        head_missing_benchmarks: list[str] = []
        head_gap_items: list[dict[str, Any]] = []
        valid_count = 0

        for benchmark_name in required:
            key = (head, benchmark_name)
            plan_row = plan_by_key.get(key)
            manifest_row = manifest_by_key.get(key)
            validation_row = validation_by_key.get(key)
            validation_errors = validation_row.get("errors") if validation_row else ["cache_validation_record_missing"]
            if not isinstance(validation_errors, list):
                validation_errors = ["cache_validation_errors_invalid"]
            validation_errors = [str(error) for error in validation_errors]
            valid = bool(validation_row and validation_row.get("valid") is True and not validation_errors)
            if valid:
                valid_count += 1
            else:
                gap_item = build_benchmark_gap_item(head, benchmark_name, plan_row, manifest_row, validation_row)
                head_gap_items.append(gap_item)
                head_missing_benchmarks.append(benchmark_name)
                head_error_counts.update(validation_errors)
                total_error_counts.update(validation_errors)

        expected = len(required)
        missing = expected - valid_count
        head_queue_id = f"benchmark_head_gap::{head}"
        if missing:
            gap_queue.append({
                "queue_id": head_queue_id,
                "head": head,
                "priority": "P0",
                "status": "open_blocked",
                "gap_type": "head_benchmark_score_cache_coverage_gap",
                "expected": expected,
                "valid": valid_count,
                "missing": missing,
                "error_counts": dict(sorted(head_error_counts.items())),
                "missing_benchmarks": head_missing_benchmarks,
                "benchmark_gap_items": head_gap_items,
                "operator_next_action": (
                    "Resolve each benchmark through existing benchmark acquisition/cache intake workflow, "
                    "then rerun benchmark score cache validation and this dashboard."
                ),
                "allowed_use": "head-level benchmark evaluation coverage tracking only",
                "forbidden_use": (
                    "Do not use benchmark rows as training labels, do not bypass benchmark intake, "
                    "do not open model claims, and do not release."
                ),
                "safe_for_training_import": False,
                "benchmark_metric_claim_allowed": False,
                "safe_for_model_claim": False,
                "release_ready": False,
            })
        total_expected += expected
        total_valid += valid_count
        total_missing += missing
        heads.append({
            "head": head,
            "expected": expected,
            "valid": valid_count,
            "missing": missing,
            "error_counts": dict(sorted(head_error_counts.items())),
            "ready": expected > 0 and valid_count == expected,
            "required_benchmarks": required,
            "missing_benchmarks": head_missing_benchmarks,
            "gap_queue_id": head_queue_id if missing else None,
            "training_ready_from_matrix": matrix_row.get("training_ready") is True,
            "benchmark_data_ready_from_matrix": matrix_row.get("benchmark_data_ready") is True,
            "scorecard_ready_from_matrix": matrix_row.get("scorecard_ready") is True,
            "ready_for_model_claim": False,
            "safe_for_model_claim": False,
        })

    reported_benchmark_rows = validation.get("benchmark_rows")
    reported_valid_rows = validation.get("valid_rows")
    reported_invalid_rows = validation.get("invalid_rows")
    reported_heads_ready = validation.get("heads_ready")
    source_count_consistent = (
        manifest.get("expected_benchmarks") == total_expected
        and validation.get("benchmark_rows") == total_expected
        and validation.get("valid_rows") == total_valid
        and validation.get("invalid_rows") == total_missing
        and validation.get("heads_ready") == sum(1 for row in heads if row["ready"])
        and len(acquisition_rows) == total_expected
    )
    if not source_count_consistent:
        input_errors.append("source_counts_inconsistent")

    dashboard = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "local_only": True,
        "status": "blocked",
        "inputs": {
            "benchmark_score_cache_manifest": relative(args.manifest),
            "benchmark_score_cache_validation_report": relative(args.validation_report),
            "benchmark_matrix_report": relative(args.matrix_report),
            "benchmark_acquisition_plan": relative(args.acquisition_plan),
        },
        "input_errors": sorted(set(input_errors)),
        "benchmark_rows": reported_benchmark_rows,
        "valid_rows": reported_valid_rows,
        "invalid_rows": reported_invalid_rows,
        "heads_ready": reported_heads_ready,
        "ready_for_model_claim": False,
        "safe_for_model_claim": False,
        "release_ready": False,
        "summary": {
            "head_count": len(HEAD_ORDER),
            "expected": total_expected,
            "valid": total_valid,
            "missing": total_missing,
            "gap_queue_rows": len(gap_queue),
            "benchmark_gap_rows": total_missing,
            "heads_ready": sum(1 for row in heads if row["ready"]),
            "source_count_consistent": source_count_consistent,
            "error_counts": dict(sorted(total_error_counts.items())),
        },
        "heads": heads,
        "gap_queue": relative(args.gap_queue),
        "policy_checks": {
            "benchmark_is_training_label_source": False,
            "benchmark_intake_modified": False,
            "model_claim_gate_opened": False,
            "release_gate_opened": False,
        },
        "policy": POLICY,
    }

    args.dashboard.parent.mkdir(parents=True, exist_ok=True)
    args.dashboard.write_text(json.dumps(dashboard, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    write_jsonl(args.gap_queue, gap_queue)

    print(json.dumps({
        "benchmark_rows": dashboard["benchmark_rows"],
        "valid_rows": dashboard["valid_rows"],
        "invalid_rows": dashboard["invalid_rows"],
        "heads_ready": dashboard["heads_ready"],
        "ready_for_model_claim": dashboard["ready_for_model_claim"],
        "gap_queue_rows": len(gap_queue),
        "dashboard": str(args.dashboard),
        "gap_queue": str(args.gap_queue),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
