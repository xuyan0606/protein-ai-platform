#!/usr/bin/env python3
import json
from datetime import datetime, timezone
from pathlib import Path
from build_p700_p0_real_input_pending_build_checklist import load_json, load_jsonl

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'datasets/governance/p807_p0_pending_build_authorization_expiry_revocation_check_gate.jsonl'
BOARD = ROOT / 'datasets/governance/p808_p0_pending_build_authorization_usage_idempotency_replay_guard.jsonl'
REPORT = ROOT / 'reports/p808_p0_pending_build_authorization_usage_idempotency_replay_guard_report.json'
OUT = ROOT / 'reports/p808_p0_pending_build_authorization_usage_idempotency_replay_guard_validation_report.json'
FIELDS = ('authorization_current', 'authorization_nonce_present', 'nonce_integrity_verified', 'usage_limit_defined', 'prior_usage_checked', 'idempotency_key_verified', 'replay_detected', 'authorization_consumed', 'release_ready', 'production_execution_allowed')

def main():
    source_rows = [r for r in load_jsonl(SOURCE) if r.get('boundary') != 'summary']
    rows = load_jsonl(BOARD)
    gates, summary = rows[:-1] if rows else [], rows[-1] if rows else {}
    report, failures = load_json(REPORT), []
    def fail(check, condition, observed, expected):
        if condition:
            failures.append({'check': check, 'observed': observed, 'expected': expected})
    fail('source_rows', len(source_rows) != 5, len(source_rows), 5)
    fail('replay_guard_rows', len(gates) != 5, len(gates), 5)
    fail('summary', summary.get('boundary') != 'summary', summary.get('boundary'), 'summary')
    for field in FIELDS:
        fail(field, report.get(field + '_rows') != 0, report.get(field + '_rows'), 0)
    for i, row in enumerate(gates, 1):
        fail(f'row_{i}_status', row.get('gate_status') != 'empty_no_current_authorization_to_consume', row.get('gate_status'), 'empty_no_current_authorization_to_consume')
        for field in FIELDS:
            fail(f'row_{i}_{field}', row.get(field) is not False, row.get(field), False)
    result = {'created_at': datetime.now(timezone.utc).isoformat(), 'manifest_id': 'P808', 'local_only': True, 'success': not failures, 'failure_count': len(failures), 'failures': failures, 'replay_guard_rows': len(gates), **{field + '_rows': 0 for field in FIELDS}}
    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'success': result['success'], 'replay_guard_rows': len(gates), 'authorization_consumed_rows': 0, 'replay_detected_rows': 0, 'failures': len(failures)}, ensure_ascii=False))
    return 0 if not failures else 1

if __name__ == '__main__':
    raise SystemExit(main())
