#!/usr/bin/env python3
"""Validate next-unlock local operator work receipt semantics."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
RECEIPTS = AI_ROOT / "datasets" / "governance" / "next_unlock_operator_work_receipts.jsonl"
LEDGER_STATUS = AI_ROOT / "datasets" / "governance" / "next_unlock_operator_work_ledger_status.jsonl"
REPORT_OUT = AI_ROOT / "reports" / "next_unlock_operator_work_receipt_validation_report.json"
JSONL_OUT = AI_ROOT / "datasets" / "governance" / "next_unlock_operator_work_receipt_status.jsonl"


REQUIRED_NOTE_TERMS = [
    "local target state only",
    "downstream validators",
]
REQUIRED_POLICY_TERMS = [
    "reviewed decisions",
    "approvals",
    "claim readiness",
    "customer delivery",
    "deployment",
    "sync",
    "server restart",
]


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


def local_path(rel_path: str | None) -> Path | None:
    return (AI_ROOT / rel_path) if rel_path else None


def path_exists(rel_path: str | None) -> bool:
    path = local_path(rel_path)
    return bool(path and path.exists())


def jsonl_row_count(rel_path: str | None) -> int | None:
    path = local_path(rel_path)
    if not path or not path.exists() or path.suffix != ".jsonl":
        return None
    return len(load_jsonl(path))


def check(name: str, passed: bool, observed: Any = None, expected: Any = None) -> dict[str, Any]:
    row = {"name": name, "passed": bool(passed)}
    if observed is not None:
        row["observed"] = observed
    if expected is not None:
        row["expected"] = expected
    return row


def by_action(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {str(row.get("action_id")): row for row in rows if row.get("action_id")}


def validate_row(row: dict[str, Any], ledger_status: dict[str, Any] | None) -> list[dict[str, Any]]:
    action_id = str(row.get("action_id"))
    decision_input = row.get("decision_input")
    observed_decision_input_rows = jsonl_row_count(decision_input)
    target_rows = row.get("target_rows_or_missing_rows")
    expected_target_rows_met = bool(
        observed_decision_input_rows is not None
        and target_rows is not None
        and observed_decision_input_rows >= target_rows
    )
    referenced_paths = [
        row.get("operator_open_first"),
        row.get("decision_input"),
        row.get("validator_report"),
        *(row.get("next_evidence_artifacts") or []),
    ]
    missing_paths = sorted({path for path in referenced_paths if path and not path_exists(path)})
    validator_report = load_json(local_path(row.get("validator_report")) or Path(""))
    validator_summary = row.get("validator_summary") or {}
    policy = str(row.get("policy") or "").lower()
    receipt_note = str(row.get("receipt_note") or "").lower()
    return [
        check("matching ledger validation row exists", ledger_status is not None, action_id, "existing action_id"),
        check("receipt id is stable", row.get("receipt_id") == f"{action_id}-LOCAL-WORK-RECEIPT", row.get("receipt_id"), f"{action_id}-LOCAL-WORK-RECEIPT"),
        check("ledger id is stable", row.get("ledger_id") == f"{action_id}-LOCAL-OPERATOR-WORK-LEDGER", row.get("ledger_id"), f"{action_id}-LOCAL-OPERATOR-WORK-LEDGER"),
        check("receipt remains open blocked", row.get("receipt_status") == "receipt_open_blocked", row.get("receipt_status"), "receipt_open_blocked"),
        check("ledger validation remains blocked", row.get("ledger_validation_status") == "operator_work_ledger_validated_blocked", row.get("ledger_validation_status"), "operator_work_ledger_validated_blocked"),
        check("ledger validation matches source status", row.get("ledger_validation_status") == (ledger_status or {}).get("validation_status"), {"receipt": row.get("ledger_validation_status"), "ledger_status": (ledger_status or {}).get("validation_status")}, "same validation_status"),
        check("completion-ready remains false", row.get("completion_ready") is False, row.get("completion_ready"), False),
        check("requires human input remains true", row.get("requires_human_input") is True, row.get("requires_human_input"), True),
        check("execution order matches ledger status", row.get("execution_order") == (ledger_status or {}).get("execution_order"), {"receipt": row.get("execution_order"), "ledger_status": (ledger_status or {}).get("execution_order")}, "same execution_order"),
        check("decision input existence flag matches local file", row.get("decision_input_exists") == path_exists(decision_input), {"flag": row.get("decision_input_exists"), "exists": path_exists(decision_input)}, "same file existence"),
        check("decision input exists when present", not decision_input or path_exists(decision_input), decision_input, "optional existing local path"),
        check("decision input row count matches local JSONL", row.get("decision_input_rows") == observed_decision_input_rows, {"receipt": row.get("decision_input_rows"), "observed": observed_decision_input_rows}, "same row count"),
        check("target rows met is row-count observation only", row.get("target_rows_met") == expected_target_rows_met and row.get("completion_ready") is False, {"target_rows_met": row.get("target_rows_met"), "expected": expected_target_rows_met, "completion_ready": row.get("completion_ready")}, "target rows observation must not unlock completion"),
        check("validator report exists", path_exists(row.get("validator_report")), row.get("validator_report"), "existing local path"),
        check("validator summary reports file existence", validator_summary.get("exists") is True and bool(validator_report), validator_summary, "existing validator report summary"),
        check("operator path exists", path_exists(row.get("operator_open_first")), row.get("operator_open_first"), "existing local path"),
        check("next evidence artifacts exist", not missing_paths, missing_paths, []),
        check("verify command is local safe pipeline", row.get("verify_command") == "python3 scripts/run_safe_training_pipeline.py", row.get("verify_command"), "python3 scripts/run_safe_training_pipeline.py"),
        check("receipt note preserves local status boundary", all(term in receipt_note for term in REQUIRED_NOTE_TERMS), row.get("receipt_note"), REQUIRED_NOTE_TERMS),
        check("policy blocks completion/approval/deployment meanings", all(term in policy for term in REQUIRED_POLICY_TERMS), row.get("policy"), REQUIRED_POLICY_TERMS),
    ]


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate next-unlock operator work receipts")
    parser.add_argument("--receipts", type=Path, default=RECEIPTS)
    parser.add_argument("--ledger-status", type=Path, default=LEDGER_STATUS)
    parser.add_argument("--report", type=Path, default=REPORT_OUT)
    parser.add_argument("--jsonl", type=Path, default=JSONL_OUT)
    args = parser.parse_args()

    receipt_rows = load_jsonl(args.receipts)
    ledger_status_by_action = by_action(load_jsonl(args.ledger_status))

    status_rows = []
    for row in sorted(receipt_rows, key=lambda item: (item.get("execution_order") or 999, str(item.get("receipt_id")))):
        action_id = str(row.get("action_id"))
        checks = validate_row(row, ledger_status_by_action.get(action_id))
        failed_checks = [item["name"] for item in checks if not item["passed"]]
        status_rows.append({
            "receipt_id": row.get("receipt_id"),
            "ledger_id": row.get("ledger_id"),
            "action_id": action_id,
            "lane_id": row.get("lane_id"),
            "workstream": row.get("workstream"),
            "execution_order": row.get("execution_order"),
            "receipt_status": row.get("receipt_status"),
            "validation_status": "operator_work_receipt_validated_blocked" if not failed_checks else "operator_work_receipt_invalid",
            "ledger_validation_status": row.get("ledger_validation_status"),
            "decision_input": row.get("decision_input"),
            "decision_input_rows": row.get("decision_input_rows"),
            "target_rows_or_missing_rows": row.get("target_rows_or_missing_rows"),
            "target_rows_met": row.get("target_rows_met"),
            "completion_ready": row.get("completion_ready"),
            "requires_human_input": row.get("requires_human_input"),
            "failed_checks": failed_checks,
            "checks": checks,
            "verify_command": row.get("verify_command"),
            "policy": "Operator work receipt validation only. Validated receipt means local target-state tracking only; it is not completion, approval, customer delivery, deployment, sync, server restart, or claim readiness.",
        })

    write_jsonl(args.jsonl, status_rows)
    invalid_rows = [row for row in status_rows if row["validation_status"] == "operator_work_receipt_invalid"]
    target_rows_met = [row for row in status_rows if row["target_rows_met"]]
    report = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "local_only": True,
        "online_deployment": False,
        "source_receipts": rel(args.receipts),
        "source_ledger_status": rel(args.ledger_status),
        "jsonl": rel(args.jsonl),
        "receipt_rows": len(status_rows),
        "validated_receipt_rows": len(status_rows) - len(invalid_rows),
        "invalid_receipt_rows": len(invalid_rows),
        "open_blocked_receipt_rows": sum(1 for row in status_rows if row["receipt_status"] == "receipt_open_blocked"),
        "completion_ready_items": sum(1 for row in status_rows if row["completion_ready"]),
        "requires_human_input_items": sum(1 for row in status_rows if row["requires_human_input"]),
        "target_rows_met_items": len(target_rows_met),
        "target_rows_met_completion_ready_items": sum(1 for row in target_rows_met if row["completion_ready"]),
        "observed_decision_input_rows": sum(row["decision_input_rows"] or 0 for row in status_rows),
        "invalid_receipt_items": [
            {
                "receipt_id": row["receipt_id"],
                "action_id": row["action_id"],
                "failed_checks": row["failed_checks"],
            }
            for row in invalid_rows
        ],
        "target_rows_met_items_detail": [
            {
                "receipt_id": row["receipt_id"],
                "action_id": row["action_id"],
                "workstream": row["workstream"],
                "decision_input_rows": row["decision_input_rows"],
                "target_rows_or_missing_rows": row["target_rows_or_missing_rows"],
                "completion_ready": row["completion_ready"],
            }
            for row in target_rows_met
        ],
        "policy": "This validator confirms local operator receipt semantics only. It does not create reviewed decisions, grant approvals, unlock claims, approve customer delivery, authorize deployment, sync files, or restart servers.",
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "receipt_rows": report["receipt_rows"],
        "validated_receipt_rows": report["validated_receipt_rows"],
        "invalid_receipt_rows": report["invalid_receipt_rows"],
        "completion_ready_items": report["completion_ready_items"],
        "target_rows_met_items": report["target_rows_met_items"],
        "output": str(args.report),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
