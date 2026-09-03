#!/usr/bin/env python3
"""Validate the P688 P0 real-input closeout blocker ledger."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
SOURCE_JSONL = AI_ROOT / "datasets" / "governance" / "p687_p0_real_input_closeout_readiness_gate.jsonl"
SOURCE_VALIDATION = AI_ROOT / "reports" / "p687_p0_real_input_closeout_readiness_gate_validation_report.json"
LEDGER = AI_ROOT / "datasets" / "governance" / "p688_p0_real_input_closeout_blocker_ledger.jsonl"
REPORT = AI_ROOT / "reports" / "p688_p0_real_input_closeout_blocker_ledger_report.json"
OUT = AI_ROOT / "reports" / "p688_p0_real_input_closeout_blocker_ledger_validation_report.json"

FALSE_FIELDS = (
    "queue_dequeued", "operator_dispatch_sent", "operator_acknowledged",
    "external_input_acknowledged", "receive_preflight_executed",
    "response_payload_present", "response_received", "response_validated",
    "real_input_received", "evidence_payload_present", "evidence_quarantined",
    "evidence_released", "evidence_promoted_to_decision", "decision_route_executed",
    "routed_to_formal_review", "formal_intake_dry_run_executed",
    "formal_intake_dry_run_passed", "formal_validator_passed",
    "reviewed_decision_written", "formal_intake_written", "runtime_receipt_written",
    "training_label_written", "blocker_resolved", "closeout_ready",
    "completion_ready_observed", "completion_ready", "p0_unblocked",
    "training_import_allowed", "safe_for_training_import", "safe_for_model_claim",
    "customer_delivery_ready", "release_ready", "production_execution_allowed",
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
    source_validation = load_json(SOURCE_VALIDATION)
    source_rows = [row for row in load_jsonl(SOURCE_JSONL) if row.get("lane") != "summary"]
    rows = load_jsonl(LEDGER)
    report = load_json(REPORT)
    failures: list[dict[str, Any]] = []
    lane_rows = rows[:-1] if rows else []
    summary = rows[-1] if rows else {}

    fail_if(source_validation.get("success") is not True, failures, "p687_validation_success", source_validation.get("success"), True)
    fail_if(len(source_rows) != 5, failures, "source_closeout_gate_rows_exact", len(source_rows), 5)
    fail_if(len(lane_rows) != 5, failures, "ledger_lane_rows_exact", len(lane_rows), 5)
    fail_if(summary.get("lane") != "summary", failures, "summary_row_present", summary.get("lane"), "summary")
    for field, expected in (
        ("audit_rows", 6), ("blocker_ledger_rows", 5),
        ("open_blocker_ledger_rows", 5), ("empty_blocker_ledger_rows", 5),
        ("blocked_blocker_ledger_rows", 5),
    ):
        fail_if(report.get(field) != expected, failures, f"report_{field}", report.get(field), expected)
    fail_if(report.get("blocker_ledger_status") != "open_empty_closeout_blocker", failures, "report_status", report.get("blocker_ledger_status"), "open_empty_closeout_blocker")
    for field in FALSE_FIELDS:
        fail_if(report.get(field) is not False, failures, f"report_{field}_false", report.get(field), False)
        fail_if(report.get(f"{field}_rows") != 0, failures, f"report_{field}_rows_zero", report.get(f"{field}_rows"), 0)

    source_ids = {row.get("closeout_gate_id") for row in source_rows}
    observed_source_ids = {row.get("source_closeout_gate_id") for row in lane_rows}
    fail_if(observed_source_ids != source_ids, failures, "source_closeout_gate_ids_covered", observed_source_ids, source_ids)
    ids = [row.get("blocker_ledger_id") for row in lane_rows]
    fail_if(len(ids) != len(set(ids)), failures, "blocker_ledger_ids_unique", ids, "unique")
    orders = [row.get("blocker_ledger_order") for row in lane_rows]
    fail_if(orders != [1, 2, 3, 4, 5], failures, "blocker_ledger_order", orders, [1, 2, 3, 4, 5])
    for index, row in enumerate(lane_rows, start=1):
        fail_if(row.get("blocker_ledger_status") != "open_empty_closeout_blocker", failures, f"row_{index}_status", row.get("blocker_ledger_status"), "open_empty_closeout_blocker")
        for field in ("blocker_ledger_open", "blocker_ledger_empty", "blocker_ledger_blocked"):
            fail_if(row.get(field) is not True, failures, f"row_{index}_{field}", row.get(field), True)
        for field in (
            "blocker_ledger_id", "lane", "source_closeout_gate_id", "formal_target_file",
            "blocker_reason", "next_unblocking_evidence", "validator_command", "operator_action",
            "completion_condition", "policy",
        ):
            fail_if(row.get(field) in (None, "", []), failures, f"row_{index}_{field}_present", row.get(field), "present")
        for field in FALSE_FIELDS:
            fail_if(row.get(field) is not False, failures, f"row_{index}_{field}_false", row.get(field), False)

    fail_if(summary.get("blocker_ledger_rows") != 5, failures, "summary_ledger_rows", summary.get("blocker_ledger_rows"), 5)
    fail_if(summary.get("open_blocker_ledger_rows") != 5, failures, "summary_open_rows", summary.get("open_blocker_ledger_rows"), 5)
    fail_if(summary.get("empty_blocker_ledger_rows") != 5, failures, "summary_empty_rows", summary.get("empty_blocker_ledger_rows"), 5)
    fail_if(summary.get("blocked_blocker_ledger_rows") != 5, failures, "summary_blocked_rows", summary.get("blocked_blocker_ledger_rows"), 5)
    for field in FALSE_FIELDS:
        fail_if(summary.get(field) is not False, failures, f"summary_{field}_false", summary.get(field), False)
        fail_if(summary.get(f"{field}_rows") != 0, failures, f"summary_{field}_rows_zero", summary.get(f"{field}_rows"), 0)

    result = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "local_only": True,
        "success": not failures,
        "failure_count": len(failures),
        "failures": failures,
        "manifest_id": "P688",
        "audit_rows": len(rows),
        "blocker_ledger_rows": len(lane_rows),
        "open_blocker_ledger_rows": sum(row.get("blocker_ledger_open") is True for row in lane_rows),
        "empty_blocker_ledger_rows": sum(row.get("blocker_ledger_empty") is True for row in lane_rows),
        "blocked_blocker_ledger_rows": sum(row.get("blocker_ledger_blocked") is True for row in lane_rows),
        "policy": "Validation only. P688 confirms closeout blockers remain open, empty, and fail-closed.",
    }
    for field in FALSE_FIELDS:
        result[f"{field}_rows"] = sum(row.get(field) is True for row in lane_rows)
        result[field] = False
    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({
        "success": result["success"],
        "blocker_ledger_rows": result["blocker_ledger_rows"],
        "open_blocker_ledger_rows": result["open_blocker_ledger_rows"],
        "blocker_resolved_rows": result["blocker_resolved_rows"],
        "closeout_ready_rows": result["closeout_ready_rows"],
        "completion_ready_observed_rows": result["completion_ready_observed_rows"],
        "response_received_rows": result["response_received_rows"],
        "real_input_received_rows": result["real_input_received_rows"],
        "failures": result["failure_count"],
        "output": str(OUT),
    }, ensure_ascii=False))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
