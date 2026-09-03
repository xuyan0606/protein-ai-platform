#!/usr/bin/env python3
"""Build independent, non-authorizing packets for parallel human review."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
BATCHES = ROOT / "datasets/curation/literature_measurement_review_batches.jsonl"
QUEUE = ROOT / "reports/literature_measurement_review_queue.json"
OUTPUT = ROOT / "reports/literature_measurement_review_dispatch.json"


def build_dispatch(batches: list[dict[str, Any]], queue: list[dict[str, Any]]) -> dict[str, Any]:
    by_id = {str(row.get("review_task_id")): row for row in queue}
    packets = []
    seen: set[str] = set()
    for batch in batches:
        task_ids = [str(task) for task in batch.get("tasks", [])]
        missing = [task for task in task_ids if task not in by_id]
        if missing:
            raise ValueError(f"unknown review task(s): {','.join(missing)}")
        if seen.intersection(task_ids):
            raise ValueError("review task assigned to multiple dispatch packets")
        seen.update(task_ids)
        packets.append({
            "packet_id": f"dispatch::{batch.get('batch_id')}",
            "batch_id": batch.get("batch_id"),
            "review_priority": batch.get("review_priority"),
            "review_lane": batch.get("review_lane"),
            "task_ids": task_ids,
            "tasks": [{"review_task_id": task, "source_path": by_id[task].get("source_path"), "source_sha256": by_id[task].get("source_sha256"), "measurement_ids": by_id[task].get("measurement_ids")} for task in task_ids],
            "decision_output": "datasets/curation/literature_measurement_review_decisions.local.jsonl",
            "formal_intake_authorized": False,
            "training_import_allowed": False,
            "safe_for_model_claim": False,
            "release_ready": False,
        })
    if seen != set(by_id):
        raise ValueError("queue tasks not assigned to a dispatch packet")
    return {"packet_count": len(packets), "task_count": len(seen), "packets": packets, "formal_intake_authorized": False, "training_import_allowed": False, "safe_for_model_claim": False, "release_ready": False, "policy": "Dispatch only; reviewers must submit independently validated human decisions."}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--batches", type=Path, default=BATCHES)
    parser.add_argument("--queue", type=Path, default=QUEUE)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    args = parser.parse_args()
    result = build_dispatch(load_jsonl(args.batches), json.loads(args.queue.read_text(encoding="utf-8"))["rows"])
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({key: result[key] for key in ("packet_count", "task_count", "formal_intake_authorized")}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
