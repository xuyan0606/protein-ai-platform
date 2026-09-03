#!/usr/bin/env python3
"""Isolated tamper and recovery regression for execution receipt current proof."""

from __future__ import annotations

import copy
import fcntl
import hashlib
import json
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from enzyme_agent_execution_receipt_proof_io import acquire_lock, write_json_atomic

AI_ROOT = Path(__file__).resolve().parents[1]
VALIDATOR = AI_ROOT / "scripts" / "validate_enzyme_agent_execution_receipt_proof_current.py"
SOURCES = {
    "wave": AI_ROOT / "reports" / "enzyme_agent_controlled_execution_wave_report.json",
    "receipts": AI_ROOT / "datasets" / "governance" / "enzyme_agent_execution_receipts.local.jsonl",
    "gate": AI_ROOT / "reports" / "enzyme_agent_execution_receipt_gate_report.json",
    "gate_validation": AI_ROOT / "reports" / "enzyme_agent_execution_receipt_gate_validation_report.json",
    "lineage": AI_ROOT / "reports" / "enzyme_agent_execution_receipt_lineage_validation_report.json",
}
OUTPUT = AI_ROOT / "reports" / "enzyme_agent_execution_receipt_proof_current_regression_report.json"
LOCK = AI_ROOT / "reports" / ".enzyme_agent_execution_receipt_proof.lock"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path: Path, data: dict[str, Any]) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def run(paths: dict[str, Path], output: Path, lock: Path, *extra: str) -> tuple[int, dict[str, Any]]:
    process = subprocess.run([sys.executable, str(VALIDATOR), "--wave", str(paths["wave"]), "--receipts", str(paths["receipts"]), "--gate", str(paths["gate"]), "--gate-validation", str(paths["gate_validation"]), "--lineage", str(paths["lineage"]), "--output", str(output), "--lock-path", str(lock), *extra], cwd=AI_ROOT, capture_output=True, text=True, check=False)
    report = json.loads(output.read_text(encoding="utf-8")) if output.is_file() else {}
    return process.returncode, report


def bind_fixture(paths: dict[str, Path], lock: Path) -> None:
    receipts_sha = sha(paths["receipts"])
    wave = json.loads(SOURCES["wave"].read_text(encoding="utf-8"))
    wave.update({"receipts_path": str(paths["receipts"].resolve()), "receipts_sha256": receipts_sha, "output_path": str(paths["wave"].resolve())})
    write(paths["wave"], wave)
    gate = json.loads(SOURCES["gate"].read_text(encoding="utf-8"))
    gate.update({"execution_wave_report": str(paths["wave"].resolve()), "execution_wave_report_sha256": sha(paths["wave"]), "execution_wave_receipts_path": str(paths["receipts"].resolve()), "execution_wave_receipts_sha256": receipts_sha, "output_path": str(paths["gate"].resolve()), "lock_path": str(lock.resolve())})
    write(paths["gate"], gate)
    gate_validation = json.loads(SOURCES["gate_validation"].read_text(encoding="utf-8"))
    gate_validation.update({"gate_report_path": str(paths["gate"].resolve()), "gate_report_sha256": sha(paths["gate"]), "execution_wave_path": str(paths["wave"].resolve()), "execution_wave_sha256": sha(paths["wave"]), "receipts_path": str(paths["receipts"].resolve()), "receipts_sha256": receipts_sha, "output_path": str(paths["gate_validation"].resolve()), "lock_path": str(lock.resolve())})
    write(paths["gate_validation"], gate_validation)
    lineage = json.loads(SOURCES["lineage"].read_text(encoding="utf-8"))
    lineage.update({"receipts_path": str(paths["receipts"].resolve()), "receipts_sha256": receipts_sha, "execution_wave_path": str(paths["wave"].resolve()), "execution_wave_sha256": sha(paths["wave"]), "gate_report_path": str(paths["gate"].resolve()), "gate_report_sha256": sha(paths["gate"]), "gate_validation_path": str(paths["gate_validation"].resolve()), "gate_validation_sha256": sha(paths["gate_validation"]), "output_path": str(paths["lineage"].resolve()), "lock_path": str(lock.resolve())})
    write(paths["lineage"], lineage)


def main() -> int:
    protected = [VALIDATOR, *SOURCES.values()]
    before = {str(path): sha(path) for path in protected}
    results: list[dict[str, Any]] = []
    with tempfile.TemporaryDirectory(prefix="receipt-proof-current-") as name:
        root = Path(name)
        paths = {key: root / source.name for key, source in SOURCES.items()}
        paths["receipts"].write_bytes(SOURCES["receipts"].read_bytes())
        lock, current = root / "proof.lock", root / "current.json"
        bind_fixture(paths, lock)
        rc, report = run(paths, current, lock)
        results.append({"case": "fixture_control", "passed": rc == 0 and report.get("success") is True})
        cases = [
            ("gate_wave_sha_drift", "gate", "execution_wave_report_sha256", "0" * 64, "gate_wave_sha"),
            ("gate_validation_gate_sha_drift", "gate_validation", "gate_report_sha256", "1" * 64, "gate_validation_gate_sha"),
            ("lineage_gate_validation_sha_drift", "lineage", "gate_validation_sha256", "2" * 64, "lineage_gate_validation_sha"),
            ("lineage_script_sha_drift", "lineage", "lineage_script_sha256", "3" * 64, "lineage_script_sha"),
            ("gate_output_path_drift", "gate", "output_path", "/tmp/forged-gate.json", "gate_output_path"),
            ("gate_validation_lock_drift", "gate_validation", "lock_path", "/tmp/forged.lock", "gate_validation_lock_path"),
            ("lineage_atomic_false", "lineage", "atomic_commit", False, "lineage_atomic_commit"),
        ]
        for case, role, field, value, expected in cases:
            bind_fixture(paths, lock)
            data = json.loads(paths[role].read_text(encoding="utf-8")); data[field] = value; write(paths[role], data)
            rc, report = run(paths, current, lock)
            checks = [row.get("check") for row in report.get("failures") or []]
            results.append({"case": case, "passed": rc != 0 and expected in checks, "expected_check": expected})
        bind_fixture(paths, lock); run(paths, current, lock); prior = current.read_bytes()
        holder = lock.open("a+"); fcntl.flock(holder.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        rc, _ = run(paths, current, lock, "--lock-timeout-seconds", "0")
        fcntl.flock(holder.fileno(), fcntl.LOCK_UN); holder.close()
        results.append({"case": "lock_timeout_preserves_prior", "passed": rc != 0 and current.read_bytes() == prior})
        rc, _ = run(paths, current, lock, "--fail-before-replace")
        no_temp = not list(root.glob(f".{current.name}.receipt-proof-current-*"))
        results.append({"case": "replace_interrupt_preserves_prior", "passed": rc != 0 and current.read_bytes() == prior and no_temp})
        rc, report = run(paths, current, lock)
        results.append({"case": "recovery_commits_current", "passed": rc == 0 and report.get("success") is True})
    after = {str(path): sha(path) for path in protected}
    failed = sum(not row["passed"] for row in results)
    failures = [] if before == after and failed == 0 else [{"check": "all_cases_and_inputs", "failed_cases": failed, "inputs_changed": before != after}]
    script = Path(__file__).resolve()
    final = {"schema_version": 1, "mode": "enzyme-agent-execution-receipt-proof-current-regression-v1", "created_at": datetime.now(timezone.utc).isoformat(), "success": not failures, "isolated_fixture": True, "regression_script_path": str(script), "regression_script_sha256": sha(script), "current_validator_path": str(VALIDATOR), "current_validator_sha256": sha(VALIDATOR), "output_path": str(OUTPUT), "lock_path": str(LOCK), "lock_acquired": True, "atomic_commit": True, "case_count": len(results), "passed_case_count": len(results) - failed, "failed_case_count": failed, "real_inputs_mutated": before != after, "failure_count": len(failures), "failures": failures, "cases": results, "safe_for_model_claim": False, "release_ready": False}
    handle = acquire_lock(LOCK, 30.0)
    if handle is None:
        return 1
    try:
        write_json_atomic(OUTPUT, final, prefix="receipt-proof-current-regression")
    finally:
        handle.close()
    print(json.dumps({"success": final["success"], "case_count": final["case_count"], "passed_case_count": final["passed_case_count"], "failure_count": final["failure_count"], "real_inputs_mutated": final["real_inputs_mutated"], "output": str(OUTPUT)}, ensure_ascii=False))
    return 0 if final["success"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
