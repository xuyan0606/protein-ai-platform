#!/usr/bin/env python3
"""Materialize review-ready decision templates for all unresolved numbering batches."""
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPORTS = [ROOT/f"reports/curation_batch_{p}_report.json" for p in ("p0","p1","p2")]
DRAFTS = ROOT/"datasets/curation/numbering_deterministic_reject_decisions.review_draft.jsonl"
OUT = ROOT/"reports/numbering_decision_review_batch_report.json"

def load_jsonl(path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]

def resolve(path):
    path=Path(path)
    if path.is_absolute(): return path
    candidate=Path.cwd()/path
    return candidate if candidate.exists() else ROOT/path

def main():
    created=datetime.now(timezone.utc).isoformat(); drafts={str(r.get("record_id")):r for r in load_jsonl(DRAFTS)}; batches=[]; missing=[]
    for report_path in REPORTS:
        report=json.loads(report_path.read_text(encoding="utf-8"))
        for batch in report.get("batches") or []:
            source_path=resolve(batch["jsonl"]); source_rows=load_jsonl(source_path); templates=[]
            for source in source_rows:
                record_id=str(source.get("record_id")); draft=drafts.get(record_id)
                if not draft:
                    missing.append(record_id); continue
                row=dict(draft); row.update({"batch_id":batch["batch_id"],"priority":report["priority"],"human_review_status":"pending","human_confirmed":False,"formal_write_allowed":False,"reviewer":"","reviewed_at":"","review_basis":""}); templates.append(row)
            template_path=source_path.with_name(f"{batch['batch_id']}.decision_review_template.jsonl")
            md_path=source_path.with_name(f"{batch['batch_id']}.decision_review_checklist.md")
            template_path.write_text("".join(json.dumps(r,ensure_ascii=False,sort_keys=True)+"\n" for r in templates),encoding="utf-8")
            md_path.write_text("\n".join([f"# {batch['batch_id']} decision review","",f"Rows: {len(templates)}","","For each row, verify source references and mutation mismatch, then fill reviewer, reviewed_at, review_basis, human_review_status, and human_confirmed.","","Do not copy to the formal decision file unless human_confirmed=true and the formal validator passes.",""]),encoding="utf-8")
            batches.append({"batch_id":batch["batch_id"],"priority":report["priority"],"rows":len(templates),"source":str(source_path),"template":str(template_path),"checklist":str(md_path)})
    result={"created_at":created,"success":not missing,"batch_rows":len(batches),"template_rows":sum(b["rows"] for b in batches),"missing_draft_rows":len(missing),"missing_record_ids":missing,"formal_decisions_written":0,"policy":"Templates only; human confirmation and formal validation are required before any decision write.","batches":batches}
    OUT.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8"); print(json.dumps({k:result[k] for k in ("success","batch_rows","template_rows","missing_draft_rows","formal_decisions_written")},ensure_ascii=False)); return 0 if not missing else 1

if __name__=="__main__": raise SystemExit(main())
