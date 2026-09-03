#!/usr/bin/env python3
"""Validate Stage 25 execute closeout checklist."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
CHECKLIST = AI_ROOT / "reports" / "stage25_execute_closeout_checklist_20260806.json"
OUTPUT = AI_ROOT / "reports" / "stage25_execute_closeout_checklist_validation_20260806.json"
EXPECTED_CHECKS = {
    "approved_for_family_importer",
    "human_review_status",
    "intake_approval",
    "paper_pdf",
    "payload_draft",
    "source_locators",
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
    fail_if(not CHECKLIST.exists(), failures, "checklist_exists", "missing", str(CHECKLIST))
    checklist = load_json(CHECKLIST) if CHECKLIST.exists() else {}
    proposals = checklist.get("proposals") if isinstance(checklist.get("proposals"), list) else []
    items = checklist.get("checklist_items") if isinstance(checklist.get("checklist_items"), list) else []

    fail_if(checklist.get("mode") != "stage25_execute_closeout_checklist", failures, "mode", checklist.get("mode"), "stage25_execute_closeout_checklist")
    fail_if(checklist.get("proposal_rows") != 4, failures, "proposal_rows", checklist.get("proposal_rows"), 4)
    fail_if(checklist.get("checklist_item_rows") != 24, failures, "checklist_item_rows", checklist.get("checklist_item_rows"), 24)
    fail_if(checklist.get("closed_item_rows") != 0, failures, "closed_item_rows_zero", checklist.get("closed_item_rows"), 0)
    fail_if(checklist.get("closeout_ready_rows") != 0, failures, "closeout_ready_rows_zero", checklist.get("closeout_ready_rows"), 0)
    for index, row in enumerate(proposals, start=1):
        prefix = f"proposals[{index}]"
        fail_if(row.get("blocker_count") != 6, failures, f"{prefix}.blocker_count", row.get("blocker_count"), 6)
        fail_if(set(row.get("checks") or []) != EXPECTED_CHECKS, failures, f"{prefix}.checks", sorted(row.get("checks") or []), sorted(EXPECTED_CHECKS))
        fail_if(row.get("closeout_ready") is not False, failures, f"{prefix}.closeout_ready_false", row.get("closeout_ready"), False)
        fail_if(not row.get("required_before_apply"), failures, f"{prefix}.required_before_apply_nonempty", row.get("required_before_apply"), "non-empty")
    for index, row in enumerate(items, start=1):
        prefix = f"checklist_items[{index}]"
        fail_if(row.get("check") not in EXPECTED_CHECKS, failures, f"{prefix}.check_expected", row.get("check"), sorted(EXPECTED_CHECKS))
        fail_if(row.get("closed") is not False, failures, f"{prefix}.closed_false", row.get("closed"), False)

    for flag in ("external_sqlite_mutated", "apply_executed", "export_safe_released", "safe_for_model_claim", "release_ready"):
        fail_if(checklist.get(flag) is not False, failures, f"{flag}_false", checklist.get(flag), False)
    fail_if(checklist.get("formal_decision_rows_written") != 0, failures, "formal_decision_rows_written_zero", checklist.get("formal_decision_rows_written"), 0)

    validation = {
        "schema_version": 1,
        "created_at": "2026-08-06",
        "mode": "stage25_execute_closeout_checklist_validation",
        "stage": 25,
        "checklist_valid": not failures,
        "failure_count": len(failures),
        "failures": failures,
        "proposal_rows": len(proposals),
        "checklist_item_rows": len(items),
        "closed_item_rows": checklist.get("closed_item_rows"),
        "closeout_ready_rows": checklist.get("closeout_ready_rows"),
        "external_sqlite_mutated": False,
        "formal_decision_rows_written": 0,
        "apply_executed": False,
        "export_safe_released": False,
        "safe_for_model_claim": False,
        "release_ready": False,
    }
    OUTPUT.write_text(json.dumps(validation, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(OUTPUT), "checklist_valid": validation["checklist_valid"], "failure_count": validation["failure_count"], "checklist_item_rows": validation["checklist_item_rows"]}, ensure_ascii=False, sort_keys=True))
    return 0 if validation["checklist_valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
