#!/usr/bin/env python3
"""Validate the P484 next-unlock operator navigation gap audit."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
OPERATOR_INDEX = AI_ROOT / "reports" / "next_unlock_operator_index.json"
OPERATOR_INDEX_JSONL = AI_ROOT / "datasets" / "governance" / "next_unlock_operator_index.jsonl"
EXECUTION_VALIDATION = AI_ROOT / "reports" / "next_unlock_execution_validation_report.json"
P483_REPORT = AI_ROOT / "reports" / "p483_next_unlock_execution_gap_audit_report.json"
P483_VALIDATION = AI_ROOT / "reports" / "p483_next_unlock_execution_gap_audit_validation_report.json"
LOCAL_RELEASE = AI_ROOT / "reports" / "local_release_manifest.json"
CLAIM_MATRIX = AI_ROOT / "reports" / "claim_readiness_matrix.json"
AUDIT = AI_ROOT / "datasets" / "governance" / "p484_next_unlock_operator_navigation_gap_audit.jsonl"
REPORT = AI_ROOT / "reports" / "p484_next_unlock_operator_navigation_gap_audit_report.json"
OUT = AI_ROOT / "reports" / "p484_next_unlock_operator_navigation_gap_audit_validation_report.json"


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
    index = load_json(OPERATOR_INDEX)
    execution_validation = load_json(EXECUTION_VALIDATION)
    p483_report = load_json(P483_REPORT)
    p483_validation = load_json(P483_VALIDATION)
    local_release = load_json(LOCAL_RELEASE)
    claim_matrix = load_json(CLAIM_MATRIX)
    index_rows = [row for row in load_jsonl(OPERATOR_INDEX_JSONL) if isinstance(row, dict)]
    audit_rows = load_jsonl(AUDIT)
    report = load_json(REPORT)
    expected_rows = len(index_rows) + 1
    open_items = int(index.get("open_items") or 0)
    source_ready_items = int(index.get("completion_ready_items") or 0)
    index_by_action = {row.get("action_id"): row for row in index_rows}
    failures: list[dict[str, Any]] = []

    fail_if(len(audit_rows) != expected_rows, failures, "audit_rows_expected", len(audit_rows), expected_rows)
    fail_if(report.get("audit_rows") != expected_rows, failures, "report_audit_rows_expected", report.get("audit_rows"), expected_rows)
    fail_if(report.get("operator_navigation_rows") != len(index_rows), failures, "operator_navigation_rows_bound", report.get("operator_navigation_rows"), len(index_rows))
    fail_if(report.get("summary_audit_rows") != 1, failures, "summary_audit_rows_one", report.get("summary_audit_rows"), 1)
    fail_if(report.get("open_item_rows") != open_items, failures, "open_item_rows_bound", report.get("open_item_rows"), open_items)
    fail_if(report.get("source_completion_ready_items") != source_ready_items, failures, "source_completion_ready_items_bound", report.get("source_completion_ready_items"), source_ready_items)
    fail_if(report.get("blocked_gap_rows") != open_items, failures, "blocked_gap_rows_bound", report.get("blocked_gap_rows"), open_items)
    fail_if(report.get("total_actions") != index.get("total_actions"), failures, "total_actions_bound", report.get("total_actions"), index.get("total_actions"))
    fail_if(report.get("started_actions") != index.get("started_actions"), failures, "started_actions_bound", report.get("started_actions"), index.get("started_actions"))
    fail_if(report.get("validation_completion_ready_actions") != index.get("validation_completion_ready_actions"), failures, "validation_completion_ready_actions_bound", report.get("validation_completion_ready_actions"), index.get("validation_completion_ready_actions"))
    fail_if(report.get("validation_blocked_actions") != index.get("validation_blocked_actions"), failures, "validation_blocked_actions_bound", report.get("validation_blocked_actions"), index.get("validation_blocked_actions"))
    fail_if(report.get("missing_operator_open_first") != index.get("missing_operator_open_first"), failures, "missing_operator_open_first_bound", report.get("missing_operator_open_first"), index.get("missing_operator_open_first"))
    fail_if(report.get("missing_decision_inputs") != index.get("missing_decision_inputs"), failures, "missing_decision_inputs_bound", report.get("missing_decision_inputs"), index.get("missing_decision_inputs"))
    fail_if(report.get("missing_templates") != index.get("missing_templates"), failures, "missing_templates_bound", report.get("missing_templates"), index.get("missing_templates"))
    fail_if(report.get("missing_validator_reports") != index.get("missing_validator_reports"), failures, "missing_validator_reports_bound", report.get("missing_validator_reports"), index.get("missing_validator_reports"))
    fail_if(report.get("p483_blocked_gap_rows") != p483_report.get("blocked_gap_rows"), failures, "p483_blocked_gap_rows_bound", report.get("p483_blocked_gap_rows"), p483_report.get("blocked_gap_rows"))
    fail_if(report.get("p483_validation_success") is not True, failures, "p483_validation_success_true", report.get("p483_validation_success"), True)
    fail_if(p483_validation.get("success") is not True, failures, "source_p483_validation_success_true", p483_validation.get("success"), True)
    fail_if(report.get("local_release_ready") is not False, failures, "local_release_ready_false", report.get("local_release_ready"), False)
    fail_if(local_release.get("release_ready") is not False, failures, "source_local_release_ready_false", local_release.get("release_ready"), False)
    fail_if(report.get("claims_blocked") != claim_matrix.get("claims_blocked"), failures, "claims_blocked_bound", report.get("claims_blocked"), claim_matrix.get("claims_blocked"))
    fail_if(index.get("total_actions") != len(index_rows), failures, "source_total_actions_bound", index.get("total_actions"), len(index_rows))
    fail_if(index.get("open_items") != execution_validation.get("blocked_actions"), failures, "source_open_items_match_blocked_actions", index.get("open_items"), execution_validation.get("blocked_actions"))
    fail_if(index.get("completion_ready_items") != execution_validation.get("completion_ready_actions"), failures, "source_ready_items_match_validation", index.get("completion_ready_items"), execution_validation.get("completion_ready_actions"))

    seen_actions: list[Any] = []
    seen_types: list[Any] = []
    for idx, row in enumerate(audit_rows):
        gap_type = row.get("gap_type")
        seen_types.append(gap_type)
        fail_if(gap_type not in {"next_unlock_operator_navigation_gap", "next_unlock_operator_navigation_summary_gap"}, failures, "gap_type_allowed", {"index": idx, "observed": gap_type}, "allowed P484 gap type")
        for field in ("training_import_allowed", "safe_for_training_import", "safe_for_model_claim", "customer_delivery_ready", "release_ready", "production_execution_allowed", "completion_ready"):
            fail_if(row.get(field) is not False, failures, f"row_{field}_false", {"index": idx, "observed": row.get(field)}, False)
        if gap_type == "next_unlock_operator_navigation_gap":
            action_id = row.get("action_id")
            seen_actions.append(action_id)
            source = index_by_action.get(action_id, {})
            fail_if(action_id not in index_by_action, failures, "action_known", {"index": idx, "observed": action_id}, sorted(index_by_action))
            fail_if(row.get("stage_id") != source.get("stage_id"), failures, "action_stage_id_bound", {"index": idx, "observed": row.get("stage_id")}, source.get("stage_id"))
            fail_if(row.get("workstream") != source.get("workstream"), failures, "action_workstream_bound", {"index": idx, "observed": row.get("workstream")}, source.get("workstream"))
            fail_if(row.get("source_status") != source.get("status"), failures, "action_status_bound", {"index": idx, "observed": row.get("source_status")}, source.get("status"))
            fail_if(row.get("source_completion_ready") != (source.get("completion_ready") is True), failures, "action_source_completion_ready_bound", {"index": idx, "observed": row.get("source_completion_ready")}, source.get("completion_ready") is True)
            fail_if(row.get("failed_check_count") != len(source.get("failed_checks") or []), failures, "action_failed_check_count_bound", {"index": idx, "observed": row.get("failed_check_count")}, len(source.get("failed_checks") or []))
            missing_local_path_count = sum(
                1
                for name in ("operator_open_first", "decision_input", "template", "validator_report")
                if source.get(f"{name}_exists") is False and source.get(name)
            )
            fail_if(row.get("missing_local_path_count") != missing_local_path_count, failures, "missing_local_path_count_bound", {"index": idx, "observed": row.get("missing_local_path_count")}, missing_local_path_count)
        if gap_type == "next_unlock_operator_navigation_summary_gap":
            fail_if(row.get("open_item_rows") != open_items, failures, "summary_open_item_rows_bound", row.get("open_item_rows"), open_items)
            fail_if(row.get("source_completion_ready_items") != source_ready_items, failures, "summary_source_completion_ready_items_bound", row.get("source_completion_ready_items"), source_ready_items)
            fail_if(row.get("blocked_gap_rows") != open_items, failures, "summary_blocked_gap_rows_bound", row.get("blocked_gap_rows"), open_items)

    fail_if(sorted(seen_actions) != sorted(index_by_action), failures, "actions_exactly_covered", sorted(seen_actions), sorted(index_by_action))
    fail_if(seen_types.count("next_unlock_operator_navigation_gap") != len(index_rows), failures, "navigation_gap_type_count", seen_types.count("next_unlock_operator_navigation_gap"), len(index_rows))
    fail_if(seen_types.count("next_unlock_operator_navigation_summary_gap") != 1, failures, "summary_type_count", seen_types.count("next_unlock_operator_navigation_summary_gap"), 1)
    for field in ("training_import_allowed", "safe_for_training_import", "safe_for_model_claim", "customer_delivery_ready", "release_ready", "production_execution_allowed"):
        fail_if(report.get(field) is not False, failures, f"report_{field}_false", report.get(field), False)

    result = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "local_only": True,
        "success": not failures,
        "audit_rows": len(audit_rows),
        "operator_navigation_rows": len(index_rows),
        "open_item_rows": open_items,
        "source_completion_ready_items": source_ready_items,
        "blocked_gap_rows": open_items,
        "failures": failures,
        "training_import_allowed": False,
        "safe_for_training_import": False,
        "safe_for_model_claim": False,
        "customer_delivery_ready": False,
        "release_ready": False,
        "production_execution_allowed": False,
        "policy": "Validation only. Operator navigation gaps do not authorize training, claims, delivery, release, ordering, or production execution.",
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "success": result["success"],
        "audit_rows": result["audit_rows"],
        "operator_navigation_rows": result["operator_navigation_rows"],
        "open_item_rows": result["open_item_rows"],
        "failures": len(failures),
        "output": str(OUT),
    }, ensure_ascii=False))
    return 0 if result["success"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
