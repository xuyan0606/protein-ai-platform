#!/usr/bin/env python3
import json
from datetime import datetime, timezone
from pathlib import Path
from build_p700_p0_real_input_pending_build_checklist import load_jsonl

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'datasets/governance/p802_p0_pending_build_production_final_preflight_gate.jsonl'
OUT = ROOT / 'datasets/governance/p803_p0_pending_build_production_start_request_receipt_contract_gate.jsonl'
REPORT = ROOT / 'reports/p803_p0_pending_build_production_start_request_receipt_contract_gate_report.json'
MD = ROOT / 'reports/p803_p0_pending_build_production_start_request_receipt_contract_gate.md'
FIELDS = ('preflight_passed', 'start_request_present', 'start_request_authorized', 'operator_acknowledged', 'start_receipt_present', 'receipt_integrity_validated', 'execution_result_present', 'formal_decision_ready', 'production_execution_started', 'production_execution_allowed')

def main():
    created = datetime.now(timezone.utc).isoformat()
    source_rows = [r for r in load_jsonl(SOURCE) if r.get('boundary') != 'summary']
    rows = []
    for i, source in enumerate(source_rows, 1):
        row = {'start_gate_id': f"p803::{source.get('preflight_gate_id')}", 'start_gate_order': i, 'created_at': created, 'boundary': source.get('boundary'), 'source_p802_id': source.get('preflight_gate_id'), 'gate_status': 'empty_no_authorized_start_request_or_receipt', 'blocker_reason': 'No passed preflight, authorized start request, operator acknowledgement, start receipt, or execution result exists.', 'operator_action': 'Do not dispatch, acknowledge, start, or fabricate a production execution receipt.', 'policy': 'P803 is read-only and fail-closed.'}
        row.update({field: False for field in FIELDS})
        rows.append(row)
    zero = {field + '_rows': 0 for field in FIELDS}
    summary = {'start_gate_id': 'p803::summary', 'start_gate_order': len(rows) + 1, 'created_at': created, 'boundary': 'summary', 'start_gate_rows': len(rows), **zero}
    OUT.write_text(''.join(json.dumps(row, ensure_ascii=False, sort_keys=True) + '\n' for row in rows + [summary]), encoding='utf-8')
    REPORT.write_text(json.dumps({'manifest_id': 'P803', 'created_at': created, 'local_only': True, 'start_gate_rows': len(rows), **zero}, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    MD.write_text(f'# P803 production start request/receipt contract gate\n\nRows: `{len(rows)}`. Start receipts: `0`.\n', encoding='utf-8')
    print(json.dumps({'manifest_id': 'P803', 'start_gate_rows': len(rows), 'start_receipt_present_rows': 0, 'production_execution_started_rows': 0}, ensure_ascii=False))
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
