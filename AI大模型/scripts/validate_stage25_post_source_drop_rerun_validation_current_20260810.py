#!/usr/bin/env python3
"""Bind the post-source receipt validation report to current inputs."""

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
RECEIPT = AI_ROOT / "reports" / "stage25_post_source_drop_rerun_receipt_20260806.json"
VALIDATION = AI_ROOT / "reports" / "stage25_post_source_drop_rerun_receipt_validation_20260806.json"
VALIDATOR = AI_ROOT / "scripts" / "validate_stage25_post_source_drop_rerun_receipt_20260806.py"
LOCK_PATH = AI_ROOT / "reports" / ".stage25_post_source_drop_rerun_receipt.lock"
OUTPUT = AI_ROOT / "reports" / "stage25_post_source_drop_rerun_validation_current_20260810.json"


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
    parser = argparse.ArgumentParser(description="Validate current post-source validation provenance")
    parser.add_argument("--validation", type=Path, default=VALIDATION)
    parser.add_argument("--receipt", type=Path, default=RECEIPT)
    parser.add_argument("--validator", type=Path, default=VALIDATOR)
    parser.add_argument("--expected-validation-output", type=Path, default=None)
    parser.add_argument("--expected-lock-path", type=Path, default=LOCK_PATH)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    args = parser.parse_args()

    validation_path = args.validation.resolve()
    receipt_path = args.receipt.resolve()
    validator_path = args.validator.resolve()
    expected_validation_output = (args.expected_validation_output or validation_path).resolve()
    expected_lock_path = args.expected_lock_path.resolve()
    output_path = args.output.resolve()
    expected_lock_path.parent.mkdir(parents=True, exist_ok=True)

    with expected_lock_path.open("w", encoding="utf-8") as lock_handle:
        fcntl.flock(lock_handle.fileno(), fcntl.LOCK_EX)
        failures: list[dict[str, Any]] = []
        for check, path in (
            ("validation_report_exists", validation_path),
            ("receipt_exists", receipt_path),
            ("validator_exists", validator_path),
        ):
            if not path.is_file():
                failures.append({"check": check, "observed": str(path), "expected": "file"})

        validation = load_json(validation_path) if validation_path.is_file() else {}
        current_receipt_sha = sha256(receipt_path) if receipt_path.is_file() else None
        current_validator_sha = sha256(validator_path) if validator_path.is_file() else None
        current_validation_sha = sha256(validation_path) if validation_path.is_file() else None
        current_script_path = Path(__file__).resolve()
        current_script_sha = sha256(current_script_path)

        add_check(failures, "validation_schema_version", validation.get("schema_version"), 3)
        add_check(failures, "validation_mode", validation.get("mode"), "stage25_post_source_drop_rerun_receipt_validation")
        add_check(failures, "validation_success", validation.get("success"), True)
        add_check(failures, "receipt_valid", validation.get("receipt_valid"), True)
        add_check(failures, "validation_failure_count_zero", validation.get("failure_count"), 0)
        add_check(failures, "validation_failures_empty", validation.get("failures") or [], [])
        add_check(failures, "receipt_path_current", validation.get("receipt_path"), str(receipt_path))
        add_check(failures, "receipt_sha256_current", validation.get("receipt_sha256"), current_receipt_sha)
        add_check(failures, "validator_script_path_current", validation.get("validator_script_path"), str(validator_path))
        add_check(failures, "validator_script_sha256_current", validation.get("validator_script_sha256"), current_validator_sha)
        add_check(failures, "validation_output_path_canonical", validation.get("validation_output_path"), str(expected_validation_output))
        add_check(failures, "validation_lock_path_canonical", validation.get("validation_lock_path"), str(expected_lock_path))
        add_check(failures, "validation_atomic_commit", validation.get("validation_atomic_commit"), True)
        add_check(failures, "safe_for_model_claim_false", validation.get("safe_for_model_claim"), False)
        add_check(failures, "release_ready_false", validation.get("release_ready"), False)

        report = {
            "schema_version": 1,
            "mode": "stage25_post_source_drop_rerun_validation_current",
            "success": not failures,
            "validation_report_path": str(validation_path),
            "validation_report_sha256": current_validation_sha,
            "receipt_path": str(receipt_path),
            "receipt_sha256": current_receipt_sha,
            "validator_script_path": str(validator_path),
            "validator_script_sha256": current_validator_sha,
            "current_validator_script_path": str(current_script_path),
            "current_validator_script_sha256": current_script_sha,
            "current_validation_output_path": str(output_path),
            "current_validation_lock_path": str(expected_lock_path),
            "current_validation_atomic_commit": True,
            "failure_count": len(failures),
            "failures": failures,
            "safe_for_model_claim": False,
            "release_ready": False,
            "policy": "Current-state proof only; it does not execute the post-source recipe or authorize SQLite, apply, training, model claims, or release.",
        }
        write_json_atomic(output_path, report)

    print(json.dumps({"success": report["success"], "failure_count": report["failure_count"], "output": str(output_path)}, ensure_ascii=False, sort_keys=True))
    return 0 if report["success"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
