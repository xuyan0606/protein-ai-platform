#!/usr/bin/env python3
"""Build deterministic, bounded dispatch batches for literature review."""
from __future__ import annotations
import argparse, json
from collections import defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
INPUT = ROOT / "reports/literature_measurement_review_queue.json"
OUTPUT = ROOT / "datasets/curation/literature_measurement_review_batches.jsonl"
REPORT = ROOT / "reports/literature_measurement_review_batches_report.json"

def build_batches(rows: list[dict[str, Any]], batch_size: int = 10) -> list[dict[str, Any]]:
    groups = defaultdict(list)
    for row in rows:
        groups[(str(row.get("review_priority", "P9")), str(row.get("review_lane", "unclassified")))].append(row)
    output = []
    for priority, lane in sorted(groups):
        items = sorted(groups[(priority, lane)], key=lambda r: str(r.get("review_task_id", "")))
        for offset in range(0, len(items), batch_size):
            chunk = items[offset:offset + batch_size]
            output.append({"batch_id": f"literature-review-{priority}-{lane}-{offset // batch_size + 1:03d}", "review_priority": priority, "review_lane": lane, "task_count": len(chunk), "measurement_count": sum(int(r.get("measurement_count", 0) or 0) for r in chunk), "tasks": [r.get("review_task_id") for r in chunk], "status": "ready_for_parallel_human_review", "training_import_allowed": False, "safe_for_model_claim": False, "release_ready": False})
    return output

def main() -> int:
    p = argparse.ArgumentParser(); p.add_argument("--input", type=Path, default=INPUT); p.add_argument("--output", type=Path, default=OUTPUT); p.add_argument("--report", type=Path, default=REPORT); p.add_argument("--batch-size", type=int, default=10); a = p.parse_args()
    rows = json.loads(a.input.read_text(encoding="utf-8"))["rows"]; batches = build_batches(rows, max(1, a.batch_size))
    a.output.parent.mkdir(parents=True, exist_ok=True); a.output.write_text("".join(json.dumps(x, ensure_ascii=False, sort_keys=True) + "\n" for x in batches), encoding="utf-8")
    report = {"queue_rows": len(rows), "batch_rows": len(batches), "task_rows_in_batches": sum(x["task_count"] for x in batches), "measurement_rows_in_batches": sum(x["measurement_count"] for x in batches), "parallel_review_ready": True, "training_import_allowed": False, "safe_for_model_claim": False, "release_ready": False, "policy": "Dispatch planning only; no human decision or formal intake is written."}
    a.report.parent.mkdir(parents=True, exist_ok=True); a.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"); print(json.dumps(report, ensure_ascii=False)); return 0
if __name__ == "__main__": raise SystemExit(main())
