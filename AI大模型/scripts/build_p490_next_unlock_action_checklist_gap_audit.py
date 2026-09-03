#!/usr/bin/env python3
"""Build a source-bound audit of next-unlock action checklist gaps."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
CHECKLIST_REPORT = AI_ROOT / "reports" / "next_unlock_action_checklist_report.json"
CHECKLIST = AI_ROOT / "datasets" / "governance" / "next_unlock_action_checklist.jsonl"
CHECKLIST_VALIDATION = AI_ROOT / "reports" / "next_unlock_action_checklist_validation_report.json"
CHECKLIST_STATUS = AI_ROOT / "datasets" / "governance" / "next_unlock_action_checklist_status.jsonl"
P489_REPORT = AI_ROOT / "reports" / "p489_next_unlock_lane_dispatch_gap_audit_report.json"
P489_VALIDATION = AI_ROOT / "reports" / "p489_next_unlock_lane_dispatch_gap_audit_validation_report.json"
LOCAL_RELEASE = AI_ROOT / "reports" / "local_release_manifest.json"
CLAIM_MATRIX = AI_ROOT / "reports" / "claim_readiness_matrix.json"
OUT_JSONL = AI_ROOT / "datasets" / "governance" / "p490_next_unlock_action_checklist_gap_audit.jsonl"
OUT_REPORT = AI_ROOT / "reports" / "p490_next_unlock_action_checklist_gap_audit_report.json"


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
        "source_report": "reports/next_unlock_action_checklist_report.json",
        "source_jsonl": "datasets/governance/next_unlock_action_checklist.jsonl",
        "source_state": source_state,
        "blocker": blocker,
        "training_import_allowed": False,
        "safe_for_training_import": False,
        "safe_for_model_claim": False,
        "customer_delivery_ready": False,
        "release_ready": False,
        "production_execution_allowed": False,
        "policy": "Action checklist gap audit only; checklist rows are local operator guidance and do not create reviewed decisions, approvals, training data, model claims, customer delivery authorization, release approval, deployment, sync, restart, or production execution.",
    }


def main() -> int:
    checklist_report = load_json(CHECKLIST_REPORT)
    checklist_validation = load_json(CHECKLIST_VALIDATION)
    p489_report = load_json(P489_REPORT)
    p489_validation = load_json(P489_VALIDATION)
    local_release = load_json(LOCAL_RELEASE)
    claim_matrix = load_json(CLAIM_MATRIX)
    checklist_rows = [row for row in load_jsonl(CHECKLIST) if isinstance(row, dict)]
    status_rows = [row for row in load_jsonl(CHECKLIST_STATUS) if isinstance(row, dict)]
    status_by_checklist = {row.get("checklist_id"): row for row in status_rows}
    rows: list[dict[str, Any]] = []

    for item in checklist_rows:
        checklist_id = item.get("checklist_id")
        status = status_by_checklist.get(checklist_id, {})
        rows.append(base(
            f"p490-next-unlock-action-checklist::{checklist_id}",
            "next_unlock_action_checklist_gap",
            {
                "checklist_id": checklist_id,
                "action_id": item.get("action_id"),
                "dispatch_packet_id": item.get("dispatch_packet_id"),
                "lane_id": item.get("lane_id"),
                "workstream": item.get("workstream"),
                "source_checklist_status": item.get("checklist_status"),
                "validation_status": status.get("validation_status"),
                "dispatch_validation_status": item.get("dispatch_validation_status"),
                "launch_status": item.get("launch_status"),
                "ready_for_local_operator": item.get("ready_for_local_operator"),
                "source_completion_ready": item.get("completion_ready"),
                "requires_human_input": item.get("requires_human_input"),
                "operator_open_first": item.get("operator_open_first"),
                "decision_input": item.get("decision_input"),
                "template": item.get("template"),
                "validator_report": item.get("validator_report"),
                "missing_local_materials": item.get("missing_local_materials") or [],
                "checklist_steps": item.get("checklist_steps") or [],
            },
            "checklist row remains open blocked and requires human input before any completion or authorization",
        ) | {
            "checklist_id": checklist_id,
            "action_id": item.get("action_id"),
            "dispatch_packet_id": item.get("dispatch_packet_id"),
            "lane_id": item.get("lane_id"),
            "source_checklist_status": item.get("checklist_status"),
            "dispatch_validation_status": item.get("dispatch_validation_status"),
            "launch_status": item.get("launch_status"),
            "ready_for_local_operator": item.get("ready_for_local_operator"),
            "requires_human_input": item.get("requires_human_input"),
            "source_completion_ready": item.get("completion_ready"),
            "completion_ready": False,
        })

    open_blocked_checklist_rows = sum(1 for row in checklist_rows if row.get("checklist_status") == "checklist_open_blocked")
    invalid_or_blocked_checklist_rows = sum(1 for row in checklist_rows if row.get("checklist_status") != "checklist_open_blocked")
    ready_for_local_operator_rows = sum(1 for row in checklist_rows if row.get("ready_for_local_operator") is True)
    source_completion_ready_items = sum(1 for row in checklist_rows if row.get("completion_ready") is True)
    requires_human_input_items = sum(1 for row in checklist_rows if row.get("requires_human_input") is True)
    rows.append(base(
        "p490-next-unlock-action-checklist-summary",
        "next_unlock_action_checklist_summary_gap",
        {
            "checklist_rows": checklist_report.get("checklist_rows"),
            "open_blocked_checklist_rows": checklist_report.get("open_blocked_checklist_rows"),
            "invalid_or_blocked_checklist_rows": checklist_report.get("invalid_or_blocked_checklist_rows"),
            "ready_for_local_operator_rows": checklist_report.get("ready_for_local_operator_rows"),
            "completion_ready_items": checklist_report.get("completion_ready_items"),
            "requires_human_input_items": checklist_report.get("requires_human_input_items"),
            "missing_local_material_rows": checklist_report.get("missing_local_material_rows"),
            "lane_counts": checklist_report.get("lane_counts") or {},
            "p489_dispatch_ready_blocked_packets": p489_report.get("dispatch_ready_blocked_packets"),
            "p489_validation_success": p489_validation.get("success"),
            "local_release_ready": local_release.get("release_ready"),
            "claims_blocked": claim_matrix.get("claims_blocked"),
        },
        "action checklist remains a local operator guide and does not close any next-unlock gap",
    ) | {
        "checklist_rows": checklist_report.get("checklist_rows"),
        "open_blocked_checklist_rows": open_blocked_checklist_rows,
        "invalid_or_blocked_checklist_rows": invalid_or_blocked_checklist_rows,
        "ready_for_local_operator_rows": ready_for_local_operator_rows,
        "source_completion_ready_items": source_completion_ready_items,
        "requires_human_input_items": requires_human_input_items,
        "completion_ready": False,
    })

    report = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "local_only": True,
        "audit_rows": len(rows),
        "checklist_audit_rows": len(checklist_rows),
        "summary_audit_rows": 1,
        "checklist_rows": checklist_report.get("checklist_rows"),
        "open_blocked_checklist_rows": open_blocked_checklist_rows,
        "invalid_or_blocked_checklist_rows": invalid_or_blocked_checklist_rows,
        "ready_for_local_operator_rows": ready_for_local_operator_rows,
        "source_completion_ready_items": source_completion_ready_items,
        "requires_human_input_items": requires_human_input_items,
        "p489_dispatch_ready_blocked_packets": p489_report.get("dispatch_ready_blocked_packets"),
        "p489_validation_success": p489_validation.get("success"),
        "local_release_ready": local_release.get("release_ready"),
        "claims_blocked": claim_matrix.get("claims_blocked"),
        "training_import_allowed": False,
        "safe_for_training_import": False,
        "safe_for_model_claim": False,
        "customer_delivery_ready": False,
        "release_ready": False,
        "production_execution_allowed": False,
        "audit_jsonl": "datasets/governance/p490_next_unlock_action_checklist_gap_audit.jsonl",
        "policy": "P490 audit only. Action checklist rows are not reviewed decisions, approvals, training imports, model claims, customer delivery authorization, release approval, deployment, sync, restart, or production execution.",
    }
    write_jsonl(OUT_JSONL, rows)
    OUT_REPORT.parent.mkdir(parents=True, exist_ok=True)
    OUT_REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "audit_rows": report["audit_rows"],
        "checklist_audit_rows": report["checklist_audit_rows"],
        "open_blocked_checklist_rows": report["open_blocked_checklist_rows"],
        "source_completion_ready_items": report["source_completion_ready_items"],
        "output": str(OUT_REPORT),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
