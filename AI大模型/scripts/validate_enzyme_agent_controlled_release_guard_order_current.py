#!/usr/bin/env python3
"""Bind controlled release-guard order proofs to current scripts and Wave bytes."""

from __future__ import annotations

import argparse
import fcntl
import hashlib
import importlib.util
import json
import os
import tempfile
import time
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
VALIDATION_REPORT = AI_ROOT / "reports" / "enzyme_agent_controlled_release_guard_order_validation_report.json"
REGRESSION_REPORT = AI_ROOT / "reports" / "enzyme_agent_controlled_release_guard_order_regression_report.json"
VALIDATOR_SCRIPT = AI_ROOT / "scripts" / "validate_enzyme_agent_controlled_release_guard_order.py"
REGRESSION_SCRIPT = AI_ROOT / "scripts" / "validate_enzyme_agent_controlled_release_guard_order_regression.py"
WAVE_SCRIPT = AI_ROOT / "scripts" / "run_enzyme_agent_controlled_execution_wave.py"
LOCK_PATH = AI_ROOT / "reports" / ".enzyme_agent_controlled_release_guard_order.lock"
OUTPUT = AI_ROOT / "reports" / "enzyme_agent_controlled_release_guard_order_current_validation_report.json"

EXPECTED_ACTION_CONTRACT_SHA256 = "a2747cfadabad613eb3ab2e12d3fed65f6d77d8f0b79bec7d0fd78b8ea5e9cc0"
EXPECTED_COMMAND_COUNT = 41
EXPECTED_OUTPUT_ARTIFACT_COUNT = 25


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def canonical_sha256(payload: Any) -> str:
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain an object")
    return data


def load_wave_action(path: Path) -> dict[str, Any]:
    spec = importlib.util.spec_from_file_location("controlled_release_guard_current_wave", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return (module.ACTION_COMMANDS or {}).get("act_release_guard_links") or {}


def action_contract_payload(action: dict[str, Any]) -> dict[str, Any]:
    return {
        "tool_contract_id": action.get("tool_contract_id"),
        "execution_mode": action.get("execution_mode"),
        "commands": action.get("commands"),
        "output_artifacts": action.get("output_artifacts"),
        "validator_artifacts": action.get("validator_artifacts"),
    }


def add_check(failures: list[dict[str, Any]], check: str, observed: Any, expected: Any) -> None:
    if observed != expected:
        failures.append({"check": check, "observed": observed, "expected": expected})


def validate_order_proofs_current(
    validation: dict[str, Any],
    regression: dict[str, Any],
    *,
    validation_report_path: Path,
    regression_report_path: Path,
    validator_script_path: Path,
    regression_script_path: Path,
    wave_script_path: Path,
    expected_lock_path: Path,
) -> tuple[list[dict[str, Any]], str | None]:
    failures: list[dict[str, Any]] = []
    files = {
        "validation_report": validation_report_path,
        "regression_report": regression_report_path,
        "validator_script": validator_script_path,
        "regression_script": regression_script_path,
        "wave_script": wave_script_path,
    }
    for name, path in files.items():
        if not path.is_file():
            failures.append({"check": f"{name}_exists", "observed": str(path), "expected": "file"})

    live_action_sha: str | None = None
    if wave_script_path.is_file():
        try:
            live_action_sha = canonical_sha256(action_contract_payload(load_wave_action(wave_script_path)))
        except Exception as exc:
            failures.append({"check": "wave_action_loads", "observed": f"{type(exc).__name__}:{exc}", "expected": "loadable"})

    validation_expected = {
        "schema_version": 2,
        "mode": "enzyme-agent-controlled-release-guard-order-validation-v2",
        "success": True,
        "action_id": "act_release_guard_links",
        "validator_script_path": str(validator_script_path.resolve()),
        "validator_script_sha256": sha256(validator_script_path) if validator_script_path.is_file() else None,
        "wave_script_path": str(wave_script_path.resolve()),
        "wave_script_sha256": sha256(wave_script_path) if wave_script_path.is_file() else None,
        "output_path": str(validation_report_path.resolve()),
        "lock_path": str(expected_lock_path.resolve()),
        "lock_acquired": True,
        "atomic_commit": True,
        "expected_action_contract_sha256": EXPECTED_ACTION_CONTRACT_SHA256,
        "observed_action_contract_sha256": EXPECTED_ACTION_CONTRACT_SHA256,
        "expected_command_count": EXPECTED_COMMAND_COUNT,
        "observed_command_count": EXPECTED_COMMAND_COUNT,
        "expected_output_artifact_count": EXPECTED_OUTPUT_ARTIFACT_COUNT,
        "observed_output_artifact_count": EXPECTED_OUTPUT_ARTIFACT_COUNT,
        "failure_count": 0,
        "safe_for_model_claim": False,
        "release_ready": False,
    }
    for field, expected in validation_expected.items():
        add_check(failures, f"validation_{field}_current", validation.get(field), expected)
    add_check(failures, "validation_failures_empty", validation.get("failures") or [], [])

    regression_expected = {
        "schema_version": 2,
        "mode": "enzyme-agent-controlled-release-guard-order-regression-v2",
        "success": True,
        "regression_script_path": str(regression_script_path.resolve()),
        "regression_script_sha256": sha256(regression_script_path) if regression_script_path.is_file() else None,
        "validator_script_path": str(validator_script_path.resolve()),
        "validator_script_sha256": sha256(validator_script_path) if validator_script_path.is_file() else None,
        "wave_script_path": str(wave_script_path.resolve()),
        "wave_script_sha256": sha256(wave_script_path) if wave_script_path.is_file() else None,
        "output_path": str(regression_report_path.resolve()),
        "lock_path": str(expected_lock_path.resolve()),
        "lock_acquired": True,
        "atomic_commit": True,
        "expected_action_contract_sha256": EXPECTED_ACTION_CONTRACT_SHA256,
        "case_rows": 8,
        "passed_rows": 8,
        "failed_rows": 0,
        "rejected_negative_cases": 7,
        "control_valid": True,
        "isolated_fixture": True,
        "real_inputs_mutated": False,
        "safe_for_model_claim": False,
        "release_ready": False,
    }
    for field, expected in regression_expected.items():
        add_check(failures, f"regression_{field}_current", regression.get(field), expected)
    add_check(failures, "live_action_contract_sha256_current", live_action_sha, EXPECTED_ACTION_CONTRACT_SHA256)
    return failures, live_action_sha


def acquire_lock(path: Path, timeout_seconds: float):
    path.parent.mkdir(parents=True, exist_ok=True)
    handle = path.open("a+")
    deadline = time.monotonic() + max(timeout_seconds, 0.0)
    while True:
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            return handle
        except BlockingIOError:
            if time.monotonic() >= deadline:
                handle.close()
                return None
            time.sleep(0.05)


def fsync_directory(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def write_json_atomic(path: Path, payload: dict[str, Any], *, fail_before_replace: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    encoded = (json.dumps(payload, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    descriptor, temp_name = tempfile.mkstemp(prefix=f".{path.name}.current-", dir=path.parent)
    temp_path = Path(temp_name)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(encoded)
            handle.flush()
            os.fsync(handle.fileno())
        if path.exists():
            os.chmod(temp_path, path.stat().st_mode)
        if fail_before_replace:
            raise RuntimeError("simulated_release_guard_order_current_failure_before_replace")
        os.replace(temp_path, path)
        fsync_directory(path.parent)
    finally:
        if temp_path.exists():
            temp_path.unlink()


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate current controlled release-guard order proofs")
    parser.add_argument("--validation-report", type=Path, default=VALIDATION_REPORT)
    parser.add_argument("--regression-report", type=Path, default=REGRESSION_REPORT)
    parser.add_argument("--validator-script", type=Path, default=VALIDATOR_SCRIPT)
    parser.add_argument("--regression-script", type=Path, default=REGRESSION_SCRIPT)
    parser.add_argument("--wave-script", type=Path, default=WAVE_SCRIPT)
    parser.add_argument("--expected-lock-path", type=Path, default=LOCK_PATH)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    parser.add_argument("--lock-timeout-seconds", type=float, default=30.0)
    parser.add_argument("--fail-before-replace", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()

    validation_path = args.validation_report.resolve()
    regression_path = args.regression_report.resolve()
    validator_path = args.validator_script.resolve()
    regression_script_path = args.regression_script.resolve()
    wave_path = args.wave_script.resolve()
    lock_path = args.expected_lock_path.resolve()
    output_path = args.output.resolve()
    lock_handle = acquire_lock(lock_path, args.lock_timeout_seconds)
    if lock_handle is None:
        print(json.dumps({"success": False, "error": "release_guard_order_current_lock_timeout", "output_preserved": output_path.exists()}, ensure_ascii=False, sort_keys=True))
        return 1
    try:
        validation = load_json(validation_path) if validation_path.is_file() else {}
        regression = load_json(regression_path) if regression_path.is_file() else {}
        failures, live_action_sha = validate_order_proofs_current(
            validation,
            regression,
            validation_report_path=validation_path,
            regression_report_path=regression_path,
            validator_script_path=validator_path,
            regression_script_path=regression_script_path,
            wave_script_path=wave_path,
            expected_lock_path=lock_path,
        )
        current_script = Path(__file__).resolve()
        report = {
            "schema_version": 1,
            "mode": "enzyme-agent-controlled-release-guard-order-current-v1",
            "success": not failures,
            "validation_report_path": str(validation_path),
            "validation_report_sha256": sha256(validation_path) if validation_path.is_file() else None,
            "regression_report_path": str(regression_path),
            "regression_report_sha256": sha256(regression_path) if regression_path.is_file() else None,
            "validator_script_path": str(validator_path),
            "validator_script_sha256": sha256(validator_path) if validator_path.is_file() else None,
            "regression_script_path": str(regression_script_path),
            "regression_script_sha256": sha256(regression_script_path) if regression_script_path.is_file() else None,
            "wave_script_path": str(wave_path),
            "wave_script_sha256": sha256(wave_path) if wave_path.is_file() else None,
            "current_validator_script_path": str(current_script),
            "current_validator_script_sha256": sha256(current_script),
            "current_output_path": str(output_path),
            "current_lock_path": str(lock_path),
            "current_lock_acquired": True,
            "current_atomic_commit": True,
            "expected_action_contract_sha256": EXPECTED_ACTION_CONTRACT_SHA256,
            "observed_action_contract_sha256": live_action_sha,
            "failure_count": len(failures),
            "failures": failures,
            "safe_for_model_claim": False,
            "release_ready": False,
        }
        write_json_atomic(output_path, report, fail_before_replace=args.fail_before_replace)
    except Exception as exc:
        lock_handle.close()
        print(json.dumps({"success": False, "error": f"release_guard_order_current_commit_failed:{type(exc).__name__}:{exc}", "output": str(output_path)}, ensure_ascii=False, sort_keys=True))
        return 1
    lock_handle.close()
    print(json.dumps({"success": report["success"], "failure_count": report["failure_count"], "output": str(output_path)}, ensure_ascii=False, sort_keys=True))
    return 0 if report["success"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
