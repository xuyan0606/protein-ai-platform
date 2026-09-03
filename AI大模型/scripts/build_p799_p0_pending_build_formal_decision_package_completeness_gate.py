#!/usr/bin/env python3
import json
from datetime import datetime, timezone
from pathlib import Path
from build_p700_p0_real_input_pending_build_checklist import load_jsonl
ROOT=Path(__file__).resolve().parents[1]; SOURCE=ROOT/'datasets/governance/p798_p0_pending_build_independent_review_dual_approval_gate.jsonl'; OUT=ROOT/'datasets/governance/p799_p0_pending_build_formal_decision_package_completeness_gate.jsonl'; REPORT=ROOT/'reports/p799_p0_pending_build_formal_decision_package_completeness_gate_report.json'; MD=ROOT/'reports/p799_p0_pending_build_formal_decision_package_completeness_gate.md'
FIELDS=('input_complete','evidence_complete','scope_complete','risk_complete','independent_review_complete','dual_approval_complete','formal_decision_package_complete','formal_decision_ready','release_ready','production_execution_allowed')
def main():
 c=datetime.now(timezone.utc).isoformat(); src=[r for r in load_jsonl(SOURCE) if r.get('boundary')!='summary']; rows=[]
 for i,s in enumerate(src,1):
  r={'decision_gate_id':f"p799::{s.get('review_gate_id')}",'decision_gate_order':i,'created_at':c,'boundary':s.get('boundary'),'source_p798_id':s.get('review_gate_id'),'gate_status':'empty_no_complete_formal_decision_package','blocker_reason':'Required input, evidence, scope, risk, review, and approval components are absent.','operator_action':'Do not assemble, infer, or sign a formal decision package.','policy':'P799 is read-only and fail-closed.'}; r.update({f:False for f in FIELDS}); rows.append(r)
 z={f+'_rows':0 for f in FIELDS}; summary={'decision_gate_id':'p799::summary','decision_gate_order':len(rows)+1,'created_at':c,'boundary':'summary','decision_gate_rows':len(rows),**z,'policy':'P799 remains empty and fail-closed.'}; OUT.write_text(''.join(json.dumps(r,ensure_ascii=False,sort_keys=True)+'\n' for r in rows+[summary]),encoding='utf-8'); REPORT.write_text(json.dumps({'manifest_id':'P799','created_at':c,'local_only':True,'decision_gate_rows':len(rows),**z,'artifact_jsonl':str(OUT.relative_to(ROOT)),'artifact_md':str(MD.relative_to(ROOT))},ensure_ascii=False,indent=2)+'\n',encoding='utf-8'); MD.write_text(f'# P799 formal decision package completeness gate\n\nRows: `{len(rows)}`. Complete packages: `0`.\n',encoding='utf-8'); print(json.dumps({'manifest_id':'P799','decision_gate_rows':len(rows),'formal_decision_package_complete_rows':0},ensure_ascii=False))
if __name__=='__main__': raise SystemExit(main())
