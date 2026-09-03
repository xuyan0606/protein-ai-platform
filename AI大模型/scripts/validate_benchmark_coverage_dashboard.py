#!/usr/bin/env python3
"""Validate benchmark coverage dashboard fail-closed consistency."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
DASHBOARD = AI_ROOT / "reports" / "benchmark_coverage_dashboard.json"
GAP_QUEUE = AI_ROOT / "datasets" / "benchmark" / "benchmark_gap_queue.jsonl"
OUT = AI_ROOT / "reports" / "benchmark_coverage_dashboard_validation_report.json"

EXPECTED_HEADS = (
    "mutation_rank",
    "stability",
    "activity_risk",
    "substrate_fit",
    "assay_success",
)

FALSE_GATE_KEYS = (
    "safe_for_model_claim",
    "release_ready",
)

FALSE_POLICY_CHECKS = (
    "benchmark_is_training_label_source",
    "benchmark_intake_modified",
    "model_claim_gate_opened",
    "release_gate_opened",
)


def resolve(path: Path) -> Path:
    return path if path.is_absolute() else AI_ROOT / path


def relative(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(AI_ROOT))
    except ValueError:
        return str(path)


def load_json(path: Path, failures: list[dict[str, Any]], label: str) -> dict[str, Any]:
    if not path.exists():
        failures.append({"check": f"{label}_exists", "observed": "missing", "expected": str(path)})
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        failures.append({"check": f"{label}_valid_json", "observed": str(exc), "expected": "valid JSON object"})
        return {}
    if not isinstance(data, dict):
        failures.append({"check": f"{label}_json_object", "observed": type(data).__name__, "expected": "dict"})
        return {}
    return data


def load_jsonl(path: Path, failures: list[dict[str, Any]], label: str) -> list[dict[str, Any]]:
    if not path.exists():
        failures.append({"check": f"{label}_exists", "observed": "missing", "expected": str(path)})
        return []

    rows: list[dict[str, Any]] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            failures.append({
                "check": f"{label}_valid_jsonl",
                "line": line_number,
                "observed": str(exc),
                "expected": "valid JSON object per line",
            })
            continue
        if not isinstance(row, dict):
            failures.append({
                "check": f"{label}_jsonl_object",
                "line": line_number,
                "observed": type(row).__name__,
                "expected": "dict",
            })
            continue
        rows.append(row)
    return rows


def as_int(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    return None


def fail_if(
    condition: bool,
    failures: list[dict[str, Any]],
    check: str,
    observed: Any,
    expected: Any,
) -> None:
    if condition:
        failures.append({"check": check, "observed": observed, "expected": expected})


def list_dicts(value: Any, failures: list[dict[str, Any]], check: str) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        failures.append({"check": check, "observed": type(value).__name__, "expected": "list[dict]"})
        return []
    rows = [row for row in value if isinstance(row, dict)]
    if len(rows) != len(value):
        failures.append({"check": check, "observed": "contains non-object row", "expected": "all rows are dict"})
    return rows


def validate_false_gates(
    source: dict[str, Any],
    failures: list[dict[str, Any]],
    prefix: str,
    keys: tuple[str, ...] = FALSE_GATE_KEYS,
) -> None:
    for key in keys:
        fail_if(
            source.get(key) is not False,
            failures,
            f"{prefix}_{key}_false",
            source.get(key),
            False,
        )


def validate_gap_item(item: dict[str, Any], failures: list[dict[str, Any]], head: str) -> None:
    item_id = item.get("gap_id")
    prefix = f"gap_item:{item_id or head}"
    fail_if(item.get("head") != head, failures, f"{prefix}_head_matches_parent", item.get("head"), head)
    fail_if(item.get("status") != "open_blocked", failures, f"{prefix}_status_open_blocked", item.get("status"), "open_blocked")
    fail_if(item.get("cache_validation_valid") is not False, failures, f"{prefix}_cache_validation_invalid", item.get("cache_validation_valid"), False)
    fail_if(
        not item.get("cache_validation_errors"),
        failures,
        f"{prefix}_cache_validation_errors_explain_invalid_row",
        item.get("cache_validation_errors"),
        "non-empty list",
    )
    fail_if(
        not item.get("missing_requirements"),
        failures,
        f"{prefix}_missing_requirements_explain_invalid_row",
        item.get("missing_requirements"),
        "non-empty list",
    )
    validate_false_gates(
        item,
        failures,
        prefix,
        keys=("safe_for_training_import", "benchmark_metric_claim_allowed", "safe_for_model_claim", "release_ready"),
    )


def validate_head_and_queue(
    head_row: dict[str, Any],
    queue_row: dict[str, Any] | None,
    failures: list[dict[str, Any]],
) -> tuple[int, int, int, bool, Counter[str]]:
    head = str(head_row.get("head") or "")
    expected = as_int(head_row.get("expected")) or 0
    valid = as_int(head_row.get("valid")) or 0
    missing = as_int(head_row.get("missing")) or 0
    ready = head_row.get("ready") is True
    error_counts = Counter()

    fail_if(not head, failures, "head_identity_present", head_row.get("head"), "non-empty head")
    fail_if(expected < 0 or valid < 0 or missing < 0, failures, f"head:{head}_counts_non_negative", {"expected": expected, "valid": valid, "missing": missing}, "non-negative integers")
    fail_if(expected != valid + missing, failures, f"head:{head}_expected_equals_valid_plus_missing", {"expected": expected, "valid": valid, "missing": missing}, expected)
    fail_if(ready != (expected > 0 and valid == expected), failures, f"head:{head}_ready_matches_counts", ready, expected > 0 and valid == expected)
    fail_if(head_row.get("ready_for_model_claim") is not False, failures, f"head:{head}_ready_for_model_claim_false", head_row.get("ready_for_model_claim"), False)
    validate_false_gates(head_row, failures, f"head:{head}", keys=("safe_for_model_claim",))

    missing_benchmarks = head_row.get("missing_benchmarks")
    if not isinstance(missing_benchmarks, list):
        failures.append({"check": f"head:{head}_missing_benchmarks_list", "observed": type(missing_benchmarks).__name__, "expected": "list"})
        missing_benchmarks = []
    fail_if(len(missing_benchmarks) != missing, failures, f"head:{head}_missing_benchmarks_count", len(missing_benchmarks), missing)

    head_error_counts = head_row.get("error_counts")
    if not isinstance(head_error_counts, dict):
        failures.append({"check": f"head:{head}_error_counts_dict", "observed": type(head_error_counts).__name__, "expected": "dict"})
        head_error_counts = {}
    else:
        error_counts.update({str(key): int(value) for key, value in head_error_counts.items() if isinstance(value, int) and not isinstance(value, bool)})
    fail_if(missing > 0 and not head_error_counts, failures, f"head:{head}_error_counts_explain_invalid_rows", head_error_counts, "non-empty dict")

    if missing > 0:
        fail_if(queue_row is None, failures, f"gap_queue_has_head:{head}", None, head_row.get("gap_queue_id"))
    else:
        fail_if(queue_row is not None, failures, f"gap_queue_absent_when_head_ready:{head}", queue_row.get("queue_id") if queue_row else None, None)
    if queue_row is None:
        return expected, valid, missing, ready, error_counts

    queue_id = f"benchmark_head_gap::{head}"
    fail_if(queue_row.get("queue_id") != queue_id, failures, f"gap_queue:{head}_queue_id", queue_row.get("queue_id"), queue_id)
    fail_if(head_row.get("gap_queue_id") != queue_id, failures, f"head:{head}_gap_queue_id", head_row.get("gap_queue_id"), queue_id)
    fail_if(queue_row.get("head") != head, failures, f"gap_queue:{head}_head", queue_row.get("head"), head)
    fail_if(queue_row.get("status") != "open_blocked", failures, f"gap_queue:{head}_status_open_blocked", queue_row.get("status"), "open_blocked")
    for key in ("expected", "valid", "missing"):
        fail_if(queue_row.get(key) != head_row.get(key), failures, f"gap_queue:{head}_{key}_matches_dashboard", queue_row.get(key), head_row.get(key))
    fail_if(queue_row.get("missing_benchmarks") != missing_benchmarks, failures, f"gap_queue:{head}_missing_benchmarks_match", queue_row.get("missing_benchmarks"), missing_benchmarks)
    fail_if(queue_row.get("error_counts") != dict(head_error_counts), failures, f"gap_queue:{head}_error_counts_match", queue_row.get("error_counts"), head_error_counts)
    validate_false_gates(
        queue_row,
        failures,
        f"gap_queue:{head}",
        keys=("safe_for_training_import", "benchmark_metric_claim_allowed", "safe_for_model_claim", "release_ready"),
    )

    gap_items = list_dicts(queue_row.get("benchmark_gap_items"), failures, f"gap_queue:{head}_benchmark_gap_items_list")
    item_names = [item.get("benchmark_name") for item in gap_items]
    fail_if(len(gap_items) != missing, failures, f"gap_queue:{head}_gap_item_count_explains_missing", len(gap_items), missing)
    fail_if(item_names != missing_benchmarks, failures, f"gap_queue:{head}_gap_item_names_match_missing_benchmarks", item_names, missing_benchmarks)
    for item in gap_items:
        validate_gap_item(item, failures, head)

    return expected, valid, missing, ready, error_counts


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate benchmark coverage dashboard fail-closed consistency")
    parser.add_argument("--dashboard", type=Path, default=DASHBOARD)
    parser.add_argument("--gap-queue", type=Path, default=GAP_QUEUE)
    parser.add_argument("--output", type=Path, default=OUT)
    args = parser.parse_args()

    dashboard_path = resolve(args.dashboard)
    gap_queue_path = resolve(args.gap_queue)
    output_path = resolve(args.output)

    failures: list[dict[str, Any]] = []
    dashboard = load_json(dashboard_path, failures, "dashboard")
    gap_queue = load_jsonl(gap_queue_path, failures, "gap_queue")

    heads = list_dicts(dashboard.get("heads"), failures, "dashboard_heads_list")
    head_names = [str(row.get("head") or "") for row in heads]
    head_rows = {str(row.get("head")): row for row in heads if isinstance(row.get("head"), str)}

    duplicate_heads = sorted(name for name, count in Counter(head_names).items() if name and count > 1)
    fail_if(bool(duplicate_heads), failures, "dashboard_heads_unique", duplicate_heads, [])
    fail_if(tuple(head_names) != EXPECTED_HEADS, failures, "dashboard_expected_heads_in_order", head_names, list(EXPECTED_HEADS))

    queue_by_head: dict[str, dict[str, Any]] = {}
    duplicate_queue_heads: list[str] = []
    for row in gap_queue:
        head = str(row.get("head") or "")
        if head in queue_by_head:
            duplicate_queue_heads.append(head)
        queue_by_head[head] = row
    fail_if(bool(duplicate_queue_heads), failures, "gap_queue_heads_unique", sorted(duplicate_queue_heads), [])

    total_expected = 0
    total_valid = 0
    total_missing = 0
    total_heads_ready = 0
    total_error_counts: Counter[str] = Counter()
    missing_heads: list[str] = []

    for head in EXPECTED_HEADS:
        row = head_rows.get(head)
        if not row:
            failures.append({"check": f"dashboard_head_present:{head}", "observed": None, "expected": head})
            continue
        expected, valid, missing, ready, error_counts = validate_head_and_queue(row, queue_by_head.get(head), failures)
        total_expected += expected
        total_valid += valid
        total_missing += missing
        total_heads_ready += 1 if ready else 0
        total_error_counts.update(error_counts)
        if missing > 0:
            missing_heads.append(head)

    fail_if(set(queue_by_head) != set(missing_heads), failures, "gap_queue_has_all_current_missing_heads", sorted(queue_by_head), sorted(missing_heads))

    invalid_rows = as_int(dashboard.get("invalid_rows"))
    benchmark_rows = as_int(dashboard.get("benchmark_rows"))
    valid_rows = as_int(dashboard.get("valid_rows"))
    heads_ready = as_int(dashboard.get("heads_ready"))

    fail_if(benchmark_rows != total_expected, failures, "benchmark_rows_match_head_expected_total", benchmark_rows, total_expected)
    fail_if(valid_rows != total_valid, failures, "valid_rows_match_head_valid_total", valid_rows, total_valid)
    fail_if(invalid_rows != total_missing, failures, "invalid_rows_match_head_missing_total", invalid_rows, total_missing)
    fail_if(benchmark_rows is not None and valid_rows is not None and invalid_rows != benchmark_rows - valid_rows, failures, "invalid_rows_equal_benchmark_rows_minus_valid_rows", invalid_rows, None if benchmark_rows is None or valid_rows is None else benchmark_rows - valid_rows)
    fail_if(heads_ready != total_heads_ready, failures, "heads_ready_match_ready_head_total", heads_ready, total_heads_ready)

    summary = dashboard.get("summary")
    if not isinstance(summary, dict):
        failures.append({"check": "summary_dict", "observed": type(summary).__name__, "expected": "dict"})
        summary = {}
    expected_summary = {
        "head_count": len(EXPECTED_HEADS),
        "expected": total_expected,
        "valid": total_valid,
        "missing": total_missing,
        "gap_queue_rows": len(gap_queue),
        "benchmark_gap_rows": total_missing,
        "heads_ready": total_heads_ready,
        "source_count_consistent": True,
        "error_counts": dict(sorted(total_error_counts.items())),
    }
    for key, expected in expected_summary.items():
        fail_if(summary.get(key) != expected, failures, f"summary_{key}_matches_derived", summary.get(key), expected)

    fail_if(dashboard.get("input_errors") not in ([], None), failures, "dashboard_input_errors_empty", dashboard.get("input_errors"), [])
    fail_if(dashboard.get("status") != "blocked", failures, "dashboard_status_blocked", dashboard.get("status"), "blocked")
    fail_if(dashboard.get("local_only") is not True, failures, "dashboard_local_only_true", dashboard.get("local_only"), True)
    fail_if(dashboard.get("gap_queue") != relative(gap_queue_path), failures, "dashboard_gap_queue_path_matches", dashboard.get("gap_queue"), relative(gap_queue_path))
    validate_false_gates(dashboard, failures, "dashboard")

    policy_checks = dashboard.get("policy_checks")
    if not isinstance(policy_checks, dict):
        failures.append({"check": "policy_checks_dict", "observed": type(policy_checks).__name__, "expected": "dict"})
        policy_checks = {}
    for key in FALSE_POLICY_CHECKS:
        fail_if(policy_checks.get(key) is not False, failures, f"policy_check_{key}_false", policy_checks.get(key), False)

    current_observed = {
        "benchmark_rows": benchmark_rows,
        "valid_rows": valid_rows,
        "ready_for_model_claim": dashboard.get("ready_for_model_claim"),
        "gap_queue_heads": len(queue_by_head),
    }
    current_expected = {
        "benchmark_rows": total_expected,
        "valid_rows": total_valid,
        "ready_for_model_claim": False,
        "gap_queue_heads": len(missing_heads),
    }
    for key, expected in current_expected.items():
        fail_if(current_observed.get(key) != expected, failures, f"current_state_{key}", current_observed.get(key), expected)

    ready_for_model_claim = dashboard.get("ready_for_model_claim") is True
    all_rows_valid = benchmark_rows is not None and benchmark_rows > 0 and valid_rows == benchmark_rows and invalid_rows == 0
    all_heads_ready = heads_ready == len(EXPECTED_HEADS) and total_heads_ready == len(EXPECTED_HEADS)
    if ready_for_model_claim:
        fail_if(not all_rows_valid, failures, "ready_for_model_claim_requires_all_rows_valid", {"benchmark_rows": benchmark_rows, "valid_rows": valid_rows, "invalid_rows": invalid_rows}, "all rows valid and invalid_rows=0")
        fail_if(not all_heads_ready, failures, "ready_for_model_claim_requires_all_heads_ready", {"heads_ready": heads_ready, "derived_heads_ready": total_heads_ready}, len(EXPECTED_HEADS))
        fail_if(bool(gap_queue), failures, "ready_for_model_claim_requires_empty_gap_queue", len(gap_queue), 0)
    else:
        fail_if(all_rows_valid and all_heads_ready and not gap_queue, failures, "ready_for_model_claim_false_despite_no_coverage_gaps", current_observed, "ready_for_model_claim true or explicit blocker")

    fail_if(total_missing > 0 and not total_error_counts, failures, "invalid_rows_have_error_counts", dict(total_error_counts), "non-empty error counts")
    fail_if(total_missing != sum(len(row.get("benchmark_gap_items") or []) for row in gap_queue), failures, "invalid_rows_explained_by_gap_items", sum(len(row.get("benchmark_gap_items") or []) for row in gap_queue), total_missing)

    report = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "local_only": True,
        "success": not failures,
        "dashboard": relative(dashboard_path),
        "gap_queue": relative(gap_queue_path),
        "expected_current_state": current_expected,
        "observed": {
            "benchmark_rows": benchmark_rows,
            "valid_rows": valid_rows,
            "invalid_rows": invalid_rows,
            "heads": head_names,
            "head_count": len(heads),
            "heads_ready": heads_ready,
            "ready_for_model_claim": dashboard.get("ready_for_model_claim"),
            "safe_for_model_claim": dashboard.get("safe_for_model_claim"),
            "release_ready": dashboard.get("release_ready"),
            "gap_queue_rows": len(gap_queue),
            "gap_queue_heads": sorted(queue_by_head),
        },
        "derived": {
            "benchmark_rows": total_expected,
            "valid_rows": total_valid,
            "invalid_rows": total_missing,
            "heads_ready": total_heads_ready,
            "gap_queue_rows": len(gap_queue),
            "gap_item_rows": sum(len(row.get("benchmark_gap_items") or []) for row in gap_queue),
            "error_counts": dict(sorted(total_error_counts.items())),
        },
        "failures": failures,
        "safe_for_training_pipeline": not failures,
        "safe_for_model_claim": False,
        "release_ready": False,
        "policy": (
            "Fail-closed validator for benchmark coverage dashboard consistency. Benchmark gaps may be "
            "tracked for evaluation coverage only; unresolved or unexplained benchmark rows must not "
            "open model claims, training import, intake approval, or release readiness."
        ),
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({
        "success": report["success"],
        "benchmark_rows": benchmark_rows,
        "valid_rows": valid_rows,
        "invalid_rows": invalid_rows,
        "heads_ready": heads_ready,
        "gap_queue_heads": len(queue_by_head),
        "ready_for_model_claim": dashboard.get("ready_for_model_claim"),
        "failures": len(failures),
        "output": str(output_path),
    }, ensure_ascii=False))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
