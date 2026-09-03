#!/usr/bin/env python3
"""Pin the shared claim-readiness policy independently from its consumers."""

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
CONTRACT_MODULE = AI_ROOT / "scripts" / "claim_readiness_policy_contract.py"
OUTPUT = AI_ROOT / "reports" / "claim_readiness_policy_anchor_validation_report.json"
LOCK_PATH = AI_ROOT / "reports" / ".claim_readiness_policy_anchor.lock"

EXPECTED_POLICY_VERSION = "claim-readiness-policy-v1"
EXPECTED_MUST_ALLOW_INTERNAL_CLAIM_IDS = ("internal_design_review_artifacts",)
EXPECTED_CONDITIONAL_INTERNAL_CLAIM_IDS = ("local_safe_training_pipeline",)
EXPECTED_BLOCKED_CLAIM_IDS = (
    "active_learning_experiment_submission",
    "approved_for_ordering",
    "biosecurity_screened",
    "customer_sequence_package",
    "external_tool_production_use",
    "five_head_training_run",
    "ip_fto_cleared",
    "local_release_review_package",
    "model_quality_claim",
)
EXPECTED_CANONICAL_CLAIM_IDS = tuple(sorted(
    set(EXPECTED_MUST_ALLOW_INTERNAL_CLAIM_IDS)
    | set(EXPECTED_CONDITIONAL_INTERNAL_CLAIM_IDS)
    | set(EXPECTED_BLOCKED_CLAIM_IDS)
))
EXPECTED_CANONICAL_POLICY_SHA256 = "c905ad3ae3d0cb52f4b301f30c377cd85c2e461ca79d73ff611bebf33743f64d"
EXPECTED_TEST_VECTOR_SHA256 = "11b1cec3bb19f327ed834b826cd4f6a4e431f53e2f290d3e649cdff4a29a4ef6"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def canonical_sha256(payload: Any) -> str:
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def expected_policy_payload() -> dict[str, Any]:
    return {
        "policy_version": EXPECTED_POLICY_VERSION,
        "canonical_claim_ids": list(EXPECTED_CANONICAL_CLAIM_IDS),
        "must_allow_internal_claim_ids": list(EXPECTED_MUST_ALLOW_INTERNAL_CLAIM_IDS),
        "conditional_internal_claim_ids": list(EXPECTED_CONDITIONAL_INTERNAL_CLAIM_IDS),
        "blocked_claim_ids": list(EXPECTED_BLOCKED_CLAIM_IDS),
    }


def load_contract_module(path: Path) -> ModuleType:
    spec = importlib.util.spec_from_file_location("claim_readiness_policy_anchor_target", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load claim policy contract: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def observed_policy_payload(module: ModuleType) -> dict[str, Any]:
    return {
        "policy_version": getattr(module, "POLICY_VERSION", None),
        "canonical_claim_ids": sorted(getattr(module, "CANONICAL_CLAIM_IDS", ()) or ()),
        "must_allow_internal_claim_ids": sorted(getattr(module, "MUST_ALLOW_INTERNAL_CLAIM_IDS", ()) or ()),
        "conditional_internal_claim_ids": sorted(getattr(module, "CONDITIONAL_INTERNAL_CLAIM_IDS", ()) or ()),
        "blocked_claim_ids": sorted(getattr(module, "BLOCKED_CLAIM_IDS", ()) or ()),
    }


def policy_failures(payload: dict[str, Any], policy_sha256: str | None, test_vector_sha256: str | None) -> list[dict[str, Any]]:
    failures: list[dict[str, Any]] = []
    expected = expected_policy_payload()
    for field, expected_value in expected.items():
        if payload.get(field) != expected_value:
            failures.append({"check": f"{field}_exact", "observed": payload.get(field), "expected": expected_value})
    if policy_sha256 != EXPECTED_CANONICAL_POLICY_SHA256:
        failures.append({"check": "canonical_policy_sha256_exact", "observed": policy_sha256, "expected": EXPECTED_CANONICAL_POLICY_SHA256})
    if test_vector_sha256 != EXPECTED_TEST_VECTOR_SHA256:
        failures.append({"check": "test_vector_sha256_exact", "observed": test_vector_sha256, "expected": EXPECTED_TEST_VECTOR_SHA256})
    return failures


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
    descriptor, temp_name = tempfile.mkstemp(prefix=f".{path.name}.claim-anchor-", dir=path.parent)
    temp_path = Path(temp_name)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write((json.dumps(payload, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))
            handle.flush()
            os.fsync(handle.fileno())
        if path.exists():
            os.chmod(temp_path, path.stat().st_mode)
        if fail_before_replace:
            raise RuntimeError("simulated_claim_policy_anchor_failure_before_replace")
        os.replace(temp_path, path)
        directory = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        if temp_path.exists():
            temp_path.unlink()


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate independent claim-readiness policy anchor")
    parser.add_argument("--contract-module", type=Path, default=CONTRACT_MODULE)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    parser.add_argument("--lock-path", type=Path, default=LOCK_PATH)
    parser.add_argument("--lock-timeout-seconds", type=float, default=30.0)
    parser.add_argument("--fail-before-replace", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()

    contract_path = args.contract_module.resolve()
    output_path = args.output.resolve()
    lock_path = args.lock_path.resolve()
    validator_path = Path(__file__).resolve()
    lock_handle = acquire_lock(lock_path, args.lock_timeout_seconds)
    if lock_handle is None:
        print(json.dumps({"success": False, "error": "claim_policy_anchor_lock_timeout", "output_preserved": output_path.exists()}, ensure_ascii=False, sort_keys=True))
        return 1

    failures: list[dict[str, Any]] = []
    observed_payload: dict[str, Any] = {}
    observed_policy_sha: str | None = None
    observed_test_vector_sha: str | None = None
    if not contract_path.is_file():
        failures.append({"check": "contract_module_exists", "observed": str(contract_path), "expected": "file"})
    else:
        try:
            module = load_contract_module(contract_path)
            observed_payload = observed_policy_payload(module)
            observed_policy_sha = module.canonical_policy_sha256() if callable(getattr(module, "canonical_policy_sha256", None)) else canonical_sha256(observed_payload)
            observed_test_vector_sha = module.test_vector_sha256() if callable(getattr(module, "test_vector_sha256", None)) else None
            failures.extend(policy_failures(observed_payload, observed_policy_sha, observed_test_vector_sha))
        except Exception as exc:
            failures.append({"check": "contract_module_loads", "observed": f"{type(exc).__name__}:{exc}", "expected": "loadable"})

    report = {
        "schema_version": 1,
        "mode": "claim_readiness_policy_anchor_validation",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "local_only": True,
        "success": not failures,
        "failure_count": len(failures),
        "failures": failures,
        "anchor_validator_path": str(validator_path),
        "anchor_validator_sha256": sha256(validator_path),
        "contract_module_path": str(contract_path),
        "contract_module_sha256": sha256(contract_path) if contract_path.is_file() else None,
        "output_path": str(output_path),
        "lock_path": str(lock_path),
        "lock_acquired": True,
        "atomic_commit": True,
        "expected_policy_payload": expected_policy_payload(),
        "expected_canonical_policy_sha256": EXPECTED_CANONICAL_POLICY_SHA256,
        "expected_test_vector_sha256": EXPECTED_TEST_VECTOR_SHA256,
        "observed_policy_payload": observed_payload,
        "observed_canonical_policy_sha256": observed_policy_sha,
        "observed_test_vector_sha256": observed_test_vector_sha,
        "safe_for_model_claim": False,
        "release_ready": False,
        "policy": "The independent anchor detects shared claim-policy drift and never grants claim or release readiness.",
    }
    try:
        write_json_atomic(output_path, report, fail_before_replace=args.fail_before_replace)
    except Exception as exc:
        lock_handle.close()
        print(json.dumps({"success": False, "error": f"claim_policy_anchor_commit_failed:{type(exc).__name__}:{exc}"}, ensure_ascii=False, sort_keys=True))
        return 1
    lock_handle.close()
    print(json.dumps({"success": report["success"], "failure_count": report["failure_count"], "output": str(output_path)}, ensure_ascii=False, sort_keys=True))
    return 0 if report["success"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
