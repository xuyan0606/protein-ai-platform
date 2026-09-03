#!/usr/bin/env python3
import json
from datetime import datetime, timezone
from pathlib import Path
from build_p700_p0_real_input_pending_build_checklist import load_jsonl

ROOT=Path(__file__).resolve().parents[1]
SOURCE=ROOT/'datasets/governance/p799_p0_pending_build_formal_decision_package_completeness_gate.jsonl'
OUT=ROOT/'datasets/governance/p800_p0_pending_build_release_package_integrity_gate.jsonl'
REPORT=ROOT/'reports/p800_p0_pending_build_release_package_integrity_gate_report.json'
MD=ROOT/'reports/p800_p0_pending_build_release_package_integrity_gate.md'
FIELDS=('decision_approved','artifact_manifest_complete','artifact_hash_verified','dependency_manifest_complete','rollback_plan_verified','customer_scope_verified','release_package_integrity_validated','release_ready','production_execution_allowed')

def main():
    created=datetime.now(timezone.utc).isoformat(); src=[r for r in load_jsonl(SOURCE) if r.get('boundary')!='summary']; rows=[]
    for i,s in enumerate(src,1):
        row={'release_gate_id':f"p800::{s.get('decision_gate_id')}",'release_gate_order':i,'created_at':created,'boundary':s.get('boundary'),'source_p799_id':s.get('decision_gate_id'),'gate_status':'empty_no_integrity_validated_release_package','blocker_reason':'No approved decision, complete manifest, verified hashes, rollback plan, or customer scope exists for release.','operator_action':'Do not assemble, sign, promote, or publish a release package.','policy':'P800 is read-only and fail-closed.'}; row.update({f:False for f in FIELDS}); rows.append(row)
    zero={f+'_rows':0 for f in FIELDS}; summary={'release_gate_id':'p800::summary','release_gate_order':len(rows)+1,'created_at':created,'boundary':'summary','release_gate_rows':len(rows),**zero}; OUT.write_text(''.join(json.dumps(r,ensure_ascii=False,sort_keys=True)+'\n' for r in rows+[summary]),encoding='utf-8'); REPORT.write_text(json.dumps({'manifest_id':'P800','created_at':created,'local_only':True,'release_gate_rows':len(rows),**zero},ensure_ascii=False,indent=2)+'\n',encoding='utf-8'); MD.write_text(f'# P800 release package integrity gate\n\nRows: `{len(rows)}`. Integrity-validated packages: `0`.\n',encoding='utf-8'); print(json.dumps({'manifest_id':'P800','release_gate_rows':len(rows),'release_package_integrity_validated_rows':0},ensure_ascii=False))

if __name__=='__main__': raise SystemExit(main())
