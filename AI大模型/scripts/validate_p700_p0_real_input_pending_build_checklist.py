#!/usr/bin/env python3
"""Validate the P700 fail-closed pending-build checklist."""
from __future__ import annotations
import json
from datetime import datetime, timezone
from pathlib import Path
from build_p699_p0_real_input_formal_decision_readiness_status_board import load_json, load_jsonl

AI_ROOT = Path(__file__).resolve().parents[1]
BOARD = AI_ROOT / "datasets/governance/p700_p0_real_input_pending_build_checklist.jsonl"
REPORT = AI_ROOT / "reports/p700_p0_real_input_pending_build_checklist_report.json"
OUT = AI_ROOT / "reports/p700_p0_real_input_pending_build_checklist_validation_report.json"
FALSE_FIELDS = ("pending_build_started", "pending_build_completed", "real_input_received", "evidence_received", "formal_decision_written", "formal_decision_ready", "training_import_allowed", "safe_for_model_claim", "customer_delivery_ready", "release_ready", "production_execution_allowed", "p0_unblocked", "p0_completion_ready")

def main() -> int:
    rows = load_jsonl(BOARD); report = load_json(REPORT); failures = []
    lanes, summary = rows[:-1], rows[-1] if rows else {}
    def fail(check, condition, observed):
        if condition: failures.append({"check": check, "observed": observed, "expected": "valid"})
    fail("lane_count", len(lanes) != 5, len(lanes)); fail("summary_lane", summary.get("lane") != "summary", summary.get("lane"))
    for key, expected in (("audit_rows", 6), ("pending_build_checklist_rows", 5), ("open_pending_build_rows", 5), ("empty_pending_build_rows", 5), ("blocked_pending_build_rows", 5), ("formal_intake_dry_run_executed_rows", 0), ("formal_intake_dry_run_passed_rows", 0)):
        fail(f"report_{key}", report.get(key) != expected, report.get(key))
    fail("report_status", report.get("pending_build_status") != "pending_open_empty_blocked", report.get("pending_build_status"))
    orders = [r.get("pending_build_checklist_order") for r in lanes]; fail("order", orders != [1,2,3,4,5], orders)
    ids = [r.get("pending_build_checklist_id") for r in lanes]; fail("unique_ids", len(ids) != len(set(ids)), ids)
    for i, row in enumerate(lanes, 1):
        for field, expected in (("pending_build_status", "pending_open_empty_blocked"), ("pending_build_open", True), ("pending_build_empty", True), ("pending_build_blocked", True)):
            fail(f"row_{i}_{field}", row.get(field) != expected, row.get(field))
        for field in ("pending_build_item", "blocker_reason", "next_unblocking_evidence", "completion_condition", "operator_action", "policy"):
            fail(f"row_{i}_{field}_present", not row.get(field), row.get(field))
        for field in FALSE_FIELDS: fail(f"row_{i}_{field}", row.get(field) is not False, row.get(field))
    for field in FALSE_FIELDS:
        fail(f"report_{field}", report.get(field) is not False or report.get(f"{field}_rows") != 0, {"value": report.get(field), "rows": report.get(f"{field}_rows")})
    result = {"created_at": datetime.now(timezone.utc).isoformat(), "manifest_id": "P700", "local_only": True, "success": not failures, "failure_count": len(failures), "failures": failures, "audit_rows": len(rows), "pending_build_checklist_rows": len(lanes), "open_pending_build_rows": len(lanes), "empty_pending_build_rows": len(lanes), "blocked_pending_build_rows": len(lanes), "formal_intake_dry_run_executed_rows": 0, "formal_intake_dry_run_passed_rows": 0, "pending_build_ready": False, "pending_build_ready_rows": 0, "policy": "Validation only; P700 remains pending and fail-closed."}
    result.update({field: False for field in FALSE_FIELDS}); result.update({f"{field}_rows": 0 for field in FALSE_FIELDS})
    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"success": result["success"], "pending_build_checklist_rows": len(lanes), "pending_build_ready_rows": 0, "failures": len(failures), "output": str(OUT)}, ensure_ascii=False))
    return 0 if not failures else 1

if __name__ == "__main__": raise SystemExit(main())
