#!/usr/bin/env python3
"""Build a source-bound audit of next-unlock operator navigation gaps."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
OPERATOR_INDEX = AI_ROOT / "reports" / "next_unlock_operator_index.json"
OPERATOR_INDEX_JSONL = AI_ROOT / "datasets" / "governance" / "next_unlock_operator_index.jsonl"
EXECUTION_VALIDATION = AI_ROOT / "reports" / "next_unlock_execution_validation_report.json"
P483_REPORT = AI_ROOT / "reports" / "p483_next_unlock_execution_gap_audit_report.json"
P483_VALIDATION = AI_ROOT / "reports" / "p483_next_unlock_execution_gap_audit_validation_report.json"
LOCAL_RELEASE = AI_ROOT / "reports" / "local_release_manifest.json"
CLAIM_MATRIX = AI_ROOT / "reports" / "claim_readiness_matrix.json"
OUT_JSONL = AI_ROOT / "datasets" / "governance" / "p484_next_unlock_operator_navigation_gap_audit.jsonl"
OUT_REPORT = AI_ROOT / "reports" / "p484_next_unlock_operator_navigation_gap_audit_report.json"


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
        "source_report": "reports/next_unlock_operator_index.json",
        "source_jsonl": "datasets/governance/next_unlock_operator_index.jsonl",
        "source_state": source_state,
        "blocker": blocker,
        "training_import_allowed": False,
        "safe_for_training_import": False,
        "safe_for_model_claim": False,
        "customer_delivery_ready": False,
        "release_ready": False,
        "production_execution_allowed": False,
        "policy": "Operator navigation gap audit only; index rows and local paths do not create reviewed decisions, approvals, capability unlocks, training data, model claims, delivery authorization, release approval, or production execution.",
    }


def main() -> int:
    index = load_json(OPERATOR_INDEX)
    execution_validation = load_json(EXECUTION_VALIDATION)
    p483_report = load_json(P483_REPORT)
    p483_validation = load_json(P483_VALIDATION)
    local_release = load_json(LOCAL_RELEASE)
    claim_matrix = load_json(CLAIM_MATRIX)
    index_rows = [row for row in load_jsonl(OPERATOR_INDEX_JSONL) if isinstance(row, dict)]
    rows: list[dict[str, Any]] = []

    for item in index_rows:
        action_id = item.get("action_id")
        failed_checks = list(item.get("failed_checks") or [])
        operator_sequence = list(item.get("operator_sequence") or [])
        source_completion_ready = item.get("completion_ready") is True
        missing_local_paths = [
            name
            for name, value in (
                ("operator_open_first", item.get("operator_open_first_exists")),
                ("decision_input", item.get("decision_input_exists")),
                ("template", item.get("template_exists")),
                ("validator_report", item.get("validator_report_exists")),
            )
            if value is False and item.get(name)
        ]
        rows.append(base(
            f"p484-next-unlock-operator-navigation::{action_id}",
            "next_unlock_operator_navigation_gap",
            {
                "action_id": action_id,
                "stage_id": item.get("stage_id"),
                "stage_order": item.get("stage_order"),
                "workstream": item.get("workstream"),
                "assigned_role": item.get("assigned_role"),
                "source_status": item.get("status"),
                "source_started": item.get("started"),
                "source_completion_ready": source_completion_ready,
                "failed_checks": failed_checks,
                "failed_check_count": len(failed_checks),
                "operator_open_first": item.get("operator_open_first"),
                "operator_open_first_exists": item.get("operator_open_first_exists"),
                "decision_input": item.get("decision_input"),
                "decision_input_exists": item.get("decision_input_exists"),
                "template": item.get("template"),
                "template_exists": item.get("template_exists"),
                "validator_report": item.get("validator_report"),
                "validator_report_exists": item.get("validator_report_exists"),
                "operator_sequence_length": len(operator_sequence),
                "missing_local_paths": missing_local_paths,
            },
            "operator index entry is navigation only and remains non-authorizing",
        ) | {
            "action_id": action_id,
            "stage_id": item.get("stage_id"),
            "workstream": item.get("workstream"),
            "source_status": item.get("status"),
            "source_completion_ready": source_completion_ready,
            "failed_check_count": len(failed_checks),
            "missing_local_path_count": len(missing_local_paths),
            "completion_ready": False,
        })

    open_items = int(index.get("open_items") or 0)
    source_ready_items = int(index.get("completion_ready_items") or 0)
    rows.append(base(
        "p484-next-unlock-operator-navigation-summary",
        "next_unlock_operator_navigation_summary_gap",
        {
            "total_actions": index.get("total_actions"),
            "started_actions": index.get("started_actions"),
            "open_items": open_items,
            "source_completion_ready_items": source_ready_items,
            "validation_completion_ready_actions": index.get("validation_completion_ready_actions"),
            "validation_blocked_actions": index.get("validation_blocked_actions"),
            "missing_operator_open_first": index.get("missing_operator_open_first") or [],
            "missing_decision_inputs": index.get("missing_decision_inputs") or [],
            "missing_templates": index.get("missing_templates") or [],
            "missing_validator_reports": index.get("missing_validator_reports") or [],
            "execution_validation_blocked_actions": execution_validation.get("blocked_actions"),
            "p483_blocked_gap_rows": p483_report.get("blocked_gap_rows"),
            "p483_validation_success": p483_validation.get("success"),
            "local_release_ready": local_release.get("release_ready"),
            "claims_blocked": claim_matrix.get("claims_blocked"),
        },
        "operator navigation index still contains open items and cannot authorize downstream use",
    ) | {
        "open_item_rows": open_items,
        "source_completion_ready_items": source_ready_items,
        "blocked_gap_rows": open_items,
        "completion_ready": False,
    })

    report = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "local_only": True,
        "audit_rows": len(rows),
        "operator_navigation_rows": len(index_rows),
        "summary_audit_rows": 1,
        "open_item_rows": open_items,
        "source_completion_ready_items": source_ready_items,
        "blocked_gap_rows": open_items,
        "total_actions": index.get("total_actions"),
        "started_actions": index.get("started_actions"),
        "validation_completion_ready_actions": index.get("validation_completion_ready_actions"),
        "validation_blocked_actions": index.get("validation_blocked_actions"),
        "missing_operator_open_first": index.get("missing_operator_open_first") or [],
        "missing_decision_inputs": index.get("missing_decision_inputs") or [],
        "missing_templates": index.get("missing_templates") or [],
        "missing_validator_reports": index.get("missing_validator_reports") or [],
        "p483_blocked_gap_rows": p483_report.get("blocked_gap_rows"),
        "p483_validation_success": p483_validation.get("success"),
        "local_release_ready": local_release.get("release_ready"),
        "claims_blocked": claim_matrix.get("claims_blocked"),
        "training_import_allowed": False,
        "safe_for_training_import": False,
        "safe_for_model_claim": False,
        "customer_delivery_ready": False,
        "release_ready": False,
        "production_execution_allowed": False,
        "audit_jsonl": "datasets/governance/p484_next_unlock_operator_navigation_gap_audit.jsonl",
        "policy": "P484 audit only. Operator navigation entries are not approvals, reviewed decisions, training imports, model claims, customer delivery authorization, release approval, or production execution.",
    }
    write_jsonl(OUT_JSONL, rows)
    OUT_REPORT.parent.mkdir(parents=True, exist_ok=True)
    OUT_REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "audit_rows": report["audit_rows"],
        "operator_navigation_rows": report["operator_navigation_rows"],
        "open_item_rows": report["open_item_rows"],
        "source_completion_ready_items": report["source_completion_ready_items"],
        "output": str(OUT_REPORT),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
