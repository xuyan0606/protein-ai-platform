#!/usr/bin/env python3
"""Validate the fail-closed enzyme agent audit trace."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
TRACE = AI_ROOT / "datasets" / "governance" / "enzyme_agent_trace_audit.jsonl"
REPORT = AI_ROOT / "reports" / "enzyme_agent_trace_audit_report.json"
OUT = AI_ROOT / "reports" / "enzyme_agent_trace_audit_validation_report.json"

REQUIRED_EVENT_TYPES = [
    "resource_plan_built",
    "resource_plan_validated",
    "result_template_built",
    "result_validated",
    "result_safety_regression_validated",
    "final_fail_closed_state",
]


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def fail_if(condition: bool, failures: list[dict[str, Any]], check: str, observed: Any, expected: Any) -> None:
    if condition:
        failures.append({"check": check, "observed": observed, "expected": expected})


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate enzyme agent audit trace")
    parser.add_argument("--trace", type=Path, default=TRACE)
    parser.add_argument("--report", type=Path, default=REPORT)
    parser.add_argument("--output", type=Path, default=OUT)
    args = parser.parse_args()

    trace_rows = load_jsonl(args.trace)
    report = load_json(args.report)
    failures: list[dict[str, Any]] = []
    event_types = [row.get("event_type") for row in trace_rows]
    event_indexes = [row.get("event_index") for row in trace_rows]

    fail_if(event_types != REQUIRED_EVENT_TYPES, failures, "required_event_sequence", event_types, REQUIRED_EVENT_TYPES)
    fail_if(event_indexes != list(range(1, len(REQUIRED_EVENT_TYPES) + 1)), failures, "event_indexes_sequential", event_indexes, list(range(1, len(REQUIRED_EVENT_TYPES) + 1)))
    fail_if(report.get("trace_rows") != len(trace_rows), failures, "report_trace_rows_match", report.get("trace_rows"), len(trace_rows))
    fail_if(report.get("executed_action_count") != 0, failures, "executed_action_count_zero", report.get("executed_action_count"), 0)
    fail_if(report.get("executed_action_ids") not in ([], None), failures, "executed_action_ids_empty", report.get("executed_action_ids"), [])
    fail_if(report.get("selected_variant_rows") != 0, failures, "selected_variant_rows_zero", report.get("selected_variant_rows"), 0)
    fail_if(report.get("resource_plan_validation_success") is not True, failures, "resource_plan_validation_success_true", report.get("resource_plan_validation_success"), True)
    fail_if(report.get("result_validation_success") is not True, failures, "result_validation_success_true", report.get("result_validation_success"), True)
    fail_if(report.get("result_safety_regression_success") is not True, failures, "result_safety_regression_success_true", report.get("result_safety_regression_success"), True)
    fail_if(report.get("result_safety_regression_failed_cases") not in (0, None), failures, "result_safety_regression_failed_cases_zero", report.get("result_safety_regression_failed_cases"), 0)
    fail_if(report.get("safe_for_training_import") is not False, failures, "report_training_import_false", report.get("safe_for_training_import"), False)
    fail_if(report.get("safe_for_model_claim") is not False, failures, "report_model_claim_false", report.get("safe_for_model_claim"), False)
    fail_if(report.get("release_ready") is not False, failures, "report_release_ready_false", report.get("release_ready"), False)

    for row in trace_rows:
        fail_if(row.get("local_only") is not True, failures, "trace_row_local_only_true", {"event_type": row.get("event_type"), "observed": row.get("local_only")}, True)
        fail_if(row.get("safe_for_training_import") is not False, failures, "trace_row_training_import_false", {"event_type": row.get("event_type"), "observed": row.get("safe_for_training_import")}, False)
        fail_if(row.get("safe_for_model_claim") is not False, failures, "trace_row_model_claim_false", {"event_type": row.get("event_type"), "observed": row.get("safe_for_model_claim")}, False)
        fail_if(row.get("release_ready") is not False, failures, "trace_row_release_ready_false", {"event_type": row.get("event_type"), "observed": row.get("release_ready")}, False)
        if row.get("event_type") == "final_fail_closed_state":
            fail_if(row.get("executed_action_ids") not in ([], None), failures, "final_executed_action_ids_empty", row.get("executed_action_ids"), [])
            fail_if(row.get("manual_review_required") is not True, failures, "final_manual_review_required_true", row.get("manual_review_required"), True)

    artifact_failures = []
    for rel in report.get("artifacts") or []:
        if not isinstance(rel, str) or not (AI_ROOT / rel).exists():
            artifact_failures.append(rel)
    if artifact_failures:
        failures.append({"check": "report_artifacts_exist", "observed_missing": artifact_failures, "expected": "all artifact refs exist"})

    validation_report = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "local_only": True,
        "success": not failures,
        "trace_rows": len(trace_rows),
        "event_types": event_types,
        "executed_action_count": report.get("executed_action_count"),
        "selected_variant_rows": report.get("selected_variant_rows"),
        "failures": failures,
        "safe_for_training_import": False,
        "safe_for_model_claim": False,
        "release_ready": False,
        "policy": "Passing this trace validator only proves the agent path is auditable and fail-closed. It does not approve execution, training import, model claims, customer delivery, or release.",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(validation_report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "success": validation_report["success"],
        "trace_rows": validation_report["trace_rows"],
        "executed_action_count": validation_report["executed_action_count"],
        "failures": len(failures),
        "safe_for_model_claim": False,
        "output": str(args.output),
    }, ensure_ascii=False))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
