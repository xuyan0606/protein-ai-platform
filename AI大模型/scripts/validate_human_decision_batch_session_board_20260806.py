#!/usr/bin/env python3
"""Validate human decision batch session board without approving decisions."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_BOARD = ROOT / "reports" / "human_decision_batch_session_board_20260806.json"
DEFAULT_QUEUE = ROOT / "reports" / "human_decision_priority_queue_20260806.json"
DEFAULT_OUTPUT = ROOT / "reports" / "human_decision_batch_session_board_validation_report_20260806.json"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--board", type=Path, default=DEFAULT_BOARD)
    parser.add_argument("--queue", type=Path, default=DEFAULT_QUEUE)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    board = json.loads(args.board.read_text(encoding="utf-8"))
    queue = json.loads(args.queue.read_text(encoding="utf-8"))
    queue_ids = [row.get("batch_id") for row in queue.get("queue", [])]
    board_ids = [row.get("session_id") for row in board.get("sessions", [])]
    failures = []
    if board_ids != queue_ids:
        failures.append({"check": "board_order_matches_queue", "observed": board_ids[:5], "expected": queue_ids[:5]})
    for row in board.get("sessions", []):
        if row.get("assigned_reviewer") not in (None, ""):
            failures.append({"check": "assigned_reviewer_must_be_empty", "session_id": row.get("session_id")})
        if row.get("formal_decision_rows_written") != 0:
            failures.append({"check": "formal_decision_rows_written", "session_id": row.get("session_id")})
        if row.get("release_ready") is not False or row.get("safe_for_model_claim") is not False:
            failures.append({"check": "release_flags", "session_id": row.get("session_id")})

    report = {
        "schema_version": 1,
        "success": not failures,
        "status": "valid_pending_assignment" if not failures else "invalid",
        "session_count": len(board.get("sessions", [])),
        "queue_count": len(queue.get("queue", [])),
        "failure_count": len(failures),
        "failures": failures,
        "formal_decision_rows_written": 0,
        "release_ready": False,
        "safe_for_model_claim": False,
    }
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "success": report["success"],
        "status": report["status"],
        "session_count": report["session_count"],
        "queue_count": report["queue_count"],
        "failure_count": report["failure_count"],
        "output": str(args.output),
    }, ensure_ascii=False))
    return 0 if report["success"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
