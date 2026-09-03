#!/usr/bin/env python3
"""Validate wet-lab feedback authorization execution queue operator packet receipts."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
PACKETS = AI_ROOT / "datasets" / "feedback" / "wet_lab_mutant_library_feedback_authorization_execution_queue_operator_packets.jsonl"
PACKET_VALIDATION = AI_ROOT / "reports" / "wet_lab_mutant_library_feedback_authorization_execution_queue_operator_packet_validation_report.json"
AUTH_DECISIONS = AI_ROOT / "datasets" / "feedback" / "wet_lab_mutant_library_feedback_authorizations.jsonl"
AUTH_VALIDATION = AI_ROOT / "reports" / "wet_lab_mutant_library_feedback_authorization_validation_report.json"
PREFLIGHT = AI_ROOT / "datasets" / "feedback" / "wet_lab_mutant_library_feedback_preflight.jsonl"
PREFLIGHT_REPORT = AI_ROOT / "reports" / "wet_lab_mutant_library_feedback_preflight_report.json"
RECEIPTS = AI_ROOT / "datasets" / "feedback" / "wet_lab_mutant_library_feedback_authorization_execution_queue_operator_packet_receipts.jsonl"
STATUS = AI_ROOT / "datasets" / "feedback" / "wet_lab_mutant_library_feedback_authorization_execution_queue_operator_packet_receipt_status.jsonl"
REPORT = AI_ROOT / "reports" / "wet_lab_mutant_library_feedback_authorization_execution_queue_operator_packet_receipt_validation_report.json"

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


def decision_by_candidate(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {
        str(row.get("feedback_candidate_id")): row
        for row in rows
        if row.get("feedback_candidate_id")
    }


def validation_by_candidate(report: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        str(row.get("feedback_candidate_id")): row
        for row in report.get("records") or []
        if isinstance(row, dict) and row.get("feedback_candidate_id")
    }


def preflight_ids(rows: list[dict[str, Any]]) -> set[str]:
    return {str(row.get("feedback_candidate_id")) for row in rows if row.get("feedback_candidate_id")}


def packet_candidate_ids(packet: dict[str, Any]) -> list[str]:
    ids: list[str] = []
    for receipt in packet.get("metric_receipts") or []:
        if isinstance(receipt, dict) and receipt.get("feedback_candidate_id"):
            ids.append(str(receipt.get("feedback_candidate_id")))
    return ids


def receipt_status(metric_rows: int, decision_rows: int, authorized_rows: int, preflight_rows: int) -> str:
    if decision_rows == 0:
        return "open_blocked_no_authorization_decisions"
    if authorized_rows < metric_rows:
        return "partial_or_non_authorized_decisions_present"
    if authorized_rows == metric_rows and preflight_rows < metric_rows:
        return "authorized_waiting_for_preflight"
    if authorized_rows == metric_rows and preflight_rows == metric_rows:
        return "preflight_present_but_packet_still_fail_closed"
    return "open_blocked_review_state_inconsistent"


def expected_receipt(
    packet: dict[str, Any],
    packet_validation: dict[str, Any],
    decisions: dict[str, dict[str, Any]],
    validations: dict[str, dict[str, Any]],
    preflight_id_set: set[str],
    auth_validation: dict[str, Any],
    preflight_report: dict[str, Any],
) -> dict[str, Any]:
    candidate_ids = packet_candidate_ids(packet)
    candidate_details: list[dict[str, Any]] = []
    decision_rows = 0
    authorized_rows = 0
    preflight_present_rows = 0
    for cid in candidate_ids:
        decision = decisions.get(cid)
        validation = validations.get(cid, {})
        authorized = bool(validation.get("authorized_for_feedback_intake"))
        preflight_present = cid in preflight_id_set
        if decision is not None:
            decision_rows += 1
        if authorized:
            authorized_rows += 1
        if preflight_present:
            preflight_present_rows += 1
        candidate_details.append({
            "feedback_candidate_id": cid,
            "decision_row_present": decision is not None,
            "authorization_decision": decision.get("authorization_decision") if decision else None,
            "authorization_valid": bool(validation.get("valid")),
            "authorized_for_feedback_intake": authorized,
            "authorization_errors": validation.get("errors") or [],
            "preflight_row_present": preflight_present,
        })

    return {
        "operator_packet_receipt_id": f"{packet.get('operator_packet_id')}-receipt",
        "operator_packet_id": packet.get("operator_packet_id"),
        "execution_queue_id": packet.get("execution_queue_id"),
        "execution_order": packet.get("execution_order"),
        "variant": packet.get("variant"),
        "packet_mode": packet.get("packet_mode"),
        "packet_status": packet.get("packet_status"),
        "packet_validation_all_rows_valid": bool(packet_validation.get("all_operator_packets_valid")),
        "packet_row_valid": True,
        "metric_receipt_rows": packet.get("metric_receipt_rows"),
        "feedback_candidate_ids": candidate_ids,
        "decision_input": "datasets/feedback/wet_lab_mutant_library_feedback_authorizations.jsonl",
        "decision_rows_present": decision_rows,
        "authorization_validation_rows": auth_validation.get("authorization_rows"),
        "valid_authorization_rows": auth_validation.get("valid_authorization_rows"),
        "authorized_rows": authorized_rows,
        "preflight_input": "datasets/feedback/wet_lab_mutant_library_feedback_preflight.jsonl",
        "preflight_rows_present": preflight_present_rows,
        "preflight_report_rows": preflight_report.get("preflight_rows"),
        "candidate_authorization_receipts": candidate_details,
        "receipt_status": receipt_status(len(candidate_ids), decision_rows, authorized_rows, preflight_present_rows),
        "validator_command": "python3 scripts/validate_wet_lab_mutant_library_feedback_authorizations.py",
        "preflight_command": "python3 scripts/build_wet_lab_mutant_library_feedback_preflight.py",
        "packet_validator_command": "python3 scripts/validate_wet_lab_mutant_library_feedback_authorization_execution_queue_operator_packets.py",
        "safe_pipeline_command": "python3 scripts/run_safe_training_pipeline.py",
        "completion_condition": "all metric authorization decisions validate and downstream preflight rows exist; packet receipts are never sufficient by themselves",
        "requires_human_input": True,
        "completion_ready": False,
        "policy": "Execution queue operator packet receipt only; not an authorization, not feedback preflight, not a training label, and not model claim readiness.",
    }


def validate_row(actual: dict[str, Any], expected: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    for field, expected_value in expected.items():
        if actual.get(field) != expected_value:
            errors.append(f"{field}_mismatch")
    if actual.get("requires_human_input") is not True:
        errors.append("requires_human_input_not_true")
    if actual.get("completion_ready") is not False:
        errors.append("completion_ready_not_false")
    if int(actual.get("authorized_rows") or 0) != 0:
        errors.append("authorized_rows_not_zero")
    if int(actual.get("preflight_rows_present") or 0) != 0:
        errors.append("preflight_rows_present_not_zero")
    condition = str(actual.get("completion_condition") or "").lower()
    if "authorization decisions validate" not in condition or "never sufficient by themselves" not in condition:
        errors.append("completion_condition_missing_fail_closed_language")
    policy = str(actual.get("policy") or "").lower()
    for phrase in ["not an authorization", "not feedback preflight", "not a training label", "not model claim readiness"]:
        if phrase not in policy:
            errors.append("policy_missing_fail_closed_language")
            break
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate wet-lab feedback authorization execution queue operator packet receipts")
    parser.add_argument("--packets", type=Path, default=PACKETS)
    parser.add_argument("--packet-validation", type=Path, default=PACKET_VALIDATION)
    parser.add_argument("--authorization-decisions", type=Path, default=AUTH_DECISIONS)
    parser.add_argument("--authorization-validation", type=Path, default=AUTH_VALIDATION)
    parser.add_argument("--preflight", type=Path, default=PREFLIGHT)
    parser.add_argument("--preflight-report", type=Path, default=PREFLIGHT_REPORT)
    parser.add_argument("--receipts", type=Path, default=RECEIPTS)
    parser.add_argument("--status", type=Path, default=STATUS)
    parser.add_argument("--report", type=Path, default=REPORT)
    args = parser.parse_args()

    packets = load_jsonl(args.packets)
    packet_validation = load_json(args.packet_validation)
    decisions = decision_by_candidate(load_jsonl(args.authorization_decisions))
    auth_validation = load_json(args.authorization_validation)
    validations = validation_by_candidate(auth_validation)
    preflight_rows = load_jsonl(args.preflight)
    preflight_id_set = preflight_ids(preflight_rows)
    preflight_report = load_json(args.preflight_report)
    receipts = load_jsonl(args.receipts)

    expected_rows = [
        expected_receipt(packet, packet_validation, decisions, validations, preflight_id_set, auth_validation, preflight_report)
        for packet in sorted(packets, key=lambda row: int(row.get("execution_order") or 10**9))
    ]
    expected_by_variant = {str(row.get("variant")): row for row in expected_rows}

    seen_variants: set[str] = set()
    duplicate_variants: set[str] = set()
    status_rows: list[dict[str, Any]] = []
    errors = Counter()
    for idx, receipt in enumerate(receipts, start=1):
        variant = str(receipt.get("variant") or "")
        if variant in seen_variants:
            duplicate_variants.add(variant)
        seen_variants.add(variant)
        expected = expected_by_variant.get(variant)
        row_errors = ["unexpected_variant"] if expected is None else validate_row(receipt, expected)
        if idx <= len(EXPECTED_REVIEW_ORDER) and variant != EXPECTED_REVIEW_ORDER[idx - 1]:
            row_errors.append("review_order_mismatch")
        errors.update(row_errors)
        status_rows.append({
            "operator_packet_receipt_id": receipt.get("operator_packet_receipt_id"),
            "operator_packet_id": receipt.get("operator_packet_id"),
            "variant": variant,
            "execution_order": idx,
            "receipt_status": receipt.get("receipt_status"),
            "decision_rows_present": receipt.get("decision_rows_present"),
            "authorized_rows": receipt.get("authorized_rows"),
            "preflight_rows_present": receipt.get("preflight_rows_present"),
            "valid": not row_errors,
            "completion_ready": False,
            "requires_human_input": True,
            "errors": row_errors,
            "policy": "Validated packet receipt only; not authorization, not feedback preflight, and not model claim readiness.",
        })

    missing_variants = sorted(set(expected_by_variant) - seen_variants)
    unexpected_variants = sorted(seen_variants - set(expected_by_variant))
    actual_order = [str(row.get("variant") or "") for row in receipts]
    if actual_order != EXPECTED_REVIEW_ORDER:
        errors.update({"review_order_mismatch": 1})
    if missing_variants:
        errors.update({"missing_receipt_row": len(missing_variants)})
    if unexpected_variants:
        errors.update({"unexpected_receipt_row": len(unexpected_variants)})
    if duplicate_variants:
        errors.update({"duplicate_receipt_row": len(duplicate_variants)})
        for status in status_rows:
            if status["variant"] in duplicate_variants:
                status["valid"] = False
                status["errors"].append("duplicate_receipt_row")
    if not packet_validation.get("all_operator_packets_valid"):
        errors.update({"packet_validation_not_ready": 1})

    valid_rows = sum(1 for row in status_rows if row["valid"])
    status_counts = Counter(str(row.get("receipt_status") or "") for row in receipts)
    all_valid = (
        not errors
        and valid_rows == len(receipts)
        and len(receipts) == len(expected_rows) == len(EXPECTED_REVIEW_ORDER)
        and actual_order == EXPECTED_REVIEW_ORDER
    )

    write_jsonl(args.status, status_rows)
    report = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "local_only": True,
        "operator_packet_receipt_rows": len(receipts),
        "expected_operator_packet_receipt_rows": len(expected_rows),
        "valid_operator_packet_receipt_rows": valid_rows,
        "invalid_operator_packet_receipt_rows": len(status_rows) - valid_rows,
        "missing_operator_packet_receipt_rows": len(missing_variants),
        "unexpected_operator_packet_receipt_rows": len(unexpected_variants),
        "duplicate_operator_packet_receipt_rows": len(duplicate_variants),
        "operator_packet_rows": len(packets),
        "packet_validation_all_rows_valid": bool(packet_validation.get("all_operator_packets_valid")),
        "metric_receipt_rows": sum(int(row.get("metric_receipt_rows") or 0) for row in receipts),
        "decision_input_rows": len(decisions),
        "authorization_validation_rows": auth_validation.get("authorization_rows"),
        "valid_authorization_rows": auth_validation.get("valid_authorization_rows"),
        "authorized_rows": sum(int(row.get("authorized_rows") or 0) for row in receipts),
        "preflight_rows": len(preflight_rows),
        "preflight_report_rows": preflight_report.get("preflight_rows"),
        "preflight_present_rows": sum(int(row.get("preflight_rows_present") or 0) for row in receipts),
        "open_blocked_packet_receipt_rows": status_counts.get("open_blocked_no_authorization_decisions", 0),
        "completion_ready_rows": 0,
        "requires_human_input_rows": len(status_rows),
        "ready_for_feedback_intake_rows": 0,
        "claim_eligible_rows_now": 0,
        "safe_for_model_claim": False,
        "all_operator_packet_receipts_valid": all_valid,
        "expected_review_order": EXPECTED_REVIEW_ORDER,
        "review_order": actual_order,
        "receipt_status_counts": dict(sorted(status_counts.items())),
        "error_counts": dict(errors),
        "status_output": str(args.status),
        "policy": "Packet receipt validation proves local authorization/preflight accounting only; it never authorizes rows, runs preflight, appends labels, or enables model claims.",
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({
        "operator_packet_receipt_rows": report["operator_packet_receipt_rows"],
        "valid_operator_packet_receipt_rows": report["valid_operator_packet_receipt_rows"],
        "invalid_operator_packet_receipt_rows": report["invalid_operator_packet_receipt_rows"],
        "all_operator_packet_receipts_valid": report["all_operator_packet_receipts_valid"],
        "review_order": report["review_order"],
        "output": str(args.report),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
