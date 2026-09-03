#!/usr/bin/env python3
"""Isolated tamper/recovery regression for safety current validation."""

from __future__ import annotations

import argparse
import copy
import fcntl
import hashlib
import json
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

import validate_local_release_safety_guard_links as target

AI_ROOT = Path(__file__).resolve().parents[1]
CURRENT = AI_ROOT / "scripts" / "validate_local_release_safety_guard_links_current.py"
SIGNER = AI_ROOT / "scripts" / "validate_local_release_safety_guard_links.py"
SAFETY = AI_ROOT / "reports" / "local_release_safety_guard_link_validation_report.json"
RELEASE = AI_ROOT / "reports" / "local_release_manifest.json"
DATA_LAKE = AI_ROOT / "reports" / "data_lake_manifest.json"
CONSISTENCY = AI_ROOT / "reports" / "local_release_manifest_fail_closed_consistency_validation_report.json"
OUTPUT = AI_ROOT / "reports" / "local_release_safety_guard_links_current_regression_report.json"
LOCK = AI_ROOT / "reports" / ".local_release_safety_guard_links.lock"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def run(receipt: Path, output: Path, lock: Path, *extra: str) -> tuple[int, dict[str, Any]]:
    process = subprocess.run([sys.executable, str(CURRENT), "--safety-receipt", str(receipt), "--release", str(RELEASE), "--data-lake", str(DATA_LAKE), "--consistency-receipt", str(CONSISTENCY), "--output", str(output), "--lock-path", str(lock), *extra], cwd=AI_ROOT, capture_output=True, text=True, check=False)
    report = json.loads(output.read_text(encoding="utf-8")) if output.is_file() else {}
    return process.returncode, report


def main() -> int:
    parser = argparse.ArgumentParser(description="Run isolated safety current-validation regression")
    parser.add_argument("--output", type=Path, default=OUTPUT)
    parser.add_argument("--lock-path", type=Path, default=LOCK)
    parser.add_argument("--lock-timeout-seconds", type=float, default=30.0)
    parser.add_argument("--fail-before-replace", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()
    output_path = args.output.resolve()
    lock_path = args.lock_path.resolve()
    protected = [CURRENT, SIGNER, SAFETY, RELEASE, DATA_LAKE, CONSISTENCY]
    before = {str(path): sha256(path) for path in protected}
    results: list[dict[str, Any]] = []
    with tempfile.TemporaryDirectory(prefix="safety-current-regression-") as name:
        root = Path(name)
        receipt = root / "safety.json"
        output = root / "current.json"
        lock = root / "safety.lock"
        baseline = json.loads(SAFETY.read_text(encoding="utf-8"))
        baseline.update({"output_path": str(receipt.resolve()), "lock_path": str(lock.resolve())})

        def restore() -> None:
            write(receipt, copy.deepcopy(baseline))

        restore()
        rc, report = run(receipt, output, lock)
        results.append({"case": "fixture_control", "passed": rc == 0 and report.get("success") is True})
        cases: list[tuple[str, Callable[[dict[str, Any]], None], str]] = [
            ("validator_sha_drift", lambda data: data.__setitem__("validator_script_sha256", "0" * 64), "receipt_validator_sha"),
            ("release_sha_drift", lambda data: data.__setitem__("release_sha256", "1" * 64), "receipt_release_sha"),
            ("consistency_sha_drift", lambda data: data.__setitem__("consistency_receipt_sha256", "2" * 64), "receipt_consistency_sha"),
            ("data_lake_snapshot_malformed", lambda data: data.__setitem__("data_lake_sha256", "bad"), "receipt_data_lake_snapshot_sha_valid"),
            ("output_path_drift", lambda data: data.__setitem__("output_path", "/tmp/forged-safety.json"), "receipt_output_path"),
            ("lock_path_drift", lambda data: data.__setitem__("lock_path", "/tmp/forged-safety.lock"), "receipt_lock_path"),
            ("atomic_flag_false", lambda data: data.__setitem__("atomic_commit", False), "receipt_atomic_commit"),
            ("checked_links_drift", lambda data: data.__setitem__("checked_guard_links", (data.get("checked_guard_links") or [])[:-1]), "checked_guard_links_current"),
        ]
        for case, mutate, expected in cases:
            data = copy.deepcopy(baseline); mutate(data); write(receipt, data)
            rc, report = run(receipt, output, lock)
            checks = [row.get("check") for row in report.get("failures") or []]
            results.append({"case": case, "passed": rc != 0 and expected in checks, "expected_check": expected})
        restore(); run(receipt, output, lock); prior = output.read_bytes()
        holder = lock.open("a+"); fcntl.flock(holder.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        rc, _ = run(receipt, output, lock, "--lock-timeout-seconds", "0")
        fcntl.flock(holder.fileno(), fcntl.LOCK_UN); holder.close()
        results.append({"case": "lock_timeout_preserves_prior", "passed": rc != 0 and output.read_bytes() == prior})
        rc, _ = run(receipt, output, lock, "--fail-before-replace")
        residue = list(root.glob(f".{output.name}.safety-*"))
        results.append({"case": "replace_interrupt_preserves_prior", "passed": rc != 0 and output.read_bytes() == prior and not residue})
        rc, report = run(receipt, output, lock)
        results.append({"case": "recovery_commits_current", "passed": rc == 0 and report.get("success") is True})
    after = {str(path): sha256(path) for path in protected}
    failed = sum(1 for row in results if not row.get("passed"))
    failures = []
    if failed:
        failures.append({"check": "all_cases_pass", "observed": failed, "expected": 0})
    if before != after:
        failures.append({"check": "real_inputs_unchanged", "observed": {"before": before, "after": after}, "expected": True})
    script = Path(__file__).resolve()
    final = {"schema_version": 1, "mode": "local-release-safety-guard-links-current-regression-v1", "created_at": datetime.now(timezone.utc).isoformat(), "success": not failures, "isolated_fixture": True, "regression_script_path": str(script), "regression_script_sha256": sha256(script), "current_validator_script_path": str(CURRENT), "current_validator_script_sha256": sha256(CURRENT), "signer_script_path": str(SIGNER), "signer_script_sha256": sha256(SIGNER), "output_path": str(output_path), "lock_path": str(lock_path), "lock_acquired": True, "atomic_commit": True, "case_count": len(results), "passed_case_count": len(results) - failed, "failed_case_count": failed, "real_inputs_mutated": before != after, "failure_count": len(failures), "failures": failures, "cases": results, "safe_for_model_claim": False, "release_ready": False}
    handle = target.acquire_lock(lock_path, args.lock_timeout_seconds)
    if handle is None:
        print(json.dumps({"success": False, "error": "safety_current_regression_lock_timeout", "output_preserved": output_path.exists()}, ensure_ascii=False))
        return 1
    try:
        target.write_json_atomic(output_path, final, fail_before_replace=args.fail_before_replace)
    except Exception as exc:
        print(json.dumps({"success": False, "error": f"safety_current_regression_commit_failed:{type(exc).__name__}:{exc}", "output": str(output_path)}, ensure_ascii=False))
        return 1
    finally:
        handle.close()
    print(json.dumps({"success": final["success"], "case_count": final["case_count"], "passed_case_count": final["passed_case_count"], "failure_count": final["failure_count"], "real_inputs_mutated": final["real_inputs_mutated"], "output": str(output_path)}, ensure_ascii=False))
    return 0 if final["success"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
