#!/usr/bin/env python3
"""Build a priority-ordered human review queue from validated batches."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INPUT = ROOT / "reports" / "human_decision_review_batches_20260806.json"
DEFAULT_OUTPUT = ROOT / "reports" / "human_decision_priority_queue_20260806.json"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    source = json.loads(args.input.read_text(encoding="utf-8"))
    batches = sorted(
        source.get("batches", []),
        key=lambda item: (
            0 if item.get("priority") == "P0" else 1,
            -int(item.get("row_count") or 0),
            str(item.get("workstream") or ""),
            int(item.get("batch_number") or 0),
        ),
    )
    queue = []
    for rank, batch in enumerate(batches, start=1):
        queue.append({
            "queue_rank": rank,
            "batch_id": batch.get("batch_id"),
            "priority": batch.get("priority"),
            "workstream": batch.get("workstream"),
            "row_count": batch.get("row_count"),
            "pending_row_ids": batch.get("pending_row_ids", []),
            "source_files": batch.get("source_files", []),
            "review_status": "pending_human_input",
            "formal_decision_rows_written": 0,
            "release_ready": False,
            "safe_for_model_claim": False,
        })
    output = {
        "schema_version": 1,
        "created_at": "2026-08-06",
        "mode": "human_decision_priority_queue",
        "write_policy": "queue_only; no_formal_decision_rows_written",
        "source_batches": str(args.input),
        "summary": {
            "batch_count": len(queue),
            "p0_batch_count": sum(1 for item in queue if item["priority"] == "P0"),
            "indexed_rows": sum(int(item.get("row_count") or 0) for item in queue),
            "formal_decision_rows_written": 0,
            "release_ready": False,
            "safe_for_model_claim": False,
        },
        "queue": queue,
    }
    args.output.write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "batch_count": output["summary"]["batch_count"],
        "p0_batch_count": output["summary"]["p0_batch_count"],
        "indexed_rows": output["summary"]["indexed_rows"],
        "formal_decision_rows_written": 0,
        "output": str(args.output),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
