#!/usr/bin/env python3
"""Aggregate local literature review decisions by dispatch batch."""
from __future__ import annotations
import argparse, json
from pathlib import Path
from typing import Any
ROOT = Path(__file__).resolve().parents[1]
BATCHES = ROOT / "datasets/curation/literature_measurement_review_batches.jsonl"
DECISIONS = ROOT / "datasets/curation/literature_measurement_review_decisions.local.jsonl"
OUTPUT = ROOT / "datasets/curation/literature_measurement_review_batch_status.jsonl"
REPORT = ROOT / "reports/literature_measurement_review_batch_status_report.json"
def load_jsonl(path: Path) -> list[dict[str, Any]]: return [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines() if x.strip()] if path.exists() else []
def build_status(batches: list[dict[str, Any]], decisions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_task={str(x.get("review_task_id")):str(x.get("decision", "pending")) for x in decisions}; rows=[]
    for batch in batches:
        values=[by_task.get(str(task), "pending") for task in batch.get("tasks", [])]
        rows.append({"batch_id":batch.get("batch_id"),"task_rows":len(values),"pending_rows":sum(x=="pending" for x in values),"approved_rows":sum(x=="approved_for_intake" for x in values),"rejected_rows":sum(x=="rejected" for x in values),"unknown_decision_rows":sum(x not in {"pending","approved_for_intake","rejected"} for x in values),"status":"pending_human_review" if any(x=="pending" for x in values) else "reviewed_pending_separate_intake","formal_intake_authorized":False,"training_import_allowed":False,"safe_for_model_claim":False,"release_ready":False})
    return rows
def main() -> int:
    p=argparse.ArgumentParser(); p.add_argument("--batches",type=Path,default=BATCHES); p.add_argument("--decisions",type=Path,default=DECISIONS); p.add_argument("--output",type=Path,default=OUTPUT); p.add_argument("--report",type=Path,default=REPORT); a=p.parse_args(); rows=build_status(load_jsonl(a.batches),load_jsonl(a.decisions)); a.output.parent.mkdir(parents=True,exist_ok=True); a.output.write_text("".join(json.dumps(x,ensure_ascii=False,sort_keys=True)+"\n" for x in rows),encoding="utf-8")
    report={"batch_rows":len(rows),"task_rows":sum(x["task_rows"] for x in rows),"pending_rows":sum(x["pending_rows"] for x in rows),"approved_rows":sum(x["approved_rows"] for x in rows),"rejected_rows":sum(x["rejected_rows"] for x in rows),"training_import_allowed":False,"safe_for_model_claim":False,"release_ready":False,"policy":"Progress aggregation only; formal intake remains independently gated."}; a.report.parent.mkdir(parents=True,exist_ok=True); a.report.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8"); print(json.dumps(report,ensure_ascii=False)); return 0
if __name__ == "__main__": raise SystemExit(main())
