#!/usr/bin/env python3
"""Validate review templates cover unresolved records exactly once and remain non-formal."""
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
REPORT=ROOT/"reports/numbering_decision_review_batch_report.json"
DECISIONS=ROOT/"datasets/curation/numbering_curation_decisions.jsonl"
OUT=ROOT/"reports/numbering_decision_review_batch_validation_report.json"

def load_jsonl(path):
    return [json.loads(line) for line in Path(path).read_text(encoding="utf-8").splitlines() if line.strip()]

def main():
    report=json.loads(REPORT.read_text(encoding="utf-8")); decided={str(r.get("record_id")) for r in load_jsonl(DECISIONS)}; rows=[]; failures=[]
    for batch in report.get("batches") or []: rows.extend(load_jsonl(batch["template"]))
    ids=[str(r.get("record_id")) for r in rows]
    def fail(check,condition,observed,expected):
        if condition: failures.append({"check":check,"observed":observed,"expected":expected})
    fail("batch_rows",report.get("batch_rows")!=20,report.get("batch_rows"),20)
    fail("template_rows",len(rows)!=471,len(rows),471)
    fail("unique_records",len(ids)!=len(set(ids)),len(ids),len(set(ids)))
    fail("decided_overlap",bool(set(ids)&decided),sorted(set(ids)&decided),[])
    for i,row in enumerate(rows,1):
        fail(f"row_{i}_draft",row.get("review_draft") is not True,row.get("review_draft"),True)
        fail(f"row_{i}_pending",row.get("human_review_status")!="pending",row.get("human_review_status"),"pending")
        fail(f"row_{i}_confirmed",row.get("human_confirmed") is not False,row.get("human_confirmed"),False)
        fail(f"row_{i}_formal",row.get("formal_write_allowed") is not False,row.get("formal_write_allowed"),False)
        fail(f"row_{i}_reviewer",row.get("reviewer")!="",row.get("reviewer"),"")
    result={"success":not failures,"failure_count":len(failures),"failures":failures,"batch_rows":report.get("batch_rows"),"template_rows":len(rows),"unique_record_rows":len(set(ids)),"decided_overlap_rows":len(set(ids)&decided),"human_confirmed_rows":sum(r.get("human_confirmed") is True for r in rows),"formal_write_allowed_rows":sum(r.get("formal_write_allowed") is True for r in rows)}
    OUT.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8"); print(json.dumps(result,ensure_ascii=False)); return 0 if not failures else 1

if __name__=="__main__": raise SystemExit(main())
