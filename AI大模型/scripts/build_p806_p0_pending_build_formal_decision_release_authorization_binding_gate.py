#!/usr/bin/env python3
import json
from datetime import datetime, timezone
from pathlib import Path
from build_p700_p0_real_input_pending_build_checklist import load_jsonl

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'datasets/governance/p805_p0_pending_build_execution_result_review_decision_conversion_gate.jsonl'
OUT = ROOT / 'datasets/governance/p806_p0_pending_build_formal_decision_release_authorization_binding_gate.jsonl'
REPORT = ROOT / 'reports/p806_p0_pending_build_formal_decision_release_authorization_binding_gate_report.json'
MD = ROOT / 'reports/p806_p0_pending_build_formal_decision_release_authorization_binding_gate.md'
FIELDS = ('formal_decision_written', 'decision_signed', 'decision_effective', 'authorizer_identity_verified', 'authorization_scope_bound', 'authorization_expiry_bound', 'release_binding_validated', 'production_authorization_present', 'release_ready', 'production_execution_allowed')

def main():
    created = datetime.now(timezone.utc).isoformat()
    source_rows = [r for r in load_jsonl(SOURCE) if r.get('boundary') != 'summary']
    rows = []
    for i, source in enumerate(source_rows, 1):
        row = {'binding_gate_id': f"p806::{source.get('conversion_gate_id')}", 'binding_gate_order': i, 'created_at': created, 'boundary': source.get('boundary'), 'source_p805_id': source.get('conversion_gate_id'), 'gate_status': 'empty_no_signed_decision_to_bind_authorization', 'blocker_reason': 'No written or signed formal decision, verified authorizer, bounded scope/expiry, or release authorization exists.', 'operator_action': 'Do not sign, bind, extend, or infer formal decision authorization.', 'policy': 'P806 is read-only and fail-closed.'}
        row.update({field: False for field in FIELDS})
        rows.append(row)
    zero = {field + '_rows': 0 for field in FIELDS}
    summary = {'binding_gate_id': 'p806::summary', 'binding_gate_order': len(rows) + 1, 'created_at': created, 'boundary': 'summary', 'binding_gate_rows': len(rows), **zero}
    OUT.write_text(''.join(json.dumps(row, ensure_ascii=False, sort_keys=True) + '\n' for row in rows + [summary]), encoding='utf-8')
    REPORT.write_text(json.dumps({'manifest_id': 'P806', 'created_at': created, 'local_only': True, 'binding_gate_rows': len(rows), **zero}, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    MD.write_text(f'# P806 formal decision/release authorization binding gate\n\nRows: `{len(rows)}`. Bound authorizations: `0`.\n', encoding='utf-8')
    print(json.dumps({'manifest_id': 'P806', 'binding_gate_rows': len(rows), 'release_binding_validated_rows': 0, 'production_authorization_present_rows': 0}, ensure_ascii=False))
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
