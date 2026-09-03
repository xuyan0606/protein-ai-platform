#!/usr/bin/env python3
"""Build a source-bound audit of operator review action completion gaps."""

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
OUT_JSONL = AI_ROOT / "datasets" / "governance" / "p477_operator_review_action_gap_audit.jsonl"
OUT_REPORT = AI_ROOT / "reports" / "p477_operator_review_action_gap_audit_report.json"


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
        "source_report": "reports/operator_review_action_queue_report.json",
        "source_state": source_state,
        "blocker": blocker,
        "training_import_allowed": False,
        "safe_for_training_import": False,
        "safe_for_model_claim": False,
        "customer_delivery_ready": False,
        "release_ready": False,
        "production_execution_allowed": False,
        "policy": "Operator review action audit only; queue rows and status summaries do not create completion decisions, approvals, training import, model claims, release, or production authorization.",
    }


def main() -> int:
    queue_rows = load_jsonl(QUEUE_JSONL)
    queue_report = load_json(QUEUE_REPORT)
    decision = load_json(DECISION_VALIDATION)
    status = load_json(STATUS_REPORT)
    rows: list[dict[str, Any]] = []

    for row in queue_rows:
        action_id = row.get("action_id")
        rows.append(base(
            f"p477-operator-action::{action_id}",
            "operator_review_action_completion_gap",
            {
                "action_id": action_id,
                "stream": row.get("stream"),
                "priority": row.get("priority"),
                "status": row.get("status"),
                "acceptance_requires": row.get("acceptance_requires"),
                "required_evidence_artifacts": row.get("required_evidence_artifacts"),
                "required_validation_reports": row.get("required_validation_reports"),
                "done_definition": row.get("done_definition"),
                "missing_action_decision": action_id in set(decision.get("missing_action_decisions") or []),
                "incomplete_action": action_id in set(decision.get("incomplete_action_ids") or []),
            },
            "operator action lacks a valid completed human decision with required evidence and validation reports",
        ) | {
            "action_id": action_id,
            "stream": row.get("stream"),
            "priority": row.get("priority"),
            "queue_status": row.get("status"),
            "decision_present": action_id not in set(decision.get("missing_action_decisions") or []),
            "completed": False,
            "completion_ready": False,
        })

    operator_completion = (status.get("status") or {}).get("operator_action_completion") or {}
    rows.append(base(
        "p477-operator-action-summary",
        "operator_review_action_completion_summary",
        {
            "queue_rows": queue_report.get("action_rows"),
            "queue_completed_rows": queue_report.get("completed_rows"),
            "queue_ready": queue_report.get("ready"),
            "decision_rows": decision.get("decision_rows"),
            "valid_rows": decision.get("valid_rows"),
            "completed_rows": decision.get("completed_rows"),
            "all_actions_decided": decision.get("all_actions_decided"),
            "all_actions_completed": decision.get("all_actions_completed"),
            "status_ready": status.get("ready"),
            "status_completed_action_rows": status.get("completed_action_rows"),
            "status_blockers": status.get("blockers"),
        },
        "operator review queue remains incomplete and cannot close governance, delivery, release, or production gates",
    ) | {
        "queue_rows": queue_report.get("action_rows"),
        "decision_rows": decision.get("decision_rows"),
        "completed_rows": decision.get("completed_rows"),
        "all_actions_completed": False,
        "completion_ready": False,
    })

    report = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "local_only": True,
        "audit_rows": len(rows),
        "action_audit_rows": len(queue_rows),
        "summary_audit_rows": 1,
        "queue_rows": queue_report.get("action_rows"),
        "queue_ready": queue_report.get("ready"),
        "decision_rows": decision.get("decision_rows"),
        "valid_rows": decision.get("valid_rows"),
        "completed_rows": decision.get("completed_rows"),
        "all_actions_decided": decision.get("all_actions_decided"),
        "all_actions_completed": decision.get("all_actions_completed"),
        "missing_action_decisions": decision.get("missing_action_decisions"),
        "incomplete_action_ids": decision.get("incomplete_action_ids"),
        "status_ready": status.get("ready"),
        "status_completed_action_rows": status.get("completed_action_rows"),
        "stream_counts": dict(sorted(Counter(str(row.get("stream")) for row in queue_rows).items())),
        "priority_counts": dict(sorted(Counter(str(row.get("priority")) for row in queue_rows).items())),
        "training_import_allowed": False,
        "safe_for_training_import": False,
        "safe_for_model_claim": False,
        "customer_delivery_ready": False,
        "release_ready": False,
        "production_execution_allowed": False,
        "audit_jsonl": "datasets/governance/p477_operator_review_action_gap_audit.jsonl",
        "policy": "P477 audit only. Operator action queues remain open until explicit completion decisions reference required evidence and validation reports.",
    }
    write_jsonl(OUT_JSONL, rows)
    OUT_REPORT.parent.mkdir(parents=True, exist_ok=True)
    OUT_REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "audit_rows": report["audit_rows"],
        "action_audit_rows": report["action_audit_rows"],
        "decision_rows": report["decision_rows"],
        "completed_rows": report["completed_rows"],
        "all_actions_completed": False,
        "output": str(OUT_REPORT),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
