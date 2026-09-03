#!/usr/bin/env python3
"""Validate next-unlock action-level local operator checklists."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
CHECKLIST = AI_ROOT / "datasets" / "governance" / "next_unlock_action_checklist.jsonl"
LAUNCH_BOARD = AI_ROOT / "datasets" / "governance" / "next_unlock_multi_agent_launch_board.jsonl"
DISPATCH_STATUS = AI_ROOT / "datasets" / "governance" / "next_unlock_lane_dispatch_status.jsonl"
REPORT_OUT = AI_ROOT / "reports" / "next_unlock_action_checklist_validation_report.json"
JSONL_OUT = AI_ROOT / "datasets" / "governance" / "next_unlock_action_checklist_status.jsonl"


REQUIRED_CHECKLIST_STEPS = [
    "record human-reviewed input only when available",
    "do not mark completion until downstream validator reports completion-ready",
]

REQUIRED_POLICY_TERMS = [
    "reviewed decisions",
    "approvals",
    "claims",
    "customer delivery",
    "deployment",
    "sync",
    "restart",
]


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


def path_exists(rel_path: str | None) -> bool:
    return bool(rel_path) and (AI_ROOT / rel_path).exists()


def check(name: str, passed: bool, observed: Any = None, expected: Any = None) -> dict[str, Any]:
    row = {"name": name, "passed": bool(passed)}
    if observed is not None:
        row["observed"] = observed
    if expected is not None:
        row["expected"] = expected
    return row


def by_action(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {str(row.get("action_id")): row for row in rows if row.get("action_id")}


def by_dispatch(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {str(row.get("dispatch_packet_id")): row for row in rows if row.get("dispatch_packet_id")}


def validate_row(
    row: dict[str, Any],
    launch_row: dict[str, Any] | None,
    dispatch_row: dict[str, Any] | None,
) -> list[dict[str, Any]]:
    action_id = str(row.get("action_id"))
    checklist_steps = row.get("checklist_steps") or []
    policy = str(row.get("policy") or "").lower()
    referenced_paths = [
        row.get("operator_open_first"),
        row.get("decision_input"),
        row.get("template"),
        row.get("validator_report"),
        *(row.get("next_evidence_artifacts") or []),
    ]
    missing_paths = sorted({path for path in referenced_paths if path and not path_exists(path)})
    launch_order = launch_row.get("execution_order") if launch_row else None
    launch_status = launch_row.get("launch_status") if launch_row else None
    dispatch_validation_status = dispatch_row.get("validation_status") if dispatch_row else None
    return [
        check("matching launch board row exists", launch_row is not None, action_id, "existing action_id"),
        check("matching dispatch validation row exists", dispatch_row is not None, row.get("dispatch_packet_id"), "existing dispatch_packet_id"),
        check("checklist id is stable", row.get("checklist_id") == f"{action_id}-LOCAL-ACTION-CHECKLIST", row.get("checklist_id"), f"{action_id}-LOCAL-ACTION-CHECKLIST"),
        check("checklist remains open blocked", row.get("checklist_status") == "checklist_open_blocked", row.get("checklist_status"), "checklist_open_blocked"),
        check("dispatch validation remains blocked", row.get("dispatch_validation_status") == dispatch_validation_status == "dispatch_validated_blocked", {"checklist": row.get("dispatch_validation_status"), "dispatch": dispatch_validation_status}, "dispatch_validated_blocked"),
        check("launch status remains started blocked", row.get("launch_status") == launch_status == "local_agent_started_blocked", {"checklist": row.get("launch_status"), "launch": launch_status}, "local_agent_started_blocked"),
        check("ready for local operator is true", row.get("ready_for_local_operator") is True, row.get("ready_for_local_operator"), True),
        check("completion-ready remains false", row.get("completion_ready") is False, row.get("completion_ready"), False),
        check("requires human input remains true", row.get("requires_human_input") is True, row.get("requires_human_input"), True),
        check("execution order matches launch board", row.get("execution_order") == launch_order, {"checklist": row.get("execution_order"), "launch": launch_order}, "same execution_order"),
        check("operator path exists", path_exists(row.get("operator_open_first")), row.get("operator_open_first"), "existing local path"),
        check("decision input path exists when present", not row.get("decision_input") or path_exists(row.get("decision_input")), row.get("decision_input"), "optional existing local path"),
        check("template path exists when present", not row.get("template") or path_exists(row.get("template")), row.get("template"), "optional existing local path"),
        check("validator report exists", path_exists(row.get("validator_report")), row.get("validator_report"), "existing local path"),
        check("next evidence artifacts exist", not missing_paths, missing_paths, []),
        check("reported missing local materials remains empty", not row.get("missing_local_materials") and not missing_paths, {"reported": row.get("missing_local_materials"), "observed": missing_paths}, []),
        check("verify command is local safe pipeline", row.get("verify_command") == "python3 scripts/run_safe_training_pipeline.py", row.get("verify_command"), "python3 scripts/run_safe_training_pipeline.py"),
        check("checklist steps preserve human-input guard", all(step in checklist_steps for step in REQUIRED_CHECKLIST_STEPS), checklist_steps, REQUIRED_CHECKLIST_STEPS),
        check("policy blocks completion/approval/deployment meanings", all(term in policy for term in REQUIRED_POLICY_TERMS), row.get("policy"), REQUIRED_POLICY_TERMS),
    ]


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate next-unlock action checklist")
    parser.add_argument("--checklist", type=Path, default=CHECKLIST)
    parser.add_argument("--launch-board", type=Path, default=LAUNCH_BOARD)
    parser.add_argument("--dispatch-status", type=Path, default=DISPATCH_STATUS)
    parser.add_argument("--report", type=Path, default=REPORT_OUT)
    parser.add_argument("--jsonl", type=Path, default=JSONL_OUT)
    args = parser.parse_args()

    checklist_rows = load_jsonl(args.checklist)
    launch_rows = by_action(load_jsonl(args.launch_board))
    dispatch_rows = by_dispatch(load_jsonl(args.dispatch_status))

    status_rows = []
    for row in sorted(checklist_rows, key=lambda item: (item.get("execution_order") or 999, str(item.get("checklist_id")))):
        checks = validate_row(row, launch_rows.get(str(row.get("action_id"))), dispatch_rows.get(str(row.get("dispatch_packet_id"))))
        failed_checks = [item["name"] for item in checks if not item["passed"]]
        status_rows.append({
            "checklist_id": row.get("checklist_id"),
            "action_id": row.get("action_id"),
            "dispatch_packet_id": row.get("dispatch_packet_id"),
            "lane_id": row.get("lane_id"),
            "execution_order": row.get("execution_order"),
            "workstream": row.get("workstream"),
            "checklist_status": row.get("checklist_status"),
            "validation_status": "checklist_validated_blocked" if not failed_checks else "checklist_invalid",
            "ready_for_local_operator": row.get("ready_for_local_operator"),
            "completion_ready": row.get("completion_ready"),
            "requires_human_input": row.get("requires_human_input"),
            "missing_local_materials": row.get("missing_local_materials") or [],
            "failed_checks": failed_checks,
            "checks": checks,
            "verify_command": row.get("verify_command"),
            "policy": "Checklist validation only. Validated checklist means local operator guide only; it is not completion, approval, customer delivery, deployment, sync, server restart, or claim readiness.",
        })

    write_jsonl(args.jsonl, status_rows)
    invalid_rows = [row for row in status_rows if row["validation_status"] == "checklist_invalid"]
    report = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "local_only": True,
        "online_deployment": False,
        "source_checklist": rel(args.checklist),
        "source_launch_board": rel(args.launch_board),
        "source_dispatch_status": rel(args.dispatch_status),
        "jsonl": rel(args.jsonl),
        "checklist_rows": len(status_rows),
        "validated_checklist_rows": len(status_rows) - len(invalid_rows),
        "invalid_checklist_rows": len(invalid_rows),
        "completion_ready_items": sum(1 for row in status_rows if row["completion_ready"]),
        "requires_human_input_items": sum(1 for row in status_rows if row["requires_human_input"]),
        "missing_local_material_rows": sum(1 for row in status_rows if row["missing_local_materials"]),
        "invalid_checklist_items": [
            {
                "checklist_id": row["checklist_id"],
                "action_id": row["action_id"],
                "failed_checks": row["failed_checks"],
            }
            for row in invalid_rows
        ],
        "policy": "This validator confirms local operator checklist semantics only. It does not create reviewed decisions, grant approvals, unlock claims, approve customer delivery, authorize deployment, sync files, or restart servers.",
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "checklist_rows": report["checklist_rows"],
        "validated_checklist_rows": report["validated_checklist_rows"],
        "invalid_checklist_rows": report["invalid_checklist_rows"],
        "completion_ready_items": report["completion_ready_items"],
        "output": str(args.report),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
