#!/usr/bin/env python3
"""Build receipt/status rows for wet-lab feedback authorization operator checklist."""

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
PREFLIGHT_REPORT = AI_ROOT / "reports" / "wet_lab_mutant_library_feedback_preflight_report.json"
OUTPUT = AI_ROOT / "datasets" / "feedback" / "wet_lab_mutant_library_feedback_authorization_operator_receipts.jsonl"
REPORT = AI_ROOT / "reports" / "wet_lab_mutant_library_feedback_authorization_operator_receipt_report.json"


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def validation_by_candidate(report: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        str(row.get("feedback_candidate_id")): row
        for row in report.get("records") or []
        if isinstance(row, dict) and row.get("feedback_candidate_id")
    }


def decision_by_candidate(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {
        str(row.get("feedback_candidate_id")): row
        for row in rows
        if row.get("feedback_candidate_id")
    }


def preflight_ids(rows: list[dict[str, Any]]) -> set[str]:
    return {str(row.get("feedback_candidate_id")) for row in rows if row.get("feedback_candidate_id")}


def main() -> int:
    parser = argparse.ArgumentParser(description="Build wet-lab feedback authorization operator receipts")
    parser.add_argument("--checklist", type=Path, default=CHECKLIST)
    parser.add_argument("--checklist-validation", type=Path, default=CHECKLIST_VALIDATION)
    parser.add_argument("--authorization-decisions", type=Path, default=AUTH_DECISIONS)
    parser.add_argument("--authorization-validation", type=Path, default=AUTH_VALIDATION)
    parser.add_argument("--preflight", type=Path, default=PREFLIGHT)
    parser.add_argument("--preflight-report", type=Path, default=PREFLIGHT_REPORT)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    parser.add_argument("--report", type=Path, default=REPORT)
    args = parser.parse_args()

    checklist = load_jsonl(args.checklist)
    checklist_validation = load_json(args.checklist_validation)
    decisions = decision_by_candidate(load_jsonl(args.authorization_decisions))
    auth_validation = load_json(args.authorization_validation)
    auth_validation_by_id = validation_by_candidate(auth_validation)
    preflight_rows = load_jsonl(args.preflight)
    preflight_id_set = preflight_ids(preflight_rows)
    preflight_report = load_json(args.preflight_report)

    rows: list[dict[str, Any]] = []
    for item in sorted(checklist, key=lambda row: int(row.get("execution_order") or 10**9)):
        cid = str(item.get("feedback_candidate_id") or "")
        decision = decisions.get(cid)
        validation = auth_validation_by_id.get(cid, {})
        authorized = bool(validation.get("authorized_for_feedback_intake"))
        preflight_present = cid in preflight_id_set
        receipt_status = "open_blocked_no_authorization_decision"
        if decision is not None and not authorized:
            receipt_status = "decision_present_but_not_authorized"
        if authorized and not preflight_present:
            receipt_status = "authorized_waiting_for_preflight"
        if authorized and preflight_present:
            receipt_status = "preflight_present_but_receipt_still_fail_closed"
        rows.append({
            "operator_receipt_id": f"wetlab-mutlib-auth-receipt-{cid.replace('wetlab-mutlib-', '')}",
            "operator_checklist_id": item.get("operator_checklist_id"),
            "feedback_candidate_id": cid,
            "variant": item.get("variant"),
            "metric_name": item.get("metric_name"),
            "review_mode": item.get("review_mode"),
            "checklist_status": item.get("checklist_status"),
            "checklist_validated": bool(checklist_validation.get("all_checklist_rows_valid")),
            "decision_input": str(args.authorization_decisions.relative_to(AI_ROOT)),
            "decision_row_present": decision is not None,
            "authorization_decision": decision.get("authorization_decision") if decision else None,
            "authorization_valid": bool(validation.get("valid")),
            "authorized_for_feedback_intake": authorized,
            "authorization_errors": validation.get("errors") or [],
            "preflight_input": str(args.preflight.relative_to(AI_ROOT)),
            "preflight_row_present": preflight_present,
            "receipt_status": receipt_status,
            "validator_command": "python3 scripts/validate_wet_lab_mutant_library_feedback_authorizations.py",
            "preflight_command": "python3 scripts/build_wet_lab_mutant_library_feedback_preflight.py",
            "safe_pipeline_command": "python3 scripts/run_safe_training_pipeline.py",
            "completion_condition": "authorization validator and downstream preflight must pass; receipt rows are never sufficient by themselves",
            "requires_human_input": True,
            "completion_ready": False,
            "policy": "Operator receipt only; not an authorization, not feedback preflight, and not a training label.",
        })

    status_counts = Counter(row["receipt_status"] for row in rows)
    mode_counts = Counter(str(row.get("review_mode") or "") for row in rows)
    write_jsonl(args.output, rows)
    report = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "local_only": True,
        "operator_receipt_rows": len(rows),
        "operator_checklist_rows": len(checklist),
        "checklist_all_rows_valid": bool(checklist_validation.get("all_checklist_rows_valid")),
        "decision_input_rows": len(decisions),
        "authorization_validation_rows": auth_validation.get("authorization_rows"),
        "valid_authorization_rows": auth_validation.get("valid_authorization_rows"),
        "authorized_rows": sum(1 for row in rows if row["authorized_for_feedback_intake"]),
        "preflight_rows": len(preflight_rows),
        "preflight_report_rows": preflight_report.get("preflight_rows"),
        "open_blocked_receipt_rows": status_counts.get("open_blocked_no_authorization_decision", 0),
        "decision_present_but_not_authorized_rows": status_counts.get("decision_present_but_not_authorized", 0),
        "authorized_waiting_for_preflight_rows": status_counts.get("authorized_waiting_for_preflight", 0),
        "preflight_present_rows": sum(1 for row in rows if row["preflight_row_present"]),
        "tradeoff_review_receipt_rows": mode_counts.get("tradeoff_review_required", 0),
        "completion_ready_rows": 0,
        "requires_human_input_rows": len(rows),
        "ready_for_feedback_intake_rows": 0,
        "claim_eligible_rows_now": 0,
        "safe_for_model_claim": False,
        "receipt_status_counts": dict(sorted(status_counts.items())),
        "mode_counts": dict(sorted(mode_counts.items())),
        "output": str(args.output),
        "policy": "Receipts record local operator input status only; they never grant authorization, write preflight, append labels, or enable model claims.",
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({
        "operator_receipt_rows": report["operator_receipt_rows"],
        "decision_input_rows": report["decision_input_rows"],
        "authorized_rows": report["authorized_rows"],
        "open_blocked_receipt_rows": report["open_blocked_receipt_rows"],
        "output": str(args.report),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
