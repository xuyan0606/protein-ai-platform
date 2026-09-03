#!/usr/bin/env python3
import json
from datetime import datetime, timezone
from pathlib import Path
from build_p700_p0_real_input_pending_build_checklist import load_jsonl

ROOT=Path(__file__).resolve().parents[1]
SOURCE=ROOT/'datasets/governance/p800_p0_pending_build_release_package_integrity_gate.jsonl'
OUT=ROOT/'datasets/governance/p801_p0_pending_build_production_change_window_rollback_readiness_gate.jsonl'
REPORT=ROOT/'reports/p801_p0_pending_build_production_change_window_rollback_readiness_gate_report.json'
MD=ROOT/'reports/p801_p0_pending_build_production_change_window_rollback_readiness_gate.md'
FIELDS=('release_package_validated','change_request_present','change_owner_verified','maintenance_window_authorized','rollback_artifact_verified','rollback_operator_confirmed','production_approval_present','production_execution_allowed')

def main():
    created=datetime.now(timezone.utc).isoformat(); src=[r for r in load_jsonl(SOURCE) if r.get('boundary')!='summary']; rows=[]
    for i,s in enumerate(src,1):
        row={'change_gate_id':f"p801::{s.get('release_gate_id')}",'change_gate_order':i,'created_at':created,'boundary':s.get('boundary'),'source_p800_id':s.get('release_gate_id'),'gate_status':'empty_no_authorized_production_change_window','blocker_reason':'No validated release package, change request, authorized window, rollback artifact, or production approval exists.','operator_action':'Do not schedule, approve, start, or simulate a production change.','policy':'P801 is read-only and fail-closed.'}; row.update({f:False for f in FIELDS}); rows.append(row)
    zero={f+'_rows':0 for f in FIELDS}; summary={'change_gate_id':'p801::summary','change_gate_order':len(rows)+1,'created_at':created,'boundary':'summary','change_gate_rows':len(rows),**zero}; OUT.write_text(''.join(json.dumps(r,ensure_ascii=False,sort_keys=True)+'\n' for r in rows+[summary]),encoding='utf-8'); REPORT.write_text(json.dumps({'manifest_id':'P801','created_at':created,'local_only':True,'change_gate_rows':len(rows),**zero},ensure_ascii=False,indent=2)+'\n',encoding='utf-8'); MD.write_text(f'# P801 production change window/rollback readiness gate\n\nRows: `{len(rows)}`. Authorized production windows: `0`.\n',encoding='utf-8'); print(json.dumps({'manifest_id':'P801','change_gate_rows':len(rows),'production_approval_present_rows':0},ensure_ascii=False))

if __name__=='__main__': raise SystemExit(main())
