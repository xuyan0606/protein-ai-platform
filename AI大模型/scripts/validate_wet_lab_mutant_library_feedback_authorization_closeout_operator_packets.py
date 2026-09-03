#!/usr/bin/env python3
"""Validate wet-lab feedback authorization closeout operator packets."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
CLOSEOUT = AI_ROOT / "datasets" / "feedback" / "wet_lab_mutant_library_feedback_authorization_closeout_board.jsonl"
CLOSEOUT_VALIDATION = AI_ROOT / "reports" / "wet_lab_mutant_library_feedback_authorization_closeout_board_validation_report.json"
PACKETS = AI_ROOT / "datasets" / "feedback" / "wet_lab_mutant_library_feedback_authorization_closeout_operator_packets.jsonl"
MARKDOWN = AI_ROOT / "reports" / "wet_lab_mutant_library_feedback_authorization_closeout_operator_packets.md"
STATUS = AI_ROOT / "datasets" / "feedback" / "wet_lab_mutant_library_feedback_authorization_closeout_operator_packet_status.jsonl"
REPORT = AI_ROOT / "reports" / "wet_lab_mutant_library_feedback_authorization_closeout_operator_packet_validation_report.json"

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


def closeout_by_variant(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {str(row.get("variant") or ""): row for row in rows if row.get("variant")}


def packet_focus(row: dict[str, Any]) -> list[str]:
    items = []
    if int(row.get("missing_decision_rows") or 0):
        items.append("Collect reviewed authorization decisions for all metric rows.")
    if int(row.get("missing_authorized_rows") or 0):
        items.append("Keep authorization validator closed until reviewed decisions exist.")
    if int(row.get("missing_preflight_rows") or 0):
        items.append("Run downstream preflight only after authorization rows validate.")
    items.append("Re-run closeout board validator after any human decision input.")
    return items


def expected_packet(row: dict[str, Any], validation: dict[str, Any]) -> dict[str, Any]:
    variant = str(row.get("variant") or "")
    return {
        "closeout_operator_packet_id": f"wetlab-mutlib-auth-closeout-packet-{variant.lower()}",
        "closeout_board_id": row.get("closeout_board_id"),
        "operator_packet_order": row.get("execution_order"),
        "variant": variant,
        "packet_mode": {
            "E331Q": "tradeoff_closeout_review",
            "D105N": "positive_candidate_closeout_review",
            "S265T": "watch_only_closeout_review",
        }.get(variant, "closeout_review"),
        "packet_status": "open_blocked_waiting_for_human_authorization",
        "closeout_row_valid": bool(row.get("receipt_row_valid")),
        "closeout_validation_all_rows_valid": bool(validation.get("all_closeout_rows_valid")),
        "metric_receipt_rows": row.get("metric_receipt_rows"),
        "missing_decision_rows": row.get("missing_decision_rows"),
        "missing_authorized_rows": row.get("missing_authorized_rows"),
        "missing_preflight_rows": row.get("missing_preflight_rows"),
        "decision_rows_present": row.get("decision_rows_present"),
        "authorized_rows": row.get("authorized_rows"),
        "preflight_rows_present": row.get("preflight_rows_present"),
        "required_closeout_items": row.get("required_closeout_items") or [],
        "packet_focus": packet_focus(row),
        "operator_open_first": "datasets/feedback/wet_lab_mutant_library_feedback_authorizations.template.jsonl",
        "write_reviewed_decisions_to": "datasets/feedback/wet_lab_mutant_library_feedback_authorizations.jsonl",
        "authorization_validator_command": "python3 scripts/validate_wet_lab_mutant_library_feedback_authorizations.py",
        "preflight_command": "python3 scripts/build_wet_lab_mutant_library_feedback_preflight.py",
        "closeout_validator_command": "python3 scripts/validate_wet_lab_mutant_library_feedback_authorization_closeout_board.py",
        "safe_pipeline_command": "python3 scripts/run_safe_training_pipeline.py",
        "completion_condition": "all reviewed authorization decisions validate, preflight rows exist, and closeout board revalidates; closeout packet alone is never sufficient",
        "requires_human_input": True,
        "completion_ready": False,
        "ready_for_feedback_intake": False,
        "safe_for_model_claim": False,
        "policy": "Closeout operator packet only; not an authorization, not feedback preflight, not a training label, and not model claim readiness.",
    }


def validate_row(actual: dict[str, Any], expected: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    for field, expected_value in expected.items():
        if actual.get(field) != expected_value:
            errors.append(f"{field}_mismatch")
    if actual.get("packet_status") != "open_blocked_waiting_for_human_authorization":
        errors.append("packet_status_not_open_blocked")
    if actual.get("requires_human_input") is not True:
        errors.append("requires_human_input_not_true")
    if actual.get("completion_ready") is not False:
        errors.append("completion_ready_not_false")
    if actual.get("ready_for_feedback_intake") is not False:
        errors.append("ready_for_feedback_intake_not_false")
    if actual.get("safe_for_model_claim") is not False:
        errors.append("safe_for_model_claim_not_false")
    condition = str(actual.get("completion_condition") or "").lower()
    if "closeout packet alone is never sufficient" not in condition:
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
    parser = argparse.ArgumentParser(description="Validate wet-lab feedback authorization closeout operator packets")
    parser.add_argument("--closeout", type=Path, default=CLOSEOUT)
    parser.add_argument("--closeout-validation", type=Path, default=CLOSEOUT_VALIDATION)
    parser.add_argument("--packets", type=Path, default=PACKETS)
    parser.add_argument("--markdown", type=Path, default=MARKDOWN)
    parser.add_argument("--status", type=Path, default=STATUS)
    parser.add_argument("--report", type=Path, default=REPORT)
    args = parser.parse_args()

    closeout_rows = load_jsonl(args.closeout)
    closeout_validation = load_json(args.closeout_validation)
    packets = load_jsonl(args.packets)
    expected_rows = [expected_packet(row, closeout_validation) for row in sorted(closeout_rows, key=lambda row: int(row.get("execution_order") or 10**9))]
    expected_by_variant = {str(row.get("variant")): row for row in expected_rows}

    seen_variants: set[str] = set()
    duplicate_variants: set[str] = set()
    status_rows: list[dict[str, Any]] = []
    errors = Counter()
    for idx, packet in enumerate(packets, start=1):
        variant = str(packet.get("variant") or "")
        if variant in seen_variants:
            duplicate_variants.add(variant)
        seen_variants.add(variant)
        expected = expected_by_variant.get(variant)
        row_errors = ["unexpected_variant"] if expected is None else validate_row(packet, expected)
        if idx <= len(EXPECTED_REVIEW_ORDER) and variant != EXPECTED_REVIEW_ORDER[idx - 1]:
            row_errors.append("review_order_mismatch")
        errors.update(row_errors)
        status_rows.append({
            "closeout_operator_packet_id": packet.get("closeout_operator_packet_id"),
            "closeout_board_id": packet.get("closeout_board_id"),
            "variant": variant,
            "operator_packet_order": idx,
            "packet_status": packet.get("packet_status"),
            "decision_rows_present": packet.get("decision_rows_present"),
            "authorized_rows": packet.get("authorized_rows"),
            "preflight_rows_present": packet.get("preflight_rows_present"),
            "valid": not row_errors,
            "completion_ready": False,
            "requires_human_input": True,
            "errors": row_errors,
            "policy": "Validated closeout operator packet only; not authorization, not feedback preflight, and not model claim readiness.",
        })

    missing_variants = sorted(set(expected_by_variant) - seen_variants)
    unexpected_variants = sorted(seen_variants - set(expected_by_variant))
    actual_order = [str(row.get("variant") or "") for row in packets]
    if actual_order != EXPECTED_REVIEW_ORDER:
        errors.update({"review_order_mismatch": 1})
    if missing_variants:
        errors.update({"missing_packet_row": len(missing_variants)})
    if unexpected_variants:
        errors.update({"unexpected_packet_row": len(unexpected_variants)})
    if duplicate_variants:
        errors.update({"duplicate_packet_row": len(duplicate_variants)})
        for status in status_rows:
            if status["variant"] in duplicate_variants:
                status["valid"] = False
                status["errors"].append("duplicate_packet_row")
    if not closeout_validation.get("all_closeout_rows_valid"):
        errors.update({"closeout_validation_not_ready": 1})
    for err in markdown_errors(args.markdown):
        errors.update({err: 1})

    valid_rows = sum(1 for row in status_rows if row["valid"])
    status_counts = Counter(str(row.get("packet_status") or "") for row in packets)
    all_valid = (
        not errors
        and valid_rows == len(packets)
        and len(packets) == len(expected_rows) == len(EXPECTED_REVIEW_ORDER)
        and actual_order == EXPECTED_REVIEW_ORDER
    )

    write_jsonl(args.status, status_rows)
    report = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "local_only": True,
        "closeout_operator_packet_rows": len(packets),
        "expected_closeout_operator_packet_rows": len(expected_rows),
        "valid_closeout_operator_packet_rows": valid_rows,
        "invalid_closeout_operator_packet_rows": len(status_rows) - valid_rows,
        "missing_closeout_operator_packet_rows": len(missing_variants),
        "unexpected_closeout_operator_packet_rows": len(unexpected_variants),
        "duplicate_closeout_operator_packet_rows": len(duplicate_variants),
        "closeout_board_rows": len(closeout_rows),
        "closeout_validation_all_rows_valid": bool(closeout_validation.get("all_closeout_rows_valid")),
        "open_blocked_packet_rows": status_counts.get("open_blocked_waiting_for_human_authorization", 0),
        "decision_rows_present": sum(int(row.get("decision_rows_present") or 0) for row in packets),
        "authorized_rows": sum(int(row.get("authorized_rows") or 0) for row in packets),
        "preflight_rows_present": sum(int(row.get("preflight_rows_present") or 0) for row in packets),
        "completion_ready_rows": 0,
        "requires_human_input_rows": len(status_rows),
        "ready_for_feedback_intake_rows": 0,
        "claim_eligible_rows_now": 0,
        "safe_for_model_claim": False,
        "all_closeout_operator_packets_valid": all_valid,
        "expected_review_order": EXPECTED_REVIEW_ORDER,
        "review_order": actual_order,
        "packet_status_counts": dict(sorted(status_counts.items())),
        "error_counts": dict(errors),
        "status_output": str(args.status),
        "policy": "Closeout operator packet validation proves local review packet integrity only; it never authorizes rows, runs preflight, appends labels, or enables model claims.",
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({
        "closeout_operator_packet_rows": report["closeout_operator_packet_rows"],
        "valid_closeout_operator_packet_rows": report["valid_closeout_operator_packet_rows"],
        "invalid_closeout_operator_packet_rows": report["invalid_closeout_operator_packet_rows"],
        "all_closeout_operator_packets_valid": report["all_closeout_operator_packets_valid"],
        "review_order": report["review_order"],
        "output": str(args.report),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
