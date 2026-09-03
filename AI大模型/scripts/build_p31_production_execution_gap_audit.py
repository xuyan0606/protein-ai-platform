#!/usr/bin/env python3
"""Build a source-bound audit of P31 production execution gaps."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
PENDING_ACTIONS = AI_ROOT / "datasets" / "governance" / "p26_p31_pending_backlog_all_started_actions.jsonl"
ACTIVE_MATRIX = AI_ROOT / "datasets" / "governance" / "active_stage_execution_matrix.jsonl"
LOCAL_RELEASE = AI_ROOT / "reports" / "local_release_manifest.json"
CUSTOMER = AI_ROOT / "reports" / "customer_delivery_readiness_report.json"
GOVERNANCE = AI_ROOT / "reports" / "governance_readiness_report.json"
OPERATOR_STATUS = AI_ROOT / "reports" / "operator_review_status_report.json"
CLAIM_MATRIX = AI_ROOT / "reports" / "claim_readiness_matrix.json"
OUT_JSONL = AI_ROOT / "datasets" / "governance" / "p31_production_execution_gap_audit.jsonl"
OUT_REPORT = AI_ROOT / "reports" / "p31_production_execution_gap_audit_report.json"


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    value = json.loads(path.read_text(encoding="utf-8"))
    return value if isinstance(value, dict) else {}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def claim_row(matrix: dict[str, Any], claim_id: str) -> dict[str, Any]:
    for row in matrix.get("claims") or []:
        if isinstance(row, dict) and row.get("claim_id") == claim_id:
            return row
    return {}


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def base(audit_id: str, gap_type: str, source_report: str, source_state: dict[str, Any], blocker: str) -> dict[str, Any]:
    return {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "local_only": True,
        "audit_id": audit_id,
        "gap_type": gap_type,
        "source_report": source_report,
        "source_state": source_state,
        "blocker": blocker,
        "training_import_allowed": False,
        "safe_for_training_import": False,
        "safe_for_model_claim": False,
        "customer_delivery_ready": False,
        "release_ready": False,
        "production_execution_allowed": False,
        "sync_allowed": False,
        "deploy_allowed": False,
        "restart_allowed": False,
        "grey_release_allowed": False,
        "policy": "P31 production execution audit only; it does not authorize sync, deploy, restart, grey release, customer delivery, production execution, or release.",
    }


def main() -> int:
    pending_rows = [row for row in load_jsonl(PENDING_ACTIONS) if row.get("stage_id") == "P31"]
    active_rows = [row for row in load_jsonl(ACTIVE_MATRIX) if row.get("stage_id") == "P31"]
    release = load_json(LOCAL_RELEASE)
    customer = load_json(CUSTOMER)
    governance = load_json(GOVERNANCE)
    operator = load_json(OPERATOR_STATUS)
    claims = load_json(CLAIM_MATRIX)
    release_claim = claim_row(claims, "local_release_review_package")
    summary = release.get("readiness_summary") if isinstance(release.get("readiness_summary"), dict) else {}
    operator_completion = (operator.get("status") or {}).get("operator_action_completion") or {}
    rows: list[dict[str, Any]] = []

    for row in pending_rows:
        action_id = row.get("action_id")
        rows.append(base(
            f"p31-pending-action::{action_id}",
            "p31_pending_production_action",
            "datasets/governance/p26_p31_pending_backlog_all_started_actions.jsonl",
            {
                "action_id": action_id,
                "title": row.get("title"),
                "status": row.get("status"),
                "blocker": row.get("blocker"),
                "source_state": row.get("source_state"),
                "next_action": row.get("next_action"),
                "requires_human_or_external_input": row.get("requires_human_or_external_input"),
                "release_ready": row.get("release_ready"),
                "production_execution_allowed": row.get("production_execution_allowed"),
            },
            "P31 action remains started only and blocked from production execution",
        ) | {
            "action_id": action_id,
            "status": row.get("status"),
            "completion_ready": False,
        })

    for row in active_rows:
        rows.append(base(
            f"p31-active-stage::{row.get('stage_id')}",
            "p31_active_stage_execution_gate",
            "datasets/governance/active_stage_execution_matrix.jsonl",
            {
                "stage_id": row.get("stage_id"),
                "status": row.get("status"),
                "evidence": row.get("evidence"),
                "blockers": row.get("blockers"),
                "human_or_external_next_actions": row.get("human_or_external_next_actions"),
                "release_ready": row.get("release_ready"),
                "production_execution_allowed": row.get("production_execution_allowed"),
            },
            "active P31 execution matrix allows review preparation only, not production actions",
        ) | {
            "stage_id": row.get("stage_id"),
            "stage_status": row.get("status"),
            "completion_ready": False,
        })

    rows.append(base(
        "p31-production-execution-summary",
        "p31_release_and_production_summary",
        "reports/local_release_manifest.json",
        {
            "local_release_ready": release.get("release_ready"),
            "customer_delivery_ready": customer.get("ready"),
            "governance_ready": governance.get("ready"),
            "operator_review_ready": operator.get("ready"),
            "operator_completed_action_rows": operator_completion.get("completed_rows"),
            "operator_all_actions_completed": operator_completion.get("all_actions_completed"),
            "claim_matrix_blocked_claims": claims.get("claims_blocked"),
            "local_release_review_package_ready": release_claim.get("ready"),
            "local_release_review_package_allowed": release_claim.get("allowed"),
            "active_stage_execution_matrix_production_execution_allowed": summary.get("active_stage_execution_matrix_production_execution_allowed"),
            "master_overall_status": summary.get("master_overall_status"),
        },
        "release, customer delivery, governance, operator completion, and production authorization gates remain closed",
    ) | {
        "completion_ready": False,
        "local_release_review_package_ready": release_claim.get("ready"),
        "local_release_review_package_allowed": release_claim.get("allowed"),
    })

    report = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "local_only": True,
        "audit_rows": len(rows),
        "pending_action_rows": len(pending_rows),
        "active_stage_rows": len(active_rows),
        "local_release_ready": release.get("release_ready"),
        "customer_delivery_ready": customer.get("ready"),
        "governance_ready": governance.get("ready"),
        "operator_review_ready": operator.get("ready"),
        "operator_completed_action_rows": operator_completion.get("completed_rows"),
        "operator_all_actions_completed": operator_completion.get("all_actions_completed"),
        "claim_matrix_blocked_claims": claims.get("claims_blocked"),
        "local_release_review_package_ready": release_claim.get("ready"),
        "local_release_review_package_allowed": release_claim.get("allowed"),
        "active_stage_execution_matrix_production_execution_allowed": summary.get("active_stage_execution_matrix_production_execution_allowed"),
        "master_overall_status": summary.get("master_overall_status"),
        "training_import_allowed": False,
        "safe_for_training_import": False,
        "safe_for_model_claim": False,
        "customer_delivery_ready_for_release": False,
        "release_ready": False,
        "production_execution_allowed": False,
        "sync_allowed": False,
        "deploy_allowed": False,
        "restart_allowed": False,
        "grey_release_allowed": False,
        "audit_jsonl": "datasets/governance/p31_production_execution_gap_audit.jsonl",
        "policy": "P31 audit only. Production sync/deploy/restart/grey release remains forbidden until explicit production authorization and all release/customer/governance/operator gates pass.",
    }
    write_jsonl(OUT_JSONL, rows)
    OUT_REPORT.parent.mkdir(parents=True, exist_ok=True)
    OUT_REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "audit_rows": report["audit_rows"],
        "pending_action_rows": report["pending_action_rows"],
        "active_stage_rows": report["active_stage_rows"],
        "release_ready": False,
        "production_execution_allowed": False,
        "output": str(OUT_REPORT),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
