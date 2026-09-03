#!/usr/bin/env python3
"""Build current execution eligibility matrix for enzyme agent actions."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
OUT_JSONL = AI_ROOT / "datasets" / "governance" / "enzyme_agent_execution_eligibility_matrix.jsonl"
OUT_REPORT = AI_ROOT / "reports" / "enzyme_agent_execution_eligibility_matrix_report.json"
EXECUTION_WAVE = AI_ROOT / "reports" / "enzyme_agent_controlled_execution_wave_report.json"


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def eligibility_for(action: dict[str, Any]) -> tuple[str, list[str]]:
    classification = action.get("classification")
    reasons: list[str] = []
    if classification == "recommended_read_only":
        reasons.append("read_only_planning_allowed_but_not_execution_claim")
    elif classification == "executable_after_user_confirmation":
        reasons.append("requires_explicit_user_confirmation")
        reasons.append("requires_execution_receipt")
        reasons.append("requires_validator_artifacts")
    elif classification == "blocked_requires_human_decision":
        reasons.append("blocked_requires_human_decision")
        if action.get("writes_formal_decision"):
            reasons.append("writes_formal_decision_requires_manual_formal_file")
    elif classification == "forbidden_for_current_request":
        reasons.append("forbidden_for_current_request")
    else:
        reasons.append("unknown_classification")
    return "blocked_current_request", reasons


def current_execution_allowed(action: dict[str, Any], receipt: dict[str, Any] | None) -> bool:
    if not receipt:
        return False
    if action.get("classification") not in {"recommended_read_only", "executable_after_user_confirmation"}:
        return False
    if action.get("action_id") == "act_safe_pipeline":
        return False
    return receipt.get("return_status") == "executed_passed"


def main() -> int:
    parser = argparse.ArgumentParser(description="Build enzyme agent execution eligibility matrix")
    parser.add_argument("--output-jsonl", type=Path, default=OUT_JSONL)
    parser.add_argument("--output-report", type=Path, default=OUT_REPORT)
    args = parser.parse_args()

    created_at = datetime.now(timezone.utc).isoformat()
    plan = load_json(AI_ROOT / "reports" / "enzyme_resource_retrieval_plan_report.json")
    trace = load_json(AI_ROOT / "reports" / "enzyme_agent_trace_audit_report.json")
    receipt_gate = load_json(AI_ROOT / "reports" / "enzyme_agent_execution_receipt_gate_report.json")
    receipt_validation = load_json(AI_ROOT / "reports" / "enzyme_agent_execution_receipt_gate_validation_report.json")
    receipt_regression = load_json(AI_ROOT / "reports" / "enzyme_agent_execution_receipt_safety_regression_report.json")
    execution_wave = load_json(EXECUTION_WAVE)
    receipts = load_jsonl(AI_ROOT / "datasets" / "governance" / "enzyme_agent_execution_receipts.local.jsonl")

    executed_ids = set(execution_wave.get("executed_action_ids") or trace.get("executed_action_ids") or [])
    receipt_ids = set(receipt_gate.get("receipt_action_ids") or [])
    receipts_by_action = {row.get("action_id"): row for row in receipts}
    rows: list[dict[str, Any]] = []
    for action in plan.get("actions") or []:
        status, reasons = eligibility_for(action)
        action_id = action.get("action_id")
        receipt = receipts_by_action.get(action_id)
        receipt_status = receipt.get("return_status") if receipt else None
        executed_in_wave = action_id in executed_ids
        allowed_now = current_execution_allowed(action, receipt)
        if receipt_status in {"executed_passed", "executed_failed", "blocked"}:
            status = receipt_status
        elif action_id == "act_safe_pipeline" and execution_wave.get("skipped_actions"):
            status = "skipped"
        rows.append({
            "created_at": created_at,
            "local_only": True,
            "plan_id": plan.get("plan_id"),
            "action_id": action_id,
            "title": action.get("title"),
            "classification": action.get("classification"),
            "risk_level": action.get("risk_level"),
            "tool_name": action.get("tool_name"),
            "allowed_execution_mode": action.get("allowed_execution_mode"),
            "human_confirmation_required": bool(
                action.get("human_confirmation_required")
                or action.get("classification") == "executable_after_user_confirmation"
            ),
            "formal_decision_required": bool(action.get("writes_formal_decision")),
            "receipt_required": action.get("classification") in {"executable_after_user_confirmation", "recommended_read_only"},
            "validator_artifacts_required": action.get("classification") in {"executable_after_user_confirmation", "recommended_read_only"},
            "authorization_ref": execution_wave.get("authorization_ref"),
            "current_execution_allowed": allowed_now,
            "execution_status": status,
            "blocked_reasons": reasons,
            "executed_in_current_trace": executed_in_wave,
            "receipt_present": action_id in receipt_ids,
            "receipt_status": receipt_status,
            "executed_with_receipt": bool(executed_in_wave and action_id in receipt_ids),
            "writes_training_rows": bool(action.get("writes_training_rows")),
            "safe_for_training_import": False,
            "safe_for_model_claim": False,
            "release_ready": False,
        })

    classification_counts: dict[str, int] = {}
    for row in rows:
        classification_counts[row["classification"]] = classification_counts.get(row["classification"], 0) + 1

    report = {
        "created_at": created_at,
        "local_only": True,
        "plan_id": plan.get("plan_id"),
        "action_rows": len(rows),
        "classification_counts": classification_counts,
        "current_execution_allowed_rows": sum(1 for row in rows if row["current_execution_allowed"]),
        "requires_user_confirmation_rows": sum(1 for row in rows if row["human_confirmation_required"]),
        "formal_decision_required_rows": sum(1 for row in rows if row["formal_decision_required"]),
        "receipt_required_rows": sum(1 for row in rows if row["receipt_required"]),
        "executed_in_current_trace_rows": sum(1 for row in rows if row["executed_in_current_trace"]),
        "receipt_present_rows": sum(1 for row in rows if row["receipt_present"]),
        "executed_with_receipt_rows": sum(1 for row in rows if row["executed_with_receipt"]),
        "executed_passed_rows": sum(1 for row in rows if row["receipt_status"] == "executed_passed"),
        "executed_failed_rows": sum(1 for row in rows if row["receipt_status"] == "executed_failed"),
        "skipped_rows": sum(1 for row in rows if row["execution_status"] == "skipped"),
        "authorization_ref": execution_wave.get("authorization_ref"),
        "execution_wave_report": str(EXECUTION_WAVE.relative_to(AI_ROOT)) if EXECUTION_WAVE.exists() else None,
        "receipt_gate_validation_success": bool(receipt_validation.get("success")),
        "receipt_safety_regression_success": bool(receipt_regression.get("success")),
        "receipt_safety_regression_failed_cases": receipt_regression.get("failed_regression_cases"),
        "matrix": str(args.output_jsonl.relative_to(AI_ROOT)),
        "safe_for_execution_claim": False,
        "safe_for_training_import": False,
        "safe_for_model_claim": False,
        "release_ready": False,
        "policy": "Matrix reflects the authorized local P175 execution wave. Validator-only/manual gate checks may be receipted, but formal human decisions, training imports, physics ddG success, model claims, and release remain blocked unless their separate gates pass.",
    }
    write_jsonl(args.output_jsonl, rows)
    args.output_report.parent.mkdir(parents=True, exist_ok=True)
    args.output_report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "action_rows": report["action_rows"],
        "current_execution_allowed_rows": report["current_execution_allowed_rows"],
        "executed_in_current_trace_rows": report["executed_in_current_trace_rows"],
        "receipt_present_rows": report["receipt_present_rows"],
        "safe_for_model_claim": False,
        "output": str(args.output_report),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
