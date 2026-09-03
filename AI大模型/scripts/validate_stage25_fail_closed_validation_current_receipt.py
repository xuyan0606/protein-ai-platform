#!/usr/bin/env python3
"""Validate the Stage 25 runner receipt against its current command contract."""

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
RECEIPT = AI_ROOT / "reports" / "stage25_fail_closed_validation_run_report_20260806.json"
RUNNER = AI_ROOT / "scripts" / "run_stage25_fail_closed_validation_20260806.py"
OUTPUT = AI_ROOT / "reports" / "stage25_fail_closed_validation_current_receipt_validation_report.json"
LOCK_PATH = AI_ROOT / "reports" / "stage25_fail_closed_validation_run_20260806.lock"


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_runner(path: Path) -> ModuleType:
    spec = importlib.util.spec_from_file_location("stage25_current_runner", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load runner: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def add_check(failures: list[dict[str, Any]], check: str, observed: Any, expected: Any) -> None:
    if observed != expected:
        failures.append({"check": check, "observed": observed, "expected": expected})


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate current Stage 25 fail-closed receipt")
    parser.add_argument("--receipt", type=Path, default=RECEIPT)
    parser.add_argument("--runner", type=Path, default=RUNNER)
    parser.add_argument("--expected-output", type=Path, default=RECEIPT)
    parser.add_argument("--expected-lock-path", type=Path, default=LOCK_PATH)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    args = parser.parse_args()

    failures: list[dict[str, Any]] = []
    receipt = load_json(args.receipt)
    module: ModuleType | None = None
    if not args.receipt.is_file():
        failures.append({"check": "receipt_exists", "observed": str(args.receipt), "expected": "file"})
    if not args.runner.is_file():
        failures.append({"check": "runner_exists", "observed": str(args.runner), "expected": "file"})
    else:
        try:
            module = load_runner(args.runner)
        except Exception as exc:
            failures.append({"check": "runner_loads", "observed": f"{type(exc).__name__}:{exc}", "expected": "loadable"})

    commands = list(getattr(module, "COMMANDS", [])) if module else []
    expected_rows = len(commands)
    current_runner_sha = sha256(args.runner) if args.runner.is_file() else None
    current_contract_sha = module.command_contract_sha256(commands) if module else None
    command_rows = receipt.get("commands") if isinstance(receipt.get("commands"), list) else []

    add_check(failures, "receipt_run_valid", receipt.get("run_valid"), True)
    add_check(failures, "receipt_failure_count_zero", receipt.get("failure_count"), 0)
    add_check(failures, "receipt_failures_empty", receipt.get("failures") or [], [])
    add_check(failures, "receipt_lock_acquired", receipt.get("lock_acquired"), True)
    add_check(failures, "receipt_atomic_commit", receipt.get("receipt_atomic_commit"), True)
    add_check(failures, "runner_path_current", receipt.get("runner_script_path"), str(args.runner.resolve()))
    add_check(failures, "runner_sha_current", receipt.get("runner_script_sha256"), current_runner_sha)
    add_check(failures, "contract_version_current", receipt.get("command_contract_version"), getattr(module, "COMMAND_CONTRACT_VERSION", None) if module else None)
    add_check(failures, "contract_sha_current", receipt.get("command_contract_sha256"), current_contract_sha)
    add_check(failures, "command_count_current", receipt.get("command_count"), expected_rows)
    add_check(failures, "command_rows_current", len(command_rows), expected_rows)
    add_check(failures, "output_path_canonical", receipt.get("output_path"), str(args.expected_output.resolve()))
    add_check(failures, "lock_path_canonical", receipt.get("run_lock_path"), str(args.expected_lock_path.resolve()))
    add_check(failures, "all_command_results_success", [row.get("success") for row in command_rows if isinstance(row, dict)], [True] * expected_rows)
    add_check(failures, "safe_for_model_claim_false", receipt.get("safe_for_model_claim"), False)
    add_check(failures, "release_ready_false", receipt.get("release_ready"), False)

    report = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "success": not failures,
        "receipt_path": str(args.receipt.resolve()),
        "receipt_sha256": sha256(args.receipt) if args.receipt.is_file() else None,
        "runner_script_path": str(args.runner.resolve()),
        "runner_script_sha256": current_runner_sha,
        "command_contract_version": getattr(module, "COMMAND_CONTRACT_VERSION", None) if module else None,
        "command_contract_sha256": current_contract_sha,
        "command_rows": expected_rows,
        "failure_count": len(failures),
        "failures": failures,
        "safe_for_model_claim": False,
        "release_ready": False,
        "policy": "Read-only Stage 25 current-state proof; expected nonzero command returncodes are accepted only when their recorded command result is success=true.",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"success": report["success"], "command_rows": expected_rows, "failure_count": len(failures), "output": str(args.output)}, ensure_ascii=False))
    return 0 if report["success"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
