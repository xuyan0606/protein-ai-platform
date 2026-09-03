#!/usr/bin/env python3
"""Validate the enzyme agent execution receipt gate."""

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
REPORT = AI_ROOT / "reports" / "enzyme_agent_execution_receipt_gate_report.json"
OUT = AI_ROOT / "reports" / "enzyme_agent_execution_receipt_gate_validation_report.json"
EXECUTION_WAVE = AI_ROOT / "reports" / "enzyme_agent_controlled_execution_wave_report.json"
WAVE_SCRIPT = AI_ROOT / "scripts" / "run_enzyme_agent_controlled_execution_wave.py"
LOCK_PATH = AI_ROOT / "reports" / ".enzyme_agent_execution_receipt_proof.lock"

REQUIRED_RECEIPT_FIELDS = {
    "receipt_id",
    "created_at",
    "local_only",
    "trace_id",
    "plan_id",
    "action_id",
    "tool_contract_id",
    "execution_mode",
    "input_artifacts",
    "output_artifacts",
    "validator_artifacts",
    "return_status",
    "writes_formal_decision",
    "writes_training_rows",
    "safe_for_training_import",
    "safe_for_model_claim",
    "release_ready",
}

ALLOWED_RETURN_STATUS = {"not_executed", "executed_passed", "executed_failed", "blocked"}


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def fail_if(condition: bool, failures: list[dict[str, Any]], check: str, observed: Any, expected: Any) -> None:
    if condition:
        failures.append({"check": check, "observed": observed, "expected": expected})


def validate_receipt_gate_object(
    report: dict[str, Any],
    receipts: list[dict[str, Any]],
    ai_root: Path = AI_ROOT,
    execution_wave: dict[str, Any] | None = None,
    execution_wave_path: Path = EXECUTION_WAVE,
) -> list[dict[str, Any]]:
    failures: list[dict[str, Any]] = []
    executed_action_ids = report.get("executed_action_ids") or []
    receipt_action_ids = [row.get("action_id") for row in receipts]
    wave = execution_wave if execution_wave is not None else load_json(execution_wave_path)
    receipt_path = (ai_root / "datasets" / "governance" / "enzyme_agent_execution_receipts.local.jsonl").resolve()
    receipt_sha256 = sha256(receipt_path) if receipt_path.is_file() else None

    fail_if(report.get("executed_action_count") != len(executed_action_ids), failures, "executed_action_count_matches_ids", report.get("executed_action_count"), len(executed_action_ids))
    fail_if(report.get("receipt_rows") != len(receipts), failures, "receipt_rows_match_file", report.get("receipt_rows"), len(receipts))
    fail_if(report.get("missing_receipt_action_ids") not in ([], None), failures, "missing_receipts_empty", report.get("missing_receipt_action_ids"), [])
    fail_if(report.get("unexpected_receipt_action_ids") not in ([], None), failures, "unexpected_receipts_empty", report.get("unexpected_receipt_action_ids"), [])
    fail_if(set(executed_action_ids) != set(receipt_action_ids), failures, "receipt_actions_match_executed_actions", sorted(receipt_action_ids), sorted(executed_action_ids))
    fail_if(len(receipt_action_ids) != len(set(receipt_action_ids)), failures, "receipt_action_ids_unique", receipt_action_ids, "unique action_id per execution wave")
    fail_if(report.get("receipt_required_before_execution_claim") is not True, failures, "receipt_required_true", report.get("receipt_required_before_execution_claim"), True)
    fail_if(report.get("safe_for_execution_claim") is not False, failures, "safe_for_execution_claim_false", report.get("safe_for_execution_claim"), False)
    fail_if(report.get("safe_for_training_import") is not False, failures, "report_training_import_false", report.get("safe_for_training_import"), False)
    fail_if(report.get("safe_for_model_claim") is not False, failures, "report_model_claim_false", report.get("safe_for_model_claim"), False)
    fail_if(report.get("release_ready") is not False, failures, "report_release_ready_false", report.get("release_ready"), False)
    expected_wave_fields = {
        "schema_version": 2,
        "mode": "enzyme-agent-controlled-execution-wave-v2",
        "success": True,
        "wave_script_path": str(WAVE_SCRIPT.resolve()),
        "wave_script_sha256": sha256(WAVE_SCRIPT) if WAVE_SCRIPT.is_file() else None,
        "receipts_path": str(receipt_path),
        "receipts_sha256": receipt_sha256,
        "output_path": str(execution_wave_path.resolve()),
        "lock_path": str((ai_root / "reports" / ".enzyme_agent_controlled_execution_wave.lock").resolve()),
        "lock_acquired": True,
        "receipts_atomic_commit": True,
        "report_atomic_commit": True,
    }
    for field, expected in expected_wave_fields.items():
        fail_if(wave.get(field) != expected, failures, "execution_wave_provenance_current", {"field": field, "observed": wave.get(field)}, expected)
    expected_gate_fields = {
        "schema_version": 2,
        "mode": "enzyme-agent-execution-receipt-gate-v2",
        "execution_wave_report": str(execution_wave_path.relative_to(ai_root)),
        "execution_wave_report_sha256": sha256(execution_wave_path) if execution_wave_path.is_file() else None,
        "execution_wave_receipts_path": str(receipt_path),
        "execution_wave_receipts_sha256": receipt_sha256,
        "execution_wave_script_path": str(WAVE_SCRIPT.resolve()),
        "execution_wave_script_sha256": sha256(WAVE_SCRIPT) if WAVE_SCRIPT.is_file() else None,
        "execution_wave_atomic_pair_valid": True,
    }
    for field, expected in expected_gate_fields.items():
        fail_if(report.get(field) != expected, failures, "receipt_gate_execution_wave_binding", {"field": field, "observed": report.get(field)}, expected)

    for idx, row in enumerate(receipts):
        missing = sorted(REQUIRED_RECEIPT_FIELDS - set(row))
        if missing:
            failures.append({"check": "receipt_required_fields_present", "index": idx, "missing": missing})
        fail_if(row.get("local_only") is not True, failures, "receipt_local_only_true", {"index": idx, "observed": row.get("local_only")}, True)
        fail_if(row.get("safe_for_training_import") is not False, failures, "receipt_training_import_false", {"index": idx, "observed": row.get("safe_for_training_import")}, False)
        fail_if(row.get("safe_for_model_claim") is not False, failures, "receipt_model_claim_false", {"index": idx, "observed": row.get("safe_for_model_claim")}, False)
        fail_if(row.get("release_ready") is not False, failures, "receipt_release_ready_false", {"index": idx, "observed": row.get("release_ready")}, False)
        fail_if(row.get("return_status") not in ALLOWED_RETURN_STATUS, failures, "receipt_return_status_allowed", {"index": idx, "observed": row.get("return_status")}, sorted(ALLOWED_RETURN_STATUS))
        if row.get("return_status") in {"executed_passed", "executed_failed"}:
            fail_if(not row.get("output_artifacts"), failures, "executed_receipt_output_artifacts_nonempty", {"index": idx, "observed": row.get("output_artifacts")}, "nonempty")
            fail_if(not row.get("validator_artifacts"), failures, "executed_receipt_validator_artifacts_nonempty", {"index": idx, "observed": row.get("validator_artifacts")}, "nonempty")
        for rel in (row.get("output_artifacts") or []) + (row.get("validator_artifacts") or []):
            if not isinstance(rel, str) or not (ai_root / rel).exists():
                failures.append({"check": "receipt_artifact_exists", "index": idx, "observed": rel, "expected": "existing local artifact"})

    return failures


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate enzyme agent execution receipt gate")
    parser.add_argument("--receipts", type=Path, default=RECEIPTS)
    parser.add_argument("--report", type=Path, default=REPORT)
    parser.add_argument("--output", type=Path, default=OUT)
    parser.add_argument("--execution-wave", type=Path, default=EXECUTION_WAVE)
    parser.add_argument("--lock-path", type=Path, default=LOCK_PATH)
    parser.add_argument("--lock-timeout-seconds", type=float, default=30.0)
    args = parser.parse_args()

    lock_handle = acquire_lock(args.lock_path, args.lock_timeout_seconds)
    if lock_handle is None:
        print(json.dumps({"success": False, "error": "receipt_proof_lock_timeout", "output_preserved": args.output.exists()}, ensure_ascii=False))
        return 1

    try:
        report = load_json(args.report)
        receipts = load_jsonl(args.receipts)
        execution_wave = load_json(args.execution_wave)
        failures = validate_receipt_gate_object(report, receipts, execution_wave=execution_wave, execution_wave_path=args.execution_wave)
        executed_action_ids = report.get("executed_action_ids") or []

        script = Path(__file__).resolve()
        validation = {
        "schema_version": 2,
        "mode": "enzyme-agent-execution-receipt-gate-validation-v2",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "validator_script_path": str(script),
        "validator_script_sha256": sha256(script),
        "gate_report_path": str(args.report.resolve()),
        "gate_report_sha256": sha256(args.report) if args.report.is_file() else None,
        "execution_wave_path": str(args.execution_wave.resolve()),
        "execution_wave_sha256": sha256(args.execution_wave) if args.execution_wave.is_file() else None,
        "receipts_path": str(args.receipts.resolve()),
        "receipts_sha256": sha256(args.receipts) if args.receipts.is_file() else None,
        "output_path": str(args.output.resolve()),
        "lock_path": str(args.lock_path.resolve()),
        "lock_acquired": True,
        "atomic_commit": True,
        "local_only": True,
        "success": not failures,
        "executed_action_count": len(executed_action_ids),
        "receipt_rows": len(receipts),
        "executed_passed_receipt_rows": sum(1 for row in receipts if row.get("return_status") == "executed_passed"),
        "executed_failed_receipt_rows": sum(1 for row in receipts if row.get("return_status") == "executed_failed"),
        "missing_receipt_action_count": len(report.get("missing_receipt_action_ids") or []),
        "unexpected_receipt_action_count": len(report.get("unexpected_receipt_action_ids") or []),
        "failures": failures,
        "safe_for_execution_claim": False,
        "safe_for_training_import": False,
        "safe_for_model_claim": False,
        "release_ready": False,
        "policy": "Receipt gate validation only confirms current execution claims are blocked or fully receipted. It does not authorize execution, training import, model claims, customer delivery, or release.",
        }
        write_json_atomic(args.output, validation, prefix="receipt-gate-validation")
    finally:
        lock_handle.close()
    print(json.dumps({
        "success": validation["success"],
        "executed_action_count": validation["executed_action_count"],
        "receipt_rows": validation["receipt_rows"],
        "failures": len(failures),
        "safe_for_model_claim": False,
        "output": str(args.output),
    }, ensure_ascii=False))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
