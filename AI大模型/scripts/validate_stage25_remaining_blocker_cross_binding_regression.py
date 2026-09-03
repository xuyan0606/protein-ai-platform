#!/usr/bin/env python3
"""Regression cases for Stage 25 remaining blocker cross-binding."""

from __future__ import annotations

import copy
import json
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from validate_stage25_remaining_blocker_cross_binding import ACTIVATION, CLOSURE, COVERAGE, build_report


AI_ROOT = Path(__file__).resolve().parents[1]
OUT = AI_ROOT / "reports" / "stage25_remaining_blocker_cross_binding_regression_report.json"


def load_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return data


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def run_case(case_id: str, expected_valid: bool, closure: dict[str, Any], activation: dict[str, Any], coverage: dict[str, Any], tmpdir: Path) -> dict[str, Any]:
    case_dir = tmpdir / case_id
    case_dir.mkdir(parents=True, exist_ok=True)
    closure_path = case_dir / "closure.json"
    activation_path = case_dir / "activation.json"
    coverage_path = case_dir / "coverage.json"
    write_json(closure_path, closure)
    write_json(activation_path, activation)
    write_json(coverage_path, coverage)
    observed = build_report(closure_path, activation_path, coverage_path)
    failures = observed.get("failures") or []
    observed_valid = not failures
    return {
        "case_id": case_id,
        "expected_valid": expected_valid,
        "observed_valid": observed_valid,
        "passed": observed_valid == expected_valid,
        "failure_count": len(failures),
        "failure_checks": [failure.get("check") for failure in failures],
    }


def main() -> int:
    base_closure = load_json(CLOSURE)
    base_activation = load_json(ACTIVATION)
    base_coverage = load_json(COVERAGE)
    cases: list[dict[str, Any]] = []

    with tempfile.TemporaryDirectory(prefix="stage25-blocker-cross-binding-") as tmp:
        tmpdir = Path(tmp)
        cases.append(run_case("control_current_inputs_valid", True, copy.deepcopy(base_closure), copy.deepcopy(base_activation), copy.deepcopy(base_coverage), tmpdir))

        missing_coverage = copy.deepcopy(base_coverage)
        missing_coverage["rows"] = missing_coverage["rows"][:-1]
        missing_coverage["blocker_rows"] = len(missing_coverage["rows"])
        cases.append(run_case("missing_coverage_blocker_rejected", False, copy.deepcopy(base_closure), copy.deepcopy(base_activation), missing_coverage, tmpdir))

        extra_activation = copy.deepcopy(base_activation)
        extra_row = copy.deepcopy(extra_activation["activations"][0])
        extra_row["blocker_id"] = "stage25_unexpected_blocker"
        extra_activation["activations"].append(extra_row)
        extra_activation["activation_rows"] = len(extra_activation["activations"])
        extra_activation["mapped_blocker_ids"].append("stage25_unexpected_blocker")
        cases.append(run_case("extra_activation_blocker_rejected", False, copy.deepcopy(base_closure), extra_activation, copy.deepcopy(base_coverage), tmpdir))

        completion_ready_drift = copy.deepcopy(base_closure)
        completion_ready_drift["blockers"][0]["completion_ready"] = True
        completion_ready_drift["completion_ready_rows"] = 1
        cases.append(run_case("closure_completion_ready_drift_rejected", False, completion_ready_drift, copy.deepcopy(base_activation), copy.deepcopy(base_coverage), tmpdir))

        uncovered_drift = copy.deepcopy(base_coverage)
        uncovered_drift["rows"][0]["coverage_complete"] = False
        uncovered_drift["uncovered_blockers"] = [uncovered_drift["rows"][0]["blocker_id"]]
        cases.append(run_case("coverage_uncovered_blocker_rejected", False, copy.deepcopy(base_closure), copy.deepcopy(base_activation), uncovered_drift, tmpdir))

        receipt_drift = copy.deepcopy(base_coverage)
        receipt_drift["rows"][0]["current_receipt"] = "/tmp/forged_stage25_receipt.json"
        cases.append(run_case("current_receipt_drift_rejected", False, copy.deepcopy(base_closure), copy.deepcopy(base_activation), receipt_drift, tmpdir))

    passed_rows = sum(1 for case in cases if case["passed"])
    failed_rows = len(cases) - passed_rows
    rejected_negative_cases = sum(1 for case in cases if case["expected_valid"] is False and case["observed_valid"] is False)
    report = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "local_only": True,
        "success": failed_rows == 0,
        "case_rows": len(cases),
        "passed_rows": passed_rows,
        "failed_rows": failed_rows,
        "rejected_negative_cases": rejected_negative_cases,
        "control_valid": cases[0]["observed_valid"],
        "real_inputs_mutated": False,
        "cases": cases,
        "safe_for_model_claim": False,
        "release_ready": False,
        "policy": "Isolated fixtures verify the Stage 25 remaining-blocker cross-binding fails closed on missing, extra, completion-ready, uncovered and receipt-drift cases.",
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "success": report["success"],
        "case_rows": report["case_rows"],
        "passed_rows": report["passed_rows"],
        "failed_rows": report["failed_rows"],
        "rejected_negative_cases": report["rejected_negative_cases"],
        "real_inputs_mutated": False,
        "output": str(OUT),
    }, ensure_ascii=False, sort_keys=True))
    return 0 if report["success"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
