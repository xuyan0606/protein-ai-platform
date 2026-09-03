#!/usr/bin/env python3
"""Build a source-bound audit of human decision backlog gaps."""

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
OUT_JSONL = AI_ROOT / "datasets" / "governance" / "p476_human_decision_backlog_gap_audit.jsonl"
OUT_REPORT = AI_ROOT / "reports" / "p476_human_decision_backlog_gap_audit_report.json"


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    value = json.loads(path.read_text(encoding="utf-8"))
    return value if isinstance(value, dict) else {}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def base(audit_id: str, gap_type: str, source_state: dict[str, Any], blocker: str) -> dict[str, Any]:
    return {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "local_only": True,
        "audit_id": audit_id,
        "gap_type": gap_type,
        "source_report": "reports/human_decision_backlog_report.json",
        "source_state": source_state,
        "blocker": blocker,
        "training_import_allowed": False,
        "safe_for_training_import": False,
        "safe_for_model_claim": False,
        "release_ready": False,
        "production_execution_allowed": False,
        "policy": "Human decision backlog audit only; backlog rows do not create decisions, approvals, training import, model claims, release, or production authorization.",
    }


def main() -> int:
    backlog_rows = load_jsonl(BACKLOG_JSONL)
    report = load_json(BACKLOG_REPORT)
    consistency = load_json(CONSISTENCY)
    rows: list[dict[str, Any]] = []

    for item in backlog_rows:
        backlog_id = item.get("backlog_id")
        missing_rows = int(item.get("missing_rows") or 0)
        rows.append(base(
            f"p476-human-backlog::{backlog_id}",
            "human_decision_backlog_item",
            {
                "backlog_id": backlog_id,
                "workstream": item.get("workstream"),
                "priority": item.get("priority"),
                "decision_scope": item.get("decision_scope"),
                "review_source": item.get("review_source"),
                "decision_input": item.get("decision_input"),
                "template": item.get("template"),
                "validator_report": item.get("validator_report"),
                "required_rows": item.get("required_rows"),
                "current_decision_rows": item.get("current_decision_rows"),
                "current_valid_rows": item.get("current_valid_rows"),
                "completed_rows": item.get("completed_rows"),
                "missing_rows": item.get("missing_rows"),
                "ready": item.get("ready"),
            },
            "human decision backlog item remains open or not ready",
        ) | {
            "backlog_id": backlog_id,
            "workstream": item.get("workstream"),
            "priority": item.get("priority"),
            "required_rows": item.get("required_rows"),
            "completed_rows": item.get("completed_rows"),
            "missing_rows": missing_rows,
            "ready": item.get("ready") is True,
            "completion_ready": False,
        })

    rows.append(base(
        "p476-human-backlog-summary",
        "human_decision_backlog_summary",
        {
            "backlog_items": report.get("backlog_items"),
            "open_items": report.get("open_items"),
            "ready_items": report.get("ready_items"),
            "total_required_rows": report.get("total_required_rows"),
            "total_completed_rows": report.get("total_completed_rows"),
            "total_missing_rows": report.get("total_missing_rows"),
            "priority_counts": report.get("priority_counts"),
            "consistency_success": consistency.get("success"),
            "consistency_expected_backlog_items": consistency.get("expected_backlog_items"),
            "consistency_total_missing_rows": consistency.get("total_missing_rows"),
            "feedback_source_required_rows": consistency.get("feedback_source_required_rows"),
            "plate_feedback_required_rows": consistency.get("plate_feedback_required_rows"),
        },
        "overall human decision backlog remains open and blocks training, claims, delivery, release, and production execution",
    ) | {
        "backlog_items": report.get("backlog_items"),
        "open_items": report.get("open_items"),
        "ready_items": report.get("ready_items"),
        "total_missing_rows": report.get("total_missing_rows"),
        "completion_ready": False,
    })

    audit_report = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "local_only": True,
        "audit_rows": len(rows),
        "backlog_item_audit_rows": len(backlog_rows),
        "summary_audit_rows": 1,
        "backlog_items": report.get("backlog_items"),
        "open_items": report.get("open_items"),
        "ready_items": report.get("ready_items"),
        "total_required_rows": report.get("total_required_rows"),
        "total_completed_rows": report.get("total_completed_rows"),
        "total_missing_rows": report.get("total_missing_rows"),
        "priority_counts": report.get("priority_counts"),
        "workstream_counts": dict(sorted(Counter(str(row.get("workstream")) for row in backlog_rows).items())),
        "consistency_success": consistency.get("success"),
        "consistency_failures": consistency.get("failures"),
        "safe_for_training_pipeline": consistency.get("safe_for_training_pipeline"),
        "training_import_allowed": False,
        "safe_for_training_import": False,
        "safe_for_model_claim": False,
        "release_ready": False,
        "production_execution_allowed": False,
        "audit_jsonl": "datasets/governance/p476_human_decision_backlog_gap_audit.jsonl",
        "policy": "P476 audit only. Human backlog visibility is not human approval, reviewed evidence, training import, model claim, release, or production execution.",
    }
    write_jsonl(OUT_JSONL, rows)
    OUT_REPORT.parent.mkdir(parents=True, exist_ok=True)
    OUT_REPORT.write_text(json.dumps(audit_report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "audit_rows": audit_report["audit_rows"],
        "backlog_item_audit_rows": audit_report["backlog_item_audit_rows"],
        "open_items": audit_report["open_items"],
        "total_missing_rows": audit_report["total_missing_rows"],
        "safe_for_model_claim": False,
        "output": str(OUT_REPORT),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
