#!/usr/bin/env python3
"""Regression for controlled execution-wave receipt/report pair atomicity."""

from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from run_enzyme_agent_controlled_execution_wave import acquire_lock, commit_receipt_pair, receipt_bytes, write_json_atomic


AI_ROOT = Path(__file__).resolve().parents[1]
WAVE_SCRIPT = AI_ROOT / "scripts" / "run_enzyme_agent_controlled_execution_wave.py"
OUTPUT = AI_ROOT / "reports" / "enzyme_agent_controlled_execution_wave_pair_atomicity_regression_report.json"
LOCK_PATH = AI_ROOT / "reports" / ".enzyme_agent_controlled_execution_wave.lock"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build_pair(receipts_path: Path, report_path: Path, lock_path: Path, generation: str) -> tuple[bytes, dict[str, Any]]:
    rows = [{"action_id": "fixture_action", "return_status": "executed_passed", "generation": generation}]
    payload = receipt_bytes(rows)
    report = {
        "schema_version": 2,
        "mode": "enzyme-agent-controlled-execution-wave-v2",
        "success": True,
        "wave_script_path": str(WAVE_SCRIPT.resolve()),
        "wave_script_sha256": sha256(WAVE_SCRIPT),
        "receipts_path": str(receipts_path.resolve()),
        "receipts_sha256": hashlib.sha256(payload).hexdigest(),
        "output_path": str(report_path.resolve()),
        "lock_path": str(lock_path.resolve()),
        "lock_acquired": True,
        "receipts_atomic_commit": True,
        "report_atomic_commit": True,
        "generation": generation,
    }
    return payload, report


def pair_matches(receipts_path: Path, report_path: Path) -> bool:
    if not receipts_path.is_file() or not report_path.is_file():
        return False
    report = json.loads(report_path.read_text(encoding="utf-8"))
    return report.get("receipts_sha256") == hashlib.sha256(receipts_path.read_bytes()).hexdigest()


def commit_under_lock(receipts_path: Path, report_path: Path, lock_path: Path, payload: bytes, report: dict[str, Any], timeout: float) -> tuple[bool, str]:
    handle = acquire_lock(lock_path, timeout)
    if handle is None:
        return False, "lock_timeout"
    try:
        commit_receipt_pair(receipts_path, payload, report_path, report)
        return True, "committed"
    except Exception as exc:
        return False, f"{type(exc).__name__}:{exc}"
    finally:
        handle.close()


def main() -> int:
    parser = argparse.ArgumentParser(description="Run wave receipt/report pair atomicity regression")
    parser.add_argument("--output", type=Path, default=OUTPUT)
    parser.add_argument("--lock-path", type=Path, default=LOCK_PATH)
    parser.add_argument("--lock-timeout-seconds", type=float, default=30.0)
    args = parser.parse_args()
    protected = [WAVE_SCRIPT]
    before = {str(path): sha256(path) for path in protected}
    results: list[dict[str, Any]] = []

    with tempfile.TemporaryDirectory(prefix="execution-wave-pair-atomicity-") as temp_name:
        root = Path(temp_name)
        receipts = root / "receipts.jsonl"
        report = root / "wave.json"
        lock = root / "wave.lock"
        payload_a, report_a = build_pair(receipts, report, lock, "generation-a")
        committed, status = commit_under_lock(receipts, report, lock, payload_a, report_a, 2.0)
        results.append({"case": "complete_pair_atomic_commit", "passed": committed and pair_matches(receipts, report) and json.loads(report.read_text(encoding="utf-8")).get("generation") == "generation-a", "status": status})

        prior_receipts = receipts.read_bytes()
        prior_report = report.read_bytes()
        payload_b, report_b = build_pair(receipts, report, lock, "generation-b")
        handle = acquire_lock(lock, 2.0)
        assert handle is not None
        try:
            try:
                commit_receipt_pair(receipts, payload_b, report, report_b, fail_before_receipts_replace=True)
            except RuntimeError:
                pass
        finally:
            handle.close()
        results.append({"case": "before_receipts_replace_preserves_prior_pair", "passed": receipts.read_bytes() == prior_receipts and report.read_bytes() == prior_report and pair_matches(receipts, report)})

        try:
            commit_receipt_pair(receipts, payload_b, report, report_b, fail_after_receipts_replace=True)
        except RuntimeError:
            pass
        results.append({"case": "after_receipts_replace_pair_mismatch_rejected", "passed": receipts.read_bytes() != prior_receipts and report.read_bytes() == prior_report and not pair_matches(receipts, report)})

        commit_under_lock(receipts, report, lock, payload_a, report_a, 2.0)
        valid_receipts = receipts.read_bytes()
        valid_report = report.read_bytes()
        try:
            commit_receipt_pair(receipts, payload_b, report, report_b, fail_before_report_replace=True)
        except RuntimeError:
            pass
        results.append({"case": "before_report_replace_pair_mismatch_rejected", "passed": receipts.read_bytes() != valid_receipts and report.read_bytes() == valid_report and not pair_matches(receipts, report)})

        # Restore a valid pair and prove a held lock fails closed, then recovers.
        commit_under_lock(receipts, report, lock, payload_a, report_a, 2.0)
        prior_pair = (receipts.read_bytes(), report.read_bytes())
        handle = lock.open("a+")
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        blocked, blocked_status = commit_under_lock(receipts, report, lock, payload_b, report_b, 0.0)
        preserved = (receipts.read_bytes(), report.read_bytes()) == prior_pair
        fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        handle.close()
        recovered, recovered_status = commit_under_lock(receipts, report, lock, payload_b, report_b, 2.0)
        results.append({"case": "lock_timeout_preserves_and_recovery_commits", "passed": blocked is False and preserved and recovered and pair_matches(receipts, report), "blocked_status": blocked_status, "recovered_status": recovered_status})

    after = {str(path): sha256(path) for path in protected}
    failed_case_count = sum(1 for row in results if not row.get("passed"))
    failures = []
    if failed_case_count:
        failures.append({"check": "all_cases_pass", "observed": failed_case_count, "expected": 0})
    if before != after:
        failures.append({"check": "real_inputs_unchanged", "observed": {"before": before, "after": after}, "expected": True})
    script = Path(__file__).resolve()
    output_path = args.output.resolve()
    lock_path = args.lock_path.resolve()
    final_report = {
        "schema_version": 1,
        "mode": "enzyme-agent-controlled-execution-wave-pair-atomicity-regression-v1",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "success": not failures,
        "isolated_fixture": True,
        "regression_script_path": str(script),
        "regression_script_sha256": sha256(script),
        "wave_script_path": str(WAVE_SCRIPT.resolve()),
        "wave_script_sha256": sha256(WAVE_SCRIPT),
        "output_path": str(output_path),
        "lock_path": str(lock_path),
        "lock_acquired": True,
        "atomic_commit": True,
        "case_count": len(results),
        "passed_case_count": sum(1 for row in results if row.get("passed")),
        "failed_case_count": failed_case_count,
        "real_inputs_mutated": before != after,
        "failure_count": len(failures),
        "failures": failures,
        "cases": results,
        "safe_for_model_claim": False,
        "release_ready": False,
    }
    handle = acquire_lock(lock_path, args.lock_timeout_seconds)
    if handle is None:
        print(json.dumps({"success": False, "error": "wave_pair_atomicity_regression_lock_timeout", "output_preserved": output_path.exists()}, ensure_ascii=False, sort_keys=True))
        return 1
    try:
        write_json_atomic(output_path, final_report, prefix="wave-pair-regression")
    finally:
        handle.close()
    print(json.dumps({"success": final_report["success"], "case_count": final_report["case_count"], "passed_case_count": final_report["passed_case_count"], "failure_count": final_report["failure_count"], "real_inputs_mutated": final_report["real_inputs_mutated"], "output": str(output_path)}, ensure_ascii=False, sort_keys=True))
    return 0 if final_report["success"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
