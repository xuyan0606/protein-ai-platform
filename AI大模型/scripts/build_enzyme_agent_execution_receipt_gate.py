#!/usr/bin/env python3
"""Build a fail-closed receipt gate for future enzyme agent action execution."""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from enzyme_agent_execution_receipt_proof_io import acquire_lock, write_json_atomic, write_jsonl_atomic


AI_ROOT = Path(__file__).resolve().parents[1]
RECEIPTS = AI_ROOT / "datasets" / "governance" / "enzyme_agent_execution_receipts.local.jsonl"
TEMPLATE = AI_ROOT / "datasets" / "governance" / "enzyme_agent_execution_receipts.template.jsonl"
OUT = AI_ROOT / "reports" / "enzyme_agent_execution_receipt_gate_report.json"
EXECUTION_WAVE = AI_ROOT / "reports" / "enzyme_agent_controlled_execution_wave_report.json"
WAVE_SCRIPT = AI_ROOT / "scripts" / "run_enzyme_agent_controlled_execution_wave.py"
LOCK_PATH = AI_ROOT / "reports" / ".enzyme_agent_execution_receipt_proof.lock"


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description="Build enzyme agent execution receipt gate")
    parser.add_argument("--receipts", type=Path, default=RECEIPTS)
    parser.add_argument("--template", type=Path, default=TEMPLATE)
    parser.add_argument("--output", type=Path, default=OUT)
    parser.add_argument("--lock-path", type=Path, default=LOCK_PATH)
    parser.add_argument("--lock-timeout-seconds", type=float, default=30.0)
    args = parser.parse_args()

    lock_handle = acquire_lock(args.lock_path, args.lock_timeout_seconds)
    if lock_handle is None:
        print(json.dumps({"success": False, "error": "receipt_proof_lock_timeout", "output_preserved": args.output.exists()}, ensure_ascii=False))
        return 1
    try:

        created_at = datetime.now(timezone.utc).isoformat()
        trace = load_json(AI_ROOT / "reports" / "enzyme_agent_trace_audit_report.json")
        resource_plan = load_json(AI_ROOT / "reports" / "enzyme_resource_retrieval_plan_report.json")
        execution_wave = load_json(EXECUTION_WAVE)
        if not args.receipts.exists():
            write_jsonl_atomic(args.receipts, [], prefix="receipt-gate")
        receipts = load_jsonl(args.receipts)
        executed_action_ids = execution_wave.get("executed_action_ids") or trace.get("executed_action_ids") or []
        receipt_action_ids = [row.get("action_id") for row in receipts]
        receipt_status_counts: dict[str, int] = {}
        for row in receipts:
            status = row.get("return_status") or "missing_status"
            receipt_status_counts[status] = receipt_status_counts.get(status, 0) + 1

        template_row = {
        "receipt_id": "example_do_not_copy_without_actual_execution",
        "created_at": created_at,
        "local_only": True,
        "trace_id": trace.get("trace_id") or "enzyme_agent_trace_20260731_p170",
        "plan_id": trace.get("plan_id") or resource_plan.get("plan_id"),
        "action_id": "act_example",
        "tool_contract_id": "tool_example",
        "execution_mode": "local_script",
        "human_confirmation_ref": "required_before_execution",
        "input_artifacts": [],
        "output_artifacts": [],
        "validator_artifacts": [],
        "return_status": "not_executed",
        "writes_formal_decision": False,
        "writes_training_rows": False,
        "safe_for_training_import": False,
        "safe_for_model_claim": False,
        "release_ready": False,
        "template_policy": "Template only. A real receipt requires explicit user authorization, concrete artifacts, validator outputs, and must still keep training/model/release flags false unless separate formal gates approve them.",
        }
        write_jsonl_atomic(args.template, [template_row], prefix="receipt-gate")

        script = Path(__file__).resolve()
        report = {
        "schema_version": 2,
        "mode": "enzyme-agent-execution-receipt-gate-v2",
        "created_at": created_at,
        "receipt_gate_builder_script_path": str(script),
        "receipt_gate_builder_script_sha256": sha256(script),
        "output_path": str(args.output.resolve()),
        "lock_path": str(args.lock_path.resolve()),
        "lock_acquired": True,
        "atomic_commit": True,
        "local_only": True,
        "schema": "schemas/enzyme_agent_execution_receipt.schema.json",
        "trace_id": trace.get("trace_id"),
        "plan_id": execution_wave.get("plan_id") or trace.get("plan_id") or resource_plan.get("plan_id"),
        "execution_wave_report": str(EXECUTION_WAVE.relative_to(AI_ROOT)) if EXECUTION_WAVE.exists() else None,
        "execution_wave_report_sha256": sha256(EXECUTION_WAVE) if EXECUTION_WAVE.is_file() else None,
        "execution_wave_receipts_path": execution_wave.get("receipts_path"),
        "execution_wave_receipts_sha256": execution_wave.get("receipts_sha256"),
        "execution_wave_script_path": execution_wave.get("wave_script_path"),
        "execution_wave_script_sha256": execution_wave.get("wave_script_sha256"),
        "execution_wave_atomic_pair_valid": all(execution_wave.get(field) is True for field in ("success", "lock_acquired", "receipts_atomic_commit", "report_atomic_commit")),
        "authorization_ref": execution_wave.get("authorization_ref"),
        "executed_action_count": len(executed_action_ids),
        "executed_action_ids": executed_action_ids,
        "receipt_rows": len(receipts),
        "receipt_action_ids": receipt_action_ids,
        "receipt_status_counts": receipt_status_counts,
        "executed_passed_receipt_rows": receipt_status_counts.get("executed_passed", 0),
        "executed_failed_receipt_rows": receipt_status_counts.get("executed_failed", 0),
        "missing_receipt_action_ids": sorted(set(executed_action_ids) - set(receipt_action_ids)),
        "unexpected_receipt_action_ids": sorted(set(receipt_action_ids) - set(executed_action_ids)),
        "template": str(args.template.relative_to(AI_ROOT)),
        "receipts": str(args.receipts.relative_to(AI_ROOT)),
        "receipt_required_before_execution_claim": True,
        "safe_for_execution_claim": False,
        "safe_for_training_import": False,
        "safe_for_model_claim": False,
        "release_ready": False,
        "policy": "Executed actions must have one matching receipt with concrete outputs and validator artifacts. Receipts record execution evidence only; they do not create formal human decisions, import training rows, approve physics ddG, or unlock model/release claims.",
        }
        write_json_atomic(args.output, report, prefix="receipt-gate")
    finally:
        lock_handle.close()
    print(json.dumps({
        "executed_action_count": report["executed_action_count"],
        "receipt_rows": report["receipt_rows"],
        "missing_receipts": len(report["missing_receipt_action_ids"]),
        "unexpected_receipts": len(report["unexpected_receipt_action_ids"]),
        "safe_for_model_claim": False,
        "output": str(args.output),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
