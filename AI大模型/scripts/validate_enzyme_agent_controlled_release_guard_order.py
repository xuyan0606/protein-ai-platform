#!/usr/bin/env python3
"""Validate and atomically attest controlled release-guard command ordering."""

from __future__ import annotations

import argparse
import fcntl
import hashlib
import importlib.util
import json
import os
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
WAVE_SCRIPT = AI_ROOT / "scripts" / "run_enzyme_agent_controlled_execution_wave.py"
OUT = AI_ROOT / "reports" / "enzyme_agent_controlled_release_guard_order_validation_report.json"
LOCK_PATH = AI_ROOT / "reports" / ".enzyme_agent_controlled_release_guard_order.lock"

SCHEMA_VERSION = 2
MODE = "enzyme-agent-controlled-release-guard-order-validation-v2"
EXPECTED_TOOL_CONTRACT_ID = "tool_local_release_safety_guard_links"
EXPECTED_EXECUTION_MODE = "local_script"
EXPECTED_COMMANDS = [
    ["scripts/validate_enzyme_agent_controlled_release_guard_order.py"],
    ["scripts/validate_enzyme_agent_controlled_release_guard_order_regression.py"],
    ["scripts/validate_enzyme_agent_controlled_release_guard_order_current.py"],
    ["scripts/validate_enzyme_agent_controlled_release_guard_order_current_regression.py"],
    ["scripts/validate_enzyme_agent_controlled_release_guard_order_atomicity_regression.py"],
    ["scripts/validate_local_release_consistency_semantic_policy.py"],
    ["scripts/validate_local_release_consistency_semantic_policy_regression.py"],
    ["scripts/validate_local_release_consistency_semantic_policy_current.py"],
    ["scripts/validate_local_release_consistency_semantic_policy_current_regression.py"],
    ["scripts/validate_local_release_consistency_semantic_policy_atomicity_regression.py"],
    ["scripts/validate_local_release_consistency_receipt_atomicity_regression.py"],
    ["scripts/validate_local_release_safety_guard_links_atomicity_regression.py"],
    ["scripts/build_data_lake_manifest.py"],
    ["scripts/validate_data_lake_live_content_integrity.py"],
    ["scripts/build_claim_readiness_matrix.py"],
    ["scripts/validate_claim_readiness_matrix_fail_closed_policy.py"],
    ["scripts/validate_claim_readiness_matrix_fail_closed_policy_current.py"],
    ["scripts/validate_claim_promotion_decisions.py"],
    ["scripts/build_local_release_manifest.py"],
    ["scripts/sync_stage25_operator_docs_dynamic_status.py"],
    ["scripts/validate_stage25_operator_docs_sync_current_receipt.py"],
    ["scripts/build_data_lake_manifest.py"],
    ["scripts/validate_data_lake_live_content_integrity.py"],
    ["scripts/build_claim_readiness_matrix.py"],
    ["scripts/validate_claim_readiness_matrix_fail_closed_policy.py"],
    ["scripts/validate_claim_readiness_matrix_fail_closed_policy_current.py"],
    ["scripts/validate_claim_promotion_decisions.py"],
    ["scripts/build_local_release_manifest.py"],
    ["scripts/validate_local_release_manifest_fail_closed_consistency.py"],
    ["scripts/validate_local_release_consistency_receipt_current.py"],
    ["scripts/validate_local_release_consistency_receipt_current_regression.py"],
    ["scripts/build_data_lake_manifest.py"],
    ["scripts/validate_data_lake_live_content_integrity.py"],
    ["scripts/build_claim_readiness_matrix.py"],
    ["scripts/validate_claim_readiness_matrix_fail_closed_policy.py"],
    ["scripts/validate_claim_readiness_matrix_fail_closed_policy_current.py"],
    ["scripts/validate_claim_promotion_decisions.py"],
    ["scripts/build_local_release_manifest.py"],
    ["scripts/validate_local_release_safety_guard_links.py"],
    ["scripts/build_data_lake_manifest.py"],
    ["scripts/validate_data_lake_live_content_integrity.py"],
]

EXPECTED_TERMINAL_CONVERGENCE = [
    ["scripts/validate_local_release_safety_guard_links.py"],
    ["scripts/build_data_lake_manifest.py"],
    ["scripts/validate_data_lake_live_content_integrity.py"],
]

EXPECTED_OUTPUT_ARTIFACTS = [
    "reports/enzyme_agent_controlled_release_guard_order_validation_report.json",
    "reports/enzyme_agent_controlled_release_guard_order_regression_report.json",
    "reports/enzyme_agent_controlled_release_guard_order_current_validation_report.json",
    "reports/enzyme_agent_controlled_release_guard_order_current_regression_report.json",
    "reports/enzyme_agent_controlled_release_guard_order_atomicity_regression_report.json",
    "reports/local_release_consistency_semantic_policy_validation_report.json",
    "reports/local_release_consistency_semantic_policy_regression_report.json",
    "reports/local_release_consistency_semantic_policy_current_validation_report.json",
    "reports/local_release_consistency_semantic_policy_current_regression_report.json",
    "reports/local_release_consistency_semantic_policy_atomicity_regression_report.json",
    "reports/local_release_consistency_receipt_atomicity_regression_report.json",
    "reports/local_release_safety_guard_links_atomicity_regression_report.json",
    "reports/data_lake_manifest.json",
    "reports/data_lake_live_content_integrity_validation_report.json",
    "reports/claim_readiness_matrix.json",
    "reports/claim_readiness_matrix_fail_closed_policy_validation_report.json",
    "reports/claim_readiness_matrix_fail_closed_policy_current_validation_report.json",
    "reports/claim_promotion_decision_validation_report.json",
    "reports/stage25_operator_docs_dynamic_status_sync_report.json",
    "reports/stage25_operator_docs_sync_current_receipt_validation_report.json",
    "reports/local_release_manifest.json",
    "reports/local_release_manifest_fail_closed_consistency_validation_report.json",
    "reports/local_release_consistency_receipt_current_validation_report.json",
    "reports/local_release_consistency_receipt_current_regression_report.json",
    "reports/local_release_safety_guard_link_validation_report.json",
]

EXPECTED_VALIDATOR_ARTIFACTS = [
    "reports/local_release_safety_guard_link_validation_report.json",
]

EXPECTED_ACTION_CONTRACT_SHA256 = "a2747cfadabad613eb3ab2e12d3fed65f6d77d8f0b79bec7d0fd78b8ea5e9cc0"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def canonical_sha256(payload: Any) -> str:
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def action_contract_payload(action: dict[str, Any]) -> dict[str, Any]:
    return {
        "tool_contract_id": action.get("tool_contract_id"),
        "execution_mode": action.get("execution_mode"),
        "commands": action.get("commands"),
        "output_artifacts": action.get("output_artifacts"),
        "validator_artifacts": action.get("validator_artifacts"),
    }


def expected_action() -> dict[str, Any]:
    return {
        "tool_contract_id": EXPECTED_TOOL_CONTRACT_ID,
        "execution_mode": EXPECTED_EXECUTION_MODE,
        "commands": EXPECTED_COMMANDS,
        "output_artifacts": EXPECTED_OUTPUT_ARTIFACTS,
        "validator_artifacts": EXPECTED_VALIDATOR_ARTIFACTS,
    }


def load_wave_module(path: Path) -> Any:
    spec = importlib.util.spec_from_file_location("run_enzyme_agent_controlled_execution_wave", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def acquire_lock(path: Path, timeout_seconds: float):
    path.parent.mkdir(parents=True, exist_ok=True)
    handle = path.open("a+")
    deadline = time.monotonic() + max(timeout_seconds, 0.0)
    while True:
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            handle.seek(0)
            handle.truncate()
            handle.write(f"pid={os.getpid()}\n")
            handle.flush()
            os.fsync(handle.fileno())
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
    descriptor, temp_name = tempfile.mkstemp(prefix=f".{path.name}.order-", dir=path.parent)
    temp_path = Path(temp_name)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(encoded)
            handle.flush()
            os.fsync(handle.fileno())
        if path.exists():
            os.chmod(temp_path, path.stat().st_mode)
        if fail_before_replace:
            raise RuntimeError("simulated_release_guard_order_failure_before_replace")
        os.replace(temp_path, path)
        fsync_directory(path.parent)
    finally:
        if temp_path.exists():
            temp_path.unlink()


def validate_release_guard_action(action: dict[str, Any]) -> list[dict[str, Any]]:
    failures: list[dict[str, Any]] = []
    expected = expected_action()
    checks = (
        ("release_guard_tool_contract_id_exact", action.get("tool_contract_id"), EXPECTED_TOOL_CONTRACT_ID),
        ("release_guard_execution_mode_exact", action.get("execution_mode"), EXPECTED_EXECUTION_MODE),
        ("release_guard_command_order_exact", action.get("commands"), EXPECTED_COMMANDS),
        ("release_guard_output_artifacts_exact", action.get("output_artifacts"), EXPECTED_OUTPUT_ARTIFACTS),
        ("release_guard_validator_artifacts_exact", action.get("validator_artifacts"), EXPECTED_VALIDATOR_ARTIFACTS),
    )
    for check, observed, expected_value in checks:
        if observed != expected_value:
            failures.append({"check": check, "observed": observed, "expected": expected_value})
    observed_commands = action.get("commands")
    observed_terminal = (
        observed_commands[-len(EXPECTED_TERMINAL_CONVERGENCE):]
        if isinstance(observed_commands, list)
        else None
    )
    if observed_terminal != EXPECTED_TERMINAL_CONVERGENCE:
        failures.append({
            "check": "release_guard_terminal_convergence_exact",
            "observed": observed_terminal,
            "expected": EXPECTED_TERMINAL_CONVERGENCE,
        })
    expected_digest = canonical_sha256(action_contract_payload(expected))
    if expected_digest != EXPECTED_ACTION_CONTRACT_SHA256:
        failures.append({
            "check": "release_guard_expected_action_contract_sha256",
            "observed": expected_digest,
            "expected": EXPECTED_ACTION_CONTRACT_SHA256,
        })
    return failures


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate controlled release-guard action order")
    parser.add_argument("--wave-script", type=Path, default=WAVE_SCRIPT)
    parser.add_argument("--output", type=Path, default=OUT)
    parser.add_argument("--lock-path", type=Path, default=LOCK_PATH)
    parser.add_argument("--lock-timeout-seconds", type=float, default=30.0)
    parser.add_argument("--fail-before-replace", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()

    wave_path = args.wave_script.resolve()
    output_path = args.output.resolve()
    lock_path = args.lock_path.resolve()
    lock_handle = acquire_lock(lock_path, args.lock_timeout_seconds)
    if lock_handle is None:
        print(json.dumps({
            "success": False,
            "error": "release_guard_order_lock_timeout",
            "lock_path": str(lock_path),
            "output_preserved": output_path.exists(),
        }, ensure_ascii=False, sort_keys=True))
        return 1

    try:
        failures: list[dict[str, Any]] = []
        action: dict[str, Any] = {}
        if not wave_path.is_file():
            failures.append({"check": "wave_script_exists", "observed": str(wave_path), "expected": "file"})
        else:
            try:
                module = load_wave_module(wave_path)
                action = (module.ACTION_COMMANDS or {}).get("act_release_guard_links") or {}
            except Exception as exc:
                failures.append({"check": "wave_script_loads", "observed": f"{type(exc).__name__}:{exc}", "expected": "loadable"})
        failures.extend(validate_release_guard_action(action))
        observed_payload = action_contract_payload(action)
        report = {
            "schema_version": SCHEMA_VERSION,
            "mode": MODE,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "local_only": True,
            "success": not failures,
            "action_id": "act_release_guard_links",
            "validator_script_path": str(Path(__file__).resolve()),
            "validator_script_sha256": sha256(Path(__file__).resolve()),
            "wave_script_path": str(wave_path),
            "wave_script_sha256": sha256(wave_path) if wave_path.is_file() else None,
            "output_path": str(output_path),
            "lock_path": str(lock_path),
            "lock_acquired": True,
            "atomic_commit": True,
            "expected_action_contract_sha256": EXPECTED_ACTION_CONTRACT_SHA256,
            "observed_action_contract_sha256": canonical_sha256(observed_payload),
            "expected_command_count": len(EXPECTED_COMMANDS),
            "observed_command_count": len(action.get("commands") or []),
            "expected_output_artifact_count": len(EXPECTED_OUTPUT_ARTIFACTS),
            "observed_output_artifact_count": len(action.get("output_artifacts") or []),
            "failure_count": len(failures),
            "failures": failures,
            "safe_for_model_claim": False,
            "release_ready": False,
            "policy": "The controlled release-guard wave must end with safety, manifest and live convergence. This structural receipt never grants release readiness.",
        }
        write_json_atomic(output_path, report, fail_before_replace=args.fail_before_replace)
    except Exception as exc:
        lock_handle.close()
        print(json.dumps({
            "success": False,
            "error": f"release_guard_order_commit_failed:{type(exc).__name__}:{exc}",
            "output": str(output_path),
        }, ensure_ascii=False, sort_keys=True))
        return 1
    lock_handle.close()
    print(json.dumps({
        "success": report["success"],
        "expected_command_count": report["expected_command_count"],
        "observed_command_count": report["observed_command_count"],
        "failures": report["failure_count"],
        "output": str(output_path),
    }, ensure_ascii=False, sort_keys=True))
    return 0 if report["success"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
