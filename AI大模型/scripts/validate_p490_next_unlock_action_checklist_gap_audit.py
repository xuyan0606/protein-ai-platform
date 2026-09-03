#!/usr/bin/env python3
"""Validate the P490 next-unlock action checklist gap audit."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
CHECKLIST_REPORT = AI_ROOT / "reports" / "next_unlock_action_checklist_report.json"
CHECKLIST = AI_ROOT / "datasets" / "governance" / "next_unlock_action_checklist.jsonl"
CHECKLIST_VALIDATION = AI_ROOT / "reports" / "next_unlock_action_checklist_validation_report.json"
CHECKLIST_STATUS = AI_ROOT / "datasets" / "governance" / "next_unlock_action_checklist_status.jsonl"
P489_REPORT = AI_ROOT / "reports" / "p489_next_unlock_lane_dispatch_gap_audit_report.json"
P489_VALIDATION = AI_ROOT / "reports" / "p489_next_unlock_lane_dispatch_gap_audit_validation_report.json"
LOCAL_RELEASE = AI_ROOT / "reports" / "local_release_manifest.json"
CLAIM_MATRIX = AI_ROOT / "reports" / "claim_readiness_matrix.json"
AUDIT = AI_ROOT / "datasets" / "governance" / "p490_next_unlock_action_checklist_gap_audit.jsonl"
REPORT = AI_ROOT / "reports" / "p490_next_unlock_action_checklist_gap_audit_report.json"
OUT = AI_ROOT / "reports" / "p490_next_unlock_action_checklist_gap_audit_validation_report.json"


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
    checklist_report = load_json(CHECKLIST_REPORT)
    checklist_validation = load_json(CHECKLIST_VALIDATION)
    p489_report = load_json(P489_REPORT)
    p489_validation = load_json(P489_VALIDATION)
    local_release = load_json(LOCAL_RELEASE)
    claim_matrix = load_json(CLAIM_MATRIX)
    checklist_rows = [row for row in load_jsonl(CHECKLIST) if isinstance(row, dict)]
    status_rows = [row for row in load_jsonl(CHECKLIST_STATUS) if isinstance(row, dict)]
    audit_rows = load_jsonl(AUDIT)
    report = load_json(REPORT)
    checklist_by_id = {row.get("checklist_id"): row for row in checklist_rows}
    status_by_id = {row.get("checklist_id"): row for row in status_rows}
    expected_rows = len(checklist_rows) + 1
    open_blocked_checklist_rows = sum(1 for row in checklist_rows if row.get("checklist_status") == "checklist_open_blocked")
    invalid_or_blocked_checklist_rows = sum(1 for row in checklist_rows if row.get("checklist_status") != "checklist_open_blocked")
    ready_for_local_operator_rows = sum(1 for row in checklist_rows if row.get("ready_for_local_operator") is True)
    source_completion_ready_items = sum(1 for row in checklist_rows if row.get("completion_ready") is True)
    requires_human_input_items = sum(1 for row in checklist_rows if row.get("requires_human_input") is True)
    failures: list[dict[str, Any]] = []

    fail_if(len(audit_rows) != expected_rows, failures, "audit_rows_expected", len(audit_rows), expected_rows)
    fail_if(report.get("audit_rows") != expected_rows, failures, "report_audit_rows_expected", report.get("audit_rows"), expected_rows)
    fail_if(report.get("checklist_audit_rows") != len(checklist_rows), failures, "checklist_audit_rows_bound", report.get("checklist_audit_rows"), len(checklist_rows))
    fail_if(report.get("summary_audit_rows") != 1, failures, "summary_audit_rows_one", report.get("summary_audit_rows"), 1)
    fail_if(report.get("checklist_rows") != checklist_report.get("checklist_rows"), failures, "checklist_rows_bound", report.get("checklist_rows"), checklist_report.get("checklist_rows"))
    fail_if(report.get("open_blocked_checklist_rows") != open_blocked_checklist_rows, failures, "open_blocked_checklist_rows_bound", report.get("open_blocked_checklist_rows"), open_blocked_checklist_rows)
    fail_if(report.get("invalid_or_blocked_checklist_rows") != invalid_or_blocked_checklist_rows, failures, "invalid_or_blocked_checklist_rows_bound", report.get("invalid_or_blocked_checklist_rows"), invalid_or_blocked_checklist_rows)
    fail_if(report.get("ready_for_local_operator_rows") != ready_for_local_operator_rows, failures, "ready_for_local_operator_rows_bound", report.get("ready_for_local_operator_rows"), ready_for_local_operator_rows)
    fail_if(report.get("source_completion_ready_items") != source_completion_ready_items, failures, "source_completion_ready_items_bound", report.get("source_completion_ready_items"), source_completion_ready_items)
    fail_if(report.get("requires_human_input_items") != requires_human_input_items, failures, "requires_human_input_items_bound", report.get("requires_human_input_items"), requires_human_input_items)
    fail_if(report.get("p489_dispatch_ready_blocked_packets") != p489_report.get("dispatch_ready_blocked_packets"), failures, "p489_dispatch_ready_blocked_packets_bound", report.get("p489_dispatch_ready_blocked_packets"), p489_report.get("dispatch_ready_blocked_packets"))
    fail_if(report.get("p489_validation_success") is not True, failures, "p489_validation_success_true", report.get("p489_validation_success"), True)
    fail_if(p489_validation.get("success") is not True, failures, "source_p489_validation_success_true", p489_validation.get("success"), True)
    fail_if(report.get("local_release_ready") is not False, failures, "local_release_ready_false", report.get("local_release_ready"), False)
    fail_if(local_release.get("release_ready") is not False, failures, "source_local_release_ready_false", local_release.get("release_ready"), False)
    fail_if(report.get("claims_blocked") != claim_matrix.get("claims_blocked"), failures, "claims_blocked_bound", report.get("claims_blocked"), claim_matrix.get("claims_blocked"))
    fail_if(checklist_report.get("online_deployment") is not False, failures, "source_online_deployment_false", checklist_report.get("online_deployment"), False)
    fail_if(checklist_report.get("checklist_rows") != len(checklist_rows), failures, "source_checklist_rows_bound", checklist_report.get("checklist_rows"), len(checklist_rows))
    fail_if(checklist_report.get("open_blocked_checklist_rows") != len(checklist_rows), failures, "source_all_checklist_rows_open_blocked", checklist_report.get("open_blocked_checklist_rows"), len(checklist_rows))
    fail_if(checklist_report.get("invalid_or_blocked_checklist_rows") != 0, failures, "source_invalid_or_blocked_checklist_rows_zero", checklist_report.get("invalid_or_blocked_checklist_rows"), 0)
    fail_if(checklist_report.get("ready_for_local_operator_rows") != len(checklist_rows), failures, "source_ready_for_local_operator_rows_bound", checklist_report.get("ready_for_local_operator_rows"), len(checklist_rows))
    fail_if(checklist_report.get("completion_ready_items") != 0, failures, "source_completion_ready_items_zero", checklist_report.get("completion_ready_items"), 0)
    fail_if(checklist_report.get("requires_human_input_items") != len(checklist_rows), failures, "source_requires_human_input_items_bound", checklist_report.get("requires_human_input_items"), len(checklist_rows))
    fail_if(checklist_validation.get("validated_checklist_rows") != len(checklist_rows), failures, "source_validated_checklist_rows_bound", checklist_validation.get("validated_checklist_rows"), len(checklist_rows))
    fail_if(checklist_validation.get("invalid_checklist_rows") != 0, failures, "source_invalid_checklist_rows_zero", checklist_validation.get("invalid_checklist_rows"), 0)
    fail_if(checklist_validation.get("completion_ready_items") != 0, failures, "source_validation_completion_ready_items_zero", checklist_validation.get("completion_ready_items"), 0)
    fail_if(checklist_validation.get("requires_human_input_items") != len(checklist_rows), failures, "source_validation_requires_human_input_items_bound", checklist_validation.get("requires_human_input_items"), len(checklist_rows))

    seen_checklists: list[Any] = []
    seen_types: list[Any] = []
    for idx, row in enumerate(audit_rows):
        gap_type = row.get("gap_type")
        seen_types.append(gap_type)
        fail_if(gap_type not in {"next_unlock_action_checklist_gap", "next_unlock_action_checklist_summary_gap"}, failures, "gap_type_allowed", {"index": idx, "observed": gap_type}, "allowed P490 gap type")
        for field in ("training_import_allowed", "safe_for_training_import", "safe_for_model_claim", "customer_delivery_ready", "release_ready", "production_execution_allowed", "completion_ready"):
            fail_if(row.get(field) is not False, failures, f"row_{field}_false", {"index": idx, "observed": row.get(field)}, False)
        if gap_type == "next_unlock_action_checklist_gap":
            checklist_id = row.get("checklist_id")
            seen_checklists.append(checklist_id)
            source = checklist_by_id.get(checklist_id, {})
            status = status_by_id.get(checklist_id, {})
            fail_if(checklist_id not in checklist_by_id, failures, "checklist_known", {"index": idx, "observed": checklist_id}, sorted(checklist_by_id))
            fail_if(row.get("action_id") != source.get("action_id"), failures, "checklist_action_id_bound", {"index": idx, "observed": row.get("action_id")}, source.get("action_id"))
            fail_if(row.get("dispatch_packet_id") != source.get("dispatch_packet_id"), failures, "checklist_dispatch_packet_id_bound", {"index": idx, "observed": row.get("dispatch_packet_id")}, source.get("dispatch_packet_id"))
            fail_if(row.get("lane_id") != source.get("lane_id"), failures, "checklist_lane_id_bound", {"index": idx, "observed": row.get("lane_id")}, source.get("lane_id"))
            fail_if(row.get("source_checklist_status") != source.get("checklist_status"), failures, "checklist_status_bound", {"index": idx, "observed": row.get("source_checklist_status")}, source.get("checklist_status"))
            fail_if(row.get("dispatch_validation_status") != source.get("dispatch_validation_status"), failures, "checklist_dispatch_validation_status_bound", {"index": idx, "observed": row.get("dispatch_validation_status")}, source.get("dispatch_validation_status"))
            fail_if(row.get("launch_status") != source.get("launch_status"), failures, "checklist_launch_status_bound", {"index": idx, "observed": row.get("launch_status")}, source.get("launch_status"))
            fail_if(row.get("ready_for_local_operator") != source.get("ready_for_local_operator"), failures, "checklist_ready_for_local_operator_bound", {"index": idx, "observed": row.get("ready_for_local_operator")}, source.get("ready_for_local_operator"))
            fail_if(row.get("requires_human_input") != source.get("requires_human_input"), failures, "checklist_requires_human_input_bound", {"index": idx, "observed": row.get("requires_human_input")}, source.get("requires_human_input"))
            fail_if(row.get("source_completion_ready") != source.get("completion_ready"), failures, "checklist_completion_ready_bound", {"index": idx, "observed": row.get("source_completion_ready")}, source.get("completion_ready"))
            fail_if(status.get("validation_status") != "checklist_validated_blocked", failures, "source_checklist_validated_blocked", {"index": idx, "observed": status.get("validation_status")}, "checklist_validated_blocked")
        if gap_type == "next_unlock_action_checklist_summary_gap":
            fail_if(row.get("checklist_rows") != checklist_report.get("checklist_rows"), failures, "summary_checklist_rows_bound", row.get("checklist_rows"), checklist_report.get("checklist_rows"))
            fail_if(row.get("open_blocked_checklist_rows") != open_blocked_checklist_rows, failures, "summary_open_blocked_checklist_rows_bound", row.get("open_blocked_checklist_rows"), open_blocked_checklist_rows)
            fail_if(row.get("source_completion_ready_items") != 0, failures, "summary_source_completion_ready_items_zero", row.get("source_completion_ready_items"), 0)
            fail_if(row.get("requires_human_input_items") != requires_human_input_items, failures, "summary_requires_human_input_items_bound", row.get("requires_human_input_items"), requires_human_input_items)

    fail_if(sorted(seen_checklists) != sorted(checklist_by_id), failures, "checklists_exactly_covered", sorted(seen_checklists), sorted(checklist_by_id))
    fail_if(seen_types.count("next_unlock_action_checklist_gap") != len(checklist_rows), failures, "checklist_gap_type_count", seen_types.count("next_unlock_action_checklist_gap"), len(checklist_rows))
    fail_if(seen_types.count("next_unlock_action_checklist_summary_gap") != 1, failures, "summary_type_count", seen_types.count("next_unlock_action_checklist_summary_gap"), 1)
    for field in ("training_import_allowed", "safe_for_training_import", "safe_for_model_claim", "customer_delivery_ready", "release_ready", "production_execution_allowed"):
        fail_if(report.get(field) is not False, failures, f"report_{field}_false", report.get(field), False)

    result = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "local_only": True,
        "success": not failures,
        "audit_rows": len(audit_rows),
        "checklist_audit_rows": len(checklist_rows),
        "open_blocked_checklist_rows": open_blocked_checklist_rows,
        "source_completion_ready_items": source_completion_ready_items,
        "requires_human_input_items": requires_human_input_items,
        "failures": failures,
        "training_import_allowed": False,
        "safe_for_training_import": False,
        "safe_for_model_claim": False,
        "customer_delivery_ready": False,
        "release_ready": False,
        "production_execution_allowed": False,
        "policy": "Validation only. Action checklist gaps do not authorize training, claims, delivery, release, ordering, deployment, sync, restart, or production execution.",
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "success": result["success"],
        "audit_rows": result["audit_rows"],
        "checklist_audit_rows": result["checklist_audit_rows"],
        "open_blocked_checklist_rows": result["open_blocked_checklist_rows"],
        "failures": len(failures),
        "output": str(OUT),
    }, ensure_ascii=False))
    return 0 if result["success"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
