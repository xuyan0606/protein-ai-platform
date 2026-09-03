#!/usr/bin/env python3
"""Validate one-to-one, lane-consistent literature review dispatch batches."""
from __future__ import annotations
import argparse, json
from pathlib import Path
from typing import Any
ROOT = Path(__file__).resolve().parents[1]
QUEUE = ROOT / "reports/literature_measurement_review_queue.json"
BATCHES = ROOT / "datasets/curation/literature_measurement_review_batches.jsonl"
REPORT = ROOT / "reports/literature_measurement_review_batches_validation_report.json"
def load_jsonl(path: Path) -> list[dict[str, Any]]: return [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines() if x.strip()]
def build_report(queue: list[dict[str, Any]], batches: list[dict[str, Any]], batch_size: int) -> dict[str, Any]:
    source = {str(x.get("review_task_id")): x for x in queue}; assigned=[]; failures=[]
    for batch in batches:
        tasks = batch.get("tasks", [])
        if len(tasks) != int(batch.get("task_count", -1)): failures.append("task_count_mismatch")
        if len(tasks) > batch_size: failures.append("batch_size_exceeded")
        for task in tasks:
            row = source.get(str(task))
            if not row: failures.append("unknown_task_assignment"); continue
            assigned.append(str(task))
            if row.get("review_priority") != batch.get("review_priority") or row.get("review_lane") != batch.get("review_lane"): failures.append("task_priority_or_lane_mismatch")
    if len(assigned) != len(set(assigned)): failures.append("duplicate_task_assignment")
    if set(source) != set(assigned): failures.append("queue_coverage_mismatch")
    failures = sorted(set(failures))
    return {"success": not failures, "queue_rows": len(queue), "batch_rows": len(batches), "assigned_task_rows": len(assigned), "unique_assigned_task_rows": len(set(assigned)), "failures": failures, "training_import_allowed": False, "safe_for_model_claim": False, "release_ready": False, "policy": "Dispatch validation only; no decision, intake, or authorization is created."}
def main() -> int:
    p=argparse.ArgumentParser(); p.add_argument("--queue",type=Path,default=QUEUE); p.add_argument("--batches",type=Path,default=BATCHES); p.add_argument("--report",type=Path,default=REPORT); p.add_argument("--batch-size",type=int,default=10); a=p.parse_args()
    queue=json.loads(a.queue.read_text(encoding="utf-8"))["rows"]; report=build_report(queue,load_jsonl(a.batches),a.batch_size); a.report.parent.mkdir(parents=True,exist_ok=True); a.report.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8"); print(json.dumps(report,ensure_ascii=False)); return 0 if report["success"] else 1
if __name__ == "__main__": raise SystemExit(main())
