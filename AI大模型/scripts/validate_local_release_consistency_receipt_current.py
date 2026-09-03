#!/usr/bin/env python3
"""Bind a local-release consistency receipt to current semantic inputs."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
from typing import Any

try:
    import validate_local_release_manifest_fail_closed_consistency as target
    from local_release_consistency_receipt_contract import (
        CONTRACT_VERSION,
        INPUT_ROLES,
        build_semantic_inputs,
        test_vector_sha256,
    )
except ModuleNotFoundError:
    from scripts import validate_local_release_manifest_fail_closed_consistency as target
    from scripts.local_release_consistency_receipt_contract import (
        CONTRACT_VERSION,
        INPUT_ROLES,
        build_semantic_inputs,
        test_vector_sha256,
    )

try:
    from validate_local_release_consistency_semantic_policy_current import validate_policy_report_current
except ModuleNotFoundError:
    from scripts.validate_local_release_consistency_semantic_policy_current import validate_policy_report_current


AI_ROOT = Path(__file__).resolve().parents[1]
RECEIPT = AI_ROOT / "reports" / "local_release_manifest_fail_closed_consistency_validation_report.json"
VALIDATOR = AI_ROOT / "scripts" / "validate_local_release_manifest_fail_closed_consistency.py"
SEMANTIC_CONTRACT = AI_ROOT / "scripts" / "local_release_consistency_receipt_contract.py"
RELEASE = AI_ROOT / "reports" / "local_release_manifest.json"
DATA_LAKE = AI_ROOT / "reports" / "data_lake_manifest.json"
LIVE_INTEGRITY = AI_ROOT / "reports" / "data_lake_live_content_integrity_validation_report.json"
CONTRACT_POLICY = AI_ROOT / "reports" / "data_lake_release_input_contract_policy_validation_report.json"
SEMANTIC_POLICY = AI_ROOT / "reports" / "local_release_consistency_semantic_policy_validation_report.json"
SEMANTIC_POLICY_LOCK = AI_ROOT / "reports" / ".local_release_consistency_semantic_policy.lock"
LOCK_PATH = AI_ROOT / "reports" / ".local_release_manifest_fail_closed_consistency.lock"
OUTPUT = AI_ROOT / "reports" / "local_release_consistency_receipt_current_validation_report.json"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def add_check(failures: list[dict[str, Any]], check: str, observed: Any, expected: Any) -> None:
    if observed != expected:
        failures.append({"check": check, "observed": observed, "expected": expected})


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate current local-release consistency receipt")
    parser.add_argument("--receipt", type=Path, default=RECEIPT)
    parser.add_argument("--validator", type=Path, default=VALIDATOR)
    parser.add_argument("--semantic-contract", type=Path, default=SEMANTIC_CONTRACT)
    parser.add_argument("--release", type=Path, default=RELEASE)
    parser.add_argument("--data-lake", type=Path, default=DATA_LAKE)
    parser.add_argument("--live-integrity", type=Path, default=LIVE_INTEGRITY)
    parser.add_argument("--contract-policy", type=Path, default=CONTRACT_POLICY)
    parser.add_argument("--semantic-policy", type=Path, default=SEMANTIC_POLICY)
    parser.add_argument("--expected-lock-path", type=Path, default=LOCK_PATH)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    parser.add_argument("--lock-timeout-seconds", type=float, default=30.0)
    args = parser.parse_args()

    receipt_path = args.receipt.resolve()
    validator_path = args.validator.resolve()
    semantic_contract_path = args.semantic_contract.resolve()
    release_path = args.release.resolve()
    data_lake_path = args.data_lake.resolve()
    live_integrity_path = args.live_integrity.resolve()
    contract_policy_path = args.contract_policy.resolve()
    semantic_policy_path = args.semantic_policy.resolve()
    lock_path = args.expected_lock_path.resolve()
    output_path = args.output.resolve()

    lock_handle = target.acquire_receipt_lock(lock_path, args.lock_timeout_seconds)
    if lock_handle is None:
        print(json.dumps({"success": False, "error": "local_release_consistency_current_lock_timeout", "lock_path": str(lock_path)}, ensure_ascii=False))
        return 1

    failures: list[dict[str, Any]] = []
    required_paths = {
        "receipt": receipt_path,
        "validator": validator_path,
        "semantic_contract": semantic_contract_path,
        "release": release_path,
        "data_lake": data_lake_path,
        "live_integrity": live_integrity_path,
        "contract_policy": contract_policy_path,
        "semantic_policy": semantic_policy_path,
    }
    for name, path in required_paths.items():
        if not path.is_file():
            failures.append({"check": f"{name}_exists", "observed": str(path), "expected": "file"})

    receipt = target.load_json(receipt_path)
    release, _ = target.load_json_snapshot(release_path)
    data_lake, _ = target.load_json_snapshot(data_lake_path)
    live_integrity, _ = target.load_json_snapshot(live_integrity_path)
    contract_policy, _ = target.load_json_snapshot(contract_policy_path)
    semantic_policy, _ = target.load_json_snapshot(semantic_policy_path)
    failures.extend(validate_policy_report_current(
        semantic_policy,
        policy_report_path=semantic_policy_path,
        policy_script_path=Path(__file__).resolve().parent / "validate_local_release_consistency_semantic_policy.py",
        contract_module_path=semantic_contract_path,
        expected_output_path=semantic_policy_path,
        expected_lock_path=SEMANTIC_POLICY_LOCK,
    ))
    current_semantic = build_semantic_inputs({
        "release": release,
        "data_lake": data_lake,
        "live_integrity": live_integrity,
        "contract_policy": contract_policy,
        "semantic_policy": semantic_policy,
    })
    terminal_deferred = os.environ.get("KWB_DEFER_SAFE_PIPELINE_TERMINAL") == "1"

    add_check(failures, "receipt_schema_version", receipt.get("schema_version"), 2)
    add_check(failures, "receipt_mode", receipt.get("mode"), "local_release_manifest_fail_closed_consistency")
    add_check(failures, "receipt_success", receipt.get("success"), True)
    add_check(failures, "receipt_failure_count_zero", receipt.get("failure_count"), 0)
    add_check(failures, "receipt_failures_empty", receipt.get("failures") or [], [])
    add_check(failures, "receipt_release_ready_false", receipt.get("release_ready"), False)
    add_check(failures, "receipt_safe_for_model_claim_false", receipt.get("safe_for_model_claim"), False)
    add_check(failures, "receipt_terminal_mode_current", receipt.get("safe_pipeline_terminal_deferred"), terminal_deferred)
    add_check(failures, "receipt_validator_path_current", receipt.get("validator_script_path"), str(validator_path))
    add_check(failures, "receipt_validator_sha256_current", receipt.get("validator_script_sha256"), sha256(validator_path) if validator_path.is_file() else None)
    add_check(failures, "receipt_semantic_contract_path_current", receipt.get("semantic_contract_module_path"), str(semantic_contract_path))
    add_check(failures, "receipt_semantic_contract_sha256_current", receipt.get("semantic_contract_module_sha256"), sha256(semantic_contract_path) if semantic_contract_path.is_file() else None)
    add_check(failures, "receipt_semantic_contract_version", receipt.get("semantic_contract_version"), CONTRACT_VERSION)
    add_check(failures, "receipt_semantic_test_vector", receipt.get("semantic_contract_test_vector_sha256"), test_vector_sha256())
    add_check(failures, "receipt_semantic_policy_sha256_current", receipt.get("semantic_policy_sha256"), sha256(semantic_policy_path) if semantic_policy_path.is_file() else None)
    add_check(failures, "receipt_output_path", receipt.get("output_path"), str(receipt_path))
    add_check(failures, "receipt_lock_path", receipt.get("lock_path"), str(lock_path))
    add_check(failures, "receipt_lock_acquired", receipt.get("lock_acquired"), True)
    add_check(failures, "receipt_atomic_commit", receipt.get("receipt_atomic_commit"), True)
    for field, path in (
        ("release_path", release_path),
        ("data_lake_path", data_lake_path),
        ("live_integrity_path", live_integrity_path),
        ("contract_policy_path", contract_policy_path),
        ("semantic_policy_path", semantic_policy_path),
    ):
        add_check(failures, f"receipt_{field}", receipt.get(field), str(path))
    add_check(failures, "semantic_input_rows", receipt.get("semantic_input_rows"), len(INPUT_ROLES))
    add_check(failures, "semantic_inputs_exact_current", receipt.get("semantic_inputs"), current_semantic["rows"])
    add_check(failures, "semantic_inputs_sha256_current", receipt.get("semantic_inputs_sha256"), current_semantic["sha256"])

    current_script = Path(__file__).resolve()
    report = {
        "schema_version": 1,
        "mode": "local_release_consistency_receipt_current",
        "success": not failures,
        "receipt_path": str(receipt_path),
        "receipt_sha256": sha256(receipt_path) if receipt_path.is_file() else None,
        "validator_script_path": str(validator_path),
        "validator_script_sha256": sha256(validator_path) if validator_path.is_file() else None,
        "semantic_contract_module_path": str(semantic_contract_path),
        "semantic_contract_module_sha256": sha256(semantic_contract_path) if semantic_contract_path.is_file() else None,
        "semantic_contract_version": CONTRACT_VERSION,
        "semantic_contract_test_vector_sha256": test_vector_sha256(),
        "semantic_policy_path": str(semantic_policy_path),
        "semantic_policy_sha256": sha256(semantic_policy_path) if semantic_policy_path.is_file() else None,
        "semantic_input_rows": current_semantic["input_rows"],
        "semantic_inputs_sha256": current_semantic["sha256"],
        "current_validator_script_path": str(current_script),
        "current_validator_script_sha256": sha256(current_script),
        "current_output_path": str(output_path),
        "current_lock_path": str(lock_path),
        "current_atomic_commit": True,
        "safe_pipeline_terminal_deferred": terminal_deferred,
        "failure_count": len(failures),
        "failures": failures,
        "safe_for_model_claim": False,
        "release_ready": False,
    }
    target.write_json_atomic(output_path, report)
    lock_handle.close()
    print(json.dumps({"success": report["success"], "failure_count": report["failure_count"], "output": str(output_path)}, ensure_ascii=False, sort_keys=True))
    return 0 if report["success"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
