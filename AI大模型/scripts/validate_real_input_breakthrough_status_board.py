#!/usr/bin/env python3
import json
from pathlib import Path
from build_p700_p0_real_input_pending_build_checklist import load_json, load_jsonl

ROOT=Path(__file__).resolve().parents[1]
BOARD=ROOT/"datasets/governance/real_input_breakthrough_status_board.jsonl"
REPORT=ROOT/"reports/real_input_breakthrough_status_board_report.json"
OUT=ROOT/"reports/real_input_breakthrough_status_board_validation_report.json"

def main():
    rows=load_jsonl(BOARD); lanes=rows[:-1] if rows else []; summary=rows[-1] if rows else {}; report=load_json(REPORT); failures=[]
    def fail(check, condition, observed, expected):
        if condition: failures.append({"check":check,"observed":observed,"expected":expected})
    fail("lane_rows",len(lanes)!=5,len(lanes),5)
    fail("summary",summary.get("lane")!="summary",summary.get("lane"),"summary")
    fail("lane_set",{r.get("lane") for r in lanes}!={"plate_feedback","strict_holdout","substrate_identity","numbering_curation","governance"},sorted(r.get("lane") for r in lanes),"five canonical lanes")
    fail("structure_ready_rows",report.get("structure_ready_rows")!=5,report.get("structure_ready_rows"),5)
    numbering=next((r for r in lanes if r.get("lane")=="numbering_curation"),{})
    fail("numbering_validated",numbering.get("validated_formal_rows")!=4,numbering.get("validated_formal_rows"),4)
    fail("numbering_applied",numbering.get("applied_rows")!=4,numbering.get("applied_rows"),4)
    for row in lanes:
        fail(f"{row.get('lane')}.nonnegative",any(int(row.get(k) or 0)<0 for k in ("candidate_or_draft_rows","validated_formal_rows","applied_rows","remaining_rows")),row,"nonnegative counts")
    result={"success":not failures,"failure_count":len(failures),"failures":failures,"lane_rows":len(lanes),"structure_ready_rows":report.get("structure_ready_rows"),"numbering_validated_rows":numbering.get("validated_formal_rows"),"numbering_applied_rows":numbering.get("applied_rows"),"remaining_rows":report.get("remaining_rows")}
    OUT.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8"); print(json.dumps(result,ensure_ascii=False)); return 0 if not failures else 1

if __name__=="__main__": raise SystemExit(main())
