#!/usr/bin/env python3
"""Validate KWB enzyme action-space and tool contracts."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
ACTIONS = AI_ROOT / "datasets" / "governance" / "enzyme_action_space_registry.jsonl"
CONTRACTS = AI_ROOT / "datasets" / "governance" / "enzyme_tool_contracts.jsonl"
OUT = AI_ROOT / "reports" / "enzyme_tool_contract_validation_report.json"

REQUIRED_ACTION_IDS = {
    "act_numbering_review",
    "act_structure_chain_mapping",
    "act_msa_conservation",
    "act_ddg_proxy_or_physics",
    "act_wet_lab_feedback_authorization",
    "act_fireprot_candidate_review",
    "act_benchmark_score_cache",
    "act_model_claim_consistency",
    "act_release_guard_links",
    "act_know_how_retrieval",
    "act_tool_contract_validation",
    "act_safe_pipeline",
}

REQUIRED_CONTRACT_IDS = {
    "tool_numbering_curation_validate_apply",
    "tool_structure_chain_mapping_validate_apply",
    "tool_msa_mmseqs_cache_validate",
    "tool_ddg_backend_readiness_probe",
    "tool_wet_lab_feedback_authorization_gate",
    "tool_fireprot_reviewed_import_gate",
    "tool_benchmark_score_cache_validate",
    "tool_model_claim_fail_closed_consistency",
    "tool_local_release_safety_guard_links",
    "tool_enzyme_know_how_retrieval_plan",
    "tool_enzyme_tool_contract_validator",
    "tool_safe_training_pipeline",
}

REQUIRED_ACTION_FIELDS = {
    "action_id",
    "category",
    "title",
    "description",
    "primary_contract_id",
    "input_artifacts",
    "output_artifacts",
    "risk_level",
    "human_confirmation_required",
    "writes_formal_decision",
    "writes_training_rows",
    "safe_for_model_claim",
}

REQUIRED_CONTRACT_FIELDS = {
    "contract_id",
    "tool_name",
    "category",
    "allowed_execution_mode",
    "entrypoints",
    "runtime_readiness",
    "license_status",
    "human_confirmation_required",
    "can_write_formal_decision",
    "can_write_training_rows",
    "requires_safe_pipeline_after_execution",
}

VALID_EXECUTION_MODES = {"read_only", "local_script", "manual_only"}
HUMAN_GATE_CATEGORIES = {"human_curation", "external_data", "external_tool", "benchmark"}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate enzyme action-space and tool contracts")
    parser.add_argument("--actions", type=Path, default=ACTIONS)
    parser.add_argument("--contracts", type=Path, default=CONTRACTS)
    parser.add_argument("--output", type=Path, default=OUT)
    args = parser.parse_args()

    actions = load_jsonl(args.actions)
    contracts = load_jsonl(args.contracts)
    failures: list[dict[str, Any]] = []

    action_ids = {str(row.get("action_id")) for row in actions}
    contract_ids = {str(row.get("contract_id")) for row in contracts}

    missing_actions = sorted(REQUIRED_ACTION_IDS - action_ids)
    extra_actions = sorted(action_ids - REQUIRED_ACTION_IDS)
    missing_contracts = sorted(REQUIRED_CONTRACT_IDS - contract_ids)
    extra_contracts = sorted(contract_ids - REQUIRED_CONTRACT_IDS)
    if missing_actions:
        failures.append({"check": "required_actions_present", "missing": missing_actions})
    if extra_actions:
        failures.append({"check": "no_unexpected_actions", "extra": extra_actions})
    if missing_contracts:
        failures.append({"check": "required_contracts_present", "missing": missing_contracts})
    if extra_contracts:
        failures.append({"check": "no_unexpected_contracts", "extra": extra_contracts})

    for row in actions:
        action_id = row.get("action_id")
        missing = sorted(field for field in REQUIRED_ACTION_FIELDS if field not in row)
        if missing:
            failures.append({"check": "action_required_fields", "action_id": action_id, "missing": missing})
        if row.get("primary_contract_id") not in contract_ids:
            failures.append({"check": "action_contract_exists", "action_id": action_id, "contract_id": row.get("primary_contract_id")})
        if row.get("writes_training_rows") is not False:
            failures.append({"check": "no_action_writes_training_rows", "action_id": action_id, "observed": row.get("writes_training_rows")})
        if row.get("safe_for_model_claim") is not False:
            failures.append({"check": "no_action_safe_for_model_claim", "action_id": action_id, "observed": row.get("safe_for_model_claim")})
        if row.get("writes_formal_decision") and row.get("human_confirmation_required") is not True:
            failures.append({"check": "formal_decision_action_requires_human_confirmation", "action_id": action_id})
        if row.get("category") in HUMAN_GATE_CATEGORIES and row.get("human_confirmation_required") is not True:
            failures.append({"check": "risky_action_requires_human_confirmation", "action_id": action_id, "category": row.get("category")})
        if not isinstance(row.get("input_artifacts"), list) or not isinstance(row.get("output_artifacts"), list):
            failures.append({"check": "action_artifact_lists", "action_id": action_id})

    for row in contracts:
        contract_id = row.get("contract_id")
        missing = sorted(field for field in REQUIRED_CONTRACT_FIELDS if field not in row)
        if missing:
            failures.append({"check": "contract_required_fields", "contract_id": contract_id, "missing": missing})
        if row.get("allowed_execution_mode") not in VALID_EXECUTION_MODES:
            failures.append({"check": "contract_execution_mode_valid", "contract_id": contract_id, "observed": row.get("allowed_execution_mode")})
        if not isinstance(row.get("entrypoints"), list) or not row.get("entrypoints"):
            failures.append({"check": "contract_entrypoints_nonempty", "contract_id": contract_id})
        if row.get("can_write_training_rows") is not False:
            failures.append({"check": "no_contract_writes_training_rows", "contract_id": contract_id, "observed": row.get("can_write_training_rows")})
        if row.get("can_write_formal_decision") is not False:
            failures.append({"check": "no_agent_contract_writes_formal_decision", "contract_id": contract_id, "observed": row.get("can_write_formal_decision")})
        if row.get("category") in HUMAN_GATE_CATEGORIES and row.get("human_confirmation_required") is not True:
            failures.append({"check": "risky_contract_requires_human_confirmation", "contract_id": contract_id, "category": row.get("category")})
        if row.get("category") == "external_tool" and row.get("allowed_execution_mode") != "manual_only":
            failures.append({"check": "external_tool_manual_only_until_authorized", "contract_id": contract_id, "mode": row.get("allowed_execution_mode")})

    report = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "local_only": True,
        "success": not failures,
        "action_rows": len(actions),
        "contract_rows": len(contracts),
        "required_action_rows": len(REQUIRED_ACTION_IDS),
        "required_contract_rows": len(REQUIRED_CONTRACT_IDS),
        "human_confirmation_required_actions": sum(1 for row in actions if row.get("human_confirmation_required")),
        "formal_decision_actions": sum(1 for row in actions if row.get("writes_formal_decision")),
        "training_write_actions": sum(1 for row in actions if row.get("writes_training_rows")),
        "safe_for_model_claim_actions": sum(1 for row in actions if row.get("safe_for_model_claim")),
        "contract_training_write_tools": sum(1 for row in contracts if row.get("can_write_training_rows")),
        "contract_formal_write_tools": sum(1 for row in contracts if row.get("can_write_formal_decision")),
        "failures": failures,
        "safe_for_controlled_agent_planning": not failures,
        "safe_for_training_import": False,
        "safe_for_model_claim": False,
        "release_ready": False,
        "policy": "Tool contracts are metadata for controlled planning. They do not authorize writing formal human decisions, training rows, model claims, downloads, or production release.",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "success": report["success"],
        "action_rows": report["action_rows"],
        "contract_rows": report["contract_rows"],
        "failures": len(failures),
        "output": str(args.output),
    }, ensure_ascii=False))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
