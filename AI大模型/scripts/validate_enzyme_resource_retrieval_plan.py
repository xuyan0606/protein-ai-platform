#!/usr/bin/env python3
"""Validate fail-closed enzyme resource retrieval plan and checkpoint."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
PLAN = AI_ROOT / "reports" / "enzyme_resource_retrieval_plan_report.json"
CHECKPOINTS = AI_ROOT / "datasets" / "governance" / "enzyme_agent_state_checkpoints.jsonl"
ACTION_REGISTRY = AI_ROOT / "datasets" / "governance" / "enzyme_action_space_registry.jsonl"
OUT = AI_ROOT / "reports" / "enzyme_resource_retrieval_plan_validation_report.json"

REQUIRED_CATEGORIES = {
    "recommended_read_only",
    "executable_after_user_confirmation",
    "blocked_requires_human_decision",
    "forbidden_for_current_request",
}


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate enzyme resource retrieval plan")
    parser.add_argument("--plan", type=Path, default=PLAN)
    parser.add_argument("--checkpoints", type=Path, default=CHECKPOINTS)
    parser.add_argument("--actions", type=Path, default=ACTION_REGISTRY)
    parser.add_argument("--output", type=Path, default=OUT)
    args = parser.parse_args()

    plan = load_json(args.plan)
    checkpoints = load_jsonl(args.checkpoints)
    action_registry = load_jsonl(args.actions)
    failures: list[dict[str, Any]] = []

    categories = plan.get("categories") or {}
    actions = plan.get("actions") or []
    action_ids = {str(row.get("action_id")) for row in actions}
    registry_action_ids = {str(row.get("action_id")) for row in action_registry}
    categorized_ids: set[str] = set()

    if set(categories) != REQUIRED_CATEGORIES:
        failures.append({"check": "required_categories_exact", "observed": sorted(categories), "expected": sorted(REQUIRED_CATEGORIES)})
    if action_ids != registry_action_ids:
        failures.append({"check": "plan_actions_match_registry", "observed_missing": sorted(registry_action_ids - action_ids), "extra": sorted(action_ids - registry_action_ids)})
    for category, rows in categories.items():
        if not isinstance(rows, list):
            failures.append({"check": "category_rows_list", "category": category})
            continue
        for row in rows:
            action_id = str(row.get("action_id"))
            categorized_ids.add(action_id)
            if row.get("classification") != category:
                failures.append({"check": "row_classification_matches_category", "action_id": action_id, "classification": row.get("classification"), "category": category})

    if categorized_ids != action_ids:
        failures.append({"check": "all_plan_actions_categorized_once", "missing": sorted(action_ids - categorized_ids), "extra": sorted(categorized_ids - action_ids)})
    if plan.get("safe_for_execution") is not False:
        failures.append({"check": "safe_for_execution_false", "observed": plan.get("safe_for_execution")})
    if plan.get("safe_for_training_import") is not False:
        failures.append({"check": "safe_for_training_import_false", "observed": plan.get("safe_for_training_import")})
    if plan.get("safe_for_model_claim") is not False:
        failures.append({"check": "safe_for_model_claim_false", "observed": plan.get("safe_for_model_claim")})
    if plan.get("release_ready") is not False:
        failures.append({"check": "release_ready_false", "observed": plan.get("release_ready")})

    summary = plan.get("summary") or {}
    if summary.get("writes_training_rows") != 0:
        failures.append({"check": "summary_training_writes_zero", "observed": summary.get("writes_training_rows")})
    if summary.get("safe_for_model_claim_rows") != 0:
        failures.append({"check": "summary_model_claim_rows_zero", "observed": summary.get("safe_for_model_claim_rows")})
    if summary.get("action_rows") != len(actions):
        failures.append({"check": "summary_action_rows_match", "observed": summary.get("action_rows"), "expected": len(actions)})

    if len(checkpoints) != 1:
        failures.append({"check": "one_checkpoint_row", "observed": len(checkpoints), "expected": 1})
    else:
        checkpoint = checkpoints[0]
        if checkpoint.get("plan_id") != plan.get("plan_id"):
            failures.append({"check": "checkpoint_plan_id_matches", "observed": checkpoint.get("plan_id"), "expected": plan.get("plan_id")})
        if checkpoint.get("stage") != "retrieval_plan_built":
            failures.append({"check": "checkpoint_stage_retrieval_only", "observed": checkpoint.get("stage")})
        if checkpoint.get("executed_action_ids") not in ([], None):
            failures.append({"check": "checkpoint_executed_actions_empty", "observed": checkpoint.get("executed_action_ids")})
        claim_snapshot = checkpoint.get("claim_snapshot") or {}
        for field in ["safe_for_training_import", "safe_for_model_claim", "release_ready"]:
            if claim_snapshot.get(field) is not False:
                failures.append({"check": "checkpoint_claim_snapshot_false", "field": field, "observed": claim_snapshot.get(field)})
        expected_blocked = sorted(row.get("action_id") for row in categories.get("blocked_requires_human_decision", []))
        if sorted(checkpoint.get("blocked_action_ids") or []) != expected_blocked:
            failures.append({"check": "checkpoint_blocked_ids_match", "observed": checkpoint.get("blocked_action_ids"), "expected": expected_blocked})
        expected_forbidden = sorted(row.get("action_id") for row in categories.get("forbidden_for_current_request", []))
        if sorted(checkpoint.get("forbidden_action_ids") or []) != expected_forbidden:
            failures.append({"check": "checkpoint_forbidden_ids_match", "observed": checkpoint.get("forbidden_action_ids"), "expected": expected_forbidden})

    report = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "local_only": True,
        "success": not failures,
        "plan_id": plan.get("plan_id"),
        "action_rows": len(actions),
        "checkpoint_rows": len(checkpoints),
        "recommended_read_only_rows": len(categories.get("recommended_read_only") or []),
        "executable_after_user_confirmation_rows": len(categories.get("executable_after_user_confirmation") or []),
        "blocked_requires_human_decision_rows": len(categories.get("blocked_requires_human_decision") or []),
        "forbidden_for_current_request_rows": len(categories.get("forbidden_for_current_request") or []),
        "failures": failures,
        "safe_for_controlled_agent_planning": not failures,
        "safe_for_execution": False,
        "safe_for_training_import": False,
        "safe_for_model_claim": False,
        "release_ready": False,
        "policy": "Validation confirms resource retrieval planning only. It does not authorize execution, formal decisions, training import, model claims, downloads, MCP calls, or release.",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "success": report["success"],
        "action_rows": report["action_rows"],
        "checkpoint_rows": report["checkpoint_rows"],
        "failures": len(failures),
        "output": str(args.output),
    }, ensure_ascii=False))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
