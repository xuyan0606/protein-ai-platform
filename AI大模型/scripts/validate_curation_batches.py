#!/usr/bin/env python3
"""Validate numbering work batches exclude completed decisions and have no duplicates."""
import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
QUEUE = ROOT / "datasets/curation/numbering_curation_queue.jsonl"
DECISIONS = ROOT / "datasets/curation/numbering_curation_decisions.jsonl"
REPORT = ROOT / "reports/curation_batch_report.json"
OUT = ROOT / "reports/curation_batch_validation_report.json"

def load_jsonl(path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]

def main():
    parser=argparse.ArgumentParser(); parser.add_argument("--queue",type=Path,default=QUEUE); parser.add_argument("--decisions",type=Path,default=DECISIONS); parser.add_argument("--report",type=Path,default=REPORT); parser.add_argument("--output",type=Path,default=OUT); args=parser.parse_args()
    report=json.loads(args.report.read_text(encoding="utf-8")); queue=load_jsonl(args.queue); decisions=load_jsonl(args.decisions); decided={str(r.get("record_id")) for r in decisions if r.get("record_id")}; priority=report.get("priority"); priority_ids={str(r.get("record_id")) for r in queue if r.get("priority")==priority}; priority_decided=decided & priority_ids; expected=priority_ids-decided; batch_rows=[]; failures=[]
    for batch in report.get("batches") or []:
        batch_rows.extend(load_jsonl(Path(batch["jsonl"])))
    ids=[str(r.get("record_id")) for r in batch_rows]
    def fail(check,condition,observed,expected_value):
        if condition: failures.append({"check":check,"observed":observed,"expected":expected_value})
    fail("available_rows",report.get("available_rows")!=len(expected),report.get("available_rows"),len(expected))
    fail("already_decided_rows",report.get("already_decided_rows")!=len(priority_decided),report.get("already_decided_rows"),len(priority_decided))
    fail("no_decided_overlap",bool(set(ids)&decided),sorted(set(ids)&decided),[])
    fail("unique_batch_ids",len(ids)!=len(set(ids)),len(ids),len(set(ids)))
    fail("covered_rows",report.get("covered_rows")!=len(ids),report.get("covered_rows"),len(ids))
    fail("batch_subset",not set(ids).issubset(expected),sorted(set(ids)-expected),[])
    result={"success":not failures,"failure_count":len(failures),"failures":failures,"available_undecided_rows":len(expected),"already_decided_rows":len(priority_decided),"covered_rows":len(ids),"duplicate_rows":len(ids)-len(set(ids)),"decided_overlap_rows":len(set(ids)&decided)}
    args.output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8"); print(json.dumps(result,ensure_ascii=False)); return 0 if not failures else 1

if __name__=="__main__": raise SystemExit(main())
