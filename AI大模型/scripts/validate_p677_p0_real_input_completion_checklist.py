#!/usr/bin/env python3
"""Validate the P677 real-input completion checklist remains fail-closed."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
P676_PACKAGE = AI_ROOT / "datasets" / "governance" / "p676_p0_real_input_handoff_work_package.jsonl"
P676_VALIDATION = AI_ROOT / "reports" / "p676_p0_real_input_handoff_work_package_validation_report.json"
CHECKLIST = AI_ROOT / "datasets" / "governance" / "p677_p0_real_input_completion_checklist.jsonl"
CHECKLIST_CSV = AI_ROOT / "datasets" / "governance" / "p677_p0_real_input_completion_checklist.csv"
REPORT = AI_ROOT / "reports" / "p677_p0_real_input_completion_checklist_report.json"
OUT = AI_ROOT / "reports" / "p677_p0_real_input_completion_checklist_validation_report.json"

EXPECTED_LANES = {
    "plate_feedback",
    "strict_holdout",
    "substrate_identity",
    "numbering_curation",
    "governance",
}
FALSE_FIELDS = (
    "real_input_received",
    "formal_validator_passed",
    "completion_ready",
    "p0_unblocked",
    "training_import_allowed",
    "safe_for_training_import",
    "safe_for_model_claim",
    "customer_delivery_ready",
    "release_ready",
    "production_execution_allowed",
)
REPORT_FALSE_FIELDS = (
    "training_import_allowed",
    "safe_for_training_import",
    "safe_for_model_claim",
    "customer_delivery_ready",
    "release_ready",
    "production_execution_allowed",
    "p0_unblocked",
    "completion_ready",
)


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    value = json.loads(path.read_text(encoding="utf-8"))
    return value if isinstance(value, dict) else {}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def fail_if(condition: bool, failures: list[dict[str, Any]], check: str, observed: Any, expected: Any) -> None:
    if condition:
        failures.append({"check": check, "observed": observed, "expected": expected})


def main() -> int:
    p676_rows = load_jsonl(P676_PACKAGE)
    p676_validation = load_json(P676_VALIDATION)
    rows = load_jsonl(CHECKLIST)
    report = load_json(REPORT)
    failures: list[dict[str, Any]] = []

    p676_ids = {row.get("handoff_id") for row in p676_rows}
    checklist_handoff_ids = {row.get("handoff_id") for row in rows}
    lanes = {row.get("lane") for row in rows}
    fail_if(p676_validation.get("success") is not True, failures, "p676_validation_success", p676_validation.get("success"), True)
    fail_if(len(rows) != len(p676_rows), failures, "checklist_rows_match_p676", len(rows), len(p676_rows))
    fail_if(checklist_handoff_ids != p676_ids, failures, "checklist_handoff_ids_match_p676", sorted(checklist_handoff_ids), sorted(p676_ids))
    fail_if(lanes != EXPECTED_LANES, failures, "checklist_lanes_exact", sorted(lanes), sorted(EXPECTED_LANES))
    fail_if(not CHECKLIST_CSV.exists(), failures, "checklist_csv_exists", CHECKLIST_CSV.exists(), True)

    priorities = [row.get("priority") for row in rows]
    fail_if(priorities != sorted(priorities), failures, "priorities_sorted", priorities, sorted(priorities))
    for idx, row in enumerate(rows, start=1):
        for field in (
            "checklist_id",
            "handoff_id",
            "lane",
            "first_operator_action",
            "formal_target_file",
            "template_or_reference_file",
            "primary_validator_command",
            "completion_condition",
        ):
            fail_if(not row.get(field), failures, f"row_{field}_present", {"row": idx, "value": row.get(field)}, "present")
        fail_if(not row.get("required_fields"), failures, "row_required_fields_present", {"row": idx, "value": row.get("required_fields")}, "non-empty")
        fail_if(row.get("source_status") != "open_blocked_waiting_for_real_input", failures, "row_source_status_open_blocked", {"row": idx, "value": row.get("source_status")}, "open_blocked_waiting_for_real_input")
        for field in FALSE_FIELDS:
            fail_if(row.get(field) is not False, failures, f"row_{field}_false", {"row": idx, "value": row.get(field)}, False)

    fail_if(report.get("checklist_rows") != len(rows), failures, "report_checklist_rows", report.get("checklist_rows"), len(rows))
    fail_if(report.get("source_handoff_rows") != len(p676_rows), failures, "report_source_handoff_rows", report.get("source_handoff_rows"), len(p676_rows))
    fail_if(report.get("source_handoff_validation_success") is not True, failures, "report_source_validation_success", report.get("source_handoff_validation_success"), True)
    for field in ("completion_ready_rows", "real_input_received_rows", "formal_validator_passed_rows", "p0_unblocked_rows"):
        fail_if(report.get(field) != 0, failures, f"report_{field}_zero", report.get(field), 0)
    for field in REPORT_FALSE_FIELDS:
        fail_if(report.get(field) is not False, failures, f"report_{field}_false", report.get(field), False)

    result = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "local_only": True,
        "success": not failures,
        "failure_count": len(failures),
        "failures": failures,
        "checklist_rows": len(rows),
        "source_handoff_rows": len(p676_rows),
        "open_checklist_rows": len(rows),
        "completion_ready_rows": 0,
        "real_input_received_rows": 0,
        "formal_validator_passed_rows": 0,
        "p0_unblocked_rows": 0,
        "training_import_allowed": False,
        "safe_for_training_import": False,
        "safe_for_model_claim": False,
        "customer_delivery_ready": False,
        "release_ready": False,
        "production_execution_allowed": False,
        "p0_unblocked": False,
        "completion_ready": False,
        "policy": "Validation only. P677 checklist rows are not completion evidence until real formal input files and their validators pass.",
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({
        "success": result["success"],
        "checklist_rows": len(rows),
        "completion_ready_rows": 0,
        "failures": len(failures),
        "output": str(OUT),
    }, ensure_ascii=False))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
