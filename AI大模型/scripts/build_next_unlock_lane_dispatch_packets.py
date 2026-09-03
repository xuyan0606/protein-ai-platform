#!/usr/bin/env python3
"""Build local dispatch packets for next-unlock agent lanes."""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
LANE_STATUS = AI_ROOT / "datasets" / "governance" / "next_unlock_agent_lane_status.jsonl"
LAUNCH_STATUS = AI_ROOT / "datasets" / "governance" / "next_unlock_multi_agent_launch_status.jsonl"
REPORT_OUT = AI_ROOT / "reports" / "next_unlock_lane_dispatch_packet_report.json"
JSONL_OUT = AI_ROOT / "datasets" / "governance" / "next_unlock_lane_dispatch_packets.jsonl"


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


def dispatch_status(lane: dict[str, Any], launch_rows: list[dict[str, Any]], missing_paths: list[str]) -> str:
    if lane.get("lane_status") == "lane_invalid":
        return "dispatch_invalid"
    if missing_paths:
        return "dispatch_blocked_missing_local_materials"
    if any(row.get("completion_ready") for row in launch_rows):
        return "dispatch_contains_completion_ready_item"
    if lane.get("lane_status") == "lane_started_blocked":
        return "dispatch_ready_blocked"
    return "dispatch_not_ready"


def main() -> int:
    parser = argparse.ArgumentParser(description="Build next-unlock local lane dispatch packets")
    parser.add_argument("--lane-status", type=Path, default=LANE_STATUS)
    parser.add_argument("--launch-status", type=Path, default=LAUNCH_STATUS)
    parser.add_argument("--report", type=Path, default=REPORT_OUT)
    parser.add_argument("--jsonl", type=Path, default=JSONL_OUT)
    args = parser.parse_args()

    lane_rows = load_jsonl(args.lane_status)
    launch_rows = load_jsonl(args.launch_status)
    launch_by_lane: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in launch_rows:
        launch_by_lane[str(row.get("lane_id") or "unassigned_lane")].append(row)

    packets = []
    for lane in sorted(lane_rows, key=lambda row: str(row.get("lane_id"))):
        lane_id = str(lane.get("lane_id"))
        lane_launches = sorted(
            launch_by_lane.get(lane_id, []),
            key=lambda row: (row.get("execution_order") or 999, str(row.get("launch_id"))),
        )
        referenced_paths = [
            *(lane.get("operator_open_first") or []),
            *(lane.get("next_evidence_artifacts") or []),
        ]
        missing_paths = sorted({path for path in referenced_paths if not path_exists(path)})
        action_sequence = [
            {
                "execution_order": row.get("execution_order"),
                "action_id": row.get("action_id"),
                "stage_id": row.get("stage_id"),
                "workstream": row.get("workstream"),
                "launch_status": row.get("launch_status"),
                "validation_status": row.get("validation_status"),
                "operator_open_first": row.get("operator_open_first"),
                "next_evidence_artifacts": row.get("next_evidence_artifacts") or [],
                "failed_checks": row.get("failed_checks") or [],
                "verify_command": row.get("verify_command"),
            }
            for row in lane_launches
        ]
        status = dispatch_status(lane, lane_launches, missing_paths)
        packets.append({
            "dispatch_packet_id": f"{lane_id}-NEXT-UNLOCK-DISPATCH",
            "lane_id": lane_id,
            "dispatch_status": status,
            "lane_status": lane.get("lane_status"),
            "launch_items": len(lane_launches),
            "validated_launch_items": sum(1 for row in lane_launches if row.get("validation_status") == "launch_validated_blocked"),
            "invalid_launch_items": sum(1 for row in lane_launches if row.get("validation_status") == "launch_invalid"),
            "completion_ready_items": sum(1 for row in lane_launches if row.get("completion_ready")),
            "requires_human_input_items": sum(1 for row in lane_launches if row.get("requires_human_input")),
            "missing_local_materials": missing_paths,
            "operator_open_first": lane.get("operator_open_first") or [],
            "next_evidence_artifacts": lane.get("next_evidence_artifacts") or [],
            "action_sequence": action_sequence,
            "verify_command": "python3 scripts/run_safe_training_pipeline.py",
            "dispatch_scope": "local_file_coordination_only",
            "policy": "Dispatch packet readiness means local materials are grouped for work. It does not mean completion, review, approval, deployment, sync, customer delivery, or claim readiness.",
        })

    write_jsonl(args.jsonl, packets)
    ready_blocked_packets = [row for row in packets if row["dispatch_status"] == "dispatch_ready_blocked"]
    invalid_packets = [row for row in packets if row["dispatch_status"] == "dispatch_invalid"]
    missing_material_packets = [
        row for row in packets if row["dispatch_status"] == "dispatch_blocked_missing_local_materials"
    ]
    report = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "local_only": True,
        "online_deployment": False,
        "source_lane_status": rel(args.lane_status),
        "source_launch_status": rel(args.launch_status),
        "jsonl": rel(args.jsonl),
        "dispatch_packets": len(packets),
        "dispatch_ready_blocked_packets": len(ready_blocked_packets),
        "invalid_dispatch_packets": len(invalid_packets),
        "dispatch_packets_missing_local_materials": len(missing_material_packets),
        "total_launch_items": sum(row["launch_items"] for row in packets),
        "validated_launch_items": sum(row["validated_launch_items"] for row in packets),
        "invalid_launch_items": sum(row["invalid_launch_items"] for row in packets),
        "completion_ready_items": sum(row["completion_ready_items"] for row in packets),
        "requires_human_input_items": sum(row["requires_human_input_items"] for row in packets),
        "dispatch_status_counts": {
            status: sum(1 for row in packets if row["dispatch_status"] == status)
            for status in sorted({row["dispatch_status"] for row in packets})
        },
        "packet_ids": [row["dispatch_packet_id"] for row in packets],
        "policy": "This report groups local lane dispatch packets only. It does not create reviewed decisions, grant approvals, unlock claims, deploy online services, sync files, or restart servers.",
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "dispatch_packets": report["dispatch_packets"],
        "dispatch_ready_blocked_packets": report["dispatch_ready_blocked_packets"],
        "invalid_dispatch_packets": report["invalid_dispatch_packets"],
        "completion_ready_items": report["completion_ready_items"],
        "output": str(args.report),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
