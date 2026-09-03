#!/usr/bin/env python3
"""Validate next-unlock local operator work ledger semantics."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
LEDGER = AI_ROOT / "datasets" / "governance" / "next_unlock_operator_work_ledger.jsonl"
CHECKLIST_STATUS = AI_ROOT / "datasets" / "governance" / "next_unlock_action_checklist_status.jsonl"
REMEDIATION_QUEUE = AI_ROOT / "datasets" / "governance" / "next_unlock_remediation_queue.jsonl"
HUMAN_BACKLOG = AI_ROOT / "datasets" / "governance" / "human_decision_backlog.jsonl"
REPORT_OUT = AI_ROOT / "reports" / "next_unlock_operator_work_ledger_validation_report.json"
JSONL_OUT = AI_ROOT / "datasets" / "governance" / "next_unlock_operator_work_ledger_status.jsonl"


BACKLOG_OPTIONAL_WORKSTREAMS = {"msa_conservation", "model_claim"}
REQUIRED_WORK_STEPS = [
    "write human-reviewed input only into the listed decision or intake file when available",
    "keep ledger_status open until downstream validator reports completion-ready",
]
REQUIRED_POLICY_TERMS = [
    "reviewed decisions",
    "approvals",
    "claim readiness",
    "customer delivery",
    "deployment",
    "sync",
    "server restart",
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


def by_workstream(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {str(row.get("workstream")): row for row in rows if row.get("workstream")}


def validate_row(
    row: dict[str, Any],
    checklist_status: dict[str, Any] | None,
    remediation: dict[str, Any] | None,
    backlog: dict[str, Any] | None,
) -> list[dict[str, Any]]:
    action_id = str(row.get("action_id"))
    workstream = str(row.get("workstream"))
    work_steps = row.get("operator_work_steps") or []
    policy = str(row.get("policy") or "").lower()
    referenced_paths = [
        row.get("operator_open_first"),
        row.get("decision_input"),
        row.get("template"),
        row.get("validator_report"),
        *(row.get("next_evidence_artifacts") or []),
    ]
    missing_paths = sorted({path for path in referenced_paths if path and not path_exists(path)})
    backlog_required = workstream not in BACKLOG_OPTIONAL_WORKSTREAMS
    expected_backlog_id = backlog.get("backlog_id") if backlog else None
    expected_missing_rows = backlog.get("missing_rows") if backlog else None
    return [
        check("matching checklist status row exists", checklist_status is not None, action_id, "existing action_id"),
        check("matching remediation row exists", remediation is not None, action_id, "existing action_id"),
        check("human backlog link matches requirement", (backlog is not None and row.get("human_backlog_id") == expected_backlog_id) if backlog_required else row.get("human_backlog_id") is None, {"ledger": row.get("human_backlog_id"), "backlog": expected_backlog_id, "required": backlog_required}, "matched when required, null when optional"),
        check("ledger id is stable", row.get("ledger_id") == f"{action_id}-LOCAL-OPERATOR-WORK-LEDGER", row.get("ledger_id"), f"{action_id}-LOCAL-OPERATOR-WORK-LEDGER"),
        check("checklist id is stable", row.get("checklist_id") == f"{action_id}-LOCAL-ACTION-CHECKLIST", row.get("checklist_id"), f"{action_id}-LOCAL-ACTION-CHECKLIST"),
        check("ledger remains open blocked", row.get("ledger_status") == "operator_work_open_blocked", row.get("ledger_status"), "operator_work_open_blocked"),
        check("checklist validation remains blocked", checklist_status and checklist_status.get("validation_status") == "checklist_validated_blocked", checklist_status.get("validation_status") if checklist_status else None, "checklist_validated_blocked"),
        check("ready for local operator work is true", row.get("ready_for_local_operator_work") is True, row.get("ready_for_local_operator_work"), True),
        check("local materials remain ready", row.get("local_materials_ready") is True and not missing_paths, {"flag": row.get("local_materials_ready"), "missing": missing_paths}, True),
        check("completion-ready remains false", row.get("completion_ready") is False, row.get("completion_ready"), False),
        check("requires human input remains true", row.get("requires_human_input") is True, row.get("requires_human_input"), True),
        check("execution order matches checklist", row.get("execution_order") == (checklist_status or {}).get("execution_order"), {"ledger": row.get("execution_order"), "checklist": (checklist_status or {}).get("execution_order")}, "same execution_order"),
        check("remediation id matches action", row.get("remediation_id") == (remediation or {}).get("remediation_id"), {"ledger": row.get("remediation_id"), "remediation": (remediation or {}).get("remediation_id")}, "same remediation_id"),
        check("blocker count matches remediation", row.get("blocker_count") == (remediation or {}).get("blocker_count"), {"ledger": row.get("blocker_count"), "remediation": (remediation or {}).get("blocker_count")}, "same blocker_count"),
        check("blocker ids match remediation", row.get("blocker_ids") == ((remediation or {}).get("blocker_ids") or []), row.get("blocker_ids"), (remediation or {}).get("blocker_ids") or []),
        check("failed checks match remediation", row.get("failed_checks") == ((remediation or {}).get("failed_checks") or []), row.get("failed_checks"), (remediation or {}).get("failed_checks") or []),
        check("backlog missing rows match when linked", (row.get("backlog_missing_rows") == expected_missing_rows) if backlog else row.get("backlog_missing_rows") is None, {"ledger": row.get("backlog_missing_rows"), "backlog": expected_missing_rows}, "same missing_rows or null"),
        check("operator path exists", path_exists(row.get("operator_open_first")), row.get("operator_open_first"), "existing local path"),
        check("decision input path exists when present", not row.get("decision_input") or path_exists(row.get("decision_input")), row.get("decision_input"), "optional existing local path"),
        check("template path exists when present", not row.get("template") or path_exists(row.get("template")), row.get("template"), "optional existing local path"),
        check("validator report exists", path_exists(row.get("validator_report")), row.get("validator_report"), "existing local path"),
        check("next evidence artifacts exist", not missing_paths, missing_paths, []),
        check("verify command is local safe pipeline", row.get("verify_command") == "python3 scripts/run_safe_training_pipeline.py", row.get("verify_command"), "python3 scripts/run_safe_training_pipeline.py"),
        check("operator work steps preserve human-input guard", all(step in work_steps for step in REQUIRED_WORK_STEPS), work_steps, REQUIRED_WORK_STEPS),
        check("policy blocks completion/approval/deployment meanings", all(term in policy for term in REQUIRED_POLICY_TERMS), row.get("policy"), REQUIRED_POLICY_TERMS),
    ]


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate next-unlock operator work ledger")
    parser.add_argument("--ledger", type=Path, default=LEDGER)
    parser.add_argument("--checklist-status", type=Path, default=CHECKLIST_STATUS)
    parser.add_argument("--remediation-queue", type=Path, default=REMEDIATION_QUEUE)
    parser.add_argument("--human-backlog", type=Path, default=HUMAN_BACKLOG)
    parser.add_argument("--report", type=Path, default=REPORT_OUT)
    parser.add_argument("--jsonl", type=Path, default=JSONL_OUT)
    args = parser.parse_args()

    ledger_rows = load_jsonl(args.ledger)
    checklist_by_action = by_action(load_jsonl(args.checklist_status))
    remediation_by_action = by_action(load_jsonl(args.remediation_queue))
    backlog_by_workstream = by_workstream(load_jsonl(args.human_backlog))

    status_rows = []
    for row in sorted(ledger_rows, key=lambda item: (item.get("execution_order") or 999, str(item.get("ledger_id")))):
        action_id = str(row.get("action_id"))
        workstream = str(row.get("workstream"))
        checks = validate_row(
            row,
            checklist_by_action.get(action_id),
            remediation_by_action.get(action_id),
            backlog_by_workstream.get(workstream),
        )
        failed_checks = [item["name"] for item in checks if not item["passed"]]
        status_rows.append({
            "ledger_id": row.get("ledger_id"),
            "action_id": action_id,
            "checklist_id": row.get("checklist_id"),
            "lane_id": row.get("lane_id"),
            "workstream": workstream,
            "execution_order": row.get("execution_order"),
            "ledger_status": row.get("ledger_status"),
            "validation_status": "operator_work_ledger_validated_blocked" if not failed_checks else "operator_work_ledger_invalid",
            "ready_for_local_operator_work": row.get("ready_for_local_operator_work"),
            "completion_ready": row.get("completion_ready"),
            "requires_human_input": row.get("requires_human_input"),
            "human_backlog_id": row.get("human_backlog_id"),
            "backlog_missing_rows": row.get("backlog_missing_rows"),
            "failed_checks": failed_checks,
            "checks": checks,
            "verify_command": row.get("verify_command"),
            "policy": "Operator work ledger validation only. Validated ledger means local work tracking only; it is not completion, approval, customer delivery, deployment, sync, server restart, or claim readiness.",
        })

    write_jsonl(args.jsonl, status_rows)
    invalid_rows = [row for row in status_rows if row["validation_status"] == "operator_work_ledger_invalid"]
    report = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "local_only": True,
        "online_deployment": False,
        "source_ledger": rel(args.ledger),
        "source_checklist_status": rel(args.checklist_status),
        "source_remediation_queue": rel(args.remediation_queue),
        "source_human_backlog": rel(args.human_backlog),
        "jsonl": rel(args.jsonl),
        "ledger_rows": len(status_rows),
        "validated_ledger_rows": len(status_rows) - len(invalid_rows),
        "invalid_ledger_rows": len(invalid_rows),
        "open_blocked_ledger_rows": sum(1 for row in status_rows if row["ledger_status"] == "operator_work_open_blocked"),
        "ready_for_local_operator_work_rows": sum(1 for row in status_rows if row["ready_for_local_operator_work"]),
        "completion_ready_items": sum(1 for row in status_rows if row["completion_ready"]),
        "requires_human_input_items": sum(1 for row in status_rows if row["requires_human_input"]),
        "linked_human_backlog_rows": sum(1 for row in status_rows if row.get("human_backlog_id")),
        "unlinked_human_backlog_rows": sum(1 for row in status_rows if not row.get("human_backlog_id")),
        "total_backlog_missing_rows": sum(row.get("backlog_missing_rows") or 0 for row in status_rows),
        "invalid_ledger_items": [
            {
                "ledger_id": row["ledger_id"],
                "action_id": row["action_id"],
                "failed_checks": row["failed_checks"],
            }
            for row in invalid_rows
        ],
        "policy": "This validator confirms local operator work ledger semantics only. It does not create reviewed decisions, grant approvals, unlock claims, approve customer delivery, authorize deployment, sync files, or restart servers.",
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "ledger_rows": report["ledger_rows"],
        "validated_ledger_rows": report["validated_ledger_rows"],
        "invalid_ledger_rows": report["invalid_ledger_rows"],
        "completion_ready_items": report["completion_ready_items"],
        "output": str(args.report),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
