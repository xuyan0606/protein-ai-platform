#!/usr/bin/env python3
"""Validate the P679 P0 real-input status freshness audit."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
STATUS = AI_ROOT / "datasets" / "governance" / "p678_p0_real_input_live_status_board.jsonl"
STATUS_VALIDATION = AI_ROOT / "reports" / "p678_p0_real_input_live_status_board_validation_report.json"
AUDIT = AI_ROOT / "datasets" / "governance" / "p679_p0_real_input_status_freshness_audit.jsonl"
REPORT = AI_ROOT / "reports" / "p679_p0_real_input_status_freshness_audit_report.json"
OUT = AI_ROOT / "reports" / "p679_p0_real_input_status_freshness_audit_validation_report.json"

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
    status_rows = load_jsonl(STATUS)
    status_validation = load_json(STATUS_VALIDATION)
    audit_rows = load_jsonl(AUDIT)
    report = load_json(REPORT)
    failures: list[dict[str, Any]] = []
    expected_rows = len(status_rows) + 1
    lane_rows = audit_rows[:-1] if audit_rows else []
    summary = audit_rows[-1] if audit_rows else {}

    fail_if(status_validation.get("success") is not True, failures, "p678_validation_success", status_validation.get("success"), True)
    fail_if(len(audit_rows) != expected_rows, failures, "audit_rows_exact", len(audit_rows), expected_rows)
    fail_if(len(lane_rows) != len(status_rows), failures, "lane_rows_exact", len(lane_rows), len(status_rows))
    fail_if(summary.get("lane") != "summary", failures, "summary_row_present", summary.get("lane"), "summary")
    for index, row in enumerate(lane_rows, start=1):
        fail_if(row.get("freshness_audit_status") != "current_source_bound", failures, "current_source_bound", {"row": index, "value": row.get("freshness_audit_status")}, "current_source_bound")
        fail_if(row.get("stale_or_missing_source") is not False, failures, "stale_or_missing_source_false", {"row": index, "value": row.get("stale_or_missing_source")}, False)
        for field in ("audit_id", "lane", "source_status_id", "formal_target_file", "validator_report", "source_snapshot", "blocker", "policy"):
            fail_if(row.get(field) in (None, "", []), failures, f"row_{field}_present", {"row": index, "value": row.get(field)}, "present")
        for field in FALSE_FIELDS:
            fail_if(row.get(field) is not False, failures, f"row_{field}_false", {"row": index, "value": row.get(field)}, False)

    fail_if(summary.get("freshness_audit_status") != "blocked_source_bound_audit", failures, "summary_blocked_source_bound", summary.get("freshness_audit_status"), "blocked_source_bound_audit")
    fail_if(summary.get("stale_rows") != 0, failures, "summary_stale_zero", summary.get("stale_rows"), 0)
    fail_if(summary.get("source_missing_rows") != 0, failures, "summary_missing_zero", summary.get("source_missing_rows"), 0)
    fail_if(report.get("audit_rows") != expected_rows, failures, "report_audit_rows", report.get("audit_rows"), expected_rows)
    fail_if(report.get("freshness_audit_rows") != len(status_rows), failures, "report_freshness_rows", report.get("freshness_audit_rows"), len(status_rows))
    fail_if(report.get("stale_rows") != 0, failures, "report_stale_zero", report.get("stale_rows"), 0)
    fail_if(report.get("source_missing_rows") != 0, failures, "report_missing_zero", report.get("source_missing_rows"), 0)
    fail_if(report.get("completion_ready_rows") != 0, failures, "report_completion_zero", report.get("completion_ready_rows"), 0)
    fail_if(report.get("p0_unblocked_rows") != 0, failures, "report_unblocked_zero", report.get("p0_unblocked_rows"), 0)
    fail_if(report.get("source_status_validation_success") is not True, failures, "report_source_validation_success", report.get("source_status_validation_success"), True)
    for field in FALSE_FIELDS:
        fail_if(report.get(field) is not False, failures, f"report_{field}_false", report.get(field), False)

    result = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "local_only": True,
        "success": not failures,
        "failure_count": len(failures),
        "failures": failures,
        "audit_rows": len(audit_rows),
        "freshness_audit_rows": len(status_rows),
        "current_source_bound_rows": len(status_rows),
        "stale_rows": 0,
        "source_missing_rows": 0,
        "completion_ready_rows": 0,
        "p0_unblocked_rows": 0,
        "freshness_audit_status": "blocked_source_bound_audit",
        "training_import_allowed": False,
        "safe_for_training_import": False,
        "safe_for_model_claim": False,
        "customer_delivery_ready": False,
        "release_ready": False,
        "production_execution_allowed": False,
        "p0_unblocked": False,
        "completion_ready": False,
        "policy": "Validation only. P679 checks freshness and source binding; it cannot approve or import real inputs.",
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({
        "success": result["success"],
        "audit_rows": len(audit_rows),
        "freshness_audit_rows": len(status_rows),
        "stale_rows": 0,
        "source_missing_rows": 0,
        "failures": len(failures),
        "output": str(OUT),
    }, ensure_ascii=False))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
