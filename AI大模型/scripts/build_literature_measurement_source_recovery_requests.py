#!/usr/bin/env python3
"""Build local-only source recovery requests for blocked literature review tasks."""
from __future__ import annotations
import argparse, json
from collections import defaultdict
from pathlib import Path
from typing import Any
ROOT = Path(__file__).resolve().parents[1]
QUEUE = ROOT / "reports/literature_measurement_review_queue.json"
OUTPUT = ROOT / "datasets/curation/literature_measurement_source_recovery_requests.jsonl"
REPORT = ROOT / "reports/literature_measurement_source_recovery_requests_report.json"
def build_requests(rows: list[dict[str, Any]], root: Path) -> dict[str, Any]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        source=str(row.get("source_path", ""))
        if not source or not (root / source).is_file(): grouped[source].append(row)
    requests=[]
    for source, items in sorted(grouped.items()):
        requests.append({"request_id":f"literature-source-recovery::{source}","source_path":source,"expected_sha256":sorted({str(x.get("source_sha256", "")) for x in items}),"pmcids":sorted({str(x.get("pmcid", "")) for x in items}),"dois":sorted({str(x.get("doi", "")) for x in items}),"review_task_ids":sorted(str(x.get("review_task_id")) for x in items),"affected_task_count":len(items),"status":"blocked_missing_local_source","recovery_action":"restore exact source file and verify SHA-256 before review resumes","training_import_allowed":False,"safe_for_model_claim":False,"release_ready":False})
    return {"requests":requests,"queue_rows":len(rows),"missing_source_request_rows":len(requests),"affected_task_rows":sum(x["affected_task_count"] for x in requests),"formal_intake_authorized":False,"training_import_allowed":False,"safe_for_model_claim":False,"release_ready":False,"policy":"Recovery request only; no source is downloaded, synthesized, or promoted."}
def main() -> int:
    p=argparse.ArgumentParser(); p.add_argument("--queue",type=Path,default=QUEUE); p.add_argument("--root",type=Path,default=ROOT); p.add_argument("--output",type=Path,default=OUTPUT); p.add_argument("--report",type=Path,default=REPORT); a=p.parse_args(); rows=json.loads(a.queue.read_text(encoding="utf-8"))["rows"]; result=build_requests(rows,a.root); a.output.parent.mkdir(parents=True,exist_ok=True); a.output.write_text("".join(json.dumps(x,ensure_ascii=False,sort_keys=True)+"\n" for x in result["requests"]),encoding="utf-8"); a.report.parent.mkdir(parents=True,exist_ok=True); a.report.write_text(json.dumps({k:v for k,v in result.items() if k!="requests"},ensure_ascii=False,indent=2)+"\n",encoding="utf-8"); print(json.dumps({k:v for k,v in result.items() if k!="requests"},ensure_ascii=False)); return 0
if __name__ == "__main__": raise SystemExit(main())
