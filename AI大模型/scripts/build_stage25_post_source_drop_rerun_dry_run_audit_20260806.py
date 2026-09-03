#!/usr/bin/env python3
"""Build a dry-run audit for the Stage 25 post-source-drop rerun receipt."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
RERUN = AI_ROOT / "reports" / "stage25_post_source_drop_rerun_receipt_20260806.json"
RERUN_VALIDATION = AI_ROOT / "reports" / "stage25_post_source_drop_rerun_receipt_validation_20260806.json"
OUT = AI_ROOT / "reports" / "stage25_post_source_drop_rerun_dry_run_audit_20260806.json"


def load_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise SystemExit(f"{path} must contain a JSON object")
    return data


def main() -> int:
    receipt = load_json(RERUN)
    receipt_validation = load_json(RERUN_VALIDATION)
    command_rows = []
    for row in receipt.get("commands") or []:
        expected_output = row.get("expected_output")
        expected_path = Path(str(expected_output)) if expected_output else None
        command_rows.append({
            "name": row.get("name"),
            "cmd": row.get("cmd"),
            "writes_sqlite": row.get("writes_sqlite") is True,
            "blocks_apply_until_passed": row.get("blocks_apply_until_passed") is True,
            "expected_output": expected_output,
            "expected_output_exists": expected_path.exists() if expected_path else None,
        })
    missing_outputs = [
        row for row in command_rows
        if row.get("expected_output") and row.get("expected_output_exists") is not True
    ]
    sqlite_write_rows = [row for row in command_rows if row.get("writes_sqlite") is True]
    command_contract_valid = receipt_validation.get("command_contract_valid") is True
    rerun_recipe_operational = (
        receipt_validation.get("receipt_valid") is True
        and command_contract_valid
        and not missing_outputs
        and not sqlite_write_rows
        and len(command_rows) == receipt.get("command_rows")
    )
    report = {
        "schema_version": 1,
        "created_at": "2026-08-06",
        "mode": "stage25_post_source_drop_rerun_dry_run_audit",
        "stage": 25,
        "source_receipt": str(RERUN),
        "source_receipt_validation": str(RERUN_VALIDATION),
        "source_receipt_valid": receipt_validation.get("receipt_valid") is True,
        "command_contract_sha256": receipt_validation.get("command_contract_sha256"),
        "command_contract_valid": command_contract_valid,
        "command_rows": len(command_rows),
        "expected_command_rows": receipt.get("command_rows"),
        "expected_output_rows": sum(1 for row in command_rows if row.get("expected_output")),
        "missing_expected_output_rows": len(missing_outputs),
        "sqlite_write_command_rows": len(sqlite_write_rows),
        "all_expected_outputs_present": not missing_outputs,
        "all_commands_non_sqlite_write": not sqlite_write_rows,
        "rerun_recipe_operational": rerun_recipe_operational,
        "commands_executed": False,
        "commands_executed_rows": 0,
        "commands_not_executed_rows": len(command_rows),
        "source_drop_event_receipted": False,
        "outputs_freshness_verified": False,
        "rerun_completion_receipted": False,
        "ready_for_source_drop_rerun": False,
        "commands": command_rows,
        "missing_expected_outputs": missing_outputs,
        "source_evidence_ready": False,
        "ready_for_reviewed_extraction": False,
        "ready_for_sqlite_apply": False,
        "external_sqlite_mutated": False,
        "apply_executed": False,
        "formal_decision_rows_written": 0,
        "export_safe_released": False,
        "safe_for_model_claim": False,
        "release_ready": False,
        "policy": "Dry-run audit only. rerun_recipe_operational means the exact validated non-SQLite recipe and its expected output paths are available. Existing outputs may be stale. This audit does not execute commands, receipt a source-drop event, verify output freshness, prove rerun completion, source evidence, reviewed extraction, SQLite apply approval, formal decisions, benchmark intake, model claims, customer delivery, or release.",
    }
    OUT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "output": str(OUT),
        "command_rows": report["command_rows"],
        "missing_expected_output_rows": report["missing_expected_output_rows"],
        "sqlite_write_command_rows": report["sqlite_write_command_rows"],
    }, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
