#!/usr/bin/env python3
"""Build action-level local checklist rows from validated dispatch packets."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
DISPATCH_PACKETS = AI_ROOT / "datasets" / "governance" / "next_unlock_lane_dispatch_packets.jsonl"
DISPATCH_STATUS = AI_ROOT / "datasets" / "governance" / "next_unlock_lane_dispatch_status.jsonl"
LAUNCH_BOARD = AI_ROOT / "datasets" / "governance" / "next_unlock_multi_agent_launch_board.jsonl"
REPORT_OUT = AI_ROOT / "reports" / "next_unlock_action_checklist_report.json"
JSONL_OUT = AI_ROOT / "datasets" / "governance" / "next_unlock_action_checklist.jsonl"


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


def by_action(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {str(row.get("action_id")): row for row in rows if row.get("action_id")}


def by_dispatch(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {str(row.get("dispatch_packet_id")): row for row in rows if row.get("dispatch_packet_id")}


def checklist_status(dispatch_status: str | None, launch: dict[str, Any]) -> str:
    if dispatch_status != "dispatch_validated_blocked":
        return "checklist_blocked_by_dispatch_validation"
    if launch.get("completion_ready"):
        return "checklist_contains_completion_ready_item"
    if not launch.get("requires_human_input"):
        return "checklist_invalid_missing_human_input_guard"
    return "checklist_open_blocked"


def main() -> int:
    parser = argparse.ArgumentParser(description="Build next-unlock action-level checklist")
    parser.add_argument("--dispatch-packets", type=Path, default=DISPATCH_PACKETS)
    parser.add_argument("--dispatch-status", type=Path, default=DISPATCH_STATUS)
    parser.add_argument("--launch-board", type=Path, default=LAUNCH_BOARD)
    parser.add_argument("--report", type=Path, default=REPORT_OUT)
    parser.add_argument("--jsonl", type=Path, default=JSONL_OUT)
    args = parser.parse_args()

    packets = load_jsonl(args.dispatch_packets)
    dispatch_status = by_dispatch(load_jsonl(args.dispatch_status))
    launch_by_action = by_action(load_jsonl(args.launch_board))

    checklist_rows = []
    for packet in sorted(packets, key=lambda row: str(row.get("lane_id"))):
        packet_id = str(packet.get("dispatch_packet_id"))
        packet_status = dispatch_status.get(packet_id, {})
        validation_status = packet_status.get("validation_status")
        for action in packet.get("action_sequence") or []:
            action_id = str(action.get("action_id"))
            launch = launch_by_action.get(action_id, {})
            operator_open_first = launch.get("operator_open_first") or action.get("operator_open_first")
            decision_input = launch.get("decision_input")
            template = launch.get("template")
            validator_report = launch.get("validator_report")
            referenced_paths = [
                operator_open_first,
                decision_input,
                template,
                validator_report,
                *(launch.get("next_evidence_artifacts") or action.get("next_evidence_artifacts") or []),
            ]
            missing_paths = sorted({path for path in referenced_paths if path and not path_exists(path)})
            status = checklist_status(validation_status, launch)
            if missing_paths:
                status = "checklist_blocked_missing_local_materials"
            checklist_rows.append({
                "checklist_id": f"{action_id}-LOCAL-ACTION-CHECKLIST",
                "dispatch_packet_id": packet_id,
                "lane_id": packet.get("lane_id"),
                "execution_order": action.get("execution_order"),
                "action_id": action_id,
                "stage_id": action.get("stage_id"),
                "workstream": action.get("workstream"),
                "checklist_status": status,
                "dispatch_validation_status": validation_status,
                "launch_status": action.get("launch_status"),
                "ready_for_local_operator": status == "checklist_open_blocked",
                "completion_ready": False,
                "requires_human_input": True,
                "operator_open_first": operator_open_first,
                "decision_input": decision_input,
                "template": template,
                "validator_report": validator_report,
                "next_evidence_artifacts": launch.get("next_evidence_artifacts") or action.get("next_evidence_artifacts") or [],
                "missing_local_materials": missing_paths,
                "checklist_steps": [
                    "open operator_open_first material",
                    "review source evidence locally",
                    "record human-reviewed input only when available",
                    "run listed validator or local safe pipeline after any human input is added",
                    "do not mark completion until downstream validator reports completion-ready",
                ],
                "verify_command": launch.get("verify_command") or action.get("verify_command") or "python3 scripts/run_safe_training_pipeline.py",
                "completion_condition": launch.get("completion_condition"),
                "policy": "Action checklist is a local operator guide only. It does not create reviewed decisions, grant approvals, unlock claims, approve customer delivery, authorize deployment, sync files, or restart servers.",
            })

    checklist_rows.sort(key=lambda row: (row.get("execution_order") or 999, row["checklist_id"]))
    write_jsonl(args.jsonl, checklist_rows)
    open_blocked_rows = [row for row in checklist_rows if row["checklist_status"] == "checklist_open_blocked"]
    invalid_rows = [row for row in checklist_rows if row["checklist_status"] != "checklist_open_blocked"]
    report = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "local_only": True,
        "online_deployment": False,
        "source_dispatch_packets": rel(args.dispatch_packets),
        "source_dispatch_status": rel(args.dispatch_status),
        "source_launch_board": rel(args.launch_board),
        "jsonl": rel(args.jsonl),
        "checklist_rows": len(checklist_rows),
        "open_blocked_checklist_rows": len(open_blocked_rows),
        "invalid_or_blocked_checklist_rows": len(invalid_rows),
        "ready_for_local_operator_rows": sum(1 for row in checklist_rows if row["ready_for_local_operator"]),
        "completion_ready_items": sum(1 for row in checklist_rows if row["completion_ready"]),
        "requires_human_input_items": sum(1 for row in checklist_rows if row["requires_human_input"]),
        "missing_local_material_rows": sum(1 for row in checklist_rows if row["missing_local_materials"]),
        "lane_counts": {
            lane_id: sum(1 for row in checklist_rows if row["lane_id"] == lane_id)
            for lane_id in sorted({str(row["lane_id"]) for row in checklist_rows})
        },
        "top_checklist_items": [
            {
                "execution_order": row["execution_order"],
                "checklist_id": row["checklist_id"],
                "lane_id": row["lane_id"],
                "workstream": row["workstream"],
                "operator_open_first": row["operator_open_first"],
                "decision_input": row["decision_input"],
                "validator_report": row["validator_report"],
            }
            for row in checklist_rows[:12]
        ],
        "policy": "This report is a local operator checklist only. It does not create reviewed decisions, grant approvals, unlock claims, approve customer delivery, authorize deployment, sync files, or restart servers.",
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "checklist_rows": report["checklist_rows"],
        "open_blocked_checklist_rows": report["open_blocked_checklist_rows"],
        "ready_for_local_operator_rows": report["ready_for_local_operator_rows"],
        "completion_ready_items": report["completion_ready_items"],
        "output": str(args.report),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
