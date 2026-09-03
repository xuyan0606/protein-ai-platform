#!/usr/bin/env python3
"""Build a source-bound audit of next-unlock blocker matrix gaps."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
BLOCKER_MATRIX = AI_ROOT / "reports" / "next_unlock_blocker_matrix.json"
BLOCKERS = AI_ROOT / "datasets" / "governance" / "next_unlock_blockers.jsonl"
P484_REPORT = AI_ROOT / "reports" / "p484_next_unlock_operator_navigation_gap_audit_report.json"
P484_VALIDATION = AI_ROOT / "reports" / "p484_next_unlock_operator_navigation_gap_audit_validation_report.json"
EXECUTION_VALIDATION = AI_ROOT / "reports" / "next_unlock_execution_validation_report.json"
LOCAL_RELEASE = AI_ROOT / "reports" / "local_release_manifest.json"
CLAIM_MATRIX = AI_ROOT / "reports" / "claim_readiness_matrix.json"
OUT_JSONL = AI_ROOT / "datasets" / "governance" / "p485_next_unlock_blocker_matrix_gap_audit.jsonl"
OUT_REPORT = AI_ROOT / "reports" / "p485_next_unlock_blocker_matrix_gap_audit_report.json"


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
        "source_report": "reports/next_unlock_blocker_matrix.json",
        "source_jsonl": "datasets/governance/next_unlock_blockers.jsonl",
        "source_state": source_state,
        "blocker": blocker,
        "training_import_allowed": False,
        "safe_for_training_import": False,
        "safe_for_model_claim": False,
        "customer_delivery_ready": False,
        "release_ready": False,
        "production_execution_allowed": False,
        "policy": "Blocker matrix gap audit only; blocker rows are evidence-gap tracking rows and do not create reviewed decisions, approvals, capability unlocks, training data, model claims, delivery authorization, release approval, or production execution.",
    }


def main() -> int:
    matrix = load_json(BLOCKER_MATRIX)
    p484_report = load_json(P484_REPORT)
    p484_validation = load_json(P484_VALIDATION)
    execution_validation = load_json(EXECUTION_VALIDATION)
    local_release = load_json(LOCAL_RELEASE)
    claim_matrix = load_json(CLAIM_MATRIX)
    blockers = [row for row in load_jsonl(BLOCKERS) if isinstance(row, dict)]
    rows: list[dict[str, Any]] = []

    for blocker in blockers:
        blocker_id = blocker.get("blocker_id")
        rows.append(base(
            f"p485-next-unlock-blocker::{blocker_id}",
            "next_unlock_blocker_matrix_gap",
            {
                "blocker_id": blocker_id,
                "action_id": blocker.get("action_id"),
                "stage_id": blocker.get("stage_id"),
                "stage_order": blocker.get("stage_order"),
                "workstream": blocker.get("workstream"),
                "priority": blocker.get("priority"),
                "severity": blocker.get("severity"),
                "source_status": blocker.get("status"),
                "blocker_category": blocker.get("blocker_category"),
                "failed_check": blocker.get("failed_check"),
                "observed": blocker.get("observed"),
                "expected": blocker.get("expected"),
                "decision_input": blocker.get("decision_input"),
                "validator_report": blocker.get("validator_report"),
                "next_evidence_artifact": blocker.get("next_evidence_artifact"),
                "completion_condition": blocker.get("completion_condition"),
            },
            "blocker matrix row remains open evidence-gap tracking only",
        ) | {
            "blocker_id": blocker_id,
            "action_id": blocker.get("action_id"),
            "stage_id": blocker.get("stage_id"),
            "workstream": blocker.get("workstream"),
            "severity": blocker.get("severity"),
            "source_status": blocker.get("status"),
            "completion_ready": False,
        })

    open_blocker_rows = sum(1 for row in blockers if row.get("status") == "open")
    rows.append(base(
        "p485-next-unlock-blocker-matrix-summary",
        "next_unlock_blocker_matrix_summary_gap",
        {
            "action_rows": matrix.get("action_rows"),
            "blocked_actions": matrix.get("blocked_actions"),
            "completion_ready_actions": matrix.get("completion_ready_actions"),
            "blocker_rows": matrix.get("blocker_rows"),
            "open_blocker_rows": open_blocker_rows,
            "critical_blockers": matrix.get("critical_blockers"),
            "high_blockers": matrix.get("high_blockers"),
            "medium_blockers": matrix.get("medium_blockers"),
            "workstream_blockers": matrix.get("workstream_blockers") or {},
            "stage_blockers": matrix.get("stage_blockers") or {},
            "p484_open_item_rows": p484_report.get("open_item_rows"),
            "p484_validation_success": p484_validation.get("success"),
            "execution_validation_blocked_actions": execution_validation.get("blocked_actions"),
            "local_release_ready": local_release.get("release_ready"),
            "claims_blocked": claim_matrix.get("claims_blocked"),
        },
        "blocker matrix still has open evidence gaps and cannot authorize downstream use",
    ) | {
        "open_blocker_rows": open_blocker_rows,
        "blocker_rows": matrix.get("blocker_rows"),
        "critical_blockers": matrix.get("critical_blockers"),
        "high_blockers": matrix.get("high_blockers"),
        "medium_blockers": matrix.get("medium_blockers"),
        "completion_ready": False,
    })

    report = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "local_only": True,
        "audit_rows": len(rows),
        "blocker_audit_rows": len(blockers),
        "summary_audit_rows": 1,
        "open_blocker_rows": open_blocker_rows,
        "blocker_rows": matrix.get("blocker_rows"),
        "critical_blockers": matrix.get("critical_blockers"),
        "high_blockers": matrix.get("high_blockers"),
        "medium_blockers": matrix.get("medium_blockers"),
        "blocked_actions": matrix.get("blocked_actions"),
        "completion_ready_actions": matrix.get("completion_ready_actions"),
        "p484_open_item_rows": p484_report.get("open_item_rows"),
        "p484_validation_success": p484_validation.get("success"),
        "execution_validation_blocked_actions": execution_validation.get("blocked_actions"),
        "local_release_ready": local_release.get("release_ready"),
        "claims_blocked": claim_matrix.get("claims_blocked"),
        "training_import_allowed": False,
        "safe_for_training_import": False,
        "safe_for_model_claim": False,
        "customer_delivery_ready": False,
        "release_ready": False,
        "production_execution_allowed": False,
        "audit_jsonl": "datasets/governance/p485_next_unlock_blocker_matrix_gap_audit.jsonl",
        "policy": "P485 audit only. Blocker matrix rows are not approvals, reviewed decisions, training imports, model claims, customer delivery authorization, release approval, or production execution.",
    }
    write_jsonl(OUT_JSONL, rows)
    OUT_REPORT.parent.mkdir(parents=True, exist_ok=True)
    OUT_REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "audit_rows": report["audit_rows"],
        "blocker_audit_rows": report["blocker_audit_rows"],
        "open_blocker_rows": report["open_blocker_rows"],
        "critical_blockers": report["critical_blockers"],
        "output": str(OUT_REPORT),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
