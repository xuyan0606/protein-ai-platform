#!/usr/bin/env python3
import json
from datetime import datetime, timezone
from pathlib import Path
from build_p700_p0_real_input_pending_build_checklist import load_json, load_jsonl

ROOT=Path(__file__).resolve().parents[1]
SOURCE=ROOT/'datasets/governance/p800_p0_pending_build_release_package_integrity_gate.jsonl'; BOARD=ROOT/'datasets/governance/p801_p0_pending_build_production_change_window_rollback_readiness_gate.jsonl'; REPORT=ROOT/'reports/p801_p0_pending_build_production_change_window_rollback_readiness_gate_report.json'; OUT=ROOT/'reports/p801_p0_pending_build_production_change_window_rollback_readiness_gate_validation_report.json'
FIELDS=('release_package_validated','change_request_present','change_owner_verified','maintenance_window_authorized','rollback_artifact_verified','rollback_operator_confirmed','production_approval_present','production_execution_allowed')
def main():
    src=[r for r in load_jsonl(SOURCE) if r.get('boundary')!='summary']; rows=load_jsonl(BOARD); gates,summary=rows[:-1] if rows else [],rows[-1] if rows else {}; rep=load_json(REPORT); failures=[]
    def fail(c,x,o,e):
        if x: failures.append({'check':c,'observed':o,'expected':e})
    fail('source_rows',len(src)!=5,len(src),5); fail('change_gate_rows',len(gates)!=5,len(gates),5); fail('summary',summary.get('boundary')!='summary',summary.get('boundary'),'summary')
    for field in FIELDS: fail(field,rep.get(field+'_rows')!=0,rep.get(field+'_rows'),0)
    for i,row in enumerate(gates,1):
        fail(f'row_{i}_status',row.get('gate_status')!='empty_no_authorized_production_change_window',row.get('gate_status'),'empty_no_authorized_production_change_window')
        for field in FIELDS: fail(f'row_{i}_{field}',row.get(field) is not False,row.get(field),False)
    result={'created_at':datetime.now(timezone.utc).isoformat(),'manifest_id':'P801','local_only':True,'success':not failures,'failure_count':len(failures),'failures':failures,'change_gate_rows':len(gates),**{f+'_rows':0 for f in FIELDS}}; OUT.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8'); print(json.dumps({'success':result['success'],'change_gate_rows':len(gates),'production_approval_present_rows':0,'production_execution_allowed_rows':0,'failures':len(failures)},ensure_ascii=False)); return 0 if not failures else 1
if __name__=='__main__': raise SystemExit(main())
