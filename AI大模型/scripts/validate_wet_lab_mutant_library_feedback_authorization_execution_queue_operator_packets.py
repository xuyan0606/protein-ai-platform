#!/usr/bin/env python3
"""Validate wet-lab feedback authorization execution queue operator packets fail-closed."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
QUEUE = AI_ROOT / "datasets" / "feedback" / "wet_lab_mutant_library_feedback_authorization_execution_queue.jsonl"
QUEUE_STATUS = AI_ROOT / "datasets" / "feedback" / "wet_lab_mutant_library_feedback_authorization_execution_queue_status.jsonl"
QUEUE_VALIDATION = AI_ROOT / "reports" / "wet_lab_mutant_library_feedback_authorization_execution_queue_validation_report.json"
PACKETS = AI_ROOT / "datasets" / "feedback" / "wet_lab_mutant_library_feedback_authorization_execution_queue_operator_packets.jsonl"
MARKDOWN = AI_ROOT / "reports" / "wet_lab_mutant_library_feedback_authorization_execution_queue_operator_packets.md"
STATUS = AI_ROOT / "datasets" / "feedback" / "wet_lab_mutant_library_feedback_authorization_execution_queue_operator_packet_status.jsonl"
REPORT = AI_ROOT / "reports" / "wet_lab_mutant_library_feedback_authorization_execution_queue_operator_packet_validation_report.json"

EXPECTED_REVIEW_ORDER = ["E331Q", "D105N", "S265T"]
PACKET_MODES = {
    "E331Q": "critical_tradeoff_bundle_review",
    "D105N": "mixed_positive_candidate_bundle_review",
    "S265T": "watch_only_bundle_review",
}
REQUIRED_REVIEW_FIELDS = [
    "authorization_decision",
    "qc_decision",
    "reviewer",
    "reviewed_at",
    "authorization_basis",
    "source_trace_reviewed",
    "numbering_reviewed",
    "unit_condition_reviewed",
    "batch_control_reviewed",
    "replicate_policy_reviewed",
    "residual_risks",
]


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
    return {
        str(row.get("variant") or ""): row
        for row in rows
        if row.get("variant")
    }


def review_focus(row: dict[str, Any]) -> list[str]:
    modes = row.get("review_mode_counts") or {}
    if modes.get("tradeoff_review_required"):
        return [
            "Review all E331Q metrics together before any metric-level decision.",
            "Do not convert acid-retention benefit into a single go label while thermal stability is no_go.",
            "Record tradeoff rationale, residual risks, and whether each metric remains separate evidence.",
        ]
    if modes.get("positive_candidate_review_required"):
        return [
            "Review source trace, numbering, units/conditions, batch/control, and replicate/QC for each positive metric.",
            "Keep the watch metric separate unless reviewer basis explicitly supports intake.",
            "Authorize only metric rows that remain defensible after QC review.",
        ]
    return [
        "Review watch-only metrics for uncertainty and missing evidence.",
        "Use needs_more_info unless reviewer can justify a reviewed evidence decision.",
        "Do not promote watch-only evidence into a go/no-go training label without explicit basis.",
    ]


def expected_packets(queue_rows: list[dict[str, Any]], status_rows: list[dict[str, Any]], queue_validation: dict[str, Any]) -> list[dict[str, Any]]:
    status_lookup = status_by_variant(status_rows)
    packets: list[dict[str, Any]] = []
    for order, row in enumerate(queue_rows, start=1):
        variant = str(row.get("variant") or "")
        status = status_lookup.get(variant, {})
        packets.append({
            "operator_packet_id": f"wetlab-mutlib-auth-exec-packet-{variant.lower()}",
            "execution_queue_id": row.get("execution_queue_id"),
            "execution_order": order,
            "variant": variant,
            "packet_mode": PACKET_MODES.get(variant, "variant_bundle_review"),
            "packet_status": "open_blocked_waiting_for_human_authorization",
            "queue_row_valid": bool(status.get("valid")),
            "queue_validation_all_rows_valid": bool(queue_validation.get("all_queue_rows_valid")),
            "metric_receipt_rows": row.get("metric_receipt_rows"),
            "review_mode_counts": row.get("review_mode_counts") or {},
            "receipt_status_counts": row.get("receipt_status_counts") or {},
            "metric_receipts": row.get("metric_receipts") or [],
            "decision_present_rows": row.get("decision_present_rows"),
            "authorized_rows": row.get("authorized_rows"),
            "preflight_present_rows": row.get("preflight_present_rows"),
            "review_focus": review_focus(row),
            "operator_open_first": "datasets/feedback/wet_lab_mutant_library_feedback_authorizations.template.jsonl",
            "write_reviewed_decisions_to": "datasets/feedback/wet_lab_mutant_library_feedback_authorizations.jsonl",
            "required_review_fields": REQUIRED_REVIEW_FIELDS,
            "validator_command": "python3 scripts/validate_wet_lab_mutant_library_feedback_authorizations.py",
            "preflight_command": "python3 scripts/build_wet_lab_mutant_library_feedback_preflight.py",
            "queue_validator_command": "python3 scripts/validate_wet_lab_mutant_library_feedback_authorization_execution_queue.py",
            "safe_pipeline_command": "python3 scripts/run_safe_training_pipeline.py",
            "completion_condition": "reviewed metric authorization decisions validate, preflight rows are generated downstream, and execution packet status is revalidated; packet alone is never sufficient",
            "requires_human_input": True,
            "completion_ready": False,
            "policy": "Execution queue operator packet only; not an authorization, not feedback preflight, not a training label, and not model claim readiness.",
        })
    return packets


def validate_packet(actual: dict[str, Any], expected: dict[str, Any]) -> list[str]:
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
    if int(actual.get("authorized_rows") or 0) != 0:
        errors.append("authorized_rows_not_zero")
    if int(actual.get("preflight_present_rows") or 0) != 0:
        errors.append("preflight_present_rows_not_zero")
    condition = str(actual.get("completion_condition") or "").lower()
    if "preflight rows are generated downstream" not in condition or "packet alone is never sufficient" not in condition:
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
    for phrase in ["not authorizations", "not feedback preflight", "not training labels", "not model claim readiness"]:
        if phrase not in text:
            errors.append("markdown_missing_fail_closed_language")
            break
    for variant in EXPECTED_REVIEW_ORDER:
        if variant.lower() not in text:
            errors.append("markdown_missing_expected_variant")
            break
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate wet-lab feedback authorization execution queue operator packets")
    parser.add_argument("--queue", type=Path, default=QUEUE)
    parser.add_argument("--queue-status", type=Path, default=QUEUE_STATUS)
    parser.add_argument("--queue-validation", type=Path, default=QUEUE_VALIDATION)
    parser.add_argument("--packets", type=Path, default=PACKETS)
    parser.add_argument("--markdown", type=Path, default=MARKDOWN)
    parser.add_argument("--status", type=Path, default=STATUS)
    parser.add_argument("--report", type=Path, default=REPORT)
    args = parser.parse_args()

    queue_rows = load_jsonl(args.queue)
    queue_status_rows = load_jsonl(args.queue_status)
    queue_validation = load_json(args.queue_validation)
    packet_rows = load_jsonl(args.packets)
    expected_rows = expected_packets(queue_rows, queue_status_rows, queue_validation)
    expected_by_variant = {str(row.get("variant")): row for row in expected_rows}

    seen_variants: set[str] = set()
    duplicate_variants: set[str] = set()
    status_rows: list[dict[str, Any]] = []
    errors = Counter()

    for idx, packet in enumerate(packet_rows, start=1):
        variant = str(packet.get("variant") or "")
        if variant in seen_variants:
            duplicate_variants.add(variant)
        seen_variants.add(variant)
        expected = expected_by_variant.get(variant)
        row_errors = ["unexpected_variant"] if expected is None else validate_packet(packet, expected)
        if idx <= len(EXPECTED_REVIEW_ORDER) and variant != EXPECTED_REVIEW_ORDER[idx - 1]:
            row_errors.append("review_order_mismatch")
        errors.update(row_errors)
        status_rows.append({
            "operator_packet_id": packet.get("operator_packet_id"),
            "execution_queue_id": packet.get("execution_queue_id"),
            "variant": variant,
            "execution_order": idx,
            "packet_mode": packet.get("packet_mode"),
            "packet_status": packet.get("packet_status"),
            "queue_row_valid": packet.get("queue_row_valid"),
            "decision_present_rows": packet.get("decision_present_rows"),
            "authorized_rows": packet.get("authorized_rows"),
            "preflight_present_rows": packet.get("preflight_present_rows"),
            "valid": not row_errors,
            "completion_ready": False,
            "requires_human_input": True,
            "errors": row_errors,
            "policy": "Validated execution queue operator packet only; not authorization, not feedback preflight, and not model claim readiness.",
        })

    missing_variants = sorted(set(expected_by_variant) - seen_variants)
    unexpected_variants = sorted(seen_variants - set(expected_by_variant))
    actual_order = [str(row.get("variant") or "") for row in packet_rows]
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
    if not queue_validation.get("all_queue_rows_valid"):
        errors.update({"queue_validation_not_ready": 1})
    for err in markdown_errors(args.markdown):
        errors.update({err: 1})

    valid_rows = sum(1 for row in status_rows if row["valid"])
    status_counts = Counter(str(row.get("packet_status") or "") for row in packet_rows)
    authorized_rows = sum(int(row.get("authorized_rows") or 0) for row in packet_rows)
    preflight_present_rows = sum(int(row.get("preflight_present_rows") or 0) for row in packet_rows)
    all_valid = (
        not errors
        and valid_rows == len(packet_rows)
        and len(packet_rows) == len(expected_rows) == len(EXPECTED_REVIEW_ORDER)
        and actual_order == EXPECTED_REVIEW_ORDER
    )

    write_jsonl(args.status, status_rows)
    report = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "local_only": True,
        "operator_packet_rows": len(packet_rows),
        "expected_operator_packet_rows": len(expected_rows),
        "valid_operator_packet_rows": valid_rows,
        "invalid_operator_packet_rows": len(status_rows) - valid_rows,
        "missing_operator_packet_rows": len(missing_variants),
        "unexpected_operator_packet_rows": len(unexpected_variants),
        "duplicate_operator_packet_rows": len(duplicate_variants),
        "execution_queue_rows": len(queue_rows),
        "queue_validation_all_rows_valid": bool(queue_validation.get("all_queue_rows_valid")),
        "open_blocked_packet_rows": status_counts.get("open_blocked_waiting_for_human_authorization", 0),
        "decision_present_rows": sum(int(row.get("decision_present_rows") or 0) for row in packet_rows),
        "authorized_rows": authorized_rows,
        "preflight_present_rows": preflight_present_rows,
        "completion_ready_rows": 0,
        "requires_human_input_rows": len(status_rows),
        "ready_for_feedback_intake_rows": 0,
        "claim_eligible_rows_now": 0,
        "safe_for_model_claim": False,
        "all_operator_packets_valid": all_valid,
        "expected_review_order": EXPECTED_REVIEW_ORDER,
        "review_order": actual_order,
        "packet_status_counts": dict(sorted(status_counts.items())),
        "error_counts": dict(errors),
        "status_output": str(args.status),
        "policy": "Execution queue operator packet validation proves local review packet integrity only; it never authorizes rows, runs preflight, appends labels, or enables model claims.",
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({
        "operator_packet_rows": report["operator_packet_rows"],
        "valid_operator_packet_rows": report["valid_operator_packet_rows"],
        "invalid_operator_packet_rows": report["invalid_operator_packet_rows"],
        "all_operator_packets_valid": report["all_operator_packets_valid"],
        "review_order": report["review_order"],
        "output": str(args.report),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
