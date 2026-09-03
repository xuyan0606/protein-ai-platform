#!/usr/bin/env python3
"""Start all next-unlock actions as fail-closed local work packets."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
PLAN = AI_ROOT / "reports" / "next_unlock_plan.json"
ACTIONS = AI_ROOT / "datasets" / "governance" / "next_unlock_actions.jsonl"
REPORT_OUT = AI_ROOT / "reports" / "next_unlock_execution_board.json"
PACKETS_OUT = AI_ROOT / "datasets" / "governance" / "next_unlock_start_packets.jsonl"


ROLE_BY_WORKSTREAM = {
    "numbering_curation": "sequence_numbering_reviewer",
    "structure_chain_mapping": "structure_mapping_reviewer",
    "domain_interval_occurrence_selection": "domain_annotation_reviewer",
    "msa_conservation": "msa_runtime_operator",
    "experiment_feedback_source_review": "experiment_feedback_curator",
    "plate_feedback_intake": "assay_plate_data_curator",
    "external_license_review": "legal_license_reviewer",
    "biosecurity_screening": "biosecurity_reviewer",
    "sequence_ip_fto": "ip_fto_reviewer",
    "workstream_acceptance": "workstream_acceptance_reviewer",
    "operator_review_actions": "operator_reviewer",
    "model_claim": "release_claim_reviewer",
}


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def rel(path: str | None) -> str | None:
    if not path:
        return None
    value = Path(path)
    try:
        return str(value.relative_to(AI_ROOT)) if value.is_absolute() else str(value)
    except ValueError:
        return str(value)


def exists(path: str | None) -> bool:
    if path is None:
        return True
    value = Path(path)
    full = value if value.is_absolute() else AI_ROOT / value
    return full.exists()


def packet(action: dict[str, Any], stage_lookup: dict[str, dict[str, Any]]) -> dict[str, Any]:
    stage = stage_lookup.get(str(action.get("stage_id")), {})
    source = rel(action.get("source_artifact"))
    decision_input = rel(action.get("decision_input"))
    validator = rel(action.get("validator_report"))
    source_ready = exists(source)
    decision_input_ready = exists(decision_input)
    validator_ready = exists(validator)
    start_blockers = []
    if not source_ready:
        start_blockers.append("source artifact missing")
    if not decision_input_ready:
        start_blockers.append("decision input missing")
    if not validator_ready:
        start_blockers.append("validator report missing")
    upstream_blockers = list(stage.get("blockers") or [])
    started = not start_blockers
    return {
        "packet_id": f"{action.get('action_id')}-START",
        "action_id": action.get("action_id"),
        "stage_id": action.get("stage_id"),
        "stage_order": stage.get("order"),
        "workstream": action.get("workstream"),
        "priority": action.get("priority"),
        "assigned_role": ROLE_BY_WORKSTREAM.get(str(action.get("workstream")), "human_reviewer"),
        "action_type": action.get("action_type"),
        "target_rows": action.get("target_rows"),
        "source_artifact": source,
        "source_artifact_exists": source_ready,
        "decision_input": decision_input,
        "decision_input_exists": decision_input_ready,
        "validator_report": validator,
        "validator_report_exists": validator_ready,
        "started": started,
        "status": "started_blocked" if started else "blocked_missing_artifact",
        "completion_ready": False,
        "human_review_required": bool(action.get("human_review_required", True)),
        "acceptance_check": action.get("acceptance_check"),
        "start_blockers": start_blockers,
        "upstream_blockers": upstream_blockers,
        "next_local_command": "python3 scripts/run_safe_training_pipeline.py",
        "policy": "This start packet opens local work only; it is not a reviewed decision, approval, or capability unlock.",
    }


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Build next unlock execution board")
    parser.add_argument("--plan", type=Path, default=PLAN)
    parser.add_argument("--actions", type=Path, default=ACTIONS)
    parser.add_argument("--report", type=Path, default=REPORT_OUT)
    parser.add_argument("--packets", type=Path, default=PACKETS_OUT)
    args = parser.parse_args()

    plan = load_json(args.plan)
    actions = load_jsonl(args.actions)
    stage_lookup = {
        str(stage.get("stage_id")): stage
        for stage in plan.get("stages", [])
        if isinstance(stage, dict) and stage.get("stage_id")
    }
    packets = [packet(action, stage_lookup) for action in actions]
    write_jsonl(args.packets, packets)

    stage_rows = []
    for stage_id, stage in stage_lookup.items():
        stage_packets = [item for item in packets if item.get("stage_id") == stage_id]
        started = sum(1 for item in stage_packets if item.get("started"))
        missing = sum(1 for item in stage_packets if not item.get("started"))
        stage_rows.append({
            "stage_id": stage_id,
            "order": stage.get("order"),
            "title": stage.get("title"),
            "plan_status": stage.get("status"),
            "action_packets": len(stage_packets),
            "started_packets": started,
            "missing_artifact_packets": missing,
            "completion_ready": False,
            "status": "started_blocked" if missing == 0 else "blocked_missing_artifact",
            "upstream_blockers": stage.get("blockers") or [],
        })
    stage_rows.sort(key=lambda row: row.get("order") or 0)

    not_started = [item for item in packets if not item.get("started")]
    report = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "local_only": True,
        "plan": rel(str(args.plan)),
        "actions": rel(str(args.actions)),
        "packets": rel(str(args.packets)),
        "total_actions": len(actions),
        "started_actions": len(packets) - len(not_started),
        "not_started_actions": len(not_started),
        "completion_ready_actions": 0,
        "stage_count": len(stage_rows),
        "started_stage_count": sum(1 for item in stage_rows if item.get("status") == "started_blocked"),
        "completion_ready_stage_count": 0,
        "not_started": [
            {
                "action_id": item.get("action_id"),
                "workstream": item.get("workstream"),
                "start_blockers": item.get("start_blockers"),
            }
            for item in not_started
        ],
        "stages": stage_rows,
        "policy": "All actions are local work starts only. Human/legal/biosecurity/operator decisions must still be written to their reviewed decision inputs and pass validators before any unlock is ready.",
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "started_actions": report["started_actions"],
        "not_started_actions": report["not_started_actions"],
        "completion_ready_actions": report["completion_ready_actions"],
        "output": str(args.report),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
