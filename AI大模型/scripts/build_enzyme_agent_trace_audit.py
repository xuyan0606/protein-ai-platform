#!/usr/bin/env python3
"""Build a fail-closed audit trace for the enzyme agent planning/result path."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
TRACE_OUT = AI_ROOT / "datasets" / "governance" / "enzyme_agent_trace_audit.jsonl"
REPORT_OUT = AI_ROOT / "reports" / "enzyme_agent_trace_audit_report.json"


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Build enzyme agent audit trace")
    parser.add_argument("--trace-output", type=Path, default=TRACE_OUT)
    parser.add_argument("--report-output", type=Path, default=REPORT_OUT)
    args = parser.parse_args()

    created_at = datetime.now(timezone.utc).isoformat()
    resource_plan = load_json(AI_ROOT / "reports" / "enzyme_resource_retrieval_plan_report.json")
    resource_validation = load_json(AI_ROOT / "reports" / "enzyme_resource_retrieval_plan_validation_report.json")
    checkpoints = load_jsonl(AI_ROOT / "datasets" / "governance" / "enzyme_agent_state_checkpoints.jsonl")
    result = load_json(AI_ROOT / "reports" / "enzyme_agent_result_template.json")
    result_validation = load_json(AI_ROOT / "reports" / "enzyme_agent_result_validation_report.json")
    result_regression = load_json(AI_ROOT / "reports" / "enzyme_agent_result_safety_regression_report.json")

    checkpoint = checkpoints[0] if checkpoints else {}
    executed_action_ids = checkpoint.get("executed_action_ids") or []
    blocked_action_ids = checkpoint.get("blocked_action_ids") or []
    forbidden_action_ids = checkpoint.get("forbidden_action_ids") or []
    source_plan_id = resource_plan.get("plan_id") or checkpoint.get("plan_id") or "missing_plan"

    trace_rows = [
        {
            "trace_id": "enzyme_agent_trace_20260731_p170",
            "event_index": 1,
            "event_type": "resource_plan_built",
            "created_at": created_at,
            "local_only": True,
            "plan_id": source_plan_id,
            "artifact": "reports/enzyme_resource_retrieval_plan_report.json",
            "action_rows": (resource_plan.get("summary") or {}).get("action_rows"),
            "blocked_action_ids": blocked_action_ids,
            "forbidden_action_ids": forbidden_action_ids,
            "executed_action_ids": executed_action_ids,
            "safe_for_training_import": False,
            "safe_for_model_claim": False,
            "release_ready": False,
        },
        {
            "trace_id": "enzyme_agent_trace_20260731_p170",
            "event_index": 2,
            "event_type": "resource_plan_validated",
            "created_at": created_at,
            "local_only": True,
            "artifact": "reports/enzyme_resource_retrieval_plan_validation_report.json",
            "success": bool(resource_validation.get("success")),
            "failures": len(resource_validation.get("failures") or []),
            "safe_for_execution": bool(resource_validation.get("safe_for_execution")),
            "safe_for_training_import": False,
            "safe_for_model_claim": False,
            "release_ready": False,
        },
        {
            "trace_id": "enzyme_agent_trace_20260731_p170",
            "event_index": 3,
            "event_type": "result_template_built",
            "created_at": created_at,
            "local_only": True,
            "artifact": "reports/enzyme_agent_result_template.json",
            "result_id": result.get("result_id"),
            "selected_variant_rows": len(result.get("selected_variants") or []),
            "manual_review_required": bool(result.get("manual_review_required")),
            "safe_for_training_import": bool(result.get("safe_for_training_import")),
            "safe_for_model_claim": bool(result.get("safe_for_model_claim")),
            "release_ready": bool(result.get("release_ready")),
        },
        {
            "trace_id": "enzyme_agent_trace_20260731_p170",
            "event_index": 4,
            "event_type": "result_validated",
            "created_at": created_at,
            "local_only": True,
            "artifact": "reports/enzyme_agent_result_validation_report.json",
            "success": bool(result_validation.get("success")),
            "failures": len(result_validation.get("failures") or []),
            "selected_variant_rows": result_validation.get("selected_variant_rows"),
            "safe_for_training_import": False,
            "safe_for_model_claim": False,
            "release_ready": False,
        },
        {
            "trace_id": "enzyme_agent_trace_20260731_p170",
            "event_index": 5,
            "event_type": "result_safety_regression_validated",
            "created_at": created_at,
            "local_only": True,
            "artifact": "reports/enzyme_agent_result_safety_regression_report.json",
            "success": bool(result_regression.get("success")),
            "case_rows": result_regression.get("case_rows"),
            "actual_rejected_negative_cases": result_regression.get("actual_rejected_negative_cases"),
            "failed_regression_cases": result_regression.get("failed_regression_cases"),
            "safe_for_training_import": False,
            "safe_for_model_claim": False,
            "release_ready": False,
        },
        {
            "trace_id": "enzyme_agent_trace_20260731_p170",
            "event_index": 6,
            "event_type": "final_fail_closed_state",
            "created_at": created_at,
            "local_only": True,
            "artifact": str(args.report_output.relative_to(AI_ROOT)),
            "executed_action_ids": executed_action_ids,
            "selected_variant_rows": len(result.get("selected_variants") or []),
            "manual_review_required": True,
            "safe_for_training_import": False,
            "safe_for_model_claim": False,
            "release_ready": False,
        },
    ]

    report = {
        "trace_id": "enzyme_agent_trace_20260731_p170",
        "created_at": created_at,
        "local_only": True,
        "plan_id": source_plan_id,
        "trace_rows": len(trace_rows),
        "event_types": [row["event_type"] for row in trace_rows],
        "executed_action_count": len(executed_action_ids),
        "executed_action_ids": executed_action_ids,
        "blocked_action_count": len(blocked_action_ids),
        "forbidden_action_count": len(forbidden_action_ids),
        "selected_variant_rows": len(result.get("selected_variants") or []),
        "resource_plan_validation_success": bool(resource_validation.get("success")),
        "result_validation_success": bool(result_validation.get("success")),
        "result_safety_regression_success": bool(result_regression.get("success")),
        "result_safety_regression_failed_cases": result_regression.get("failed_regression_cases"),
        "artifacts": [
            "reports/enzyme_resource_retrieval_plan_report.json",
            "reports/enzyme_resource_retrieval_plan_validation_report.json",
            "datasets/governance/enzyme_agent_state_checkpoints.jsonl",
            "reports/enzyme_agent_result_template.json",
            "reports/enzyme_agent_result_validation_report.json",
            "reports/enzyme_agent_result_safety_regression_report.json",
            str(args.trace_output.relative_to(AI_ROOT)),
        ],
        "safe_for_training_import": False,
        "safe_for_model_claim": False,
        "release_ready": False,
        "policy": "Audit trace records planning and validation only. It proves no controlled enzyme agent tool was executed and does not approve training import, model claims, customer delivery, ordering, or release.",
    }

    write_jsonl(args.trace_output, trace_rows)
    args.report_output.parent.mkdir(parents=True, exist_ok=True)
    args.report_output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "trace_rows": report["trace_rows"],
        "executed_action_count": report["executed_action_count"],
        "result_validation_success": report["result_validation_success"],
        "result_safety_regression_success": report["result_safety_regression_success"],
        "safe_for_model_claim": False,
        "output": str(args.report_output),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
