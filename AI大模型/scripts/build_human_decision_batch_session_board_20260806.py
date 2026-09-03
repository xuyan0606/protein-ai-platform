#!/usr/bin/env python3
"""Build a human decision batch session board for operational review tracking."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INPUT = ROOT / "reports" / "human_decision_priority_queue_20260806.json"
DEFAULT_OUTPUT = ROOT / "reports" / "human_decision_batch_session_board_20260806.json"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    queue = json.loads(args.input.read_text(encoding="utf-8"))
    board = []
    for entry in queue.get("queue", []):
        board.append({
            "session_id": f"{entry.get('batch_id')}",
            "queue_rank": entry.get("queue_rank"),
            "batch_id": entry.get("batch_id"),
            "priority": entry.get("priority"),
            "workstream": entry.get("workstream"),
            "row_count": entry.get("row_count"),
            "assigned_reviewer": None,
            "status": "pending_assignment",
            "evidence_refs": [],
            "closed_rows": 0,
            "formal_decision_rows_written": 0,
            "release_ready": False,
            "safe_for_model_claim": False,
        })
    output = {
        "schema_version": 1,
        "created_at": "2026-08-06",
        "mode": "human_decision_batch_session_board",
        "write_policy": "session_tracking_only; no_formal_decision_rows_written",
        "source_queue": str(args.input),
        "summary": {
            "session_count": len(board),
            "assigned_count": sum(1 for row in board if row["assigned_reviewer"]),
            "open_count": sum(1 for row in board if row["status"] != "closed"),
            "formal_decision_rows_written": 0,
            "release_ready": False,
            "safe_for_model_claim": False,
        },
        "sessions": board,
    }
    args.output.write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "session_count": len(board),
        "assigned_count": output["summary"]["assigned_count"],
        "formal_decision_rows_written": 0,
        "output": str(args.output),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
