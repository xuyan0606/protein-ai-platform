#!/usr/bin/env python3
"""Exercise marker-regression proof atomicity and lock serialization."""

from __future__ import annotations

import argparse
import fcntl
import json
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from stage25_operator_docs_sync_regression_proof_io import acquire_lock, sha256, write_json_atomic


AI_ROOT = Path(__file__).resolve().parents[1]
WRITER = AI_ROOT / "scripts" / "validate_stage25_operator_docs_dynamic_status_sync_regression.py"
CURRENT = AI_ROOT / "scripts" / "validate_stage25_operator_docs_dynamic_status_sync_regression_current.py"
CURRENT_REGRESSION = AI_ROOT / "scripts" / "validate_stage25_operator_docs_dynamic_status_sync_regression_current_regression.py"
SYNC = AI_ROOT / "scripts" / "sync_stage25_operator_docs_dynamic_status.py"
PROOF_IO = AI_ROOT / "scripts" / "stage25_operator_docs_sync_regression_proof_io.py"
CANONICAL_REPORT = AI_ROOT / "reports" / "stage25_operator_docs_dynamic_status_sync_regression_report.json"
CANONICAL_CURRENT = AI_ROOT / "reports" / "stage25_operator_docs_dynamic_status_sync_regression_current_validation_report.json"
CANONICAL_CURRENT_REGRESSION = AI_ROOT / "reports" / "stage25_operator_docs_dynamic_status_sync_regression_current_regression_report.json"
OUTPUT = AI_ROOT / "reports" / "stage25_operator_docs_dynamic_status_sync_regression_atomicity_regression_report.json"
LOCK = AI_ROOT / "reports" / ".stage25_operator_docs_sync_regression_proof.lock"


def load_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def run(command: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, cwd=AI_ROOT, capture_output=True, text=True, check=False, timeout=300)


def writer_command(output: Path, lock: Path, *, timeout: float = 2.0, fail: bool = False) -> list[str]:
    command = [sys.executable, str(WRITER), "--output", str(output), "--lock-path", str(lock), "--lock-timeout-seconds", str(timeout)]
    if fail:
        command.append("--fail-before-replace")
    return command


def current_command(report: Path, output: Path, lock: Path, *, timeout: float = 2.0, fail: bool = False) -> list[str]:
    command = [sys.executable, str(CURRENT), "--report", str(report), "--output", str(output), "--lock-path", str(lock), "--lock-timeout-seconds", str(timeout)]
    if fail:
        command.append("--fail-before-replace")
    return command


def current_regression_command(output: Path, lock: Path, *, timeout: float = 2.0, fail: bool = False) -> list[str]:
    command = [sys.executable, str(CURRENT_REGRESSION), "--output", str(output), "--lock-path", str(lock), "--lock-timeout-seconds", str(timeout)]
    if fail:
        command.append("--fail-before-replace")
    return command


def coherent(report: dict[str, Any], *, mode: str, output: Path, lock: Path, case_count: int) -> bool:
    return (
        report.get("success") is True
        and report.get("mode") == mode
        and report.get("output_path") == str(output.resolve())
        and report.get("lock_path") == str(lock.resolve())
        and report.get("lock_acquired") is True
        and report.get("atomic_commit") is True
        and report.get("case_count", report.get("case_rows")) == case_count
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Run marker-regression proof atomicity regression")
    parser.add_argument("--output", type=Path, default=OUTPUT)
    parser.add_argument("--lock-path", type=Path, default=LOCK)
    parser.add_argument("--lock-timeout-seconds", type=float, default=30.0)
    args = parser.parse_args()
    output_path = args.output.resolve()
    lock_path = args.lock_path.resolve()
    protected = [WRITER, CURRENT, CURRENT_REGRESSION, SYNC, PROOF_IO, CANONICAL_REPORT, CANONICAL_CURRENT, CANONICAL_CURRENT_REGRESSION]
    before = {str(path): sha256(path) for path in protected if path.is_file()}
    results: list[dict[str, Any]] = []

    with tempfile.TemporaryDirectory(prefix="operator-doc-marker-atomicity-") as name:
        root = Path(name)
        lock = root / "proof.lock"
        marker_report = root / "marker.json"
        current_report = root / "current.json"
        current_regression_report = root / "current-regression.json"

        complete = run(writer_command(marker_report, lock))
        complete_report = load_json(marker_report)
        results.append({"case_id": "writer_atomic_commit_complete_json", "passed": complete.returncode == 0 and coherent(complete_report, mode="stage25-operator-docs-dynamic-status-sync-regression-v2", output=marker_report, lock=lock, case_count=13)})

        prior = b'{"sentinel":"prior-marker"}\n'
        marker_report.write_bytes(prior)
        interrupted = run(writer_command(marker_report, lock, fail=True))
        residual = sorted(path.name for path in root.glob(f".{marker_report.name}.marker-regression-*"))
        results.append({"case_id": "writer_replace_interruption_preserves_prior", "passed": interrupted.returncode != 0 and marker_report.read_bytes() == prior and not residual})

        marker_report.write_bytes(prior)
        holder = lock.open("a+")
        fcntl.flock(holder.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        blocked = run(writer_command(marker_report, lock, timeout=0.0))
        blocked_preserved = marker_report.read_bytes() == prior
        fcntl.flock(holder.fileno(), fcntl.LOCK_UN)
        holder.close()
        recovered = run(writer_command(marker_report, lock))
        recovered_report = load_json(marker_report)
        results.append({"case_id": "writer_lock_timeout_and_recovery", "passed": blocked.returncode != 0 and blocked_preserved and recovered.returncode == 0 and coherent(recovered_report, mode="stage25-operator-docs-dynamic-status-sync-regression-v2", output=marker_report, lock=lock, case_count=13)})

        first = subprocess.Popen(writer_command(marker_report, lock, timeout=5.0), cwd=AI_ROOT, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        second = subprocess.Popen(writer_command(marker_report, lock, timeout=5.0), cwd=AI_ROOT, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        first.communicate(timeout=300)
        second.communicate(timeout=300)
        double_report = load_json(marker_report)
        results.append({"case_id": "double_writer_serializes", "passed": first.returncode == 0 and second.returncode == 0 and coherent(double_report, mode="stage25-operator-docs-dynamic-status-sync-regression-v2", output=marker_report, lock=lock, case_count=13)})

        run(writer_command(marker_report, lock))
        current_report.write_bytes(b'{"sentinel":"prior-current"}\n')
        current_interrupted = run(current_command(marker_report, current_report, lock, fail=True))
        current_residual = sorted(path.name for path in root.glob(f".{current_report.name}.marker-regression-current-*"))
        results.append({"case_id": "current_replace_interruption_preserves_prior", "passed": current_interrupted.returncode != 0 and current_report.read_bytes() == b'{"sentinel":"prior-current"}\n' and not current_residual})

        current_regression_report.write_bytes(b'{"sentinel":"prior-current-regression"}\n')
        regression_interrupted = run(current_regression_command(current_regression_report, lock, fail=True))
        regression_residual = sorted(path.name for path in root.glob(f".{current_regression_report.name}.marker-current-regression-*"))
        results.append({"case_id": "current_regression_replace_interruption_preserves_prior", "passed": regression_interrupted.returncode != 0 and current_regression_report.read_bytes() == b'{"sentinel":"prior-current-regression"}\n' and not regression_residual})

        run(writer_command(marker_report, lock))
        writer_process = subprocess.Popen(writer_command(marker_report, lock, timeout=5.0), cwd=AI_ROOT, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        current_process = subprocess.Popen(current_command(marker_report, current_report, lock, timeout=5.0), cwd=AI_ROOT, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        regression_process = subprocess.Popen(current_regression_command(current_regression_report, lock, timeout=5.0), cwd=AI_ROOT, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        writer_process.communicate(timeout=300)
        current_process.communicate(timeout=300)
        regression_process.communicate(timeout=300)
        final_current = run(current_command(marker_report, current_report, lock, timeout=5.0))
        mixed_marker = load_json(marker_report)
        mixed_current = load_json(current_report)
        mixed_regression = load_json(current_regression_report)
        results.append({
            "case_id": "mixed_writers_serialize_and_recover_current_pair",
            "passed": writer_process.returncode == 0
            and regression_process.returncode == 0
            and final_current.returncode == 0
            and coherent(mixed_marker, mode="stage25-operator-docs-dynamic-status-sync-regression-v2", output=marker_report, lock=lock, case_count=13)
            and coherent(mixed_current, mode="stage25-operator-docs-dynamic-status-sync-regression-current-v1", output=current_report, lock=lock, case_count=13)
            and coherent(mixed_regression, mode="stage25-operator-docs-dynamic-status-sync-regression-current-regression-v1", output=current_regression_report, lock=lock, case_count=14)
            and mixed_current.get("regression_report_sha256") == sha256(marker_report),
            "writer_returncode": writer_process.returncode,
            "current_returncode": current_process.returncode,
            "current_regression_returncode": regression_process.returncode,
            "recovery_current_returncode": final_current.returncode,
        })

    after = {str(path): sha256(path) for path in protected if path.is_file()}
    real_inputs_mutated = before != after
    failed = sum(1 for row in results if not row.get("passed"))
    failures: list[dict[str, Any]] = []
    if failed:
        failures.append({"check": "all_cases_pass", "observed": failed, "expected": 0})
    if real_inputs_mutated:
        failures.append({"check": "real_inputs_unchanged", "observed": {"before": before, "after": after}, "expected": True})

    script_path = Path(__file__).resolve()
    report = {
        "schema_version": 1,
        "mode": "stage25-operator-docs-dynamic-status-sync-regression-atomicity-v1",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "success": not failures,
        "isolated_fixture": True,
        "atomicity_script_path": str(script_path),
        "atomicity_script_sha256": sha256(script_path),
        "writer_script_path": str(WRITER.resolve()),
        "writer_script_sha256": sha256(WRITER),
        "current_validator_script_path": str(CURRENT.resolve()),
        "current_validator_script_sha256": sha256(CURRENT),
        "current_regression_script_path": str(CURRENT_REGRESSION.resolve()),
        "current_regression_script_sha256": sha256(CURRENT_REGRESSION),
        "proof_io_path": str(PROOF_IO.resolve()),
        "proof_io_sha256": sha256(PROOF_IO),
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
    handle = acquire_lock(lock_path, args.lock_timeout_seconds)
    if handle is None:
        print(json.dumps({"success": False, "error": "operator_docs_sync_regression_atomicity_lock_timeout", "output_preserved": output_path.exists()}, ensure_ascii=False))
        return 1
    try:
        write_json_atomic(output_path, report, prefix="marker-atomicity")
    finally:
        handle.close()
    print(json.dumps({"success": report["success"], "case_count": report["case_count"], "passed_case_count": report["passed_case_count"], "failure_count": report["failure_count"], "real_inputs_mutated": report["real_inputs_mutated"], "output": str(output_path)}, ensure_ascii=False))
    return 0 if report["success"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
