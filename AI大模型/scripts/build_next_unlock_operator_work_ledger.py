#!/usr/bin/env python3
"""Build a local operator work ledger from validated next-unlock checklists."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
CHECKLIST = AI_ROOT / "datasets" / "governance" / "next_unlock_action_checklist.jsonl"
CHECKLIST_STATUS = AI_ROOT / "datasets" / "governance" / "next_unlock_action_checklist_status.jsonl"
REMEDIATION_QUEUE = AI_ROOT / "datasets" / "governance" / "next_unlock_remediation_queue.jsonl"
HUMAN_BACKLOG = AI_ROOT / "datasets" / "governance" / "human_decision_backlog.jsonl"
REPORT_OUT = AI_ROOT / "reports" / "next_unlock_operator_work_ledger_report.json"
JSONL_OUT = AI_ROOT / "datasets" / "governance" / "next_unlock_operator_work_ledger.jsonl"


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")


def rel(path: Path) -> str:
    try:
        return str(path.relative_to(AI_ROOT))
    except ValueError:
        return str(path)


def by_action(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {str(row.get("action_id")): row for row in rows if row.get("action_id")}


def by_workstream(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {str(row.get("workstream")): row for row in rows if row.get("workstream")}


def ledger_status(checklist_row: dict[str, Any], status_row: dict[str, Any] | None) -> str:
    if not status_row or status_row.get("validation_status") != "checklist_validated_blocked":
        return "operator_work_blocked_by_checklist_validation"
    if checklist_row.get("completion_ready"):
        return "operator_work_invalid_completion_ready"
    if not checklist_row.get("requires_human_input"):
        return "operator_work_invalid_missing_human_input_guard"
    return "operator_work_open_blocked"


def main() -> int:
    parser = argparse.ArgumentParser(description="Build next-unlock operator work ledger")
    parser.add_argument("--checklist", type=Path, default=CHECKLIST)
    parser.add_argument("--checklist-status", type=Path, default=CHECKLIST_STATUS)
    parser.add_argument("--remediation-queue", type=Path, default=REMEDIATION_QUEUE)
    parser.add_argument("--human-backlog", type=Path, default=HUMAN_BACKLOG)
    parser.add_argument("--report", type=Path, default=REPORT_OUT)
    parser.add_argument("--jsonl", type=Path, default=JSONL_OUT)
    args = parser.parse_args()

    checklist_rows = load_jsonl(args.checklist)
    status_by_action = by_action(load_jsonl(args.checklist_status))
    remediation_by_action = by_action(load_jsonl(args.remediation_queue))
    backlog_by_workstream = by_workstream(load_jsonl(args.human_backlog))

    ledger_rows = []
    for row in sorted(checklist_rows, key=lambda item: (item.get("execution_order") or 999, str(item.get("checklist_id")))):
        action_id = str(row.get("action_id"))
        remediation = remediation_by_action.get(action_id, {})
        backlog = backlog_by_workstream.get(str(row.get("workstream")), {})
        status = ledger_status(row, status_by_action.get(action_id))
        local_materials_ready = not row.get("missing_local_materials")
        ledger_rows.append({
            "ledger_id": f"{action_id}-LOCAL-OPERATOR-WORK-LEDGER",
            "action_id": action_id,
            "checklist_id": row.get("checklist_id"),
            "execution_order": row.get("execution_order"),
            "lane_id": row.get("lane_id"),
            "workstream": row.get("workstream"),
            "ledger_status": status,
            "ready_for_local_operator_work": status == "operator_work_open_blocked" and local_materials_ready,
            "local_materials_ready": local_materials_ready,
            "completion_ready": False,
            "requires_human_input": True,
            "human_backlog_id": backlog.get("backlog_id"),
            "backlog_missing_rows": backlog.get("missing_rows"),
            "backlog_milestone_missing_rows": backlog.get("milestone_missing_rows"),
            "backlog_next_action": backlog.get("next_action"),
            "remediation_id": remediation.get("remediation_id"),
            "severity": remediation.get("severity"),
            "priority": remediation.get("priority"),
            "blocker_count": remediation.get("blocker_count"),
            "blocker_ids": remediation.get("blocker_ids") or [],
            "failed_checks": remediation.get("failed_checks") or [],
            "operator_open_first": row.get("operator_open_first"),
            "decision_input": row.get("decision_input"),
            "template": row.get("template"),
            "validator_report": row.get("validator_report"),
            "next_evidence_artifacts": row.get("next_evidence_artifacts") or [],
            "completion_condition": row.get("completion_condition"),
            "verify_command": row.get("verify_command") or "python3 scripts/run_safe_training_pipeline.py",
            "operator_work_steps": [
                "open operator_open_first material",
                "inspect local evidence only",
                "write human-reviewed input only into the listed decision or intake file when available",
                "run verify_command after any local human input is added",
                "keep ledger_status open until downstream validator reports completion-ready",
            ],
            "policy": "Operator work ledger only. Open ledger rows do not create reviewed decisions, approvals, claim readiness, customer delivery, deployment, sync, or server restart.",
        })

    write_jsonl(args.jsonl, ledger_rows)
    by_lane = Counter(str(row.get("lane_id")) for row in ledger_rows)
    by_workstream_count = Counter(str(row.get("workstream")) for row in ledger_rows)
    open_blocked = [row for row in ledger_rows if row["ledger_status"] == "operator_work_open_blocked"]
    report = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "local_only": True,
        "online_deployment": False,
        "source_checklist": rel(args.checklist),
        "source_checklist_status": rel(args.checklist_status),
        "source_remediation_queue": rel(args.remediation_queue),
        "source_human_backlog": rel(args.human_backlog),
        "jsonl": rel(args.jsonl),
        "ledger_rows": len(ledger_rows),
        "open_blocked_ledger_rows": len(open_blocked),
        "ready_for_local_operator_work_rows": sum(1 for row in ledger_rows if row["ready_for_local_operator_work"]),
        "invalid_or_blocked_ledger_rows": len(ledger_rows) - len(open_blocked),
        "completion_ready_items": sum(1 for row in ledger_rows if row["completion_ready"]),
        "requires_human_input_items": sum(1 for row in ledger_rows if row["requires_human_input"]),
        "local_materials_ready_rows": sum(1 for row in ledger_rows if row["local_materials_ready"]),
        "linked_human_backlog_rows": sum(1 for row in ledger_rows if row.get("human_backlog_id")),
        "unlinked_human_backlog_rows": sum(1 for row in ledger_rows if not row.get("human_backlog_id")),
        "total_backlog_missing_rows": sum(row.get("backlog_missing_rows") or 0 for row in ledger_rows),
        "lane_counts": dict(sorted(by_lane.items())),
        "workstream_counts": dict(sorted(by_workstream_count.items())),
        "top_work_items": [
            {
                "execution_order": row["execution_order"],
                "ledger_id": row["ledger_id"],
                "workstream": row["workstream"],
                "ledger_status": row["ledger_status"],
                "human_backlog_id": row["human_backlog_id"],
                "backlog_missing_rows": row["backlog_missing_rows"],
                "operator_open_first": row["operator_open_first"],
                "decision_input": row["decision_input"],
                "validator_report": row["validator_report"],
            }
            for row in ledger_rows[:12]
        ],
        "policy": "This ledger is a local operator coordination artifact only. It does not create reviewed decisions, grant approvals, unlock claims, approve customer delivery, authorize deployment, sync files, or restart servers.",
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "ledger_rows": report["ledger_rows"],
        "open_blocked_ledger_rows": report["open_blocked_ledger_rows"],
        "ready_for_local_operator_work_rows": report["ready_for_local_operator_work_rows"],
        "completion_ready_items": report["completion_ready_items"],
        "output": str(args.report),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
