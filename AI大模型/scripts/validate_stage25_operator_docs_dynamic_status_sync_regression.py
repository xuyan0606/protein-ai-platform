#!/usr/bin/env python3
"""Prove marker-bound Stage 25 documentation synchronization fails closed."""

from __future__ import annotations

import argparse
import json
import fcntl
import os
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

from stage25_operator_docs_sync_regression_proof_io import acquire_lock, sha256, write_json_atomic
from sync_stage25_operator_docs_dynamic_status import INPUT_PATHS, expected_lines


AI_ROOT = Path(__file__).resolve().parents[1]
PLATFORM_ROOT = AI_ROOT.parent
SYNC = AI_ROOT / "scripts" / "sync_stage25_operator_docs_dynamic_status.py"
NEXT_OPERATOR = AI_ROOT / "reports" / "next_operator_packet_20260806.md"
DAILY_REPORT = PLATFORM_ROOT / "docs" / "manuals" / "2026-08-06-daily-report.md"
OUTPUT = AI_ROOT / "reports" / "stage25_operator_docs_dynamic_status_sync_regression_report.json"
LOCK = AI_ROOT / "reports" / ".stage25_operator_docs_sync_regression_proof.lock"
PROOF_IO = AI_ROOT / "scripts" / "stage25_operator_docs_sync_regression_proof_io.py"
MARKERS = (
    "<!-- stage25-sync:latest-release -->",
    "<!-- stage25-sync:core-counts -->",
    "<!-- stage25-sync:data-lake -->",
    "<!-- stage25-sync:human-backlog -->",
    "<!-- stage25-sync:post-source -->",
)


def run_sync(
    next_path: Path,
    daily_path: Path,
    report_path: Path,
    check: bool,
    fail_after: int = 0,
    mutate_after_plan: str = "",
    lock_path: Path | None = None,
    lock_timeout_seconds: float = 1.0,
    receipt_fail_stage: str = "",
    receipt_delay_seconds: float = 0.0,
) -> tuple[subprocess.CompletedProcess[str], dict]:
    effective_lock_path = lock_path or report_path.with_suffix(".lock")
    command = [
        sys.executable,
        str(SYNC),
        "--next-operator", str(next_path),
        "--daily-report", str(daily_path),
        "--output", str(report_path),
        "--lock-path", str(effective_lock_path),
        "--lock-timeout-seconds", str(lock_timeout_seconds),
    ]
    if check:
        command.append("--check")
    environment = os.environ.copy()
    if fail_after:
        environment["STAGE25_DOC_SYNC_TEST_FAIL_AFTER"] = str(fail_after)
    if mutate_after_plan:
        environment["STAGE25_DOC_SYNC_TEST_MUTATE_AFTER_PLAN"] = mutate_after_plan
    if receipt_fail_stage:
        environment["STAGE25_DOC_SYNC_TEST_RECEIPT_FAIL_STAGE"] = receipt_fail_stage
    if receipt_delay_seconds:
        environment["STAGE25_DOC_SYNC_TEST_RECEIPT_DELAY_SECONDS"] = str(receipt_delay_seconds)
    process = subprocess.run(command, cwd=AI_ROOT, text=True, capture_output=True, timeout=300, env=environment)
    report = json.loads(report_path.read_text(encoding="utf-8")) if report_path.exists() else {}
    return process, report


def stale_first_slot(text: str) -> str:
    lines = text.splitlines()
    index = lines.index(MARKERS[0]) + 1
    lines[index] = lines[index] + " stale"
    return "\n".join(lines) + "\n"


def normalize_targets(text: str) -> list[str]:
    lines = text.splitlines()
    for marker in MARKERS:
        index = lines.index(marker) + 1
        lines[index] = "<SYNC_TARGET>"
    return lines


def backlog_value_rejected(temp_root: Path, case_id: str, value: object) -> bool:
    canonical_path = INPUT_PATHS["human_backlog"]
    payload = json.loads(canonical_path.read_text(encoding="utf-8"))
    payload["open_items"] = value
    fixture_path = temp_root / f"{case_id}-human-backlog.json"
    fixture_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    INPUT_PATHS["human_backlog"] = fixture_path
    try:
        _lines, failures = expected_lines()
    finally:
        INPUT_PATHS["human_backlog"] = canonical_path
    return "human_backlog_rows_valid" in [str(row.get("check") or "") for row in failures]


def main() -> int:
    parser = argparse.ArgumentParser(description="Run operator-doc marker and transaction regression")
    parser.add_argument("--output", type=Path, default=OUTPUT)
    parser.add_argument("--lock-path", type=Path, default=LOCK)
    parser.add_argument("--lock-timeout-seconds", type=float, default=30.0)
    parser.add_argument("--fail-before-replace", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()
    output_path = args.output.resolve()
    lock_path = args.lock_path.resolve()
    lock_handle = acquire_lock(lock_path, args.lock_timeout_seconds)
    if lock_handle is None:
        print(json.dumps({"success": False, "error": "operator_docs_sync_regression_lock_timeout", "output_preserved": output_path.exists()}, ensure_ascii=False))
        return 1

    script_path = Path(__file__).resolve()
    next_source = NEXT_OPERATOR.read_text(encoding="utf-8")
    daily_source = DAILY_REPORT.read_text(encoding="utf-8")
    results: list[dict[str, object]] = []

    with tempfile.TemporaryDirectory(prefix="stage25-doc-sync-") as temp_dir:
        temp_root = Path(temp_dir)

        def paths(case_id: str) -> tuple[Path, Path, Path]:
            return (
                temp_root / f"{case_id}-next.md",
                temp_root / f"{case_id}-daily.md",
                temp_root / f"{case_id}-report.json",
            )

        for case_id, value in (
            ("backlog-open-items-string", "11"),
            ("backlog-open-items-boolean", True),
            ("backlog-open-items-negative", -1),
        ):
            rejected = backlog_value_rejected(temp_root, case_id, value)
            results.append({"case_id": f"{case_id}_rejected", "tamper_rejected": rejected, "expected_check": "human_backlog_rows_valid", "expected_check_observed": rejected})

        next_path, daily_path, report_path = paths("stale-check")
        next_path.write_text(stale_first_slot(next_source), encoding="utf-8")
        daily_path.write_text(daily_source, encoding="utf-8")
        process, report = run_sync(next_path, daily_path, report_path, check=True)
        checks = [str(row.get("check") or "") for row in report.get("failures") or []]
        rejected = process.returncode != 0 and "documents_current" in checks
        results.append({"case_id": "stale_check_rejected", "tamper_rejected": rejected, "expected_check": "documents_current", "expected_check_observed": "documents_current" in checks})

        next_path, daily_path, report_path = paths("missing-marker")
        next_path.write_text(next_source.replace(MARKERS[1] + "\n", "", 1), encoding="utf-8")
        daily_path.write_text(daily_source, encoding="utf-8")
        process, report = run_sync(next_path, daily_path, report_path, check=False)
        checks = [str(row.get("check") or "") for row in report.get("failures") or []]
        rejected = process.returncode != 0 and "marker_exactly_once" in checks
        results.append({"case_id": "missing_marker_rejected", "tamper_rejected": rejected, "expected_check": "marker_exactly_once", "expected_check_observed": "marker_exactly_once" in checks})

        next_path, daily_path, report_path = paths("duplicate-marker")
        duplicate = MARKERS[2] + "\n- duplicate target\n"
        next_path.write_text(next_source + duplicate, encoding="utf-8")
        daily_path.write_text(daily_source, encoding="utf-8")
        process, report = run_sync(next_path, daily_path, report_path, check=False)
        checks = [str(row.get("check") or "") for row in report.get("failures") or []]
        rejected = process.returncode != 0 and "marker_exactly_once" in checks
        results.append({"case_id": "duplicate_marker_rejected", "tamper_rejected": rejected, "expected_check": "marker_exactly_once", "expected_check_observed": "marker_exactly_once" in checks})

        next_path, daily_path, report_path = paths("cross-document-failure")
        stale_next = stale_first_slot(next_source)
        invalid_daily = daily_source.replace(MARKERS[1] + "\n", "", 1)
        next_path.write_text(stale_next, encoding="utf-8")
        daily_path.write_text(invalid_daily, encoding="utf-8")
        before_next_bytes = next_path.read_bytes()
        before_daily_bytes = daily_path.read_bytes()
        process, report = run_sync(next_path, daily_path, report_path, check=False)
        checks = [str(row.get("check") or "") for row in report.get("failures") or []]
        no_partial_write = (
            process.returncode != 0
            and "marker_exactly_once" in checks
            and next_path.read_bytes() == before_next_bytes
            and daily_path.read_bytes() == before_daily_bytes
            and report.get("transaction_applied") is False
        )
        results.append({"case_id": "cross_document_failure_no_partial_write", "tamper_rejected": no_partial_write, "expected_check": "no_partial_write", "expected_check_observed": no_partial_write})

        next_path, daily_path, report_path = paths("commit-rollback")
        stale_next = stale_first_slot(next_source)
        stale_daily = stale_first_slot(daily_source)
        next_path.write_text(stale_next, encoding="utf-8")
        daily_path.write_text(stale_daily, encoding="utf-8")
        before_next_bytes = next_path.read_bytes()
        before_daily_bytes = daily_path.read_bytes()
        process, report = run_sync(next_path, daily_path, report_path, check=False, fail_after=1)
        checks = [str(row.get("check") or "") for row in report.get("failures") or []]
        rolled_back = (
            process.returncode != 0
            and "document_transaction_commit" in checks
            and report.get("rollback_performed") is True
            and next_path.read_bytes() == before_next_bytes
            and daily_path.read_bytes() == before_daily_bytes
        )
        results.append({"case_id": "commit_failure_rolls_back_all_docs", "tamper_rejected": rolled_back, "expected_check": "document_transaction_commit", "expected_check_observed": "document_transaction_commit" in checks})

        next_path, daily_path, report_path = paths("concurrent-modification")
        stale_next = stale_first_slot(next_source)
        next_path.write_text(stale_next, encoding="utf-8")
        daily_path.write_text(daily_source, encoding="utf-8")
        before_daily_bytes = daily_path.read_bytes()
        process, report = run_sync(next_path, daily_path, report_path, check=False, mutate_after_plan=next_path.name)
        checks = [str(row.get("check") or "") for row in report.get("failures") or []]
        concurrent_edit_preserved = (
            process.returncode != 0
            and "document_changed_after_plan" in checks
            and next_path.read_bytes().endswith(b"external-concurrent-edit\n")
            and daily_path.read_bytes() == before_daily_bytes
            and report.get("transaction_applied") is False
        )
        results.append({"case_id": "concurrent_edit_preserved", "tamper_rejected": concurrent_edit_preserved, "expected_check": "document_changed_after_plan", "expected_check_observed": "document_changed_after_plan" in checks})

        next_path, daily_path, report_path = paths("lock-contention")
        next_path.write_text(next_source, encoding="utf-8")
        daily_path.write_text(daily_source, encoding="utf-8")
        sync_fixture_lock_path = temp_root / "held-sync.lock"
        with sync_fixture_lock_path.open("a+") as lock_handle:
            fcntl.flock(lock_handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            process, report = run_sync(next_path, daily_path, report_path, check=False, lock_path=sync_fixture_lock_path, lock_timeout_seconds=0.05)
            fcntl.flock(lock_handle.fileno(), fcntl.LOCK_UN)
        checks = [str(row.get("check") or "") for row in report.get("failures") or []]
        lock_rejected = process.returncode != 0 and "sync_lock_acquired" in checks and report.get("lock_acquired") is False
        results.append({"case_id": "lock_contention_rejected", "tamper_rejected": lock_rejected, "expected_check": "sync_lock_acquired", "expected_check_observed": "sync_lock_acquired" in checks})

        next_path, daily_path, report_path = paths("receipt-failure")
        stale_next = stale_first_slot(next_source)
        stale_daily = stale_first_slot(daily_source)
        next_path.write_text(stale_next, encoding="utf-8")
        daily_path.write_text(stale_daily, encoding="utf-8")
        before_next_bytes = next_path.read_bytes()
        before_daily_bytes = daily_path.read_bytes()
        prior_receipt = {"sentinel": "prior-complete-receipt"}
        report_path.write_text(json.dumps(prior_receipt) + "\n", encoding="utf-8")
        process, report = run_sync(
            next_path,
            daily_path,
            report_path,
            check=False,
            receipt_fail_stage="before_replace",
        )
        receipt_failure_rolled_back = (
            process.returncode != 0
            and report == prior_receipt
            and next_path.read_bytes() == before_next_bytes
            and daily_path.read_bytes() == before_daily_bytes
        )
        results.append({"case_id": "receipt_failure_preserves_prior_state", "tamper_rejected": receipt_failure_rolled_back, "expected_check": "atomic_receipt_or_rollback", "expected_check_observed": receipt_failure_rolled_back})

        next_path, daily_path, first_report_path = paths("receipt-lock-first")
        second_report_path = temp_root / "receipt-lock-second-report.json"
        shared_lock_path = temp_root / "receipt-commit-held.lock"
        next_path.write_text(next_source, encoding="utf-8")
        daily_path.write_text(daily_source, encoding="utf-8")
        first_command = [
            sys.executable,
            str(SYNC),
            "--next-operator", str(next_path),
            "--daily-report", str(daily_path),
            "--output", str(first_report_path),
            "--lock-path", str(shared_lock_path),
            "--lock-timeout-seconds", "1",
        ]
        first_environment = os.environ.copy()
        first_environment["STAGE25_DOC_SYNC_TEST_RECEIPT_DELAY_SECONDS"] = "0.3"
        first_process = subprocess.Popen(first_command, cwd=AI_ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=first_environment)
        time.sleep(0.08)
        second_process, second_report = run_sync(
            next_path,
            daily_path,
            second_report_path,
            check=False,
            lock_path=shared_lock_path,
            lock_timeout_seconds=0.05,
        )
        first_returncode = first_process.wait(timeout=300)
        receipt_lock_held = (
            first_returncode == 0
            and second_process.returncode != 0
            and second_report.get("lock_acquired") is False
            and first_report_path.exists()
        )
        results.append({"case_id": "receipt_commit_remains_under_lock", "tamper_rejected": receipt_lock_held, "expected_check": "sync_lock_acquired", "expected_check_observed": receipt_lock_held})

        next_path, daily_path, report_path = paths("apply-repair")
        stale_next = stale_first_slot(next_source)
        stale_daily = stale_first_slot(daily_source)
        next_path.write_text(stale_next, encoding="utf-8")
        daily_path.write_text(stale_daily, encoding="utf-8")
        before_next = normalize_targets(stale_next)
        before_daily = normalize_targets(stale_daily)
        process, report = run_sync(next_path, daily_path, report_path, check=False)
        repaired_only_targets = (
            process.returncode == 0
            and report.get("success") is True
            and report.get("changed_rows") == 2
            and normalize_targets(next_path.read_text(encoding="utf-8")) == before_next
            and normalize_targets(daily_path.read_text(encoding="utf-8")) == before_daily
        )
        results.append({"case_id": "apply_repairs_only_targets", "tamper_rejected": repaired_only_targets, "expected_check": "target_only_repair", "expected_check_observed": repaired_only_targets})

    passed = sum(bool(row["tamper_rejected"]) for row in results)
    report = {
        "schema_version": 2,
        "mode": "stage25-operator-docs-dynamic-status-sync-regression-v2",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "success": passed == len(results),
        "isolated_fixture": True,
        "case_rows": len(results),
        "passed_rows": passed,
        "failed_rows": len(results) - passed,
        "real_inputs_mutated": False,
        "regression_script_path": str(script_path),
        "regression_script_sha256": sha256(script_path),
        "sync_script_path": str(SYNC.resolve()),
        "sync_script_sha256": sha256(SYNC),
        "proof_io_path": str(PROOF_IO.resolve()),
        "proof_io_sha256": sha256(PROOF_IO),
        "output_path": str(output_path),
        "lock_path": str(lock_path),
        "lock_acquired": True,
        "atomic_commit": True,
        "results": results,
        "safe_for_model_claim": False,
        "release_ready": False,
        "policy": "Regression edits temporary Markdown copies only; canonical operator documents remain unchanged.",
    }
    try:
        write_json_atomic(output_path, report, prefix="marker-regression", fail_before_replace=args.fail_before_replace)
    except Exception as exc:
        print(json.dumps({"success": False, "error": f"{type(exc).__name__}:{exc}", "output_preserved": output_path.exists()}, ensure_ascii=False))
        return 1
    finally:
        lock_handle.close()
    print(json.dumps({
        "success": report["success"],
        "case_rows": report["case_rows"],
        "passed_rows": report["passed_rows"],
        "failed_rows": report["failed_rows"],
        "real_inputs_mutated": report["real_inputs_mutated"],
        "output": str(output_path),
    }, ensure_ascii=False))
    return 0 if report["success"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
