#!/usr/bin/env python3
"""Exercise claim-policy receipt freshness, interruption, and lock handling."""

from __future__ import annotations

import argparse
import copy
import fcntl
import json
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

import validate_claim_readiness_matrix_fail_closed_policy as signer


AI_ROOT = Path(__file__).resolve().parents[1]
SIGNER = Path(signer.__file__).resolve()
CURRENT = AI_ROOT / "scripts" / "validate_claim_readiness_matrix_fail_closed_policy_current.py"
OUTPUT = AI_ROOT / "reports" / "claim_readiness_matrix_fail_closed_policy_current_regression_report.json"
LOCK_PATH = AI_ROOT / "reports" / ".claim_readiness_matrix_fail_closed_policy_current_regression.lock"


def run(command: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, cwd=AI_ROOT, capture_output=True, text=True, check=False)


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}


def current_command(receipt: Path, signer_lock: Path, output: Path, current_lock: Path) -> list[str]:
    return [
        sys.executable,
        str(CURRENT),
        "--receipt",
        str(receipt),
        "--signer-lock-path",
        str(signer_lock),
        "--output",
        str(output),
        "--lock-path",
        str(current_lock),
    ]


def mutate_sha(field: str) -> Callable[[dict[str, Any]], None]:
    def mutate(payload: dict[str, Any]) -> None:
        payload[field] = "0" * 64
    return mutate


def main() -> int:
    parser = argparse.ArgumentParser(description="Run claim-policy current regression")
    parser.add_argument("--output", type=Path, default=OUTPUT)
    parser.add_argument("--lock-path", type=Path, default=LOCK_PATH)
    parser.add_argument("--lock-timeout-seconds", type=float, default=30.0)
    parser.add_argument("--fail-before-replace", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()

    output_path = args.output.resolve()
    lock_path = args.lock_path.resolve()
    lock_handle = signer.acquire_lock(lock_path, args.lock_timeout_seconds)
    if lock_handle is None:
        print(json.dumps({"success": False, "error": "claim_policy_current_regression_lock_timeout", "output_preserved": output_path.exists()}, ensure_ascii=False, sort_keys=True))
        return 1

    protected = [
        SIGNER,
        CURRENT,
        signer.BUILDER,
        signer.CLAIM_MATRIX,
        signer.POLICY_CONTRACT,
        signer.POLICY_ANCHOR_VALIDATOR,
        signer.POLICY_ANCHOR_REPORT,
    ]
    before = {str(path): signer.sha256(path) for path in protected if path.is_file()}
    rows: list[dict[str, Any]] = []

    with tempfile.TemporaryDirectory(prefix="claim-policy-current-regression-") as name:
        root = Path(name)
        receipt = root / "receipt.json"
        signer_lock = root / "signer.lock"
        current_output = root / "current.json"
        current_lock = root / "current.lock"
        signer_result = run([
            sys.executable,
            str(SIGNER),
            "--output",
            str(receipt),
            "--lock-path",
            str(signer_lock),
        ])
        current_result = run(current_command(receipt, signer_lock, current_output, current_lock))
        current_report = load_json(current_output)
        rows.append({
            "case": "control_current_accepts",
            "passed": signer_result.returncode == 0 and current_result.returncode == 0 and current_report.get("success") is True,
        })

        baseline = load_json(receipt)
        tamper_cases: list[tuple[str, Callable[[dict[str, Any]], None], str]] = [
            ("stale_validator_sha", mutate_sha("validator_sha256"), "validator_sha256"),
            ("stale_builder_sha", mutate_sha("builder_sha256"), "builder_sha256"),
            ("stale_matrix_sha", mutate_sha("claim_matrix_sha256"), "claim_matrix_sha256"),
            ("output_path_drift", lambda payload: payload.update(policy_output_path=str(root / "wrong.json")), "policy_output_path"),
            ("lock_path_drift", lambda payload: payload.update(policy_lock_path=str(root / "wrong.lock")), "policy_lock_path"),
            ("atomic_commit_false", lambda payload: payload.update(policy_atomic_commit=False), "policy_atomic_commit"),
            ("source_parity_false", lambda payload: payload.update(source_parity_success=False), "source_parity_success"),
        ]
        for index, (name_case, mutate, expected_check) in enumerate(tamper_cases, start=1):
            candidate = copy.deepcopy(baseline)
            candidate_path = root / f"tampered-{index}.json"
            candidate["policy_output_path"] = str(candidate_path.resolve())
            mutate(candidate)
            candidate_path.write_text(json.dumps(candidate, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            case_output = root / f"tampered-current-{index}.json"
            result = run(current_command(candidate_path, signer_lock, case_output, root / f"tampered-current-{index}.lock"))
            report = load_json(case_output)
            checks = {str(item.get("check")) for item in report.get("failures") or [] if isinstance(item, dict)}
            rows.append({
                "case": name_case,
                "passed": result.returncode != 0 and report.get("success") is False and expected_check in checks,
                "observed_checks": sorted(checks),
                "expected_check": expected_check,
            })

        prior_signer = receipt.read_bytes()
        interrupted_signer = run([
            sys.executable,
            str(SIGNER),
            "--output",
            str(receipt),
            "--lock-path",
            str(signer_lock),
            "--fail-before-replace",
        ])
        rows.append({
            "case": "signer_replace_interruption_preserves_prior",
            "passed": interrupted_signer.returncode != 0 and receipt.read_bytes() == prior_signer,
        })

        prior_current = current_output.read_bytes()
        interrupted_current = run(current_command(receipt, signer_lock, current_output, current_lock) + ["--fail-before-replace"])
        rows.append({
            "case": "current_replace_interruption_preserves_prior",
            "passed": interrupted_current.returncode != 0 and current_output.read_bytes() == prior_current,
        })

        held_lock = signer_lock.open("a+")
        fcntl.flock(held_lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        prior_lock_output = receipt.read_bytes()
        timed_out = run([
            sys.executable,
            str(SIGNER),
            "--output",
            str(receipt),
            "--lock-path",
            str(signer_lock),
            "--lock-timeout-seconds",
            "0",
        ])
        after_timeout = receipt.read_bytes()
        fcntl.flock(held_lock.fileno(), fcntl.LOCK_UN)
        held_lock.close()
        recovered = run([
            sys.executable,
            str(SIGNER),
            "--output",
            str(receipt),
            "--lock-path",
            str(signer_lock),
        ])
        rows.append({
            "case": "signer_lock_timeout_and_recovery",
            "passed": timed_out.returncode != 0 and after_timeout == prior_lock_output and recovered.returncode == 0,
        })

    after = {str(path): signer.sha256(path) for path in protected if path.is_file()}
    real_inputs_mutated = before != after
    failed_rows = sum(1 for row in rows if not row.get("passed"))
    report = {
        "schema_version": 1,
        "mode": "claim_readiness_matrix_fail_closed_policy_current_regression",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "local_only": True,
        "success": failed_rows == 0 and not real_inputs_mutated,
        "case_count": len(rows),
        "passed_case_count": len(rows) - failed_rows,
        "failed_rows": failed_rows,
        "real_inputs_mutated": real_inputs_mutated,
        "cases": rows,
        "regression_script_path": str(Path(__file__).resolve()),
        "regression_script_sha256": signer.sha256(Path(__file__).resolve()),
        "output_path": str(output_path),
        "lock_path": str(lock_path),
        "lock_acquired": True,
        "atomic_commit": True,
        "safe_for_model_claim": False,
        "release_ready": False,
        "policy": "Isolated regression only; no claim, training, delivery, or release capability is granted.",
    }
    try:
        signer.write_json_atomic(output_path, report, fail_before_replace=args.fail_before_replace)
    except Exception as exc:
        lock_handle.close()
        print(json.dumps({"success": False, "error": f"claim_policy_current_regression_commit_failed:{type(exc).__name__}:{exc}"}, ensure_ascii=False, sort_keys=True))
        return 1
    lock_handle.close()
    print(json.dumps({
        "success": report["success"],
        "case_count": report["case_count"],
        "passed_case_count": report["passed_case_count"],
        "failed_rows": report["failed_rows"],
        "real_inputs_mutated": report["real_inputs_mutated"],
        "output": str(output_path),
    }, ensure_ascii=False, sort_keys=True))
    return 0 if report["success"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
