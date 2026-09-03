#!/usr/bin/env python3
"""Validate wet-lab feedback authorization dashboard consistency fail-closed."""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
WORKLIST = AI_ROOT / "datasets" / "feedback" / "wet_lab_mutant_library_feedback_authorization_worklist.jsonl"
WORKLIST_STATUS = AI_ROOT / "datasets" / "feedback" / "wet_lab_mutant_library_feedback_authorization_worklist_status.jsonl"
WORKLIST_VALIDATION = AI_ROOT / "reports" / "wet_lab_mutant_library_feedback_authorization_worklist_validation_report.json"
DASHBOARD_ITEMS = AI_ROOT / "datasets" / "feedback" / "wet_lab_mutant_library_feedback_authorization_dashboard_items.jsonl"
DASHBOARD_JSON = AI_ROOT / "reports" / "wet_lab_mutant_library_feedback_authorization_dashboard.json"
DASHBOARD_MD = AI_ROOT / "reports" / "wet_lab_mutant_library_feedback_authorization_dashboard.md"
DASHBOARD_STATUS = AI_ROOT / "datasets" / "feedback" / "wet_lab_mutant_library_feedback_authorization_dashboard_status.jsonl"
REPORT = AI_ROOT / "reports" / "wet_lab_mutant_library_feedback_authorization_dashboard_validation_report.json"

PRIORITY_ORDER = {
    "critical_tradeoff_review": 0,
    "medium_mixed_benefit_review": 1,
    "standard_multi_property_review": 2,
}


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def numeric(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def ratio_value(value: Any) -> float:
    return float(value) if numeric(value) else -1.0


def variant_expected(worklist_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_variant: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in worklist_rows:
        by_variant[str(row.get("variant") or "")].append(row)

    expected: list[dict[str, Any]] = []
    for variant, rows in by_variant.items():
        priority_counts = Counter(
            str((row.get("qc_context") or {}).get("review_priority"))
            for row in rows
            if isinstance(row.get("qc_context"), dict)
        )
        outcome_counts = Counter(str(row.get("outcome_candidate") or "") for row in rows)
        ratios = [ratio_value(row.get("vs_control_ratio")) for row in rows]
        top_priority = min(priority_counts, key=lambda priority: PRIORITY_ORDER.get(priority, 99)) if priority_counts else ""
        expected.append({
            "variant": variant,
            "source_project": rows[0].get("source_project"),
            "review_priority": top_priority,
            "metric_rows": len(rows),
            "outcome_counts": dict(sorted(outcome_counts.items())),
            "priority_counts": dict(sorted(priority_counts.items())),
            "ratio_min": min(ratios) if ratios else None,
            "ratio_max": max(ratios) if ratios else None,
            "authorized_rows": sum(1 for row in rows if row.get("authorized_for_feedback_intake") is True),
            "blocked_rows": sum(1 for row in rows if row.get("worklist_status") != "authorized_ready_for_preflight"),
            "metric_candidate_ids": sorted(str(row.get("feedback_candidate_id")) for row in rows),
        })
    return sorted(expected, key=lambda row: (PRIORITY_ORDER.get(str(row.get("review_priority")), 99), str(row.get("variant"))))


def validate_item(item: dict[str, Any], expected: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    for field in [
        "variant",
        "source_project",
        "review_priority",
        "metric_rows",
        "outcome_counts",
        "priority_counts",
        "ratio_min",
        "ratio_max",
        "authorized_rows",
        "blocked_rows",
    ]:
        if item.get(field) != expected.get(field):
            errors.append(f"{field}_mismatch")

    if item.get("requires_human_input") is not True:
        errors.append("requires_human_input_not_true")
    if item.get("completion_ready") is not False:
        errors.append("completion_ready_not_false")

    metric_rows = item.get("metric_review_rows")
    if not isinstance(metric_rows, list):
        errors.append("invalid_metric_review_rows")
        metric_rows = []
    observed_ids = sorted(str(row.get("feedback_candidate_id")) for row in metric_rows if isinstance(row, dict))
    if observed_ids != expected.get("metric_candidate_ids"):
        errors.append("metric_candidate_ids_mismatch")
    if len(metric_rows) != expected.get("metric_rows"):
        errors.append("metric_review_row_count_mismatch")
    for metric in metric_rows:
        if not isinstance(metric, dict):
            errors.append("invalid_metric_review_row")
            continue
        if metric.get("worklist_status") != "blocked_waiting_for_authorization":
            errors.append("metric_worklist_status_not_blocked")
        if not metric.get("authorization_template_id"):
            errors.append("metric_missing_authorization_template_id")
        if not metric.get("source_file"):
            errors.append("metric_missing_source_file")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate wet-lab feedback authorization dashboard")
    parser.add_argument("--worklist", type=Path, default=WORKLIST)
    parser.add_argument("--worklist-status", type=Path, default=WORKLIST_STATUS)
    parser.add_argument("--worklist-validation", type=Path, default=WORKLIST_VALIDATION)
    parser.add_argument("--dashboard-items", type=Path, default=DASHBOARD_ITEMS)
    parser.add_argument("--dashboard-json", type=Path, default=DASHBOARD_JSON)
    parser.add_argument("--dashboard-md", type=Path, default=DASHBOARD_MD)
    parser.add_argument("--dashboard-status", type=Path, default=DASHBOARD_STATUS)
    parser.add_argument("--report", type=Path, default=REPORT)
    args = parser.parse_args()

    worklist = load_jsonl(args.worklist)
    worklist_status = load_jsonl(args.worklist_status)
    worklist_validation = load_json(args.worklist_validation)
    dashboard_items = load_jsonl(args.dashboard_items)
    dashboard = load_json(args.dashboard_json)
    markdown_text = args.dashboard_md.read_text(encoding="utf-8") if args.dashboard_md.exists() else ""

    expected_rows = variant_expected(worklist)
    expected_by_variant = {str(row["variant"]): row for row in expected_rows}
    item_by_variant = {str(row.get("variant")): row for row in dashboard_items}
    status_rows: list[dict[str, Any]] = []
    errors = Counter()

    duplicate_variants = [
        variant for variant, count in Counter(str(row.get("variant")) for row in dashboard_items).items()
        if count > 1
    ]
    if duplicate_variants:
        errors.update({"duplicate_dashboard_variant": len(duplicate_variants)})

    for expected in expected_rows:
        variant = str(expected["variant"])
        item = item_by_variant.get(variant)
        item_errors = ["missing_dashboard_item"] if item is None else validate_item(item, expected)
        errors.update(item_errors)
        status_rows.append({
            "variant": variant,
            "review_priority": expected.get("review_priority"),
            "metric_rows": expected.get("metric_rows"),
            "authorized_rows": expected.get("authorized_rows"),
            "valid": not item_errors,
            "completion_ready": False,
            "requires_human_input": True,
            "errors": item_errors,
            "policy": "Validated dashboard row only; not authorization, not feedback intake, and not model claim readiness.",
        })

    unexpected_variants = sorted(set(item_by_variant) - set(expected_by_variant))
    if unexpected_variants:
        errors.update({"unexpected_dashboard_variant": len(unexpected_variants)})

    expected_review_order = [row["variant"] for row in expected_rows]
    if dashboard.get("review_order") != expected_review_order:
        errors.update({"review_order_mismatch": 1})
    if dashboard.get("variant_review_rows") != len(expected_rows):
        errors.update({"variant_review_rows_mismatch": 1})
    if dashboard.get("authorization_worklist_rows") != len(worklist):
        errors.update({"authorization_worklist_rows_mismatch": 1})
    if dashboard.get("valid_worklist_rows") != worklist_validation.get("valid_worklist_rows"):
        errors.update({"valid_worklist_rows_mismatch": 1})
    if dashboard.get("invalid_worklist_rows") != worklist_validation.get("invalid_worklist_rows"):
        errors.update({"invalid_worklist_rows_mismatch": 1})
    if dashboard.get("all_numeric_candidates_covered") is not bool(worklist_validation.get("all_numeric_candidates_covered")):
        errors.update({"all_numeric_candidates_covered_mismatch": 1})

    authorized_rows = sum(1 for row in worklist if row.get("authorized_for_feedback_intake") is True)
    critical_rows = sum(
        1
        for row in worklist
        if isinstance(row.get("qc_context"), dict)
        and row["qc_context"].get("review_priority") == "critical_tradeoff_review"
    )
    completion_ready_rows = sum(1 for row in worklist_status if row.get("completion_ready") is True)
    requires_human_input_rows = sum(1 for row in worklist_status if row.get("requires_human_input") is True)
    if dashboard.get("authorized_rows") != authorized_rows:
        errors.update({"authorized_rows_mismatch": 1})
    if dashboard.get("critical_tradeoff_worklist_rows") != critical_rows:
        errors.update({"critical_tradeoff_worklist_rows_mismatch": 1})
    if dashboard.get("completion_ready_rows") != completion_ready_rows:
        errors.update({"completion_ready_rows_mismatch": 1})
    if dashboard.get("requires_human_input_rows") != requires_human_input_rows:
        errors.update({"requires_human_input_rows_mismatch": 1})
    if dashboard.get("ready_for_feedback_intake_rows") != 0:
        errors.update({"dashboard_sets_ready_for_feedback_intake": 1})
    if dashboard.get("claim_eligible_rows_now") != 0:
        errors.update({"dashboard_sets_claim_eligible_rows": 1})
    if dashboard.get("safe_for_model_claim") is not False:
        errors.update({"dashboard_sets_safe_for_model_claim": 1})

    markdown_required = [
        "This dashboard is local review navigation only.",
        "not an authorization",
        "not feedback preflight",
        "not a training label",
        "E331Q",
        "D105N",
        "S265T",
        "python3 scripts/run_safe_training_pipeline.py",
    ]
    for phrase in markdown_required:
        if phrase not in markdown_text:
            errors.update({"markdown_missing_required_content": 1})
            break

    for phrase in ["not an authorization", "not feedback preflight", "not a training label"]:
        if phrase not in str(dashboard.get("policy", "")).lower():
            errors.update({"dashboard_policy_missing_fail_closed_language": 1})
            break

    valid_status_rows = sum(1 for row in status_rows if row["valid"])
    all_valid = not errors and valid_status_rows == len(expected_rows)
    write_jsonl(args.dashboard_status, status_rows)
    report = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "local_only": True,
        "variant_review_rows": len(dashboard_items),
        "expected_variant_review_rows": len(expected_rows),
        "valid_dashboard_rows": valid_status_rows,
        "invalid_dashboard_rows": len(status_rows) - valid_status_rows,
        "unexpected_dashboard_variant_rows": len(unexpected_variants),
        "duplicate_dashboard_variant_rows": len(duplicate_variants),
        "authorization_worklist_rows": len(worklist),
        "authorized_rows": authorized_rows,
        "critical_tradeoff_worklist_rows": critical_rows,
        "completion_ready_rows": 0,
        "requires_human_input_rows": requires_human_input_rows,
        "ready_for_feedback_intake_rows": 0,
        "claim_eligible_rows_now": 0,
        "safe_for_model_claim": False,
        "review_order": expected_review_order,
        "dashboard_md_present": args.dashboard_md.exists(),
        "all_dashboard_rows_valid": all_valid,
        "error_counts": dict(errors),
        "unexpected_variants": unexpected_variants,
        "status_output": str(args.dashboard_status),
        "policy": "Dashboard validation proves navigation consistency only; it never authorizes rows, runs preflight, appends labels, or enables model claims.",
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({
        "variant_review_rows": report["variant_review_rows"],
        "valid_dashboard_rows": report["valid_dashboard_rows"],
        "invalid_dashboard_rows": report["invalid_dashboard_rows"],
        "all_dashboard_rows_valid": report["all_dashboard_rows_valid"],
        "output": str(args.report),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
