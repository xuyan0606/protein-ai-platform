#!/usr/bin/env python3
"""Validate the P476 human decision backlog gap audit."""

from __future__ import annotations

import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
BACKLOG_JSONL = AI_ROOT / "datasets" / "governance" / "human_decision_backlog.jsonl"
BACKLOG_REPORT = AI_ROOT / "reports" / "human_decision_backlog_report.json"
CONSISTENCY = AI_ROOT / "reports" / "human_decision_backlog_fail_closed_consistency_validation_report.json"
AUDIT = AI_ROOT / "datasets" / "governance" / "p476_human_decision_backlog_gap_audit.jsonl"
REPORT = AI_ROOT / "reports" / "p476_human_decision_backlog_gap_audit_report.json"
OUT = AI_ROOT / "reports" / "p476_human_decision_backlog_gap_audit_validation_report.json"


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
    backlog_rows = load_jsonl(BACKLOG_JSONL)
    backlog_report = load_json(BACKLOG_REPORT)
    consistency = load_json(CONSISTENCY)
    audit_rows = load_jsonl(AUDIT)
    report = load_json(REPORT)
    failures: list[dict[str, Any]] = []
    expected_rows = len(backlog_rows) + 1

    fail_if(len(audit_rows) != expected_rows, failures, "audit_rows_expected", len(audit_rows), expected_rows)
    fail_if(report.get("audit_rows") != expected_rows, failures, "report_audit_rows_expected", report.get("audit_rows"), expected_rows)
    fail_if(report.get("backlog_item_audit_rows") != len(backlog_rows), failures, "backlog_item_audit_rows_bound", report.get("backlog_item_audit_rows"), len(backlog_rows))
    fail_if(report.get("summary_audit_rows") != 1, failures, "summary_audit_rows_one", report.get("summary_audit_rows"), 1)
    for field in ("backlog_items", "open_items", "ready_items", "total_required_rows", "total_completed_rows", "total_missing_rows", "priority_counts"):
        fail_if(report.get(field) != backlog_report.get(field), failures, f"{field}_bound", report.get(field), backlog_report.get(field))
    fail_if(report.get("workstream_counts") != dict(sorted(Counter(str(row.get("workstream")) for row in backlog_rows).items())), failures, "workstream_counts_bound", report.get("workstream_counts"), dict(sorted(Counter(str(row.get("workstream")) for row in backlog_rows).items())))
    fail_if(report.get("consistency_success") is not True, failures, "consistency_success_true", report.get("consistency_success"), True)
    fail_if(consistency.get("success") is not True, failures, "source_consistency_success_true", consistency.get("success"), True)
    fail_if(report.get("consistency_failures") != [], failures, "consistency_failures_empty", report.get("consistency_failures"), [])
    fail_if(report.get("safe_for_training_pipeline") is not True, failures, "safe_for_training_pipeline_true", report.get("safe_for_training_pipeline"), True)
    fail_if(report.get("open_items") != len(backlog_rows), failures, "open_items_all_backlog_rows", report.get("open_items"), len(backlog_rows))
    fail_if(report.get("ready_items") != 0, failures, "ready_items_zero", report.get("ready_items"), 0)
    fail_if(report.get("total_missing_rows") != consistency.get("total_missing_rows"), failures, "total_missing_rows_consistency_bound", report.get("total_missing_rows"), consistency.get("total_missing_rows"))

    by_id = {row.get("backlog_id"): row for row in backlog_rows}
    seen_types = []
    for idx, row in enumerate(audit_rows):
        gap_type = row.get("gap_type")
        seen_types.append(gap_type)
        fail_if(gap_type not in {"human_decision_backlog_item", "human_decision_backlog_summary"}, failures, "gap_type_allowed", {"index": idx, "observed": gap_type}, "allowed P476 gap type")
        for field in ("training_import_allowed", "safe_for_training_import", "safe_for_model_claim", "release_ready", "production_execution_allowed", "completion_ready"):
            fail_if(row.get(field) is not False, failures, f"row_{field}_false", {"index": idx, "observed": row.get(field)}, False)
        if gap_type == "human_decision_backlog_item":
            source = by_id.get(row.get("backlog_id"), {})
            for field in ("workstream", "priority", "required_rows", "completed_rows", "missing_rows"):
                fail_if(row.get(field) != source.get(field), failures, f"item_{field}_bound", {"index": idx, "observed": row.get(field)}, source.get(field))
            fail_if(row.get("ready") is not False, failures, "item_ready_false", {"index": idx, "observed": row.get("ready")}, False)
        if gap_type == "human_decision_backlog_summary":
            fail_if(row.get("backlog_items") != backlog_report.get("backlog_items"), failures, "summary_backlog_items_bound", row.get("backlog_items"), backlog_report.get("backlog_items"))
            fail_if(row.get("open_items") != backlog_report.get("open_items"), failures, "summary_open_items_bound", row.get("open_items"), backlog_report.get("open_items"))
            fail_if(row.get("ready_items") != 0, failures, "summary_ready_items_zero", row.get("ready_items"), 0)
            fail_if(row.get("total_missing_rows") != backlog_report.get("total_missing_rows"), failures, "summary_missing_rows_bound", row.get("total_missing_rows"), backlog_report.get("total_missing_rows"))

    fail_if(seen_types.count("human_decision_backlog_item") != len(backlog_rows), failures, "item_audit_type_count", seen_types.count("human_decision_backlog_item"), len(backlog_rows))
    fail_if(seen_types.count("human_decision_backlog_summary") != 1, failures, "summary_audit_type_count", seen_types.count("human_decision_backlog_summary"), 1)
    for field in ("training_import_allowed", "safe_for_training_import", "safe_for_model_claim", "release_ready", "production_execution_allowed"):
        fail_if(report.get(field) is not False, failures, f"report_{field}_false", report.get(field), False)

    validation = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "local_only": True,
        "success": not failures,
        "audit_rows": len(audit_rows),
        "backlog_item_audit_rows": len(backlog_rows),
        "open_items": backlog_report.get("open_items"),
        "ready_items": backlog_report.get("ready_items"),
        "total_missing_rows": backlog_report.get("total_missing_rows"),
        "consistency_success": consistency.get("success"),
        "failures": failures,
        "training_import_allowed": False,
        "safe_for_training_import": False,
        "safe_for_model_claim": False,
        "release_ready": False,
        "production_execution_allowed": False,
        "policy": "Validation only. Human decision backlog remains open and does not authorize decisions, training, claims, release, or production execution.",
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(validation, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "success": validation["success"],
        "audit_rows": validation["audit_rows"],
        "open_items": validation["open_items"],
        "total_missing_rows": validation["total_missing_rows"],
        "failures": len(failures),
        "output": str(OUT),
    }, ensure_ascii=False))
    return 0 if validation["success"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
