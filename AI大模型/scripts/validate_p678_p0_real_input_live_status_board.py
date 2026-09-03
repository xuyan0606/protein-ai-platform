#!/usr/bin/env python3
"""Validate P678 P0 real-input live status board."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
CHECKLIST = AI_ROOT / "datasets" / "governance" / "p677_p0_real_input_completion_checklist.jsonl"
P677_VALIDATION = AI_ROOT / "reports" / "p677_p0_real_input_completion_checklist_validation_report.json"
STATUS = AI_ROOT / "datasets" / "governance" / "p678_p0_real_input_live_status_board.jsonl"
REPORT = AI_ROOT / "reports" / "p678_p0_real_input_live_status_board_report.json"
OUT = AI_ROOT / "reports" / "p678_p0_real_input_live_status_board_validation_report.json"

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
    checklist = load_jsonl(CHECKLIST)
    p677_validation = load_json(P677_VALIDATION)
    rows = load_jsonl(STATUS)
    report = load_json(REPORT)
    failures: list[dict[str, Any]] = []

    checklist_lanes = {row.get("lane") for row in checklist}
    status_lanes = {row.get("lane") for row in rows}
    fail_if(p677_validation.get("success") is not True, failures, "p677_validation_success", p677_validation.get("success"), True)
    fail_if(len(rows) != len(checklist), failures, "status_rows_match_checklist", len(rows), len(checklist))
    fail_if(status_lanes != checklist_lanes or status_lanes != EXPECTED_LANES, failures, "status_lanes_exact", sorted(status_lanes), sorted(EXPECTED_LANES))
    for idx, row in enumerate(rows, start=1):
        fail_if(not str(row.get("live_status") or "").startswith("blocked_"), failures, "row_live_status_blocked", {"row": idx, "value": row.get("live_status")}, "blocked_*")
        for field in ("status_id", "checklist_id", "handoff_id", "lane", "formal_target_file", "validator_report", "blocker", "observed", "next_required_action", "completion_condition"):
            fail_if(row.get(field) in (None, "", []), failures, f"row_{field}_present", {"row": idx, "value": row.get(field)}, "present")
        for field in FALSE_FIELDS:
            fail_if(row.get(field) is not False, failures, f"row_{field}_false", {"row": idx, "value": row.get(field)}, False)

    fail_if(report.get("status_rows") != len(rows), failures, "report_status_rows", report.get("status_rows"), len(rows))
    fail_if(report.get("source_checklist_rows") != len(checklist), failures, "report_source_checklist_rows", report.get("source_checklist_rows"), len(checklist))
    fail_if(report.get("source_checklist_validation_success") is not True, failures, "report_source_checklist_validation_success", report.get("source_checklist_validation_success"), True)
    for field in ("blocked_status_rows",):
        fail_if(report.get(field) != len(rows), failures, f"report_{field}", report.get(field), len(rows))
    for field in ("real_input_received_rows", "formal_validator_passed_rows", "completion_ready_rows", "p0_unblocked_rows"):
        fail_if(report.get(field) != 0, failures, f"report_{field}_zero", report.get(field), 0)
    for field in REPORT_FALSE_FIELDS:
        fail_if(report.get(field) is not False, failures, f"report_{field}_false", report.get(field), False)

    result = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "local_only": True,
        "success": not failures,
        "failure_count": len(failures),
        "failures": failures,
        "status_rows": len(rows),
        "blocked_status_rows": len(rows),
        "source_checklist_rows": len(checklist),
        "real_input_received_rows": 0,
        "formal_validator_passed_rows": 0,
        "completion_ready_rows": 0,
        "p0_unblocked_rows": 0,
        "training_import_allowed": False,
        "safe_for_training_import": False,
        "safe_for_model_claim": False,
        "customer_delivery_ready": False,
        "release_ready": False,
        "production_execution_allowed": False,
        "p0_unblocked": False,
        "completion_ready": False,
        "policy": "Validation only. P678 live status reports current blockers and cannot write or approve formal inputs.",
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({
        "success": result["success"],
        "status_rows": len(rows),
        "blocked_status_rows": len(rows),
        "completion_ready_rows": 0,
        "failures": len(failures),
        "output": str(OUT),
    }, ensure_ascii=False))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
