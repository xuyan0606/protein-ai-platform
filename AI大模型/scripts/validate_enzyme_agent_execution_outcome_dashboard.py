#!/usr/bin/env python3
"""Validate the enzyme-agent execution outcome dashboard."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
DASHBOARD = AI_ROOT / "datasets" / "governance" / "enzyme_agent_execution_outcome_dashboard.jsonl"
REPORT = AI_ROOT / "reports" / "enzyme_agent_execution_outcome_dashboard_report.json"
OUT = AI_ROOT / "reports" / "enzyme_agent_execution_outcome_dashboard_validation_report.json"
WET_LAB_AUTHORIZATION_VALIDATION = (
    AI_ROOT / "reports" / "wet_lab_mutant_library_feedback_authorization_validation_report.json"
)


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def fail_if(condition: bool, failures: list[dict[str, Any]], check: str, observed: Any, expected: Any) -> None:
    if condition:
        failures.append({"check": check, "observed": observed, "expected": expected})


def validate_dashboard(rows: list[dict[str, Any]], report: dict[str, Any]) -> list[dict[str, Any]]:
    failures: list[dict[str, Any]] = []
    wet_lab_authorization = load_json(WET_LAB_AUTHORIZATION_VALIDATION)
    expected_wet_lab_authorizations = int(wet_lab_authorization.get("authorization_rows") or 0)
    action_ids = [row.get("action_id") for row in rows]
    fail_if(report.get("action_rows") != len(rows), failures, "action_rows_match", report.get("action_rows"), len(rows))
    fail_if(len(action_ids) != len(set(action_ids)), failures, "action_ids_unique", action_ids, "unique")
    by_action = {row.get("action_id"): row for row in rows}
    ddg = by_action.get("act_ddg_proxy_or_physics") or {}
    physics_runtime_ready = ddg.get("outcome_class") == "physics_ddg_runtime_ready"
    expected_unlocked_rows = (1 if expected_wet_lab_authorizations > 0 else 0) + (1 if physics_runtime_ready else 0)
    fail_if(report.get("hard_gate_unlocked_rows") != expected_unlocked_rows, failures, "hard_gate_unlocked_rows_match_wet_lab_authorization_state", report.get("hard_gate_unlocked_rows"), expected_unlocked_rows)
    fail_if(report.get("safe_for_training_import") is not False, failures, "report_training_import_false", report.get("safe_for_training_import"), False)
    fail_if(report.get("safe_for_model_claim") is not False, failures, "report_model_claim_false", report.get("safe_for_model_claim"), False)
    fail_if(report.get("release_ready") is not False, failures, "report_release_ready_false", report.get("release_ready"), False)
    fail_if(report.get("rosetta_pyrosetta_foldx_physics_ddg_ready") is not physics_runtime_ready, failures, "physics_ddg_ready_matches_ddg_outcome", report.get("rosetta_pyrosetta_foldx_physics_ddg_ready"), physics_runtime_ready)
    fail_if(report.get("benchmark_ready_for_model_claim") is not False, failures, "benchmark_ready_for_model_claim_false", report.get("benchmark_ready_for_model_claim"), False)
    formal = report.get("formal_counts") or {}
    fail_if(formal.get("wet_lab_feedback_authorizations") != expected_wet_lab_authorizations, failures, "wet_lab_authorizations_match_validation_report", formal.get("wet_lab_feedback_authorizations"), expected_wet_lab_authorizations)
    fail_if(formal.get("strict_repaired_supervised_rows") != 0, failures, "strict_repaired_supervised_rows_zero", formal.get("strict_repaired_supervised_rows"), 0)
    fail_if(formal.get("claim_eligible_rows") != 0, failures, "claim_eligible_rows_zero", formal.get("claim_eligible_rows"), 0)

    fail_if(ddg.get("outcome_class") not in {"physical_ddg_not_ready", "physics_ddg_runtime_ready"}, failures, "ddg_outcome_supported_state", ddg.get("outcome_class"), "physical_ddg_not_ready or physics_ddg_runtime_ready")
    fail_if(ddg.get("hard_gate_unlocked") is not physics_runtime_ready, failures, "ddg_hard_gate_unlocked_matches_physics_runtime", ddg.get("hard_gate_unlocked"), physics_runtime_ready)
    benchmark = by_action.get("act_benchmark_score_cache") or {}
    fail_if(benchmark.get("hard_gate_unlocked") is not False, failures, "benchmark_hard_gate_unlocked_false", benchmark.get("hard_gate_unlocked"), False)
    wet_lab = by_action.get("act_wet_lab_feedback_authorization") or {}
    fail_if(
        wet_lab.get("hard_gate_unlocked") is not (expected_wet_lab_authorizations > 0),
        failures,
        "wet_lab_hard_gate_unlocked_matches_authorization_rows",
        wet_lab.get("hard_gate_unlocked"),
        expected_wet_lab_authorizations > 0,
    )

    for idx, row in enumerate(rows):
        fail_if(row.get("writes_formal_decision") is not False, failures, "row_writes_formal_decision_false", {"index": idx, "action_id": row.get("action_id"), "observed": row.get("writes_formal_decision")}, False)
        fail_if(row.get("writes_training_rows") is not False, failures, "row_writes_training_rows_false", {"index": idx, "action_id": row.get("action_id"), "observed": row.get("writes_training_rows")}, False)
        fail_if(row.get("safe_for_training_import") is not False, failures, "row_training_import_false", {"index": idx, "action_id": row.get("action_id"), "observed": row.get("safe_for_training_import")}, False)
        fail_if(row.get("safe_for_model_claim") is not False, failures, "row_model_claim_false", {"index": idx, "action_id": row.get("action_id"), "observed": row.get("safe_for_model_claim")}, False)
        fail_if(row.get("release_ready") is not False, failures, "row_release_ready_false", {"index": idx, "action_id": row.get("action_id"), "observed": row.get("release_ready")}, False)

    return failures


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate enzyme agent execution outcome dashboard")
    parser.add_argument("--dashboard", type=Path, default=DASHBOARD)
    parser.add_argument("--report", type=Path, default=REPORT)
    parser.add_argument("--output", type=Path, default=OUT)
    args = parser.parse_args()

    rows = load_jsonl(args.dashboard)
    report = load_json(args.report)
    failures = validate_dashboard(rows, report)
    validation = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "local_only": True,
        "success": not failures,
        "action_rows": len(rows),
        "failures": failures,
        "safe_for_training_import": False,
        "safe_for_model_claim": False,
        "release_ready": False,
        "policy": "Validation keeps execution outcomes separated from formal decisions, training imports, model claims, and release. A local PyRosetta physics runtime unlock is allowed only as computational evidence.",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(validation, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "success": validation["success"],
        "action_rows": validation["action_rows"],
        "failures": len(failures),
        "safe_for_model_claim": False,
        "output": str(args.output),
    }, ensure_ascii=False))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
