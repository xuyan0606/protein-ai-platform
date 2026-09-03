#!/usr/bin/env python3
"""Build a source-bound audit of next-unlock operator work receipt gaps."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
RECEIPT_REPORT = AI_ROOT / "reports" / "next_unlock_operator_work_receipt_report.json"
RECEIPTS = AI_ROOT / "datasets" / "governance" / "next_unlock_operator_work_receipts.jsonl"
RECEIPT_VALIDATION = AI_ROOT / "reports" / "next_unlock_operator_work_receipt_validation_report.json"
RECEIPT_STATUS = AI_ROOT / "datasets" / "governance" / "next_unlock_operator_work_receipt_status.jsonl"
P491_REPORT = AI_ROOT / "reports" / "p491_next_unlock_operator_work_ledger_gap_audit_report.json"
P491_VALIDATION = AI_ROOT / "reports" / "p491_next_unlock_operator_work_ledger_gap_audit_validation_report.json"
LOCAL_RELEASE = AI_ROOT / "reports" / "local_release_manifest.json"
CLAIM_MATRIX = AI_ROOT / "reports" / "claim_readiness_matrix.json"
OUT_JSONL = AI_ROOT / "datasets" / "governance" / "p492_next_unlock_operator_work_receipt_gap_audit.jsonl"
OUT_REPORT = AI_ROOT / "reports" / "p492_next_unlock_operator_work_receipt_gap_audit_report.json"


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    value = json.loads(path.read_text(encoding="utf-8"))
    return value if isinstance(value, dict) else {}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def base(audit_id: str, gap_type: str, source_state: dict[str, Any], blocker: str) -> dict[str, Any]:
    return {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "local_only": True,
        "audit_id": audit_id,
        "gap_type": gap_type,
        "source_report": "reports/next_unlock_operator_work_receipt_report.json",
        "source_jsonl": "datasets/governance/next_unlock_operator_work_receipts.jsonl",
        "source_state": source_state,
        "blocker": blocker,
        "training_import_allowed": False,
        "safe_for_training_import": False,
        "safe_for_model_claim": False,
        "customer_delivery_ready": False,
        "release_ready": False,
        "production_execution_allowed": False,
        "policy": "Operator work receipt gap audit only; receipt rows are local target-state observations and do not create reviewed decisions, approvals, training data, model claims, customer delivery authorization, release approval, deployment, sync, restart, or production execution.",
    }


def main() -> int:
    receipt_report = load_json(RECEIPT_REPORT)
    receipt_validation = load_json(RECEIPT_VALIDATION)
    p491_report = load_json(P491_REPORT)
    p491_validation = load_json(P491_VALIDATION)
    local_release = load_json(LOCAL_RELEASE)
    claim_matrix = load_json(CLAIM_MATRIX)
    receipt_rows = [row for row in load_jsonl(RECEIPTS) if isinstance(row, dict)]
    status_rows = [row for row in load_jsonl(RECEIPT_STATUS) if isinstance(row, dict)]
    status_by_receipt = {row.get("receipt_id"): row for row in status_rows}
    rows: list[dict[str, Any]] = []

    for item in receipt_rows:
        receipt_id = item.get("receipt_id")
        status = status_by_receipt.get(receipt_id, {})
        rows.append(base(
            f"p492-next-unlock-operator-work-receipt::{receipt_id}",
            "next_unlock_operator_work_receipt_gap",
            {
                "receipt_id": receipt_id,
                "ledger_id": item.get("ledger_id"),
                "action_id": item.get("action_id"),
                "lane_id": item.get("lane_id"),
                "workstream": item.get("workstream"),
                "source_receipt_status": item.get("receipt_status"),
                "validation_status": status.get("validation_status"),
                "ledger_validation_status": item.get("ledger_validation_status"),
                "decision_input": item.get("decision_input"),
                "decision_input_exists": item.get("decision_input_exists"),
                "decision_input_rows": item.get("decision_input_rows"),
                "target_rows_or_missing_rows": item.get("target_rows_or_missing_rows"),
                "source_target_rows_met": item.get("target_rows_met"),
                "source_completion_ready": item.get("completion_ready"),
                "requires_human_input": item.get("requires_human_input"),
                "validator_report": item.get("validator_report"),
                "validator_summary": item.get("validator_summary") or {},
                "operator_open_first": item.get("operator_open_first"),
                "receipt_note": item.get("receipt_note"),
            },
            "operator work receipt remains open blocked and target-state observations do not authorize completion",
        ) | {
            "receipt_id": receipt_id,
            "ledger_id": item.get("ledger_id"),
            "action_id": item.get("action_id"),
            "lane_id": item.get("lane_id"),
            "workstream": item.get("workstream"),
            "source_receipt_status": item.get("receipt_status"),
            "validation_status": status.get("validation_status"),
            "ledger_validation_status": item.get("ledger_validation_status"),
            "source_target_rows_met": item.get("target_rows_met"),
            "source_completion_ready": item.get("completion_ready"),
            "requires_human_input": item.get("requires_human_input"),
            "completion_ready": False,
        })

    open_blocked_receipt_rows = sum(1 for row in receipt_rows if row.get("receipt_status") == "receipt_open_blocked")
    invalid_or_blocked_receipt_rows = sum(1 for row in receipt_rows if row.get("receipt_status") != "receipt_open_blocked")
    source_completion_ready_items = sum(1 for row in receipt_rows if row.get("completion_ready") is True)
    requires_human_input_items = sum(1 for row in receipt_rows if row.get("requires_human_input") is True)
    decision_input_present_rows = sum(1 for row in receipt_rows if row.get("decision_input"))
    decision_input_existing_rows = sum(1 for row in receipt_rows if row.get("decision_input_exists") is True)
    source_target_rows_met_items = sum(1 for row in receipt_rows if row.get("target_rows_met") is True)
    observed_decision_input_rows = sum(int(row.get("decision_input_rows") or 0) for row in receipt_rows)
    validated_receipt_rows = sum(1 for row in status_rows if row.get("validation_status") == "operator_work_receipt_validated_blocked")
    invalid_receipt_rows = sum(1 for row in status_rows if row.get("validation_status") == "operator_work_receipt_invalid")
    rows.append(base(
        "p492-next-unlock-operator-work-receipt-summary",
        "next_unlock_operator_work_receipt_summary_gap",
        {
            "receipt_rows": receipt_report.get("receipt_rows"),
            "open_blocked_receipt_rows": receipt_report.get("open_blocked_receipt_rows"),
            "invalid_or_blocked_receipt_rows": receipt_report.get("invalid_or_blocked_receipt_rows"),
            "completion_ready_items": receipt_report.get("completion_ready_items"),
            "requires_human_input_items": receipt_report.get("requires_human_input_items"),
            "decision_input_present_rows": receipt_report.get("decision_input_present_rows"),
            "decision_input_existing_rows": receipt_report.get("decision_input_existing_rows"),
            "target_rows_met_items": receipt_report.get("target_rows_met_items"),
            "observed_decision_input_rows": receipt_report.get("observed_decision_input_rows"),
            "validated_receipt_rows": receipt_validation.get("validated_receipt_rows"),
            "invalid_receipt_rows": receipt_validation.get("invalid_receipt_rows"),
            "target_rows_met_completion_ready_items": receipt_validation.get("target_rows_met_completion_ready_items"),
            "p491_open_blocked_ledger_rows": p491_report.get("open_blocked_ledger_rows"),
            "p491_validation_success": p491_validation.get("success"),
            "local_release_ready": local_release.get("release_ready"),
            "claims_blocked": claim_matrix.get("claims_blocked"),
        },
        "operator work receipts remain local target-state tracking and do not close any next-unlock gap",
    ) | {
        "receipt_rows": receipt_report.get("receipt_rows"),
        "open_blocked_receipt_rows": open_blocked_receipt_rows,
        "invalid_or_blocked_receipt_rows": invalid_or_blocked_receipt_rows,
        "source_completion_ready_items": source_completion_ready_items,
        "requires_human_input_items": requires_human_input_items,
        "decision_input_present_rows": decision_input_present_rows,
        "decision_input_existing_rows": decision_input_existing_rows,
        "source_target_rows_met_items": source_target_rows_met_items,
        "observed_decision_input_rows": observed_decision_input_rows,
        "validated_receipt_rows": validated_receipt_rows,
        "invalid_receipt_rows": invalid_receipt_rows,
        "completion_ready": False,
    })

    report = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "local_only": True,
        "audit_rows": len(rows),
        "receipt_audit_rows": len(receipt_rows),
        "summary_audit_rows": 1,
        "receipt_rows": receipt_report.get("receipt_rows"),
        "open_blocked_receipt_rows": open_blocked_receipt_rows,
        "invalid_or_blocked_receipt_rows": invalid_or_blocked_receipt_rows,
        "source_completion_ready_items": source_completion_ready_items,
        "requires_human_input_items": requires_human_input_items,
        "decision_input_present_rows": decision_input_present_rows,
        "decision_input_existing_rows": decision_input_existing_rows,
        "source_target_rows_met_items": source_target_rows_met_items,
        "observed_decision_input_rows": observed_decision_input_rows,
        "validated_receipt_rows": validated_receipt_rows,
        "invalid_receipt_rows": invalid_receipt_rows,
        "target_rows_met_completion_ready_items": receipt_validation.get("target_rows_met_completion_ready_items"),
        "p491_open_blocked_ledger_rows": p491_report.get("open_blocked_ledger_rows"),
        "p491_validation_success": p491_validation.get("success"),
        "local_release_ready": local_release.get("release_ready"),
        "claims_blocked": claim_matrix.get("claims_blocked"),
        "training_import_allowed": False,
        "safe_for_training_import": False,
        "safe_for_model_claim": False,
        "customer_delivery_ready": False,
        "release_ready": False,
        "production_execution_allowed": False,
        "audit_jsonl": "datasets/governance/p492_next_unlock_operator_work_receipt_gap_audit.jsonl",
        "policy": "P492 audit only. Operator work receipts are not reviewed decisions, approvals, training imports, model claims, customer delivery authorization, release approval, deployment, sync, restart, or production execution.",
    }
    write_jsonl(OUT_JSONL, rows)
    OUT_REPORT.parent.mkdir(parents=True, exist_ok=True)
    OUT_REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "audit_rows": report["audit_rows"],
        "receipt_audit_rows": report["receipt_audit_rows"],
        "open_blocked_receipt_rows": report["open_blocked_receipt_rows"],
        "source_completion_ready_items": report["source_completion_ready_items"],
        "output": str(OUT_REPORT),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
