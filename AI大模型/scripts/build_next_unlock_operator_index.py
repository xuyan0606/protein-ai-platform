#!/usr/bin/env python3
"""Build an operator navigation index for next-unlock actions."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
COMPLETION_STATUS = AI_ROOT / "datasets" / "governance" / "next_unlock_completion_status.jsonl"
START_PACKETS = AI_ROOT / "datasets" / "governance" / "next_unlock_start_packets.jsonl"
NEXT_UNLOCK_PLAN = AI_ROOT / "datasets" / "governance" / "next_unlock_actions.jsonl"
VALIDATION_REPORT = AI_ROOT / "reports" / "next_unlock_execution_validation_report.json"
REPORT_OUT = AI_ROOT / "reports" / "next_unlock_operator_index.json"
JSONL_OUT = AI_ROOT / "datasets" / "governance" / "next_unlock_operator_index.jsonl"


ACTION_HINTS = {
    "P43-A001": {
        "operator_open_first": "datasets/curation/numbering_review_packets/",
        "template": "datasets/curation/numbering_curation_decisions.template.jsonl",
        "completion_condition": ">= 75 valid reviewed numbering decisions, strict supervised rows >= 100, and safe entrypoint failures == 0",
    },
    "P43-A002": {
        "operator_open_first": "datasets/curation/structure_chain_review_packets/",
        "template": "datasets/curation/structure_chain_mapping_decisions.template.jsonl",
        "completion_condition": ">= 25 reviewed chain mappings, invalid rows == 0, and >= 25 usable coordinate mappings",
    },
    "P43-A003": {
        "operator_open_first": "datasets/curation/domain_interpro_review_packets/",
        "template": "datasets/curation/domain_interval_decisions.template.jsonl",
        "completion_condition": "domain unresolved rows reduced by 75, decision invalid rows == 0, and usable domain rows remain present",
    },
    "P43-A004": {
        "operator_open_first": "reports/msa_conservation_manifest.json",
        "template": "config/msa_runtime.local.example.json",
        "completion_condition": "MSA runtime ready or trusted cache validation ready, with zero MSA cache manifest errors",
    },
    "P43-A005": {
        "operator_open_first": "datasets/feedback/source_review_packets/",
        "template": "datasets/feedback/experiment_feedback.template.jsonl",
        "completion_condition": "feedback training eligible rows > 0 and invalid rows == 0",
    },
    "P43-A006": {
        "operator_open_first": "datasets/feedback/plate_review_packets/feedback_plate_review_priority_001.jsonl",
        "template": "datasets/feedback/experiment_feedback_plate.template.jsonl",
        "completion_condition": "plate feedback training eligible rows > 0 and invalid rows == 0",
    },
    "P43-A007": {
        "operator_open_first": "datasets/governance/external_license_review_packets.jsonl",
        "template": "datasets/governance/external_license_review_decisions.template.jsonl",
        "completion_condition": "all license packet items decided and license validator ready for customer delivery",
    },
    "P43-A008": {
        "operator_open_first": "datasets/governance/biosecurity_screening_drafts.jsonl",
        "template": "datasets/governance/biosecurity_screening_decisions.template.jsonl",
        "completion_condition": "all biosecurity drafts decided and ready_for_ordering is true",
    },
    "P43-A009": {
        "operator_open_first": "datasets/curation/sequence_ip_review_packets/",
        "template": "datasets/governance/sequence_ip_fto_decisions.template.jsonl",
        "completion_condition": "all delivery candidates decided and IP/FTO validator ready for customer delivery",
    },
    "P43-A010": {
        "operator_open_first": "reports/workstream_acceptance_gates.json",
        "template": "datasets/governance/workstream_acceptance_decisions.template.jsonl",
        "completion_condition": "all workstreams human accepted",
    },
    "P43-A011": {
        "operator_open_first": "datasets/governance/operator_review_action_queue.jsonl",
        "template": "datasets/governance/operator_review_action_decisions.template.jsonl",
        "completion_condition": "all operator actions completed with evidence artifacts and validation reports",
    },
    "P43-A012": {
        "operator_open_first": "reports/claim_readiness_matrix.json",
        "template": None,
        "completion_condition": "claim matrix blocked claims == 0 for the requested claim scope",
    },
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


def by_action(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {str(row.get("action_id")): row for row in rows if row.get("action_id")}


def main() -> int:
    parser = argparse.ArgumentParser(description="Build next-unlock operator index")
    parser.add_argument("--completion-status", type=Path, default=COMPLETION_STATUS)
    parser.add_argument("--start-packets", type=Path, default=START_PACKETS)
    parser.add_argument("--plan", type=Path, default=NEXT_UNLOCK_PLAN)
    parser.add_argument("--validation-report", type=Path, default=VALIDATION_REPORT)
    parser.add_argument("--report", type=Path, default=REPORT_OUT)
    parser.add_argument("--jsonl", type=Path, default=JSONL_OUT)
    args = parser.parse_args()

    status_by_action = by_action(load_jsonl(args.completion_status))
    start_by_action = by_action(load_jsonl(args.start_packets))
    plan_by_action = by_action(load_jsonl(args.plan))
    validation = load_json(args.validation_report)

    action_ids = sorted(set(plan_by_action) | set(start_by_action) | set(status_by_action))
    rows = []
    for action_id in action_ids:
        plan = plan_by_action.get(action_id, {})
        start = start_by_action.get(action_id, {})
        status = status_by_action.get(action_id, {})
        hints = ACTION_HINTS.get(action_id, {})
        operator_open_first = hints.get("operator_open_first") or start.get("source_artifact") or plan.get("source_artifact")
        decision_input = status.get("decision_input") if "decision_input" in status else start.get("decision_input", plan.get("decision_input"))
        template = hints.get("template")
        validator_report = status.get("validator_report") or start.get("validator_report") or plan.get("validator_report")
        completion_ready = bool(status.get("completion_ready"))
        failed_checks = status.get("failed_checks") or []
        row = {
            "action_id": action_id,
            "stage_id": status.get("stage_id") or start.get("stage_id") or plan.get("stage_id"),
            "stage_order": status.get("stage_order") or start.get("stage_order"),
            "workstream": status.get("workstream") or start.get("workstream") or plan.get("workstream"),
            "priority": status.get("priority") or start.get("priority") or plan.get("priority"),
            "assigned_role": start.get("assigned_role") or status.get("assigned_role"),
            "action_type": start.get("action_type") or plan.get("action_type"),
            "status": status.get("status") or start.get("status") or "not_started",
            "started": bool(start.get("started") or status.get("started")),
            "completion_ready": completion_ready,
            "failed_checks": failed_checks,
            "operator_open_first": operator_open_first,
            "operator_open_first_exists": exists(operator_open_first),
            "decision_input": decision_input,
            "decision_input_exists": exists(decision_input),
            "template": template,
            "template_exists": exists(template),
            "validator_report": validator_report,
            "validator_report_exists": exists(validator_report),
            "target_rows": start.get("target_rows") if start.get("target_rows") is not None else plan.get("target_rows"),
            "verify_command": start.get("next_local_command") or "python3 scripts/run_safe_training_pipeline.py",
            "acceptance_check": start.get("acceptance_check") or plan.get("acceptance_check"),
            "completion_condition": hints.get("completion_condition") or start.get("acceptance_check") or plan.get("acceptance_check"),
            "operator_sequence": [
                item
                for item in [operator_open_first, decision_input, template, validator_report, "reports/next_unlock_execution_validation_report.json"]
                if item
            ],
            "policy": "Index only. It does not create reviewed decisions, approvals, capability unlocks, downloads, deployments, syncs, or server restarts.",
        }
        rows.append(row)

    rows.sort(key=lambda row: (row.get("stage_order") or 999, str(row.get("priority") or ""), row["action_id"]))
    write_jsonl(args.jsonl, rows)

    open_rows = [row for row in rows if not row["completion_ready"]]
    ready_rows = [row for row in rows if row["completion_ready"]]
    report = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "local_only": True,
        "source_completion_status": rel(args.completion_status),
        "source_start_packets": rel(args.start_packets),
        "source_plan": rel(args.plan),
        "source_validation_report": rel(args.validation_report),
        "jsonl": rel(args.jsonl),
        "total_actions": len(rows),
        "started_actions": sum(1 for row in rows if row["started"]),
        "open_items": len(open_rows),
        "completion_ready_items": len(ready_rows),
        "validation_completion_ready_actions": validation.get("completion_ready_actions"),
        "validation_blocked_actions": validation.get("blocked_actions"),
        "missing_operator_open_first": [row["action_id"] for row in rows if not row["operator_open_first_exists"]],
        "missing_decision_inputs": [row["action_id"] for row in rows if row["decision_input"] and not row["decision_input_exists"]],
        "missing_templates": [row["action_id"] for row in rows if row["template"] and not row["template_exists"]],
        "missing_validator_reports": [row["action_id"] for row in rows if row["validator_report"] and not row["validator_report_exists"]],
        "top_open_items": [
            {
                "action_id": row["action_id"],
                "workstream": row["workstream"],
                "operator_open_first": row["operator_open_first"],
                "decision_input": row["decision_input"],
                "failed_checks": row["failed_checks"],
            }
            for row in open_rows[:12]
        ],
        "policy": "This operator index is a local navigation artifact only; it does not write reviewed decisions, grant approvals, unlock claims, download tools, deploy services, sync files, or restart servers.",
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "total_actions": report["total_actions"],
        "open_items": report["open_items"],
        "completion_ready_items": report["completion_ready_items"],
        "output": str(args.report),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
