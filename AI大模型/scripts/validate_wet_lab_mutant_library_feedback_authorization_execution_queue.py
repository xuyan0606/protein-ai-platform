#!/usr/bin/env python3
"""Validate wet-lab feedback authorization execution queue fail-closed."""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
RECEIPTS = AI_ROOT / "datasets" / "feedback" / "wet_lab_mutant_library_feedback_authorization_operator_receipts.jsonl"
RECEIPT_VALIDATION = AI_ROOT / "reports" / "wet_lab_mutant_library_feedback_authorization_operator_receipt_validation_report.json"
QUEUE = AI_ROOT / "datasets" / "feedback" / "wet_lab_mutant_library_feedback_authorization_execution_queue.jsonl"
MARKDOWN = AI_ROOT / "reports" / "wet_lab_mutant_library_feedback_authorization_execution_queue.md"
STATUS = AI_ROOT / "datasets" / "feedback" / "wet_lab_mutant_library_feedback_authorization_execution_queue_status.jsonl"
REPORT = AI_ROOT / "reports" / "wet_lab_mutant_library_feedback_authorization_execution_queue_validation_report.json"

EXPECTED_REVIEW_ORDER = ["E331Q", "D105N", "S265T"]
MODE_ORDER = {
    "tradeoff_review_required": 0,
    "positive_candidate_review_required": 1,
    "watch_candidate_review_required": 2,
    "negative_candidate_review_required": 3,
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


def variant_sort_key(item: dict[str, Any]) -> tuple[int, str]:
    modes = item.get("review_mode_counts") or {}
    top = min((MODE_ORDER.get(str(mode), 99) for mode, count in modes.items() if count), default=99)
    return (top, str(item.get("variant") or ""))


def next_action(mode_counts: Counter[str]) -> str:
    if mode_counts.get("tradeoff_review_required", 0):
        return "Review the full variant tradeoff as one bundle before any metric-level authorization decision."
    if mode_counts.get("positive_candidate_review_required", 0):
        return "Review positive candidate metrics after source trace, numbering, unit/condition, batch/control, and replicate/QC checks."
    return "Review watch metrics and decide whether each should remain needs_more_info or become reviewed evidence."


def expected_queue_rows(receipts: list[dict[str, Any]], receipt_validation: dict[str, Any]) -> list[dict[str, Any]]:
    by_variant: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for receipt in receipts:
        by_variant[str(receipt.get("variant") or "")].append(receipt)

    rows: list[dict[str, Any]] = []
    for variant, variant_receipts in by_variant.items():
        mode_counts = Counter(str(row.get("review_mode") or "") for row in variant_receipts)
        status_counts = Counter(str(row.get("receipt_status") or "") for row in variant_receipts)
        rows.append({
            "execution_queue_id": f"wetlab-mutlib-auth-exec-{variant.lower()}",
            "variant": variant,
            "metric_receipt_rows": len(variant_receipts),
            "review_mode_counts": dict(sorted(mode_counts.items())),
            "receipt_status_counts": dict(sorted(status_counts.items())),
            "open_blocked_receipt_rows": status_counts.get("open_blocked_no_authorization_decision", 0),
            "decision_present_rows": sum(1 for row in variant_receipts if row.get("decision_row_present") is True),
            "authorized_rows": sum(1 for row in variant_receipts if row.get("authorized_for_feedback_intake") is True),
            "preflight_present_rows": sum(1 for row in variant_receipts if row.get("preflight_row_present") is True),
            "receipt_validation_all_rows_valid": bool(receipt_validation.get("all_receipt_rows_valid")),
            "queue_status": "open_blocked_waiting_for_human_authorization",
            "next_action_summary": next_action(mode_counts),
            "operator_open_first": "datasets/feedback/wet_lab_mutant_library_feedback_authorizations.template.jsonl",
            "write_reviewed_decisions_to": "datasets/feedback/wet_lab_mutant_library_feedback_authorizations.jsonl",
            "validator_command": "python3 scripts/validate_wet_lab_mutant_library_feedback_authorizations.py",
            "preflight_command": "python3 scripts/build_wet_lab_mutant_library_feedback_preflight.py",
            "safe_pipeline_command": "python3 scripts/run_safe_training_pipeline.py",
            "metric_receipts": [
                {
                    "operator_receipt_id": row.get("operator_receipt_id"),
                    "feedback_candidate_id": row.get("feedback_candidate_id"),
                    "metric_name": row.get("metric_name"),
                    "review_mode": row.get("review_mode"),
                    "receipt_status": row.get("receipt_status"),
                    "decision_row_present": row.get("decision_row_present"),
                    "preflight_row_present": row.get("preflight_row_present"),
                }
                for row in sorted(variant_receipts, key=lambda item: str(item.get("metric_name") or ""))
            ],
            "completion_condition": "all metric authorization decisions validate and downstream preflight is generated; execution queue alone is never sufficient",
            "requires_human_input": True,
            "completion_ready": False,
            "policy": "Execution queue only; not an authorization, not feedback preflight, and not a training label.",
        })
    return sorted(rows, key=variant_sort_key)


def validate_queue_row(actual: dict[str, Any], expected: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    for field, expected_value in expected.items():
        if actual.get(field) != expected_value:
            errors.append(f"{field}_mismatch")

    if actual.get("queue_status") != "open_blocked_waiting_for_human_authorization":
        errors.append("queue_status_not_open_blocked")
    if actual.get("requires_human_input") is not True:
        errors.append("requires_human_input_not_true")
    if actual.get("completion_ready") is not False:
        errors.append("completion_ready_not_false")
    if int(actual.get("authorized_rows") or 0) != 0:
        errors.append("authorized_rows_not_zero")
    if int(actual.get("preflight_present_rows") or 0) != 0:
        errors.append("preflight_present_rows_not_zero")

    condition = str(actual.get("completion_condition") or "").lower()
    if "authorization decisions validate" not in condition or "execution queue alone is never sufficient" not in condition:
        errors.append("completion_condition_missing_fail_closed_language")
    policy = str(actual.get("policy") or "").lower()
    for phrase in ["not an authorization", "not feedback preflight", "not a training label"]:
        if phrase not in policy:
            errors.append("policy_missing_fail_closed_language")
            break
    return errors


def markdown_errors(path: Path) -> list[str]:
    if not path.exists():
        return ["markdown_missing"]
    text = path.read_text(encoding="utf-8").lower()
    errors: list[str] = []
    for phrase in ["not an authorization", "not feedback preflight", "not a training label"]:
        if phrase not in text:
            errors.append("markdown_missing_fail_closed_language")
            break
    for variant in EXPECTED_REVIEW_ORDER:
        if variant.lower() not in text:
            errors.append("markdown_missing_expected_variant")
            break
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate wet-lab feedback authorization execution queue")
    parser.add_argument("--receipts", type=Path, default=RECEIPTS)
    parser.add_argument("--receipt-validation", type=Path, default=RECEIPT_VALIDATION)
    parser.add_argument("--queue", type=Path, default=QUEUE)
    parser.add_argument("--markdown", type=Path, default=MARKDOWN)
    parser.add_argument("--status", type=Path, default=STATUS)
    parser.add_argument("--report", type=Path, default=REPORT)
    args = parser.parse_args()

    receipts = load_jsonl(args.receipts)
    receipt_validation = load_json(args.receipt_validation)
    queue_rows = load_jsonl(args.queue)
    expected_rows = expected_queue_rows(receipts, receipt_validation)
    expected_by_variant = {str(row.get("variant")): row for row in expected_rows}

    seen_variants: set[str] = set()
    duplicate_variants: set[str] = set()
    status_rows: list[dict[str, Any]] = []
    errors = Counter()

    for idx, queue_row in enumerate(queue_rows, start=1):
        variant = str(queue_row.get("variant") or "")
        if variant in seen_variants:
            duplicate_variants.add(variant)
        seen_variants.add(variant)
        expected = expected_by_variant.get(variant)
        row_errors = ["unexpected_variant"] if expected is None else validate_queue_row(queue_row, expected)
        if idx <= len(EXPECTED_REVIEW_ORDER) and variant != EXPECTED_REVIEW_ORDER[idx - 1]:
            row_errors.append("review_order_mismatch")
        errors.update(row_errors)
        status_rows.append({
            "execution_queue_id": queue_row.get("execution_queue_id"),
            "variant": variant,
            "execution_order": idx,
            "metric_receipt_rows": queue_row.get("metric_receipt_rows"),
            "queue_status": queue_row.get("queue_status"),
            "decision_present_rows": queue_row.get("decision_present_rows"),
            "authorized_rows": queue_row.get("authorized_rows"),
            "preflight_present_rows": queue_row.get("preflight_present_rows"),
            "valid": not row_errors,
            "completion_ready": False,
            "requires_human_input": True,
            "errors": row_errors,
            "policy": "Validated execution queue row only; not authorization, not feedback preflight, and not model claim readiness.",
        })

    missing_variants = sorted(set(expected_by_variant) - seen_variants)
    unexpected_variants = sorted(seen_variants - set(expected_by_variant))
    actual_order = [str(row.get("variant") or "") for row in queue_rows]
    if actual_order != EXPECTED_REVIEW_ORDER:
        errors.update({"review_order_mismatch": 1})
    if missing_variants:
        errors.update({"missing_queue_row": len(missing_variants)})
    if unexpected_variants:
        errors.update({"unexpected_queue_row": len(unexpected_variants)})
    if duplicate_variants:
        errors.update({"duplicate_queue_row": len(duplicate_variants)})
        for status in status_rows:
            if status["variant"] in duplicate_variants:
                status["valid"] = False
                status["errors"].append("duplicate_queue_row")
    if not receipt_validation.get("all_receipt_rows_valid"):
        errors.update({"receipt_validation_not_ready": 1})
    for err in markdown_errors(args.markdown):
        errors.update({err: 1})

    valid_rows = sum(1 for row in status_rows if row["valid"])
    status_counts = Counter(str(row.get("queue_status") or "") for row in queue_rows)
    authorized_rows = sum(int(row.get("authorized_rows") or 0) for row in queue_rows)
    preflight_present_rows = sum(int(row.get("preflight_present_rows") or 0) for row in queue_rows)
    all_valid = (
        not errors
        and valid_rows == len(queue_rows)
        and len(queue_rows) == len(expected_rows) == len(EXPECTED_REVIEW_ORDER)
        and actual_order == EXPECTED_REVIEW_ORDER
    )

    write_jsonl(args.status, status_rows)
    report = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "local_only": True,
        "execution_queue_rows": len(queue_rows),
        "expected_execution_queue_rows": len(expected_rows),
        "valid_queue_rows": valid_rows,
        "invalid_queue_rows": len(status_rows) - valid_rows,
        "missing_queue_rows": len(missing_variants),
        "unexpected_queue_rows": len(unexpected_variants),
        "duplicate_queue_rows": len(duplicate_variants),
        "operator_receipt_rows": len(receipts),
        "receipt_validation_all_rows_valid": bool(receipt_validation.get("all_receipt_rows_valid")),
        "open_blocked_queue_rows": status_counts.get("open_blocked_waiting_for_human_authorization", 0),
        "decision_present_rows": sum(int(row.get("decision_present_rows") or 0) for row in queue_rows),
        "authorized_rows": authorized_rows,
        "preflight_present_rows": preflight_present_rows,
        "completion_ready_rows": 0,
        "requires_human_input_rows": len(status_rows),
        "ready_for_feedback_intake_rows": 0,
        "claim_eligible_rows_now": 0,
        "safe_for_model_claim": False,
        "all_queue_rows_valid": all_valid,
        "expected_review_order": EXPECTED_REVIEW_ORDER,
        "review_order": actual_order,
        "queue_status_counts": dict(sorted(status_counts.items())),
        "error_counts": dict(errors),
        "status_output": str(args.status),
        "policy": "Execution queue validation proves local review ordering only; it never authorizes rows, runs preflight, appends labels, or enables model claims.",
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({
        "execution_queue_rows": report["execution_queue_rows"],
        "valid_queue_rows": report["valid_queue_rows"],
        "invalid_queue_rows": report["invalid_queue_rows"],
        "all_queue_rows_valid": report["all_queue_rows_valid"],
        "review_order": report["review_order"],
        "output": str(args.report),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
