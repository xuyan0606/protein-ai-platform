#!/usr/bin/env python3
"""Build the P699 fail-closed formal-decision readiness status board."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from build_p698_p0_real_input_formal_decision_readiness_false_positive_guard import (
    FALSE_FIELDS as P698_FALSE_FIELDS,
    load_json,
    load_jsonl,
)


AI_ROOT = Path(__file__).resolve().parents[1]
SOURCE_JSONL = AI_ROOT / "datasets/governance/p698_p0_real_input_formal_decision_readiness_false_positive_guard.jsonl"
SOURCE_REPORT = AI_ROOT / "reports/p698_p0_real_input_formal_decision_readiness_false_positive_guard_report.json"
SOURCE_VALIDATION = AI_ROOT / "reports/p698_p0_real_input_formal_decision_readiness_false_positive_guard_validation_report.json"
OUT_JSONL = AI_ROOT / "datasets/governance/p699_p0_real_input_formal_decision_readiness_status_board.jsonl"
OUT_REPORT = AI_ROOT / "reports/p699_p0_real_input_formal_decision_readiness_status_board_report.json"
OUT_MD = AI_ROOT / "reports/p699_p0_real_input_formal_decision_readiness_status_board.md"

FALSE_FIELDS = tuple(P698_FALSE_FIELDS) + (
    "formal_decision_readiness_reviewed",
    "formal_decision_readiness_approved",
)


def zero_counts() -> dict[str, int]:
    return {f"{field}_rows": 0 for field in FALSE_FIELDS}


def build_row(source: dict[str, Any], order: int, created_at: str) -> dict[str, Any]:
    row = dict(source)
    row.update({
        "formal_decision_readiness_status_board_id": f"p699::{source.get('lane')}",
        "formal_decision_readiness_status_board_order": order,
        "created_at": created_at,
        "source_formal_decision_false_positive_guard_id": source.get(
            "formal_decision_false_positive_guard_id"
        ),
        "source_p698_validation_success": True,
        "formal_decision_readiness_status": (
            "open_empty_formal_decision_readiness_status_board"
        ),
        "formal_decision_readiness_status_open": True,
        "formal_decision_readiness_status_empty": True,
        "formal_decision_readiness_status_blocked": True,
        "formal_decision_readiness_status_note": (
            "P699 records status only. Formal decision readiness has not been reviewed or "
            "approved because the required real input and evidence remain absent."
        ),
        "policy": (
            "P699 is a local formal-decision readiness status board only. It does not review "
            "or approve readiness, receive input or evidence, write decisions, perform formal "
            "intake, create receipts or labels, resolve blockers, or authorize claims, release, "
            "delivery, or production."
        ),
    })
    for field in FALSE_FIELDS:
        row[field] = False
    return row


def main() -> int:
    created_at = datetime.now(timezone.utc).isoformat()
    source_report = load_json(SOURCE_REPORT)
    source_validation = load_json(SOURCE_VALIDATION)
    source_rows = [row for row in load_jsonl(SOURCE_JSONL) if row.get("lane") != "summary"]
    source_rows.sort(
        key=lambda row: int(row.get("formal_decision_false_positive_guard_order") or 0)
    )
    board_rows = [build_row(row, index, created_at) for index, row in enumerate(source_rows, start=1)]
    summary = {
        "formal_decision_readiness_status_board_id": "p699::summary",
        "formal_decision_readiness_status_board_order": len(board_rows) + 1,
        "created_at": created_at,
        "local_only": True,
        "lane": "summary",
        "source_formal_decision_false_positive_guard_rows": source_report.get(
            "formal_decision_false_positive_guard_rows"
        ),
        "source_p698_validation_success": source_validation.get("success"),
        "formal_decision_readiness_status_board_rows": len(board_rows),
        "open_formal_decision_readiness_status_board_rows": len(board_rows),
        "empty_formal_decision_readiness_status_board_rows": len(board_rows),
        "blocked_formal_decision_readiness_status_board_rows": len(board_rows),
        "formal_decision_readiness_status": (
            "open_empty_formal_decision_readiness_status_board"
        ),
        "formal_intake_dry_run_executed_rows": 0,
        "formal_intake_dry_run_passed_rows": 0,
        "p0_unblocked": False,
        "p0_completion_ready": False,
        "blocker": (
            "P698 false-positive guard remains open and empty; formal decision readiness is "
            "not reviewed or approved."
        ),
        "policy": "P699 is a local status board only; all formal decision and authorization gates remain fail-closed.",
        **zero_counts(),
        **{field: False for field in FALSE_FIELDS},
    }
    rows = board_rows + [summary]
    OUT_JSONL.write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )
    report = {
        "created_at": created_at,
        "local_only": True,
        "manifest_id": "P699",
        "source_jsonl": str(SOURCE_JSONL.relative_to(AI_ROOT)),
        "source_report": str(SOURCE_REPORT.relative_to(AI_ROOT)),
        "source_validation_report": str(SOURCE_VALIDATION.relative_to(AI_ROOT)),
        "source_formal_decision_false_positive_guard_rows": source_report.get(
            "formal_decision_false_positive_guard_rows"
        ),
        "source_p698_validation_success": source_validation.get("success"),
        "formal_decision_readiness_status_board_rows": len(board_rows),
        "audit_rows": len(rows),
        "open_formal_decision_readiness_status_board_rows": len(board_rows),
        "empty_formal_decision_readiness_status_board_rows": len(board_rows),
        "blocked_formal_decision_readiness_status_board_rows": len(board_rows),
        "formal_decision_readiness_status": (
            "open_empty_formal_decision_readiness_status_board"
        ),
        "formal_intake_dry_run_executed_rows": 0,
        "formal_intake_dry_run_passed_rows": 0,
        "p0_unblocked": False,
        "p0_completion_ready": False,
        "artifact_jsonl": str(OUT_JSONL.relative_to(AI_ROOT)),
        "artifact_md": str(OUT_MD.relative_to(AI_ROOT)),
        "policy": "P699 binds source-bound readiness status rows; formal decision and authorization gates remain fail-closed.",
        **zero_counts(),
        **{field: False for field in FALSE_FIELDS},
    }
    OUT_REPORT.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    OUT_MD.write_text(
        "\n".join([
            "# P699 P0 real-input formal decision readiness status board",
            "",
            "Status: formal decision readiness status remains open, empty, and blocked; no readiness review or approval exists.",
            "",
            f"- formal_decision_readiness_status_board_rows: `{len(board_rows)}`",
            f"- open_formal_decision_readiness_status_board_rows: `{len(board_rows)}`",
            f"- empty_formal_decision_readiness_status_board_rows: `{len(board_rows)}`",
            f"- blocked_formal_decision_readiness_status_board_rows: `{len(board_rows)}`",
            "",
            "This artifact is a local status board. It is not a formal decision, approval, acknowledgement, formal intake, runtime receipt, training label, release approval, or production authorization.",
        ]) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({
        "manifest_id": "P699",
        "formal_decision_readiness_status_board_rows": len(board_rows),
        "open_formal_decision_readiness_status_board_rows": len(board_rows),
        "empty_formal_decision_readiness_status_board_rows": len(board_rows),
        "formal_decision_ready_rows": 0,
        "formal_decision_readiness_reviewed_rows": 0,
        "formal_decision_readiness_approved_rows": 0,
        "output": str(OUT_REPORT),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
