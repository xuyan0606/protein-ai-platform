#!/usr/bin/env python3
import json
from datetime import datetime,timezone
from pathlib import Path
from build_p700_p0_real_input_pending_build_checklist import load_json,load_jsonl
ROOT=Path(__file__).resolve().parents[1]; SOURCE=ROOT/'datasets/governance/p798_p0_pending_build_independent_review_dual_approval_gate.jsonl'; BOARD=ROOT/'datasets/governance/p799_p0_pending_build_formal_decision_package_completeness_gate.jsonl'; REPORT=ROOT/'reports/p799_p0_pending_build_formal_decision_package_completeness_gate_report.json'; OUT=ROOT/'reports/p799_p0_pending_build_formal_decision_package_completeness_gate_validation_report.json'; FIELDS=('input_complete','evidence_complete','scope_complete','risk_complete','independent_review_complete','dual_approval_complete','formal_decision_package_complete','formal_decision_ready','release_ready','production_execution_allowed')
def main():
 src=[r for r in load_jsonl(SOURCE) if r.get('boundary')!='summary']; rows=load_jsonl(BOARD); gates,summary=rows[:-1] if rows else [],rows[-1] if rows else {}; rep=load_json(REPORT); fails=[]
 def f(c,x,o,e):
  if x:fails.append({'check':c,'observed':o,'expected':e})
 f('source_rows',len(src)!=5,len(src),5); f('decision_gate_rows',len(gates)!=5,len(gates),5); f('summary',summary.get('boundary')!='summary',summary.get('boundary'),'summary')
 for x in FIELDS:f(x,rep.get(x+'_rows')!=0,rep.get(x+'_rows'),0)
 for i,r in enumerate(gates,1):
  f(f'row_{i}_status',r.get('gate_status')!='empty_no_complete_formal_decision_package',r.get('gate_status'),'empty_no_complete_formal_decision_package')
  for x in FIELDS:f(f'row_{i}_{x}',r.get(x) is not False,r.get(x),False)
 result={'created_at':datetime.now(timezone.utc).isoformat(),'manifest_id':'P799','local_only':True,'success':not fails,'failure_count':len(fails),'failures':fails,'decision_gate_rows':len(gates),**{x+'_rows':0 for x in FIELDS}}; OUT.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8'); print(json.dumps({'success':result['success'],'decision_gate_rows':len(gates),'formal_decision_package_complete_rows':0,'failures':len(fails)},ensure_ascii=False)); return 0 if not fails else 1
if __name__=='__main__': raise SystemExit(main())
