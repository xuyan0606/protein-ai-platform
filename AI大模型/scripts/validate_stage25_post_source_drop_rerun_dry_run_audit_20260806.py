#!/usr/bin/env python3
"""Validate the Stage 25 post-source-drop rerun dry-run audit."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
AUDIT = AI_ROOT / "reports" / "stage25_post_source_drop_rerun_dry_run_audit_20260806.json"
RECEIPT_VALIDATION = AI_ROOT / "reports" / "stage25_post_source_drop_rerun_receipt_validation_20260806.json"
OUT = AI_ROOT / "reports" / "stage25_post_source_drop_rerun_dry_run_audit_validation_20260806.json"


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
    fail_if(not AUDIT.exists(), failures, "audit_exists", "missing", str(AUDIT))
    audit = load_json(AUDIT) if AUDIT.exists() else {}
    receipt_validation = load_json(RECEIPT_VALIDATION) if RECEIPT_VALIDATION.exists() else {}
    expected_command_rows = receipt_validation.get("command_rows")
    expected_contract_sha256 = receipt_validation.get("command_contract_sha256")
    fail_if(audit.get("mode") != "stage25_post_source_drop_rerun_dry_run_audit", failures, "mode", audit.get("mode"), "stage25_post_source_drop_rerun_dry_run_audit")
    fail_if(receipt_validation.get("receipt_valid") is not True, failures, "receipt_validation_valid", receipt_validation.get("receipt_valid"), True)
    fail_if(receipt_validation.get("failure_count") != 0, failures, "receipt_validation_failure_count_zero", receipt_validation.get("failure_count"), 0)
    fail_if(audit.get("command_rows") != expected_command_rows, failures, "command_rows", audit.get("command_rows"), expected_command_rows)
    fail_if(audit.get("expected_command_rows") != expected_command_rows, failures, "expected_command_rows", audit.get("expected_command_rows"), expected_command_rows)
    fail_if(audit.get("source_receipt_valid") is not True, failures, "source_receipt_valid", audit.get("source_receipt_valid"), True)
    fail_if(audit.get("command_contract_valid") is not True, failures, "command_contract_valid", audit.get("command_contract_valid"), True)
    fail_if(audit.get("command_contract_sha256") != expected_contract_sha256, failures, "command_contract_sha256_parity", audit.get("command_contract_sha256"), expected_contract_sha256)
    fail_if(audit.get("missing_expected_output_rows") != 0, failures, "missing_expected_output_rows_zero", audit.get("missing_expected_output_rows"), 0)
    fail_if(audit.get("sqlite_write_command_rows") != 0, failures, "sqlite_write_command_rows_zero", audit.get("sqlite_write_command_rows"), 0)
    fail_if(audit.get("all_expected_outputs_present") is not True, failures, "all_expected_outputs_present", audit.get("all_expected_outputs_present"), True)
    fail_if(audit.get("all_commands_non_sqlite_write") is not True, failures, "all_commands_non_sqlite_write", audit.get("all_commands_non_sqlite_write"), True)
    fail_if(audit.get("rerun_recipe_operational") is not True, failures, "rerun_recipe_operational", audit.get("rerun_recipe_operational"), True)
    for flag in ("commands_executed", "source_drop_event_receipted", "outputs_freshness_verified", "rerun_completion_receipted", "ready_for_source_drop_rerun"):
        fail_if(audit.get(flag) is not False, failures, f"{flag}_false", audit.get(flag), False)
    fail_if(audit.get("commands_executed_rows") != 0, failures, "commands_executed_rows_zero", audit.get("commands_executed_rows"), 0)
    fail_if(audit.get("commands_not_executed_rows") != expected_command_rows, failures, "commands_not_executed_rows", audit.get("commands_not_executed_rows"), expected_command_rows)
    for flag in ("source_evidence_ready", "ready_for_reviewed_extraction", "ready_for_sqlite_apply"):
        fail_if(audit.get(flag) is not False, failures, f"{flag}_false", audit.get(flag), False)
    policy = str(audit.get("policy") or "")
    for term in ("may be stale", "does not execute commands", "verify output freshness", "prove rerun completion"):
        fail_if(term not in policy, failures, f"policy_contains.{term}", policy, f"contains {term}")
    for flag in ("external_sqlite_mutated", "apply_executed", "export_safe_released", "safe_for_model_claim", "release_ready"):
        fail_if(audit.get(flag) is not False, failures, f"{flag}_false", audit.get(flag), False)
    fail_if(audit.get("formal_decision_rows_written") != 0, failures, "formal_decision_rows_written_zero", audit.get("formal_decision_rows_written"), 0)

    validation = {
        "schema_version": 1,
        "created_at": "2026-08-06",
        "mode": "stage25_post_source_drop_rerun_dry_run_audit_validation",
        "stage": 25,
        "audit_valid": not failures,
        "failure_count": len(failures),
        "failures": failures,
        "command_rows": audit.get("command_rows"),
        "source_receipt_valid": audit.get("source_receipt_valid"),
        "command_contract_sha256": audit.get("command_contract_sha256"),
        "command_contract_valid": audit.get("command_contract_valid"),
        "missing_expected_output_rows": audit.get("missing_expected_output_rows"),
        "sqlite_write_command_rows": audit.get("sqlite_write_command_rows"),
        "rerun_recipe_operational": audit.get("rerun_recipe_operational"),
        "commands_executed": False,
        "commands_executed_rows": 0,
        "commands_not_executed_rows": audit.get("commands_not_executed_rows"),
        "source_drop_event_receipted": False,
        "outputs_freshness_verified": False,
        "rerun_completion_receipted": False,
        "ready_for_source_drop_rerun": audit.get("ready_for_source_drop_rerun"),
        "source_evidence_ready": False,
        "ready_for_reviewed_extraction": False,
        "ready_for_sqlite_apply": False,
        "external_sqlite_mutated": False,
        "apply_executed": False,
        "formal_decision_rows_written": 0,
        "export_safe_released": False,
        "safe_for_model_claim": False,
        "release_ready": False,
    }
    OUT.write_text(json.dumps(validation, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "output": str(OUT),
        "audit_valid": validation["audit_valid"],
        "failure_count": validation["failure_count"],
        "ready_for_source_drop_rerun": validation["ready_for_source_drop_rerun"],
    }, ensure_ascii=False, sort_keys=True))
    return 0 if validation["audit_valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
