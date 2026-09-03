#!/usr/bin/env python3
"""Validate the P486 next-unlock remediation queue gap audit."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
REMEDIATION_REPORT = AI_ROOT / "reports" / "next_unlock_remediation_queue.json"
REMEDIATION_QUEUE = AI_ROOT / "datasets" / "governance" / "next_unlock_remediation_queue.jsonl"
BLOCKER_MATRIX = AI_ROOT / "reports" / "next_unlock_blocker_matrix.json"
P485_REPORT = AI_ROOT / "reports" / "p485_next_unlock_blocker_matrix_gap_audit_report.json"
P485_VALIDATION = AI_ROOT / "reports" / "p485_next_unlock_blocker_matrix_gap_audit_validation_report.json"
LOCAL_RELEASE = AI_ROOT / "reports" / "local_release_manifest.json"
CLAIM_MATRIX = AI_ROOT / "reports" / "claim_readiness_matrix.json"
AUDIT = AI_ROOT / "datasets" / "governance" / "p486_next_unlock_remediation_queue_gap_audit.jsonl"
REPORT = AI_ROOT / "reports" / "p486_next_unlock_remediation_queue_gap_audit_report.json"
OUT = AI_ROOT / "reports" / "p486_next_unlock_remediation_queue_gap_audit_validation_report.json"


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
    remediation_report = load_json(REMEDIATION_REPORT)
    blocker_matrix = load_json(BLOCKER_MATRIX)
    p485_report = load_json(P485_REPORT)
    p485_validation = load_json(P485_VALIDATION)
    local_release = load_json(LOCAL_RELEASE)
    claim_matrix = load_json(CLAIM_MATRIX)
    queue = [row for row in load_jsonl(REMEDIATION_QUEUE) if isinstance(row, dict)]
    audit_rows = load_jsonl(AUDIT)
    report = load_json(REPORT)
    expected_rows = len(queue) + 1
    open_rows = sum(1 for row in queue if row.get("queue_status") == "open")
    ready_to_start_rows = sum(1 for row in queue if row.get("ready_to_start") is True)
    requires_human_input_rows = sum(1 for row in queue if row.get("requires_human_input") is True)
    queue_by_id = {row.get("remediation_id"): row for row in queue}
    failures: list[dict[str, Any]] = []

    fail_if(len(audit_rows) != expected_rows, failures, "audit_rows_expected", len(audit_rows), expected_rows)
    fail_if(report.get("audit_rows") != expected_rows, failures, "report_audit_rows_expected", report.get("audit_rows"), expected_rows)
    fail_if(report.get("remediation_audit_rows") != len(queue), failures, "remediation_audit_rows_bound", report.get("remediation_audit_rows"), len(queue))
    fail_if(report.get("summary_audit_rows") != 1, failures, "summary_audit_rows_one", report.get("summary_audit_rows"), 1)
    fail_if(report.get("queue_rows") != remediation_report.get("queue_rows"), failures, "queue_rows_bound", report.get("queue_rows"), remediation_report.get("queue_rows"))
    fail_if(report.get("open_rows") != open_rows, failures, "open_rows_bound", report.get("open_rows"), open_rows)
    fail_if(report.get("ready_to_start_rows") != ready_to_start_rows, failures, "ready_to_start_rows_bound", report.get("ready_to_start_rows"), ready_to_start_rows)
    fail_if(report.get("requires_human_input_rows") != requires_human_input_rows, failures, "requires_human_input_rows_bound", report.get("requires_human_input_rows"), requires_human_input_rows)
    fail_if(report.get("critical_rows") != remediation_report.get("critical_items"), failures, "critical_rows_bound", report.get("critical_rows"), remediation_report.get("critical_items"))
    fail_if(report.get("high_rows") != remediation_report.get("high_items"), failures, "high_rows_bound", report.get("high_rows"), remediation_report.get("high_items"))
    fail_if(report.get("medium_rows") != remediation_report.get("medium_items"), failures, "medium_rows_bound", report.get("medium_rows"), remediation_report.get("medium_items"))
    fail_if(report.get("source_blocker_rows") != blocker_matrix.get("blocker_rows"), failures, "source_blocker_rows_bound", report.get("source_blocker_rows"), blocker_matrix.get("blocker_rows"))
    fail_if(report.get("source_open_blocker_rows") != p485_report.get("open_blocker_rows"), failures, "source_open_blocker_rows_bound", report.get("source_open_blocker_rows"), p485_report.get("open_blocker_rows"))
    fail_if(report.get("p485_validation_success") is not True, failures, "p485_validation_success_true", report.get("p485_validation_success"), True)
    fail_if(p485_validation.get("success") is not True, failures, "source_p485_validation_success_true", p485_validation.get("success"), True)
    fail_if(report.get("local_release_ready") is not False, failures, "local_release_ready_false", report.get("local_release_ready"), False)
    fail_if(local_release.get("release_ready") is not False, failures, "source_local_release_ready_false", local_release.get("release_ready"), False)
    fail_if(report.get("claims_blocked") != claim_matrix.get("claims_blocked"), failures, "claims_blocked_bound", report.get("claims_blocked"), claim_matrix.get("claims_blocked"))
    fail_if(remediation_report.get("queue_rows") != len(queue), failures, "source_queue_rows_bound", remediation_report.get("queue_rows"), len(queue))
    fail_if(remediation_report.get("open_items") != open_rows, failures, "source_open_items_bound", remediation_report.get("open_items"), open_rows)
    fail_if(remediation_report.get("ready_to_start_items") != ready_to_start_rows, failures, "source_ready_to_start_items_bound", remediation_report.get("ready_to_start_items"), ready_to_start_rows)
    fail_if(remediation_report.get("requires_human_input_items") != requires_human_input_rows, failures, "source_requires_human_input_items_bound", remediation_report.get("requires_human_input_items"), requires_human_input_rows)
    fail_if(open_rows != len(queue), failures, "all_queue_rows_open", open_rows, len(queue))
    fail_if(requires_human_input_rows != len(queue), failures, "all_queue_rows_require_human_input", requires_human_input_rows, len(queue))

    seen_remediations: list[Any] = []
    seen_types: list[Any] = []
    for idx, row in enumerate(audit_rows):
        gap_type = row.get("gap_type")
        seen_types.append(gap_type)
        fail_if(gap_type not in {"next_unlock_remediation_queue_gap", "next_unlock_remediation_queue_summary_gap"}, failures, "gap_type_allowed", {"index": idx, "observed": gap_type}, "allowed P486 gap type")
        for field in ("training_import_allowed", "safe_for_training_import", "safe_for_model_claim", "customer_delivery_ready", "release_ready", "production_execution_allowed", "completion_ready"):
            fail_if(row.get(field) is not False, failures, f"row_{field}_false", {"index": idx, "observed": row.get(field)}, False)
        if gap_type == "next_unlock_remediation_queue_gap":
            remediation_id = row.get("remediation_id")
            seen_remediations.append(remediation_id)
            source = queue_by_id.get(remediation_id, {})
            fail_if(remediation_id not in queue_by_id, failures, "remediation_known", {"index": idx, "observed": remediation_id}, sorted(queue_by_id))
            fail_if(row.get("action_id") != source.get("action_id"), failures, "remediation_action_id_bound", {"index": idx, "observed": row.get("action_id")}, source.get("action_id"))
            fail_if(row.get("stage_id") != source.get("stage_id"), failures, "remediation_stage_id_bound", {"index": idx, "observed": row.get("stage_id")}, source.get("stage_id"))
            fail_if(row.get("workstream") != source.get("workstream"), failures, "remediation_workstream_bound", {"index": idx, "observed": row.get("workstream")}, source.get("workstream"))
            fail_if(row.get("severity") != source.get("severity"), failures, "remediation_severity_bound", {"index": idx, "observed": row.get("severity")}, source.get("severity"))
            fail_if(row.get("queue_status") != source.get("queue_status"), failures, "remediation_status_bound", {"index": idx, "observed": row.get("queue_status")}, source.get("queue_status"))
            fail_if(row.get("source_ready_to_start") != (source.get("ready_to_start") is True), failures, "remediation_ready_to_start_bound", {"index": idx, "observed": row.get("source_ready_to_start")}, source.get("ready_to_start") is True)
            fail_if(row.get("requires_human_input") != (source.get("requires_human_input") is True), failures, "remediation_requires_human_input_bound", {"index": idx, "observed": row.get("requires_human_input")}, source.get("requires_human_input") is True)
            fail_if(row.get("blocker_count") != source.get("blocker_count"), failures, "remediation_blocker_count_bound", {"index": idx, "observed": row.get("blocker_count")}, source.get("blocker_count"))
            fail_if(source.get("queue_status") != "open", failures, "source_remediation_status_open", {"index": idx, "observed": source.get("queue_status")}, "open")
        if gap_type == "next_unlock_remediation_queue_summary_gap":
            fail_if(row.get("queue_rows") != remediation_report.get("queue_rows"), failures, "summary_queue_rows_bound", row.get("queue_rows"), remediation_report.get("queue_rows"))
            fail_if(row.get("open_rows") != open_rows, failures, "summary_open_rows_bound", row.get("open_rows"), open_rows)
            fail_if(row.get("ready_to_start_rows") != ready_to_start_rows, failures, "summary_ready_to_start_rows_bound", row.get("ready_to_start_rows"), ready_to_start_rows)
            fail_if(row.get("requires_human_input_rows") != requires_human_input_rows, failures, "summary_requires_human_input_rows_bound", row.get("requires_human_input_rows"), requires_human_input_rows)

    fail_if(sorted(seen_remediations) != sorted(queue_by_id), failures, "remediations_exactly_covered", sorted(seen_remediations), sorted(queue_by_id))
    fail_if(seen_types.count("next_unlock_remediation_queue_gap") != len(queue), failures, "remediation_gap_type_count", seen_types.count("next_unlock_remediation_queue_gap"), len(queue))
    fail_if(seen_types.count("next_unlock_remediation_queue_summary_gap") != 1, failures, "summary_type_count", seen_types.count("next_unlock_remediation_queue_summary_gap"), 1)
    for field in ("training_import_allowed", "safe_for_training_import", "safe_for_model_claim", "customer_delivery_ready", "release_ready", "production_execution_allowed"):
        fail_if(report.get(field) is not False, failures, f"report_{field}_false", report.get(field), False)

    result = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "local_only": True,
        "success": not failures,
        "audit_rows": len(audit_rows),
        "remediation_audit_rows": len(queue),
        "open_rows": open_rows,
        "ready_to_start_rows": ready_to_start_rows,
        "requires_human_input_rows": requires_human_input_rows,
        "failures": failures,
        "training_import_allowed": False,
        "safe_for_training_import": False,
        "safe_for_model_claim": False,
        "customer_delivery_ready": False,
        "release_ready": False,
        "production_execution_allowed": False,
        "policy": "Validation only. Remediation queue gaps do not authorize training, claims, delivery, release, ordering, or production execution.",
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "success": result["success"],
        "audit_rows": result["audit_rows"],
        "remediation_audit_rows": result["remediation_audit_rows"],
        "open_rows": result["open_rows"],
        "failures": len(failures),
        "output": str(OUT),
    }, ensure_ascii=False))
    return 0 if result["success"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
