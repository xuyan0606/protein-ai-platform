#!/usr/bin/env python3
"""Validate batch status aggregates against dispatch tasks and decisions."""
from __future__ import annotations
import argparse, json
from pathlib import Path
from typing import Any
ROOT = Path(__file__).resolve().parents[1]
BATCHES = ROOT / "datasets/curation/literature_measurement_review_batches.jsonl"
DECISIONS = ROOT / "datasets/curation/literature_measurement_review_decisions.local.jsonl"
STATUS = ROOT / "datasets/curation/literature_measurement_review_batch_status.jsonl"
REPORT = ROOT / "reports/literature_measurement_review_batch_status_validation_report.json"
def load_jsonl(path: Path) -> list[dict[str, Any]]: return [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines() if x.strip()] if path.exists() else []
def validate_status(batches: list[dict[str, Any]], decisions: list[dict[str, Any]], statuses: list[dict[str, Any]]) -> dict[str, Any]:
    decisions_by_task={str(x.get("review_task_id")):str(x.get("decision", "pending")) for x in decisions}; status_by_batch={str(x.get("batch_id")):x for x in statuses}; failures=[]
    for batch in batches:
        bid=str(batch.get("batch_id")); expected=[decisions_by_task.get(str(t), "pending") for t in batch.get("tasks", [])]; actual=status_by_batch.get(bid)
        if not actual: failures.append("missing_batch_status"); continue
        counts={"task_rows":len(expected),"pending_rows":sum(x=="pending" for x in expected),"approved_rows":sum(x=="approved_for_intake" for x in expected),"rejected_rows":sum(x=="rejected" for x in expected),"unknown_decision_rows":sum(x not in {"pending","approved_for_intake","rejected"} for x in expected)}
        if any(int(actual.get(k, -1)) != v for k,v in counts.items()): failures.append("status_count_mismatch")
    if set(status_by_batch) != {str(x.get("batch_id")) for x in batches}: failures.append("batch_coverage_mismatch")
    return {"success":not failures,"batch_rows":len(batches),"status_rows":len(statuses),"failures":sorted(set(failures)),"training_import_allowed":False,"safe_for_model_claim":False,"release_ready":False,"policy":"Status validation only; no authorization or formal intake is created."}
def main() -> int:
    p=argparse.ArgumentParser(); p.add_argument("--batches",type=Path,default=BATCHES); p.add_argument("--decisions",type=Path,default=DECISIONS); p.add_argument("--status",type=Path,default=STATUS); p.add_argument("--report",type=Path,default=REPORT); a=p.parse_args(); result=validate_status(load_jsonl(a.batches),load_jsonl(a.decisions),load_jsonl(a.status)); a.report.parent.mkdir(parents=True,exist_ok=True); a.report.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8"); print(json.dumps(result,ensure_ascii=False)); return 0 if result["success"] else 1
if __name__ == "__main__": raise SystemExit(main())
