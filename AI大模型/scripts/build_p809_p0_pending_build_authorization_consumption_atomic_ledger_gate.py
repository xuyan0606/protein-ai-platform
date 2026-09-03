#!/usr/bin/env python3
import json
from datetime import datetime, timezone
from pathlib import Path
from build_p700_p0_real_input_pending_build_checklist import load_jsonl

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'datasets/governance/p808_p0_pending_build_authorization_usage_idempotency_replay_guard.jsonl'
OUT = ROOT / 'datasets/governance/p809_p0_pending_build_authorization_consumption_atomic_ledger_gate.jsonl'
REPORT = ROOT / 'reports/p809_p0_pending_build_authorization_consumption_atomic_ledger_gate_report.json'
MD = ROOT / 'reports/p809_p0_pending_build_authorization_consumption_atomic_ledger_gate.md'
FIELDS = ('authorization_consumed', 'ledger_entry_present', 'atomic_commit_verified', 'partial_write_detected', 'ledger_hash_verified', 'usage_counter_updated', 'duplicate_consumption_detected', 'audit_receipt_present', 'release_ready', 'production_execution_allowed')

def main():
    created = datetime.now(timezone.utc).isoformat()
    source_rows = [r for r in load_jsonl(SOURCE) if r.get('boundary') != 'summary']
    rows = []
    for i, source in enumerate(source_rows, 1):
        row = {'ledger_gate_id': f"p809::{source.get('replay_guard_id')}", 'ledger_gate_order': i, 'created_at': created, 'boundary': source.get('boundary'), 'source_p808_id': source.get('replay_guard_id'), 'gate_status': 'empty_no_authorization_consumption_to_ledger', 'blocker_reason': 'No consumed authorization, atomic ledger entry, usage-counter update, or audit receipt exists.', 'operator_action': 'Do not create, backfill, duplicate, or attest an authorization-consumption ledger entry.', 'policy': 'P809 is a read-only authorization consumption atomic-ledger gate; it performs no consumption or ledger mutation.'}
        row.update({field: False for field in FIELDS})
        rows.append(row)
    zero = {field + '_rows': 0 for field in FIELDS}
    summary = {'ledger_gate_id': 'p809::summary', 'ledger_gate_order': len(rows) + 1, 'created_at': created, 'boundary': 'summary', 'ledger_gate_rows': len(rows), **zero}
    OUT.write_text(''.join(json.dumps(row, ensure_ascii=False, sort_keys=True) + '\n' for row in rows + [summary]), encoding='utf-8')
    REPORT.write_text(json.dumps({'manifest_id': 'P809', 'created_at': created, 'local_only': True, 'ledger_gate_rows': len(rows), **zero}, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    MD.write_text(f'# P809 authorization consumption atomic-ledger gate\n\nRows: `{len(rows)}`. Ledger entries: `0`.\n', encoding='utf-8')
    print(json.dumps({'manifest_id': 'P809', 'ledger_gate_rows': len(rows), 'ledger_entry_present_rows': 0, 'audit_receipt_present_rows': 0}, ensure_ascii=False))
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
