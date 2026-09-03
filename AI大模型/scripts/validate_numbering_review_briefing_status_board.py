#!/usr/bin/env python3
"""Validate the row-level numbering briefing status board."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
BRIEFING_JSON = AI_ROOT / "reports" / "numbering_review_briefing.json"
BRIEFING_VALIDATION = AI_ROOT / "reports" / "numbering_review_briefing_validation_report.json"
STATUS_BOARD = AI_ROOT / "datasets" / "curation" / "numbering_review_briefing_status_board.jsonl"
STATUS_REPORT = AI_ROOT / "reports" / "numbering_review_briefing_status_board_report.json"
STATUS_MD = AI_ROOT / "reports" / "numbering_review_briefing_status_board.md"
DECISIONS = AI_ROOT / "datasets" / "curation" / "numbering_curation_decisions.jsonl"
REPORT_OUT = AI_ROOT / "reports" / "numbering_review_briefing_status_board_validation_report.json"


VALID_STATUSES = {
    "open_blocked_waiting_for_human_review",
    "reviewed_decision_present_requires_validation_apply",
}


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def row_key(row: dict[str, Any]) -> str:
    return str(row.get("record_id") or "")


def expected_status_rows(briefing_rows: list[dict[str, Any]], decision_record_ids: set[str]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for order, row in enumerate(briefing_rows, start=1):
        record_id = row_key(row)
        decision_present = record_id in decision_record_ids
        rows.append({
            "execution_order": order,
            "record_id": record_id,
            "packet_id": row.get("packet_id"),
            "title_flag": row.get("title_flag"),
            "decision_row_present": decision_present,
            "briefing_status": "reviewed_decision_present_requires_validation_apply" if decision_present else "open_blocked_waiting_for_human_review",
        })
    return rows


def validate_status_row(row: dict[str, Any], expected: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    for field in ["execution_order", "record_id", "packet_id", "title_flag", "decision_row_present", "briefing_status"]:
        if row.get(field) != expected.get(field):
            errors.append(f"{field}_mismatch")
    if row.get("briefing_status") not in VALID_STATUSES:
        errors.append("invalid_status")
    if row.get("completion_ready") is not False:
        errors.append("completion_ready_must_be_false")
    if row.get("safe_for_model_claim") is not False:
        errors.append("safe_for_model_claim_must_be_false")
    if int(row.get("claim_eligible_rows_now") or 0) != 0:
        errors.append("claim_eligible_rows_must_be_zero")
    if "numbering_curation_decisions.jsonl" not in str(row.get("write_reviewed_decisions_to") or ""):
        errors.append("missing_decision_target")
    for field in ["canonical_position", "canonical_wild_type", "canonical_mutant", "confidence", "usable_as_supervised_label"]:
        if field in row:
            errors.append(f"forbidden_field_{field}")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate numbering briefing status board")
    parser.add_argument("--briefing-json", type=Path, default=BRIEFING_JSON)
    parser.add_argument("--briefing-validation", type=Path, default=BRIEFING_VALIDATION)
    parser.add_argument("--status-board", type=Path, default=STATUS_BOARD)
    parser.add_argument("--status-report", type=Path, default=STATUS_REPORT)
    parser.add_argument("--status-md", type=Path, default=STATUS_MD)
    parser.add_argument("--decisions", type=Path, default=DECISIONS)
    parser.add_argument("--report", type=Path, default=REPORT_OUT)
    args = parser.parse_args()

    briefing = load_json(args.briefing_json)
    briefing_validation = load_json(args.briefing_validation)
    status_report = load_json(args.status_report)
    rows = load_jsonl(args.status_board)
    decision_rows = load_jsonl(args.decisions)
    decision_record_ids = {str(row.get("record_id") or "") for row in decision_rows if row.get("record_id")}
    expected_rows = expected_status_rows(briefing.get("briefing_rows") or [], decision_record_ids)
    expected_by_id = {row["record_id"]: row for row in expected_rows}

    errors: list[str] = []
    row_errors: list[dict[str, Any]] = []
    if not briefing.get("local_only"):
        errors.append("briefing_not_local_only")
    if not briefing_validation.get("all_rows_valid"):
        errors.append("briefing_validation_not_all_valid")
    if len(rows) != len(expected_rows):
        errors.append("status_row_count_mismatch")

    seen: set[str] = set()
    for row in rows:
        record_id = row_key(row)
        current_errors: list[str] = []
        if not record_id:
            current_errors.append("missing_record_id")
        if record_id in seen:
            current_errors.append("duplicate_record_id")
        seen.add(record_id)
        expected = expected_by_id.get(record_id)
        if expected is None:
            current_errors.append("unexpected_record_id")
        else:
            current_errors.extend(validate_status_row(row, expected))
        if current_errors:
            row_errors.append({"record_id": record_id, "errors": current_errors})
            errors.extend(current_errors)

    missing_ids = sorted(set(expected_by_id) - seen)
    if missing_ids:
        errors.append("missing_status_rows")

    status_counts = Counter(str(row.get("briefing_status") or "") for row in rows)
    if status_report.get("briefing_rows") != len(rows):
        errors.append("status_report_row_count_mismatch")
    if status_report.get("status_counts") != dict(sorted(status_counts.items())):
        errors.append("status_report_status_counts_mismatch")

    md_text = args.status_md.read_text(encoding="utf-8") if args.status_md.exists() else ""
    for token in [
        "not a reviewed numbering decision",
        "not a training label",
        "not model claim readiness",
    ]:
        if token not in md_text:
            errors.append(f"markdown_missing_{token.replace(' ', '_')}")

    report = {
        "local_only": True,
        "status_board": str(args.status_board),
        "status_report": str(args.status_report),
        "status_md": str(args.status_md),
        "briefing_rows": len(briefing.get("briefing_rows") or []),
        "status_rows": len(rows),
        "expected_status_rows": len(expected_rows),
        "valid_status_rows": len(rows) - len(row_errors),
        "invalid_status_rows": len(row_errors),
        "missing_status_rows": len(missing_ids),
        "decision_input_rows": len(decision_rows),
        "decision_rows_present_for_briefing": sum(1 for row in rows if row.get("decision_row_present")),
        "open_blocked_briefing_rows": status_counts.get("open_blocked_waiting_for_human_review", 0),
        "completion_ready_rows": 0,
        "claim_eligible_rows_now": 0,
        "safe_for_model_claim": False,
        "all_status_rows_valid": not errors,
        "error_counts": dict(Counter(errors)),
        "row_errors": row_errors,
        "missing_record_ids": missing_ids,
        "policy": "Status board validation only; it never writes reviewed numbering decisions, supervised labels, or model claims.",
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({
        "status_rows": report["status_rows"],
        "valid_status_rows": report["valid_status_rows"],
        "invalid_status_rows": report["invalid_status_rows"],
        "output": str(args.report),
    }, ensure_ascii=False))
    return 0 if report["all_status_rows_valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
