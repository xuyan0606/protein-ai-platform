#!/usr/bin/env python3
"""Independently pin the post-source rerun receipt policy."""

from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import os
import runpy
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
BUILDER = AI_ROOT / "scripts" / "build_stage25_post_source_drop_rerun_receipt_20260806.py"
VALIDATOR = AI_ROOT / "scripts" / "validate_stage25_post_source_drop_rerun_receipt_20260806.py"
RECEIPT = AI_ROOT / "reports" / "stage25_post_source_drop_rerun_receipt_20260806.json"
VALIDATION = AI_ROOT / "reports" / "stage25_post_source_drop_rerun_receipt_validation_20260806.json"
OUTPUT = AI_ROOT / "reports" / "stage25_post_source_drop_rerun_independent_policy_validation_20260810.json"

POLICY_VERSION = "stage25-post-source-drop-independent-policy-v1"
EXPECTED_BUILDER_CONTRACT_VERSION = "stage25-post-source-drop-rerun-receipt-v2"
EXPECTED_RECEIPT_SCHEMA_VERSION = 2
EXPECTED_VALIDATION_SCHEMA_VERSION = 3
EXPECTED_COMMAND_CONTRACT_SCHEMA_VERSION = 1
EXPECTED_COMMAND_ROWS = 62
EXPECTED_COMMAND_TEST_VECTOR_SHA256 = "d35a00f41ae05a4bb9febabd61a0450d3f521d9f3297ff202fad6206e539e2eb"
EXPECTED_BUILDER_RELATIVE_PATH = "scripts/build_stage25_post_source_drop_rerun_receipt_20260806.py"
EXPECTED_VALIDATOR_RELATIVE_PATH = "scripts/validate_stage25_post_source_drop_rerun_receipt_20260806.py"
EXPECTED_RECEIPT_RELATIVE_PATH = "reports/stage25_post_source_drop_rerun_receipt_20260806.json"
EXPECTED_VALIDATION_RELATIVE_PATH = "reports/stage25_post_source_drop_rerun_receipt_validation_20260806.json"
EXPECTED_LOCK_RELATIVE_PATH = "reports/.stage25_post_source_drop_rerun_receipt.lock"


def load_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return data


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def add_check(failures: list[dict[str, Any]], check: str, observed: Any, expected: Any) -> None:
    if observed != expected:
        if isinstance(observed, Path):
            observed = str(observed)
        if isinstance(expected, Path):
            expected = str(expected)
        failures.append({"check": check, "observed": observed, "expected": expected})


def normalize_value(value: Any, replacements: list[tuple[str, str]]) -> Any:
    if isinstance(value, str):
        for source, target in replacements:
            if value == source:
                return target
            if value.startswith(f"{source}/"):
                return f"{target}{value[len(source):]}"
        return value
    if isinstance(value, list):
        return [normalize_value(item, replacements) for item in value]
    if isinstance(value, dict):
        return {key: normalize_value(item, replacements) for key, item in value.items()}
    return value


def normalized_commands(namespace: dict[str, Any], raw_commands: Any) -> list[dict[str, Any]]:
    if not isinstance(raw_commands, list):
        return []
    replacements = [
        (str(namespace.get("BACKEND_PYTHON")), "$BACKEND_PYTHON"),
        (str(namespace.get("ENZYME_DB_ROOT")), "$ENZYME_DB_ROOT"),
        (str(namespace.get("AI_ROOT")), "$AI_ROOT"),
        (sys.executable, "$PYTHON"),
    ]
    rows: list[dict[str, Any]] = []
    for index, row in enumerate(raw_commands, start=1):
        if not isinstance(row, dict):
            return []
        normalized = normalize_value(dict(row), replacements)
        normalized["step"] = index
        rows.append(normalized)
    return rows


def canonical_sha256(rows: list[dict[str, Any]]) -> str:
    payload = json.dumps(rows, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def fsync_directory(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def write_json_atomic(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    encoded = (json.dumps(payload, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    descriptor, temp_name = tempfile.mkstemp(prefix=f".{path.name}.policy-", dir=path.parent)
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
    parser = argparse.ArgumentParser(description="Validate independent post-source rerun policy")
    parser.add_argument("--builder", type=Path, default=BUILDER)
    parser.add_argument("--validator", type=Path, default=VALIDATOR)
    parser.add_argument("--receipt", type=Path, default=RECEIPT)
    parser.add_argument("--validation", type=Path, default=VALIDATION)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    args = parser.parse_args()

    builder_path = args.builder.resolve()
    validator_path = args.validator.resolve()
    receipt_path = args.receipt.resolve()
    validation_path = args.validation.resolve()
    output_path = args.output.resolve()
    root = builder_path.parents[1]
    expected_builder = (root / EXPECTED_BUILDER_RELATIVE_PATH).resolve()
    expected_validator = (root / EXPECTED_VALIDATOR_RELATIVE_PATH).resolve()
    expected_receipt = (root / EXPECTED_RECEIPT_RELATIVE_PATH).resolve()
    expected_validation = (root / EXPECTED_VALIDATION_RELATIVE_PATH).resolve()
    expected_lock = (root / EXPECTED_LOCK_RELATIVE_PATH).resolve()
    expected_lock.parent.mkdir(parents=True, exist_ok=True)

    with expected_lock.open("w", encoding="utf-8") as lock_handle:
        fcntl.flock(lock_handle.fileno(), fcntl.LOCK_EX)
        failures: list[dict[str, Any]] = []
        for check, path in (
            ("builder_exists", builder_path),
            ("validator_exists", validator_path),
            ("receipt_exists", receipt_path),
            ("validation_exists", validation_path),
        ):
            if not path.is_file():
                failures.append({"check": check, "observed": str(path), "expected": "file"})

        namespace: dict[str, Any] = {}
        if builder_path.is_file():
            try:
                namespace = runpy.run_path(str(builder_path))
            except Exception as exc:
                failures.append({"check": "builder_loads", "observed": f"{type(exc).__name__}:{exc}", "expected": "loadable"})
        receipt = load_json(receipt_path) if receipt_path.is_file() else {}
        validation = load_json(validation_path) if validation_path.is_file() else {}
        builder_rows = normalized_commands(namespace, namespace.get("COMMANDS"))
        receipt_rows = normalized_commands(namespace, receipt.get("commands"))
        builder_vector_sha = canonical_sha256(builder_rows)
        receipt_vector_sha = canonical_sha256(receipt_rows)
        builder_output = Path(namespace["OUTPUT"]).resolve() if namespace.get("OUTPUT") else None
        builder_lock = Path(namespace["LOCK_PATH"]).resolve() if namespace.get("LOCK_PATH") else None

        add_check(failures, "builder_path_canonical", builder_path, expected_builder)
        add_check(failures, "validator_path_canonical", validator_path, expected_validator)
        add_check(failures, "receipt_path_canonical", receipt_path, expected_receipt)
        add_check(failures, "validation_path_canonical", validation_path, expected_validation)
        add_check(failures, "builder_contract_version_exact", namespace.get("BUILDER_CONTRACT_VERSION"), EXPECTED_BUILDER_CONTRACT_VERSION)
        add_check(failures, "builder_output_path_exact", builder_output, expected_receipt)
        add_check(failures, "builder_lock_path_exact", builder_lock, expected_lock)
        add_check(failures, "command_rows_exact", len(builder_rows), EXPECTED_COMMAND_ROWS)
        add_check(failures, "command_test_vector_sha256_exact", builder_vector_sha, EXPECTED_COMMAND_TEST_VECTOR_SHA256)
        add_check(failures, "receipt_command_test_vector_sha256_exact", receipt_vector_sha, EXPECTED_COMMAND_TEST_VECTOR_SHA256)
        add_check(failures, "receipt_commands_match_builder", receipt_rows, builder_rows)
        add_check(failures, "all_commands_non_sqlite", [row.get("writes_sqlite") for row in builder_rows], [False] * EXPECTED_COMMAND_ROWS)
        add_check(failures, "all_commands_block_apply", [row.get("blocks_apply_until_passed") for row in builder_rows], [True] * EXPECTED_COMMAND_ROWS)
        add_check(failures, "receipt_schema_version_exact", receipt.get("schema_version"), EXPECTED_RECEIPT_SCHEMA_VERSION)
        add_check(failures, "receipt_builder_contract_version_exact", receipt.get("builder_contract_version"), EXPECTED_BUILDER_CONTRACT_VERSION)
        add_check(failures, "receipt_command_contract_schema_version_exact", receipt.get("command_contract_schema_version"), EXPECTED_COMMAND_CONTRACT_SCHEMA_VERSION)
        add_check(failures, "receipt_command_rows_exact", receipt.get("command_rows"), EXPECTED_COMMAND_ROWS)
        add_check(failures, "receipt_output_path_exact", receipt.get("output_path"), str(expected_receipt))
        add_check(failures, "receipt_lock_path_exact", receipt.get("lock_path"), str(expected_lock))
        add_check(failures, "receipt_sqlite_write_rows_zero", receipt.get("sqlite_write_command_rows"), 0)
        add_check(failures, "validation_schema_version_exact", validation.get("schema_version"), EXPECTED_VALIDATION_SCHEMA_VERSION)
        add_check(failures, "validation_success", validation.get("success"), True)
        add_check(failures, "validation_failure_count_zero", validation.get("failure_count"), 0)
        add_check(failures, "validation_receipt_path_exact", validation.get("receipt_path"), str(receipt_path))
        add_check(failures, "validation_validator_path_exact", validation.get("validator_script_path"), str(validator_path))
        add_check(failures, "validation_output_path_exact", validation.get("validation_output_path"), str(expected_validation))
        add_check(failures, "validation_lock_path_exact", validation.get("validation_lock_path"), str(expected_lock))
        add_check(failures, "validation_atomic_commit", validation.get("validation_atomic_commit"), True)

        policy_script = Path(__file__).resolve()
        report = {
            "schema_version": 1,
            "mode": "stage25_post_source_drop_rerun_independent_policy_validation",
            "policy_version": POLICY_VERSION,
            "success": not failures,
            "policy_script_path": str(policy_script),
            "policy_script_sha256": sha256(policy_script),
            "policy_output_path": str(output_path),
            "policy_lock_path": str(expected_lock),
            "policy_atomic_commit": True,
            "builder_path": str(builder_path),
            "builder_sha256": sha256(builder_path) if builder_path.is_file() else None,
            "validator_path": str(validator_path),
            "validator_sha256": sha256(validator_path) if validator_path.is_file() else None,
            "receipt_path": str(receipt_path),
            "receipt_sha256": sha256(receipt_path) if receipt_path.is_file() else None,
            "validation_path": str(validation_path),
            "validation_sha256": sha256(validation_path) if validation_path.is_file() else None,
            "expected_builder_contract_version": EXPECTED_BUILDER_CONTRACT_VERSION,
            "expected_receipt_schema_version": EXPECTED_RECEIPT_SCHEMA_VERSION,
            "expected_validation_schema_version": EXPECTED_VALIDATION_SCHEMA_VERSION,
            "expected_command_contract_schema_version": EXPECTED_COMMAND_CONTRACT_SCHEMA_VERSION,
            "expected_command_rows": EXPECTED_COMMAND_ROWS,
            "expected_command_test_vector_sha256": EXPECTED_COMMAND_TEST_VECTOR_SHA256,
            "observed_builder_command_test_vector_sha256": builder_vector_sha,
            "observed_receipt_command_test_vector_sha256": receipt_vector_sha,
            "expected_builder_relative_path": EXPECTED_BUILDER_RELATIVE_PATH,
            "expected_validator_relative_path": EXPECTED_VALIDATOR_RELATIVE_PATH,
            "expected_receipt_relative_path": EXPECTED_RECEIPT_RELATIVE_PATH,
            "expected_validation_relative_path": EXPECTED_VALIDATION_RELATIVE_PATH,
            "expected_lock_relative_path": EXPECTED_LOCK_RELATIVE_PATH,
            "failure_count": len(failures),
            "failures": failures,
            "safe_for_model_claim": False,
            "release_ready": False,
            "policy": "Independent portable-vector policy; success does not execute commands or authorize SQLite, apply, training, model claims, production, or release.",
        }
        write_json_atomic(output_path, report)

    print(json.dumps({"success": report["success"], "command_rows": len(builder_rows), "failure_count": report["failure_count"], "output": str(output_path)}, ensure_ascii=False, sort_keys=True))
    return 0 if report["success"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
