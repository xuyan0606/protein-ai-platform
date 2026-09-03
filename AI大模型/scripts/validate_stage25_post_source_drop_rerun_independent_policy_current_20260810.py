#!/usr/bin/env python3
"""Bind the independent post-source policy report to current files."""

from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import os
import tempfile
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
POLICY_REPORT = AI_ROOT / "reports" / "stage25_post_source_drop_rerun_independent_policy_validation_20260810.json"
POLICY_SCRIPT = AI_ROOT / "scripts" / "validate_stage25_post_source_drop_rerun_independent_policy_20260810.py"
BUILDER = AI_ROOT / "scripts" / "build_stage25_post_source_drop_rerun_receipt_20260806.py"
VALIDATOR = AI_ROOT / "scripts" / "validate_stage25_post_source_drop_rerun_receipt_20260806.py"
RECEIPT = AI_ROOT / "reports" / "stage25_post_source_drop_rerun_receipt_20260806.json"
VALIDATION = AI_ROOT / "reports" / "stage25_post_source_drop_rerun_receipt_validation_20260806.json"
LOCK_PATH = AI_ROOT / "reports" / ".stage25_post_source_drop_rerun_receipt.lock"
OUTPUT = AI_ROOT / "reports" / "stage25_post_source_drop_rerun_independent_policy_current_20260810.json"

EXPECTED_POLICY_VERSION = "stage25-post-source-drop-independent-policy-v1"
EXPECTED_BUILDER_CONTRACT_VERSION = "stage25-post-source-drop-rerun-receipt-v2"
EXPECTED_COMMAND_ROWS = 62
EXPECTED_COMMAND_VECTOR_SHA256 = "d35a00f41ae05a4bb9febabd61a0450d3f521d9f3297ff202fad6206e539e2eb"


def load_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return data


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def add_check(failures: list[dict[str, Any]], check: str, observed: Any, expected: Any) -> None:
    if observed != expected:
        failures.append({"check": check, "observed": observed, "expected": expected})


def fsync_directory(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def write_json_atomic(path: Path, payload: dict[str, Any]) -> None:
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
        os.replace(temp_path, path)
        fsync_directory(path.parent)
    finally:
        if temp_path.exists():
            temp_path.unlink()


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate current independent post-source policy report")
    parser.add_argument("--policy-report", type=Path, default=POLICY_REPORT)
    parser.add_argument("--policy-script", type=Path, default=POLICY_SCRIPT)
    parser.add_argument("--builder", type=Path, default=BUILDER)
    parser.add_argument("--validator", type=Path, default=VALIDATOR)
    parser.add_argument("--receipt", type=Path, default=RECEIPT)
    parser.add_argument("--validation", type=Path, default=VALIDATION)
    parser.add_argument("--expected-policy-output", type=Path, default=None)
    parser.add_argument("--expected-lock-path", type=Path, default=LOCK_PATH)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    args = parser.parse_args()

    policy_report_path = args.policy_report.resolve()
    policy_script_path = args.policy_script.resolve()
    builder_path = args.builder.resolve()
    validator_path = args.validator.resolve()
    receipt_path = args.receipt.resolve()
    validation_path = args.validation.resolve()
    expected_policy_output = (args.expected_policy_output or policy_report_path).resolve()
    expected_lock_path = args.expected_lock_path.resolve()
    output_path = args.output.resolve()
    expected_lock_path.parent.mkdir(parents=True, exist_ok=True)

    with expected_lock_path.open("w", encoding="utf-8") as lock_handle:
        fcntl.flock(lock_handle.fileno(), fcntl.LOCK_EX)
        failures: list[dict[str, Any]] = []
        paths = {
            "policy_report": policy_report_path,
            "policy_script": policy_script_path,
            "builder": builder_path,
            "validator": validator_path,
            "receipt": receipt_path,
            "validation": validation_path,
        }
        for name, path in paths.items():
            if not path.is_file():
                failures.append({"check": f"{name}_exists", "observed": str(path), "expected": "file"})
        policy = load_json(policy_report_path) if policy_report_path.is_file() else {}

        add_check(failures, "policy_schema_version", policy.get("schema_version"), 1)
        add_check(failures, "policy_mode", policy.get("mode"), "stage25_post_source_drop_rerun_independent_policy_validation")
        add_check(failures, "policy_success", policy.get("success"), True)
        add_check(failures, "policy_failure_count_zero", policy.get("failure_count"), 0)
        add_check(failures, "policy_failures_empty", policy.get("failures") or [], [])
        add_check(failures, "policy_version_exact", policy.get("policy_version"), EXPECTED_POLICY_VERSION)
        add_check(failures, "policy_script_path_current", policy.get("policy_script_path"), str(policy_script_path))
        add_check(failures, "policy_script_sha256_current", policy.get("policy_script_sha256"), sha256(policy_script_path) if policy_script_path.is_file() else None)
        add_check(failures, "policy_output_path_canonical", policy.get("policy_output_path"), str(expected_policy_output))
        add_check(failures, "policy_lock_path_canonical", policy.get("policy_lock_path"), str(expected_lock_path))
        add_check(failures, "policy_atomic_commit", policy.get("policy_atomic_commit"), True)
        for name, path in (("builder", builder_path), ("validator", validator_path), ("receipt", receipt_path), ("validation", validation_path)):
            add_check(failures, f"{name}_path_current", policy.get(f"{name}_path"), str(path))
            add_check(failures, f"{name}_sha256_current", policy.get(f"{name}_sha256"), sha256(path) if path.is_file() else None)
        add_check(failures, "builder_contract_version_exact", policy.get("expected_builder_contract_version"), EXPECTED_BUILDER_CONTRACT_VERSION)
        add_check(failures, "receipt_schema_version_exact", policy.get("expected_receipt_schema_version"), 2)
        add_check(failures, "validation_schema_version_exact", policy.get("expected_validation_schema_version"), 3)
        add_check(failures, "command_contract_schema_version_exact", policy.get("expected_command_contract_schema_version"), 1)
        add_check(failures, "command_rows_exact", policy.get("expected_command_rows"), EXPECTED_COMMAND_ROWS)
        add_check(failures, "command_vector_sha256_exact", policy.get("expected_command_test_vector_sha256"), EXPECTED_COMMAND_VECTOR_SHA256)
        add_check(failures, "builder_command_vector_current", policy.get("observed_builder_command_test_vector_sha256"), EXPECTED_COMMAND_VECTOR_SHA256)
        add_check(failures, "receipt_command_vector_current", policy.get("observed_receipt_command_test_vector_sha256"), EXPECTED_COMMAND_VECTOR_SHA256)
        add_check(failures, "safe_for_model_claim_false", policy.get("safe_for_model_claim"), False)
        add_check(failures, "release_ready_false", policy.get("release_ready"), False)

        current_script = Path(__file__).resolve()
        report = {
            "schema_version": 1,
            "mode": "stage25_post_source_drop_rerun_independent_policy_current",
            "success": not failures,
            "policy_report_path": str(policy_report_path),
            "policy_report_sha256": sha256(policy_report_path) if policy_report_path.is_file() else None,
            "policy_script_path": str(policy_script_path),
            "policy_script_sha256": sha256(policy_script_path) if policy_script_path.is_file() else None,
            "builder_path": str(builder_path),
            "builder_sha256": sha256(builder_path) if builder_path.is_file() else None,
            "validator_path": str(validator_path),
            "validator_sha256": sha256(validator_path) if validator_path.is_file() else None,
            "receipt_path": str(receipt_path),
            "receipt_sha256": sha256(receipt_path) if receipt_path.is_file() else None,
            "validation_path": str(validation_path),
            "validation_sha256": sha256(validation_path) if validation_path.is_file() else None,
            "current_validator_script_path": str(current_script),
            "current_validator_script_sha256": sha256(current_script),
            "current_output_path": str(output_path),
            "current_lock_path": str(expected_lock_path),
            "current_atomic_commit": True,
            "expected_policy_version": EXPECTED_POLICY_VERSION,
            "expected_command_rows": EXPECTED_COMMAND_ROWS,
            "expected_command_vector_sha256": EXPECTED_COMMAND_VECTOR_SHA256,
            "failure_count": len(failures),
            "failures": failures,
            "safe_for_model_claim": False,
            "release_ready": False,
        }
        write_json_atomic(output_path, report)

    print(json.dumps({"success": report["success"], "failure_count": report["failure_count"], "output": str(output_path)}, ensure_ascii=False, sort_keys=True))
    return 0 if report["success"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
