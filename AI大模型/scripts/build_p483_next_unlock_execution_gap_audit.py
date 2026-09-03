#!/usr/bin/env python3
"""Build a source-bound audit of next-unlock execution gaps."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
PLAN = AI_ROOT / "reports" / "next_unlock_plan.json"
BOARD = AI_ROOT / "reports" / "next_unlock_execution_board.json"
VALIDATION = AI_ROOT / "reports" / "next_unlock_execution_validation_report.json"
ACTIONS = AI_ROOT / "datasets" / "governance" / "next_unlock_actions.jsonl"
COMPLETION_STATUS = AI_ROOT / "datasets" / "governance" / "next_unlock_completion_status.jsonl"
LOCAL_RELEASE = AI_ROOT / "reports" / "local_release_manifest.json"
CLAIM_MATRIX = AI_ROOT / "reports" / "claim_readiness_matrix.json"
OUT_JSONL = AI_ROOT / "datasets" / "governance" / "p483_next_unlock_execution_gap_audit.jsonl"
OUT_REPORT = AI_ROOT / "reports" / "p483_next_unlock_execution_gap_audit_report.json"


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
        "source_report": "reports/next_unlock_execution_validation_report.json",
        "source_board": "reports/next_unlock_execution_board.json",
        "source_state": source_state,
        "blocker": blocker,
        "training_import_allowed": False,
        "safe_for_training_import": False,
        "safe_for_model_claim": False,
        "customer_delivery_ready": False,
        "release_ready": False,
        "production_execution_allowed": False,
        "policy": "Next-unlock execution gap audit only; started packets and completion-ready observations do not authorize training, model claims, customer delivery, release, ordering, or production execution.",
    }


def main() -> int:
    plan = load_json(PLAN)
    board = load_json(BOARD)
    validation = load_json(VALIDATION)
    local_release = load_json(LOCAL_RELEASE)
    claim_matrix = load_json(CLAIM_MATRIX)
    actions = [row for row in load_jsonl(ACTIONS) if isinstance(row, dict)]
    completion_rows = [row for row in load_jsonl(COMPLETION_STATUS) if isinstance(row, dict)]
    completion_by_action = {row.get("action_id"): row for row in completion_rows}
    stage_rows = [row for row in validation.get("stage_summary") or [] if isinstance(row, dict)]
    rows: list[dict[str, Any]] = []

    for action in actions:
        action_id = action.get("action_id")
        completion = completion_by_action.get(action_id, {})
        failed_checks = list(completion.get("failed_checks") or [])
        source_completion_ready = completion.get("completion_ready") is True
        rows.append(base(
            f"p483-next-unlock-action::{action_id}",
            "next_unlock_action_execution_gap",
            {
                "action_id": action_id,
                "stage_id": action.get("stage_id"),
                "workstream": action.get("workstream"),
                "priority": action.get("priority"),
                "action_type": action.get("action_type"),
                "target_rows": action.get("target_rows"),
                "source_artifact": action.get("source_artifact"),
                "decision_input": action.get("decision_input"),
                "validator_report": action.get("validator_report"),
                "human_review_required": action.get("human_review_required"),
                "started": completion.get("started"),
                "source_status": completion.get("status"),
                "source_completion_ready": source_completion_ready,
                "failed_checks": failed_checks,
                "failed_check_count": len(failed_checks),
            },
            "next-unlock action is not a delivery/model/release authorization",
        ) | {
            "action_id": action_id,
            "stage_id": action.get("stage_id"),
            "workstream": action.get("workstream"),
            "source_status": completion.get("status"),
            "source_completion_ready": source_completion_ready,
            "failed_check_count": len(failed_checks),
            "completion_ready": False,
        })

    for stage in stage_rows:
        stage_id = stage.get("stage_id")
        source_completion_ready = stage.get("completion_ready") is True
        rows.append(base(
            f"p483-next-unlock-stage::{stage_id}",
            "next_unlock_stage_execution_gap",
            {
                "stage_id": stage_id,
                "stage_order": stage.get("stage_order"),
                "action_rows": stage.get("action_rows"),
                "completion_ready_actions": stage.get("completion_ready_actions"),
                "blocked_actions": stage.get("blocked_actions"),
                "source_completion_ready": source_completion_ready,
                "board_stage_status": next((row.get("status") for row in board.get("stages") or [] if row.get("stage_id") == stage_id), None),
                "board_stage_completion_ready": next((row.get("completion_ready") for row in board.get("stages") or [] if row.get("stage_id") == stage_id), None),
            },
            "next-unlock stage remains non-authorizing until all formal gates pass",
        ) | {
            "stage_id": stage_id,
            "stage_order": stage.get("stage_order"),
            "source_completion_ready": source_completion_ready,
            "source_blocked_actions": stage.get("blocked_actions"),
            "completion_ready": False,
        })

    blocked_action_rows = int(validation.get("blocked_actions") or 0)
    stage_completion_ready_count = int(validation.get("completion_ready_stage_count") or 0)
    blocked_stage_rows = max(0, len(stage_rows) - stage_completion_ready_count)
    rows.append(base(
        "p483-next-unlock-execution-summary",
        "next_unlock_execution_summary_gap",
        {
            "planning_artifact_ready": plan.get("planning_artifact_ready"),
            "capability_unlocks_ready": plan.get("capability_unlocks_ready"),
            "blocked_unlocks": plan.get("blocked_unlocks"),
            "action_rows": plan.get("action_rows"),
            "board_started_actions": board.get("started_actions"),
            "board_completion_ready_actions": board.get("completion_ready_actions"),
            "validation_completion_ready_actions": validation.get("completion_ready_actions"),
            "validation_blocked_actions": validation.get("blocked_actions"),
            "stage_count": validation.get("stage_count"),
            "validation_completion_ready_stage_count": validation.get("completion_ready_stage_count"),
            "blocked_stage_rows": blocked_stage_rows,
            "local_release_ready": local_release.get("release_ready"),
            "claims_blocked": claim_matrix.get("claims_blocked"),
        },
        "next-unlock execution remains blocked for model claim, delivery, release, and production use",
    ) | {
        "source_completion_ready_actions": validation.get("completion_ready_actions"),
        "blocked_action_rows": blocked_action_rows,
        "source_completion_ready_stage_count": stage_completion_ready_count,
        "blocked_stage_rows": blocked_stage_rows,
        "completion_ready": False,
    })

    report = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "local_only": True,
        "audit_rows": len(rows),
        "action_audit_rows": len(actions),
        "stage_audit_rows": len(stage_rows),
        "summary_audit_rows": 1,
        "blocked_action_rows": blocked_action_rows,
        "blocked_stage_rows": blocked_stage_rows,
        "blocked_gap_rows": blocked_action_rows + blocked_stage_rows,
        "plan_action_rows": plan.get("action_rows"),
        "board_total_actions": board.get("total_actions"),
        "board_started_actions": board.get("started_actions"),
        "board_completion_ready_actions": board.get("completion_ready_actions"),
        "validation_completion_ready_actions": validation.get("completion_ready_actions"),
        "validation_blocked_actions": validation.get("blocked_actions"),
        "stage_count": validation.get("stage_count"),
        "validation_completion_ready_stage_count": validation.get("completion_ready_stage_count"),
        "plan_blocked_unlocks": plan.get("blocked_unlocks"),
        "plan_capability_unlocks_ready": plan.get("capability_unlocks_ready"),
        "local_release_ready": local_release.get("release_ready"),
        "claims_blocked": claim_matrix.get("claims_blocked"),
        "training_import_allowed": False,
        "safe_for_training_import": False,
        "safe_for_model_claim": False,
        "customer_delivery_ready": False,
        "release_ready": False,
        "production_execution_allowed": False,
        "audit_jsonl": "datasets/governance/p483_next_unlock_execution_gap_audit.jsonl",
        "policy": "P483 audit only. Next-unlock execution observations are not approvals, training data, model claims, delivery authorization, release approval, or production execution.",
    }
    write_jsonl(OUT_JSONL, rows)
    OUT_REPORT.parent.mkdir(parents=True, exist_ok=True)
    OUT_REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "audit_rows": report["audit_rows"],
        "action_audit_rows": report["action_audit_rows"],
        "stage_audit_rows": report["stage_audit_rows"],
        "blocked_gap_rows": report["blocked_gap_rows"],
        "output": str(OUT_REPORT),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
