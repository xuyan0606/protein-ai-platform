#!/usr/bin/env python3
"""Fail closed when literature review workflow reports disagree."""
from __future__ import annotations
import argparse, json
from pathlib import Path
from typing import Any
ROOT = Path(__file__).resolve().parents[1]
FILES = {
    "queue": ROOT / "reports/literature_measurement_review_queue_validation_report.json",
    "decisions": ROOT / "reports/literature_measurement_review_decision_validation_report.json",
    "batches": ROOT / "reports/literature_measurement_review_batches_validation_report.json",
    "status": ROOT / "reports/literature_measurement_review_batch_status_report.json",
    "status_validation": ROOT / "reports/literature_measurement_review_batch_status_validation_report.json",
    "preview": ROOT / "reports/literature_measurement_approved_preview.json",
}
OUTPUT = ROOT / "reports/literature_measurement_review_healthcheck_report.json"
def read(path: Path) -> dict[str, Any]: return json.loads(path.read_text(encoding="utf-8"))
def build_report(queue: dict[str, Any], decisions: dict[str, Any], batches: dict[str, Any], status: dict[str, Any], status_validation: dict[str, Any], preview: dict[str, Any]) -> dict[str, Any]:
    failures=[]
    if queue.get("valid_rows") != queue.get("queue_rows"): failures.append("queue_validation_failed")
    if batches.get("success") is not True or status_validation.get("success") is not True: failures.append("downstream_validation_failed")
    expected = queue.get("queue_rows")
    if any(x.get(k) != expected for x,k in ((decisions,"queue_rows"),(batches,"queue_rows"),(batches,"assigned_task_rows"),(status,"task_rows"))): failures.append("task_count_mismatch")
    if decisions.get("approved_rows") != status.get("approved_rows") or decisions.get("approved_rows") != preview.get("approved_preview_rows"): failures.append("approved_count_mismatch")
    if decisions.get("pending_rows") != status.get("pending_rows"): failures.append("pending_count_mismatch")
    return {"success":not failures,"queue_rows":expected,"decision_rows":decisions.get("decision_rows"),"batch_rows":status.get("batch_rows"),"pending_rows":decisions.get("pending_rows"),"approved_rows":decisions.get("approved_rows"),"rejected_rows":status.get("rejected_rows"),"failures":sorted(set(failures)),"formal_intake_authorized":False,"training_import_allowed":False,"safe_for_model_claim":False,"release_ready":False,"policy":"Cross-artifact healthcheck only; no decision is promoted or applied."}
def main() -> int:
    p=argparse.ArgumentParser(); p.add_argument("--output",type=Path,default=OUTPUT); a=p.parse_args(); values={k:read(v) for k,v in FILES.items()}; report=build_report(**values); a.output.parent.mkdir(parents=True,exist_ok=True); a.output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8"); print(json.dumps(report,ensure_ascii=False)); return 0 if report["success"] else 1
if __name__ == "__main__": raise SystemExit(main())
