#!/usr/bin/env python3
"""Build lane-level status for local next-unlock agents."""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
LAUNCH_STATUS = AI_ROOT / "datasets" / "governance" / "next_unlock_multi_agent_launch_status.jsonl"
REPORT_OUT = AI_ROOT / "reports" / "next_unlock_agent_lane_status_report.json"
JSONL_OUT = AI_ROOT / "datasets" / "governance" / "next_unlock_agent_lane_status.jsonl"


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


def lane_status(rows: list[dict[str, Any]]) -> str:
    if any(row.get("validation_status") == "launch_invalid" for row in rows):
        return "lane_invalid"
    if any(row.get("completion_ready") for row in rows):
        return "lane_has_completion_ready_items"
    if rows and all(row.get("validation_status") == "launch_validated_blocked" for row in rows):
        return "lane_started_blocked"
    return "lane_not_ready"


def main() -> int:
    parser = argparse.ArgumentParser(description="Build next-unlock local agent lane status")
    parser.add_argument("--launch-status", type=Path, default=LAUNCH_STATUS)
    parser.add_argument("--report", type=Path, default=REPORT_OUT)
    parser.add_argument("--jsonl", type=Path, default=JSONL_OUT)
    args = parser.parse_args()

    launch_rows = load_jsonl(args.launch_status)
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in launch_rows:
        grouped[str(row.get("lane_id") or "unassigned_lane")].append(row)

    lane_rows = []
    for lane_id, rows in sorted(grouped.items()):
        rows.sort(key=lambda row: (row.get("execution_order") or 999, str(row.get("launch_id"))))
        status = lane_status(rows)
        lane_rows.append({
            "lane_id": lane_id,
            "lane_status": status,
            "launch_items": len(rows),
            "validated_launch_items": sum(1 for row in rows if row.get("validation_status") == "launch_validated_blocked"),
            "invalid_launch_items": sum(1 for row in rows if row.get("validation_status") == "launch_invalid"),
            "started_items": sum(1 for row in rows if row.get("started")),
            "ready_to_start_items": sum(1 for row in rows if row.get("ready_to_start")),
            "completion_ready_items": sum(1 for row in rows if row.get("completion_ready")),
            "requires_human_input_items": sum(1 for row in rows if row.get("requires_human_input")),
            "action_ids": [row.get("action_id") for row in rows],
            "workstreams": [row.get("workstream") for row in rows],
            "operator_open_first": [row.get("operator_open_first") for row in rows if row.get("operator_open_first")],
            "next_evidence_artifacts": sorted({
                artifact
                for row in rows
                for artifact in (row.get("next_evidence_artifacts") or [])
            }),
            "verify_command": "python3 scripts/run_safe_training_pipeline.py",
            "policy": "Lane status is a local coordination view only. Started blocked lanes still require human inputs and do not mean completion, review, approval, deployment, customer delivery, or claim readiness.",
        })

    write_jsonl(args.jsonl, lane_rows)
    blocked_lanes = [row for row in lane_rows if row["lane_status"] == "lane_started_blocked"]
    invalid_lanes = [row for row in lane_rows if row["lane_status"] == "lane_invalid"]
    report = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "local_only": True,
        "online_deployment": False,
        "source_launch_status": rel(args.launch_status),
        "jsonl": rel(args.jsonl),
        "lane_rows": len(lane_rows),
        "started_blocked_lanes": len(blocked_lanes),
        "invalid_lanes": len(invalid_lanes),
        "lanes_with_completion_ready_items": sum(1 for row in lane_rows if row["completion_ready_items"]),
        "total_launch_items": sum(row["launch_items"] for row in lane_rows),
        "validated_launch_items": sum(row["validated_launch_items"] for row in lane_rows),
        "invalid_launch_items": sum(row["invalid_launch_items"] for row in lane_rows),
        "started_items": sum(row["started_items"] for row in lane_rows),
        "completion_ready_items": sum(row["completion_ready_items"] for row in lane_rows),
        "requires_human_input_items": sum(row["requires_human_input_items"] for row in lane_rows),
        "lane_order": [row["lane_id"] for row in lane_rows],
        "lane_status_counts": {
            status: sum(1 for row in lane_rows if row["lane_status"] == status)
            for status in sorted({row["lane_status"] for row in lane_rows})
        },
        "policy": "This report summarizes local agent-lane coordination only. It does not create reviewed decisions, grant approvals, unlock claims, deploy online services, sync files, or restart servers.",
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "lane_rows": report["lane_rows"],
        "started_blocked_lanes": report["started_blocked_lanes"],
        "invalid_lanes": report["invalid_lanes"],
        "completion_ready_items": report["completion_ready_items"],
        "output": str(args.report),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
