#!/usr/bin/env python3
"""Validate the P492 next-unlock operator work receipt gap audit."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
RECEIPT_REPORT = AI_ROOT / "reports" / "next_unlock_operator_work_receipt_report.json"
RECEIPTS = AI_ROOT / "datasets" / "governance" / "next_unlock_operator_work_receipts.jsonl"
RECEIPT_VALIDATION = AI_ROOT / "reports" / "next_unlock_operator_work_receipt_validation_report.json"
RECEIPT_STATUS = AI_ROOT / "datasets" / "governance" / "next_unlock_operator_work_receipt_status.jsonl"
P491_REPORT = AI_ROOT / "reports" / "p491_next_unlock_operator_work_ledger_gap_audit_report.json"
P491_VALIDATION = AI_ROOT / "reports" / "p491_next_unlock_operator_work_ledger_gap_audit_validation_report.json"
LOCAL_RELEASE = AI_ROOT / "reports" / "local_release_manifest.json"
CLAIM_MATRIX = AI_ROOT / "reports" / "claim_readiness_matrix.json"
AUDIT = AI_ROOT / "datasets" / "governance" / "p492_next_unlock_operator_work_receipt_gap_audit.jsonl"
REPORT = AI_ROOT / "reports" / "p492_next_unlock_operator_work_receipt_gap_audit_report.json"
OUT = AI_ROOT / "reports" / "p492_next_unlock_operator_work_receipt_gap_audit_validation_report.json"


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
    receipt_report = load_json(RECEIPT_REPORT)
    receipt_validation = load_json(RECEIPT_VALIDATION)
    p491_report = load_json(P491_REPORT)
    p491_validation = load_json(P491_VALIDATION)
    local_release = load_json(LOCAL_RELEASE)
    claim_matrix = load_json(CLAIM_MATRIX)
    receipt_rows = [row for row in load_jsonl(RECEIPTS) if isinstance(row, dict)]
    status_rows = [row for row in load_jsonl(RECEIPT_STATUS) if isinstance(row, dict)]
    audit_rows = load_jsonl(AUDIT)
    report = load_json(REPORT)
    receipt_by_id = {row.get("receipt_id"): row for row in receipt_rows}
    status_by_id = {row.get("receipt_id"): row for row in status_rows}
    expected_rows = len(receipt_rows) + 1
    open_blocked_receipt_rows = sum(1 for row in receipt_rows if row.get("receipt_status") == "receipt_open_blocked")
    invalid_or_blocked_receipt_rows = sum(1 for row in receipt_rows if row.get("receipt_status") != "receipt_open_blocked")
    source_completion_ready_items = sum(1 for row in receipt_rows if row.get("completion_ready") is True)
    requires_human_input_items = sum(1 for row in receipt_rows if row.get("requires_human_input") is True)
    decision_input_present_rows = sum(1 for row in receipt_rows if row.get("decision_input"))
    decision_input_existing_rows = sum(1 for row in receipt_rows if row.get("decision_input_exists") is True)
    source_target_rows_met_items = sum(1 for row in receipt_rows if row.get("target_rows_met") is True)
    observed_decision_input_rows = sum(int(row.get("decision_input_rows") or 0) for row in receipt_rows)
    validated_receipt_rows = sum(1 for row in status_rows if row.get("validation_status") == "operator_work_receipt_validated_blocked")
    invalid_receipt_rows = sum(1 for row in status_rows if row.get("validation_status") == "operator_work_receipt_invalid")
    failures: list[dict[str, Any]] = []

    fail_if(len(audit_rows) != expected_rows, failures, "audit_rows_expected", len(audit_rows), expected_rows)
    fail_if(report.get("audit_rows") != expected_rows, failures, "report_audit_rows_expected", report.get("audit_rows"), expected_rows)
    fail_if(report.get("receipt_audit_rows") != len(receipt_rows), failures, "receipt_audit_rows_bound", report.get("receipt_audit_rows"), len(receipt_rows))
    fail_if(report.get("summary_audit_rows") != 1, failures, "summary_audit_rows_one", report.get("summary_audit_rows"), 1)
    fail_if(report.get("receipt_rows") != receipt_report.get("receipt_rows"), failures, "receipt_rows_bound", report.get("receipt_rows"), receipt_report.get("receipt_rows"))
    fail_if(report.get("open_blocked_receipt_rows") != open_blocked_receipt_rows, failures, "open_blocked_receipt_rows_bound", report.get("open_blocked_receipt_rows"), open_blocked_receipt_rows)
    fail_if(report.get("invalid_or_blocked_receipt_rows") != invalid_or_blocked_receipt_rows, failures, "invalid_or_blocked_receipt_rows_bound", report.get("invalid_or_blocked_receipt_rows"), invalid_or_blocked_receipt_rows)
    fail_if(report.get("source_completion_ready_items") != source_completion_ready_items, failures, "source_completion_ready_items_bound", report.get("source_completion_ready_items"), source_completion_ready_items)
    fail_if(report.get("requires_human_input_items") != requires_human_input_items, failures, "requires_human_input_items_bound", report.get("requires_human_input_items"), requires_human_input_items)
    fail_if(report.get("decision_input_present_rows") != decision_input_present_rows, failures, "decision_input_present_rows_bound", report.get("decision_input_present_rows"), decision_input_present_rows)
    fail_if(report.get("decision_input_existing_rows") != decision_input_existing_rows, failures, "decision_input_existing_rows_bound", report.get("decision_input_existing_rows"), decision_input_existing_rows)
    fail_if(report.get("source_target_rows_met_items") != source_target_rows_met_items, failures, "source_target_rows_met_items_bound", report.get("source_target_rows_met_items"), source_target_rows_met_items)
    fail_if(report.get("observed_decision_input_rows") != observed_decision_input_rows, failures, "observed_decision_input_rows_bound", report.get("observed_decision_input_rows"), observed_decision_input_rows)
    fail_if(report.get("validated_receipt_rows") != validated_receipt_rows, failures, "validated_receipt_rows_bound", report.get("validated_receipt_rows"), validated_receipt_rows)
    fail_if(report.get("invalid_receipt_rows") != invalid_receipt_rows, failures, "invalid_receipt_rows_bound", report.get("invalid_receipt_rows"), invalid_receipt_rows)
    fail_if(report.get("target_rows_met_completion_ready_items") != 0, failures, "target_rows_met_completion_ready_items_zero", report.get("target_rows_met_completion_ready_items"), 0)
    fail_if(report.get("p491_open_blocked_ledger_rows") != p491_report.get("open_blocked_ledger_rows"), failures, "p491_open_blocked_ledger_rows_bound", report.get("p491_open_blocked_ledger_rows"), p491_report.get("open_blocked_ledger_rows"))
    fail_if(report.get("p491_validation_success") is not True, failures, "p491_validation_success_true", report.get("p491_validation_success"), True)
    fail_if(p491_validation.get("success") is not True, failures, "source_p491_validation_success_true", p491_validation.get("success"), True)
    fail_if(report.get("local_release_ready") is not False, failures, "local_release_ready_false", report.get("local_release_ready"), False)
    fail_if(local_release.get("release_ready") is not False, failures, "source_local_release_ready_false", local_release.get("release_ready"), False)
    fail_if(report.get("claims_blocked") != claim_matrix.get("claims_blocked"), failures, "claims_blocked_bound", report.get("claims_blocked"), claim_matrix.get("claims_blocked"))
    fail_if(receipt_report.get("online_deployment") is not False, failures, "source_online_deployment_false", receipt_report.get("online_deployment"), False)
    fail_if(receipt_report.get("receipt_rows") != len(receipt_rows), failures, "source_receipt_rows_bound", receipt_report.get("receipt_rows"), len(receipt_rows))
    fail_if(receipt_report.get("open_blocked_receipt_rows") != len(receipt_rows), failures, "source_all_receipt_rows_open_blocked", receipt_report.get("open_blocked_receipt_rows"), len(receipt_rows))
    fail_if(receipt_report.get("invalid_or_blocked_receipt_rows") != 0, failures, "source_invalid_or_blocked_receipt_rows_zero", receipt_report.get("invalid_or_blocked_receipt_rows"), 0)
    fail_if(receipt_report.get("completion_ready_items") != 0, failures, "source_completion_ready_items_zero", receipt_report.get("completion_ready_items"), 0)
    fail_if(receipt_report.get("requires_human_input_items") != len(receipt_rows), failures, "source_requires_human_input_items_bound", receipt_report.get("requires_human_input_items"), len(receipt_rows))
    fail_if(receipt_report.get("target_rows_met_items") != 0, failures, "source_target_rows_met_items_zero", receipt_report.get("target_rows_met_items"), 0)
    fail_if(receipt_validation.get("validated_receipt_rows") != len(receipt_rows), failures, "source_validated_receipt_rows_bound", receipt_validation.get("validated_receipt_rows"), len(receipt_rows))
    fail_if(receipt_validation.get("invalid_receipt_rows") != 0, failures, "source_invalid_receipt_rows_zero", receipt_validation.get("invalid_receipt_rows"), 0)
    fail_if(receipt_validation.get("completion_ready_items") != 0, failures, "source_validation_completion_ready_items_zero", receipt_validation.get("completion_ready_items"), 0)
    fail_if(receipt_validation.get("target_rows_met_completion_ready_items") != 0, failures, "source_target_rows_met_completion_ready_items_zero", receipt_validation.get("target_rows_met_completion_ready_items"), 0)

    seen_receipts: list[Any] = []
    seen_types: list[Any] = []
    for idx, row in enumerate(audit_rows):
        gap_type = row.get("gap_type")
        seen_types.append(gap_type)
        fail_if(gap_type not in {"next_unlock_operator_work_receipt_gap", "next_unlock_operator_work_receipt_summary_gap"}, failures, "gap_type_allowed", {"index": idx, "observed": gap_type}, "allowed P492 gap type")
        for field in ("training_import_allowed", "safe_for_training_import", "safe_for_model_claim", "customer_delivery_ready", "release_ready", "production_execution_allowed", "completion_ready"):
            fail_if(row.get(field) is not False, failures, f"row_{field}_false", {"index": idx, "observed": row.get(field)}, False)
        if gap_type == "next_unlock_operator_work_receipt_gap":
            receipt_id = row.get("receipt_id")
            seen_receipts.append(receipt_id)
            source = receipt_by_id.get(receipt_id, {})
            status = status_by_id.get(receipt_id, {})
            fail_if(receipt_id not in receipt_by_id, failures, "receipt_known", {"index": idx, "observed": receipt_id}, sorted(receipt_by_id))
            fail_if(row.get("ledger_id") != source.get("ledger_id"), failures, "receipt_ledger_id_bound", {"index": idx, "observed": row.get("ledger_id")}, source.get("ledger_id"))
            fail_if(row.get("action_id") != source.get("action_id"), failures, "receipt_action_id_bound", {"index": idx, "observed": row.get("action_id")}, source.get("action_id"))
            fail_if(row.get("lane_id") != source.get("lane_id"), failures, "receipt_lane_id_bound", {"index": idx, "observed": row.get("lane_id")}, source.get("lane_id"))
            fail_if(row.get("workstream") != source.get("workstream"), failures, "receipt_workstream_bound", {"index": idx, "observed": row.get("workstream")}, source.get("workstream"))
            fail_if(row.get("source_receipt_status") != source.get("receipt_status"), failures, "receipt_status_bound", {"index": idx, "observed": row.get("source_receipt_status")}, source.get("receipt_status"))
            fail_if(row.get("validation_status") != status.get("validation_status"), failures, "receipt_validation_status_bound", {"index": idx, "observed": row.get("validation_status")}, status.get("validation_status"))
            fail_if(row.get("ledger_validation_status") != source.get("ledger_validation_status"), failures, "receipt_ledger_validation_status_bound", {"index": idx, "observed": row.get("ledger_validation_status")}, source.get("ledger_validation_status"))
            fail_if(row.get("source_target_rows_met") != source.get("target_rows_met"), failures, "receipt_target_rows_met_bound", {"index": idx, "observed": row.get("source_target_rows_met")}, source.get("target_rows_met"))
            fail_if(row.get("requires_human_input") != source.get("requires_human_input"), failures, "receipt_requires_human_input_bound", {"index": idx, "observed": row.get("requires_human_input")}, source.get("requires_human_input"))
            fail_if(row.get("source_completion_ready") != source.get("completion_ready"), failures, "receipt_completion_ready_bound", {"index": idx, "observed": row.get("source_completion_ready")}, source.get("completion_ready"))
            fail_if(source.get("receipt_status") != "receipt_open_blocked", failures, "source_receipt_open_blocked", {"index": idx, "observed": source.get("receipt_status")}, "receipt_open_blocked")
            fail_if(status.get("validation_status") != "operator_work_receipt_validated_blocked", failures, "source_receipt_validated_blocked", {"index": idx, "observed": status.get("validation_status")}, "operator_work_receipt_validated_blocked")
        if gap_type == "next_unlock_operator_work_receipt_summary_gap":
            fail_if(row.get("receipt_rows") != receipt_report.get("receipt_rows"), failures, "summary_receipt_rows_bound", row.get("receipt_rows"), receipt_report.get("receipt_rows"))
            fail_if(row.get("open_blocked_receipt_rows") != open_blocked_receipt_rows, failures, "summary_open_blocked_receipt_rows_bound", row.get("open_blocked_receipt_rows"), open_blocked_receipt_rows)
            fail_if(row.get("source_completion_ready_items") != 0, failures, "summary_source_completion_ready_items_zero", row.get("source_completion_ready_items"), 0)
            fail_if(row.get("source_target_rows_met_items") != 0, failures, "summary_source_target_rows_met_items_zero", row.get("source_target_rows_met_items"), 0)

    fail_if(sorted(seen_receipts) != sorted(receipt_by_id), failures, "receipts_exactly_covered", sorted(seen_receipts), sorted(receipt_by_id))
    fail_if(seen_types.count("next_unlock_operator_work_receipt_gap") != len(receipt_rows), failures, "receipt_gap_type_count", seen_types.count("next_unlock_operator_work_receipt_gap"), len(receipt_rows))
    fail_if(seen_types.count("next_unlock_operator_work_receipt_summary_gap") != 1, failures, "summary_type_count", seen_types.count("next_unlock_operator_work_receipt_summary_gap"), 1)
    for field in ("training_import_allowed", "safe_for_training_import", "safe_for_model_claim", "customer_delivery_ready", "release_ready", "production_execution_allowed"):
        fail_if(report.get(field) is not False, failures, f"report_{field}_false", report.get(field), False)

    result = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "local_only": True,
        "success": not failures,
        "audit_rows": len(audit_rows),
        "receipt_audit_rows": len(receipt_rows),
        "open_blocked_receipt_rows": open_blocked_receipt_rows,
        "source_completion_ready_items": source_completion_ready_items,
        "requires_human_input_items": requires_human_input_items,
        "source_target_rows_met_items": source_target_rows_met_items,
        "observed_decision_input_rows": observed_decision_input_rows,
        "failures": failures,
        "training_import_allowed": False,
        "safe_for_training_import": False,
        "safe_for_model_claim": False,
        "customer_delivery_ready": False,
        "release_ready": False,
        "production_execution_allowed": False,
        "policy": "Validation only. Operator work receipt gaps do not authorize training, claims, delivery, release, ordering, deployment, sync, restart, or production execution.",
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "success": result["success"],
        "audit_rows": result["audit_rows"],
        "receipt_audit_rows": result["receipt_audit_rows"],
        "open_blocked_receipt_rows": result["open_blocked_receipt_rows"],
        "failures": len(failures),
        "output": str(OUT),
    }, ensure_ascii=False))
    return 0 if result["success"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
