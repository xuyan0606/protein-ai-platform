#!/usr/bin/env python3
"""Validate the current operator-doc marker regression proof."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from stage25_operator_docs_sync_regression_proof_io import acquire_lock, sha256, write_json_atomic


AI_ROOT = Path(__file__).resolve().parents[1]
REPORT = AI_ROOT / "reports" / "stage25_operator_docs_dynamic_status_sync_regression_report.json"
REGRESSION = AI_ROOT / "scripts" / "validate_stage25_operator_docs_dynamic_status_sync_regression.py"
SYNC = AI_ROOT / "scripts" / "sync_stage25_operator_docs_dynamic_status.py"
PROOF_IO = AI_ROOT / "scripts" / "stage25_operator_docs_sync_regression_proof_io.py"
OUTPUT = AI_ROOT / "reports" / "stage25_operator_docs_dynamic_status_sync_regression_current_validation_report.json"
LOCK = AI_ROOT / "reports" / ".stage25_operator_docs_sync_regression_proof.lock"
EXPECTED_CASE_IDS = (
    "backlog-open-items-string_rejected",
    "backlog-open-items-boolean_rejected",
    "backlog-open-items-negative_rejected",
    "stale_check_rejected",
    "missing_marker_rejected",
    "duplicate_marker_rejected",
    "cross_document_failure_no_partial_write",
    "commit_failure_rolls_back_all_docs",
    "concurrent_edit_preserved",
    "lock_contention_rejected",
    "receipt_failure_preserves_prior_state",
    "receipt_commit_remains_under_lock",
    "apply_repairs_only_targets",
)


def load_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def check(failures: list[dict[str, Any]], name: str, observed: Any, expected: Any) -> None:
    if observed != expected:
        failures.append({"check": name, "observed": observed, "expected": expected})


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate current operator-doc marker regression proof")
    parser.add_argument("--report", type=Path, default=REPORT)
    parser.add_argument("--regression-script", type=Path, default=REGRESSION)
    parser.add_argument("--sync-script", type=Path, default=SYNC)
    parser.add_argument("--proof-io", type=Path, default=PROOF_IO)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    parser.add_argument("--lock-path", type=Path, default=LOCK)
    parser.add_argument("--lock-timeout-seconds", type=float, default=30.0)
    parser.add_argument("--fail-before-replace", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()
    report_path = args.report.resolve()
    output_path = args.output.resolve()
    lock_path = args.lock_path.resolve()
    handle = acquire_lock(lock_path, args.lock_timeout_seconds)
    if handle is None:
        print(json.dumps({"success": False, "error": "operator_docs_sync_regression_current_lock_timeout", "output_preserved": output_path.exists()}, ensure_ascii=False))
        return 1
    try:
        report = load_json(report_path)
        failures: list[dict[str, Any]] = []
        results = report.get("results") if isinstance(report.get("results"), list) else []
        observed_case_ids = tuple(str(row.get("case_id") or "") for row in results if isinstance(row, dict))
        all_cases_passed = all(
            row.get("tamper_rejected") is True and row.get("expected_check_observed") is True
            for row in results
            if isinstance(row, dict)
        ) and len(results) == len(EXPECTED_CASE_IDS)

        check(failures, "report_schema_version", report.get("schema_version"), 2)
        check(failures, "report_mode", report.get("mode"), "stage25-operator-docs-dynamic-status-sync-regression-v2")
        check(failures, "report_success", report.get("success"), True)
        check(failures, "report_isolated_fixture", report.get("isolated_fixture"), True)
        check(failures, "report_case_rows", report.get("case_rows"), len(EXPECTED_CASE_IDS))
        check(failures, "report_passed_rows", report.get("passed_rows"), len(EXPECTED_CASE_IDS))
        check(failures, "report_failed_rows", report.get("failed_rows"), 0)
        check(failures, "report_real_inputs_unchanged", report.get("real_inputs_mutated"), False)
        check(failures, "report_case_ids_exact", observed_case_ids, EXPECTED_CASE_IDS)
        check(failures, "report_all_cases_passed", all_cases_passed, True)
        check(failures, "report_safe_for_model_claim_closed", report.get("safe_for_model_claim"), False)
        check(failures, "report_release_ready_closed", report.get("release_ready"), False)
        check(failures, "report_regression_script_path", report.get("regression_script_path"), str(args.regression_script.resolve()))
        check(failures, "report_regression_script_sha_current", report.get("regression_script_sha256"), sha256(args.regression_script) if args.regression_script.is_file() else None)
        check(failures, "report_sync_script_path", report.get("sync_script_path"), str(args.sync_script.resolve()))
        check(failures, "report_sync_script_sha_current", report.get("sync_script_sha256"), sha256(args.sync_script) if args.sync_script.is_file() else None)
        check(failures, "report_proof_io_path", report.get("proof_io_path"), str(args.proof_io.resolve()))
        check(failures, "report_proof_io_sha_current", report.get("proof_io_sha256"), sha256(args.proof_io) if args.proof_io.is_file() else None)
        check(failures, "report_output_path", report.get("output_path"), str(report_path))
        check(failures, "report_lock_path", report.get("lock_path"), str(lock_path))
        check(failures, "report_lock_acquired", report.get("lock_acquired"), True)
        check(failures, "report_atomic_commit", report.get("atomic_commit"), True)

        script_path = Path(__file__).resolve()
        result = {
            "schema_version": 1,
            "mode": "stage25-operator-docs-dynamic-status-sync-regression-current-v1",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "success": not failures,
            "current_validator_script_path": str(script_path),
            "current_validator_script_sha256": sha256(script_path),
            "regression_report_path": str(report_path),
            "regression_report_sha256": sha256(report_path) if report_path.is_file() else None,
            "regression_script_path": str(args.regression_script.resolve()),
            "regression_script_sha256": sha256(args.regression_script) if args.regression_script.is_file() else None,
            "sync_script_path": str(args.sync_script.resolve()),
            "sync_script_sha256": sha256(args.sync_script) if args.sync_script.is_file() else None,
            "proof_io_path": str(args.proof_io.resolve()),
            "proof_io_sha256": sha256(args.proof_io) if args.proof_io.is_file() else None,
            "output_path": str(output_path),
            "lock_path": str(lock_path),
            "lock_acquired": True,
            "atomic_commit": True,
            "case_count": len(EXPECTED_CASE_IDS),
            "passed_case_count": len(EXPECTED_CASE_IDS) if not failures else 0,
            "failure_count": len(failures),
            "failures": failures,
            "safe_for_model_claim": False,
            "release_ready": False,
        }
        write_json_atomic(output_path, result, prefix="marker-regression-current", fail_before_replace=args.fail_before_replace)
    except Exception as exc:
        print(json.dumps({"success": False, "error": f"{type(exc).__name__}:{exc}", "output_preserved": output_path.exists()}, ensure_ascii=False))
        return 1
    finally:
        handle.close()
    print(json.dumps({"success": result["success"], "case_count": result["case_count"], "failure_count": result["failure_count"], "output": str(output_path)}, ensure_ascii=False))
    return 0 if result["success"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
