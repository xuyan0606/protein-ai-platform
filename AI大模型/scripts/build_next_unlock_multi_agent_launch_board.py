#!/usr/bin/env python3
"""Build a local multi-agent launch board for next-unlock remediation work."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
REMEDIATION_QUEUE = AI_ROOT / "datasets" / "governance" / "next_unlock_remediation_queue.jsonl"
REPORT_OUT = AI_ROOT / "reports" / "next_unlock_multi_agent_launch_board.json"
JSONL_OUT = AI_ROOT / "datasets" / "governance" / "next_unlock_multi_agent_launch_board.jsonl"


LANE_BY_WORKSTREAM = {
    "numbering_curation": ("sequence_data_agent", "Review numbering packets and record verified mapping inputs"),
    "structure_chain_mapping": ("structure_domain_agent", "Review structure chain packets and coordinate feature blockers"),
    "domain_interval_occurrence_selection": ("structure_domain_agent", "Resolve domain occurrence selection blockers"),
    "msa_conservation": ("msa_feedback_agent", "Configure local MSA runtime or validated conservation cache inputs"),
    "experiment_feedback_source_review": ("msa_feedback_agent", "Transcribe schema-valid experiment feedback inputs"),
    "plate_feedback_intake": ("msa_feedback_agent", "Transcribe schema-valid plate/well feedback inputs"),
    "external_license_review": ("governance_agent", "Prepare license review decision inputs for human/legal review"),
    "biosecurity_screening": ("governance_agent", "Prepare biosecurity screening decision inputs for human review"),
    "sequence_ip_fto": ("governance_agent", "Prepare sequence IP/FTO decision inputs for legal review"),
    "workstream_acceptance": ("acceptance_claim_agent", "Prepare workstream acceptance decision inputs"),
    "operator_review_actions": ("acceptance_claim_agent", "Prepare operator action completion evidence inputs"),
    "model_claim": ("acceptance_claim_agent", "Recheck claim matrix after upstream remediation is completed"),
}


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


def launch_status(row: dict[str, Any]) -> str:
    if row.get("ready_to_start"):
        return "local_agent_started_blocked"
    return "local_agent_not_started_missing_inputs"


def main() -> int:
    parser = argparse.ArgumentParser(description="Build next-unlock multi-agent launch board")
    parser.add_argument("--remediation-queue", type=Path, default=REMEDIATION_QUEUE)
    parser.add_argument("--report", type=Path, default=REPORT_OUT)
    parser.add_argument("--jsonl", type=Path, default=JSONL_OUT)
    args = parser.parse_args()

    queue = load_jsonl(args.remediation_queue)
    rows = []
    for item in queue:
        lane_id, lane_role = LANE_BY_WORKSTREAM.get(
            str(item.get("workstream")),
            ("general_remediation_agent", "Resolve local validator blockers"),
        )
        status = launch_status(item)
        rows.append({
            "launch_id": f"{item.get('action_id')}-LOCAL-AGENT-LAUNCH",
            "remediation_id": item.get("remediation_id"),
            "execution_order": item.get("execution_order"),
            "action_id": item.get("action_id"),
            "stage_id": item.get("stage_id"),
            "stage_order": item.get("stage_order"),
            "workstream": item.get("workstream"),
            "priority": item.get("priority"),
            "severity": item.get("severity"),
            "lane_id": lane_id,
            "lane_role": lane_role,
            "assigned_role": item.get("assigned_role"),
            "launch_status": status,
            "started": status == "local_agent_started_blocked",
            "ready_to_start": bool(item.get("ready_to_start")),
            "completion_ready": False,
            "requires_human_input": bool(item.get("requires_human_input")),
            "queue_status": item.get("queue_status"),
            "remediation_type": item.get("remediation_type"),
            "blocker_count": item.get("blocker_count"),
            "blocker_ids": item.get("blocker_ids") or [],
            "blocker_categories": item.get("blocker_categories") or [],
            "failed_checks": item.get("failed_checks") or [],
            "observed_expected": item.get("observed_expected") or [],
            "operator_open_first": item.get("operator_open_first"),
            "decision_input": item.get("decision_input"),
            "template": item.get("template"),
            "target_rows": item.get("target_rows"),
            "validator_report": item.get("validator_report"),
            "next_evidence_artifacts": item.get("next_evidence_artifacts") or [],
            "verify_command": item.get("verify_command") or "python3 scripts/run_safe_training_pipeline.py",
            "completion_condition": item.get("completion_condition"),
            "policy": "Local multi-agent launch record only. Started means assigned and ready to work locally; it does not mean completed, reviewed, approved, deployed, synced, customer-ready, or claim-ready.",
        })

    rows.sort(key=lambda row: (row.get("execution_order") or 999, row["launch_id"]))
    write_jsonl(args.jsonl, rows)

    lane_counts = Counter(str(row["lane_id"]) for row in rows)
    status_counts = Counter(str(row["launch_status"]) for row in rows)
    report = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "local_only": True,
        "online_deployment": False,
        "source_remediation_queue": rel(args.remediation_queue),
        "jsonl": rel(args.jsonl),
        "total_launch_items": len(rows),
        "launch_rows": len(rows),
        "started_items": sum(1 for row in rows if row["started"]),
        "not_started_items": sum(1 for row in rows if not row["started"]),
        "ready_to_launch_items": sum(1 for row in rows if row["ready_to_start"]),
        "blocked_launch_items": sum(1 for row in rows if not row["ready_to_start"]),
        "completion_ready_items": sum(1 for row in rows if row["completion_ready"]),
        "requires_human_input_items": sum(1 for row in rows if row["requires_human_input"]),
        "local_agent_lanes": len(lane_counts),
        "agent_count": len(lane_counts),
        "parallel_groups": len(lane_counts),
        "lane_counts": dict(sorted(lane_counts.items())),
        "status_counts": dict(sorted(status_counts.items())),
        "top_launch_items": [
            {
                "execution_order": row["execution_order"],
                "launch_id": row["launch_id"],
                "lane_id": row["lane_id"],
                "workstream": row["workstream"],
                "launch_status": row["launch_status"],
                "operator_open_first": row["operator_open_first"],
                "next_evidence_artifacts": row["next_evidence_artifacts"],
            }
            for row in rows[:12]
        ],
        "policy": "This launch board starts local work lanes only. It does not create reviewed decisions, grant approvals, unlock claims, download tools, deploy online services, sync files, or restart servers.",
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "total_launch_items": report["total_launch_items"],
        "started_items": report["started_items"],
        "ready_to_launch_items": report["ready_to_launch_items"],
        "completion_ready_items": report["completion_ready_items"],
        "output": str(args.report),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
