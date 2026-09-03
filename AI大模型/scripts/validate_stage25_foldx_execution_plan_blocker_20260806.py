#!/usr/bin/env python3
"""Validate the Stage 25 FoldX execution-plan blocker receipt."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
RECEIPT = AI_ROOT / "reports" / "stage25_foldx_execution_plan_blocker_20260806.json"
OUTPUT = AI_ROOT / "reports" / "stage25_foldx_execution_plan_blocker_validation_20260806.json"


def load_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise SystemExit(f"{path} must contain a JSON object")
    return data


def fail_if(condition: bool, failures: list[dict[str, Any]], check: str, observed: Any, expected: Any) -> None:
    if condition:
        failures.append({"check": check, "observed": observed, "expected": expected})


def main() -> int:
    failures: list[dict[str, Any]] = []
    fail_if(not RECEIPT.exists(), failures, "receipt_exists", "missing", str(RECEIPT))
    receipt = load_json(RECEIPT) if RECEIPT.exists() else {}

    fail_if(receipt.get("mode") != "stage25_foldx_execution_plan_blocker", failures, "mode", receipt.get("mode"), "stage25_foldx_execution_plan_blocker")
    fail_if(receipt.get("selected_backend") != "foldx", failures, "selected_backend", receipt.get("selected_backend"), "foldx")
    fail_if(receipt.get("plan_rows") != 25, failures, "plan_rows", receipt.get("plan_rows"), 25)
    fail_if(receipt.get("jsonl_rows") != 25, failures, "jsonl_rows", receipt.get("jsonl_rows"), 25)
    fail_if(receipt.get("ready_rows") != 0, failures, "ready_rows_zero", receipt.get("ready_rows"), 0)
    fail_if(receipt.get("blocked_rows") != 25, failures, "blocked_rows", receipt.get("blocked_rows"), 25)
    fail_if(receipt.get("receipt_decision") != "blocked_execution_plan_no_ready_rows", failures, "receipt_decision", receipt.get("receipt_decision"), "blocked_execution_plan_no_ready_rows")
    fail_if(receipt.get("foldx_technical_probe_ready") is not True, failures, "foldx_technical_probe_ready", receipt.get("foldx_technical_probe_ready"), True)
    fail_if(receipt.get("foldx_buildmodel_technical_smoke_executed") is not True, failures, "foldx_buildmodel_technical_smoke_executed", receipt.get("foldx_buildmodel_technical_smoke_executed"), True)
    fail_if(receipt.get("foldx_technical_smoke_only") is not True, failures, "foldx_technical_smoke_only", receipt.get("foldx_technical_smoke_only"), True)
    fail_if(receipt.get("foldx_technical_smoke_artifact_count") != 5, failures, "foldx_technical_smoke_artifact_count", receipt.get("foldx_technical_smoke_artifact_count"), 5)
    fail_if(receipt.get("foldx_technical_smoke_satisfies_formal_provision") is not False, failures, "foldx_technical_smoke_satisfies_formal_provision_false", receipt.get("foldx_technical_smoke_satisfies_formal_provision"), False)
    fail_if(receipt.get("foldx_ready_for_execution") is not False, failures, "foldx_ready_for_execution_false", receipt.get("foldx_ready_for_execution"), False)
    fail_if(receipt.get("foldx_data_ready") is not False, failures, "foldx_data_ready_false", receipt.get("foldx_data_ready"), False)
    fail_if(not receipt.get("foldx_backend_blockers"), failures, "foldx_backend_blockers_nonempty", receipt.get("foldx_backend_blockers"), "non-empty")
    fail_if(not receipt.get("plan_blocker_counts"), failures, "plan_blocker_counts_nonempty", receipt.get("plan_blocker_counts"), "non-empty")
    for flag in (
        "formal_runtime_receipt_written",
        "approved_for_physical_ddg_runtime",
        "foldx_buildmodel_physical_smoke_executed",
        "external_sqlite_mutated",
        "apply_executed",
        "export_safe_released",
        "safe_for_model_claim",
        "release_ready",
    ):
        fail_if(receipt.get(flag) is not False, failures, f"{flag}_false", receipt.get(flag), False)
    fail_if(receipt.get("bridge_intake_rows_written") != 0, failures, "bridge_intake_rows_written_zero", receipt.get("bridge_intake_rows_written"), 0)

    validation = {
        "schema_version": 1,
        "created_at": "2026-08-06",
        "mode": "stage25_foldx_execution_plan_blocker_validation",
        "stage": 25,
        "receipt_valid": not failures,
        "failure_count": len(failures),
        "failures": failures,
        "plan_rows": receipt.get("plan_rows"),
        "ready_rows": receipt.get("ready_rows"),
        "blocked_rows": receipt.get("blocked_rows"),
        "receipt_decision": receipt.get("receipt_decision"),
        "foldx_ready_for_execution": receipt.get("foldx_ready_for_execution"),
        "foldx_data_ready": receipt.get("foldx_data_ready"),
        "formal_runtime_receipt_written": False,
        "approved_for_physical_ddg_runtime": False,
        "foldx_buildmodel_physical_smoke_executed": False,
        "foldx_buildmodel_technical_smoke_executed": receipt.get("foldx_buildmodel_technical_smoke_executed"),
        "foldx_technical_smoke_only": receipt.get("foldx_technical_smoke_only"),
        "foldx_technical_smoke_artifact_count": receipt.get("foldx_technical_smoke_artifact_count"),
        "foldx_technical_smoke_satisfies_formal_provision": False,
        "bridge_intake_rows_written": 0,
        "external_sqlite_mutated": False,
        "apply_executed": False,
        "export_safe_released": False,
        "safe_for_model_claim": False,
        "release_ready": False,
    }
    OUTPUT.write_text(json.dumps(validation, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "output": str(OUTPUT),
        "receipt_valid": validation["receipt_valid"],
        "failure_count": validation["failure_count"],
        "ready_rows": validation["ready_rows"],
    }, ensure_ascii=False, sort_keys=True))
    return 0 if validation["receipt_valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
