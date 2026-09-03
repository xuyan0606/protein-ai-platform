#!/usr/bin/env python3
"""Validate the read-only release/benchmark human decision worklist."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_WORKLIST = AI_ROOT / "reports" / "release_benchmark_human_decision_worklist_20260806.json"
DEFAULT_REPORT = AI_ROOT / "reports" / "release_benchmark_human_decision_worklist_validation_report_20260806.json"
DEFAULT_BACKLOG = AI_ROOT / "reports" / "human_decision_backlog_report.json"


def load_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise SystemExit(f"{path} must contain a JSON object")
    return data


def fail_if(condition: bool, failures: list[dict[str, Any]], check: str, observed: Any, expected: Any) -> None:
    if condition:
        failures.append({"check": check, "observed": observed, "expected": expected})


def validate(worklist: dict[str, Any], backlog: dict[str, Any]) -> dict[str, Any]:
    failures: list[dict[str, Any]] = []
    fail_if(worklist.get("schema_version") != 1, failures, "schema_version", worklist.get("schema_version"), 1)
    fail_if(worklist.get("mode") != "manual_decision_worklist", failures, "mode", worklist.get("mode"), "manual_decision_worklist")
    fail_if(worklist.get("write_policy") != "read_only_gap_worklist; no formal decision rows written", failures, "write_policy", worklist.get("write_policy"), "read_only_gap_worklist; no formal decision rows written")
    fail_if(not str(worklist.get("interpretation_warning") or "").strip(), failures, "interpretation_warning_present", worklist.get("interpretation_warning"), "non-empty")
    for flag in ("release_ready", "safe_for_model_claim", "benchmark_ready_for_model_claim"):
        fail_if(worklist.get(flag) is not False, failures, f"{flag}_false", worklist.get(flag), False)

    summary = worklist.get("backlog_summary")
    fail_if(not isinstance(summary, dict), failures, "backlog_summary_object", type(summary).__name__, "object")
    summary = summary if isinstance(summary, dict) else {}
    expected_summary = {
        "total_backlog_items": backlog.get("backlog_items"),
        "open_backlog_items": backlog.get("open_items"),
        "ready_backlog_items": backlog.get("ready_items"),
        "required_rows": backlog.get("total_required_rows"),
        "completed_rows": backlog.get("total_completed_rows"),
        "missing_rows": backlog.get("total_missing_rows"),
    }
    for field, expected in expected_summary.items():
        fail_if(summary.get(field) != expected, failures, f"backlog_summary.{field}", summary.get(field), expected)
    expected_priority_counts = backlog.get("priority_counts") or {}
    fail_if(summary.get("priority_counts") != expected_priority_counts, failures, "backlog_summary.priority_counts", summary.get("priority_counts"), expected_priority_counts)

    non_backlog = worklist.get("non_backlog_gap_summary")
    fail_if(not isinstance(non_backlog, dict), failures, "non_backlog_gap_summary_object", type(non_backlog).__name__, "object")
    non_backlog = non_backlog if isinstance(non_backlog, dict) else {}
    fail_if(non_backlog.get("item_count") != 2, failures, "non_backlog_gap_summary.item_count", non_backlog.get("item_count"), 2)
    fail_if(set(non_backlog.get("item_types") or []) != {"structural_execution_gap", "runtime_evidence_gap"}, failures, "non_backlog_gap_summary.item_types", non_backlog.get("item_types"), ["runtime_evidence_gap", "structural_execution_gap"])
    for flag in ("release_ready", "safe_for_model_claim"):
        fail_if(non_backlog.get(flag) is not False, failures, f"non_backlog_gap_summary.{flag}_false", non_backlog.get(flag), False)

    reports = worklist.get("fail_closed_reports")
    fail_if(not isinstance(reports, list) or len(reports) < 4, failures, "fail_closed_reports_minimum", reports, "list with at least 4 paths")
    for path_text in reports if isinstance(reports, list) else []:
        fail_if(not (AI_ROOT / str(path_text)).exists(), failures, "fail_closed_report_exists", path_text, "existing path under AI root")

    items = worklist.get("items")
    fail_if(not isinstance(items, list), failures, "items_list", type(items).__name__, "list")
    items = items if isinstance(items, list) else []
    backlog_items = [item for item in items if isinstance(item, dict) and item.get("backlog_id")]
    human_backlog_items = [item for item in items if isinstance(item, dict) and item.get("item_type") == "human_decision_backlog"]
    structural_gap_items = [item for item in items if isinstance(item, dict) and item.get("item_type") == "structural_execution_gap"]
    runtime_gap_items = [item for item in items if isinstance(item, dict) and item.get("item_type") == "runtime_evidence_gap"]
    expected_backlog_count = backlog.get("backlog_items")
    fail_if(len(backlog_items) != expected_backlog_count, failures, "backlog_item_count", len(backlog_items), expected_backlog_count)
    fail_if(len(human_backlog_items) != expected_backlog_count, failures, "human_backlog_item_type_count", len(human_backlog_items), expected_backlog_count)
    source_backlog_ids = {str(item.get("backlog_id")) for item in backlog.get("items") or [] if isinstance(item, dict) and item.get("backlog_id")}
    worklist_backlog_ids = {str(item.get("backlog_id")) for item in backlog_items}
    fail_if(worklist_backlog_ids != source_backlog_ids, failures, "backlog_ids_match_source", sorted(worklist_backlog_ids), sorted(source_backlog_ids))
    fail_if(len(structural_gap_items) != 1, failures, "structural_execution_gap_count", len(structural_gap_items), 1)
    fail_if(len(runtime_gap_items) != 1, failures, "runtime_evidence_gap_count", len(runtime_gap_items), 1)
    priority_counts = {str(priority): 0 for priority in expected_priority_counts}
    seen_ids: set[str] = set()
    for index, item in enumerate(items, start=1):
        if not isinstance(item, dict):
            failures.append({"check": "item_object", "index": index, "observed": type(item).__name__, "expected": "object"})
            continue
        prefix = f"items[{index}]"
        for field in ("item_type", "workstream", "decision_file", "current_gap", "validator_report", "next_human_input"):
            fail_if(not str(item.get(field) or "").strip(), failures, f"{prefix}.{field}_present", item.get(field), "non-empty")
        fail_if("validator" in item, failures, f"{prefix}.validator_field_removed", item.get("validator"), "use validator_report")
        fail_if(item.get("item_type") not in {"human_decision_backlog", "structural_execution_gap", "runtime_evidence_gap"}, failures, f"{prefix}.item_type_known", item.get("item_type"), ["human_decision_backlog", "runtime_evidence_gap", "structural_execution_gap"])
        if item.get("backlog_id"):
            fail_if(item.get("item_type") != "human_decision_backlog", failures, f"{prefix}.backlog_item_type", item.get("item_type"), "human_decision_backlog")
            backlog_id = str(item["backlog_id"])
            fail_if(backlog_id in seen_ids, failures, f"{prefix}.backlog_id_unique", backlog_id, "unique")
            seen_ids.add(backlog_id)
            priority = item.get("priority")
            fail_if(priority not in priority_counts, failures, f"{prefix}.priority_known", priority, sorted(priority_counts))
            if priority in priority_counts:
                priority_counts[priority] += 1
        else:
            fail_if(item.get("item_type") == "human_decision_backlog", failures, f"{prefix}.non_backlog_item_type", item.get("item_type"), "non-backlog gap type")
            for flag in ("release_ready", "safe_for_model_claim", "benchmark_ready_for_model_claim"):
                fail_if(item.get(flag) is not False, failures, f"{prefix}.{flag}_false", item.get(flag), False)
        true_gate_flags = [name for name, value in item.items() if ("ready" in name or "claim" in name or "release" in name) and value is True]
        fail_if(bool(true_gate_flags), failures, f"{prefix}.no_true_gate_flags", true_gate_flags, [])
    fail_if(priority_counts != expected_priority_counts, failures, "items.priority_counts_match_source", priority_counts, expected_priority_counts)

    return {
        "schema_version": 1,
        "worklist_valid": not failures,
        "failure_count": len(failures),
        "failures": failures,
        "item_count": len(items),
        "backlog_item_count": len(backlog_items),
        "non_backlog_gap_count": len(structural_gap_items) + len(runtime_gap_items),
        "source_backlog_items": backlog.get("backlog_items"),
        "source_backlog_ids_match": worklist_backlog_ids == source_backlog_ids,
        "release_ready": False,
        "safe_for_model_claim": False,
        "benchmark_ready_for_model_claim": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate release/benchmark human decision worklist")
    parser.add_argument("--worklist", type=Path, default=DEFAULT_WORKLIST)
    parser.add_argument("--backlog", type=Path, default=DEFAULT_BACKLOG)
    parser.add_argument("--output", type=Path, default=DEFAULT_REPORT)
    args = parser.parse_args()

    report = validate(load_json(args.worklist), load_json(args.backlog))
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(args.output), "worklist_valid": report["worklist_valid"], "failure_count": report["failure_count"], "backlog_item_count": report["backlog_item_count"]}, ensure_ascii=False, sort_keys=True))
    return 0 if report["worklist_valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
