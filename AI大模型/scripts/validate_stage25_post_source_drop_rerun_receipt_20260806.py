#!/usr/bin/env python3
"""Validate the Stage 25 post-source-drop rerun receipt."""

from __future__ import annotations

import json
import hashlib
import argparse
import fcntl
import os
import runpy
import tempfile
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
RECEIPT = AI_ROOT / "reports" / "stage25_post_source_drop_rerun_receipt_20260806.json"
OUTPUT = AI_ROOT / "reports" / "stage25_post_source_drop_rerun_receipt_validation_20260806.json"
BUILDER = AI_ROOT / "scripts" / "build_stage25_post_source_drop_rerun_receipt_20260806.py"


def load_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return data


def fail_if(condition: bool, failures: list[dict[str, Any]], check: str, observed: Any, expected: Any) -> None:
    if condition:
        failures.append({"check": check, "observed": observed, "expected": expected})


def canonical_sha256(commands: list[dict[str, Any]]) -> str:
    payload = json.dumps(commands, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def load_expected_commands() -> list[dict[str, Any]]:
    namespace = runpy.run_path(str(BUILDER))
    raw_commands = namespace.get("COMMANDS")
    if not isinstance(raw_commands, list):
        raise ValueError(f"{BUILDER} must define COMMANDS as a list")
    commands = []
    for index, row in enumerate(raw_commands, start=1):
        if not isinstance(row, dict):
            raise ValueError(f"{BUILDER} COMMANDS[{index}] must be an object")
        normalized = dict(row)
        normalized["step"] = index
        commands.append(normalized)
    return commands


def fsync_directory(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def write_json_atomic(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    encoded = (json.dumps(payload, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    descriptor, temp_name = tempfile.mkstemp(prefix=f".{path.name}.validation-", dir=path.parent)
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
    parser = argparse.ArgumentParser(description="Validate the current post-source-drop rerun receipt")
    parser.add_argument("--receipt", type=Path, default=RECEIPT)
    parser.add_argument("--builder", type=Path, default=BUILDER)
    parser.add_argument("--expected-output", type=Path, default=None)
    parser.add_argument("--expected-lock-path", type=Path, default=None)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    args = parser.parse_args()

    receipt_path = args.receipt.resolve()
    builder_path = args.builder.resolve()
    expected_output = (args.expected_output or receipt_path).resolve()
    expected_lock_path = (args.expected_lock_path or (AI_ROOT / "reports" / ".stage25_post_source_drop_rerun_receipt.lock")).resolve()
    expected_lock_path.parent.mkdir(parents=True, exist_ok=True)
    lock_handle = expected_lock_path.open("w", encoding="utf-8")
    fcntl.flock(lock_handle.fileno(), fcntl.LOCK_EX)
    failures: list[dict[str, Any]] = []
    fail_if(not receipt_path.exists(), failures, "receipt_exists", "missing", str(receipt_path))
    receipt = load_json(receipt_path) if receipt_path.exists() else {}
    fail_if(not builder_path.exists(), failures, "builder_exists", "missing", str(builder_path))
    namespace = runpy.run_path(str(builder_path)) if builder_path.exists() else {}
    commands = receipt.get("commands") if isinstance(receipt.get("commands"), list) else []
    raw_commands = namespace.get("COMMANDS")
    expected_commands = []
    if isinstance(raw_commands, list):
        for index, row in enumerate(raw_commands, start=1):
            if not isinstance(row, dict):
                failures.append({"check": f"builder_commands[{index}]_object", "observed": row, "expected": "object"})
                continue
            normalized = dict(row)
            normalized["step"] = index
            expected_commands.append(normalized)
    else:
        failures.append({"check": "builder_commands_list", "observed": type(raw_commands).__name__, "expected": "list"})
    expected_names = [str(row.get("name")) for row in expected_commands]
    observed_names = [str(row.get("name")) for row in commands if isinstance(row, dict)]
    expected_contract_sha256 = canonical_sha256(expected_commands)
    observed_contract_sha256 = canonical_sha256(commands)
    expected_command_rows = len(expected_commands)
    current_builder_sha256 = hashlib.sha256(builder_path.read_bytes()).hexdigest() if builder_path.exists() else None
    validator_script_path = Path(__file__).resolve()
    validator_script_sha256 = hashlib.sha256(validator_script_path.read_bytes()).hexdigest()
    expected_builder_contract_version = namespace.get("BUILDER_CONTRACT_VERSION")
    expected_builder_output = Path(namespace["OUTPUT"]).resolve() if namespace.get("OUTPUT") else None
    expected_builder_lock = Path(namespace["LOCK_PATH"]).resolve() if namespace.get("LOCK_PATH") else None

    fail_if(receipt.get("mode") != "stage25_post_source_drop_rerun_receipt", failures, "mode", receipt.get("mode"), "stage25_post_source_drop_rerun_receipt")
    fail_if(receipt.get("schema_version") != 2, failures, "schema_version", receipt.get("schema_version"), 2)
    fail_if(receipt.get("builder_contract_version") != expected_builder_contract_version, failures, "builder_contract_version_current", receipt.get("builder_contract_version"), expected_builder_contract_version)
    fail_if(receipt.get("builder_script_path") != str(builder_path), failures, "builder_script_path_current", receipt.get("builder_script_path"), str(builder_path))
    fail_if(receipt.get("builder_script_sha256") != current_builder_sha256, failures, "builder_script_sha256_current", receipt.get("builder_script_sha256"), current_builder_sha256)
    fail_if(receipt.get("output_path") != str(expected_output), failures, "output_path_canonical", receipt.get("output_path"), str(expected_output))
    fail_if(receipt.get("lock_path") != str(expected_lock_path), failures, "lock_path_canonical", receipt.get("lock_path"), str(expected_lock_path))
    if expected_builder_output is not None:
        fail_if(expected_output != expected_builder_output, failures, "builder_output_contract_canonical", str(expected_output), str(expected_builder_output))
    if expected_builder_lock is not None:
        fail_if(expected_lock_path != expected_builder_lock, failures, "builder_lock_contract_canonical", str(expected_lock_path), str(expected_builder_lock))
    fail_if(receipt.get("lock_acquired") is not True, failures, "lock_acquired_true", receipt.get("lock_acquired"), True)
    fail_if(receipt.get("receipt_atomic_commit") is not True, failures, "receipt_atomic_commit_true", receipt.get("receipt_atomic_commit"), True)
    fail_if(receipt.get("rerun_ready") is not True, failures, "rerun_ready_true", receipt.get("rerun_ready"), True)
    fail_if(receipt.get("command_rows") != expected_command_rows, failures, "command_rows", receipt.get("command_rows"), expected_command_rows)
    fail_if(receipt.get("command_contract_schema_version") != 1, failures, "command_contract_schema_version", receipt.get("command_contract_schema_version"), 1)
    fail_if(receipt.get("command_contract_sha256") != expected_contract_sha256, failures, "receipt_command_contract_sha256", receipt.get("command_contract_sha256"), expected_contract_sha256)
    fail_if(observed_contract_sha256 != expected_contract_sha256, failures, "observed_command_contract_sha256", observed_contract_sha256, expected_contract_sha256)
    fail_if(commands != expected_commands, failures, "commands_exact_contract", commands, expected_commands)
    fail_if(observed_names != expected_names, failures, "command_names_exact_order", observed_names, expected_names)
    fail_if(receipt.get("command_names") != expected_names, failures, "receipt_command_names_exact_order", receipt.get("command_names"), expected_names)
    fail_if(receipt.get("unique_command_name_rows") != expected_command_rows, failures, "unique_command_name_rows", receipt.get("unique_command_name_rows"), expected_command_rows)
    fail_if(receipt.get("duplicate_command_names") != [], failures, "duplicate_command_names_empty", receipt.get("duplicate_command_names"), [])
    fail_if(receipt.get("sqlite_write_command_rows") != 0, failures, "sqlite_write_command_rows_zero", receipt.get("sqlite_write_command_rows"), 0)
    fail_if(len(commands) != receipt.get("command_rows"), failures, "commands_len_matches", len(commands), receipt.get("command_rows"))
    fail_if("incoming/fulltext" not in str(receipt.get("rerun_trigger") or ""), failures, "rerun_trigger_mentions_fulltext_intake", receipt.get("rerun_trigger"), "contains incoming/fulltext")

    expected_steps = list(range(1, len(commands) + 1))
    observed_steps = [row.get("step") for row in commands if isinstance(row, dict)]
    fail_if(observed_steps != expected_steps, failures, "steps_contiguous", observed_steps, expected_steps)
    for index, row in enumerate(commands, start=1):
        prefix = f"commands[{index}]"
        fail_if(not row.get("name"), failures, f"{prefix}.name_present", row.get("name"), "non-empty")
        fail_if(not row.get("cwd"), failures, f"{prefix}.cwd_present", row.get("cwd"), "non-empty")
        fail_if(not isinstance(row.get("cmd"), list) or not row.get("cmd"), failures, f"{prefix}.cmd_list", row.get("cmd"), "non-empty list")
        fail_if(not row.get("expected_output"), failures, f"{prefix}.expected_output_present", row.get("expected_output"), "non-empty")
        fail_if(row.get("writes_sqlite") is not False, failures, f"{prefix}.writes_sqlite_false", row.get("writes_sqlite"), False)
        fail_if(row.get("blocks_apply_until_passed") is not True, failures, f"{prefix}.blocks_apply_until_passed_true", row.get("blocks_apply_until_passed"), True)

    fail_if("exact non-SQLite command recipe" not in str(receipt.get("policy") or ""), failures, "policy_defines_rerun_ready_scope", receipt.get("policy"), "contains exact non-SQLite command recipe")
    for flag in ("commands_executed", "source_drop_event_receipted", "outputs_freshness_verified", "rerun_completion_receipted"):
        fail_if(receipt.get(flag) is not False, failures, f"{flag}_false", receipt.get(flag), False)
    fail_if(receipt.get("commands_executed_rows") != 0, failures, "commands_executed_rows_zero", receipt.get("commands_executed_rows"), 0)
    for flag in ("source_evidence_ready", "ready_for_reviewed_extraction", "ready_for_sqlite_apply"):
        fail_if(receipt.get(flag) is not False, failures, f"{flag}_false", receipt.get(flag), False)

    for flag in ("external_sqlite_mutated", "apply_executed", "export_safe_released", "safe_for_model_claim", "release_ready"):
        fail_if(receipt.get(flag) is not False, failures, f"{flag}_false", receipt.get(flag), False)
    fail_if(receipt.get("formal_decision_rows_written") != 0, failures, "formal_decision_rows_written_zero", receipt.get("formal_decision_rows_written"), 0)

    report = {
        "schema_version": 3,
        "created_at": "2026-08-06",
        "mode": "stage25_post_source_drop_rerun_receipt_validation",
        "stage": 25,
        "success": not failures,
        "receipt_valid": not failures,
        "failure_count": len(failures),
        "failures": failures,
        "command_rows": len(commands),
        "unique_command_name_rows": receipt.get("unique_command_name_rows"),
        "duplicate_command_names": receipt.get("duplicate_command_names"),
        "command_names_exact": observed_names == expected_names,
        "command_contract_sha256": observed_contract_sha256,
        "command_contract_valid": observed_contract_sha256 == expected_contract_sha256 and commands == expected_commands,
        "builder_contract_version": expected_builder_contract_version,
        "builder_script_path": str(builder_path),
        "builder_script_sha256": current_builder_sha256,
        "receipt_path": str(receipt_path),
        "receipt_sha256": hashlib.sha256(receipt_path.read_bytes()).hexdigest() if receipt_path.is_file() else None,
        "validator_script_path": str(validator_script_path),
        "validator_script_sha256": validator_script_sha256,
        "validation_output_path": str(args.output.resolve()),
        "validation_lock_path": str(expected_lock_path),
        "validation_atomic_commit": True,
        "output_path_canonical": str(expected_output),
        "lock_path_canonical": str(expected_lock_path),
        "lock_acquired": receipt.get("lock_acquired"),
        "receipt_atomic_commit": receipt.get("receipt_atomic_commit"),
        "sqlite_write_command_rows": receipt.get("sqlite_write_command_rows"),
        "rerun_ready": receipt.get("rerun_ready"),
        "commands_executed": False,
        "commands_executed_rows": 0,
        "source_drop_event_receipted": False,
        "outputs_freshness_verified": False,
        "rerun_completion_receipted": False,
        "source_evidence_ready": False,
        "ready_for_reviewed_extraction": False,
        "ready_for_sqlite_apply": False,
        "external_sqlite_mutated": False,
        "formal_decision_rows_written": 0,
        "apply_executed": False,
        "export_safe_released": False,
        "safe_for_model_claim": False,
        "release_ready": False,
    }
    write_json_atomic(args.output.resolve(), report)
    lock_handle.close()
    print(json.dumps({"output": str(args.output.resolve()), "receipt_valid": report["receipt_valid"], "failure_count": report["failure_count"], "command_rows": report["command_rows"]}, ensure_ascii=False, sort_keys=True))
    return 0 if report["receipt_valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
