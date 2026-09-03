#!/usr/bin/env python3
"""Validate local multi-agent launch board semantics."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
LAUNCH_BOARD = AI_ROOT / "datasets" / "governance" / "next_unlock_multi_agent_launch_board.jsonl"
REMEDIATION_QUEUE = AI_ROOT / "datasets" / "governance" / "next_unlock_remediation_queue.jsonl"
REPORT_OUT = AI_ROOT / "reports" / "next_unlock_multi_agent_launch_validation_report.json"
JSONL_OUT = AI_ROOT / "datasets" / "governance" / "next_unlock_multi_agent_launch_status.jsonl"


REQUIRED_POLICY_TERMS = [
    "does not mean completed",
    "reviewed",
    "approved",
    "deployed",
    "synced",
    "customer-ready",
    "claim-ready",
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


def exists(rel_path: str | None) -> bool:
    return bool(rel_path) and (AI_ROOT / rel_path).exists()


def by_remediation(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {str(row.get("remediation_id")): row for row in rows if row.get("remediation_id")}


def check(name: str, passed: bool, observed: Any = None, expected: Any = None) -> dict[str, Any]:
    row = {"name": name, "passed": bool(passed)}
    if observed is not None:
        row["observed"] = observed
    if expected is not None:
        row["expected"] = expected
    return row


def status_from_checks(checks: list[dict[str, Any]]) -> str:
    return "launch_validated_blocked" if checks and all(item["passed"] for item in checks) else "launch_invalid"


def item_checks(row: dict[str, Any], queue_row: dict[str, Any] | None, expected_order: int) -> list[dict[str, Any]]:
    policy = str(row.get("policy") or "")
    decision_input = row.get("decision_input")
    template = row.get("template")
    return [
        check("remediation queue row exists", queue_row is not None, row.get("remediation_id"), "existing remediation_id"),
        check("execution order is stable", row.get("execution_order") == expected_order, row.get("execution_order"), expected_order),
        check("ready-to-start item is marked started", bool(row.get("ready_to_start")) == bool(row.get("started")), {
            "ready_to_start": row.get("ready_to_start"),
            "started": row.get("started"),
        }, "started iff ready_to_start"),
        check("launch status remains started blocked", row.get("launch_status") == "local_agent_started_blocked", row.get("launch_status"), "local_agent_started_blocked"),
        check("completion-ready remains false", row.get("completion_ready") is False, row.get("completion_ready"), False),
        check("requires human input remains true", row.get("requires_human_input") is True, row.get("requires_human_input"), True),
        check("queue status remains open", row.get("queue_status") == "open", row.get("queue_status"), "open"),
        check("operator first-open artifact exists", exists(row.get("operator_open_first")), row.get("operator_open_first"), "existing local path"),
        check("decision input exists when present", not decision_input or exists(decision_input), decision_input, "existing local path or null"),
        check("template exists when present", not template or exists(template), template, "existing local path or null"),
        check("validator report exists", exists(row.get("validator_report")), row.get("validator_report"), "existing local path"),
        check("verify command is local safe pipeline", row.get("verify_command") == "python3 scripts/run_safe_training_pipeline.py", row.get("verify_command"), "python3 scripts/run_safe_training_pipeline.py"),
        check("policy blocks completion/approval/deployment meanings", all(term in policy for term in REQUIRED_POLICY_TERMS), policy, REQUIRED_POLICY_TERMS),
    ]


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate next-unlock local multi-agent launch board")
    parser.add_argument("--launch-board", type=Path, default=LAUNCH_BOARD)
    parser.add_argument("--remediation-queue", type=Path, default=REMEDIATION_QUEUE)
    parser.add_argument("--report", type=Path, default=REPORT_OUT)
    parser.add_argument("--jsonl", type=Path, default=JSONL_OUT)
    args = parser.parse_args()

    launch_rows = load_jsonl(args.launch_board)
    remediation_rows = load_jsonl(args.remediation_queue)
    queue_by_remediation = by_remediation(remediation_rows)

    status_rows = []
    for expected_order, row in enumerate(sorted(launch_rows, key=lambda item: item.get("execution_order") or 999), 1):
        queue_row = queue_by_remediation.get(str(row.get("remediation_id")))
        checks = item_checks(row, queue_row, expected_order)
        failed_checks = [item["name"] for item in checks if not item["passed"]]
        status = status_from_checks(checks)
        status_rows.append({
            "launch_id": row.get("launch_id"),
            "remediation_id": row.get("remediation_id"),
            "execution_order": row.get("execution_order"),
            "action_id": row.get("action_id"),
            "stage_id": row.get("stage_id"),
            "workstream": row.get("workstream"),
            "lane_id": row.get("lane_id"),
            "launch_status": row.get("launch_status"),
            "validation_status": status,
            "started": bool(row.get("started")),
            "ready_to_start": bool(row.get("ready_to_start")),
            "completion_ready": bool(row.get("completion_ready")),
            "requires_human_input": bool(row.get("requires_human_input")),
            "failed_checks": failed_checks,
            "checks": checks,
            "operator_open_first": row.get("operator_open_first"),
            "next_evidence_artifacts": row.get("next_evidence_artifacts") or [],
            "verify_command": row.get("verify_command"),
            "policy": "Launch validation only. Validated launch means locally assigned and still blocked; it is not completion, approval, deployment, customer delivery, or claim readiness.",
        })

    write_jsonl(args.jsonl, status_rows)
    invalid_rows = [row for row in status_rows if row["validation_status"] == "launch_invalid"]
    lane_counts = Counter(str(row.get("lane_id")) for row in status_rows)
    report = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "local_only": True,
        "online_deployment": False,
        "source_launch_board": rel(args.launch_board),
        "source_remediation_queue": rel(args.remediation_queue),
        "jsonl": rel(args.jsonl),
        "launch_rows": len(status_rows),
        "validated_launch_rows": len(status_rows) - len(invalid_rows),
        "invalid_launch_rows": len(invalid_rows),
        "started_items": sum(1 for row in status_rows if row["started"]),
        "completion_ready_items": sum(1 for row in status_rows if row["completion_ready"]),
        "requires_human_input_items": sum(1 for row in status_rows if row["requires_human_input"]),
        "local_agent_lanes": len(lane_counts),
        "lane_counts": dict(sorted(lane_counts.items())),
        "invalid_launch_items": [
            {
                "launch_id": row["launch_id"],
                "action_id": row["action_id"],
                "failed_checks": row["failed_checks"],
            }
            for row in invalid_rows
        ],
        "policy": "This validator confirms local launch-board semantics only. It does not create reviewed decisions, grant approvals, unlock claims, deploy online services, sync files, or restart servers.",
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "launch_rows": report["launch_rows"],
        "validated_launch_rows": report["validated_launch_rows"],
        "invalid_launch_rows": report["invalid_launch_rows"],
        "completion_ready_items": report["completion_ready_items"],
        "output": str(args.report),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
