#!/usr/bin/env python3
"""Create and validate local human decisions for literature measurement tasks."""
from __future__ import annotations
import argparse, json
from datetime import datetime
from pathlib import Path
from typing import Any
ROOT = Path(__file__).resolve().parents[1]
QUEUE = ROOT / "reports/literature_measurement_review_queue.json"
DECISIONS = ROOT / "datasets/curation/literature_measurement_review_decisions.local.jsonl"
REPORT = ROOT / "reports/literature_measurement_review_decision_validation_report.json"

def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines() if x.strip()] if path.exists() else []
def load_queue(path: Path) -> list[dict[str, Any]]:
    return json.loads(path.read_text(encoding="utf-8"))["rows"]
def valid_time(value: Any) -> bool:
    try: datetime.fromisoformat(str(value).replace("Z", "+00:00")); return True
    except (TypeError, ValueError): return False
def validate_decision(row: dict[str, Any], queue_row: dict[str, Any]) -> list[str]:
    errors=[]
    if row.get("review_task_id") != queue_row.get("review_task_id"): errors.append("review_task_id_mismatch")
    if row.get("measurement_ids") != queue_row.get("measurement_ids"): errors.append("measurement_ids_mismatch")
    if row.get("decision") not in {"approved_for_intake", "rejected"}: errors.append("decision_missing_or_invalid")
    if not row.get("reviewer"): errors.append("reviewer_missing")
    if not valid_time(row.get("reviewed_at")): errors.append("reviewed_at_missing_or_invalid")
    if not row.get("review_basis"): errors.append("review_basis_missing")
    if not row.get("authorization_receipt"): errors.append("authorization_receipt_missing")
    return errors
def build_report(queue: list[dict[str, Any]], decisions: list[dict[str, Any]]) -> dict[str, Any]:
    by_id={str(x.get("review_task_id")):x for x in queue}; seen=set(); records=[]; global_errors=[]
    for row in decisions:
        task_id=str(row.get("review_task_id")); errors=validate_decision(row,by_id.get(task_id,{}))
        if task_id in seen:
            errors.append("duplicate_review_task_id")
            if "duplicate_review_task_id" not in global_errors: global_errors.append("duplicate_review_task_id")
        seen.add(task_id); records.append({"review_task_id":row.get("review_task_id"),"decision":row.get("decision"),"valid":not errors,"errors":errors})
    if set(by_id)-seen: global_errors.append("missing_decision_for_queue_row")
    pending_rows = sum(1 for x in records if x["decision"] == "pending") + len(set(by_id) - seen)
    return {"queue_rows":len(queue),"decision_rows":len(decisions),"valid_rows":sum(x["valid"] for x in records),"approved_rows":sum(x["valid"] and x["decision"]=="approved_for_intake" for x in records),"pending_rows":pending_rows,"global_errors":global_errors,"records":records,"formal_intake_authorized":False,"training_import_allowed":False,"safe_for_model_claim":False,"release_ready":False,"policy":"Local human decision record only; explicit downstream authorization is separately required."}
def main() -> int:
    p=argparse.ArgumentParser(); p.add_argument("--queue",type=Path,default=QUEUE); p.add_argument("--decisions",type=Path,default=DECISIONS); p.add_argument("--report",type=Path,default=REPORT); p.add_argument("--write-template",action="store_true"); a=p.parse_args(); queue=load_queue(a.queue)
    if a.write_template and not a.decisions.exists():
        a.decisions.parent.mkdir(parents=True,exist_ok=True); a.decisions.write_text("".join(json.dumps({"review_task_id":r["review_task_id"],"measurement_ids":r["measurement_ids"],"decision":"pending","reviewer":"","reviewed_at":"","review_basis":"","authorization_receipt":"","notes":""},ensure_ascii=False,sort_keys=True)+"\n" for r in queue),encoding="utf-8")
    report=build_report(queue,load_jsonl(a.decisions)); a.report.parent.mkdir(parents=True,exist_ok=True); a.report.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8"); print(json.dumps(report,ensure_ascii=False)); return 0 if not report["global_errors"] and report["valid_rows"]==len(queue) else 1
if __name__ == "__main__": raise SystemExit(main())
