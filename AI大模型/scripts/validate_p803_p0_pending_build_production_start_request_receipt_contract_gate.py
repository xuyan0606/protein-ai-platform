#!/usr/bin/env python3
import json
from datetime import datetime, timezone
from pathlib import Path
from build_p700_p0_real_input_pending_build_checklist import load_json, load_jsonl

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'datasets/governance/p802_p0_pending_build_production_final_preflight_gate.jsonl'
BOARD = ROOT / 'datasets/governance/p803_p0_pending_build_production_start_request_receipt_contract_gate.jsonl'
REPORT = ROOT / 'reports/p803_p0_pending_build_production_start_request_receipt_contract_gate_report.json'
OUT = ROOT / 'reports/p803_p0_pending_build_production_start_request_receipt_contract_gate_validation_report.json'
FIELDS = ('preflight_passed', 'start_request_present', 'start_request_authorized', 'operator_acknowledged', 'start_receipt_present', 'receipt_integrity_validated', 'execution_result_present', 'formal_decision_ready', 'production_execution_started', 'production_execution_allowed')

def main():
    source_rows = [r for r in load_jsonl(SOURCE) if r.get('boundary') != 'summary']
    rows = load_jsonl(BOARD)
    gates, summary = rows[:-1] if rows else [], rows[-1] if rows else {}
    report, failures = load_json(REPORT), []
    def fail(check, condition, observed, expected):
        if condition:
            failures.append({'check': check, 'observed': observed, 'expected': expected})
    fail('source_rows', len(source_rows) != 5, len(source_rows), 5)
    fail('start_gate_rows', len(gates) != 5, len(gates), 5)
    fail('summary', summary.get('boundary') != 'summary', summary.get('boundary'), 'summary')
    for field in FIELDS:
        fail(field, report.get(field + '_rows') != 0, report.get(field + '_rows'), 0)
    for i, row in enumerate(gates, 1):
        fail(f'row_{i}_status', row.get('gate_status') != 'empty_no_authorized_start_request_or_receipt', row.get('gate_status'), 'empty_no_authorized_start_request_or_receipt')
        for field in FIELDS:
            fail(f'row_{i}_{field}', row.get(field) is not False, row.get(field), False)
    result = {'created_at': datetime.now(timezone.utc).isoformat(), 'manifest_id': 'P803', 'local_only': True, 'success': not failures, 'failure_count': len(failures), 'failures': failures, 'start_gate_rows': len(gates), **{field + '_rows': 0 for field in FIELDS}}
    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'success': result['success'], 'start_gate_rows': len(gates), 'start_receipt_present_rows': 0, 'production_execution_started_rows': 0, 'failures': len(failures)}, ensure_ascii=False))
    return 0 if not failures else 1

if __name__ == '__main__':
    raise SystemExit(main())
