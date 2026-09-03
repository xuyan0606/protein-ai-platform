#!/usr/bin/env python3
"""Validate the claim-readiness policy receipt against current files."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import validate_claim_readiness_matrix_fail_closed_policy as signer


AI_ROOT = Path(__file__).resolve().parents[1]
RECEIPT = AI_ROOT / "reports" / "claim_readiness_matrix_fail_closed_policy_validation_report.json"
OUTPUT = AI_ROOT / "reports" / "claim_readiness_matrix_fail_closed_policy_current_validation_report.json"
LOCK_PATH = AI_ROOT / "reports" / ".claim_readiness_matrix_fail_closed_policy_current.lock"


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}


def add_check(failures: list[dict[str, Any]], check: str, observed: Any, expected: Any) -> None:
    if observed != expected:
        failures.append({"check": check, "observed": observed, "expected": expected})


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate current claim-readiness policy receipt")
    parser.add_argument("--receipt", type=Path, default=RECEIPT)
    parser.add_argument("--signer", type=Path, default=Path(signer.__file__).resolve())
    parser.add_argument("--builder", type=Path, default=signer.BUILDER)
    parser.add_argument("--claim-matrix", type=Path, default=signer.CLAIM_MATRIX)
    parser.add_argument("--policy-contract", type=Path, default=signer.POLICY_CONTRACT)
    parser.add_argument("--policy-anchor-validator", type=Path, default=signer.POLICY_ANCHOR_VALIDATOR)
    parser.add_argument("--policy-anchor-report", type=Path, default=signer.POLICY_ANCHOR_REPORT)
    parser.add_argument("--signer-lock-path", type=Path, default=signer.LOCK_PATH)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    parser.add_argument("--lock-path", type=Path, default=LOCK_PATH)
    parser.add_argument("--lock-timeout-seconds", type=float, default=30.0)
    parser.add_argument("--fail-before-replace", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()

    receipt_path = args.receipt.resolve()
    signer_path = args.signer.resolve()
    builder_path = args.builder.resolve()
    matrix_path = args.claim_matrix.resolve()
    policy_contract_path = args.policy_contract.resolve()
    policy_anchor_validator_path = args.policy_anchor_validator.resolve()
    policy_anchor_report_path = args.policy_anchor_report.resolve()
    signer_lock_path = args.signer_lock_path.resolve()
    output_path = args.output.resolve()
    lock_path = args.lock_path.resolve()
    current_path = Path(__file__).resolve()

    lock_handle = signer.acquire_lock(lock_path, args.lock_timeout_seconds)
    if lock_handle is None:
        print(json.dumps({
            "success": False,
            "error": "claim_policy_current_lock_timeout",
            "lock_path": str(lock_path),
            "output_preserved": output_path.exists(),
        }, ensure_ascii=False, sort_keys=True))
        return 1

    receipt = load_json(receipt_path)
    matrix = load_json(matrix_path)
    anchor_report = load_json(policy_anchor_report_path)
    failures: list[dict[str, Any]] = []
    add_check(failures, "schema_version", receipt.get("schema_version"), 2)
    add_check(failures, "mode", receipt.get("mode"), "claim_readiness_matrix_fail_closed_policy_validation")
    add_check(failures, "receipt_success", receipt.get("success"), True)
    add_check(failures, "source_parity_success", receipt.get("source_parity_success"), True)
    add_check(failures, "receipt_failure_count", receipt.get("failure_count"), 0)
    add_check(failures, "receipt_failures", receipt.get("failures"), [])
    add_check(failures, "safe_for_model_claim_false", receipt.get("safe_for_model_claim"), False)
    add_check(failures, "release_ready_false", receipt.get("release_ready"), False)
    add_check(failures, "policy_lock_acquired", receipt.get("policy_lock_acquired"), True)
    add_check(failures, "policy_atomic_commit", receipt.get("policy_atomic_commit"), True)
    add_check(failures, "validator_path", receipt.get("validator_path"), str(signer_path))
    add_check(failures, "builder_path", receipt.get("builder_path"), str(builder_path))
    add_check(failures, "claim_matrix_path", receipt.get("claim_matrix_path"), str(matrix_path))
    add_check(failures, "policy_output_path", receipt.get("policy_output_path"), str(receipt_path))
    add_check(failures, "policy_lock_path", receipt.get("policy_lock_path"), str(signer_lock_path))
    add_check(failures, "validator_sha256", receipt.get("validator_sha256"), signer.sha256(signer_path) if signer_path.is_file() else None)
    add_check(failures, "builder_sha256", receipt.get("builder_sha256"), signer.sha256(builder_path) if builder_path.is_file() else None)
    add_check(failures, "claim_matrix_sha256", receipt.get("claim_matrix_sha256"), signer.sha256(matrix_path) if matrix_path.is_file() else None)
    add_check(failures, "policy_contract_path", receipt.get("policy_contract_path"), str(policy_contract_path))
    add_check(failures, "policy_contract_sha256", receipt.get("policy_contract_sha256"), signer.sha256(policy_contract_path) if policy_contract_path.is_file() else None)
    add_check(failures, "policy_anchor_report_path", receipt.get("policy_anchor_report_path"), str(policy_anchor_report_path))
    add_check(failures, "policy_anchor_report_sha256", receipt.get("policy_anchor_report_sha256"), signer.sha256(policy_anchor_report_path) if policy_anchor_report_path.is_file() else None)
    add_check(failures, "policy_anchor_success", receipt.get("policy_anchor_success"), True)
    add_check(failures, "policy_anchor_validator_path", receipt.get("policy_anchor_validator_path"), str(policy_anchor_validator_path))
    add_check(failures, "policy_anchor_validator_sha256", receipt.get("policy_anchor_validator_sha256"), signer.sha256(policy_anchor_validator_path) if policy_anchor_validator_path.is_file() else None)
    add_check(failures, "policy_anchor_expected_policy_sha256", receipt.get("policy_anchor_expected_policy_sha256"), signer.EXPECTED_ANCHOR_POLICY_SHA256)
    add_check(failures, "policy_anchor_expected_test_vector_sha256", receipt.get("policy_anchor_expected_test_vector_sha256"), signer.EXPECTED_ANCHOR_TEST_VECTOR_SHA256)
    add_check(failures, "live_policy_anchor_success", anchor_report.get("success"), True)
    add_check(failures, "live_policy_anchor_failure_count", anchor_report.get("failure_count"), 0)
    add_check(failures, "live_policy_anchor_contract_path", anchor_report.get("contract_module_path"), str(policy_contract_path))
    add_check(failures, "live_policy_anchor_contract_sha256", anchor_report.get("contract_module_sha256"), signer.sha256(policy_contract_path) if policy_contract_path.is_file() else None)
    add_check(failures, "live_policy_anchor_validator_sha256", anchor_report.get("anchor_validator_sha256"), signer.sha256(policy_anchor_validator_path) if policy_anchor_validator_path.is_file() else None)
    add_check(failures, "live_policy_anchor_expected_policy_sha256", anchor_report.get("expected_canonical_policy_sha256"), signer.EXPECTED_ANCHOR_POLICY_SHA256)
    add_check(failures, "live_policy_anchor_expected_test_vector_sha256", anchor_report.get("expected_test_vector_sha256"), signer.EXPECTED_ANCHOR_TEST_VECTOR_SHA256)

    expected_matrix, rebuild_error = signer.rebuild_expected_matrix(builder_path)
    if rebuild_error:
        failures.append({"check": "current_source_parity_rebuild", "error": rebuild_error})
    else:
        failures.extend(
            {"check": f"current_{item['check']}", **{key: value for key, value in item.items() if key != "check"}}
            for item in signer.source_parity_failures(matrix, expected_matrix)
        )

    report = {
        "schema_version": 1,
        "mode": "claim_readiness_matrix_fail_closed_policy_current_validation",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "local_only": True,
        "success": not failures,
        "failure_count": len(failures),
        "failures": failures,
        "current_validator_path": str(current_path),
        "current_validator_sha256": signer.sha256(current_path),
        "signer_path": str(signer_path),
        "signer_sha256": signer.sha256(signer_path) if signer_path.is_file() else None,
        "builder_path": str(builder_path),
        "builder_sha256": signer.sha256(builder_path) if builder_path.is_file() else None,
        "claim_matrix_path": str(matrix_path),
        "claim_matrix_sha256": signer.sha256(matrix_path) if matrix_path.is_file() else None,
        "policy_contract_path": str(policy_contract_path),
        "policy_contract_sha256": signer.sha256(policy_contract_path) if policy_contract_path.is_file() else None,
        "policy_anchor_report_path": str(policy_anchor_report_path),
        "policy_anchor_report_sha256": signer.sha256(policy_anchor_report_path) if policy_anchor_report_path.is_file() else None,
        "policy_anchor_validator_path": str(policy_anchor_validator_path),
        "policy_anchor_validator_sha256": signer.sha256(policy_anchor_validator_path) if policy_anchor_validator_path.is_file() else None,
        "policy_anchor_expected_policy_sha256": signer.EXPECTED_ANCHOR_POLICY_SHA256,
        "policy_anchor_expected_test_vector_sha256": signer.EXPECTED_ANCHOR_TEST_VECTOR_SHA256,
        "receipt_path": str(receipt_path),
        "receipt_sha256": signer.sha256(receipt_path) if receipt_path.is_file() else None,
        "current_output_path": str(output_path),
        "current_lock_path": str(lock_path),
        "current_lock_acquired": True,
        "current_atomic_commit": True,
        "source_parity_success": rebuild_error is None and not signer.source_parity_failures(matrix, expected_matrix),
        "safe_for_model_claim": False,
        "release_ready": False,
        "policy": "Current validation proves the policy receipt matches live code and matrix bytes; it grants no model or release claim.",
    }
    try:
        signer.write_json_atomic(output_path, report, fail_before_replace=args.fail_before_replace)
    except Exception as exc:
        lock_handle.close()
        print(json.dumps({
            "success": False,
            "error": f"claim_policy_current_commit_failed:{type(exc).__name__}:{exc}",
            "output": str(output_path),
        }, ensure_ascii=False, sort_keys=True))
        return 1
    lock_handle.close()
    print(json.dumps({
        "success": report["success"],
        "failure_count": report["failure_count"],
        "output": str(output_path),
    }, ensure_ascii=False, sort_keys=True))
    return 0 if report["success"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
