#!/usr/bin/env python3
"""Exercise operator-doc sync concurrency and crash recovery in isolation."""

from __future__ import annotations

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


AI_ROOT = Path(__file__).resolve().parents[1]
SYNC = AI_ROOT / "scripts" / "sync_stage25_operator_docs_dynamic_status.py"
NEXT_OPERATOR = AI_ROOT / "reports" / "next_operator_packet_20260806.md"
DAILY_REPORT = AI_ROOT.parent / "docs" / "manuals" / "2026-08-06-daily-report.md"
OUTPUT = AI_ROOT / "reports" / "stage25_operator_docs_sync_terminal_recovery_regression_report.json"
MARKER = "<!-- stage25-sync:latest-release -->"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def stale_first_slot(text: str) -> str:
    lines = text.splitlines()
    index = lines.index(MARKER) + 1
    lines[index] = lines[index] + " stale"
    return "\n".join(lines) + "\n"


def command(next_path: Path, daily_path: Path, report_path: Path, lock_path: Path, timeout: float = 1.0) -> list[str]:
    return [
        sys.executable,
        str(SYNC),
        "--next-operator", str(next_path),
        "--daily-report", str(daily_path),
        "--output", str(report_path),
        "--lock-path", str(lock_path),
        "--lock-timeout-seconds", str(timeout),
    ]


def run_sync(
    next_path: Path,
    daily_path: Path,
    report_path: Path,
    lock_path: Path,
    *,
    timeout: float = 1.0,
    environment_overrides: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    environment = os.environ.copy()
    environment.update(environment_overrides or {})
    return subprocess.run(
        command(next_path, daily_path, report_path, lock_path, timeout),
        cwd=AI_ROOT,
        text=True,
        capture_output=True,
        timeout=300,
        env=environment,
    )


def receipt_matches_documents(report: dict, paths: list[Path]) -> bool:
    hashes = {
        str(Path(str(row.get("path"))).resolve()): row.get("after_sha256")
        for row in report.get("document_hashes") or []
        if row.get("path")
    }
    return all(hashes.get(str(path.resolve())) == sha256(path) for path in paths)


def document_hash_diagnostics(report: dict, paths: list[Path]) -> list[dict[str, str | None]]:
    hashes = {
        str(Path(str(row.get("path"))).resolve()): row.get("after_sha256")
        for row in report.get("document_hashes") or []
        if row.get("path")
    }
    return [
        {
            "path": str(path.resolve()),
            "receipt_sha256": hashes.get(str(path.resolve())),
            "current_sha256": sha256(path),
        }
        for path in paths
    ]


def main() -> int:
    next_source = NEXT_OPERATOR.read_text(encoding="utf-8")
    daily_source = DAILY_REPORT.read_text(encoding="utf-8")
    results: list[dict[str, object]] = []

    with tempfile.TemporaryDirectory(prefix="stage25-doc-sync-terminal-") as temp_dir:
        temp_root = Path(temp_dir)

        next_path = temp_root / "crash-next.md"
        daily_path = temp_root / "crash-daily.md"
        report_path = temp_root / "crash-report.json"
        lock_path = temp_root / "crash.lock"
        next_path.write_text(stale_first_slot(next_source), encoding="utf-8")
        daily_path.write_text(stale_first_slot(daily_source), encoding="utf-8")
        original_next = next_path.read_bytes()
        original_daily = daily_path.read_bytes()
        report_path.write_text('{"sentinel":"prior-receipt"}\n', encoding="utf-8")
        crash = run_sync(
            next_path,
            daily_path,
            report_path,
            lock_path,
            environment_overrides={"STAGE25_DOC_SYNC_TEST_CRASH_AFTER_DOCUMENT_COMMIT": "1"},
        )
        journal_path = report_path.with_name(f".{report_path.name}.transaction.json")
        crash_window_observed = (
            crash.returncode == 91
            and journal_path.is_file()
            and next_path.read_bytes() != original_next
            and daily_path.read_bytes() != original_daily
            and json.loads(report_path.read_text(encoding="utf-8")) == {"sentinel": "prior-receipt"}
        )
        recovery = run_sync(next_path, daily_path, report_path, lock_path)
        recovered_report = json.loads(report_path.read_text(encoding="utf-8")) if report_path.is_file() else {}
        crash_recovered = (
            crash_window_observed
            and recovery.returncode == 0
            and recovered_report.get("success") is True
            and recovered_report.get("recovery_performed") is True
            and recovered_report.get("recovery_mode") == "rolled_back_uncommitted_documents"
            and not journal_path.exists()
            and receipt_matches_documents(recovered_report, [next_path, daily_path])
        )
        results.append({
            "case_id": "hard_crash_recovers_uncommitted_documents",
            "tamper_rejected": crash_recovered,
            "expected_check": "journal_recovery",
            "expected_check_observed": crash_recovered,
            "crash_returncode": crash.returncode,
            "crash_window_observed": crash_window_observed,
            "recovery_returncode": recovery.returncode,
            "recovery_performed": recovered_report.get("recovery_performed"),
            "recovery_mode": recovered_report.get("recovery_mode"),
            "receipt_matches_documents": receipt_matches_documents(recovered_report, [next_path, daily_path]),
            "document_hashes": document_hash_diagnostics(recovered_report, [next_path, daily_path]),
            "journal_remaining": journal_path.exists(),
        })

        next_path = temp_root / "race-next.md"
        daily_path = temp_root / "race-daily.md"
        report_path = temp_root / "race-report.json"
        lock_path = temp_root / "race.lock"
        next_path.write_text(next_source, encoding="utf-8")
        daily_path.write_text(daily_source, encoding="utf-8")
        first_env = os.environ.copy()
        first_env["STAGE25_DOC_SYNC_TEST_RECEIPT_DELAY_SECONDS"] = "0.25"
        first = subprocess.Popen(
            command(next_path, daily_path, report_path, lock_path, 1.0),
            cwd=AI_ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=first_env,
        )
        time.sleep(0.05)
        second = run_sync(next_path, daily_path, report_path, lock_path, timeout=1.0)
        first_returncode = first.wait(timeout=300)
        race_report = json.loads(report_path.read_text(encoding="utf-8")) if report_path.is_file() else {}
        serialized = (
            first_returncode == 0
            and second.returncode == 0
            and race_report.get("success") is True
            and race_report.get("lock_acquired") is True
            and receipt_matches_documents(race_report, [next_path, daily_path])
        )
        results.append({
            "case_id": "double_process_serializes_final_receipt",
            "tamper_rejected": serialized,
            "expected_check": "serialized_receipt",
            "expected_check_observed": serialized,
            "first_returncode": first_returncode,
            "second_returncode": second.returncode,
            "final_success": race_report.get("success"),
            "final_lock_acquired": race_report.get("lock_acquired"),
            "receipt_matches_documents": receipt_matches_documents(race_report, [next_path, daily_path]),
            "document_hashes": document_hash_diagnostics(race_report, [next_path, daily_path]),
        })

        next_path = temp_root / "receipt-fail-next.md"
        daily_path = temp_root / "receipt-fail-daily.md"
        report_path = temp_root / "receipt-fail-report.json"
        lock_path = temp_root / "receipt-fail.lock"
        next_path.write_text(stale_first_slot(next_source), encoding="utf-8")
        daily_path.write_text(stale_first_slot(daily_source), encoding="utf-8")
        before_next = next_path.read_bytes()
        before_daily = daily_path.read_bytes()
        report_path.write_text('{"sentinel":"prior-receipt"}\n', encoding="utf-8")
        receipt_failure = run_sync(
            next_path,
            daily_path,
            report_path,
            lock_path,
            environment_overrides={"STAGE25_DOC_SYNC_TEST_RECEIPT_FAIL_STAGE": "before_replace"},
        )
        receipt_failure_safe = (
            receipt_failure.returncode != 0
            and next_path.read_bytes() == before_next
            and daily_path.read_bytes() == before_daily
            and json.loads(report_path.read_text(encoding="utf-8")) == {"sentinel": "prior-receipt"}
            and not report_path.with_name(f".{report_path.name}.transaction.json").exists()
        )
        results.append({"case_id": "receipt_failure_rolls_back_and_clears_journal", "tamper_rejected": receipt_failure_safe, "expected_check": "receipt_rollback", "expected_check_observed": receipt_failure_safe})

        next_path = temp_root / "partial-next.md"
        daily_path = temp_root / "partial-daily.md"
        report_path = temp_root / "partial-report.json"
        lock_path = temp_root / "partial.lock"
        next_path.write_text(stale_first_slot(next_source), encoding="utf-8")
        daily_path.write_text(stale_first_slot(daily_source), encoding="utf-8")
        before_next = next_path.read_bytes()
        before_daily = daily_path.read_bytes()
        partial = run_sync(
            next_path,
            daily_path,
            report_path,
            lock_path,
            environment_overrides={"STAGE25_DOC_SYNC_TEST_FAIL_AFTER": "1"},
        )
        partial_report = json.loads(report_path.read_text(encoding="utf-8")) if report_path.is_file() else {}
        partial_checks = [str(row.get("check") or "") for row in partial_report.get("failures") or []]
        partial_safe = (
            partial.returncode != 0
            and "document_transaction_commit" in partial_checks
            and next_path.read_bytes() == before_next
            and daily_path.read_bytes() == before_daily
            and not report_path.with_name(f".{report_path.name}.transaction.json").exists()
        )
        results.append({"case_id": "partial_replace_rolls_back_and_clears_journal", "tamper_rejected": partial_safe, "expected_check": "document_transaction_commit", "expected_check_observed": "document_transaction_commit" in partial_checks})

        next_path = temp_root / "timeout-next.md"
        daily_path = temp_root / "timeout-daily.md"
        report_path = temp_root / "timeout-report.json"
        lock_path = temp_root / "timeout.lock"
        next_path.write_text(next_source, encoding="utf-8")
        daily_path.write_text(daily_source, encoding="utf-8")
        before_next = next_path.read_bytes()
        before_daily = daily_path.read_bytes()
        with lock_path.open("a+") as lock_handle:
            fcntl.flock(lock_handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            timeout_process = run_sync(next_path, daily_path, report_path, lock_path, timeout=0.05)
            fcntl.flock(lock_handle.fileno(), fcntl.LOCK_UN)
        timeout_report = json.loads(report_path.read_text(encoding="utf-8")) if report_path.is_file() else {}
        timeout_checks = [str(row.get("check") or "") for row in timeout_report.get("failures") or []]
        timeout_safe = (
            timeout_process.returncode != 0
            and "sync_lock_acquired" in timeout_checks
            and next_path.read_bytes() == before_next
            and daily_path.read_bytes() == before_daily
        )
        results.append({"case_id": "lock_timeout_preserves_documents", "tamper_rejected": timeout_safe, "expected_check": "sync_lock_acquired", "expected_check_observed": "sync_lock_acquired" in timeout_checks})

    passed = sum(bool(row["tamper_rejected"]) for row in results)
    report = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "success": passed == len(results),
        "isolated_fixture": True,
        "case_rows": len(results),
        "passed_rows": passed,
        "failed_rows": len(results) - passed,
        "real_inputs_mutated": False,
        "results": results,
        "safe_for_model_claim": False,
        "release_ready": False,
        "policy": "All crash, race, lock and partial-replace scenarios use temporary documents, receipts, journals and locks.",
    }
    OUTPUT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "success": report["success"],
        "case_rows": report["case_rows"],
        "passed_rows": report["passed_rows"],
        "failed_rows": report["failed_rows"],
        "real_inputs_mutated": report["real_inputs_mutated"],
        "output": str(OUTPUT),
    }, ensure_ascii=False))
    return 0 if report["success"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
