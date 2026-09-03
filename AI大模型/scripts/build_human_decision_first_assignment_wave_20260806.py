#!/usr/bin/env python3
"""Build first reviewer assignment wave from the closeout package."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CLOSEOUT = ROOT / "reports" / "human_decision_next_closeout_package_20260806.json"
BATCHES = ROOT / "reports" / "human_decision_review_batches_20260806.json"
DEFAULT_OUTPUT = ROOT / "reports" / "human_decision_first_assignment_wave_20260806.json"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    closeout = json.loads(CLOSEOUT.read_text(encoding="utf-8"))
    batches = json.loads(BATCHES.read_text(encoding="utf-8"))
    by_workstream = {}
    for batch in batches.get("batches", []):
        by_workstream.setdefault(batch.get("workstream"), []).append(batch)

    assignments = []
    for item in closeout.get("items", []):
        workstream = item.get("workstream")
        candidates = sorted(by_workstream.get(workstream, []), key=lambda row: (row.get("batch_number") or 0))
        batch = candidates[0] if candidates else None
        assignments.append({
            "assignment_id": f"ASSIGN_{workstream}_001",
            "workstream": workstream,
            "priority": item.get("priority"),
            "blocker_type": item.get("blocker_type"),
            "target_batch_id": batch.get("batch_id") if batch else None,
            "target_row_count": batch.get("row_count") if batch else 0,
            "pending_row_ids": batch.get("pending_row_ids", []) if batch else [],
            "decision_input": item.get("decision_input"),
            "minimum_required_fields": item.get("minimum_required_fields", []),
            "validate_command": item.get("validate_command"),
            "assigned_reviewer": None,
            "assignment_status": "pending_assignment",
            "formal_decision_rows_written": 0,
            "release_ready": False,
            "safe_for_model_claim": False,
        })

    output = {
        "schema_version": 1,
        "created_at": "2026-08-06",
        "mode": "human_decision_first_assignment_wave",
        "write_policy": "assignment_manifest_only; no_formal_decision_rows_written",
        "summary": {
            "assignment_count": len(assignments),
            "target_rows": sum(int(row["target_row_count"] or 0) for row in assignments),
            "formal_decision_rows_written": 0,
            "release_ready": False,
            "safe_for_model_claim": False,
        },
        "assignments": assignments,
    }
    args.output.write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(output["summary"], ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
