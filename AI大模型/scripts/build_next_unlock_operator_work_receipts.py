#!/usr/bin/env python3
"""Build local receipt status rows for next-unlock operator work targets."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
LEDGER = AI_ROOT / "datasets" / "governance" / "next_unlock_operator_work_ledger.jsonl"
LEDGER_STATUS = AI_ROOT / "datasets" / "governance" / "next_unlock_operator_work_ledger_status.jsonl"
REPORT_OUT = AI_ROOT / "reports" / "next_unlock_operator_work_receipt_report.json"
JSONL_OUT = AI_ROOT / "datasets" / "governance" / "next_unlock_operator_work_receipts.jsonl"


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() and path.suffix == ".json" else {}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")


def rel(path: Path) -> str:
    try:
        return str(path.relative_to(AI_ROOT))
    except ValueError:
        return str(path)


def by_action(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {str(row.get("action_id")): row for row in rows if row.get("action_id")}


def local_path(rel_path: str | None) -> Path | None:
    return (AI_ROOT / rel_path) if rel_path else None


def jsonl_row_count(rel_path: str | None) -> int | None:
    path = local_path(rel_path)
    if not path or not path.exists() or path.suffix != ".jsonl":
        return None
    return len(load_jsonl(path))


def validator_summary(rel_path: str | None) -> dict[str, Any]:
    path = local_path(rel_path)
    if not path or not path.exists() or path.suffix != ".json":
        return {"exists": bool(path and path.exists())}
    data = load_json(path)
    keys = [
        "ready",
        "runtime_ready",
        "safe_for_model_claim",
        "all_actions_completed",
        "all_streams_accepted",
        "ready_for_customer_delivery",
        "validated_ledger_rows",
        "invalid_ledger_rows",
        "valid_rows",
        "invalid_rows",
        "completed_rows",
        "missing_rows",
        "completion_ready_items",
        "requires_human_input_items",
    ]
    summary = {"exists": True}
    for key in keys:
        if key in data:
            summary[key] = data.get(key)
    return summary


def receipt_status(ledger_row: dict[str, Any], status_row: dict[str, Any] | None) -> str:
    if not status_row or status_row.get("validation_status") != "operator_work_ledger_validated_blocked":
        return "receipt_blocked_by_ledger_validation"
    if ledger_row.get("completion_ready"):
        return "receipt_invalid_completion_ready"
    if not ledger_row.get("requires_human_input"):
        return "receipt_invalid_missing_human_input_guard"
    return "receipt_open_blocked"


def main() -> int:
    parser = argparse.ArgumentParser(description="Build next-unlock operator work receipt status")
    parser.add_argument("--ledger", type=Path, default=LEDGER)
    parser.add_argument("--ledger-status", type=Path, default=LEDGER_STATUS)
    parser.add_argument("--report", type=Path, default=REPORT_OUT)
    parser.add_argument("--jsonl", type=Path, default=JSONL_OUT)
    args = parser.parse_args()

    ledger_rows = load_jsonl(args.ledger)
    status_by_action = by_action(load_jsonl(args.ledger_status))

    receipt_rows = []
    for row in sorted(ledger_rows, key=lambda item: (item.get("execution_order") or 999, str(item.get("ledger_id")))):
        action_id = str(row.get("action_id"))
        decision_input = row.get("decision_input")
        decision_path = local_path(decision_input)
        observed_input_rows = jsonl_row_count(decision_input)
        target_rows = row.get("backlog_milestone_missing_rows") or row.get("backlog_missing_rows")
        receipt_rows.append({
            "receipt_id": f"{action_id}-LOCAL-WORK-RECEIPT",
            "ledger_id": row.get("ledger_id"),
            "action_id": action_id,
            "execution_order": row.get("execution_order"),
            "lane_id": row.get("lane_id"),
            "workstream": row.get("workstream"),
            "receipt_status": receipt_status(row, status_by_action.get(action_id)),
            "ledger_validation_status": (status_by_action.get(action_id) or {}).get("validation_status"),
            "decision_input": decision_input,
            "decision_input_exists": bool(decision_path and decision_path.exists()),
            "decision_input_rows": observed_input_rows,
            "target_rows_or_missing_rows": target_rows,
            "target_rows_met": bool(observed_input_rows is not None and target_rows is not None and observed_input_rows >= target_rows),
            "validator_report": row.get("validator_report"),
            "validator_summary": validator_summary(row.get("validator_report")),
            "completion_ready": False,
            "requires_human_input": True,
            "operator_open_first": row.get("operator_open_first"),
            "next_evidence_artifacts": row.get("next_evidence_artifacts") or [],
            "verify_command": row.get("verify_command") or "python3 scripts/run_safe_training_pipeline.py",
            "receipt_note": "Receipt tracks local target state only; schema validation and completion remain delegated to downstream validators.",
            "policy": "Operator work receipt only. It does not create reviewed decisions, approvals, claim readiness, customer delivery, deployment, sync, or server restart.",
        })

    write_jsonl(args.jsonl, receipt_rows)
    open_blocked = [row for row in receipt_rows if row["receipt_status"] == "receipt_open_blocked"]
    report = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "local_only": True,
        "online_deployment": False,
        "source_ledger": rel(args.ledger),
        "source_ledger_status": rel(args.ledger_status),
        "jsonl": rel(args.jsonl),
        "receipt_rows": len(receipt_rows),
        "open_blocked_receipt_rows": len(open_blocked),
        "invalid_or_blocked_receipt_rows": len(receipt_rows) - len(open_blocked),
        "completion_ready_items": sum(1 for row in receipt_rows if row["completion_ready"]),
        "requires_human_input_items": sum(1 for row in receipt_rows if row["requires_human_input"]),
        "decision_input_present_rows": sum(1 for row in receipt_rows if row["decision_input"]),
        "decision_input_existing_rows": sum(1 for row in receipt_rows if row["decision_input_exists"]),
        "target_rows_met_items": sum(1 for row in receipt_rows if row["target_rows_met"]),
        "observed_decision_input_rows": sum(row["decision_input_rows"] or 0 for row in receipt_rows),
        "top_receipts": [
            {
                "execution_order": row["execution_order"],
                "receipt_id": row["receipt_id"],
                "workstream": row["workstream"],
                "receipt_status": row["receipt_status"],
                "decision_input": row["decision_input"],
                "decision_input_rows": row["decision_input_rows"],
                "target_rows_or_missing_rows": row["target_rows_or_missing_rows"],
                "target_rows_met": row["target_rows_met"],
                "validator_report": row["validator_report"],
            }
            for row in receipt_rows[:12]
        ],
        "policy": "This receipt report is a local operator status artifact only. It does not create reviewed decisions, grant approvals, unlock claims, approve customer delivery, authorize deployment, sync files, or restart servers.",
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "receipt_rows": report["receipt_rows"],
        "open_blocked_receipt_rows": report["open_blocked_receipt_rows"],
        "completion_ready_items": report["completion_ready_items"],
        "observed_decision_input_rows": report["observed_decision_input_rows"],
        "output": str(args.report),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
