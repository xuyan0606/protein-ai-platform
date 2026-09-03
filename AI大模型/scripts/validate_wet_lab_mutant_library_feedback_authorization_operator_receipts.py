#!/usr/bin/env python3
"""Validate wet-lab feedback authorization operator receipts fail-closed."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
CHECKLIST = AI_ROOT / "datasets" / "feedback" / "wet_lab_mutant_library_feedback_authorization_operator_checklist.jsonl"
CHECKLIST_VALIDATION = AI_ROOT / "reports" / "wet_lab_mutant_library_feedback_authorization_operator_checklist_validation_report.json"
AUTH_DECISIONS = AI_ROOT / "datasets" / "feedback" / "wet_lab_mutant_library_feedback_authorizations.jsonl"
AUTH_VALIDATION = AI_ROOT / "reports" / "wet_lab_mutant_library_feedback_authorization_validation_report.json"
PREFLIGHT = AI_ROOT / "datasets" / "feedback" / "wet_lab_mutant_library_feedback_preflight.jsonl"
RECEIPTS = AI_ROOT / "datasets" / "feedback" / "wet_lab_mutant_library_feedback_authorization_operator_receipts.jsonl"
STATUS = AI_ROOT / "datasets" / "feedback" / "wet_lab_mutant_library_feedback_authorization_operator_receipt_status.jsonl"
REPORT = AI_ROOT / "reports" / "wet_lab_mutant_library_feedback_authorization_operator_receipt_validation_report.json"


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


def expected_status(decision_present: bool, authorized: bool, preflight_present: bool) -> str:
    if decision_present and not authorized:
        return "decision_present_but_not_authorized"
    if authorized and not preflight_present:
        return "authorized_waiting_for_preflight"
    if authorized and preflight_present:
        return "preflight_present_but_receipt_still_fail_closed"
    return "open_blocked_no_authorization_decision"


def validate_row(
    row: dict[str, Any],
    checklist: dict[str, Any],
    checklist_validated: bool,
    decision: dict[str, Any] | None,
    validation: dict[str, Any],
    preflight_present: bool,
) -> list[str]:
    errors: list[str] = []
    cid = str(checklist.get("feedback_candidate_id") or "")
    authorized = bool(validation.get("authorized_for_feedback_intake"))
    expected = {
        "operator_receipt_id": f"wetlab-mutlib-auth-receipt-{cid.replace('wetlab-mutlib-', '')}",
        "operator_checklist_id": checklist.get("operator_checklist_id"),
        "feedback_candidate_id": cid,
        "variant": checklist.get("variant"),
        "metric_name": checklist.get("metric_name"),
        "review_mode": checklist.get("review_mode"),
        "checklist_status": checklist.get("checklist_status"),
        "checklist_validated": checklist_validated,
        "decision_input": "datasets/feedback/wet_lab_mutant_library_feedback_authorizations.jsonl",
        "decision_row_present": decision is not None,
        "authorization_decision": decision.get("authorization_decision") if decision else None,
        "authorization_valid": bool(validation.get("valid")),
        "authorized_for_feedback_intake": authorized,
        "authorization_errors": validation.get("errors") or [],
        "preflight_input": "datasets/feedback/wet_lab_mutant_library_feedback_preflight.jsonl",
        "preflight_row_present": preflight_present,
        "receipt_status": expected_status(decision is not None, authorized, preflight_present),
        "validator_command": "python3 scripts/validate_wet_lab_mutant_library_feedback_authorizations.py",
        "preflight_command": "python3 scripts/build_wet_lab_mutant_library_feedback_preflight.py",
        "safe_pipeline_command": "python3 scripts/run_safe_training_pipeline.py",
        "requires_human_input": True,
        "completion_ready": False,
    }
    for field, expected_value in expected.items():
        if row.get(field) != expected_value:
            errors.append(f"{field}_mismatch")

    condition = str(row.get("completion_condition") or "").lower()
    if "authorization validator" not in condition or "never sufficient by themselves" not in condition:
        errors.append("completion_condition_missing_fail_closed_language")
    policy = str(row.get("policy") or "").lower()
    for phrase in ["not an authorization", "not feedback preflight", "not a training label"]:
        if phrase not in policy:
            errors.append("policy_missing_fail_closed_language")
            break
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate wet-lab feedback authorization operator receipts")
    parser.add_argument("--checklist", type=Path, default=CHECKLIST)
    parser.add_argument("--checklist-validation", type=Path, default=CHECKLIST_VALIDATION)
    parser.add_argument("--authorization-decisions", type=Path, default=AUTH_DECISIONS)
    parser.add_argument("--authorization-validation", type=Path, default=AUTH_VALIDATION)
    parser.add_argument("--preflight", type=Path, default=PREFLIGHT)
    parser.add_argument("--receipts", type=Path, default=RECEIPTS)
    parser.add_argument("--status", type=Path, default=STATUS)
    parser.add_argument("--report", type=Path, default=REPORT)
    args = parser.parse_args()

    checklist_rows = load_jsonl(args.checklist)
    checklist_by_id = {str(row.get("feedback_candidate_id")): row for row in checklist_rows}
    checklist_validation = load_json(args.checklist_validation)
    checklist_validated = bool(checklist_validation.get("all_checklist_rows_valid"))
    decisions = decision_by_candidate(load_jsonl(args.authorization_decisions))
    auth_validation = load_json(args.authorization_validation)
    validation_by_id = validation_by_candidate(auth_validation)
    preflight_id_set = preflight_ids(load_jsonl(args.preflight))
    receipts = load_jsonl(args.receipts)

    seen_ids: set[str] = set()
    duplicate_ids: set[str] = set()
    status_rows: list[dict[str, Any]] = []
    errors = Counter()

    for receipt in receipts:
        cid = str(receipt.get("feedback_candidate_id") or "")
        if cid in seen_ids:
            duplicate_ids.add(cid)
        seen_ids.add(cid)
        checklist = checklist_by_id.get(cid)
        row_errors = ["unexpected_feedback_candidate_id"] if checklist is None else validate_row(
            receipt,
            checklist,
            checklist_validated,
            decisions.get(cid),
            validation_by_id.get(cid, {}),
            cid in preflight_id_set,
        )
        errors.update(row_errors)
        status_rows.append({
            "operator_receipt_id": receipt.get("operator_receipt_id"),
            "operator_checklist_id": receipt.get("operator_checklist_id"),
            "feedback_candidate_id": cid,
            "variant": receipt.get("variant"),
            "metric_name": receipt.get("metric_name"),
            "receipt_status": receipt.get("receipt_status"),
            "decision_row_present": receipt.get("decision_row_present"),
            "preflight_row_present": receipt.get("preflight_row_present"),
            "valid": not row_errors,
            "completion_ready": False,
            "requires_human_input": True,
            "errors": row_errors,
            "policy": "Validated receipt row only; not authorization, not feedback preflight, and not model claim readiness.",
        })

    missing_ids = sorted(set(checklist_by_id) - seen_ids)
    unexpected_ids = sorted(seen_ids - set(checklist_by_id))
    if missing_ids:
        errors.update({"missing_receipt_row": len(missing_ids)})
    if unexpected_ids:
        errors.update({"unexpected_receipt_row": len(unexpected_ids)})
    if duplicate_ids:
        errors.update({"duplicate_receipt_row": len(duplicate_ids)})
        for status in status_rows:
            if status["feedback_candidate_id"] in duplicate_ids:
                status["valid"] = False
                status["errors"].append("duplicate_receipt_row")
    if not checklist_validated:
        errors.update({"checklist_validation_not_ready": 1})

    valid_rows = sum(1 for row in status_rows if row["valid"])
    status_counts = Counter(str(row.get("receipt_status") or "") for row in receipts)
    authorized_rows = sum(1 for row in receipts if row.get("authorized_for_feedback_intake") is True)
    preflight_present_rows = sum(1 for row in receipts if row.get("preflight_row_present") is True)
    all_valid = not errors and valid_rows == len(receipts) and len(receipts) == len(checklist_rows)

    write_jsonl(args.status, status_rows)
    report = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "local_only": True,
        "operator_receipt_rows": len(receipts),
        "expected_operator_receipt_rows": len(checklist_rows),
        "valid_receipt_rows": valid_rows,
        "invalid_receipt_rows": len(status_rows) - valid_rows,
        "missing_receipt_rows": len(missing_ids),
        "unexpected_receipt_rows": len(unexpected_ids),
        "duplicate_receipt_rows": len(duplicate_ids),
        "checklist_all_rows_valid": checklist_validated,
        "decision_input_rows": len(decisions),
        "authorization_validation_rows": auth_validation.get("authorization_rows"),
        "valid_authorization_rows": auth_validation.get("valid_authorization_rows"),
        "authorized_rows": authorized_rows,
        "preflight_present_rows": preflight_present_rows,
        "open_blocked_receipt_rows": status_counts.get("open_blocked_no_authorization_decision", 0),
        "decision_present_but_not_authorized_rows": status_counts.get("decision_present_but_not_authorized", 0),
        "authorized_waiting_for_preflight_rows": status_counts.get("authorized_waiting_for_preflight", 0),
        "completion_ready_rows": 0,
        "requires_human_input_rows": len(status_rows),
        "ready_for_feedback_intake_rows": 0,
        "claim_eligible_rows_now": 0,
        "safe_for_model_claim": False,
        "all_receipt_rows_valid": all_valid,
        "receipt_status_counts": dict(sorted(status_counts.items())),
        "error_counts": dict(errors),
        "status_output": str(args.status),
        "policy": "Receipt validation proves local operator input accounting only; it never authorizes rows, runs preflight, appends labels, or enables model claims.",
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({
        "operator_receipt_rows": report["operator_receipt_rows"],
        "valid_receipt_rows": report["valid_receipt_rows"],
        "invalid_receipt_rows": report["invalid_receipt_rows"],
        "all_receipt_rows_valid": report["all_receipt_rows_valid"],
        "output": str(args.report),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
