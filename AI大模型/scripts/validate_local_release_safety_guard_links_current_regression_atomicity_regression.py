#!/usr/bin/env python3
"""Exercise safety current-regression atomicity and lock serialization."""

from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

import validate_local_release_safety_guard_links as target


AI_ROOT = Path(__file__).resolve().parents[1]
CURRENT = AI_ROOT / "scripts" / "validate_local_release_safety_guard_links_current.py"
CURRENT_REGRESSION = AI_ROOT / "scripts" / "validate_local_release_safety_guard_links_current_regression.py"
SIGNER = AI_ROOT / "scripts" / "validate_local_release_safety_guard_links.py"
SAFETY = AI_ROOT / "reports" / "local_release_safety_guard_link_validation_report.json"
CURRENT_REPORT = AI_ROOT / "reports" / "local_release_safety_guard_links_current_validation_report.json"
CURRENT_REGRESSION_REPORT = AI_ROOT / "reports" / "local_release_safety_guard_links_current_regression_report.json"
RELEASE = AI_ROOT / "reports" / "local_release_manifest.json"
DATA_LAKE = AI_ROOT / "reports" / "data_lake_manifest.json"
CONSISTENCY = AI_ROOT / "reports" / "local_release_manifest_fail_closed_consistency_validation_report.json"
OUTPUT = AI_ROOT / "reports" / "local_release_safety_guard_links_current_regression_atomicity_regression_report.json"
LOCK = AI_ROOT / "reports" / ".local_release_safety_guard_links.lock"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return data


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def run(command: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, cwd=AI_ROOT, capture_output=True, text=True, check=False, timeout=300)


def commit_coherent(process_returncode: int, report: dict[str, Any], output: Path, lock: Path, *, mode: str, case_count: int | None = None) -> bool:
    expected_returncode = 0 if report.get("success") is True else 1
    coherent = (
        process_returncode == expected_returncode
        and report.get("schema_version") == 1
        and report.get("mode") == mode
        and report.get("output_path", report.get("current_output_path")) == str(output.resolve())
        and report.get("lock_path", report.get("current_lock_path")) == str(lock.resolve())
        and report.get("atomic_commit", report.get("current_atomic_commit")) is True
    )
    if case_count is not None:
        coherent = coherent and report.get("case_count") == case_count and report.get("passed_case_count", 0) + report.get("failed_case_count", 0) == case_count
    return coherent


def regression_command(output: Path, lock: Path, *, timeout: float = 2.0, fail: bool = False) -> list[str]:
    command = [
        sys.executable,
        str(CURRENT_REGRESSION),
        "--output",
        str(output),
        "--lock-path",
        str(lock),
        "--lock-timeout-seconds",
        str(timeout),
    ]
    if fail:
        command.append("--fail-before-replace")
    return command


def current_command(receipt: Path, output: Path, lock: Path, *, timeout: float = 2.0) -> list[str]:
    return [
        sys.executable,
        str(CURRENT),
        "--safety-receipt",
        str(receipt),
        "--release",
        str(RELEASE),
        "--data-lake",
        str(DATA_LAKE),
        "--consistency-receipt",
        str(CONSISTENCY),
        "--output",
        str(output),
        "--lock-path",
        str(lock),
        "--lock-timeout-seconds",
        str(timeout),
    ]


def main() -> int:
    parser = argparse.ArgumentParser(description="Run safety current-regression atomicity regression")
    parser.add_argument("--output", type=Path, default=OUTPUT)
    parser.add_argument("--lock-path", type=Path, default=LOCK)
    parser.add_argument("--lock-timeout-seconds", type=float, default=30.0)
    args = parser.parse_args()
    output_path = args.output.resolve()
    lock_path = args.lock_path.resolve()

    protected = [
        CURRENT,
        CURRENT_REGRESSION,
        SIGNER,
        SAFETY,
        CURRENT_REPORT,
        CURRENT_REGRESSION_REPORT,
        RELEASE,
        DATA_LAKE,
        CONSISTENCY,
    ]
    before = {str(path): sha256(path) for path in protected}
    results: list[dict[str, Any]] = []

    with tempfile.TemporaryDirectory(prefix="safety-current-regression-atomicity-") as name:
        root = Path(name)
        lock = root / "safety.lock"
        regression_output = root / "current-regression.json"

        complete = run(regression_command(regression_output, lock))
        complete_report = load_json(regression_output) if regression_output.is_file() else {}
        results.append({
            "case": "current_regression_atomic_commit_complete_json",
            "passed": commit_coherent(
                complete.returncode,
                complete_report,
                regression_output,
                lock,
                mode="local-release-safety-guard-links-current-regression-v1",
                case_count=12,
            ) and complete_report.get("lock_acquired") is True,
            "returncode": complete.returncode,
        })

        prior = b'{"sentinel":"prior-current-regression"}\n'
        regression_output.write_bytes(prior)
        interrupted = run(regression_command(regression_output, lock, fail=True))
        residual = sorted(path.name for path in root.glob(f".{regression_output.name}.safety-*"))
        results.append({
            "case": "current_regression_interrupted_replace_preserves_prior",
            "passed": interrupted.returncode != 0 and regression_output.read_bytes() == prior and not residual,
            "returncode": interrupted.returncode,
            "prior_preserved": regression_output.read_bytes() == prior,
            "residual_temp_files": residual,
        })

        regression_output.write_bytes(prior)
        holder = lock.open("a+")
        fcntl.flock(holder.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        blocked = run(regression_command(regression_output, lock, timeout=0.0))
        blocked_preserved = regression_output.read_bytes() == prior
        fcntl.flock(holder.fileno(), fcntl.LOCK_UN)
        holder.close()
        recovered = run(regression_command(regression_output, lock))
        recovered_report = load_json(regression_output) if regression_output.is_file() else {}
        results.append({
            "case": "current_regression_lock_timeout_and_recovery",
            "passed": blocked.returncode != 0
            and blocked_preserved
            and commit_coherent(
                recovered.returncode,
                recovered_report,
                regression_output,
                lock,
                mode="local-release-safety-guard-links-current-regression-v1",
                case_count=12,
            ),
            "blocked_returncode": blocked.returncode,
            "blocked_output_preserved": blocked_preserved,
            "recovered_returncode": recovered.returncode,
        })

        first = subprocess.Popen(regression_command(regression_output, lock, timeout=5.0), cwd=AI_ROOT, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        second = subprocess.Popen(regression_command(regression_output, lock, timeout=5.0), cwd=AI_ROOT, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        first.communicate(timeout=300)
        second.communicate(timeout=300)
        double_report = load_json(regression_output) if regression_output.is_file() else {}
        expected_double_returncode = 0 if double_report.get("success") is True else 1
        results.append({
            "case": "double_current_regression_serializes",
            "passed": first.returncode == expected_double_returncode
            and second.returncode == expected_double_returncode
            and commit_coherent(
                expected_double_returncode,
                double_report,
                regression_output,
                lock,
                mode="local-release-safety-guard-links-current-regression-v1",
                case_count=12,
            ),
            "first_returncode": first.returncode,
            "second_returncode": second.returncode,
        })

        receipt = root / "safety-receipt.json"
        current_output = root / "current.json"
        receipt_payload = load_json(SAFETY)
        receipt_payload.update({"output_path": str(receipt.resolve()), "lock_path": str(lock.resolve())})
        write_json(receipt, receipt_payload)
        current_process = subprocess.Popen(current_command(receipt, current_output, lock, timeout=5.0), cwd=AI_ROOT, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        regression_process = subprocess.Popen(regression_command(regression_output, lock, timeout=5.0), cwd=AI_ROOT, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        current_process.communicate(timeout=300)
        regression_process.communicate(timeout=300)
        mixed_current = load_json(current_output) if current_output.is_file() else {}
        mixed_regression = load_json(regression_output) if regression_output.is_file() else {}
        results.append({
            "case": "current_and_current_regression_serialize",
            "passed": commit_coherent(
                current_process.returncode,
                mixed_current,
                current_output,
                lock,
                mode="local-release-safety-guard-links-current-v1",
            ) and commit_coherent(
                regression_process.returncode,
                mixed_regression,
                regression_output,
                lock,
                mode="local-release-safety-guard-links-current-regression-v1",
                case_count=12,
            ),
            "current_returncode": current_process.returncode,
            "regression_returncode": regression_process.returncode,
        })

    after = {str(path): sha256(path) for path in protected}
    real_inputs_mutated = before != after
    failed = sum(1 for row in results if not row.get("passed"))
    failures = []
    if failed:
        failures.append({"check": "all_cases_pass", "observed": failed, "expected": 0})
    if real_inputs_mutated:
        failures.append({"check": "real_inputs_unchanged", "observed": {"before": before, "after": after}, "expected": True})

    script = Path(__file__).resolve()
    report = {
        "schema_version": 1,
        "mode": "local-release-safety-guard-links-current-regression-atomicity-v1",
        "success": not failures,
        "isolated_fixture": True,
        "regression_script_path": str(script),
        "regression_script_sha256": sha256(script),
        "current_validator_script_path": str(CURRENT.resolve()),
        "current_validator_script_sha256": sha256(CURRENT),
        "current_regression_script_path": str(CURRENT_REGRESSION.resolve()),
        "current_regression_script_sha256": sha256(CURRENT_REGRESSION),
        "output_path": str(output_path),
        "lock_path": str(lock_path),
        "lock_acquired": True,
        "atomic_commit": True,
        "case_count": len(results),
        "passed_case_count": len(results) - failed,
        "failed_case_count": failed,
        "real_inputs_mutated": real_inputs_mutated,
        "failure_count": len(failures),
        "failures": failures,
        "cases": results,
        "safe_for_model_claim": False,
        "release_ready": False,
    }
    handle = target.acquire_lock(lock_path, args.lock_timeout_seconds)
    if handle is None:
        print(json.dumps({"success": False, "error": "safety_current_regression_atomicity_lock_timeout", "output_preserved": output_path.exists()}, ensure_ascii=False))
        return 1
    try:
        target.write_json_atomic(output_path, report)
    finally:
        handle.close()
    print(json.dumps({"success": report["success"], "case_count": report["case_count"], "passed_case_count": report["passed_case_count"], "failure_count": report["failure_count"], "real_inputs_mutated": report["real_inputs_mutated"], "output": str(output_path)}, ensure_ascii=False))
    return 0 if report["success"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
