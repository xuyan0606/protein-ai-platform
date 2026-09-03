#!/usr/bin/env python3
"""Validate local next-unlock lane dispatch packets."""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
DISPATCH_PACKETS = AI_ROOT / "datasets" / "governance" / "next_unlock_lane_dispatch_packets.jsonl"
LANE_STATUS = AI_ROOT / "datasets" / "governance" / "next_unlock_agent_lane_status.jsonl"
LAUNCH_STATUS = AI_ROOT / "datasets" / "governance" / "next_unlock_multi_agent_launch_status.jsonl"
REPORT_OUT = AI_ROOT / "reports" / "next_unlock_lane_dispatch_validation_report.json"
JSONL_OUT = AI_ROOT / "datasets" / "governance" / "next_unlock_lane_dispatch_status.jsonl"


REQUIRED_POLICY_TERMS = [
    "does not mean completion",
    "review",
    "approval",
    "deployment",
    "sync",
    "customer delivery",
    "claim readiness",
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


def by_lane(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {str(row.get("lane_id")): row for row in rows if row.get("lane_id")}


def launch_by_lane(rows: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[str(row.get("lane_id") or "unassigned_lane")].append(row)
    return grouped


def validate_packet(
    packet: dict[str, Any],
    lane_row: dict[str, Any] | None,
    launch_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    lane_id = str(packet.get("lane_id"))
    action_sequence = packet.get("action_sequence") or []
    action_orders = [row.get("execution_order") for row in action_sequence]
    expected_actions = [row.get("action_id") for row in sorted(launch_rows, key=lambda row: row.get("execution_order") or 999)]
    observed_actions = [row.get("action_id") for row in action_sequence]
    referenced_paths = [
        *(packet.get("operator_open_first") or []),
        *(packet.get("next_evidence_artifacts") or []),
    ]
    missing_paths = sorted({path for path in referenced_paths if not path_exists(path)})
    policy = str(packet.get("policy") or "")
    return [
        check("lane status row exists", lane_row is not None, lane_id, "existing lane_id"),
        check("dispatch packet id is stable", packet.get("dispatch_packet_id") == f"{lane_id}-NEXT-UNLOCK-DISPATCH", packet.get("dispatch_packet_id"), f"{lane_id}-NEXT-UNLOCK-DISPATCH"),
        check("dispatch status remains ready blocked", packet.get("dispatch_status") == "dispatch_ready_blocked", packet.get("dispatch_status"), "dispatch_ready_blocked"),
        check("lane status remains started blocked", packet.get("lane_status") == "lane_started_blocked", packet.get("lane_status"), "lane_started_blocked"),
        check("dispatch scope is local only", packet.get("dispatch_scope") == "local_file_coordination_only", packet.get("dispatch_scope"), "local_file_coordination_only"),
        check("launch item count matches lane", packet.get("launch_items") == len(launch_rows) == len(action_sequence), {"packet": packet.get("launch_items"), "launch_rows": len(launch_rows), "action_sequence": len(action_sequence)}, "all equal"),
        check("action sequence matches launch lane", observed_actions == expected_actions, observed_actions, expected_actions),
        check("action sequence order is stable", action_orders == sorted(action_orders), action_orders, "sorted execution_order"),
        check("all launch items validated blocked", packet.get("validated_launch_items") == len(launch_rows) and all(row.get("validation_status") == "launch_validated_blocked" for row in launch_rows), packet.get("validated_launch_items"), len(launch_rows)),
        check("invalid launch items remain zero", packet.get("invalid_launch_items") == 0, packet.get("invalid_launch_items"), 0),
        check("completion-ready remains zero", packet.get("completion_ready_items") == 0 and not any(row.get("completion_ready") for row in launch_rows), packet.get("completion_ready_items"), 0),
        check("requires human input remains true for all launch items", packet.get("requires_human_input_items") == len(launch_rows) and all(row.get("requires_human_input") for row in launch_rows), packet.get("requires_human_input_items"), len(launch_rows)),
        check("missing local materials remains empty", not packet.get("missing_local_materials") and not missing_paths, {"reported": packet.get("missing_local_materials"), "observed": missing_paths}, []),
        check("referenced local materials exist", not missing_paths, missing_paths, []),
        check("verify command is local safe pipeline", packet.get("verify_command") == "python3 scripts/run_safe_training_pipeline.py", packet.get("verify_command"), "python3 scripts/run_safe_training_pipeline.py"),
        check("policy blocks completion/approval/deployment meanings", all(term in policy for term in REQUIRED_POLICY_TERMS), policy, REQUIRED_POLICY_TERMS),
    ]


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate next-unlock lane dispatch packets")
    parser.add_argument("--dispatch-packets", type=Path, default=DISPATCH_PACKETS)
    parser.add_argument("--lane-status", type=Path, default=LANE_STATUS)
    parser.add_argument("--launch-status", type=Path, default=LAUNCH_STATUS)
    parser.add_argument("--report", type=Path, default=REPORT_OUT)
    parser.add_argument("--jsonl", type=Path, default=JSONL_OUT)
    args = parser.parse_args()

    packets = load_jsonl(args.dispatch_packets)
    lane_rows = by_lane(load_jsonl(args.lane_status))
    launches_by_lane = launch_by_lane(load_jsonl(args.launch_status))

    status_rows = []
    for packet in sorted(packets, key=lambda row: str(row.get("lane_id"))):
        lane_id = str(packet.get("lane_id"))
        checks = validate_packet(packet, lane_rows.get(lane_id), launches_by_lane.get(lane_id, []))
        failed_checks = [item["name"] for item in checks if not item["passed"]]
        status_rows.append({
            "dispatch_packet_id": packet.get("dispatch_packet_id"),
            "lane_id": lane_id,
            "dispatch_status": packet.get("dispatch_status"),
            "validation_status": "dispatch_validated_blocked" if not failed_checks else "dispatch_invalid",
            "launch_items": packet.get("launch_items"),
            "validated_launch_items": packet.get("validated_launch_items"),
            "invalid_launch_items": packet.get("invalid_launch_items"),
            "completion_ready_items": packet.get("completion_ready_items"),
            "requires_human_input_items": packet.get("requires_human_input_items"),
            "missing_local_materials": packet.get("missing_local_materials") or [],
            "failed_checks": failed_checks,
            "checks": checks,
            "verify_command": packet.get("verify_command"),
            "policy": "Dispatch validation only. Validated dispatch means local packet materials are grouped and still blocked; it is not completion, approval, deployment, customer delivery, or claim readiness.",
        })

    write_jsonl(args.jsonl, status_rows)
    invalid_rows = [row for row in status_rows if row["validation_status"] == "dispatch_invalid"]
    report = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "local_only": True,
        "online_deployment": False,
        "source_dispatch_packets": rel(args.dispatch_packets),
        "source_lane_status": rel(args.lane_status),
        "source_launch_status": rel(args.launch_status),
        "jsonl": rel(args.jsonl),
        "dispatch_packets": len(status_rows),
        "validated_dispatch_packets": len(status_rows) - len(invalid_rows),
        "invalid_dispatch_packets": len(invalid_rows),
        "completion_ready_items": sum(row["completion_ready_items"] or 0 for row in status_rows),
        "requires_human_input_items": sum(row["requires_human_input_items"] or 0 for row in status_rows),
        "missing_local_material_packets": sum(1 for row in status_rows if row["missing_local_materials"]),
        "invalid_dispatch_items": [
            {
                "dispatch_packet_id": row["dispatch_packet_id"],
                "lane_id": row["lane_id"],
                "failed_checks": row["failed_checks"],
            }
            for row in invalid_rows
        ],
        "policy": "This validator confirms local dispatch packet semantics only. It does not create reviewed decisions, grant approvals, unlock claims, deploy online services, sync files, or restart servers.",
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "dispatch_packets": report["dispatch_packets"],
        "validated_dispatch_packets": report["validated_dispatch_packets"],
        "invalid_dispatch_packets": report["invalid_dispatch_packets"],
        "completion_ready_items": report["completion_ready_items"],
        "output": str(args.report),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
