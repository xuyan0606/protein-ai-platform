#!/usr/bin/env python3
import json
from datetime import datetime, timezone
from pathlib import Path
from build_p700_p0_real_input_pending_build_checklist import load_jsonl

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'datasets/governance/p801_p0_pending_build_production_change_window_rollback_readiness_gate.jsonl'
OUT = ROOT / 'datasets/governance/p802_p0_pending_build_production_final_preflight_gate.jsonl'
REPORT = ROOT / 'reports/p802_p0_pending_build_production_final_preflight_gate_report.json'
MD = ROOT / 'reports/p802_p0_pending_build_production_final_preflight_gate.md'
FIELDS = ('release_validated', 'change_approved', 'window_validated', 'rollback_validated', 'operator_verified', 'monitoring_ready', 'preflight_passed', 'execution_request_authorized', 'production_execution_started', 'audit_receipt_present')

def main():
    created = datetime.now(timezone.utc).isoformat()
    source_rows = [r for r in load_jsonl(SOURCE) if r.get('boundary') != 'summary']
    rows = []
    for i, source in enumerate(source_rows, 1):
        row = {'preflight_gate_id': f"p802::{source.get('change_gate_id')}", 'preflight_gate_order': i, 'created_at': created, 'boundary': source.get('boundary'), 'source_p801_id': source.get('change_gate_id'), 'gate_status': 'empty_no_authorized_production_preflight', 'blocker_reason': 'No validated release, change approval, window, rollback, operator, monitoring, or execution authorization exists.', 'operator_action': 'Do not pass preflight or start production execution.', 'policy': 'P802 is read-only and fail-closed.'}
        row.update({field: False for field in FIELDS})
        rows.append(row)
    zero = {field + '_rows': 0 for field in FIELDS}
    summary = {'preflight_gate_id': 'p802::summary', 'preflight_gate_order': len(rows) + 1, 'created_at': created, 'boundary': 'summary', 'preflight_gate_rows': len(rows), **zero}
    OUT.write_text(''.join(json.dumps(row, ensure_ascii=False, sort_keys=True) + '\n' for row in rows + [summary]), encoding='utf-8')
    REPORT.write_text(json.dumps({'manifest_id': 'P802', 'created_at': created, 'local_only': True, 'preflight_gate_rows': len(rows), **zero}, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    MD.write_text(f'# P802 production final preflight gate\n\nRows: `{len(rows)}`. Preflight-passed rows: `0`.\n', encoding='utf-8')
    print(json.dumps({'manifest_id': 'P802', 'preflight_gate_rows': len(rows), 'preflight_passed_rows': 0}, ensure_ascii=False))
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
