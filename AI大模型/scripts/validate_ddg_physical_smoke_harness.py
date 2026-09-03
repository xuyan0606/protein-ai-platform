#!/usr/bin/env python3
"""Validate the physical ddG smoke harness stays honest and fail-closed."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
REPORT = AI_ROOT / "reports" / "ddg_physical_smoke_harness_report.json"
JSONL = AI_ROOT / "datasets" / "governance" / "ddg_physical_smoke_harness_plan.jsonl"
OUT = AI_ROOT / "reports" / "ddg_physical_smoke_harness_validation_report.json"
EXPECTED_BACKENDS = ["rosetta", "pyrosetta", "foldx"]
REQUIRED_ARTIFACTS = [
    "parameters.json",
    "input_structure.sha256",
    "mutation_list.json",
    "ddg_table.json",
    "runtime.log",
]


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    value = json.loads(path.read_text(encoding="utf-8"))
    return value if isinstance(value, dict) else {}


def load_jsonl(path: Path) -> tuple[list[dict[str, Any]], int]:
    rows: list[dict[str, Any]] = []
    invalid = 0
    if not path.exists():
        return rows, invalid
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError:
            invalid += 1
            continue
        if isinstance(value, dict):
            rows.append(value)
        else:
            invalid += 1
    return rows, invalid


def as_int(value: Any) -> int:
    if isinstance(value, bool):
        return int(value)
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def fail_if(condition: bool, failures: list[dict[str, Any]], check: str, observed: Any, expected: Any) -> None:
    if condition:
        failures.append({"check": check, "observed": observed, "expected": expected})


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate physical ddG smoke harness")
    parser.add_argument("--report", type=Path, default=REPORT)
    parser.add_argument("--jsonl", type=Path, default=JSONL)
    parser.add_argument("--output", type=Path, default=OUT)
    args = parser.parse_args()

    report = load_json(args.report)
    rows, invalid = load_jsonl(args.jsonl)
    failures: list[dict[str, Any]] = []
    backends = [str(row.get("backend")) for row in rows]

    fail_if(not report, failures, "report_present", str(args.report), "existing JSON report")
    fail_if(invalid != 0, failures, "jsonl_valid", invalid, 0)
    fail_if(backends != EXPECTED_BACKENDS, failures, "backend_order", backends, EXPECTED_BACKENDS)
    fail_if(as_int(report.get("harness_contract_rows")) != 3, failures, "harness_contract_rows", report.get("harness_contract_rows"), 3)
    fail_if(as_int(report.get("executor_contract_implemented_rows")) != 3, failures, "executor_contract_implemented_rows", report.get("executor_contract_implemented_rows"), 3)
    fail_if(as_int(report.get("thermompnn_proxy_allowed_rows")) != 0, failures, "thermompnn_proxy_allowed_rows_zero", report.get("thermompnn_proxy_allowed_rows"), 0)
    fail_if(report.get("safe_for_model_claim") is not False, failures, "safe_for_model_claim_false", report.get("safe_for_model_claim"), False)
    fail_if(report.get("release_ready") is not False, failures, "release_ready_false", report.get("release_ready"), False)

    approved_runtime_rows = as_int(report.get("approved_runtime_receipt_rows"))
    if approved_runtime_rows == 0:
        fail_if(as_int(report.get("can_execute_physical_smoke_now_rows")) != 0, failures, "can_execute_zero_without_receipt", report.get("can_execute_physical_smoke_now_rows"), 0)
        fail_if(as_int(report.get("execute_attempted_rows")) != 0, failures, "execute_attempted_zero_without_receipt", report.get("execute_attempted_rows"), 0)
        fail_if(as_int(report.get("ddg_job_executed_rows")) != 0, failures, "ddg_job_executed_zero_without_receipt", report.get("ddg_job_executed_rows"), 0)
        fail_if(as_int(report.get("physical_smoke_passed_rows")) != 0, failures, "physical_smoke_passed_zero_without_receipt", report.get("physical_smoke_passed_rows"), 0)
        fail_if(as_int(report.get("license_install_runtime_blocker_rows")) != 3, failures, "blocker_rows_three_without_receipt", report.get("license_install_runtime_blocker_rows"), 3)

    for row in rows:
        backend = row.get("backend")
        fail_if(row.get("executor_contract_status") != "implemented", failures, f"{backend}_contract_implemented", row.get("executor_contract_status"), "implemented")
        fail_if(row.get("thermompnn_proxy_allowed") is not False, failures, f"{backend}_thermompnn_proxy_false", row.get("thermompnn_proxy_allowed"), False)
        fail_if(row.get("safe_for_model_claim") is not False, failures, f"{backend}_safe_for_model_claim_false", row.get("safe_for_model_claim"), False)
        fail_if(row.get("release_ready") is not False, failures, f"{backend}_release_ready_false", row.get("release_ready"), False)
        artifact_contract = row.get("artifact_contract") if isinstance(row.get("artifact_contract"), dict) else {}
        fail_if(artifact_contract.get("required_artifacts") != REQUIRED_ARTIFACTS, failures, f"{backend}_artifact_contract", artifact_contract.get("required_artifacts"), REQUIRED_ARTIFACTS)
        if approved_runtime_rows == 0:
            fail_if(row.get("can_execute_physical_smoke_now") is not False, failures, f"{backend}_can_execute_false_without_receipt", row.get("can_execute_physical_smoke_now"), False)
            blockers = row.get("execution_blockers") if isinstance(row.get("execution_blockers"), list) else []
            for expected in ["approved_runtime_receipt_status_missing", "approved_runtime_receipt_row_missing"]:
                fail_if(expected not in blockers, failures, f"{backend}_{expected}_blocker_present", blockers, f"contains {expected}")

    validation = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "local_only": True,
        "success": not failures,
        "backends": backends,
        "harness_contract_rows": as_int(report.get("harness_contract_rows")),
        "executor_contract_implemented_rows": as_int(report.get("executor_contract_implemented_rows")),
        "approved_runtime_receipt_rows": approved_runtime_rows,
        "can_execute_physical_smoke_now_rows": as_int(report.get("can_execute_physical_smoke_now_rows")),
        "execute_attempted_rows": as_int(report.get("execute_attempted_rows")),
        "ddg_job_executed_rows": as_int(report.get("ddg_job_executed_rows")),
        "physical_smoke_passed_rows": as_int(report.get("physical_smoke_passed_rows")),
        "failures": failures,
        "safe_for_training_import": False,
        "safe_for_model_claim": False,
        "release_ready": False,
        "policy": "The non-human physical ddG smoke harness may be implemented, but physical ddG is not ready unless approved runtime receipt, ready execution plan and smoke artifacts are all present.",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(validation, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "success": validation["success"],
                "harness_contract_rows": validation["harness_contract_rows"],
                "executor_contract_implemented_rows": validation["executor_contract_implemented_rows"],
                "physical_smoke_passed_rows": validation["physical_smoke_passed_rows"],
                "failures": len(failures),
                "output": str(args.output),
            },
            ensure_ascii=False,
        )
    )
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
