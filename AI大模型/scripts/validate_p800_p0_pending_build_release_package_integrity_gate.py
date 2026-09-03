#!/usr/bin/env python3
import json
from datetime import datetime, timezone
from pathlib import Path
from build_p700_p0_real_input_pending_build_checklist import load_json, load_jsonl
ROOT=Path(__file__).resolve().parents[1]
SOURCE=ROOT/'datasets/governance/p799_p0_pending_build_formal_decision_package_completeness_gate.jsonl'; BOARD=ROOT/'datasets/governance/p800_p0_pending_build_release_package_integrity_gate.jsonl'; REPORT=ROOT/'reports/p800_p0_pending_build_release_package_integrity_gate_report.json'; OUT=ROOT/'reports/p800_p0_pending_build_release_package_integrity_gate_validation_report.json'
FIELDS=('decision_approved','artifact_manifest_complete','artifact_hash_verified','dependency_manifest_complete','rollback_plan_verified','customer_scope_verified','release_package_integrity_validated','release_ready','production_execution_allowed')
def main():
    src=[r for r in load_jsonl(SOURCE) if r.get('boundary')!='summary']; rows=load_jsonl(BOARD); gates,summary=rows[:-1] if rows else [],rows[-1] if rows else {}; rep=load_json(REPORT); failures=[]
    def fail(c,x,o,e):
        if x: failures.append({'check':c,'observed':o,'expected':e})
    fail('source_rows',len(src)!=5,len(src),5); fail('release_gate_rows',len(gates)!=5,len(gates),5); fail('summary',summary.get('boundary')!='summary',summary.get('boundary'),'summary')
    for field in FIELDS: fail(field,rep.get(field+'_rows')!=0,rep.get(field+'_rows'),0)
    for i,row in enumerate(gates,1):
        fail(f'row_{i}_status',row.get('gate_status')!='empty_no_integrity_validated_release_package',row.get('gate_status'),'empty_no_integrity_validated_release_package')
        for field in FIELDS: fail(f'row_{i}_{field}',row.get(field) is not False,row.get(field),False)
    result={'created_at':datetime.now(timezone.utc).isoformat(),'manifest_id':'P800','local_only':True,'success':not failures,'failure_count':len(failures),'failures':failures,'release_gate_rows':len(gates),**{f+'_rows':0 for f in FIELDS}}; OUT.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8'); print(json.dumps({'success':result['success'],'release_gate_rows':len(gates),'release_package_integrity_validated_rows':0,'failures':len(failures)},ensure_ascii=False)); return 0 if not failures else 1
if __name__=='__main__': raise SystemExit(main())
