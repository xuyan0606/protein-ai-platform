#!/usr/bin/env python3
"""Validate the P477 operator review action gap audit."""

from __future__ import annotations

import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
QUEUE_JSONL = AI_ROOT / "datasets" / "governance" / "operator_review_action_queue.jsonl"
QUEUE_REPORT = AI_ROOT / "reports" / "operator_review_action_queue_report.json"
DECISION_VALIDATION = AI_ROOT / "reports" / "operator_review_action_decision_validation_report.json"
STATUS_REPORT = AI_ROOT / "reports" / "operator_review_status_report.json"
AUDIT = AI_ROOT / "datasets" / "governance" / "p477_operator_review_action_gap_audit.jsonl"
REPORT = AI_ROOT / "reports" / "p477_operator_review_action_gap_audit_report.json"
OUT = AI_ROOT / "reports" / "p477_operator_review_action_gap_audit_validation_report.json"


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
    queue_rows = load_jsonl(QUEUE_JSONL)
    queue_report = load_json(QUEUE_REPORT)
    decision = load_json(DECISION_VALIDATION)
    status = load_json(STATUS_REPORT)
    audit_rows = load_jsonl(AUDIT)
    report = load_json(REPORT)
    failures: list[dict[str, Any]] = []
    expected_rows = len(queue_rows) + 1

    fail_if(len(audit_rows) != expected_rows, failures, "audit_rows_expected", len(audit_rows), expected_rows)
    fail_if(report.get("audit_rows") != expected_rows, failures, "report_audit_rows_expected", report.get("audit_rows"), expected_rows)
    fail_if(report.get("action_audit_rows") != len(queue_rows), failures, "action_audit_rows_bound", report.get("action_audit_rows"), len(queue_rows))
    fail_if(report.get("summary_audit_rows") != 1, failures, "summary_audit_rows_one", report.get("summary_audit_rows"), 1)
    fail_if(report.get("queue_rows") != queue_report.get("action_rows"), failures, "queue_rows_bound", report.get("queue_rows"), queue_report.get("action_rows"))
    fail_if(report.get("queue_ready") is not False, failures, "queue_ready_false", report.get("queue_ready"), False)
    for field in ("decision_rows", "valid_rows", "completed_rows", "all_actions_decided", "all_actions_completed", "missing_action_decisions", "incomplete_action_ids"):
        fail_if(report.get(field) != decision.get(field), failures, f"{field}_bound", report.get(field), decision.get(field))
    fail_if(report.get("status_ready") is not False, failures, "status_ready_false", report.get("status_ready"), False)
    fail_if(report.get("status_completed_action_rows") != status.get("completed_action_rows"), failures, "status_completed_action_rows_bound", report.get("status_completed_action_rows"), status.get("completed_action_rows"))
    fail_if(report.get("stream_counts") != dict(sorted(Counter(str(row.get("stream")) for row in queue_rows).items())), failures, "stream_counts_bound", report.get("stream_counts"), dict(sorted(Counter(str(row.get("stream")) for row in queue_rows).items())))
    fail_if(report.get("priority_counts") != dict(sorted(Counter(str(row.get("priority")) for row in queue_rows).items())), failures, "priority_counts_bound", report.get("priority_counts"), dict(sorted(Counter(str(row.get("priority")) for row in queue_rows).items())))
    fail_if(decision.get("decision_rows") != 0, failures, "decision_rows_zero", decision.get("decision_rows"), 0)
    fail_if(decision.get("completed_rows") != 0, failures, "completed_rows_zero", decision.get("completed_rows"), 0)
    fail_if(decision.get("all_actions_completed") is not False, failures, "all_actions_completed_false", decision.get("all_actions_completed"), False)

    by_id = {row.get("action_id"): row for row in queue_rows}
    seen_types = []
    for idx, row in enumerate(audit_rows):
        gap_type = row.get("gap_type")
        seen_types.append(gap_type)
        fail_if(gap_type not in {"operator_review_action_completion_gap", "operator_review_action_completion_summary"}, failures, "gap_type_allowed", {"index": idx, "observed": gap_type}, "allowed P477 gap type")
        for field in ("training_import_allowed", "safe_for_training_import", "safe_for_model_claim", "customer_delivery_ready", "release_ready", "production_execution_allowed", "completion_ready"):
            fail_if(row.get(field) is not False, failures, f"row_{field}_false", {"index": idx, "observed": row.get(field)}, False)
        if gap_type == "operator_review_action_completion_gap":
            source = by_id.get(row.get("action_id"), {})
            for field, source_field in (("stream", "stream"), ("priority", "priority"), ("queue_status", "status")):
                fail_if(row.get(field) != source.get(source_field), failures, f"action_{field}_bound", {"index": idx, "observed": row.get(field)}, source.get(source_field))
            fail_if(row.get("decision_present") is not False, failures, "action_decision_present_false", {"index": idx, "observed": row.get("decision_present")}, False)
            fail_if(row.get("completed") is not False, failures, "action_completed_false", {"index": idx, "observed": row.get("completed")}, False)
        if gap_type == "operator_review_action_completion_summary":
            fail_if(row.get("queue_rows") != queue_report.get("action_rows"), failures, "summary_queue_rows_bound", row.get("queue_rows"), queue_report.get("action_rows"))
            fail_if(row.get("decision_rows") != decision.get("decision_rows"), failures, "summary_decision_rows_bound", row.get("decision_rows"), decision.get("decision_rows"))
            fail_if(row.get("completed_rows") != decision.get("completed_rows"), failures, "summary_completed_rows_bound", row.get("completed_rows"), decision.get("completed_rows"))
            fail_if(row.get("all_actions_completed") is not False, failures, "summary_all_actions_completed_false", row.get("all_actions_completed"), False)

    fail_if(seen_types.count("operator_review_action_completion_gap") != len(queue_rows), failures, "action_gap_type_count", seen_types.count("operator_review_action_completion_gap"), len(queue_rows))
    fail_if(seen_types.count("operator_review_action_completion_summary") != 1, failures, "summary_type_count", seen_types.count("operator_review_action_completion_summary"), 1)
    for field in ("training_import_allowed", "safe_for_training_import", "safe_for_model_claim", "customer_delivery_ready", "release_ready", "production_execution_allowed"):
        fail_if(report.get(field) is not False, failures, f"report_{field}_false", report.get(field), False)

    validation = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "local_only": True,
        "success": not failures,
        "audit_rows": len(audit_rows),
        "action_audit_rows": len(queue_rows),
        "queue_rows": queue_report.get("action_rows"),
        "decision_rows": decision.get("decision_rows"),
        "completed_rows": decision.get("completed_rows"),
        "all_actions_completed": decision.get("all_actions_completed"),
        "failures": failures,
        "training_import_allowed": False,
        "safe_for_training_import": False,
        "safe_for_model_claim": False,
        "customer_delivery_ready": False,
        "release_ready": False,
        "production_execution_allowed": False,
        "policy": "Validation only. Operator review actions remain incomplete and do not authorize approvals, training, claims, release, or production execution.",
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(validation, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "success": validation["success"],
        "audit_rows": validation["audit_rows"],
        "action_audit_rows": validation["action_audit_rows"],
        "completed_rows": validation["completed_rows"],
        "failures": len(failures),
        "output": str(OUT),
    }, ensure_ascii=False))
    return 0 if validation["success"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
