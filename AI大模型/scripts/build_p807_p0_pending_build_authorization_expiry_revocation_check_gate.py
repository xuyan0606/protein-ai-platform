#!/usr/bin/env python3
import json
from datetime import datetime, timezone
from pathlib import Path
from build_p700_p0_real_input_pending_build_checklist import load_jsonl

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'datasets/governance/p806_p0_pending_build_formal_decision_release_authorization_binding_gate.jsonl'
OUT = ROOT / 'datasets/governance/p807_p0_pending_build_authorization_expiry_revocation_check_gate.jsonl'
REPORT = ROOT / 'reports/p807_p0_pending_build_authorization_expiry_revocation_check_gate_report.json'
MD = ROOT / 'reports/p807_p0_pending_build_authorization_expiry_revocation_check_gate.md'
FIELDS = ('authorization_present', 'effective_at_verified', 'expiry_at_verified', 'authorization_current', 'revocation_status_checked', 'authorization_revoked', 'scope_still_valid', 'formal_decision_ready', 'release_ready', 'production_execution_allowed')

def main():
    created = datetime.now(timezone.utc).isoformat()
    source_rows = [r for r in load_jsonl(SOURCE) if r.get('boundary') != 'summary']
    rows = []
    for i, source in enumerate(source_rows, 1):
        row = {'expiry_gate_id': f"p807::{source.get('binding_gate_id')}", 'expiry_gate_order': i, 'created_at': created, 'boundary': source.get('boundary'), 'source_p806_id': source.get('binding_gate_id'), 'gate_status': 'empty_no_current_authorization_to_expiry_check', 'blocker_reason': 'No authorization record, effective/expiry timestamps, current status, revocation check, or valid scope exists.', 'operator_action': 'Do not extend, renew, ignore expiry, or infer current authorization.', 'policy': 'P807 is read-only and fail-closed.'}
        row.update({field: False for field in FIELDS})
        rows.append(row)
    zero = {field + '_rows': 0 for field in FIELDS}
    summary = {'expiry_gate_id': 'p807::summary', 'expiry_gate_order': len(rows) + 1, 'created_at': created, 'boundary': 'summary', 'expiry_gate_rows': len(rows), **zero}
    OUT.write_text(''.join(json.dumps(row, ensure_ascii=False, sort_keys=True) + '\n' for row in rows + [summary]), encoding='utf-8')
    REPORT.write_text(json.dumps({'manifest_id': 'P807', 'created_at': created, 'local_only': True, 'expiry_gate_rows': len(rows), **zero}, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    MD.write_text(f'# P807 authorization expiry/revocation check gate\n\nRows: `{len(rows)}`. Current authorizations: `0`.\n', encoding='utf-8')
    print(json.dumps({'manifest_id': 'P807', 'expiry_gate_rows': len(rows), 'authorization_current_rows': 0, 'production_execution_allowed_rows': 0}, ensure_ascii=False))
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
