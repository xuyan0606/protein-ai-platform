#!/usr/bin/env python3
"""Validate the P680 P0 operator-dispatch readiness audit."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
CHECKLIST = AI_ROOT / "datasets" / "governance" / "p677_p0_real_input_completion_checklist.jsonl"
FRESHNESS_VALIDATION = AI_ROOT / "reports" / "p679_p0_real_input_status_freshness_audit_validation_report.json"
AUDIT = AI_ROOT / "datasets" / "governance" / "p680_p0_real_input_operator_dispatch_readiness_audit.jsonl"
REPORT = AI_ROOT / "reports" / "p680_p0_real_input_operator_dispatch_readiness_audit_report.json"
OUT = AI_ROOT / "reports" / "p680_p0_real_input_operator_dispatch_readiness_audit_validation_report.json"

FALSE_FIELDS = (
    "real_input_received",
    "formal_validator_passed",
    "completion_ready",
    "p0_unblocked",
    "operator_dispatch_sent",
    "operator_acknowledged",
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
    checklist_rows = load_jsonl(CHECKLIST)
    freshness_validation = load_json(FRESHNESS_VALIDATION)
    audit_rows = load_jsonl(AUDIT)
    report = load_json(REPORT)
    failures: list[dict[str, Any]] = []
    expected_rows = len(checklist_rows) + 1
    lane_rows = audit_rows[:-1] if audit_rows else []
    summary = audit_rows[-1] if audit_rows else {}

    fail_if(freshness_validation.get("success") is not True, failures, "p679_validation_success", freshness_validation.get("success"), True)
    fail_if(len(audit_rows) != expected_rows, failures, "audit_rows_exact", len(audit_rows), expected_rows)
    fail_if(len(lane_rows) != len(checklist_rows), failures, "lane_rows_exact", len(lane_rows), len(checklist_rows))
    fail_if(summary.get("lane") != "summary", failures, "summary_row_present", summary.get("lane"), "summary")
    for index, row in enumerate(lane_rows, start=1):
        fail_if(row.get("dispatch_ready") is not True, failures, "dispatch_ready_true", {"row": index, "value": row.get("dispatch_ready")}, True)
        fail_if(row.get("dispatch_contract_complete") is not True, failures, "dispatch_contract_complete_true", {"row": index, "value": row.get("dispatch_contract_complete")}, True)
        fail_if(row.get("freshness_current") is not True, failures, "freshness_current_true", {"row": index, "value": row.get("freshness_current")}, True)
        fail_if(row.get("dispatch_status") != "blocked_operator_input_required", failures, "dispatch_status_blocked", {"row": index, "value": row.get("dispatch_status")}, "blocked_operator_input_required")
        for field in ("audit_id", "lane", "checklist_id", "freshness_audit_id", "formal_target_file", "primary_validator_command", "first_operator_action", "completion_condition", "required_dispatch_contract", "blocker", "policy"):
            fail_if(row.get(field) in (None, "", []), failures, f"row_{field}_present", {"row": index, "value": row.get(field)}, "present")
        for field in FALSE_FIELDS:
            fail_if(row.get(field) is not False, failures, f"row_{field}_false", {"row": index, "value": row.get(field)}, False)

    fail_if(summary.get("dispatch_ready_rows") != len(checklist_rows), failures, "summary_dispatch_ready_rows", summary.get("dispatch_ready_rows"), len(checklist_rows))
    fail_if(summary.get("dispatch_contract_incomplete_rows") != 0, failures, "summary_contract_incomplete_zero", summary.get("dispatch_contract_incomplete_rows"), 0)
    fail_if(summary.get("operator_dispatch_sent_rows") != 0, failures, "summary_dispatch_sent_zero", summary.get("operator_dispatch_sent_rows"), 0)
    fail_if(summary.get("operator_acknowledged_rows") != 0, failures, "summary_ack_zero", summary.get("operator_acknowledged_rows"), 0)
    fail_if(summary.get("dispatch_status") != "blocked_operator_input_required", failures, "summary_dispatch_status", summary.get("dispatch_status"), "blocked_operator_input_required")
    fail_if(report.get("audit_rows") != expected_rows, failures, "report_audit_rows", report.get("audit_rows"), expected_rows)
    fail_if(report.get("dispatch_ready_rows") != len(checklist_rows), failures, "report_dispatch_ready_rows", report.get("dispatch_ready_rows"), len(checklist_rows))
    fail_if(report.get("dispatch_contract_incomplete_rows") != 0, failures, "report_contract_incomplete_zero", report.get("dispatch_contract_incomplete_rows"), 0)
    fail_if(report.get("operator_dispatch_sent_rows") != 0, failures, "report_dispatch_sent_zero", report.get("operator_dispatch_sent_rows"), 0)
    fail_if(report.get("operator_acknowledged_rows") != 0, failures, "report_ack_zero", report.get("operator_acknowledged_rows"), 0)
    fail_if(report.get("source_freshness_validation_success") is not True, failures, "report_freshness_validation_success", report.get("source_freshness_validation_success"), True)
    for field in FALSE_FIELDS:
        fail_if(report.get(field) is not False, failures, f"report_{field}_false", report.get(field), False)

    result = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "local_only": True,
        "success": not failures,
        "failure_count": len(failures),
        "failures": failures,
        "audit_rows": len(audit_rows),
        "dispatch_readiness_rows": len(checklist_rows),
        "dispatch_ready_rows": len(checklist_rows),
        "dispatch_contract_incomplete_rows": 0,
        "operator_dispatch_sent_rows": 0,
        "operator_acknowledged_rows": 0,
        "real_input_received_rows": 0,
        "formal_validator_passed_rows": 0,
        "completion_ready_rows": 0,
        "p0_unblocked_rows": 0,
        "dispatch_status": "blocked_operator_input_required",
        "real_input_received": False,
        "formal_validator_passed": False,
        "completion_ready": False,
        "p0_unblocked": False,
        "operator_dispatch_sent": False,
        "operator_acknowledged": False,
        "training_import_allowed": False,
        "safe_for_training_import": False,
        "safe_for_model_claim": False,
        "customer_delivery_ready": False,
        "release_ready": False,
        "production_execution_allowed": False,
        "policy": "Validation only. P680 confirms packet readiness but cannot send, receive, approve, or import.",
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({
        "success": result["success"],
        "audit_rows": len(audit_rows),
        "dispatch_ready_rows": len(checklist_rows),
        "operator_dispatch_sent_rows": 0,
        "operator_acknowledged_rows": 0,
        "failures": len(failures),
        "output": str(OUT),
    }, ensure_ascii=False))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
