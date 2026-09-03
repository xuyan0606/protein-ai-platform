#!/usr/bin/env python3
"""Build a source-bound audit of next-unlock operator work ledger gaps."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
LEDGER_REPORT = AI_ROOT / "reports" / "next_unlock_operator_work_ledger_report.json"
LEDGER = AI_ROOT / "datasets" / "governance" / "next_unlock_operator_work_ledger.jsonl"
LEDGER_VALIDATION = AI_ROOT / "reports" / "next_unlock_operator_work_ledger_validation_report.json"
LEDGER_STATUS = AI_ROOT / "datasets" / "governance" / "next_unlock_operator_work_ledger_status.jsonl"
P490_REPORT = AI_ROOT / "reports" / "p490_next_unlock_action_checklist_gap_audit_report.json"
P490_VALIDATION = AI_ROOT / "reports" / "p490_next_unlock_action_checklist_gap_audit_validation_report.json"
LOCAL_RELEASE = AI_ROOT / "reports" / "local_release_manifest.json"
CLAIM_MATRIX = AI_ROOT / "reports" / "claim_readiness_matrix.json"
OUT_JSONL = AI_ROOT / "datasets" / "governance" / "p491_next_unlock_operator_work_ledger_gap_audit.jsonl"
OUT_REPORT = AI_ROOT / "reports" / "p491_next_unlock_operator_work_ledger_gap_audit_report.json"


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
        "source_report": "reports/next_unlock_operator_work_ledger_report.json",
        "source_jsonl": "datasets/governance/next_unlock_operator_work_ledger.jsonl",
        "source_state": source_state,
        "blocker": blocker,
        "training_import_allowed": False,
        "safe_for_training_import": False,
        "safe_for_model_claim": False,
        "customer_delivery_ready": False,
        "release_ready": False,
        "production_execution_allowed": False,
        "policy": "Operator work ledger gap audit only; open ledger rows are local work tracking artifacts and do not create reviewed decisions, approvals, training data, model claims, customer delivery authorization, release approval, deployment, sync, restart, or production execution.",
    }


def main() -> int:
    ledger_report = load_json(LEDGER_REPORT)
    ledger_validation = load_json(LEDGER_VALIDATION)
    p490_report = load_json(P490_REPORT)
    p490_validation = load_json(P490_VALIDATION)
    local_release = load_json(LOCAL_RELEASE)
    claim_matrix = load_json(CLAIM_MATRIX)
    ledger_rows = [row for row in load_jsonl(LEDGER) if isinstance(row, dict)]
    status_rows = [row for row in load_jsonl(LEDGER_STATUS) if isinstance(row, dict)]
    status_by_ledger = {row.get("ledger_id"): row for row in status_rows}
    rows: list[dict[str, Any]] = []

    for item in ledger_rows:
        ledger_id = item.get("ledger_id")
        status = status_by_ledger.get(ledger_id, {})
        rows.append(base(
            f"p491-next-unlock-operator-work-ledger::{ledger_id}",
            "next_unlock_operator_work_ledger_gap",
            {
                "ledger_id": ledger_id,
                "action_id": item.get("action_id"),
                "checklist_id": item.get("checklist_id"),
                "lane_id": item.get("lane_id"),
                "workstream": item.get("workstream"),
                "source_ledger_status": item.get("ledger_status"),
                "validation_status": status.get("validation_status"),
                "ready_for_local_operator_work": item.get("ready_for_local_operator_work"),
                "local_materials_ready": item.get("local_materials_ready"),
                "source_completion_ready": item.get("completion_ready"),
                "requires_human_input": item.get("requires_human_input"),
                "human_backlog_id": item.get("human_backlog_id"),
                "backlog_missing_rows": item.get("backlog_missing_rows"),
                "backlog_milestone_missing_rows": item.get("backlog_milestone_missing_rows"),
                "remediation_id": item.get("remediation_id"),
                "severity": item.get("severity"),
                "priority": item.get("priority"),
                "blocker_count": item.get("blocker_count"),
                "blocker_ids": item.get("blocker_ids") or [],
                "failed_checks": item.get("failed_checks") or [],
                "operator_open_first": item.get("operator_open_first"),
                "decision_input": item.get("decision_input"),
                "template": item.get("template"),
                "validator_report": item.get("validator_report"),
                "operator_work_steps": item.get("operator_work_steps") or [],
            },
            "operator work ledger row remains open blocked and requires human input before any completion or authorization",
        ) | {
            "ledger_id": ledger_id,
            "action_id": item.get("action_id"),
            "checklist_id": item.get("checklist_id"),
            "lane_id": item.get("lane_id"),
            "workstream": item.get("workstream"),
            "source_ledger_status": item.get("ledger_status"),
            "validation_status": status.get("validation_status"),
            "ready_for_local_operator_work": item.get("ready_for_local_operator_work"),
            "local_materials_ready": item.get("local_materials_ready"),
            "requires_human_input": item.get("requires_human_input"),
            "source_completion_ready": item.get("completion_ready"),
            "completion_ready": False,
        })

    open_blocked_ledger_rows = sum(1 for row in ledger_rows if row.get("ledger_status") == "operator_work_open_blocked")
    ready_for_local_operator_work_rows = sum(1 for row in ledger_rows if row.get("ready_for_local_operator_work") is True)
    invalid_or_blocked_ledger_rows = sum(1 for row in ledger_rows if row.get("ledger_status") != "operator_work_open_blocked")
    source_completion_ready_items = sum(1 for row in ledger_rows if row.get("completion_ready") is True)
    requires_human_input_items = sum(1 for row in ledger_rows if row.get("requires_human_input") is True)
    local_materials_ready_rows = sum(1 for row in ledger_rows if row.get("local_materials_ready") is True)
    linked_human_backlog_rows = sum(1 for row in ledger_rows if row.get("human_backlog_id"))
    unlinked_human_backlog_rows = sum(1 for row in ledger_rows if not row.get("human_backlog_id"))
    total_backlog_missing_rows = sum(int(row.get("backlog_missing_rows") or 0) for row in ledger_rows)
    validated_ledger_rows = sum(1 for row in status_rows if row.get("validation_status") == "operator_work_ledger_validated_blocked")
    invalid_ledger_rows = sum(1 for row in status_rows if row.get("validation_status") == "operator_work_ledger_invalid")
    rows.append(base(
        "p491-next-unlock-operator-work-ledger-summary",
        "next_unlock_operator_work_ledger_summary_gap",
        {
            "ledger_rows": ledger_report.get("ledger_rows"),
            "open_blocked_ledger_rows": ledger_report.get("open_blocked_ledger_rows"),
            "ready_for_local_operator_work_rows": ledger_report.get("ready_for_local_operator_work_rows"),
            "invalid_or_blocked_ledger_rows": ledger_report.get("invalid_or_blocked_ledger_rows"),
            "completion_ready_items": ledger_report.get("completion_ready_items"),
            "requires_human_input_items": ledger_report.get("requires_human_input_items"),
            "local_materials_ready_rows": ledger_report.get("local_materials_ready_rows"),
            "linked_human_backlog_rows": ledger_report.get("linked_human_backlog_rows"),
            "unlinked_human_backlog_rows": ledger_report.get("unlinked_human_backlog_rows"),
            "total_backlog_missing_rows": ledger_report.get("total_backlog_missing_rows"),
            "validated_ledger_rows": ledger_validation.get("validated_ledger_rows"),
            "invalid_ledger_rows": ledger_validation.get("invalid_ledger_rows"),
            "p490_open_blocked_checklist_rows": p490_report.get("open_blocked_checklist_rows"),
            "p490_validation_success": p490_validation.get("success"),
            "local_release_ready": local_release.get("release_ready"),
            "claims_blocked": claim_matrix.get("claims_blocked"),
        },
        "operator work ledger remains a local work tracking view and does not close any next-unlock gap",
    ) | {
        "ledger_rows": ledger_report.get("ledger_rows"),
        "open_blocked_ledger_rows": open_blocked_ledger_rows,
        "ready_for_local_operator_work_rows": ready_for_local_operator_work_rows,
        "invalid_or_blocked_ledger_rows": invalid_or_blocked_ledger_rows,
        "source_completion_ready_items": source_completion_ready_items,
        "requires_human_input_items": requires_human_input_items,
        "local_materials_ready_rows": local_materials_ready_rows,
        "linked_human_backlog_rows": linked_human_backlog_rows,
        "unlinked_human_backlog_rows": unlinked_human_backlog_rows,
        "total_backlog_missing_rows": total_backlog_missing_rows,
        "validated_ledger_rows": validated_ledger_rows,
        "invalid_ledger_rows": invalid_ledger_rows,
        "completion_ready": False,
    })

    report = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "local_only": True,
        "audit_rows": len(rows),
        "ledger_audit_rows": len(ledger_rows),
        "summary_audit_rows": 1,
        "ledger_rows": ledger_report.get("ledger_rows"),
        "open_blocked_ledger_rows": open_blocked_ledger_rows,
        "ready_for_local_operator_work_rows": ready_for_local_operator_work_rows,
        "invalid_or_blocked_ledger_rows": invalid_or_blocked_ledger_rows,
        "source_completion_ready_items": source_completion_ready_items,
        "requires_human_input_items": requires_human_input_items,
        "local_materials_ready_rows": local_materials_ready_rows,
        "linked_human_backlog_rows": linked_human_backlog_rows,
        "unlinked_human_backlog_rows": unlinked_human_backlog_rows,
        "total_backlog_missing_rows": total_backlog_missing_rows,
        "validated_ledger_rows": validated_ledger_rows,
        "invalid_ledger_rows": invalid_ledger_rows,
        "p490_open_blocked_checklist_rows": p490_report.get("open_blocked_checklist_rows"),
        "p490_validation_success": p490_validation.get("success"),
        "local_release_ready": local_release.get("release_ready"),
        "claims_blocked": claim_matrix.get("claims_blocked"),
        "training_import_allowed": False,
        "safe_for_training_import": False,
        "safe_for_model_claim": False,
        "customer_delivery_ready": False,
        "release_ready": False,
        "production_execution_allowed": False,
        "audit_jsonl": "datasets/governance/p491_next_unlock_operator_work_ledger_gap_audit.jsonl",
        "policy": "P491 audit only. Operator work ledger rows are not reviewed decisions, approvals, training imports, model claims, customer delivery authorization, release approval, deployment, sync, restart, or production execution.",
    }
    write_jsonl(OUT_JSONL, rows)
    OUT_REPORT.parent.mkdir(parents=True, exist_ok=True)
    OUT_REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "audit_rows": report["audit_rows"],
        "ledger_audit_rows": report["ledger_audit_rows"],
        "open_blocked_ledger_rows": report["open_blocked_ledger_rows"],
        "source_completion_ready_items": report["source_completion_ready_items"],
        "output": str(OUT_REPORT),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
