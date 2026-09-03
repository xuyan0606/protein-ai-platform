#!/usr/bin/env python3
"""Build a Stage 25 release/benchmark fail-closed summary."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = AI_ROOT / "reports" / "release_benchmark_stage25_fail_closed_summary_20260806.json"

INPUTS = {
    "human_decision_backlog_fail_closed": AI_ROOT / "reports" / "human_decision_backlog_fail_closed_consistency_validation_report.json",
    "release_benchmark_worklist": AI_ROOT / "reports" / "release_benchmark_human_decision_worklist_validation_report_20260806.json",
    "benchmark_readiness_packet": AI_ROOT / "reports" / "benchmark_readiness_packet_validation_report.json",
    "local_release_manifest_fail_closed": AI_ROOT / "reports" / "local_release_manifest_fail_closed_consistency_validation_report.json",
}


def load_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise SystemExit(f"{path} must contain a JSON object")
    return data


def fail_if(condition: bool, failures: list[dict[str, Any]], check: str, observed: Any, expected: Any) -> None:
    if condition:
        failures.append({"check": check, "observed": observed, "expected": expected})


def build_summary() -> dict[str, Any]:
    failures: list[dict[str, Any]] = []
    reports: dict[str, dict[str, Any]] = {}
    rows = []
    for name, path in INPUTS.items():
        if not path.exists():
            failures.append({"check": f"{name}_exists", "observed": "missing", "expected": str(path)})
            continue
        report = load_json(path)
        reports[name] = report
        rows.append({
            "name": name,
            "path": str(path),
            "failure_count": report.get("failure_count", len(report.get("failures") or [])),
            "failures": len(report.get("failures") or []),
        })

    backlog = reports.get("human_decision_backlog_fail_closed", {})
    fail_if(backlog.get("success") is not True, failures, "backlog_success", backlog.get("success"), True)
    backlog_items = backlog.get("backlog_items")
    fail_if(
        not isinstance(backlog_items, int) or isinstance(backlog_items, bool) or backlog_items <= 0,
        failures,
        "backlog_items_positive_integer",
        backlog_items,
        ">0 integer",
    )
    fail_if(backlog.get("expected_backlog_items") != backlog_items, failures, "backlog_expected_items_parity", backlog.get("expected_backlog_items"), backlog_items)
    fail_if(backlog.get("open_items") != backlog_items, failures, "backlog_all_items_open", backlog.get("open_items"), backlog_items)
    fail_if(backlog.get("ready_items") != 0, failures, "backlog_ready_items", backlog.get("ready_items"), 0)
    total_missing_rows = backlog.get("total_missing_rows")
    fail_if(
        not isinstance(total_missing_rows, int) or isinstance(total_missing_rows, bool) or total_missing_rows <= 0,
        failures,
        "backlog_total_missing_rows_positive_integer",
        total_missing_rows,
        ">0 integer",
    )
    fail_if(backlog.get("expected_total_missing_rows") != total_missing_rows, failures, "backlog_expected_missing_rows_parity", backlog.get("expected_total_missing_rows"), total_missing_rows)

    worklist = reports.get("release_benchmark_worklist", {})
    fail_if(worklist.get("worklist_valid") is not True, failures, "worklist_valid", worklist.get("worklist_valid"), True)
    fail_if(worklist.get("failure_count") != 0, failures, "worklist_failure_count", worklist.get("failure_count"), 0)
    fail_if(worklist.get("backlog_item_count") != backlog_items, failures, "worklist_backlog_item_count_parity", worklist.get("backlog_item_count"), backlog_items)
    non_backlog_gap_count = worklist.get("non_backlog_gap_count")
    fail_if(
        not isinstance(non_backlog_gap_count, int) or isinstance(non_backlog_gap_count, bool) or non_backlog_gap_count <= 0,
        failures,
        "worklist_non_backlog_gap_count_positive_integer",
        non_backlog_gap_count,
        ">0 integer",
    )
    expected_worklist_items = backlog_items + non_backlog_gap_count if isinstance(backlog_items, int) and isinstance(non_backlog_gap_count, int) else None
    fail_if(worklist.get("item_count") != expected_worklist_items, failures, "worklist_item_count_decomposition", worklist.get("item_count"), expected_worklist_items)

    benchmark = reports.get("benchmark_readiness_packet", {})
    fail_if(benchmark.get("contract_valid") is not True, failures, "benchmark_contract_valid", benchmark.get("contract_valid"), True)
    fail_if(benchmark.get("failure_count") != 0, failures, "benchmark_failure_count", benchmark.get("failure_count"), 0)
    fail_if(benchmark.get("status") != "blocked", failures, "benchmark_status_blocked", benchmark.get("status"), "blocked")
    fail_if(benchmark.get("completion_ready_rows") != 0, failures, "benchmark_completion_ready_rows", benchmark.get("completion_ready_rows"), 0)
    packet_rows = benchmark.get("packet_rows")
    fail_if(
        not isinstance(packet_rows, int) or isinstance(packet_rows, bool) or packet_rows <= 0,
        failures,
        "benchmark_packet_rows_positive_integer",
        packet_rows,
        ">0 integer",
    )
    fail_if(benchmark.get("blocked_rows") != packet_rows, failures, "benchmark_all_packets_blocked", benchmark.get("blocked_rows"), packet_rows)
    fail_if(benchmark.get("score_values_recorded") != 0, failures, "benchmark_score_values_recorded_zero", benchmark.get("score_values_recorded"), 0)
    fail_if(benchmark.get("source_discrepancies") != [], failures, "benchmark_source_discrepancies_empty", benchmark.get("source_discrepancies"), [])

    release = reports.get("local_release_manifest_fail_closed", {})
    fail_if(release.get("success") is not True, failures, "release_manifest_success", release.get("success"), True)
    fail_if(release.get("release_ready") is not False, failures, "release_manifest_release_ready_false", release.get("release_ready"), False)
    fail_if(release.get("safe_for_model_claim") is not False, failures, "release_manifest_safe_for_model_claim_false", release.get("safe_for_model_claim"), False)
    fail_if(len(release.get("failures") or []) != 0, failures, "release_manifest_failures_empty", release.get("failures"), [])

    for report_name, report in reports.items():
        for flag in ("release_ready", "safe_for_model_claim", "benchmark_ready_for_model_claim", "ready_for_model_claim"):
            if flag in report:
                fail_if(report.get(flag) is not False, failures, f"{report_name}.{flag}_false", report.get(flag), False)

    return {
        "schema_version": 1,
        "created_at": "2026-08-06",
        "mode": "read_only_release_benchmark_fail_closed_summary",
        "stage": 25,
        "summary_valid": not failures,
        "failure_count": len(failures),
        "failures": failures,
        "reports": rows,
        "human_backlog_open_items": backlog.get("open_items"),
        "human_backlog_missing_rows": backlog.get("total_missing_rows"),
        "worklist_item_count": worklist.get("item_count"),
        "worklist_non_backlog_gap_count": worklist.get("non_backlog_gap_count"),
        "benchmark_status": benchmark.get("status"),
        "benchmark_packet_rows": benchmark.get("packet_rows"),
        "benchmark_blocked_rows": benchmark.get("blocked_rows"),
        "benchmark_completion_ready_rows": benchmark.get("completion_ready_rows"),
        "benchmark_score_values_recorded": benchmark.get("score_values_recorded"),
        "release_ready": False,
        "safe_for_model_claim": False,
        "benchmark_ready_for_model_claim": False,
        "formal_decision_rows_written": 0,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Build release/benchmark Stage 25 fail-closed summary")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    summary = build_summary()
    args.output.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(args.output), "summary_valid": summary["summary_valid"], "failure_count": summary["failure_count"], "report_count": len(summary["reports"])}, ensure_ascii=False, sort_keys=True))
    return 0 if summary["summary_valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
