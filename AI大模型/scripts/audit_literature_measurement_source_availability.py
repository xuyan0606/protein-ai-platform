#!/usr/bin/env python3
"""Audit whether evidence-only literature review sources remain locally available."""
from __future__ import annotations
import argparse, json
import hashlib
from pathlib import Path
from typing import Any
ROOT = Path(__file__).resolve().parents[1]
QUEUE = ROOT / "reports/literature_measurement_review_queue.json"
REPORT = ROOT / "reports/literature_measurement_source_availability_report.json"
def build_report(rows: list[dict[str, Any]], root: Path) -> dict[str, Any]:
    records=[]
    for row in rows:
        source=str(row.get("source_path", "")); path=root / source
        expected = str(row.get("source_sha256", ""))
        actual = hashlib.sha256(path.read_bytes()).hexdigest() if source and path.is_file() else ""
        available = bool(source) and path.is_file() and (not expected or actual == expected)
        status = "source_available" if available else ("blocked_missing_local_source" if not path.is_file() else "blocked_hash_mismatch")
        records.append({"review_task_id":row.get("review_task_id"),"source_path":source,"source_available":available,"status":status,"expected_sha256":expected,"actual_sha256":actual})
    available=sum(x["source_available"] for x in records)
    return {"queue_rows":len(rows),"source_available_rows":available,"source_missing_rows":len(rows)-available,"unique_source_paths":len({x["source_path"] for x in records}),"source_complete":available==len(rows),"records":records,"formal_intake_authorized":False,"training_import_allowed":False,"safe_for_model_claim":False,"release_ready":False,"policy":"Availability audit only; missing sources are not downloaded or synthesized."}
def main() -> int:
    p=argparse.ArgumentParser(); p.add_argument("--queue",type=Path,default=QUEUE); p.add_argument("--root",type=Path,default=ROOT); p.add_argument("--report",type=Path,default=REPORT); a=p.parse_args(); rows=json.loads(a.queue.read_text(encoding="utf-8"))["rows"]; report=build_report(rows,a.root); a.report.parent.mkdir(parents=True,exist_ok=True); a.report.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8"); print(json.dumps({k:report[k] for k in ("queue_rows","source_available_rows","source_missing_rows","unique_source_paths","source_complete")},ensure_ascii=False)); return 0 if report["source_complete"] else 1
if __name__ == "__main__": raise SystemExit(main())
