#!/usr/bin/env python3
"""Build a source-bound audit of next-unlock agent lane status gaps."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
LANE_REPORT = AI_ROOT / "reports" / "next_unlock_agent_lane_status_report.json"
LANE_STATUS = AI_ROOT / "datasets" / "governance" / "next_unlock_agent_lane_status.jsonl"
P487_REPORT = AI_ROOT / "reports" / "p487_next_unlock_multi_agent_launch_gap_audit_report.json"
P487_VALIDATION = AI_ROOT / "reports" / "p487_next_unlock_multi_agent_launch_gap_audit_validation_report.json"
LOCAL_RELEASE = AI_ROOT / "reports" / "local_release_manifest.json"
CLAIM_MATRIX = AI_ROOT / "reports" / "claim_readiness_matrix.json"
OUT_JSONL = AI_ROOT / "datasets" / "governance" / "p488_next_unlock_agent_lane_status_gap_audit.jsonl"
OUT_REPORT = AI_ROOT / "reports" / "p488_next_unlock_agent_lane_status_gap_audit_report.json"


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
        "source_report": "reports/next_unlock_agent_lane_status_report.json",
        "source_jsonl": "datasets/governance/next_unlock_agent_lane_status.jsonl",
        "source_state": source_state,
        "blocker": blocker,
        "training_import_allowed": False,
        "safe_for_training_import": False,
        "safe_for_model_claim": False,
        "customer_delivery_ready": False,
        "release_ready": False,
        "production_execution_allowed": False,
        "policy": "Agent lane status gap audit only; lane started-blocked status is a local coordination observation and does not create reviewed decisions, approvals, training data, model claims, customer delivery authorization, release approval, deployment, sync, restart, or production execution.",
    }


def main() -> int:
    lane_report = load_json(LANE_REPORT)
    p487_report = load_json(P487_REPORT)
    p487_validation = load_json(P487_VALIDATION)
    local_release = load_json(LOCAL_RELEASE)
    claim_matrix = load_json(CLAIM_MATRIX)
    lane_rows = [row for row in load_jsonl(LANE_STATUS) if isinstance(row, dict)]
    rows: list[dict[str, Any]] = []

    for lane in lane_rows:
        lane_id = lane.get("lane_id")
        source_completion_ready_items = int(lane.get("completion_ready_items") or 0)
        rows.append(base(
            f"p488-next-unlock-agent-lane-status::{lane_id}",
            "next_unlock_agent_lane_status_gap",
            {
                "lane_id": lane_id,
                "source_lane_status": lane.get("lane_status"),
                "launch_items": lane.get("launch_items"),
                "validated_launch_items": lane.get("validated_launch_items"),
                "invalid_launch_items": lane.get("invalid_launch_items"),
                "started_items": lane.get("started_items"),
                "ready_to_start_items": lane.get("ready_to_start_items"),
                "source_completion_ready_items": source_completion_ready_items,
                "requires_human_input_items": lane.get("requires_human_input_items"),
                "action_ids": lane.get("action_ids") or [],
                "workstreams": lane.get("workstreams") or [],
                "operator_open_first": lane.get("operator_open_first") or [],
                "next_evidence_artifacts": lane.get("next_evidence_artifacts") or [],
            },
            "agent lane remains started-blocked and requires human input before any completion or authorization",
        ) | {
            "lane_id": lane_id,
            "source_lane_status": lane.get("lane_status"),
            "launch_items": lane.get("launch_items"),
            "started_items": lane.get("started_items"),
            "requires_human_input_items": lane.get("requires_human_input_items"),
            "source_completion_ready_items": source_completion_ready_items,
            "completion_ready": False,
        })

    started_blocked_lanes = sum(1 for row in lane_rows if row.get("lane_status") == "lane_started_blocked")
    invalid_lanes = sum(1 for row in lane_rows if row.get("lane_status") == "lane_invalid")
    lanes_with_completion_ready_items = sum(1 for row in lane_rows if int(row.get("completion_ready_items") or 0) > 0)
    total_launch_items = sum(int(row.get("launch_items") or 0) for row in lane_rows)
    validated_launch_items = sum(int(row.get("validated_launch_items") or 0) for row in lane_rows)
    invalid_launch_items = sum(int(row.get("invalid_launch_items") or 0) for row in lane_rows)
    started_items = sum(int(row.get("started_items") or 0) for row in lane_rows)
    source_completion_ready_items = sum(int(row.get("completion_ready_items") or 0) for row in lane_rows)
    requires_human_input_items = sum(int(row.get("requires_human_input_items") or 0) for row in lane_rows)
    rows.append(base(
        "p488-next-unlock-agent-lane-status-summary",
        "next_unlock_agent_lane_status_summary_gap",
        {
            "lane_rows": lane_report.get("lane_rows"),
            "started_blocked_lanes": lane_report.get("started_blocked_lanes"),
            "invalid_lanes": lane_report.get("invalid_lanes"),
            "lanes_with_completion_ready_items": lane_report.get("lanes_with_completion_ready_items"),
            "total_launch_items": lane_report.get("total_launch_items"),
            "validated_launch_items": lane_report.get("validated_launch_items"),
            "invalid_launch_items": lane_report.get("invalid_launch_items"),
            "started_items": lane_report.get("started_items"),
            "source_completion_ready_items": lane_report.get("completion_ready_items"),
            "requires_human_input_items": lane_report.get("requires_human_input_items"),
            "lane_status_counts": lane_report.get("lane_status_counts") or {},
            "p487_open_blocked_rows": p487_report.get("open_blocked_rows"),
            "p487_validation_success": p487_validation.get("success"),
            "local_release_ready": local_release.get("release_ready"),
            "claims_blocked": claim_matrix.get("claims_blocked"),
        },
        "agent lane status remains a local coordination view and does not close any next-unlock gap",
    ) | {
        "lane_rows": lane_report.get("lane_rows"),
        "started_blocked_lanes": started_blocked_lanes,
        "invalid_lanes": invalid_lanes,
        "lanes_with_completion_ready_items": lanes_with_completion_ready_items,
        "total_launch_items": total_launch_items,
        "validated_launch_items": validated_launch_items,
        "invalid_launch_items": invalid_launch_items,
        "started_items": started_items,
        "source_completion_ready_items": source_completion_ready_items,
        "requires_human_input_items": requires_human_input_items,
        "completion_ready": False,
    })

    report = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "local_only": True,
        "audit_rows": len(rows),
        "lane_audit_rows": len(lane_rows),
        "summary_audit_rows": 1,
        "lane_rows": lane_report.get("lane_rows"),
        "started_blocked_lanes": started_blocked_lanes,
        "invalid_lanes": invalid_lanes,
        "lanes_with_completion_ready_items": lanes_with_completion_ready_items,
        "total_launch_items": total_launch_items,
        "validated_launch_items": validated_launch_items,
        "invalid_launch_items": invalid_launch_items,
        "started_items": started_items,
        "source_completion_ready_items": source_completion_ready_items,
        "requires_human_input_items": requires_human_input_items,
        "p487_open_blocked_rows": p487_report.get("open_blocked_rows"),
        "p487_validation_success": p487_validation.get("success"),
        "local_release_ready": local_release.get("release_ready"),
        "claims_blocked": claim_matrix.get("claims_blocked"),
        "training_import_allowed": False,
        "safe_for_training_import": False,
        "safe_for_model_claim": False,
        "customer_delivery_ready": False,
        "release_ready": False,
        "production_execution_allowed": False,
        "audit_jsonl": "datasets/governance/p488_next_unlock_agent_lane_status_gap_audit.jsonl",
        "policy": "P488 audit only. Agent lane status is not a reviewed decision, approval, training import, model claim, customer delivery authorization, release approval, deployment, sync, restart, or production execution.",
    }
    write_jsonl(OUT_JSONL, rows)
    OUT_REPORT.parent.mkdir(parents=True, exist_ok=True)
    OUT_REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "audit_rows": report["audit_rows"],
        "lane_audit_rows": report["lane_audit_rows"],
        "started_blocked_lanes": report["started_blocked_lanes"],
        "source_completion_ready_items": report["source_completion_ready_items"],
        "output": str(OUT_REPORT),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
