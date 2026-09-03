#!/usr/bin/env python3
"""Validate the current, atomically signed execution receipt proof set."""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from enzyme_agent_execution_receipt_proof_io import acquire_lock, write_json_atomic

AI_ROOT = Path(__file__).resolve().parents[1]
WAVE = AI_ROOT / "reports" / "enzyme_agent_controlled_execution_wave_report.json"
RECEIPTS = AI_ROOT / "datasets" / "governance" / "enzyme_agent_execution_receipts.local.jsonl"
GATE = AI_ROOT / "reports" / "enzyme_agent_execution_receipt_gate_report.json"
GATE_VALIDATION = AI_ROOT / "reports" / "enzyme_agent_execution_receipt_gate_validation_report.json"
LINEAGE = AI_ROOT / "reports" / "enzyme_agent_execution_receipt_lineage_validation_report.json"
WAVE_SCRIPT = AI_ROOT / "scripts" / "run_enzyme_agent_controlled_execution_wave.py"
GATE_SCRIPT = AI_ROOT / "scripts" / "build_enzyme_agent_execution_receipt_gate.py"
GATE_VALIDATOR = AI_ROOT / "scripts" / "validate_enzyme_agent_execution_receipt_gate.py"
LINEAGE_VALIDATOR = AI_ROOT / "scripts" / "validate_enzyme_agent_execution_receipt_lineage.py"
OUT = AI_ROOT / "reports" / "enzyme_agent_execution_receipt_proof_current_validation_report.json"
LOCK = AI_ROOT / "reports" / ".enzyme_agent_execution_receipt_proof.lock"


def sha(path: Path) -> str | None:
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None


def load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}


def check(failures: list[dict[str, Any]], name: str, observed: Any, expected: Any) -> None:
    if observed != expected:
        failures.append({"check": name, "observed": observed, "expected": expected})


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate current execution receipt proof set")
    parser.add_argument("--wave", type=Path, default=WAVE)
    parser.add_argument("--receipts", type=Path, default=RECEIPTS)
    parser.add_argument("--gate", type=Path, default=GATE)
    parser.add_argument("--gate-validation", type=Path, default=GATE_VALIDATION)
    parser.add_argument("--lineage", type=Path, default=LINEAGE)
    parser.add_argument("--output", type=Path, default=OUT)
    parser.add_argument("--lock-path", type=Path, default=LOCK)
    parser.add_argument("--lock-timeout-seconds", type=float, default=30.0)
    parser.add_argument("--fail-before-replace", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()
    handle = acquire_lock(args.lock_path, args.lock_timeout_seconds)
    if handle is None:
        print(json.dumps({"success": False, "error": "receipt_proof_lock_timeout", "output_preserved": args.output.exists()}, ensure_ascii=False))
        return 1
    try:
        wave, gate, gate_validation, lineage = (load(path) for path in (args.wave, args.gate, args.gate_validation, args.lineage))
        failures: list[dict[str, Any]] = []
        wave_sha, receipts_sha, gate_sha, gate_validation_sha = sha(args.wave), sha(args.receipts), sha(args.gate), sha(args.gate_validation)
        expected_lock = str(args.lock_path.resolve())
        check(failures, "wave_success", wave.get("success"), True)
        check(failures, "gate_success", gate.get("execution_wave_atomic_pair_valid"), True)
        check(failures, "gate_validation_success", gate_validation.get("success"), True)
        check(failures, "lineage_success", lineage.get("success"), True)
        check(failures, "wave_receipts_sha", wave.get("receipts_sha256"), receipts_sha)
        check(failures, "wave_receipts_path", wave.get("receipts_path"), str(args.receipts.resolve()))
        check(failures, "wave_output_path", wave.get("output_path"), str(args.wave.resolve()))
        check(failures, "gate_wave_sha", gate.get("execution_wave_report_sha256"), wave_sha)
        check(failures, "gate_receipts_sha", gate.get("execution_wave_receipts_sha256"), receipts_sha)
        check(failures, "gate_validation_gate_sha", gate_validation.get("gate_report_sha256"), gate_sha)
        check(failures, "gate_validation_receipts_sha", gate_validation.get("receipts_sha256"), receipts_sha)
        check(failures, "lineage_gate_sha", lineage.get("gate_report_sha256"), gate_sha)
        check(failures, "lineage_gate_validation_sha", lineage.get("gate_validation_sha256"), gate_validation_sha)
        check(failures, "lineage_wave_sha", lineage.get("execution_wave_sha256"), wave_sha)
        check(failures, "lineage_receipts_sha", lineage.get("receipts_sha256"), receipts_sha)
        for report, label, script in ((gate, "gate", GATE_SCRIPT), (gate_validation, "gate_validation", GATE_VALIDATOR), (lineage, "lineage", LINEAGE_VALIDATOR)):
            check(failures, f"{label}_script_sha", report.get("receipt_gate_builder_script_sha256") or report.get("validator_script_sha256") or report.get("lineage_script_sha256"), sha(script))
            check(failures, f"{label}_lock_path", report.get("lock_path"), expected_lock)
            check(failures, f"{label}_lock_acquired", report.get("lock_acquired"), True)
            check(failures, f"{label}_atomic_commit", report.get("atomic_commit"), True)
        check(failures, "gate_output_path", gate.get("output_path"), str(args.gate.resolve()))
        check(failures, "gate_wave_path", gate.get("execution_wave_report"), str(args.wave.resolve().relative_to(AI_ROOT)) if args.wave.resolve().is_relative_to(AI_ROOT) else str(args.wave.resolve()))
        check(failures, "gate_validation_output_path", gate_validation.get("output_path"), str(args.gate_validation.resolve()))
        check(failures, "gate_validation_gate_path", gate_validation.get("gate_report_path"), str(args.gate.resolve()))
        check(failures, "lineage_output_path", lineage.get("output_path"), str(args.lineage.resolve()))
        check(failures, "lineage_gate_path", lineage.get("gate_report_path"), str(args.gate.resolve()))
        check(failures, "lineage_gate_validation_path", lineage.get("gate_validation_path"), str(args.gate_validation.resolve()))
        result = {"schema_version": 1, "mode": "enzyme-agent-execution-receipt-proof-current-v1", "created_at": datetime.now(timezone.utc).isoformat(), "success": not failures, "wave_path": str(args.wave.resolve()), "wave_sha256": wave_sha, "receipts_path": str(args.receipts.resolve()), "receipts_sha256": receipts_sha, "gate_path": str(args.gate.resolve()), "gate_sha256": gate_sha, "gate_validation_path": str(args.gate_validation.resolve()), "gate_validation_sha256": gate_validation_sha, "lineage_path": str(args.lineage.resolve()), "lineage_sha256": sha(args.lineage), "output_path": str(args.output.resolve()), "lock_path": expected_lock, "lock_acquired": True, "atomic_commit": True, "failure_count": len(failures), "failures": failures, "safe_for_model_claim": False, "release_ready": False}
        write_json_atomic(args.output, result, prefix="receipt-proof-current", fail_before_replace=args.fail_before_replace)
    finally:
        handle.close()
    print(json.dumps({"success": result["success"], "failure_count": result["failure_count"], "output": str(args.output)}, ensure_ascii=False))
    return 0 if result["success"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
