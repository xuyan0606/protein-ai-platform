#!/usr/bin/env python3
"""Pin the semantic projection policy independently from its shared implementation."""

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
from types import ModuleType
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
CONTRACT_MODULE = AI_ROOT / "scripts" / "local_release_consistency_receipt_contract.py"
OUTPUT = AI_ROOT / "reports" / "local_release_consistency_semantic_policy_validation_report.json"
LOCK_PATH = AI_ROOT / "reports" / ".local_release_consistency_semantic_policy.lock"

EXPECTED_VERSION = "local-release-consistency-semantic-input-v1"
EXPECTED_INPUT_ROLES = ("release", "data_lake", "live_integrity", "contract_policy", "semantic_policy")
EXPECTED_DATA_LAKE_SEMANTIC_EXCLUDED_PATHS = (
    "reports/local_release_consistency_receipt_current_regression_report.json",
    "reports/local_release_consistency_receipt_current_validation_report.json",
    "reports/local_release_safety_guard_links_current_regression_report.json",
    "reports/local_release_safety_guard_links_current_validation_report.json",
)
EXPECTED_RELEASE_SUMMARY_NORMALIZED_FIELDS = (
    "data_lake_live_content_integrity_release_input_contract_sha256",
    "data_lake_live_content_integrity_release_input_artifact_rows",
    "data_lake_live_content_integrity_release_input_excluded_paths",
)
EXPECTED_LIVE_NORMALIZED_FIELDS = (
    "release_input_contract_sha256",
    "release_input_artifact_rows",
    "release_input_excluded_paths",
)
EXPECTED_RELEASE_SUMMARY_EXCLUDED_FIELDS = (
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
)
EXPECTED_LIVE_FIELDS = (
    "success", "failure_count", "local_only", "validated_root", "validated_manifest_path",
    "release_input_contract_version", "release_input_contract_sha256", "release_input_artifact_rows",
    "release_input_excluded_paths", "artifact_rows", "strict_verified_rows", "volatile_existence_only_rows",
    "configured_volatile_existence_only_paths", "volatile_existence_only_paths", "missing_rows",
    "unsafe_path_rows", "size_mismatch_rows", "sha256_mismatch_rows", "row_mismatch_rows",
    "safe_for_model_claim", "release_ready",
)
EXPECTED_CONTRACT_POLICY_FIELDS = (
    "success", "failure_count", "contract_module_path", "contract_module_sha256",
    "expected_contract_version", "expected_excluded_paths", "expected_test_vector_sha256",
    "safe_for_model_claim", "release_ready",
)


def canonical_sha256(payload: Any) -> str:
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def canonical_policy_payload() -> dict[str, Any]:
    return {
        "contract_version": EXPECTED_VERSION,
        "input_roles": list(EXPECTED_INPUT_ROLES),
        "data_lake_semantic_excluded_paths": list(EXPECTED_DATA_LAKE_SEMANTIC_EXCLUDED_PATHS),
        "release_summary_normalized_fields": list(EXPECTED_RELEASE_SUMMARY_NORMALIZED_FIELDS),
        "live_normalized_fields": list(EXPECTED_LIVE_NORMALIZED_FIELDS),
        "release_summary_excluded_fields": list(EXPECTED_RELEASE_SUMMARY_EXCLUDED_FIELDS),
        "live_projection_fields": list(EXPECTED_LIVE_FIELDS),
        "contract_policy_projection_fields": list(EXPECTED_CONTRACT_POLICY_FIELDS),
    }


def test_vector_payload() -> dict[str, Any]:
    return {
        "policy": canonical_policy_payload(),
        "probe": {
            "release_ready": False,
            "safe_for_model_claim": False,
            "strict_verified_rows": 4,
            "volatile_existence_only_rows": 2,
            "failure_count": 0,
        },
    }


# These hashes are intentionally independent constants. They are computed from the
# literal payload above and must change whenever policy or canonicalization changes.
EXPECTED_CANONICAL_POLICY_SHA256 = "908529c757d0b821deeeb069712685f22f1945c52301aefddf96d54a4daedcd6"
EXPECTED_TEST_VECTOR_SHA256 = "baba614dc34a232dd161c1e7ba464ef7bd59376839298002d36243e272299977"
EXPECTED_SHARED_CONTRACT_TEST_VECTOR_SHA256 = "7dc168d07300a6322cf5c4f8a6e118cec842e7dbcf5269e0f53823a8b21bdfd1"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_contract_module(path: Path) -> ModuleType:
    spec = importlib.util.spec_from_file_location("local_release_consistency_policy_target", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load semantic contract module: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def add_check(failures: list[dict[str, Any]], check: str, observed: Any, expected: Any) -> None:
    if observed != expected:
        failures.append({"check": check, "observed": observed, "expected": expected})


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
    descriptor, temp_name = tempfile.mkstemp(prefix=f".{path.name}.policy-", dir=path.parent)
    temp_path = Path(temp_name)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(encoded)
            handle.flush()
            os.fsync(handle.fileno())
        if path.exists():
            os.chmod(temp_path, path.stat().st_mode)
        if fail_before_replace:
            raise RuntimeError("simulated_semantic_policy_failure_before_replace")
        os.replace(temp_path, path)
        fsync_directory(path.parent)
    finally:
        if temp_path.exists():
            temp_path.unlink()


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate independent local-release semantic policy anchor")
    parser.add_argument("--contract-module", type=Path, default=CONTRACT_MODULE)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    parser.add_argument("--lock-path", type=Path, default=LOCK_PATH)
    parser.add_argument("--lock-timeout-seconds", type=float, default=30.0)
    parser.add_argument("--fail-before-replace", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()

    output_path = args.output.resolve()
    lock_path = args.lock_path.resolve()
    lock_handle = acquire_lock(lock_path, args.lock_timeout_seconds)
    if lock_handle is None:
        print(json.dumps({"success": False, "error": "semantic_policy_lock_timeout", "lock_path": str(lock_path), "output_preserved": output_path.exists()}, ensure_ascii=False, sort_keys=True))
        return 1

    failures: list[dict[str, Any]] = []
    module: ModuleType | None = None
    if not args.contract_module.is_file():
        failures.append({"check": "contract_module_exists", "observed": str(args.contract_module), "expected": "file"})
    else:
        try:
            module = load_contract_module(args.contract_module)
        except Exception as exc:
            failures.append({"check": "contract_module_loads", "observed": f"{type(exc).__name__}:{exc}", "expected": "loadable"})

    observed_version = getattr(module, "CONTRACT_VERSION", None) if module else None
    observed_roles = tuple(getattr(module, "INPUT_ROLES", ()) or ()) if module else ()
    observed_data_lake_excluded = tuple(sorted(getattr(module, "DATA_LAKE_SEMANTIC_EXCLUDED_PATHS", ()) or ())) if module else ()
    observed_release_normalized = tuple(getattr(module, "RELEASE_SUMMARY_NORMALIZED_FIELDS", ()) or ()) if module else ()
    observed_live_normalized = tuple(getattr(module, "LIVE_NORMALIZED_FIELDS", ()) or ()) if module else ()
    observed_excluded = tuple(sorted(getattr(module, "RELEASE_SUMMARY_EXCLUDED_FIELDS", ()) or ())) if module else ()
    observed_live = tuple(getattr(module, "LIVE_FIELDS", ()) or ()) if module else ()
    observed_policy = tuple(getattr(module, "CONTRACT_POLICY_FIELDS", ()) or ()) if module else ()
    expected_payload = canonical_policy_payload()
    observed_payload = {
        "contract_version": observed_version,
        "input_roles": list(observed_roles),
        "data_lake_semantic_excluded_paths": list(observed_data_lake_excluded),
        "release_summary_normalized_fields": list(observed_release_normalized),
        "live_normalized_fields": list(observed_live_normalized),
        "release_summary_excluded_fields": list(observed_excluded),
        "live_projection_fields": list(observed_live),
        "contract_policy_projection_fields": list(observed_policy),
    }
    add_check(failures, "contract_version_exact", observed_version, EXPECTED_VERSION)
    add_check(failures, "input_roles_exact", observed_roles, EXPECTED_INPUT_ROLES)
    add_check(failures, "data_lake_semantic_excluded_paths_exact", observed_data_lake_excluded, EXPECTED_DATA_LAKE_SEMANTIC_EXCLUDED_PATHS)
    add_check(failures, "release_summary_normalized_fields_exact", observed_release_normalized, EXPECTED_RELEASE_SUMMARY_NORMALIZED_FIELDS)
    add_check(failures, "live_normalized_fields_exact", observed_live_normalized, EXPECTED_LIVE_NORMALIZED_FIELDS)
    add_check(failures, "release_exclusion_fields_exact", observed_excluded, tuple(sorted(EXPECTED_RELEASE_SUMMARY_EXCLUDED_FIELDS)))
    add_check(failures, "live_projection_fields_exact", observed_live, EXPECTED_LIVE_FIELDS)
    add_check(failures, "contract_policy_projection_fields_exact", observed_policy, EXPECTED_CONTRACT_POLICY_FIELDS)
    add_check(failures, "canonical_policy_sha256_exact", canonical_sha256(expected_payload), EXPECTED_CANONICAL_POLICY_SHA256)
    add_check(failures, "observed_policy_payload_sha256_exact", canonical_sha256(observed_payload), EXPECTED_CANONICAL_POLICY_SHA256)
    add_check(failures, "test_vector_sha256_exact", canonical_sha256(test_vector_payload()), EXPECTED_TEST_VECTOR_SHA256)
    observed_shared_vector = None
    if module and callable(getattr(module, "test_vector_sha256", None)):
        try:
            observed_shared_vector = module.test_vector_sha256()
        except Exception as exc:
            failures.append({"check": "shared_contract_test_vector_builds", "observed": f"{type(exc).__name__}:{exc}", "expected": "buildable"})
    add_check(failures, "shared_contract_test_vector_sha256_exact", observed_shared_vector, EXPECTED_SHARED_CONTRACT_TEST_VECTOR_SHA256)

    report = {
        "schema_version": 1,
        "mode": "local_release_consistency_semantic_policy_validation",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "success": not failures,
        "policy_script_path": str(Path(__file__).resolve()),
        "policy_script_sha256": sha256(Path(__file__).resolve()),
        "contract_module_path": str(args.contract_module.resolve()),
        "contract_module_sha256": sha256(args.contract_module) if args.contract_module.is_file() else None,
        "policy_output_path": str(output_path),
        "policy_lock_path": str(lock_path),
        "policy_lock_acquired": True,
        "policy_atomic_commit": True,
        "expected_contract_version": EXPECTED_VERSION,
        "expected_input_roles": list(EXPECTED_INPUT_ROLES),
        "expected_data_lake_semantic_excluded_paths": list(EXPECTED_DATA_LAKE_SEMANTIC_EXCLUDED_PATHS),
        "expected_release_summary_normalized_fields": list(EXPECTED_RELEASE_SUMMARY_NORMALIZED_FIELDS),
        "expected_live_normalized_fields": list(EXPECTED_LIVE_NORMALIZED_FIELDS),
        "expected_release_summary_excluded_fields": list(EXPECTED_RELEASE_SUMMARY_EXCLUDED_FIELDS),
        "expected_live_projection_fields": list(EXPECTED_LIVE_FIELDS),
        "expected_contract_policy_projection_fields": list(EXPECTED_CONTRACT_POLICY_FIELDS),
        "expected_canonical_policy_sha256": EXPECTED_CANONICAL_POLICY_SHA256,
        "expected_test_vector_sha256": EXPECTED_TEST_VECTOR_SHA256,
        "expected_shared_contract_test_vector_sha256": EXPECTED_SHARED_CONTRACT_TEST_VECTOR_SHA256,
        "observed_policy_payload": observed_payload,
        "observed_canonical_policy_sha256": canonical_sha256(observed_payload),
        "observed_test_vector_sha256": canonical_sha256(test_vector_payload()),
        "observed_shared_contract_test_vector_sha256": observed_shared_vector,
        "failure_count": len(failures),
        "failures": failures,
        "safe_for_model_claim": False,
        "release_ready": False,
        "policy": "The independent anchor pins semantic exclusions and projection field sets; it never grants model or release readiness.",
    }
    try:
        write_json_atomic(output_path, report, fail_before_replace=args.fail_before_replace)
    except Exception as exc:
        lock_handle.close()
        print(json.dumps({"success": False, "error": f"semantic_policy_commit_failed:{type(exc).__name__}:{exc}", "output": str(output_path)}, ensure_ascii=False, sort_keys=True))
        return 1
    lock_handle.close()
    print(json.dumps({"success": report["success"], "failure_count": report["failure_count"], "output": str(output_path)}, ensure_ascii=False, sort_keys=True))
    return 0 if report["success"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
