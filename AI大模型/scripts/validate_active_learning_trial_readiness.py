#!/usr/bin/env python3
"""Validate active-learning trial readiness is source-bound and fail-closed."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
REPORT = AI_ROOT / "reports" / "active_learning_trial_readiness_report.json"
OUT = AI_ROOT / "reports" / "active_learning_trial_readiness_validation_report.json"
EXPECTED_DRAFT = AI_ROOT / "datasets" / "curation" / "active_learning_trial_drafts.jsonl"

BASE_BLOCKERS = (
    "five-head model is not training-ready",
    "head-level benchmark scorecards are not ready",
    "plate-level feedback intake has no eligible rows",
    "human approval workflow is not configured",
    "budget and assay capacity are not approved",
)


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return value if isinstance(value, dict) else {}


def count_jsonl_rows(path: Path) -> int:
    if not path.exists():
        return 0
    return sum(1 for line in path.read_text(encoding="utf-8").splitlines() if line.strip())


def fail_if(condition: bool, failures: list[dict[str, Any]], check: str, observed: Any, expected: Any) -> None:
    if condition:
        failures.append({"check": check, "observed": observed, "expected": expected})


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate active-learning trial readiness")
    parser.add_argument("--report", type=Path, default=REPORT)
    parser.add_argument("--output", type=Path, default=OUT)
    args = parser.parse_args()

    report = load_json(args.report)
    multitask = load_json(AI_ROOT / "reports" / "multitask_training_readiness_report.json")
    benchmark = load_json(AI_ROOT / "reports" / "benchmark_matrix_report.json")
    biosecurity = load_json(AI_ROOT / "reports" / "biosecurity_readiness_report.json")
    customer = load_json(AI_ROOT / "reports" / "customer_delivery_readiness_report.json")

    failures: list[dict[str, Any]] = []
    draft_file = Path(str(report.get("draft_file") or EXPECTED_DRAFT))
    draft_rows = count_jsonl_rows(draft_file)
    expected_blockers = list(BASE_BLOCKERS)
    if not biosecurity.get("ready_for_ordering"):
        expected_blockers.append("biosecurity/order gate is not approved")
    if not customer.get("ready"):
        expected_blockers.append("customer delivery gate is blocked")

    fail_if(not report, failures, "report_present", str(args.report), "existing JSON report")
    fail_if(report.get("local_only") is not True, failures, "local_only_true", report.get("local_only"), True)
    fail_if(report.get("ready") is not False, failures, "ready_false", report.get("ready"), False)
    fail_if(report.get("candidate_generation_allowed") is not False, failures, "candidate_generation_allowed_false", report.get("candidate_generation_allowed"), False)
    fail_if(report.get("experiment_submission_allowed") is not False, failures, "experiment_submission_allowed_false", report.get("experiment_submission_allowed"), False)
    fail_if(report.get("human_approval_required") is not True, failures, "human_approval_required_true", report.get("human_approval_required"), True)
    fail_if(Path(str(report.get("draft_file") or "")) != EXPECTED_DRAFT, failures, "draft_file_expected", report.get("draft_file"), str(EXPECTED_DRAFT))
    fail_if(int(report.get("draft_rows") or 0) != draft_rows, failures, "draft_rows_match_file", report.get("draft_rows"), draft_rows)
    fail_if(draft_rows != 0, failures, "draft_file_empty_fail_closed", draft_rows, 0)
    fail_if(report.get("model_status") != multitask.get("status"), failures, "model_status_matches_multitask", report.get("model_status"), multitask.get("status"))
    fail_if(report.get("benchmark_ready_for_model_claim") != benchmark.get("ready_for_model_claim"), failures, "benchmark_ready_matches_source", report.get("benchmark_ready_for_model_claim"), benchmark.get("ready_for_model_claim"))
    fail_if(multitask.get("status") != "blocked", failures, "multitask_status_blocked", multitask.get("status"), "blocked")
    fail_if(benchmark.get("ready_for_model_claim") is not False, failures, "benchmark_claim_ready_false", benchmark.get("ready_for_model_claim"), False)
    fail_if(biosecurity.get("ready_for_ordering") is not False, failures, "biosecurity_ordering_false", biosecurity.get("ready_for_ordering"), False)
    fail_if(customer.get("ready") is not False, failures, "customer_delivery_ready_false", customer.get("ready"), False)
    fail_if(report.get("blockers") != expected_blockers, failures, "blockers_match_sources", report.get("blockers"), expected_blockers)

    validation = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "local_only": True,
        "checked_report": str(args.report),
        "draft_file": str(draft_file),
        "draft_rows": draft_rows,
        "model_status": multitask.get("status"),
        "benchmark_ready_for_model_claim": benchmark.get("ready_for_model_claim"),
        "biosecurity_ready_for_ordering": biosecurity.get("ready_for_ordering"),
        "customer_delivery_ready": customer.get("ready"),
        "expected_blockers": expected_blockers,
        "failures": failures,
        "success": not failures,
        "candidate_generation_allowed": False,
        "experiment_submission_allowed": False,
        "safe_for_model_claim": False,
        "release_ready": False,
        "policy": "Active-learning readiness validation is fail-closed; it does not create trial drafts, submit experiments, or open model/release gates.",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(validation, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({
        "success": validation["success"],
        "draft_rows": draft_rows,
        "failures": len(failures),
        "candidate_generation_allowed": False,
        "experiment_submission_allowed": False,
        "output": str(args.output),
    }, ensure_ascii=False))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
