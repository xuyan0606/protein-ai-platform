#!/usr/bin/env python3
"""Build a source-bound audit of next-unlock multi-agent launch gaps."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
LAUNCH_REPORT = AI_ROOT / "reports" / "next_unlock_multi_agent_launch_board.json"
LAUNCH_BOARD = AI_ROOT / "datasets" / "governance" / "next_unlock_multi_agent_launch_board.jsonl"
LAUNCH_VALIDATION = AI_ROOT / "reports" / "next_unlock_multi_agent_launch_validation_report.json"
LAUNCH_STATUS = AI_ROOT / "datasets" / "governance" / "next_unlock_multi_agent_launch_status.jsonl"
P486_REPORT = AI_ROOT / "reports" / "p486_next_unlock_remediation_queue_gap_audit_report.json"
P486_VALIDATION = AI_ROOT / "reports" / "p486_next_unlock_remediation_queue_gap_audit_validation_report.json"
LOCAL_RELEASE = AI_ROOT / "reports" / "local_release_manifest.json"
CLAIM_MATRIX = AI_ROOT / "reports" / "claim_readiness_matrix.json"
OUT_JSONL = AI_ROOT / "datasets" / "governance" / "p487_next_unlock_multi_agent_launch_gap_audit.jsonl"
OUT_REPORT = AI_ROOT / "reports" / "p487_next_unlock_multi_agent_launch_gap_audit_report.json"


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
        "source_report": "reports/next_unlock_multi_agent_launch_board.json",
        "source_jsonl": "datasets/governance/next_unlock_multi_agent_launch_board.jsonl",
        "source_state": source_state,
        "blocker": blocker,
        "training_import_allowed": False,
        "safe_for_training_import": False,
        "safe_for_model_claim": False,
        "customer_delivery_ready": False,
        "release_ready": False,
        "production_execution_allowed": False,
        "policy": "Multi-agent launch gap audit only; local started/validated launch rows do not create reviewed decisions, approvals, capability unlocks, training data, model claims, delivery authorization, release approval, deployment, sync, restart, or production execution.",
    }


def main() -> int:
    launch_report = load_json(LAUNCH_REPORT)
    launch_validation = load_json(LAUNCH_VALIDATION)
    p486_report = load_json(P486_REPORT)
    p486_validation = load_json(P486_VALIDATION)
    local_release = load_json(LOCAL_RELEASE)
    claim_matrix = load_json(CLAIM_MATRIX)
    launch_rows = [row for row in load_jsonl(LAUNCH_BOARD) if isinstance(row, dict)]
    status_rows = [row for row in load_jsonl(LAUNCH_STATUS) if isinstance(row, dict)]
    status_by_launch = {row.get("launch_id"): row for row in status_rows}
    rows: list[dict[str, Any]] = []

    for item in launch_rows:
        launch_id = item.get("launch_id")
        status = status_by_launch.get(launch_id, {})
        failed_checks = list(status.get("failed_checks") or [])
        rows.append(base(
            f"p487-next-unlock-multi-agent-launch::{launch_id}",
            "next_unlock_multi_agent_launch_gap",
            {
                "launch_id": launch_id,
                "remediation_id": item.get("remediation_id"),
                "action_id": item.get("action_id"),
                "stage_id": item.get("stage_id"),
                "workstream": item.get("workstream"),
                "lane_id": item.get("lane_id"),
                "lane_role": item.get("lane_role"),
                "severity": item.get("severity"),
                "launch_status": item.get("launch_status"),
                "validation_status": status.get("validation_status"),
                "source_started": item.get("started") is True,
                "source_ready_to_start": item.get("ready_to_start") is True,
                "source_completion_ready": item.get("completion_ready") is True,
                "requires_human_input": item.get("requires_human_input") is True,
                "queue_status": item.get("queue_status"),
                "blocker_count": item.get("blocker_count"),
                "failed_checks": item.get("failed_checks") or [],
                "validation_failed_checks": failed_checks,
                "operator_open_first": item.get("operator_open_first"),
                "decision_input": item.get("decision_input"),
                "validator_report": item.get("validator_report"),
                "next_evidence_artifacts": item.get("next_evidence_artifacts") or [],
            },
            "local multi-agent launch remains started-blocked and non-authorizing",
        ) | {
            "launch_id": launch_id,
            "remediation_id": item.get("remediation_id"),
            "action_id": item.get("action_id"),
            "workstream": item.get("workstream"),
            "lane_id": item.get("lane_id"),
            "launch_status": item.get("launch_status"),
            "validation_status": status.get("validation_status"),
            "source_started": item.get("started") is True,
            "requires_human_input": item.get("requires_human_input") is True,
            "completion_ready": False,
        })

    started_rows = sum(1 for row in launch_rows if row.get("started") is True)
    open_blocked_rows = sum(1 for row in launch_rows if row.get("launch_status") == "local_agent_started_blocked")
    requires_human_input_rows = sum(1 for row in launch_rows if row.get("requires_human_input") is True)
    completion_ready_rows = sum(1 for row in launch_rows if row.get("completion_ready") is True)
    rows.append(base(
        "p487-next-unlock-multi-agent-launch-summary",
        "next_unlock_multi_agent_launch_summary_gap",
        {
            "total_launch_items": launch_report.get("total_launch_items"),
            "launch_rows": launch_report.get("launch_rows"),
            "started_items": launch_report.get("started_items"),
            "ready_to_launch_items": launch_report.get("ready_to_launch_items"),
            "completion_ready_items": launch_report.get("completion_ready_items"),
            "requires_human_input_items": launch_report.get("requires_human_input_items"),
            "local_agent_lanes": launch_report.get("local_agent_lanes"),
            "agent_count": launch_report.get("agent_count"),
            "parallel_groups": launch_report.get("parallel_groups"),
            "lane_counts": launch_report.get("lane_counts") or {},
            "status_counts": launch_report.get("status_counts") or {},
            "validated_launch_rows": launch_validation.get("validated_launch_rows"),
            "invalid_launch_rows": launch_validation.get("invalid_launch_rows"),
            "p486_open_rows": p486_report.get("open_rows"),
            "p486_validation_success": p486_validation.get("success"),
            "local_release_ready": local_release.get("release_ready"),
            "claims_blocked": claim_matrix.get("claims_blocked"),
        },
        "multi-agent launch board remains a local started-blocked work assignment board",
    ) | {
        "launch_rows": launch_report.get("launch_rows"),
        "started_rows": started_rows,
        "open_blocked_rows": open_blocked_rows,
        "requires_human_input_rows": requires_human_input_rows,
        "source_completion_ready_rows": completion_ready_rows,
        "completion_ready": False,
    })

    report = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "local_only": True,
        "audit_rows": len(rows),
        "launch_audit_rows": len(launch_rows),
        "summary_audit_rows": 1,
        "launch_rows": launch_report.get("launch_rows"),
        "started_rows": started_rows,
        "open_blocked_rows": open_blocked_rows,
        "ready_to_launch_rows": launch_report.get("ready_to_launch_items"),
        "requires_human_input_rows": requires_human_input_rows,
        "source_completion_ready_rows": completion_ready_rows,
        "local_agent_lanes": launch_report.get("local_agent_lanes"),
        "agent_count": launch_report.get("agent_count"),
        "parallel_groups": launch_report.get("parallel_groups"),
        "validated_launch_rows": launch_validation.get("validated_launch_rows"),
        "invalid_launch_rows": launch_validation.get("invalid_launch_rows"),
        "p486_open_rows": p486_report.get("open_rows"),
        "p486_validation_success": p486_validation.get("success"),
        "local_release_ready": local_release.get("release_ready"),
        "claims_blocked": claim_matrix.get("claims_blocked"),
        "training_import_allowed": False,
        "safe_for_training_import": False,
        "safe_for_model_claim": False,
        "customer_delivery_ready": False,
        "release_ready": False,
        "production_execution_allowed": False,
        "audit_jsonl": "datasets/governance/p487_next_unlock_multi_agent_launch_gap_audit.jsonl",
        "policy": "P487 audit only. Multi-agent launch rows are not approvals, reviewed decisions, training imports, model claims, customer delivery authorization, release approval, deployment, sync, restart, or production execution.",
    }
    write_jsonl(OUT_JSONL, rows)
    OUT_REPORT.parent.mkdir(parents=True, exist_ok=True)
    OUT_REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "audit_rows": report["audit_rows"],
        "launch_audit_rows": report["launch_audit_rows"],
        "started_rows": report["started_rows"],
        "open_blocked_rows": report["open_blocked_rows"],
        "output": str(OUT_REPORT),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
