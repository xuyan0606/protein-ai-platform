#!/usr/bin/env python3
"""Validate that the safe-pipeline receipt matches the current runner contract."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
from datetime import datetime, timezone
from pathlib import Path
from types import ModuleType
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
RECEIPT = AI_ROOT / "reports" / "safe_training_pipeline_run.json"
RUNNER = AI_ROOT / "scripts" / "run_safe_training_pipeline.py"
OUTPUT = AI_ROOT / "reports" / "safe_training_pipeline_current_receipt_validation_report.json"
LOCK_PATH = AI_ROOT / "reports" / ".safe_training_pipeline.lock"


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_runner(path: Path) -> ModuleType:
    spec = importlib.util.spec_from_file_location("safe_pipeline_current_runner", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load runner: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def add_check(failures: list[dict[str, Any]], check: str, observed: Any, expected: Any) -> None:
    if observed != expected:
        failures.append({"check": check, "observed": observed, "expected": expected})


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate current safe-pipeline receipt")
    parser.add_argument("--receipt", type=Path, default=RECEIPT)
    parser.add_argument("--runner", type=Path, default=RUNNER)
    parser.add_argument("--expected-output", type=Path, default=RECEIPT)
    parser.add_argument("--expected-lock-path", type=Path, default=LOCK_PATH)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    args = parser.parse_args()

    failures: list[dict[str, Any]] = []
    receipt = load_json(args.receipt)
    runner: ModuleType | None = None
    if not args.receipt.is_file():
        failures.append({"check": "receipt_exists", "observed": str(args.receipt), "expected": "file"})
    if not args.runner.is_file():
        failures.append({"check": "runner_exists", "observed": str(args.runner), "expected": "file"})
    else:
        try:
            runner = load_runner(args.runner)
        except Exception as exc:
            failures.append({"check": "runner_loads", "observed": f"{type(exc).__name__}:{exc}", "expected": "loadable"})

    commands = list(getattr(runner, "COMMANDS", [])) if runner else []
    current_runner_sha = sha256(args.runner) if args.runner.is_file() else None
    current_contract_sha = runner.command_contract_sha256(commands) if runner else None
    expected_rows = len(commands)
    steps = receipt.get("steps") if isinstance(receipt.get("steps"), list) else []

    add_check(failures, "receipt_success", receipt.get("success"), True)
    add_check(failures, "receipt_lock_acquired", receipt.get("lock_acquired"), True)
    add_check(failures, "receipt_atomic_commit", receipt.get("receipt_atomic_commit"), True)
    add_check(failures, "receipt_failure_count_zero", receipt.get("failure_count"), 0)
    add_check(failures, "receipt_failures_empty", receipt.get("failures") or [], [])
    add_check(failures, "runner_script_path_current", receipt.get("runner_script_path"), str(args.runner.resolve()))
    add_check(failures, "runner_script_sha_current", receipt.get("runner_script_sha256"), current_runner_sha)
    add_check(failures, "command_contract_version_current", receipt.get("command_contract_version"), getattr(runner, "COMMAND_CONTRACT_VERSION", None) if runner else None)
    add_check(failures, "command_contract_sha_current", receipt.get("command_contract_sha256"), current_contract_sha)
    add_check(failures, "command_contract_rows_current", receipt.get("command_contract_rows"), expected_rows)
    add_check(failures, "receipt_output_path_canonical", receipt.get("output_path"), str(args.expected_output.resolve()))
    add_check(failures, "receipt_lock_path_canonical", receipt.get("lock_path"), str(args.expected_lock_path.resolve()))
    add_check(failures, "steps_requested_current", receipt.get("steps_requested"), expected_rows)
    add_check(failures, "steps_run_current", receipt.get("steps_run"), expected_rows)
    add_check(failures, "step_rows_current", len(steps), expected_rows)
    add_check(failures, "failed_steps_zero", receipt.get("failed_steps"), 0)
    nonzero_steps = [
        {"index": index, "command": row.get("command"), "returncode": row.get("returncode")}
        for index, row in enumerate(steps, start=1)
        if not isinstance(row, dict) or row.get("returncode") != 0
    ]
    add_check(failures, "all_step_returncodes_zero", nonzero_steps, [])
    add_check(failures, "safe_for_model_claim_false", receipt.get("safe_for_model_claim"), False)
    add_check(failures, "release_ready_false", receipt.get("release_ready"), False)

    report = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "success": not failures,
        "receipt_path": str(args.receipt.resolve()),
        "receipt_sha256": sha256(args.receipt) if args.receipt.is_file() else None,
        "runner_script_path": str(args.runner.resolve()),
        "runner_script_sha256": current_runner_sha,
        "command_contract_version": getattr(runner, "COMMAND_CONTRACT_VERSION", None) if runner else None,
        "command_contract_sha256": current_contract_sha,
        "command_rows": expected_rows,
        "step_rows": len(steps),
        "failure_count": len(failures),
        "failures": failures,
        "safe_for_model_claim": False,
        "release_ready": False,
        "policy": "Read-only current-state validation; success does not authorize training, model claims, release, or production actions.",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "success": report["success"],
        "command_rows": report["command_rows"],
        "step_rows": report["step_rows"],
        "failure_count": report["failure_count"],
        "output": str(args.output),
    }, ensure_ascii=False))
    return 0 if report["success"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
