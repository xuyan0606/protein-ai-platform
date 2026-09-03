#!/usr/bin/env python3
"""Regression cases for controlled release-guard order validation."""

from __future__ import annotations

import argparse
import copy
import json
from datetime import datetime, timezone
from pathlib import Path

from validate_enzyme_agent_controlled_release_guard_order import (
    EXPECTED_ACTION_CONTRACT_SHA256,
    EXPECTED_COMMANDS,
    EXPECTED_EXECUTION_MODE,
    EXPECTED_OUTPUT_ARTIFACTS,
    EXPECTED_TOOL_CONTRACT_ID,
    EXPECTED_VALIDATOR_ARTIFACTS,
    LOCK_PATH,
    WAVE_SCRIPT,
    acquire_lock,
    sha256,
    validate_release_guard_action,
    write_json_atomic,
)


AI_ROOT = Path(__file__).resolve().parents[1]
VALIDATOR = AI_ROOT / "scripts" / "validate_enzyme_agent_controlled_release_guard_order.py"
OUT = AI_ROOT / "reports" / "enzyme_agent_controlled_release_guard_order_regression_report.json"


def base_action() -> dict[str, object]:
    return {
        "tool_contract_id": EXPECTED_TOOL_CONTRACT_ID,
        "execution_mode": EXPECTED_EXECUTION_MODE,
        "commands": copy.deepcopy(EXPECTED_COMMANDS),
        "output_artifacts": list(EXPECTED_OUTPUT_ARTIFACTS),
        "validator_artifacts": list(EXPECTED_VALIDATOR_ARTIFACTS),
    }


def build_report(output_path: Path, lock_path: Path) -> dict[str, object]:
    cases: list[dict[str, object]] = []
    control = base_action()
    cases.append({"case_id": "control_exact_order", "expected_valid": True, "failures": validate_release_guard_action(control)})

    missing_current_receipt = base_action()
    missing_current_receipt["commands"] = [
        command
        for command in missing_current_receipt["commands"]  # type: ignore[index]
        if command != ["scripts/validate_stage25_operator_docs_sync_current_receipt.py"]
    ]
    cases.append({"case_id": "missing_current_receipt_validation_rejected", "expected_valid": False, "failures": validate_release_guard_action(missing_current_receipt)})

    missing_safety_atomicity = base_action()
    missing_safety_atomicity["commands"] = [
        command
        for command in missing_safety_atomicity["commands"]  # type: ignore[index]
        if command != ["scripts/validate_local_release_safety_guard_links_atomicity_regression.py"]
    ]
    cases.append({"case_id": "missing_safety_atomicity_refresh_rejected", "expected_valid": False, "failures": validate_release_guard_action(missing_safety_atomicity)})

    swapped_consistency_release = base_action()
    commands = swapped_consistency_release["commands"]  # type: ignore[index]
    commands[21], commands[22] = commands[22], commands[21]  # type: ignore[index]
    cases.append({"case_id": "swapped_consistency_release_rejected", "expected_valid": False, "failures": validate_release_guard_action(swapped_consistency_release)})

    missing_guard_output = base_action()
    missing_guard_output["output_artifacts"] = [
        artifact
        for artifact in missing_guard_output["output_artifacts"]  # type: ignore[index]
        if artifact != "reports/local_release_safety_guard_link_validation_report.json"
    ]
    cases.append({"case_id": "missing_guard_output_artifact_rejected", "expected_valid": False, "failures": validate_release_guard_action(missing_guard_output)})

    forged_validator = base_action()
    forged_validator["validator_artifacts"] = ["reports/forged_guard_link_validation_report.json"]
    cases.append({"case_id": "forged_validator_artifact_rejected", "expected_valid": False, "failures": validate_release_guard_action(forged_validator)})

    missing_terminal_manifest = base_action()
    del missing_terminal_manifest["commands"][-2]  # type: ignore[index]
    cases.append({"case_id": "missing_terminal_manifest_rejected", "expected_valid": False, "failures": validate_release_guard_action(missing_terminal_manifest)})

    swapped_terminal_manifest_live = base_action()
    terminal_commands = swapped_terminal_manifest_live["commands"]  # type: ignore[index]
    terminal_commands[-2], terminal_commands[-1] = terminal_commands[-1], terminal_commands[-2]  # type: ignore[index]
    cases.append({"case_id": "swapped_terminal_manifest_live_rejected", "expected_valid": False, "failures": validate_release_guard_action(swapped_terminal_manifest_live)})

    for case in cases:
        failures = case["failures"]
        case["observed_valid"] = not failures
        case["passed"] = case["observed_valid"] == case["expected_valid"]
    passed_rows = sum(1 for case in cases if case["passed"])
    failed_rows = len(cases) - passed_rows
    rejected_negative_cases = sum(1 for case in cases if case["expected_valid"] is False and case["observed_valid"] is False)
    regression_script = Path(__file__).resolve()
    return {
        "schema_version": 2,
        "mode": "enzyme-agent-controlled-release-guard-order-regression-v2",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "local_only": True,
        "success": failed_rows == 0,
        "regression_script_path": str(regression_script),
        "regression_script_sha256": sha256(regression_script),
        "validator_script_path": str(VALIDATOR.resolve()),
        "validator_script_sha256": sha256(VALIDATOR),
        "wave_script_path": str(WAVE_SCRIPT.resolve()),
        "wave_script_sha256": sha256(WAVE_SCRIPT),
        "output_path": str(output_path),
        "lock_path": str(lock_path),
        "lock_acquired": True,
        "atomic_commit": True,
        "expected_action_contract_sha256": EXPECTED_ACTION_CONTRACT_SHA256,
        "case_rows": len(cases),
        "passed_rows": passed_rows,
        "failed_rows": failed_rows,
        "rejected_negative_cases": rejected_negative_cases,
        "control_valid": cases[0]["observed_valid"],
        "isolated_fixture": True,
        "real_inputs_mutated": False,
        "cases": cases,
        "safe_for_model_claim": False,
        "release_ready": False,
        "policy": "Isolated fixtures verify exact release-guard action semantics and terminal convergence without mutating canonical inputs.",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Run controlled release-guard order regression")
    parser.add_argument("--output", type=Path, default=OUT)
    parser.add_argument("--lock-path", type=Path, default=LOCK_PATH)
    parser.add_argument("--lock-timeout-seconds", type=float, default=30.0)
    parser.add_argument("--fail-before-replace", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()
    output_path = args.output.resolve()
    lock_path = args.lock_path.resolve()
    lock_handle = acquire_lock(lock_path, args.lock_timeout_seconds)
    if lock_handle is None:
        print(json.dumps({"success": False, "error": "release_guard_order_regression_lock_timeout", "output_preserved": output_path.exists()}, ensure_ascii=False, sort_keys=True))
        return 1
    try:
        report = build_report(output_path, lock_path)
        write_json_atomic(output_path, report, fail_before_replace=args.fail_before_replace)
    except Exception as exc:
        lock_handle.close()
        print(json.dumps({"success": False, "error": f"release_guard_order_regression_commit_failed:{type(exc).__name__}:{exc}", "output": str(output_path)}, ensure_ascii=False, sort_keys=True))
        return 1
    lock_handle.close()
    print(json.dumps({
        "success": report["success"],
        "case_rows": report["case_rows"],
        "passed_rows": report["passed_rows"],
        "failed_rows": report["failed_rows"],
        "rejected_negative_cases": report["rejected_negative_cases"],
        "real_inputs_mutated": report["real_inputs_mutated"],
        "output": str(output_path),
    }, ensure_ascii=False, sort_keys=True))
    return 0 if report["success"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
