#!/usr/bin/env python3
import json
from datetime import datetime, timezone
from pathlib import Path
from build_p700_p0_real_input_pending_build_checklist import load_jsonl

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'datasets/governance/p807_p0_pending_build_authorization_expiry_revocation_check_gate.jsonl'
OUT = ROOT / 'datasets/governance/p808_p0_pending_build_authorization_usage_idempotency_replay_guard.jsonl'
REPORT = ROOT / 'reports/p808_p0_pending_build_authorization_usage_idempotency_replay_guard_report.json'
MD = ROOT / 'reports/p808_p0_pending_build_authorization_usage_idempotency_replay_guard.md'
FIELDS = ('authorization_current', 'authorization_nonce_present', 'nonce_integrity_verified', 'usage_limit_defined', 'prior_usage_checked', 'idempotency_key_verified', 'replay_detected', 'authorization_consumed', 'release_ready', 'production_execution_allowed')

def main():
    created = datetime.now(timezone.utc).isoformat()
    source_rows = [r for r in load_jsonl(SOURCE) if r.get('boundary') != 'summary']
    rows = []
    for i, source in enumerate(source_rows, 1):
        row = {'replay_guard_id': f"p808::{source.get('expiry_gate_id')}", 'replay_guard_order': i, 'created_at': created, 'boundary': source.get('boundary'), 'source_p807_id': source.get('expiry_gate_id'), 'gate_status': 'empty_no_current_authorization_to_consume', 'blocker_reason': 'No current authorization, nonce, usage limit, prior-usage check, or verified idempotency key exists.', 'operator_action': 'Do not consume, replay, duplicate, or infer authorization usage.', 'policy': 'P808 is a read-only authorization usage/idempotency/replay guard; it performs no authorization consumption.'}
        row.update({field: False for field in FIELDS})
        rows.append(row)
    zero = {field + '_rows': 0 for field in FIELDS}
    summary = {'replay_guard_id': 'p808::summary', 'replay_guard_order': len(rows) + 1, 'created_at': created, 'boundary': 'summary', 'replay_guard_rows': len(rows), **zero}
    OUT.write_text(''.join(json.dumps(row, ensure_ascii=False, sort_keys=True) + '\n' for row in rows + [summary]), encoding='utf-8')
    REPORT.write_text(json.dumps({'manifest_id': 'P808', 'created_at': created, 'local_only': True, 'replay_guard_rows': len(rows), **zero}, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    MD.write_text(f'# P808 authorization usage/idempotency/replay guard\n\nRows: `{len(rows)}`. Consumed authorizations: `0`. Replay detections: `0`.\n', encoding='utf-8')
    print(json.dumps({'manifest_id': 'P808', 'replay_guard_rows': len(rows), 'authorization_consumed_rows': 0, 'replay_detected_rows': 0}, ensure_ascii=False))
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
