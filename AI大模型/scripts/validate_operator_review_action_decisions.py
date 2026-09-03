#!/usr/bin/env python3
"""Validate operator review action completion decisions fail-closed."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
QUEUE = AI_ROOT / "datasets" / "governance" / "operator_review_action_queue.jsonl"
INPUT = AI_ROOT / "datasets" / "governance" / "operator_review_action_decisions.jsonl"
TEMPLATE = AI_ROOT / "datasets" / "governance" / "operator_review_action_decisions.template.jsonl"
REPORT_OUT = AI_ROOT / "reports" / "operator_review_action_decision_validation_report.json"

VALID_STATUS = {"completed", "blocked", "rejected", "needs_more_info"}

TEMPLATE_ROW = {
    "action_id": "review_action_001",
    "stream": "external_data_sources",
    "action_status": "needs_more_info",
    "reviewer": "human-operator",
    "reviewed_at": "2026-07-27T00:00:00+08:00",
    "evidence_artifacts": ["datasets/governance/external_license_review_decisions.jsonl"],
    "validation_reports": ["reports/external_license_review_decision_validation_report.json"],
    "completion_note": "template only; copy after the review action is actually completed",
    "residual_risks": [],
    "next_action": "complete missing source license decisions",
}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")


def exists_rel(rel: str) -> bool:
    path = Path(rel)
    if path.is_absolute():
        try:
            path.relative_to(AI_ROOT)
        except ValueError:
            return False
        return path.exists()
    return (AI_ROOT / path).exists()


def missing(value: Any) -> bool:
    return value is None or value == ""


def valid_path_set(value: Any) -> set[str]:
    if not isinstance(value, list):
        return set()
    return {path for path in value if isinstance(path, str) and path}


def validate(row: dict[str, Any], queue_by_id: dict[str, dict[str, Any]]) -> list[str]:
    errors: list[str] = []
    for field in [
        "action_id",
        "stream",
        "action_status",
        "reviewer",
        "reviewed_at",
        "evidence_artifacts",
        "validation_reports",
        "completion_note",
    ]:
        if field not in row or missing(row.get(field)):
            errors.append(f"missing_{field}")
    action_id = str(row.get("action_id"))
    queue_row = queue_by_id.get(action_id)
    if not queue_row:
        errors.append("unknown_action_id")
    elif row.get("stream") != queue_row.get("stream"):
        errors.append("stream_mismatch")
    if row.get("action_status") not in VALID_STATUS:
        errors.append("invalid_action_status")
    for field in ["evidence_artifacts", "validation_reports"]:
        value = row.get(field)
        if not isinstance(value, list):
            errors.append(f"invalid_{field}")
            continue
        missing_paths = [path for path in value if not isinstance(path, str) or not path or not exists_rel(path)]
        if missing_paths:
            errors.append(f"missing_{field}_paths")
    if row.get("residual_risks") is not None and not isinstance(row.get("residual_risks"), list):
        errors.append("invalid_residual_risks")
    if row.get("action_status") == "completed":
        if not row.get("evidence_artifacts"):
            errors.append("completed_without_evidence_artifacts")
        if not row.get("validation_reports"):
            errors.append("completed_without_validation_reports")
        if row.get("residual_risks"):
            errors.append("completed_with_residual_risks")
        if queue_row:
            provided_evidence = valid_path_set(row.get("evidence_artifacts"))
            required_evidence = valid_path_set(queue_row.get("required_evidence_artifacts"))
            provided_validation = valid_path_set(row.get("validation_reports"))
            required_validation = valid_path_set(queue_row.get("required_validation_reports"))
            if not required_evidence:
                errors.append("completed_queue_missing_required_evidence_contract")
            elif not required_evidence.issubset(provided_evidence):
                errors.append("completed_missing_required_evidence_artifacts")
            if not required_validation:
                errors.append("completed_queue_missing_required_validation_contract")
            elif not required_validation.issubset(provided_validation):
                errors.append("completed_missing_required_validation_reports")
    return errors


def action_decision_sets(records: list[dict[str, Any]]) -> tuple[list[str], list[str]]:
    decided = sorted(str(item["action_id"]) for item in records if item.get("valid"))
    completed = sorted(str(item["action_id"]) for item in records if item.get("completed"))
    return decided, completed


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate operator review action decisions")
    parser.add_argument("--queue", type=Path, default=QUEUE)
    parser.add_argument("--input", type=Path, default=INPUT)
    parser.add_argument("--template", type=Path, default=TEMPLATE)
    parser.add_argument("--report", type=Path, default=REPORT_OUT)
    args = parser.parse_args()

    args.input.parent.mkdir(parents=True, exist_ok=True)
    if not args.input.exists():
        args.input.write_text("", encoding="utf-8")
    write_jsonl(args.template, [TEMPLATE_ROW])

    queue_rows = load_jsonl(args.queue)
    decisions = load_jsonl(args.input)
    queue_by_id = {str(row.get("action_id")): row for row in queue_rows}
    records = []
    errors = Counter()
    seen = set()
    duplicates = set()
    for row in decisions:
        action_id = str(row.get("action_id"))
        if action_id in seen:
            duplicates.add(action_id)
        seen.add(action_id)
        row_errors = validate(row, queue_by_id)
        errors.update(row_errors)
        records.append({
            "action_id": row.get("action_id"),
            "stream": row.get("stream"),
            "action_status": row.get("action_status"),
            "valid": not row_errors,
            "completed": row.get("action_status") == "completed" and not row_errors,
            "errors": row_errors,
        })
    if duplicates:
        errors.update({"duplicate_action_id": len(duplicates)})
        for record in records:
            if record["action_id"] in duplicates:
                record["valid"] = False
                record["completed"] = False
                record["errors"].append("duplicate_action_id")

    valid_rows = sum(1 for item in records if item["valid"])
    decided_action_ids, completed_action_ids = action_decision_sets(records)
    completed_rows = len(completed_action_ids)
    missing_action_decisions = sorted(set(queue_by_id) - set(decided_action_ids))
    incomplete_action_ids = sorted(set(queue_by_id) - set(completed_action_ids))
    report = {
        "local_only": True,
        "input": str(args.input),
        "template": str(args.template),
        "queue_rows": len(queue_rows),
        "decision_rows": len(decisions),
        "valid_rows": valid_rows,
        "invalid_rows": len(records) - valid_rows,
        "decided_rows": len(decided_action_ids),
        "decided_action_ids": decided_action_ids,
        "all_actions_decided": len(decided_action_ids) == len(queue_rows) and bool(queue_rows) and not errors,
        "completed_rows": completed_rows,
        "all_actions_completed": completed_rows == len(queue_rows) and bool(queue_rows) and not errors,
        "missing_action_decisions": missing_action_decisions[:100],
        "incomplete_action_ids": incomplete_action_ids[:100],
        "error_counts": dict(errors),
        "records": records[:200],
        "policy": "Operator actions are complete only when a human decision references existing evidence and validation artifacts.",
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "decision_rows": len(decisions),
        "completed_rows": completed_rows,
        "all_actions_completed": report["all_actions_completed"],
        "output": str(args.report),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
