#!/usr/bin/env python3
"""Validate the P491 next-unlock operator work ledger gap audit."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
LEDGER_REPORT = AI_ROOT / "reports" / "next_unlock_operator_work_ledger_report.json"
LEDGER = AI_ROOT / "datasets" / "governance" / "next_unlock_operator_work_ledger.jsonl"
LEDGER_VALIDATION = AI_ROOT / "reports" / "next_unlock_operator_work_ledger_validation_report.json"
LEDGER_STATUS = AI_ROOT / "datasets" / "governance" / "next_unlock_operator_work_ledger_status.jsonl"
P490_REPORT = AI_ROOT / "reports" / "p490_next_unlock_action_checklist_gap_audit_report.json"
P490_VALIDATION = AI_ROOT / "reports" / "p490_next_unlock_action_checklist_gap_audit_validation_report.json"
LOCAL_RELEASE = AI_ROOT / "reports" / "local_release_manifest.json"
CLAIM_MATRIX = AI_ROOT / "reports" / "claim_readiness_matrix.json"
AUDIT = AI_ROOT / "datasets" / "governance" / "p491_next_unlock_operator_work_ledger_gap_audit.jsonl"
REPORT = AI_ROOT / "reports" / "p491_next_unlock_operator_work_ledger_gap_audit_report.json"
OUT = AI_ROOT / "reports" / "p491_next_unlock_operator_work_ledger_gap_audit_validation_report.json"


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
    ledger_report = load_json(LEDGER_REPORT)
    ledger_validation = load_json(LEDGER_VALIDATION)
    p490_report = load_json(P490_REPORT)
    p490_validation = load_json(P490_VALIDATION)
    local_release = load_json(LOCAL_RELEASE)
    claim_matrix = load_json(CLAIM_MATRIX)
    ledger_rows = [row for row in load_jsonl(LEDGER) if isinstance(row, dict)]
    status_rows = [row for row in load_jsonl(LEDGER_STATUS) if isinstance(row, dict)]
    audit_rows = load_jsonl(AUDIT)
    report = load_json(REPORT)
    ledger_by_id = {row.get("ledger_id"): row for row in ledger_rows}
    status_by_id = {row.get("ledger_id"): row for row in status_rows}
    expected_rows = len(ledger_rows) + 1
    open_blocked_ledger_rows = sum(1 for row in ledger_rows if row.get("ledger_status") == "operator_work_open_blocked")
    ready_for_local_operator_work_rows = sum(1 for row in ledger_rows if row.get("ready_for_local_operator_work") is True)
    invalid_or_blocked_ledger_rows = sum(1 for row in ledger_rows if row.get("ledger_status") != "operator_work_open_blocked")
    source_completion_ready_items = sum(1 for row in ledger_rows if row.get("completion_ready") is True)
    requires_human_input_items = sum(1 for row in ledger_rows if row.get("requires_human_input") is True)
    local_materials_ready_rows = sum(1 for row in ledger_rows if row.get("local_materials_ready") is True)
    linked_human_backlog_rows = sum(1 for row in ledger_rows if row.get("human_backlog_id"))
    unlinked_human_backlog_rows = sum(1 for row in ledger_rows if not row.get("human_backlog_id"))
    total_backlog_missing_rows = sum(int(row.get("backlog_missing_rows") or 0) for row in ledger_rows)
    validated_ledger_rows = sum(1 for row in status_rows if row.get("validation_status") == "operator_work_ledger_validated_blocked")
    invalid_ledger_rows = sum(1 for row in status_rows if row.get("validation_status") == "operator_work_ledger_invalid")
    failures: list[dict[str, Any]] = []

    fail_if(len(audit_rows) != expected_rows, failures, "audit_rows_expected", len(audit_rows), expected_rows)
    fail_if(report.get("audit_rows") != expected_rows, failures, "report_audit_rows_expected", report.get("audit_rows"), expected_rows)
    fail_if(report.get("ledger_audit_rows") != len(ledger_rows), failures, "ledger_audit_rows_bound", report.get("ledger_audit_rows"), len(ledger_rows))
    fail_if(report.get("summary_audit_rows") != 1, failures, "summary_audit_rows_one", report.get("summary_audit_rows"), 1)
    fail_if(report.get("ledger_rows") != ledger_report.get("ledger_rows"), failures, "ledger_rows_bound", report.get("ledger_rows"), ledger_report.get("ledger_rows"))
    fail_if(report.get("open_blocked_ledger_rows") != open_blocked_ledger_rows, failures, "open_blocked_ledger_rows_bound", report.get("open_blocked_ledger_rows"), open_blocked_ledger_rows)
    fail_if(report.get("ready_for_local_operator_work_rows") != ready_for_local_operator_work_rows, failures, "ready_for_local_operator_work_rows_bound", report.get("ready_for_local_operator_work_rows"), ready_for_local_operator_work_rows)
    fail_if(report.get("invalid_or_blocked_ledger_rows") != invalid_or_blocked_ledger_rows, failures, "invalid_or_blocked_ledger_rows_bound", report.get("invalid_or_blocked_ledger_rows"), invalid_or_blocked_ledger_rows)
    fail_if(report.get("source_completion_ready_items") != source_completion_ready_items, failures, "source_completion_ready_items_bound", report.get("source_completion_ready_items"), source_completion_ready_items)
    fail_if(report.get("requires_human_input_items") != requires_human_input_items, failures, "requires_human_input_items_bound", report.get("requires_human_input_items"), requires_human_input_items)
    fail_if(report.get("local_materials_ready_rows") != local_materials_ready_rows, failures, "local_materials_ready_rows_bound", report.get("local_materials_ready_rows"), local_materials_ready_rows)
    fail_if(report.get("linked_human_backlog_rows") != linked_human_backlog_rows, failures, "linked_human_backlog_rows_bound", report.get("linked_human_backlog_rows"), linked_human_backlog_rows)
    fail_if(report.get("unlinked_human_backlog_rows") != unlinked_human_backlog_rows, failures, "unlinked_human_backlog_rows_bound", report.get("unlinked_human_backlog_rows"), unlinked_human_backlog_rows)
    fail_if(report.get("total_backlog_missing_rows") != total_backlog_missing_rows, failures, "total_backlog_missing_rows_bound", report.get("total_backlog_missing_rows"), total_backlog_missing_rows)
    fail_if(report.get("validated_ledger_rows") != validated_ledger_rows, failures, "validated_ledger_rows_bound", report.get("validated_ledger_rows"), validated_ledger_rows)
    fail_if(report.get("invalid_ledger_rows") != invalid_ledger_rows, failures, "invalid_ledger_rows_bound", report.get("invalid_ledger_rows"), invalid_ledger_rows)
    fail_if(report.get("p490_open_blocked_checklist_rows") != p490_report.get("open_blocked_checklist_rows"), failures, "p490_open_blocked_checklist_rows_bound", report.get("p490_open_blocked_checklist_rows"), p490_report.get("open_blocked_checklist_rows"))
    fail_if(report.get("p490_validation_success") is not True, failures, "p490_validation_success_true", report.get("p490_validation_success"), True)
    fail_if(p490_validation.get("success") is not True, failures, "source_p490_validation_success_true", p490_validation.get("success"), True)
    fail_if(report.get("local_release_ready") is not False, failures, "local_release_ready_false", report.get("local_release_ready"), False)
    fail_if(local_release.get("release_ready") is not False, failures, "source_local_release_ready_false", local_release.get("release_ready"), False)
    fail_if(report.get("claims_blocked") != claim_matrix.get("claims_blocked"), failures, "claims_blocked_bound", report.get("claims_blocked"), claim_matrix.get("claims_blocked"))
    fail_if(ledger_report.get("online_deployment") is not False, failures, "source_online_deployment_false", ledger_report.get("online_deployment"), False)
    fail_if(ledger_report.get("ledger_rows") != len(ledger_rows), failures, "source_ledger_rows_bound", ledger_report.get("ledger_rows"), len(ledger_rows))
    fail_if(ledger_report.get("open_blocked_ledger_rows") != len(ledger_rows), failures, "source_all_ledger_rows_open_blocked", ledger_report.get("open_blocked_ledger_rows"), len(ledger_rows))
    fail_if(ledger_report.get("invalid_or_blocked_ledger_rows") != 0, failures, "source_invalid_or_blocked_ledger_rows_zero", ledger_report.get("invalid_or_blocked_ledger_rows"), 0)
    fail_if(ledger_report.get("ready_for_local_operator_work_rows") != len(ledger_rows), failures, "source_ready_for_local_operator_work_rows_bound", ledger_report.get("ready_for_local_operator_work_rows"), len(ledger_rows))
    fail_if(ledger_report.get("completion_ready_items") != 0, failures, "source_completion_ready_items_zero", ledger_report.get("completion_ready_items"), 0)
    fail_if(ledger_report.get("requires_human_input_items") != len(ledger_rows), failures, "source_requires_human_input_items_bound", ledger_report.get("requires_human_input_items"), len(ledger_rows))
    fail_if(ledger_report.get("linked_human_backlog_rows") != linked_human_backlog_rows, failures, "source_linked_human_backlog_rows_bound", ledger_report.get("linked_human_backlog_rows"), linked_human_backlog_rows)
    fail_if(ledger_report.get("unlinked_human_backlog_rows") != unlinked_human_backlog_rows, failures, "source_unlinked_human_backlog_rows_bound", ledger_report.get("unlinked_human_backlog_rows"), unlinked_human_backlog_rows)
    fail_if(ledger_validation.get("validated_ledger_rows") != len(ledger_rows), failures, "source_validated_ledger_rows_bound", ledger_validation.get("validated_ledger_rows"), len(ledger_rows))
    fail_if(ledger_validation.get("invalid_ledger_rows") != 0, failures, "source_invalid_ledger_rows_zero", ledger_validation.get("invalid_ledger_rows"), 0)
    fail_if(ledger_validation.get("completion_ready_items") != 0, failures, "source_validation_completion_ready_items_zero", ledger_validation.get("completion_ready_items"), 0)

    seen_ledgers: list[Any] = []
    seen_types: list[Any] = []
    for idx, row in enumerate(audit_rows):
        gap_type = row.get("gap_type")
        seen_types.append(gap_type)
        fail_if(gap_type not in {"next_unlock_operator_work_ledger_gap", "next_unlock_operator_work_ledger_summary_gap"}, failures, "gap_type_allowed", {"index": idx, "observed": gap_type}, "allowed P491 gap type")
        for field in ("training_import_allowed", "safe_for_training_import", "safe_for_model_claim", "customer_delivery_ready", "release_ready", "production_execution_allowed", "completion_ready"):
            fail_if(row.get(field) is not False, failures, f"row_{field}_false", {"index": idx, "observed": row.get(field)}, False)
        if gap_type == "next_unlock_operator_work_ledger_gap":
            ledger_id = row.get("ledger_id")
            seen_ledgers.append(ledger_id)
            source = ledger_by_id.get(ledger_id, {})
            status = status_by_id.get(ledger_id, {})
            fail_if(ledger_id not in ledger_by_id, failures, "ledger_known", {"index": idx, "observed": ledger_id}, sorted(ledger_by_id))
            fail_if(row.get("action_id") != source.get("action_id"), failures, "ledger_action_id_bound", {"index": idx, "observed": row.get("action_id")}, source.get("action_id"))
            fail_if(row.get("checklist_id") != source.get("checklist_id"), failures, "ledger_checklist_id_bound", {"index": idx, "observed": row.get("checklist_id")}, source.get("checklist_id"))
            fail_if(row.get("lane_id") != source.get("lane_id"), failures, "ledger_lane_id_bound", {"index": idx, "observed": row.get("lane_id")}, source.get("lane_id"))
            fail_if(row.get("workstream") != source.get("workstream"), failures, "ledger_workstream_bound", {"index": idx, "observed": row.get("workstream")}, source.get("workstream"))
            fail_if(row.get("source_ledger_status") != source.get("ledger_status"), failures, "ledger_status_bound", {"index": idx, "observed": row.get("source_ledger_status")}, source.get("ledger_status"))
            fail_if(row.get("validation_status") != status.get("validation_status"), failures, "ledger_validation_status_bound", {"index": idx, "observed": row.get("validation_status")}, status.get("validation_status"))
            fail_if(row.get("ready_for_local_operator_work") != source.get("ready_for_local_operator_work"), failures, "ledger_ready_for_local_operator_work_bound", {"index": idx, "observed": row.get("ready_for_local_operator_work")}, source.get("ready_for_local_operator_work"))
            fail_if(row.get("local_materials_ready") != source.get("local_materials_ready"), failures, "ledger_local_materials_ready_bound", {"index": idx, "observed": row.get("local_materials_ready")}, source.get("local_materials_ready"))
            fail_if(row.get("requires_human_input") != source.get("requires_human_input"), failures, "ledger_requires_human_input_bound", {"index": idx, "observed": row.get("requires_human_input")}, source.get("requires_human_input"))
            fail_if(row.get("source_completion_ready") != source.get("completion_ready"), failures, "ledger_completion_ready_bound", {"index": idx, "observed": row.get("source_completion_ready")}, source.get("completion_ready"))
            fail_if(source.get("ledger_status") != "operator_work_open_blocked", failures, "source_ledger_open_blocked", {"index": idx, "observed": source.get("ledger_status")}, "operator_work_open_blocked")
            fail_if(status.get("validation_status") != "operator_work_ledger_validated_blocked", failures, "source_ledger_validated_blocked", {"index": idx, "observed": status.get("validation_status")}, "operator_work_ledger_validated_blocked")
        if gap_type == "next_unlock_operator_work_ledger_summary_gap":
            fail_if(row.get("ledger_rows") != ledger_report.get("ledger_rows"), failures, "summary_ledger_rows_bound", row.get("ledger_rows"), ledger_report.get("ledger_rows"))
            fail_if(row.get("open_blocked_ledger_rows") != open_blocked_ledger_rows, failures, "summary_open_blocked_ledger_rows_bound", row.get("open_blocked_ledger_rows"), open_blocked_ledger_rows)
            fail_if(row.get("source_completion_ready_items") != 0, failures, "summary_source_completion_ready_items_zero", row.get("source_completion_ready_items"), 0)
            fail_if(row.get("requires_human_input_items") != requires_human_input_items, failures, "summary_requires_human_input_items_bound", row.get("requires_human_input_items"), requires_human_input_items)

    fail_if(sorted(seen_ledgers) != sorted(ledger_by_id), failures, "ledgers_exactly_covered", sorted(seen_ledgers), sorted(ledger_by_id))
    fail_if(seen_types.count("next_unlock_operator_work_ledger_gap") != len(ledger_rows), failures, "ledger_gap_type_count", seen_types.count("next_unlock_operator_work_ledger_gap"), len(ledger_rows))
    fail_if(seen_types.count("next_unlock_operator_work_ledger_summary_gap") != 1, failures, "summary_type_count", seen_types.count("next_unlock_operator_work_ledger_summary_gap"), 1)
    for field in ("training_import_allowed", "safe_for_training_import", "safe_for_model_claim", "customer_delivery_ready", "release_ready", "production_execution_allowed"):
        fail_if(report.get(field) is not False, failures, f"report_{field}_false", report.get(field), False)

    result = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "local_only": True,
        "success": not failures,
        "audit_rows": len(audit_rows),
        "ledger_audit_rows": len(ledger_rows),
        "open_blocked_ledger_rows": open_blocked_ledger_rows,
        "source_completion_ready_items": source_completion_ready_items,
        "requires_human_input_items": requires_human_input_items,
        "linked_human_backlog_rows": linked_human_backlog_rows,
        "unlinked_human_backlog_rows": unlinked_human_backlog_rows,
        "failures": failures,
        "training_import_allowed": False,
        "safe_for_training_import": False,
        "safe_for_model_claim": False,
        "customer_delivery_ready": False,
        "release_ready": False,
        "production_execution_allowed": False,
        "policy": "Validation only. Operator work ledger gaps do not authorize training, claims, delivery, release, ordering, deployment, sync, restart, or production execution.",
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "success": result["success"],
        "audit_rows": result["audit_rows"],
        "ledger_audit_rows": result["ledger_audit_rows"],
        "open_blocked_ledger_rows": result["open_blocked_ledger_rows"],
        "failures": len(failures),
        "output": str(OUT),
    }, ensure_ascii=False))
    return 0 if result["success"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
