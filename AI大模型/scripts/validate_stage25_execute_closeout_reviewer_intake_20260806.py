#!/usr/bin/env python3
"""Validate reviewer intake template for Stage 25 execute closeout items."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
INTAKE = AI_ROOT / "datasets" / "governance" / "stage25_execute_closeout_reviewer_intake_20260806.jsonl"
OUTPUT = AI_ROOT / "reports" / "stage25_execute_closeout_reviewer_intake_validation_20260806.json"
VALID_DECISIONS = {"needs_more_info", "approved", "rejected"}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        row = json.loads(line)
        if not isinstance(row, dict):
            raise ValueError(f"{path}:{line_number} must contain a JSON object")
        rows.append(row)
    return rows


def fail_if(condition: bool, failures: list[dict[str, Any]], check: str, observed: Any, expected: Any) -> None:
    if condition:
        failures.append({"check": check, "observed": observed, "expected": expected})


def main() -> int:
    failures: list[dict[str, Any]] = []
    fail_if(not INTAKE.exists(), failures, "intake_exists", "missing", str(INTAKE))
    rows = load_jsonl(INTAKE) if INTAKE.exists() else []
    ids = [row.get("intake_id") for row in rows]

    fail_if(len(rows) != 24, failures, "intake_rows", len(rows), 24)
    fail_if(len(set(ids)) != len(ids), failures, "unique_intake_ids", len(set(ids)), len(ids))
    for index, row in enumerate(rows, start=1):
        prefix = f"rows[{index}]"
        fail_if(row.get("stage") != 25, failures, f"{prefix}.stage", row.get("stage"), 25)
        fail_if(row.get("review_decision") not in VALID_DECISIONS, failures, f"{prefix}.review_decision", row.get("review_decision"), sorted(VALID_DECISIONS))
        fail_if(row.get("closed") is not False, failures, f"{prefix}.closed_false", row.get("closed"), False)
        fail_if(row.get("approved_for_family_importer") is not False, failures, f"{prefix}.approved_for_family_importer_false", row.get("approved_for_family_importer"), False)
        fail_if(row.get("export_safe") is not False, failures, f"{prefix}.export_safe_false", row.get("export_safe"), False)
        for field in ("evidence_artifacts", "source_locators", "payload_draft_refs", "required_before_apply"):
            fail_if(not isinstance(row.get(field), list), failures, f"{prefix}.{field}_list", row.get(field), "list")
        fail_if(not row.get("required_before_apply"), failures, f"{prefix}.required_before_apply_nonempty", row.get("required_before_apply"), "non-empty")

    validation = {
        "schema_version": 1,
        "created_at": "2026-08-06",
        "mode": "stage25_execute_closeout_reviewer_intake_validation",
        "stage": 25,
        "intake_valid": not failures,
        "failure_count": len(failures),
        "failures": failures,
        "intake_rows": len(rows),
        "closed_rows": sum(1 for row in rows if row.get("closed") is True),
        "approved_rows": sum(1 for row in rows if row.get("review_decision") == "approved"),
        "external_sqlite_mutated": False,
        "formal_decision_rows_written": 0,
        "apply_executed": False,
        "export_safe_released": False,
        "safe_for_model_claim": False,
        "release_ready": False,
    }
    OUTPUT.write_text(json.dumps(validation, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(OUTPUT), "intake_valid": validation["intake_valid"], "failure_count": validation["failure_count"], "intake_rows": validation["intake_rows"]}, ensure_ascii=False, sort_keys=True))
    return 0 if validation["intake_valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
