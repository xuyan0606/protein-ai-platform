#!/usr/bin/env python3
import json
from datetime import datetime, timezone
from pathlib import Path
from build_p700_p0_real_input_pending_build_checklist import load_jsonl

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'datasets/governance/p803_p0_pending_build_production_start_request_receipt_contract_gate.jsonl'
OUT = ROOT / 'datasets/governance/p804_p0_pending_build_execution_result_audit_receipt_integrity_gate.jsonl'
REPORT = ROOT / 'reports/p804_p0_pending_build_execution_result_audit_receipt_integrity_gate_report.json'
MD = ROOT / 'reports/p804_p0_pending_build_execution_result_audit_receipt_integrity_gate.md'
FIELDS = ('execution_started', 'execution_result_present', 'result_complete', 'audit_receipt_present', 'receipt_atomic', 'receipt_hash_verified', 'receipt_signature_verified', 'provenance_complete', 'formal_decision_ready', 'production_execution_allowed')

def main():
    created = datetime.now(timezone.utc).isoformat()
    source_rows = [r for r in load_jsonl(SOURCE) if r.get('boundary') != 'summary']
    rows = []
    for i, source in enumerate(source_rows, 1):
        row = {'integrity_gate_id': f"p804::{source.get('start_gate_id')}", 'integrity_gate_order': i, 'created_at': created, 'boundary': source.get('boundary'), 'source_p803_id': source.get('start_gate_id'), 'gate_status': 'empty_no_authentic_execution_result_or_audit_receipt', 'blocker_reason': 'No authentic production execution, complete result, atomic audit receipt, verified hash/signature, or provenance exists.', 'operator_action': 'Do not synthesize, complete, attest, or promote an execution result or audit receipt.', 'policy': 'P804 is read-only and fail-closed.'}
        row.update({field: False for field in FIELDS})
        rows.append(row)
    zero = {field + '_rows': 0 for field in FIELDS}
    summary = {'integrity_gate_id': 'p804::summary', 'integrity_gate_order': len(rows) + 1, 'created_at': created, 'boundary': 'summary', 'integrity_gate_rows': len(rows), **zero}
    OUT.write_text(''.join(json.dumps(row, ensure_ascii=False, sort_keys=True) + '\n' for row in rows + [summary]), encoding='utf-8')
    REPORT.write_text(json.dumps({'manifest_id': 'P804', 'created_at': created, 'local_only': True, 'integrity_gate_rows': len(rows), **zero}, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    MD.write_text(f'# P804 execution result/audit receipt integrity gate\n\nRows: `{len(rows)}`. Authentic results: `0`.\n', encoding='utf-8')
    print(json.dumps({'manifest_id': 'P804', 'integrity_gate_rows': len(rows), 'execution_result_present_rows': 0, 'audit_receipt_present_rows': 0}, ensure_ascii=False))
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
