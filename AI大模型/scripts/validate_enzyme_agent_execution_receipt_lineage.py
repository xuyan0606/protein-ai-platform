#!/usr/bin/env python3
"""Validate current enzyme-agent execution receipt lineage."""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from enzyme_agent_execution_receipt_proof_io import acquire_lock, write_json_atomic

AI_ROOT = Path(__file__).resolve().parents[1]
RECEIPTS = AI_ROOT / "datasets" / "governance" / "enzyme_agent_execution_receipts.local.jsonl"
EXECUTION_WAVE = AI_ROOT / "reports" / "enzyme_agent_controlled_execution_wave_report.json"
RECEIPT_GATE = AI_ROOT / "reports" / "enzyme_agent_execution_receipt_gate_report.json"
GATE_VALIDATION = AI_ROOT / "reports" / "enzyme_agent_execution_receipt_gate_validation_report.json"
OUT = AI_ROOT / "reports" / "enzyme_agent_execution_receipt_lineage_validation_report.json"
WAVE_SCRIPT = AI_ROOT / "scripts" / "run_enzyme_agent_controlled_execution_wave.py"
LOCK_PATH = AI_ROOT / "reports" / ".enzyme_agent_execution_receipt_proof.lock"


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()] if path.is_file() else []


def sha256(path: Path) -> str | None:
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None


def fail_if(condition: bool, failures: list[dict[str, Any]], check: str, observed: Any, expected: Any) -> None:
    if condition:
        failures.append({"check": check, "observed": observed, "expected": expected})


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate enzyme agent execution receipt lineage")
    parser.add_argument("--receipts", type=Path, default=RECEIPTS)
    parser.add_argument("--execution-wave", type=Path, default=EXECUTION_WAVE)
    parser.add_argument("--receipt-gate", type=Path, default=RECEIPT_GATE)
    parser.add_argument("--gate-validation", type=Path, default=GATE_VALIDATION)
    parser.add_argument("--output", type=Path, default=OUT)
    parser.add_argument("--lock-path", type=Path, default=LOCK_PATH)
    parser.add_argument("--lock-timeout-seconds", type=float, default=30.0)
    args = parser.parse_args()
    handle = acquire_lock(args.lock_path, args.lock_timeout_seconds)
    if handle is None:
        print(json.dumps({"success": False, "error": "receipt_proof_lock_timeout", "output_preserved": args.output.exists()}, ensure_ascii=False))
        return 1
    try:
        receipts = load_jsonl(args.receipts)
        wave = load_json(args.execution_wave)
        gate = load_json(args.receipt_gate)
        gate_validation = load_json(args.gate_validation)
        failures: list[dict[str, Any]] = []
        receipt_actions = [row.get("action_id") for row in receipts]
        receipt_ids = [row.get("receipt_id") for row in receipts]
        wave_actions = wave.get("executed_action_ids") or []
        wave_sha = sha256(args.execution_wave)
        gate_sha = sha256(args.receipt_gate)
        receipts_sha = sha256(args.receipts)
        fail_if(gate_validation.get("success") is not True, failures, "gate_validation_success", gate_validation.get("success"), True)
        fail_if(gate_validation.get("gate_report_sha256") != gate_sha, failures, "gate_validation_gate_sha_current", gate_validation.get("gate_report_sha256"), gate_sha)
        fail_if(gate_validation.get("receipts_sha256") != receipts_sha, failures, "gate_validation_receipts_sha_current", gate_validation.get("receipts_sha256"), receipts_sha)
        fail_if(not wave.get("authorization_ref"), failures, "authorization_ref_present", wave.get("authorization_ref"), "nonempty")
        fail_if(not wave.get("plan_id"), failures, "plan_id_present", wave.get("plan_id"), "nonempty")
        fail_if(len(receipts) != wave.get("executed_receipt_rows"), failures, "receipt_rows_match_wave", len(receipts), wave.get("executed_receipt_rows"))
        fail_if(set(receipt_actions) != set(wave_actions), failures, "receipt_actions_match_wave_actions", sorted(receipt_actions), sorted(wave_actions))
        fail_if(len(receipt_actions) != len(set(receipt_actions)), failures, "receipt_action_ids_unique", receipt_actions, "unique")
        fail_if(len(receipt_ids) != len(set(receipt_ids)), failures, "receipt_ids_unique", receipt_ids, "unique")
        fail_if(gate.get("receipt_rows") != len(receipts), failures, "gate_receipt_rows_match_file", gate.get("receipt_rows"), len(receipts))
        fail_if(set(gate.get("receipt_action_ids") or []) != set(receipt_actions), failures, "gate_receipt_actions_match_file", sorted(gate.get("receipt_action_ids") or []), sorted(receipt_actions))
        for field, expected in {"schema_version": 2, "mode": "enzyme-agent-controlled-execution-wave-v2", "success": True, "wave_script_path": str(WAVE_SCRIPT.resolve()), "wave_script_sha256": sha256(WAVE_SCRIPT), "receipts_path": str(args.receipts.resolve()), "receipts_sha256": receipts_sha, "output_path": str(args.execution_wave.resolve()), "lock_acquired": True, "receipts_atomic_commit": True, "report_atomic_commit": True}.items():
            fail_if(wave.get(field) != expected, failures, "wave_provenance_current", {"field": field, "observed": wave.get(field)}, expected)
        fail_if(gate.get("execution_wave_report_sha256") != wave_sha, failures, "gate_wave_report_sha_current", gate.get("execution_wave_report_sha256"), wave_sha)
        fail_if(gate.get("execution_wave_receipts_sha256") != receipts_sha, failures, "gate_wave_receipts_sha_current", gate.get("execution_wave_receipts_sha256"), receipts_sha)
        statuses = {row.get("action_id"): row.get("return_status") for row in wave.get("action_results") or []}
        for index, row in enumerate(receipts):
            action_id = row.get("action_id")
            fail_if(row.get("human_confirmation_ref") != wave.get("authorization_ref"), failures, "receipt_authorization_ref_matches_wave", index, action_id)
            fail_if(row.get("plan_id") != wave.get("plan_id"), failures, "receipt_plan_id_matches_wave", index, action_id)
            fail_if(row.get("return_status") != statuses.get(action_id), failures, "receipt_status_matches_wave", index, action_id)
            for field in ("local_only",):
                fail_if(row.get(field) is not True, failures, f"receipt_{field}_true", index, action_id)
            for field in ("writes_formal_decision", "writes_training_rows", "safe_for_training_import", "safe_for_model_claim", "release_ready"):
                fail_if(row.get(field) is not False, failures, f"receipt_{field}_false", index, action_id)
        script = Path(__file__).resolve()
        result = {"schema_version": 2, "mode": "enzyme-agent-execution-receipt-lineage-validation-v2", "created_at": datetime.now(timezone.utc).isoformat(), "lineage_script_path": str(script), "lineage_script_sha256": sha256(script), "receipts_path": str(args.receipts.resolve()), "receipts_sha256": receipts_sha, "execution_wave_path": str(args.execution_wave.resolve()), "execution_wave_sha256": wave_sha, "gate_report_path": str(args.receipt_gate.resolve()), "gate_report_sha256": gate_sha, "gate_validation_path": str(args.gate_validation.resolve()), "gate_validation_sha256": sha256(args.gate_validation), "output_path": str(args.output.resolve()), "lock_path": str(args.lock_path.resolve()), "lock_acquired": True, "atomic_commit": True, "local_only": True, "success": not failures, "authorization_ref": wave.get("authorization_ref"), "plan_id": wave.get("plan_id"), "execution_wave": str(args.execution_wave.relative_to(AI_ROOT)), "receipt_rows": len(receipts), "wave_action_rows": len(wave_actions), "receipt_action_rows": len(receipt_actions), "unique_receipt_ids": len(set(receipt_ids)), "executed_passed_rows": sum(1 for row in receipts if row.get("return_status") == "executed_passed"), "executed_failed_rows": sum(1 for row in receipts if row.get("return_status") == "executed_failed"), "failures": failures, "safe_for_training_import": False, "safe_for_model_claim": False, "release_ready": False}
        write_json_atomic(args.output, result, prefix="receipt-lineage")
    finally:
        handle.close()
    print(json.dumps({"success": result["success"], "receipt_rows": result["receipt_rows"], "failures": len(failures), "output": str(args.output)}, ensure_ascii=False))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
