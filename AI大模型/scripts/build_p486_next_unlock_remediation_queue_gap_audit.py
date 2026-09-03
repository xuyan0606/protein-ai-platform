#!/usr/bin/env python3
"""Build a source-bound audit of next-unlock remediation queue gaps."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
REMEDIATION_REPORT = AI_ROOT / "reports" / "next_unlock_remediation_queue.json"
REMEDIATION_QUEUE = AI_ROOT / "datasets" / "governance" / "next_unlock_remediation_queue.jsonl"
BLOCKER_MATRIX = AI_ROOT / "reports" / "next_unlock_blocker_matrix.json"
P485_REPORT = AI_ROOT / "reports" / "p485_next_unlock_blocker_matrix_gap_audit_report.json"
P485_VALIDATION = AI_ROOT / "reports" / "p485_next_unlock_blocker_matrix_gap_audit_validation_report.json"
LOCAL_RELEASE = AI_ROOT / "reports" / "local_release_manifest.json"
CLAIM_MATRIX = AI_ROOT / "reports" / "claim_readiness_matrix.json"
OUT_JSONL = AI_ROOT / "datasets" / "governance" / "p486_next_unlock_remediation_queue_gap_audit.jsonl"
OUT_REPORT = AI_ROOT / "reports" / "p486_next_unlock_remediation_queue_gap_audit_report.json"


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
        "source_report": "reports/next_unlock_remediation_queue.json",
        "source_jsonl": "datasets/governance/next_unlock_remediation_queue.jsonl",
        "source_state": source_state,
        "blocker": blocker,
        "training_import_allowed": False,
        "safe_for_training_import": False,
        "safe_for_model_claim": False,
        "customer_delivery_ready": False,
        "release_ready": False,
        "production_execution_allowed": False,
        "policy": "Remediation queue gap audit only; queue rows and ready-to-start observations do not create reviewed decisions, approvals, capability unlocks, training data, model claims, delivery authorization, release approval, or production execution.",
    }


def main() -> int:
    report = load_json(REMEDIATION_REPORT)
    blocker_matrix = load_json(BLOCKER_MATRIX)
    p485_report = load_json(P485_REPORT)
    p485_validation = load_json(P485_VALIDATION)
    local_release = load_json(LOCAL_RELEASE)
    claim_matrix = load_json(CLAIM_MATRIX)
    queue = [row for row in load_jsonl(REMEDIATION_QUEUE) if isinstance(row, dict)]
    rows: list[dict[str, Any]] = []

    for item in queue:
        remediation_id = item.get("remediation_id")
        blocker_ids = list(item.get("blocker_ids") or [])
        failed_checks = list(item.get("failed_checks") or [])
        next_evidence_artifacts = list(item.get("next_evidence_artifacts") or [])
        rows.append(base(
            f"p486-next-unlock-remediation::{remediation_id}",
            "next_unlock_remediation_queue_gap",
            {
                "remediation_id": remediation_id,
                "action_id": item.get("action_id"),
                "stage_id": item.get("stage_id"),
                "stage_order": item.get("stage_order"),
                "workstream": item.get("workstream"),
                "priority": item.get("priority"),
                "severity": item.get("severity"),
                "queue_status": item.get("queue_status"),
                "source_ready_to_start": item.get("ready_to_start") is True,
                "requires_human_input": item.get("requires_human_input") is True,
                "remediation_type": item.get("remediation_type"),
                "blocker_count": item.get("blocker_count"),
                "blocker_ids": blocker_ids,
                "blocker_categories": item.get("blocker_categories") or [],
                "failed_checks": failed_checks,
                "failed_check_count": len(failed_checks),
                "operator_open_first": item.get("operator_open_first"),
                "decision_input": item.get("decision_input"),
                "template": item.get("template"),
                "validator_report": item.get("validator_report"),
                "next_evidence_artifacts": next_evidence_artifacts,
                "next_evidence_artifact_count": len(next_evidence_artifacts),
                "execution_order": item.get("execution_order"),
            },
            "remediation queue row remains open planning work and is not an authorization",
        ) | {
            "remediation_id": remediation_id,
            "action_id": item.get("action_id"),
            "stage_id": item.get("stage_id"),
            "workstream": item.get("workstream"),
            "severity": item.get("severity"),
            "queue_status": item.get("queue_status"),
            "source_ready_to_start": item.get("ready_to_start") is True,
            "requires_human_input": item.get("requires_human_input") is True,
            "blocker_count": item.get("blocker_count"),
            "completion_ready": False,
        })

    open_rows = sum(1 for row in queue if row.get("queue_status") == "open")
    ready_to_start_rows = sum(1 for row in queue if row.get("ready_to_start") is True)
    requires_human_input_rows = sum(1 for row in queue if row.get("requires_human_input") is True)
    rows.append(base(
        "p486-next-unlock-remediation-queue-summary",
        "next_unlock_remediation_queue_summary_gap",
        {
            "queue_rows": report.get("queue_rows"),
            "open_items": report.get("open_items"),
            "ready_to_start_items": report.get("ready_to_start_items"),
            "requires_human_input_items": report.get("requires_human_input_items"),
            "critical_items": report.get("critical_items"),
            "high_items": report.get("high_items"),
            "medium_items": report.get("medium_items"),
            "workstream_items": report.get("workstream_items") or {},
            "source_blocker_rows": blocker_matrix.get("blocker_rows"),
            "source_open_blocker_rows": p485_report.get("open_blocker_rows"),
            "p485_validation_success": p485_validation.get("success"),
            "local_release_ready": local_release.get("release_ready"),
            "claims_blocked": claim_matrix.get("claims_blocked"),
        },
        "remediation queue remains open and requires human input before any upstream gate can change",
    ) | {
        "queue_rows": report.get("queue_rows"),
        "open_rows": open_rows,
        "ready_to_start_rows": ready_to_start_rows,
        "requires_human_input_rows": requires_human_input_rows,
        "completion_ready": False,
    })

    out_report = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "local_only": True,
        "audit_rows": len(rows),
        "remediation_audit_rows": len(queue),
        "summary_audit_rows": 1,
        "queue_rows": report.get("queue_rows"),
        "open_rows": open_rows,
        "ready_to_start_rows": ready_to_start_rows,
        "requires_human_input_rows": requires_human_input_rows,
        "critical_rows": report.get("critical_items"),
        "high_rows": report.get("high_items"),
        "medium_rows": report.get("medium_items"),
        "source_blocker_rows": blocker_matrix.get("blocker_rows"),
        "source_open_blocker_rows": p485_report.get("open_blocker_rows"),
        "p485_validation_success": p485_validation.get("success"),
        "local_release_ready": local_release.get("release_ready"),
        "claims_blocked": claim_matrix.get("claims_blocked"),
        "training_import_allowed": False,
        "safe_for_training_import": False,
        "safe_for_model_claim": False,
        "customer_delivery_ready": False,
        "release_ready": False,
        "production_execution_allowed": False,
        "audit_jsonl": "datasets/governance/p486_next_unlock_remediation_queue_gap_audit.jsonl",
        "policy": "P486 audit only. Remediation queue rows are not approvals, reviewed decisions, training imports, model claims, customer delivery authorization, release approval, or production execution.",
    }
    write_jsonl(OUT_JSONL, rows)
    OUT_REPORT.parent.mkdir(parents=True, exist_ok=True)
    OUT_REPORT.write_text(json.dumps(out_report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "audit_rows": out_report["audit_rows"],
        "remediation_audit_rows": out_report["remediation_audit_rows"],
        "open_rows": out_report["open_rows"],
        "ready_to_start_rows": out_report["ready_to_start_rows"],
        "output": str(OUT_REPORT),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
