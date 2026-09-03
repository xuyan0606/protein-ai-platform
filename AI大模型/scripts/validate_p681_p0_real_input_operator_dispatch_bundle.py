#!/usr/bin/env python3
"""Validate the P681 local operator-dispatch bundle."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
P680_VALIDATION = AI_ROOT / "reports" / "p680_p0_real_input_operator_dispatch_readiness_audit_validation_report.json"
BUNDLE = AI_ROOT / "datasets" / "governance" / "p681_p0_real_input_operator_dispatch_bundle.jsonl"
REPORT = AI_ROOT / "reports" / "p681_p0_real_input_operator_dispatch_bundle_report.json"
OUT = AI_ROOT / "reports" / "p681_p0_real_input_operator_dispatch_bundle_validation_report.json"

FALSE_FIELDS = (
    "operator_dispatch_sent",
    "operator_acknowledged",
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
    p680_validation = load_json(P680_VALIDATION)
    rows = load_jsonl(BUNDLE)
    report = load_json(REPORT)
    failures: list[dict[str, Any]] = []
    lane_rows = rows[:-1] if rows else []
    summary = rows[-1] if rows else {}

    fail_if(p680_validation.get("success") is not True, failures, "p680_validation_success", p680_validation.get("success"), True)
    fail_if(len(lane_rows) != 5, failures, "lane_rows_exact", len(lane_rows), 5)
    fail_if(summary.get("lane") != "summary", failures, "summary_row_present", summary.get("lane"), "summary")
    for index, row in enumerate(lane_rows, start=1):
        fail_if(row.get("bundle_order") != index, failures, "bundle_order", {"row": index, "value": row.get("bundle_order")}, index)
        fail_if(row.get("dispatch_ready") is not True, failures, "dispatch_ready", {"row": index, "value": row.get("dispatch_ready")}, True)
        fail_if(row.get("dispatch_bundle_status") != "ready_for_manual_dispatch_blocked", failures, "bundle_status", {"row": index, "value": row.get("dispatch_bundle_status")}, "ready_for_manual_dispatch_blocked")
        for field in ("bundle_id", "lane", "source_audit_id", "source_checklist_id", "formal_target_file", "source_work_file", "template_or_reference_file", "required_fields", "operator_action", "validator_command", "completion_condition", "blocker", "policy"):
            fail_if(row.get(field) in (None, "", []), failures, f"row_{field}_present", {"row": index, "value": row.get(field)}, "present")
        for field in FALSE_FIELDS:
            fail_if(row.get(field) is not False, failures, f"row_{field}_false", {"row": index, "value": row.get(field)}, False)

    fail_if(summary.get("bundle_rows") != 5, failures, "summary_bundle_rows", summary.get("bundle_rows"), 5)
    fail_if(summary.get("manual_dispatch_bundle_ready_rows") != 5, failures, "summary_ready_rows", summary.get("manual_dispatch_bundle_ready_rows"), 5)
    fail_if(summary.get("dispatch_bundle_status") != "ready_for_manual_dispatch_blocked", failures, "summary_bundle_status", summary.get("dispatch_bundle_status"), "ready_for_manual_dispatch_blocked")
    for field in FALSE_FIELDS:
        fail_if(summary.get(field) is not False, failures, f"summary_{field}_false", summary.get(field), False)

    fail_if(report.get("audit_rows") != 6, failures, "report_audit_rows", report.get("audit_rows"), 6)
    fail_if(report.get("bundle_rows") != 5, failures, "report_bundle_rows", report.get("bundle_rows"), 5)
    fail_if(report.get("manual_dispatch_bundle_ready_rows") != 5, failures, "report_ready_rows", report.get("manual_dispatch_bundle_ready_rows"), 5)
    fail_if(report.get("dispatch_bundle_status") != "ready_for_manual_dispatch_blocked", failures, "report_bundle_status", report.get("dispatch_bundle_status"), "ready_for_manual_dispatch_blocked")
    for field in FALSE_FIELDS:
        fail_if(report.get(field) is not False, failures, f"report_{field}_false", report.get(field), False)

    result = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "local_only": True,
        "success": not failures,
        "failure_count": len(failures),
        "failures": failures,
        "audit_rows": len(rows),
        "bundle_rows": len(lane_rows),
        "manual_dispatch_bundle_ready_rows": len(lane_rows),
        "dispatch_bundle_status": "ready_for_manual_dispatch_blocked",
        "operator_dispatch_sent_rows": 0,
        "operator_acknowledged_rows": 0,
        "real_input_received_rows": 0,
        "formal_validator_passed_rows": 0,
        "completion_ready_rows": 0,
        "p0_unblocked_rows": 0,
        "operator_dispatch_sent": False,
        "operator_acknowledged": False,
        "real_input_received": False,
        "formal_validator_passed": False,
        "completion_ready": False,
        "p0_unblocked": False,
        "training_import_allowed": False,
        "safe_for_training_import": False,
        "safe_for_model_claim": False,
        "customer_delivery_ready": False,
        "release_ready": False,
        "production_execution_allowed": False,
        "policy": "Validation only. P681 confirms local bundle integrity but cannot send, receive, approve, import, claim, release, or authorize production.",
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({
        "success": result["success"],
        "bundle_rows": result["bundle_rows"],
        "manual_dispatch_bundle_ready_rows": result["manual_dispatch_bundle_ready_rows"],
        "operator_dispatch_sent_rows": 0,
        "operator_acknowledged_rows": 0,
        "failures": result["failure_count"],
        "output": str(OUT),
    }, ensure_ascii=False))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
