#!/usr/bin/env python3
"""Bind the semantic policy report to current signer and contract bytes."""

from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import os
import tempfile
import time
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
POLICY_REPORT = AI_ROOT / "reports" / "local_release_consistency_semantic_policy_validation_report.json"
POLICY_SCRIPT = AI_ROOT / "scripts" / "validate_local_release_consistency_semantic_policy.py"
CONTRACT_MODULE = AI_ROOT / "scripts" / "local_release_consistency_receipt_contract.py"
LOCK_PATH = AI_ROOT / "reports" / ".local_release_consistency_semantic_policy.lock"
OUTPUT = AI_ROOT / "reports" / "local_release_consistency_semantic_policy_current_validation_report.json"

EXPECTED_VERSION = "local-release-consistency-semantic-input-v1"
EXPECTED_INPUT_ROLES = ["release", "data_lake", "live_integrity", "contract_policy", "semantic_policy"]
EXPECTED_DATA_LAKE_EXCLUDED = [
    "reports/local_release_consistency_receipt_current_regression_report.json",
    "reports/local_release_consistency_receipt_current_validation_report.json",
    "reports/local_release_safety_guard_links_current_regression_report.json",
    "reports/local_release_safety_guard_links_current_validation_report.json",
]
EXPECTED_RELEASE_NORMALIZED = [
    "data_lake_live_content_integrity_release_input_contract_sha256",
    "data_lake_live_content_integrity_release_input_artifact_rows",
    "data_lake_live_content_integrity_release_input_excluded_paths",
]
EXPECTED_LIVE_NORMALIZED = [
    "release_input_contract_sha256",
    "release_input_artifact_rows",
    "release_input_excluded_paths",
]
EXPECTED_RELEASE_EXCLUDED = [
    "local_release_consistency_receipt_current_failures",
    "local_release_consistency_receipt_current_regression_failed_rows",
    "local_release_consistency_receipt_current_regression_success",
    "local_release_consistency_receipt_current_success",
    "local_release_fail_closed_consistency_artifact_count",
    "local_release_fail_closed_consistency_failures",
    "local_release_fail_closed_consistency_lock_acquired",
    "local_release_fail_closed_consistency_receipt_atomic_commit",
    "local_release_fail_closed_consistency_release_ready",
    "local_release_fail_closed_consistency_success",
    "local_release_safety_guard_link_count",
    "local_release_safety_guard_link_failures",
    "local_release_safety_guard_link_success",
]
EXPECTED_LIVE_FIELDS = [
    "success", "failure_count", "local_only", "validated_root", "validated_manifest_path",
    "release_input_contract_version", "release_input_contract_sha256", "release_input_artifact_rows",
    "release_input_excluded_paths", "artifact_rows", "strict_verified_rows", "volatile_existence_only_rows",
    "configured_volatile_existence_only_paths", "volatile_existence_only_paths", "missing_rows",
    "unsafe_path_rows", "size_mismatch_rows", "sha256_mismatch_rows", "row_mismatch_rows",
    "safe_for_model_claim", "release_ready",
]
EXPECTED_CONTRACT_POLICY_FIELDS = [
    "success", "failure_count", "contract_module_path", "contract_module_sha256",
    "expected_contract_version", "expected_excluded_paths", "expected_test_vector_sha256",
    "safe_for_model_claim", "release_ready",
]
EXPECTED_CANONICAL_POLICY_SHA256 = "908529c757d0b821deeeb069712685f22f1945c52301aefddf96d54a4daedcd6"
EXPECTED_TEST_VECTOR_SHA256 = "baba614dc34a232dd161c1e7ba464ef7bd59376839298002d36243e272299977"
EXPECTED_SHARED_VECTOR_SHA256 = "7dc168d07300a6322cf5c4f8a6e118cec842e7dbcf5269e0f53823a8b21bdfd1"


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


def add_check(failures: list[dict[str, Any]], check: str, observed: Any, expected: Any) -> None:
    if observed != expected:
        failures.append({"check": check, "observed": observed, "expected": expected})


def validate_policy_report_current(
    policy: dict[str, Any],
    *,
    policy_report_path: Path,
    policy_script_path: Path,
    contract_module_path: Path,
    expected_output_path: Path,
    expected_lock_path: Path,
) -> list[dict[str, Any]]:
    failures: list[dict[str, Any]] = []
    add_check(failures, "policy_schema_version", policy.get("schema_version"), 1)
    add_check(failures, "policy_mode", policy.get("mode"), "local_release_consistency_semantic_policy_validation")
    add_check(failures, "policy_success", policy.get("success"), True)
    add_check(failures, "policy_failure_count_zero", policy.get("failure_count"), 0)
    add_check(failures, "policy_failures_empty", policy.get("failures") or [], [])
    add_check(failures, "policy_script_path_current", policy.get("policy_script_path"), str(policy_script_path.resolve()))
    add_check(failures, "policy_script_sha256_current", policy.get("policy_script_sha256"), sha256(policy_script_path) if policy_script_path.is_file() else None)
    add_check(failures, "contract_module_path_current", policy.get("contract_module_path"), str(contract_module_path.resolve()))
    add_check(failures, "contract_module_sha256_current", policy.get("contract_module_sha256"), sha256(contract_module_path) if contract_module_path.is_file() else None)
    add_check(failures, "policy_output_path_canonical", policy.get("policy_output_path"), str(expected_output_path.resolve()))
    add_check(failures, "policy_lock_path_canonical", policy.get("policy_lock_path"), str(expected_lock_path.resolve()))
    add_check(failures, "policy_lock_acquired", policy.get("policy_lock_acquired"), True)
    add_check(failures, "policy_atomic_commit", policy.get("policy_atomic_commit"), True)
    expected_fields = {
        "expected_contract_version": EXPECTED_VERSION,
        "expected_input_roles": EXPECTED_INPUT_ROLES,
        "expected_data_lake_semantic_excluded_paths": EXPECTED_DATA_LAKE_EXCLUDED,
        "expected_release_summary_normalized_fields": EXPECTED_RELEASE_NORMALIZED,
        "expected_live_normalized_fields": EXPECTED_LIVE_NORMALIZED,
        "expected_release_summary_excluded_fields": EXPECTED_RELEASE_EXCLUDED,
        "expected_live_projection_fields": EXPECTED_LIVE_FIELDS,
        "expected_contract_policy_projection_fields": EXPECTED_CONTRACT_POLICY_FIELDS,
        "expected_canonical_policy_sha256": EXPECTED_CANONICAL_POLICY_SHA256,
        "expected_test_vector_sha256": EXPECTED_TEST_VECTOR_SHA256,
        "expected_shared_contract_test_vector_sha256": EXPECTED_SHARED_VECTOR_SHA256,
        "observed_canonical_policy_sha256": EXPECTED_CANONICAL_POLICY_SHA256,
        "observed_test_vector_sha256": EXPECTED_TEST_VECTOR_SHA256,
        "observed_shared_contract_test_vector_sha256": EXPECTED_SHARED_VECTOR_SHA256,
        "safe_for_model_claim": False,
        "release_ready": False,
    }
    for field, expected in expected_fields.items():
        add_check(failures, f"{field}_exact", policy.get(field), expected)
    add_check(failures, "observed_policy_payload_sha256_exact", canonical_sha256(policy.get("observed_policy_payload")), EXPECTED_CANONICAL_POLICY_SHA256)
    return failures


def fsync_directory(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


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
            raise RuntimeError("simulated_semantic_policy_current_failure_before_replace")
        os.replace(temp_path, path)
        fsync_directory(path.parent)
    finally:
        if temp_path.exists():
            temp_path.unlink()


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate current semantic policy report")
    parser.add_argument("--policy-report", type=Path, default=POLICY_REPORT)
    parser.add_argument("--policy-script", type=Path, default=POLICY_SCRIPT)
    parser.add_argument("--contract-module", type=Path, default=CONTRACT_MODULE)
    parser.add_argument("--expected-policy-output", type=Path, default=None)
    parser.add_argument("--expected-lock-path", type=Path, default=LOCK_PATH)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    parser.add_argument("--lock-timeout-seconds", type=float, default=30.0)
    parser.add_argument("--fail-before-replace", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()

    report_path = args.policy_report.resolve()
    policy_script = args.policy_script.resolve()
    contract_module = args.contract_module.resolve()
    expected_output = (args.expected_policy_output or report_path).resolve()
    lock_path = args.expected_lock_path.resolve()
    output_path = args.output.resolve()
    lock_handle = acquire_lock(lock_path, args.lock_timeout_seconds)
    if lock_handle is None:
        print(json.dumps({"success": False, "error": "semantic_policy_current_lock_timeout", "lock_path": str(lock_path), "output_preserved": output_path.exists()}, ensure_ascii=False, sort_keys=True))
        return 1
    try:
        failures: list[dict[str, Any]] = []
        for name, path in (("policy_report", report_path), ("policy_script", policy_script), ("contract_module", contract_module)):
            if not path.is_file():
                failures.append({"check": f"{name}_exists", "observed": str(path), "expected": "file"})
        policy = load_json(report_path) if report_path.is_file() else {}
        failures.extend(validate_policy_report_current(
            policy,
            policy_report_path=report_path,
            policy_script_path=policy_script,
            contract_module_path=contract_module,
            expected_output_path=expected_output,
            expected_lock_path=lock_path,
        ))
        current_script = Path(__file__).resolve()
        report = {
            "schema_version": 1,
            "mode": "local_release_consistency_semantic_policy_current",
            "success": not failures,
            "policy_report_path": str(report_path),
            "policy_report_sha256": sha256(report_path) if report_path.is_file() else None,
            "policy_script_path": str(policy_script),
            "policy_script_sha256": sha256(policy_script) if policy_script.is_file() else None,
            "contract_module_path": str(contract_module),
            "contract_module_sha256": sha256(contract_module) if contract_module.is_file() else None,
            "current_validator_script_path": str(current_script),
            "current_validator_script_sha256": sha256(current_script),
            "current_output_path": str(output_path),
            "current_lock_path": str(lock_path),
            "current_lock_acquired": True,
            "current_atomic_commit": True,
            "failure_count": len(failures),
            "failures": failures,
            "safe_for_model_claim": False,
            "release_ready": False,
        }
        write_json_atomic(output_path, report, fail_before_replace=args.fail_before_replace)
    except Exception as exc:
        lock_handle.close()
        print(json.dumps({"success": False, "error": f"semantic_policy_current_commit_failed:{type(exc).__name__}:{exc}", "output": str(output_path)}, ensure_ascii=False, sort_keys=True))
        return 1
    lock_handle.close()
    print(json.dumps({"success": report["success"], "failure_count": report["failure_count"], "output": str(output_path)}, ensure_ascii=False, sort_keys=True))
    return 0 if report["success"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
