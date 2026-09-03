#!/usr/bin/env python3
"""Build deterministic human-review batches from the pending row index."""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INPUT = ROOT / "reports" / "human_decision_pending_row_index_20260806.json"
DEFAULT_OUTPUT = ROOT / "reports" / "human_decision_review_batches_20260806.json"
BATCH_SIZE = 50


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    source = json.loads(args.input.read_text(encoding="utf-8"))
    grouped = defaultdict(list)
    for row in source.get("items", []):
        grouped[(row.get("priority") or "UNSET", row.get("workstream") or "UNSET")].append(row)

    batches = []
    for (priority, workstream), rows in sorted(grouped.items()):
        for offset in range(0, len(rows), BATCH_SIZE):
            chunk = rows[offset:offset + BATCH_SIZE]
            batch_number = offset // BATCH_SIZE + 1
            batches.append({
                "batch_id": f"{priority}_{workstream}_{batch_number:03d}",
                "priority": priority,
                "workstream": workstream,
                "batch_number": batch_number,
                "row_count": len(chunk),
                "pending_row_ids": [row["pending_row_id"] for row in chunk],
                "source_files": sorted({row["source"] for row in chunk}),
                "review_status": "pending_human_input",
                "formal_decision_rows_written": 0,
                "evidence_refs_complete": False,
                "release_ready": False,
                "safe_for_model_claim": False,
            })

    package = {
        "schema_version": 1,
        "created_at": "2026-08-06",
        "mode": "human_decision_review_batches",
        "write_policy": "batch_manifest_only; no_formal_decision_rows_written",
        "source_index": str(args.input),
        "batch_size": BATCH_SIZE,
        "summary": {
            "indexed_rows": len(source.get("items", [])),
            "batch_count": len(batches),
            "formal_decision_rows_written": 0,
            "release_ready": False,
            "safe_for_model_claim": False,
        },
        "batches": batches,
    }
    args.output.write_text(json.dumps(package, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "indexed_rows": package["summary"]["indexed_rows"],
        "batch_count": len(batches),
        "formal_decision_rows_written": 0,
        "output": str(args.output),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
