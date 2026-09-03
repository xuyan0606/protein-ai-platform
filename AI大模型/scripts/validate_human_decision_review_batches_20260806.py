#!/usr/bin/env python3
"""Validate human-review batch coverage without approving any decisions."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INDEX = ROOT / "reports" / "human_decision_pending_row_index_20260806.json"
DEFAULT_BATCHES = ROOT / "reports" / "human_decision_review_batches_20260806.json"
DEFAULT_OUTPUT = ROOT / "reports" / "human_decision_review_batches_validation_report_20260806.json"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--index", type=Path, default=DEFAULT_INDEX)
    parser.add_argument("--batches", type=Path, default=DEFAULT_BATCHES)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    index = json.loads(args.index.read_text(encoding="utf-8"))
    batches = json.loads(args.batches.read_text(encoding="utf-8"))
    expected = [row["pending_row_id"] for row in index.get("items", [])]
    observed = [
        row_id
        for batch in batches.get("batches", [])
        for row_id in batch.get("pending_row_ids", [])
    ]
    failures = []
    if len(expected) != len(set(expected)):
        failures.append({"check": "index_unique", "observed": len(expected), "unique": len(set(expected))})
    if len(observed) != len(set(observed)):
        failures.append({"check": "batch_unique", "observed": len(observed), "unique": len(set(observed))})
    if set(expected) != set(observed):
        failures.append({
            "check": "coverage",
            "missing": sorted(set(expected) - set(observed))[:20],
            "unexpected": sorted(set(observed) - set(expected))[:20],
        })
    for batch in batches.get("batches", []):
        if batch.get("formal_decision_rows_written") != 0:
            failures.append({"check": "formal_decision_rows_written", "batch_id": batch.get("batch_id")})
        if batch.get("release_ready") is not False or batch.get("safe_for_model_claim") is not False:
            failures.append({"check": "release_flags", "batch_id": batch.get("batch_id")})

    report = {
        "schema_version": 1,
        "success": not failures,
        "status": "valid_pending_review" if not failures else "invalid",
        "indexed_rows": len(expected),
        "batched_rows": len(observed),
        "batch_count": len(batches.get("batches", [])),
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
        "indexed_rows": report["indexed_rows"],
        "batched_rows": report["batched_rows"],
        "batch_count": report["batch_count"],
        "failure_count": report["failure_count"],
        "output": str(args.output),
    }, ensure_ascii=False))
    return 0 if report["success"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
