#!/usr/bin/env python3
"""Build a fail-closed enzyme resource retrieval plan from action/tool contracts."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
ACTIONS = AI_ROOT / "datasets" / "governance" / "enzyme_action_space_registry.jsonl"
CONTRACTS = AI_ROOT / "datasets" / "governance" / "enzyme_tool_contracts.jsonl"
REPORT_OUT = AI_ROOT / "reports" / "enzyme_resource_retrieval_plan_report.json"
CHECKPOINT_OUT = AI_ROOT / "datasets" / "governance" / "enzyme_agent_state_checkpoints.jsonl"


DEFAULT_QUERY = "Plan an enzyme mutation analysis using KWB local evidence, safety guards, and available tool contracts."
FORBIDDEN_ACTION_IDS = {
    "act_ddg_proxy_or_physics",
}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def classify_action(action: dict[str, Any], contract: dict[str, Any]) -> str:
    action_id = str(action.get("action_id"))
    if action_id in FORBIDDEN_ACTION_IDS:
        return "forbidden_for_current_request"
    if action.get("writes_formal_decision") or action.get("category") in {"human_curation", "external_data", "benchmark"}:
        return "blocked_requires_human_decision"
    if contract.get("allowed_execution_mode") == "local_script" and action.get("risk_level") in {"medium", "critical"}:
        return "executable_after_user_confirmation"
    return "recommended_read_only"


def action_plan_row(action: dict[str, Any], contract: dict[str, Any], classification: str) -> dict[str, Any]:
    blocked_reason = None
    if classification == "blocked_requires_human_decision":
        blocked_reason = "human decision, license review, formal gate, or benchmark acceptance is required before execution"
    elif classification == "forbidden_for_current_request":
        blocked_reason = "external tool or physical/proxy ddG execution is outside this read-only retrieval planning request"
    elif classification == "executable_after_user_confirmation":
        blocked_reason = "local script may be executed only after explicit user confirmation in a later step"

    return {
        "action_id": action.get("action_id"),
        "title": action.get("title"),
        "category": action.get("category"),
        "risk_level": action.get("risk_level"),
        "classification": classification,
        "primary_contract_id": action.get("primary_contract_id"),
        "tool_name": contract.get("tool_name"),
        "allowed_execution_mode": contract.get("allowed_execution_mode"),
        "runtime_readiness": contract.get("runtime_readiness"),
        "license_status": contract.get("license_status"),
        "human_confirmation_required": bool(action.get("human_confirmation_required") or contract.get("human_confirmation_required")),
        "writes_formal_decision": bool(action.get("writes_formal_decision") or contract.get("can_write_formal_decision")),
        "writes_training_rows": bool(action.get("writes_training_rows") or contract.get("can_write_training_rows")),
        "safe_for_model_claim": False,
        "input_artifacts": action.get("input_artifacts") or [],
        "output_artifacts": action.get("output_artifacts") or [],
        "entrypoints": contract.get("entrypoints") or [],
        "blocked_reason": blocked_reason,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Build enzyme resource retrieval plan")
    parser.add_argument("--query", default=DEFAULT_QUERY)
    parser.add_argument("--actions", type=Path, default=ACTIONS)
    parser.add_argument("--contracts", type=Path, default=CONTRACTS)
    parser.add_argument("--report-output", type=Path, default=REPORT_OUT)
    parser.add_argument("--checkpoint-output", type=Path, default=CHECKPOINT_OUT)
    args = parser.parse_args()

    actions = load_jsonl(args.actions)
    contracts = {row.get("contract_id"): row for row in load_jsonl(args.contracts)}
    created_at = datetime.now(timezone.utc).isoformat()
    plan_id = "enzyme_resource_retrieval_plan_20260731_p167"

    categories: dict[str, list[dict[str, Any]]] = {
        "recommended_read_only": [],
        "executable_after_user_confirmation": [],
        "blocked_requires_human_decision": [],
        "forbidden_for_current_request": [],
    }
    plan_rows: list[dict[str, Any]] = []
    for action in actions:
        contract = contracts.get(action.get("primary_contract_id"), {})
        classification = classify_action(action, contract)
        row = action_plan_row(action, contract, classification)
        categories[classification].append(row)
        plan_rows.append(row)

    summary = {
        "action_rows": len(plan_rows),
        "recommended_read_only_rows": len(categories["recommended_read_only"]),
        "executable_after_user_confirmation_rows": len(categories["executable_after_user_confirmation"]),
        "blocked_requires_human_decision_rows": len(categories["blocked_requires_human_decision"]),
        "forbidden_for_current_request_rows": len(categories["forbidden_for_current_request"]),
        "writes_training_rows": sum(1 for row in plan_rows if row["writes_training_rows"]),
        "writes_formal_decision_rows": sum(1 for row in plan_rows if row["writes_formal_decision"]),
        "safe_for_model_claim_rows": sum(1 for row in plan_rows if row["safe_for_model_claim"]),
    }
    report = {
        "plan_id": plan_id,
        "created_at": created_at,
        "local_only": True,
        "request_class": "controlled_resource_retrieval_only",
        "input_query": args.query,
        "protocol": "contracts/enzyme_agent_execution_protocol.md",
        "schemas": [
            "schemas/enzyme_resource_retrieval_plan.schema.json",
            "schemas/enzyme_agent_state_checkpoint.schema.json",
        ],
        "categories": categories,
        "actions": plan_rows,
        "summary": summary,
        "safe_for_execution": False,
        "safe_for_training_import": False,
        "safe_for_model_claim": False,
        "release_ready": False,
        "policy": "This is a retrieval and planning artifact only. It does not execute tools or authorize formal decisions, training import, model claims, external downloads, MCP execution, or release.",
    }

    checkpoint = {
        "checkpoint_id": "enzyme_agent_checkpoint_20260731_p167_retrieval_plan",
        "created_at": created_at,
        "local_only": True,
        "plan_id": plan_id,
        "stage": "retrieval_plan_built",
        "selected_action_ids": [row["action_id"] for row in plan_rows],
        "selected_tool_contract_ids": sorted({row["primary_contract_id"] for row in plan_rows}),
        "blocked_action_ids": [row["action_id"] for row in categories["blocked_requires_human_decision"]],
        "forbidden_action_ids": [row["action_id"] for row in categories["forbidden_for_current_request"]],
        "executed_action_ids": [],
        "artifact_outputs": [str(args.report_output.relative_to(AI_ROOT))],
        "validator_outputs": ["reports/enzyme_resource_retrieval_plan_validation_report.json"],
        "claim_snapshot": {
            "safe_for_training_import": False,
            "safe_for_model_claim": False,
            "release_ready": False,
        },
        "policy": "Checkpoint records planning state only; no tool execution has occurred.",
    }

    args.report_output.parent.mkdir(parents=True, exist_ok=True)
    args.report_output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    write_jsonl(args.checkpoint_output, [checkpoint])
    print(json.dumps({
        "plan_id": plan_id,
        "action_rows": summary["action_rows"],
        "read_only": summary["recommended_read_only_rows"],
        "executable_after_confirmation": summary["executable_after_user_confirmation_rows"],
        "blocked": summary["blocked_requires_human_decision_rows"],
        "forbidden": summary["forbidden_for_current_request_rows"],
        "output": str(args.report_output),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
