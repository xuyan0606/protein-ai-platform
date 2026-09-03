#!/usr/bin/env python3
"""Isolated tamper and recovery regression for marker-regression current proof."""

from __future__ import annotations

import argparse
import fcntl
import json
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from stage25_operator_docs_sync_regression_proof_io import acquire_lock, sha256, write_json_atomic


AI_ROOT = Path(__file__).resolve().parents[1]
VALIDATOR = AI_ROOT / "scripts" / "validate_stage25_operator_docs_dynamic_status_sync_regression_current.py"
REGRESSION = AI_ROOT / "scripts" / "validate_stage25_operator_docs_dynamic_status_sync_regression.py"
SYNC = AI_ROOT / "scripts" / "sync_stage25_operator_docs_dynamic_status.py"
PROOF_IO = AI_ROOT / "scripts" / "stage25_operator_docs_sync_regression_proof_io.py"
REPORT = AI_ROOT / "reports" / "stage25_operator_docs_dynamic_status_sync_regression_report.json"
CURRENT_REPORT = AI_ROOT / "reports" / "stage25_operator_docs_dynamic_status_sync_regression_current_validation_report.json"
OUTPUT = AI_ROOT / "reports" / "stage25_operator_docs_dynamic_status_sync_regression_current_regression_report.json"
LOCK = AI_ROOT / "reports" / ".stage25_operator_docs_sync_regression_proof.lock"


def load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return payload


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def prepare_fixture(root: Path) -> dict[str, Path]:
    root.mkdir(parents=True, exist_ok=True)
    paths = {
        "report": root / "marker-regression.json",
        "regression": root / "marker-regression.py",
        "sync": root / "sync.py",
        "io": root / "proof-io.py",
        "current": root / "current.json",
        "lock": root / "proof.lock",
    }
    shutil.copy2(REGRESSION, paths["regression"])
    shutil.copy2(SYNC, paths["sync"])
    shutil.copy2(PROOF_IO, paths["io"])
    payload = load_json(REPORT)
    payload.update({
        "regression_script_path": str(paths["regression"].resolve()),
        "regression_script_sha256": sha256(paths["regression"]),
        "sync_script_path": str(paths["sync"].resolve()),
        "sync_script_sha256": sha256(paths["sync"]),
        "proof_io_path": str(paths["io"].resolve()),
        "proof_io_sha256": sha256(paths["io"]),
        "output_path": str(paths["report"].resolve()),
        "lock_path": str(paths["lock"].resolve()),
    })
    write_json(paths["report"], payload)
    return paths


def run_current(paths: dict[str, Path], *, timeout: float = 2.0, fail: bool = False) -> tuple[subprocess.CompletedProcess[str], dict[str, Any]]:
    command = [
        sys.executable,
        str(VALIDATOR),
        "--report", str(paths["report"]),
        "--regression-script", str(paths["regression"]),
        "--sync-script", str(paths["sync"]),
        "--proof-io", str(paths["io"]),
        "--output", str(paths["current"]),
        "--lock-path", str(paths["lock"]),
        "--lock-timeout-seconds", str(timeout),
    ]
    if fail:
        command.append("--fail-before-replace")
    process = subprocess.run(command, cwd=AI_ROOT, capture_output=True, text=True, check=False, timeout=300)
    report = load_json(paths["current"]) if paths["current"].is_file() else {}
    return process, report


def mutate_report(path: Path, mutation: Callable[[dict[str, Any]], None]) -> None:
    payload = load_json(path)
    mutation(payload)
    write_json(path, payload)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run marker-regression current tamper regression")
    parser.add_argument("--output", type=Path, default=OUTPUT)
    parser.add_argument("--lock-path", type=Path, default=LOCK)
    parser.add_argument("--lock-timeout-seconds", type=float, default=30.0)
    parser.add_argument("--fail-before-replace", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()
    output_path = args.output.resolve()
    lock_path = args.lock_path.resolve()
    protected = [VALIDATOR, REGRESSION, SYNC, PROOF_IO, REPORT, CURRENT_REPORT]
    before = {str(path): sha256(path) for path in protected if path.is_file()}
    results: list[dict[str, Any]] = []

    with tempfile.TemporaryDirectory(prefix="operator-doc-marker-current-regression-") as name:
        temp_root = Path(name)

        control_paths = prepare_fixture(temp_root / "control")
        control_process, control_report = run_current(control_paths)
        control_valid = control_process.returncode == 0 and control_report.get("success") is True and control_report.get("failure_count") == 0
        results.append({"case_id": "control_current_valid", "passed": control_valid, "expected_check": "control_success"})

        tamper_cases: list[tuple[str, Callable[[dict[str, Path]], None], str]] = [
            ("recorded_regression_script_sha_drift", lambda p: mutate_report(p["report"], lambda data: data.__setitem__("regression_script_sha256", "0" * 64)), "report_regression_script_sha_current"),
            ("live_regression_script_sha_drift", lambda p: p["regression"].write_bytes(p["regression"].read_bytes() + b"\n"), "report_regression_script_sha_current"),
            ("recorded_sync_script_sha_drift", lambda p: mutate_report(p["report"], lambda data: data.__setitem__("sync_script_sha256", "1" * 64)), "report_sync_script_sha_current"),
            ("live_sync_script_sha_drift", lambda p: p["sync"].write_bytes(p["sync"].read_bytes() + b"\n"), "report_sync_script_sha_current"),
            ("recorded_proof_io_sha_drift", lambda p: mutate_report(p["report"], lambda data: data.__setitem__("proof_io_sha256", "2" * 64)), "report_proof_io_sha_current"),
            ("live_proof_io_sha_drift", lambda p: p["io"].write_bytes(p["io"].read_bytes() + b"\n"), "report_proof_io_sha_current"),
            ("output_path_drift", lambda p: mutate_report(p["report"], lambda data: data.__setitem__("output_path", str((p["report"].parent / "forged.json").resolve()))), "report_output_path"),
            ("lock_path_drift", lambda p: mutate_report(p["report"], lambda data: data.__setitem__("lock_path", str((p["lock"].parent / "forged.lock").resolve()))), "report_lock_path"),
            ("atomic_commit_false", lambda p: mutate_report(p["report"], lambda data: data.__setitem__("atomic_commit", False)), "report_atomic_commit"),
            ("case_set_drift", lambda p: mutate_report(p["report"], lambda data: data["results"].pop()), "report_case_ids_exact"),
            ("release_gate_reopened", lambda p: mutate_report(p["report"], lambda data: data.__setitem__("release_ready", True)), "report_release_ready_closed"),
        ]
        for index, (case_id, mutation, expected_check) in enumerate(tamper_cases):
            paths = prepare_fixture(temp_root / f"tamper-{index}")
            mutation(paths)
            process, current = run_current(paths)
            checks = [str(row.get("check") or "") for row in current.get("failures") or []]
            passed = process.returncode != 0 and expected_check in checks
            results.append({"case_id": case_id, "passed": passed, "expected_check": expected_check, "observed_checks": checks})

        interrupted_paths = prepare_fixture(temp_root / "replace-interruption")
        prior = b'{"sentinel":"prior-current"}\n'
        interrupted_paths["current"].write_bytes(prior)
        interrupted, _report = run_current(interrupted_paths, fail=True)
        residual = sorted(path.name for path in interrupted_paths["current"].parent.glob(f".{interrupted_paths['current'].name}.marker-regression-current-*"))
        results.append({"case_id": "replace_interruption_preserves_prior", "passed": interrupted.returncode != 0 and interrupted_paths["current"].read_bytes() == prior and not residual, "expected_check": "atomic_replace_or_prior"})

        lock_paths = prepare_fixture(temp_root / "lock-timeout")
        lock_paths["current"].write_bytes(prior)
        holder = lock_paths["lock"].open("a+")
        fcntl.flock(holder.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        blocked, _blocked_report = run_current(lock_paths, timeout=0.0)
        blocked_preserved = lock_paths["current"].read_bytes() == prior
        fcntl.flock(holder.fileno(), fcntl.LOCK_UN)
        holder.close()
        recovered, recovered_report = run_current(lock_paths)
        results.append({"case_id": "lock_timeout_preserves_and_recovers", "passed": blocked.returncode != 0 and blocked_preserved and recovered.returncode == 0 and recovered_report.get("success") is True, "expected_check": "bounded_lock_recovery"})

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
        "mode": "stage25-operator-docs-dynamic-status-sync-regression-current-regression-v1",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "success": not failures,
        "isolated_fixture": True,
        "regression_script_path": str(script_path),
        "regression_script_sha256": sha256(script_path),
        "current_validator_script_path": str(VALIDATOR.resolve()),
        "current_validator_script_sha256": sha256(VALIDATOR),
        "marker_regression_script_path": str(REGRESSION.resolve()),
        "marker_regression_script_sha256": sha256(REGRESSION),
        "sync_script_path": str(SYNC.resolve()),
        "sync_script_sha256": sha256(SYNC),
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
        print(json.dumps({"success": False, "error": "operator_docs_sync_regression_current_regression_lock_timeout", "output_preserved": output_path.exists()}, ensure_ascii=False))
        return 1
    try:
        write_json_atomic(output_path, report, prefix="marker-current-regression", fail_before_replace=args.fail_before_replace)
    except Exception as exc:
        print(json.dumps({"success": False, "error": f"{type(exc).__name__}:{exc}", "output_preserved": output_path.exists()}, ensure_ascii=False))
        return 1
    finally:
        handle.close()
    print(json.dumps({"success": report["success"], "case_count": report["case_count"], "passed_case_count": report["passed_case_count"], "failure_count": report["failure_count"], "real_inputs_mutated": report["real_inputs_mutated"], "output": str(output_path)}, ensure_ascii=False))
    return 0 if report["success"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
