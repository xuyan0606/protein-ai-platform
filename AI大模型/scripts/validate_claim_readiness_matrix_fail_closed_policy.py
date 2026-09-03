#!/usr/bin/env python3
"""Validate claim readiness matrix remains fail-closed for external/model claims."""

from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from claim_readiness_policy_contract import (
    BLOCKED_CLAIM_IDS,
    CANONICAL_CLAIM_IDS,
    CONDITIONAL_INTERNAL_CLAIM_IDS,
    INTERNAL_CLAIM_IDS,
    MUST_ALLOW_INTERNAL_CLAIM_IDS,
    POLICY_VERSION,
    canonical_policy_sha256,
    test_vector_sha256,
)


AI_ROOT = Path(__file__).resolve().parents[1]
CLAIM_MATRIX = AI_ROOT / "reports" / "claim_readiness_matrix.json"
OUT = AI_ROOT / "reports" / "claim_readiness_matrix_fail_closed_policy_validation_report.json"
BUILDER = AI_ROOT / "scripts" / "build_claim_readiness_matrix.py"
POLICY_CONTRACT = AI_ROOT / "scripts" / "claim_readiness_policy_contract.py"
POLICY_ANCHOR_VALIDATOR = AI_ROOT / "scripts" / "validate_claim_readiness_policy_anchor.py"
POLICY_ANCHOR_REPORT = AI_ROOT / "reports" / "claim_readiness_policy_anchor_validation_report.json"
LOCK_PATH = AI_ROOT / "reports" / ".claim_readiness_matrix_fail_closed_policy.lock"
EXPECTED_ANCHOR_POLICY_SHA256 = "c905ad3ae3d0cb52f4b301f30c377cd85c2e461ca79d73ff611bebf33743f64d"
EXPECTED_ANCHOR_TEST_VECTOR_SHA256 = "11b1cec3bb19f327ed834b826cd4f6a4e431f53e2f290d3e649cdff4a29a4ef6"

HIGH_RISK_SCOPES = {
    "model_claim",
    "training",
    "experiment_submission",
    "customer_delivery",
    "ordering",
    "legal_review",
    "biosecurity",
    "tooling",
    "release_review",
}

def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


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
    descriptor, temp_name = tempfile.mkstemp(prefix=f".{path.name}.claim-policy-", dir=path.parent)
    temp_path = Path(temp_name)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write((json.dumps(payload, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))
            handle.flush()
            os.fsync(handle.fileno())
        if path.exists():
            os.chmod(temp_path, path.stat().st_mode)
        if fail_before_replace:
            raise RuntimeError("simulated_claim_policy_failure_before_replace")
        os.replace(temp_path, path)
        fsync_directory(path.parent)
    finally:
        if temp_path.exists():
            temp_path.unlink()


def rebuild_expected_matrix(builder: Path) -> tuple[dict[str, Any], str | None]:
    with tempfile.TemporaryDirectory(prefix="claim-matrix-source-parity-") as name:
        output = Path(name) / "claim_readiness_matrix.json"
        result = subprocess.run(
            [sys.executable, str(builder), "--output", str(output)],
            cwd=AI_ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0 or not output.exists():
            detail = result.stderr.strip() or result.stdout.strip() or f"returncode={result.returncode}"
            return {}, detail
        return load_json(output), None


def source_parity_failures(matrix: dict[str, Any], expected: dict[str, Any]) -> list[dict[str, Any]]:
    if matrix == expected:
        return []
    failures: list[dict[str, Any]] = []
    actual_claims = {
        str(row.get("claim_id")): row
        for row in matrix.get("claims") or []
        if isinstance(row, dict)
    }
    expected_claims = {
        str(row.get("claim_id")): row
        for row in expected.get("claims") or []
        if isinstance(row, dict)
    }
    if set(actual_claims) != set(expected_claims):
        failures.append({
            "check": "source_parity_claim_ids",
            "observed": sorted(actual_claims),
            "expected": sorted(expected_claims),
        })
    for claim_id in sorted(set(actual_claims) & set(expected_claims)):
        actual = actual_claims[claim_id]
        expected_row = expected_claims[claim_id]
        if actual != expected_row:
            failures.append({
                "check": "source_parity_claim_row",
                "claim_id": claim_id,
                "observed": actual,
                "expected": expected_row,
            })
    for field in [
        "local_only",
        "claims_allowed",
        "claims_blocked",
        "allowed_claim_ids",
        "blocked_claim_ids",
        "global_policy",
    ]:
        if matrix.get(field) != expected.get(field):
            failures.append({
                "check": f"source_parity_{field}",
                "observed": matrix.get(field),
                "expected": expected.get(field),
            })
    return failures


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate claim readiness fail-closed policy")
    parser.add_argument("--claim-matrix", type=Path, default=CLAIM_MATRIX)
    parser.add_argument("--builder", type=Path, default=BUILDER)
    parser.add_argument("--output", type=Path, default=OUT)
    parser.add_argument("--lock-path", type=Path, default=LOCK_PATH)
    parser.add_argument("--lock-timeout-seconds", type=float, default=30.0)
    parser.add_argument("--fail-before-replace", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()

    output_path = args.output.resolve()
    lock_path = args.lock_path.resolve()
    matrix_path = args.claim_matrix.resolve()
    builder_path = args.builder.resolve()
    policy_contract_path = POLICY_CONTRACT.resolve()
    policy_anchor_validator_path = POLICY_ANCHOR_VALIDATOR.resolve()
    policy_anchor_report_path = POLICY_ANCHOR_REPORT.resolve()
    validator_path = Path(__file__).resolve()
    lock_handle = acquire_lock(lock_path, args.lock_timeout_seconds)
    if lock_handle is None:
        print(json.dumps({
            "success": False,
            "error": "claim_policy_lock_timeout",
            "lock_path": str(lock_path),
            "output_preserved": output_path.exists(),
        }, ensure_ascii=False, sort_keys=True))
        return 1

    matrix_bytes = matrix_path.read_bytes() if matrix_path.is_file() else b""
    anchor_bytes = policy_anchor_report_path.read_bytes() if policy_anchor_report_path.is_file() else b""
    anchor_report = json.loads(anchor_bytes.decode("utf-8")) if anchor_bytes else {}
    matrix = json.loads(matrix_bytes.decode("utf-8")) if matrix_bytes else {}
    claims = [row for row in matrix.get("claims") or [] if isinstance(row, dict)]
    failures: list[dict[str, Any]] = []
    anchor_checks = {
        "policy_anchor_success": (anchor_report.get("success"), True),
        "policy_anchor_failure_count": (anchor_report.get("failure_count"), 0),
        "policy_anchor_contract_path": (anchor_report.get("contract_module_path"), str(policy_contract_path)),
        "policy_anchor_contract_sha256": (anchor_report.get("contract_module_sha256"), sha256(policy_contract_path) if policy_contract_path.is_file() else None),
        "policy_anchor_validator_path": (anchor_report.get("anchor_validator_path"), str(policy_anchor_validator_path)),
        "policy_anchor_validator_sha256": (anchor_report.get("anchor_validator_sha256"), sha256(policy_anchor_validator_path) if policy_anchor_validator_path.is_file() else None),
        "policy_anchor_policy_version": ((anchor_report.get("expected_policy_payload") or {}).get("policy_version"), POLICY_VERSION),
        "policy_anchor_policy_sha256": (anchor_report.get("observed_canonical_policy_sha256"), canonical_policy_sha256()),
        "policy_anchor_test_vector_sha256": (anchor_report.get("observed_test_vector_sha256"), test_vector_sha256()),
        "policy_anchor_expected_policy_sha256": (anchor_report.get("expected_canonical_policy_sha256"), EXPECTED_ANCHOR_POLICY_SHA256),
        "policy_anchor_expected_test_vector_sha256": (anchor_report.get("expected_test_vector_sha256"), EXPECTED_ANCHOR_TEST_VECTOR_SHA256),
        "independent_policy_sha256": (canonical_policy_sha256(), EXPECTED_ANCHOR_POLICY_SHA256),
        "independent_test_vector_sha256": (test_vector_sha256(), EXPECTED_ANCHOR_TEST_VECTOR_SHA256),
        "policy_anchor_safe_for_model_claim_false": (anchor_report.get("safe_for_model_claim"), False),
        "policy_anchor_release_ready_false": (anchor_report.get("release_ready"), False),
    }
    for check, (observed, expected) in anchor_checks.items():
        if observed != expected:
            failures.append({"check": check, "observed": observed, "expected": expected})

    expected_matrix, rebuild_error = rebuild_expected_matrix(args.builder)
    parity_failures = [] if rebuild_error else source_parity_failures(matrix, expected_matrix)
    if rebuild_error:
        failures.append({"check": "source_parity_rebuild", "error": rebuild_error})
    failures.extend(parity_failures)

    claim_ids = {str(row.get("claim_id")) for row in claims}
    allowed_ids = {str(row.get("claim_id")) for row in claims if row.get("allowed") is True}
    ready_ids = {str(row.get("claim_id")) for row in claims if row.get("ready") is True}
    blocked_ids = claim_ids - allowed_ids

    summary_allowed_ids = set(matrix.get("allowed_claim_ids") or [])
    summary_blocked_ids = set(matrix.get("blocked_claim_ids") or [])
    local_safe_row = next((row for row in claims if row.get("claim_id") == "local_safe_training_pipeline"), {})
    local_safe_allowed = local_safe_row.get("allowed") is True
    expected_allowed_ids = set(MUST_ALLOW_INTERNAL_CLAIM_IDS)
    if local_safe_allowed:
        expected_allowed_ids.add("local_safe_training_pipeline")
    expected_blocked_ids = claim_ids - expected_allowed_ids

    if claim_ids != CANONICAL_CLAIM_IDS:
        failures.append({
            "check": "canonical_claim_ids_exact",
            "observed": sorted(claim_ids),
            "expected": sorted(CANONICAL_CLAIM_IDS),
        })
    if len(claims) != len(claim_ids):
        failures.append({
            "check": "claim_ids_unique",
            "claim_rows": len(claims),
            "unique_claim_ids": len(claim_ids),
        })

    if allowed_ids != expected_allowed_ids:
        failures.append({"check": "allowed_claim_ids_exact", "observed": sorted(allowed_ids), "expected": sorted(expected_allowed_ids)})
    if allowed_ids - INTERNAL_CLAIM_IDS:
        failures.append({"check": "non_internal_claim_allowed", "observed": sorted(allowed_ids - INTERNAL_CLAIM_IDS), "expected_allowed_scope": sorted(INTERNAL_CLAIM_IDS)})
    if not MUST_ALLOW_INTERNAL_CLAIM_IDS.issubset(allowed_ids):
        failures.append({"check": "required_internal_claim_not_allowed", "observed_missing": sorted(MUST_ALLOW_INTERNAL_CLAIM_IDS - allowed_ids)})
    if not BLOCKED_CLAIM_IDS.issubset(blocked_ids):
        failures.append({"check": "blocked_claim_ids_include_all_high_risk", "observed_missing": sorted(BLOCKED_CLAIM_IDS - blocked_ids), "expected_blocked": sorted(BLOCKED_CLAIM_IDS)})
    if summary_allowed_ids != allowed_ids:
        failures.append({"check": "matrix_allowed_claim_ids_match_rows", "observed": matrix.get("allowed_claim_ids"), "expected": sorted(allowed_ids)})
    if summary_blocked_ids != blocked_ids:
        failures.append({"check": "matrix_blocked_claim_ids_match_rows", "observed": matrix.get("blocked_claim_ids"), "expected": sorted(blocked_ids)})
    if matrix.get("claims_allowed") != len(allowed_ids):
        failures.append({"check": "claims_allowed_count", "observed": matrix.get("claims_allowed"), "expected": len(allowed_ids)})
    if matrix.get("claims_blocked") != len(blocked_ids):
        failures.append({"check": "claims_blocked_count", "observed": matrix.get("claims_blocked"), "expected": len(blocked_ids)})

    for row in claims:
        claim_id = str(row.get("claim_id"))
        scope = str(row.get("scope") or "")
        row_failures: list[str] = []
        if claim_id in MUST_ALLOW_INTERNAL_CLAIM_IDS:
            if row.get("ready") is not True or row.get("allowed") is not True or row.get("status") != "allowed":
                row_failures.append("internal_claim_not_allowed")
            if "not customer-ready" not in str(row.get("policy") or ""):
                row_failures.append("internal_design_policy_missing_customer_exclusion")
        if claim_id == "local_safe_training_pipeline":
            policy = str(row.get("policy") or "")
            if "not model-quality" not in policy:
                row_failures.append("local_pipeline_policy_missing_model_claim_exclusion")
            if row.get("allowed") is True:
                if row.get("ready") is not True or row.get("status") != "allowed":
                    row_failures.append("local_pipeline_allowed_but_not_ready")
            else:
                if row.get("status") != "blocked" or row.get("ready") is not False:
                    row_failures.append("local_pipeline_block_state_invalid")
                if not row.get("missing_requirements"):
                    row_failures.append("local_pipeline_blocked_without_missing_requirements")
        if claim_id in BLOCKED_CLAIM_IDS or scope in HIGH_RISK_SCOPES:
            if row.get("ready") is not False or row.get("allowed") is not False or row.get("status") != "blocked":
                row_failures.append("high_risk_claim_not_blocked")
            if not row.get("missing_requirements"):
                row_failures.append("blocked_claim_missing_requirements_empty")
        if claim_id not in INTERNAL_CLAIM_IDS and claim_id not in BLOCKED_CLAIM_IDS:
            row_failures.append("unknown_claim_id_not_policy_classified")
        if row_failures:
            failures.append({
                "check": "claim_row_policy",
                "claim_id": claim_id,
                "scope": scope,
                "failures": row_failures,
                "ready": row.get("ready"),
                "allowed": row.get("allowed"),
                "status": row.get("status"),
            })

    report = {
        "schema_version": 2,
        "mode": "claim_readiness_matrix_fail_closed_policy_validation",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "local_only": True,
        "success": not failures,
        "claim_rows": len(claims),
        "ready_claim_ids": sorted(ready_ids),
        "allowed_claim_ids": sorted(allowed_ids),
        "blocked_claim_ids": sorted(blocked_ids),
        "expected_allowed_claim_ids": sorted(expected_allowed_ids),
        "expected_blocked_claim_ids": sorted(expected_blocked_ids),
        "canonical_claim_ids": sorted(CANONICAL_CLAIM_IDS),
        "policy_version": POLICY_VERSION,
        "canonical_policy_sha256": canonical_policy_sha256(),
        "policy_test_vector_sha256": test_vector_sha256(),
        "policy_contract_path": str(policy_contract_path),
        "policy_contract_sha256": sha256(policy_contract_path) if policy_contract_path.is_file() else None,
        "policy_anchor_report_path": str(policy_anchor_report_path),
        "policy_anchor_report_sha256": hashlib.sha256(anchor_bytes).hexdigest() if anchor_bytes else None,
        "policy_anchor_success": anchor_report.get("success") is True and anchor_report.get("failure_count") == 0,
        "policy_anchor_validator_path": str(policy_anchor_validator_path),
        "policy_anchor_validator_sha256": sha256(policy_anchor_validator_path) if policy_anchor_validator_path.is_file() else None,
        "policy_anchor_expected_policy_sha256": EXPECTED_ANCHOR_POLICY_SHA256,
        "policy_anchor_expected_test_vector_sha256": EXPECTED_ANCHOR_TEST_VECTOR_SHA256,
        "source_parity_success": rebuild_error is None and not parity_failures,
        "all_claims_ready": ready_ids == CANONICAL_CLAIM_IDS,
        "not_ready_claim_ids": sorted(CANONICAL_CLAIM_IDS - ready_ids),
        "promotion_policy_allows_all_claims": allowed_ids == CANONICAL_CLAIM_IDS,
        "validator_path": str(validator_path),
        "validator_sha256": sha256(validator_path),
        "builder_path": str(builder_path),
        "builder_sha256": sha256(builder_path) if builder_path.is_file() else None,
        "claim_matrix_path": str(matrix_path),
        "claim_matrix_sha256": hashlib.sha256(matrix_bytes).hexdigest() if matrix_bytes else None,
        "policy_output_path": str(output_path),
        "policy_lock_path": str(lock_path),
        "policy_lock_acquired": True,
        "policy_atomic_commit": True,
        "failures": failures,
        "safe_for_training_pipeline": bool(local_safe_allowed),
        "safe_for_model_claim": False,
        "release_ready": False,
        "policy": "Only local/internal engineering claims may be allowed. Model, training, customer, ordering, IP/FTO, biosecurity, external-tool and release claims must stay blocked until formal gates pass.",
    }
    if not matrix_path.is_file() or matrix_path.read_bytes() != matrix_bytes:
        failures.append({"check": "claim_matrix_unchanged_during_validation", "expected": "snapshot bytes unchanged"})
        report["success"] = False
        report["source_parity_success"] = False
    if not policy_anchor_report_path.is_file() or policy_anchor_report_path.read_bytes() != anchor_bytes:
        failures.append({"check": "policy_anchor_unchanged_during_validation", "expected": "snapshot bytes unchanged"})
        report["success"] = False
    report["failure_count"] = len(failures)
    try:
        write_json_atomic(output_path, report, fail_before_replace=args.fail_before_replace)
    except Exception as exc:
        lock_handle.close()
        print(json.dumps({
            "success": False,
            "error": f"claim_policy_commit_failed:{type(exc).__name__}:{exc}",
            "output": str(output_path),
        }, ensure_ascii=False, sort_keys=True))
        return 1
    lock_handle.close()
    print(json.dumps({
        "success": report["success"],
        "claim_rows": report["claim_rows"],
        "allowed_claim_ids": report["allowed_claim_ids"],
        "blocked_claim_count": len(report["blocked_claim_ids"]),
        "failures": len(failures),
        "output": str(output_path),
    }, ensure_ascii=False))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
