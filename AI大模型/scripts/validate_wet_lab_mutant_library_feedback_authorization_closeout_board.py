#!/usr/bin/env python3
"""Validate wet-lab feedback authorization closeout board."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
RECEIPTS = AI_ROOT / "datasets" / "feedback" / "wet_lab_mutant_library_feedback_authorization_execution_queue_operator_packet_receipts.jsonl"
RECEIPT_STATUS = AI_ROOT / "datasets" / "feedback" / "wet_lab_mutant_library_feedback_authorization_execution_queue_operator_packet_receipt_status.jsonl"
RECEIPT_VALIDATION = AI_ROOT / "reports" / "wet_lab_mutant_library_feedback_authorization_execution_queue_operator_packet_receipt_validation_report.json"
CLOSEOUT = AI_ROOT / "datasets" / "feedback" / "wet_lab_mutant_library_feedback_authorization_closeout_board.jsonl"
MARKDOWN = AI_ROOT / "reports" / "wet_lab_mutant_library_feedback_authorization_closeout_board.md"
STATUS = AI_ROOT / "datasets" / "feedback" / "wet_lab_mutant_library_feedback_authorization_closeout_board_status.jsonl"
REPORT = AI_ROOT / "reports" / "wet_lab_mutant_library_feedback_authorization_closeout_board_validation_report.json"

EXPECTED_REVIEW_ORDER = ["E331Q", "D105N", "S265T"]


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def status_by_variant(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {str(row.get("variant") or ""): row for row in rows if row.get("variant")}


def required_closeout_items(receipt: dict[str, Any]) -> list[str]:
    items = []
    metric_rows = int(receipt.get("metric_receipt_rows") or 0)
    decision_rows = int(receipt.get("decision_rows_present") or 0)
    authorized_rows = int(receipt.get("authorized_rows") or 0)
    preflight_rows = int(receipt.get("preflight_rows_present") or 0)
    if decision_rows < metric_rows:
        items.append("append_reviewed_authorization_decisions_for_all_metric_rows")
    if authorized_rows < metric_rows:
        items.append("pass_authorization_validator_for_approved_metric_rows")
    if preflight_rows < metric_rows:
        items.append("run_downstream_preflight_after_valid_authorization")
    items.extend(["rerun_packet_receipt_validator", "rerun_safe_training_pipeline"])
    return items


def expected_row(
    receipt: dict[str, Any],
    receipt_status_rows: list[dict[str, Any]],
    receipt_validation: dict[str, Any],
) -> dict[str, Any]:
    variant = str(receipt.get("variant") or "")
    metric_rows = int(receipt.get("metric_receipt_rows") or 0)
    decision_rows = int(receipt.get("decision_rows_present") or 0)
    authorized_rows = int(receipt.get("authorized_rows") or 0)
    preflight_rows = int(receipt.get("preflight_rows_present") or 0)
    status = status_by_variant(receipt_status_rows).get(variant, {})
    return {
        "closeout_board_id": f"wetlab-mutlib-auth-closeout-{variant.lower()}",
        "operator_packet_receipt_id": receipt.get("operator_packet_receipt_id"),
        "operator_packet_id": receipt.get("operator_packet_id"),
        "execution_order": receipt.get("execution_order"),
        "variant": variant,
        "packet_mode": receipt.get("packet_mode"),
        "receipt_status": receipt.get("receipt_status"),
        "receipt_row_valid": bool(status.get("valid")),
        "receipt_validation_all_rows_valid": bool(receipt_validation.get("all_operator_packet_receipts_valid")),
        "metric_receipt_rows": metric_rows,
        "decision_rows_present": decision_rows,
        "missing_decision_rows": max(metric_rows - decision_rows, 0),
        "authorized_rows": authorized_rows,
        "missing_authorized_rows": max(metric_rows - authorized_rows, 0),
        "preflight_rows_present": preflight_rows,
        "missing_preflight_rows": max(metric_rows - preflight_rows, 0),
        "feedback_candidate_ids": receipt.get("feedback_candidate_ids") or [],
        "required_closeout_items": required_closeout_items(receipt),
        "operator_open_first": "datasets/feedback/wet_lab_mutant_library_feedback_authorizations.template.jsonl",
        "write_reviewed_decisions_to": "datasets/feedback/wet_lab_mutant_library_feedback_authorizations.jsonl",
        "authorization_validator_command": "python3 scripts/validate_wet_lab_mutant_library_feedback_authorizations.py",
        "preflight_command": "python3 scripts/build_wet_lab_mutant_library_feedback_preflight.py",
        "receipt_validator_command": "python3 scripts/validate_wet_lab_mutant_library_feedback_authorization_execution_queue_operator_packet_receipts.py",
        "safe_pipeline_command": "python3 scripts/run_safe_training_pipeline.py",
        "closeout_status": "open_blocked_waiting_for_human_authorization",
        "completion_condition": "all metric decisions are reviewed, authorization validator passes, preflight rows exist, and safe pipeline passes; closeout board alone is never sufficient",
        "requires_human_input": True,
        "completion_ready": False,
        "ready_for_feedback_intake": False,
        "safe_for_model_claim": False,
        "policy": "Authorization closeout board only; not an authorization, not feedback preflight, not a training label, and not model claim readiness.",
    }


def validate_row(actual: dict[str, Any], expected: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    for field, expected_value in expected.items():
        if actual.get(field) != expected_value:
            errors.append(f"{field}_mismatch")
    if actual.get("closeout_status") != "open_blocked_waiting_for_human_authorization":
        errors.append("closeout_status_not_open_blocked")
    if actual.get("requires_human_input") is not True:
        errors.append("requires_human_input_not_true")
    if actual.get("completion_ready") is not False:
        errors.append("completion_ready_not_false")
    if actual.get("ready_for_feedback_intake") is not False:
        errors.append("ready_for_feedback_intake_not_false")
    if actual.get("safe_for_model_claim") is not False:
        errors.append("safe_for_model_claim_not_false")
    condition = str(actual.get("completion_condition") or "").lower()
    if "closeout board alone is never sufficient" not in condition:
        errors.append("completion_condition_missing_fail_closed_language")
    policy = str(actual.get("policy") or "").lower()
    for phrase in ["not an authorization", "not feedback preflight", "not a training label", "not model claim readiness"]:
        if phrase not in policy:
            errors.append("policy_missing_fail_closed_language")
            break
    return errors


def markdown_errors(path: Path) -> list[str]:
    if not path.exists():
        return ["markdown_missing"]
    text = path.read_text(encoding="utf-8").lower()
    errors: list[str] = []
    for phrase in ["not an authorization", "not feedback preflight", "not a training label", "not model claim readiness"]:
        if phrase not in text:
            errors.append("markdown_missing_fail_closed_language")
            break
    for variant in EXPECTED_REVIEW_ORDER:
        if variant.lower() not in text:
            errors.append("markdown_missing_expected_variant")
            break
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate wet-lab feedback authorization closeout board")
    parser.add_argument("--receipts", type=Path, default=RECEIPTS)
    parser.add_argument("--receipt-status", type=Path, default=RECEIPT_STATUS)
    parser.add_argument("--receipt-validation", type=Path, default=RECEIPT_VALIDATION)
    parser.add_argument("--closeout-board", type=Path, default=CLOSEOUT)
    parser.add_argument("--markdown", type=Path, default=MARKDOWN)
    parser.add_argument("--status", type=Path, default=STATUS)
    parser.add_argument("--report", type=Path, default=REPORT)
    args = parser.parse_args()

    receipts = load_jsonl(args.receipts)
    receipt_status_rows = load_jsonl(args.receipt_status)
    receipt_validation = load_json(args.receipt_validation)
    closeout_rows = load_jsonl(args.closeout_board)
    expected_rows = [
        expected_row(receipt, receipt_status_rows, receipt_validation)
        for receipt in sorted(receipts, key=lambda row: int(row.get("execution_order") or 10**9))
    ]
    expected_by_variant = {str(row.get("variant")): row for row in expected_rows}

    seen_variants: set[str] = set()
    duplicate_variants: set[str] = set()
    status_rows: list[dict[str, Any]] = []
    errors = Counter()
    for idx, row in enumerate(closeout_rows, start=1):
        variant = str(row.get("variant") or "")
        if variant in seen_variants:
            duplicate_variants.add(variant)
        seen_variants.add(variant)
        expected = expected_by_variant.get(variant)
        row_errors = ["unexpected_variant"] if expected is None else validate_row(row, expected)
        if idx <= len(EXPECTED_REVIEW_ORDER) and variant != EXPECTED_REVIEW_ORDER[idx - 1]:
            row_errors.append("review_order_mismatch")
        errors.update(row_errors)
        status_rows.append({
            "closeout_board_id": row.get("closeout_board_id"),
            "operator_packet_receipt_id": row.get("operator_packet_receipt_id"),
            "variant": variant,
            "execution_order": idx,
            "closeout_status": row.get("closeout_status"),
            "decision_rows_present": row.get("decision_rows_present"),
            "authorized_rows": row.get("authorized_rows"),
            "preflight_rows_present": row.get("preflight_rows_present"),
            "valid": not row_errors,
            "completion_ready": False,
            "requires_human_input": True,
            "errors": row_errors,
            "policy": "Validated closeout board row only; not authorization, not feedback preflight, and not model claim readiness.",
        })

    missing_variants = sorted(set(expected_by_variant) - seen_variants)
    unexpected_variants = sorted(seen_variants - set(expected_by_variant))
    actual_order = [str(row.get("variant") or "") for row in closeout_rows]
    if actual_order != EXPECTED_REVIEW_ORDER:
        errors.update({"review_order_mismatch": 1})
    if missing_variants:
        errors.update({"missing_closeout_row": len(missing_variants)})
    if unexpected_variants:
        errors.update({"unexpected_closeout_row": len(unexpected_variants)})
    if duplicate_variants:
        errors.update({"duplicate_closeout_row": len(duplicate_variants)})
        for status in status_rows:
            if status["variant"] in duplicate_variants:
                status["valid"] = False
                status["errors"].append("duplicate_closeout_row")
    if not receipt_validation.get("all_operator_packet_receipts_valid"):
        errors.update({"receipt_validation_not_ready": 1})
    for err in markdown_errors(args.markdown):
        errors.update({err: 1})

    valid_rows = sum(1 for row in status_rows if row["valid"])
    status_counts = Counter(str(row.get("closeout_status") or "") for row in closeout_rows)
    all_valid = (
        not errors
        and valid_rows == len(closeout_rows)
        and len(closeout_rows) == len(expected_rows) == len(EXPECTED_REVIEW_ORDER)
        and actual_order == EXPECTED_REVIEW_ORDER
    )

    write_jsonl(args.status, status_rows)
    report = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "local_only": True,
        "closeout_board_rows": len(closeout_rows),
        "expected_closeout_board_rows": len(expected_rows),
        "valid_closeout_board_rows": valid_rows,
        "invalid_closeout_board_rows": len(status_rows) - valid_rows,
        "missing_closeout_board_rows": len(missing_variants),
        "unexpected_closeout_board_rows": len(unexpected_variants),
        "duplicate_closeout_board_rows": len(duplicate_variants),
        "operator_packet_receipt_rows": len(receipts),
        "receipt_validation_all_rows_valid": bool(receipt_validation.get("all_operator_packet_receipts_valid")),
        "open_blocked_closeout_rows": status_counts.get("open_blocked_waiting_for_human_authorization", 0),
        "decision_rows_present": sum(int(row.get("decision_rows_present") or 0) for row in closeout_rows),
        "authorized_rows": sum(int(row.get("authorized_rows") or 0) for row in closeout_rows),
        "preflight_rows_present": sum(int(row.get("preflight_rows_present") or 0) for row in closeout_rows),
        "completion_ready_rows": 0,
        "requires_human_input_rows": len(status_rows),
        "ready_for_feedback_intake_rows": 0,
        "claim_eligible_rows_now": 0,
        "safe_for_model_claim": False,
        "all_closeout_rows_valid": all_valid,
        "review_order": actual_order,
        "expected_review_order": EXPECTED_REVIEW_ORDER,
        "closeout_status_counts": dict(sorted(status_counts.items())),
        "error_counts": dict(errors),
        "status_output": str(args.status),
        "policy": "Closeout board validation proves local missing-decision accounting only; it never authorizes rows, runs preflight, appends labels, or enables model claims.",
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({
        "closeout_board_rows": report["closeout_board_rows"],
        "valid_closeout_board_rows": report["valid_closeout_board_rows"],
        "invalid_closeout_board_rows": report["invalid_closeout_board_rows"],
        "all_closeout_rows_valid": report["all_closeout_rows_valid"],
        "review_order": report["review_order"],
        "output": str(args.report),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
