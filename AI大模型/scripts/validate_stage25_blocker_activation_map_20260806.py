#!/usr/bin/env python3
"""Validate Stage 25 blocker activation map."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
MAP = AI_ROOT / "reports" / "stage25_blocker_activation_map_20260806.json"
OUTPUT = AI_ROOT / "reports" / "stage25_blocker_activation_map_validation_20260806.json"
EXPECTED_BLOCKERS = {
    "stage25_new_paper_fulltext_source_table",
    "stage25_sqlite_apply",
    "stage25_formal_decisions",
    "stage25_foldx_runtime_receipt",
    "stage25_model_release_claim",
}


def load_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return data


def fail_if(condition: bool, failures: list[dict[str, Any]], check: str, observed: Any, expected: Any) -> None:
    if condition:
        failures.append({"check": check, "observed": observed, "expected": expected})


def main() -> int:
    failures: list[dict[str, Any]] = []
    fail_if(not MAP.exists(), failures, "activation_map_exists", "missing", str(MAP))
    report = load_json(MAP) if MAP.exists() else {}
    rows = report.get("activations") if isinstance(report.get("activations"), list) else []
    mapped = {str(row.get("blocker_id")) for row in rows if isinstance(row, dict)}

    fail_if(report.get("mode") != "stage25_blocker_activation_map", failures, "mode", report.get("mode"), "stage25_blocker_activation_map")
    fail_if(report.get("activation_rows") != 5, failures, "activation_rows", report.get("activation_rows"), 5)
    fail_if(report.get("all_blockers_mapped") is not True, failures, "all_blockers_mapped_true", report.get("all_blockers_mapped"), True)
    fail_if(mapped != EXPECTED_BLOCKERS, failures, "mapped_blocker_ids", sorted(mapped), sorted(EXPECTED_BLOCKERS))
    fail_if(report.get("activation_completion_ready_rows") != 0, failures, "activation_completion_ready_rows_zero", report.get("activation_completion_ready_rows"), 0)

    for index, row in enumerate(rows, start=1):
        prefix = f"activations[{index}]"
        for field in ("blocker_id", "trigger_inputs", "rerun_commands", "expected_flip_fields", "must_remain_false_until_next_gate"):
            fail_if(field not in row, failures, f"{prefix}.{field}_present", row.get(field), "present")
        fail_if(not isinstance(row.get("trigger_inputs"), list) or not row.get("trigger_inputs"), failures, f"{prefix}.trigger_inputs_nonempty", row.get("trigger_inputs"), "non-empty list")
        fail_if(not isinstance(row.get("rerun_commands"), list) or not row.get("rerun_commands"), failures, f"{prefix}.rerun_commands_nonempty", row.get("rerun_commands"), "non-empty list")
        fail_if(not isinstance(row.get("expected_flip_fields"), list) or not row.get("expected_flip_fields"), failures, f"{prefix}.expected_flip_fields_nonempty", row.get("expected_flip_fields"), "non-empty list")
        fail_if(row.get("current_completion_ready") is not False, failures, f"{prefix}.current_completion_ready_false", row.get("current_completion_ready"), False)

    for flag in ("external_sqlite_mutated", "apply_executed", "export_safe_released", "safe_for_model_claim", "release_ready"):
        fail_if(report.get(flag) is not False, failures, f"{flag}_false", report.get(flag), False)
    fail_if(report.get("formal_decision_rows_written") != 0, failures, "formal_decision_rows_written_zero", report.get("formal_decision_rows_written"), 0)

    validation = {
        "schema_version": 1,
        "created_at": "2026-08-06",
        "mode": "stage25_blocker_activation_map_validation",
        "stage": 25,
        "activation_map_valid": not failures,
        "failure_count": len(failures),
        "failures": failures,
        "activation_rows": len(rows),
        "activation_completion_ready_rows": report.get("activation_completion_ready_rows"),
        "all_blockers_mapped": report.get("all_blockers_mapped"),
        "external_sqlite_mutated": False,
        "formal_decision_rows_written": 0,
        "apply_executed": False,
        "export_safe_released": False,
        "safe_for_model_claim": False,
        "release_ready": False,
    }
    OUTPUT.write_text(json.dumps(validation, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(OUTPUT), "activation_map_valid": validation["activation_map_valid"], "failure_count": validation["failure_count"], "activation_rows": validation["activation_rows"]}, ensure_ascii=False, sort_keys=True))
    return 0 if validation["activation_map_valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
