#!/usr/bin/env python3
"""Exercise independent claim-policy anchor drift detection in memory."""

from __future__ import annotations

import argparse
import copy
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

import validate_claim_readiness_policy_anchor as anchor


AI_ROOT = Path(__file__).resolve().parents[1]
OUTPUT = AI_ROOT / "reports" / "claim_readiness_policy_anchor_regression_report.json"
LOCK_PATH = AI_ROOT / "reports" / ".claim_readiness_policy_anchor_regression.lock"


def main() -> int:
    parser = argparse.ArgumentParser(description="Run independent claim policy anchor regression")
    parser.add_argument("--output", type=Path, default=OUTPUT)
    parser.add_argument("--lock-path", type=Path, default=LOCK_PATH)
    parser.add_argument("--lock-timeout-seconds", type=float, default=30.0)
    parser.add_argument("--fail-before-replace", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()

    output_path = args.output.resolve()
    lock_path = args.lock_path.resolve()
    lock_handle = anchor.acquire_lock(lock_path, args.lock_timeout_seconds)
    if lock_handle is None:
        print(json.dumps({"success": False, "error": "claim_policy_anchor_regression_lock_timeout", "output_preserved": output_path.exists()}, ensure_ascii=False, sort_keys=True))
        return 1

    expected = anchor.expected_policy_payload()
    cases: list[tuple[str, Callable[[dict[str, Any]], None], str]] = [
        ("policy_version_drift", lambda payload: payload.update(policy_version="claim-readiness-policy-v2"), "policy_version_exact"),
        ("claim_set_expanded", lambda payload: payload["canonical_claim_ids"].append("forged_claim"), "canonical_claim_ids_exact"),
        ("claim_set_removed", lambda payload: payload["canonical_claim_ids"].pop(), "canonical_claim_ids_exact"),
        ("must_allow_set_drift", lambda payload: payload["must_allow_internal_claim_ids"].append("model_quality_claim"), "must_allow_internal_claim_ids_exact"),
        ("conditional_set_drift", lambda payload: payload["conditional_internal_claim_ids"].clear(), "conditional_internal_claim_ids_exact"),
        ("blocked_set_drift", lambda payload: payload["blocked_claim_ids"].remove("model_quality_claim"), "blocked_claim_ids_exact"),
    ]
    rows: list[dict[str, Any]] = []
    control_failures = anchor.policy_failures(expected, anchor.EXPECTED_CANONICAL_POLICY_SHA256, anchor.EXPECTED_TEST_VECTOR_SHA256)
    rows.append({"case": "control_valid", "passed": not control_failures, "failures": control_failures})
    for name, mutate, expected_check in cases:
        candidate = copy.deepcopy(expected)
        mutate(candidate)
        failures = anchor.policy_failures(candidate, anchor.canonical_sha256(candidate), anchor.EXPECTED_TEST_VECTOR_SHA256)
        checks = {str(item.get("check")) for item in failures}
        rows.append({"case": name, "passed": expected_check in checks, "expected_check": expected_check, "observed_checks": sorted(checks)})
    vector_failures = anchor.policy_failures(expected, anchor.EXPECTED_CANONICAL_POLICY_SHA256, "0" * 64)
    vector_checks = {str(item.get("check")) for item in vector_failures}
    rows.append({"case": "test_vector_drift", "passed": "test_vector_sha256_exact" in vector_checks, "expected_check": "test_vector_sha256_exact", "observed_checks": sorted(vector_checks)})

    failed_rows = sum(1 for row in rows if not row.get("passed"))
    report = {
        "schema_version": 1,
        "mode": "claim_readiness_policy_anchor_regression",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "local_only": True,
        "success": failed_rows == 0,
        "case_count": len(rows),
        "passed_case_count": len(rows) - failed_rows,
        "failed_rows": failed_rows,
        "isolated_in_memory": True,
        "real_inputs_mutated": False,
        "cases": rows,
        "regression_script_path": str(Path(__file__).resolve()),
        "regression_script_sha256": anchor.sha256(Path(__file__).resolve()),
        "anchor_validator_path": str(Path(anchor.__file__).resolve()),
        "anchor_validator_sha256": anchor.sha256(Path(anchor.__file__).resolve()),
        "output_path": str(output_path),
        "lock_path": str(lock_path),
        "lock_acquired": True,
        "atomic_commit": True,
        "safe_for_model_claim": False,
        "release_ready": False,
        "policy": "In-memory drift regression only; canonical policy files remain unchanged.",
    }
    try:
        anchor.write_json_atomic(output_path, report, fail_before_replace=args.fail_before_replace)
    except Exception as exc:
        lock_handle.close()
        print(json.dumps({"success": False, "error": f"claim_policy_anchor_regression_commit_failed:{type(exc).__name__}:{exc}"}, ensure_ascii=False, sort_keys=True))
        return 1
    lock_handle.close()
    print(json.dumps({"success": report["success"], "case_count": report["case_count"], "passed_case_count": report["passed_case_count"], "failed_rows": report["failed_rows"], "output": str(output_path)}, ensure_ascii=False, sort_keys=True))
    return 0 if report["success"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
