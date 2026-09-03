#!/usr/bin/env python3
import json
from datetime import datetime, timezone
from pathlib import Path
from build_p700_p0_real_input_pending_build_checklist import load_jsonl

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'datasets/governance/p804_p0_pending_build_execution_result_audit_receipt_integrity_gate.jsonl'
OUT = ROOT / 'datasets/governance/p805_p0_pending_build_execution_result_review_decision_conversion_gate.jsonl'
REPORT = ROOT / 'reports/p805_p0_pending_build_execution_result_review_decision_conversion_gate_report.json'
MD = ROOT / 'reports/p805_p0_pending_build_execution_result_review_decision_conversion_gate.md'
FIELDS = ('execution_result_present', 'review_scope_defined', 'reviewer_verified', 'result_reviewed', 'anomalies_assessed', 'remediation_decided', 'decision_evidence_linked', 'formal_decision_written', 'formal_decision_ready', 'production_execution_allowed')

def main():
    created = datetime.now(timezone.utc).isoformat()
    source_rows = [r for r in load_jsonl(SOURCE) if r.get('boundary') != 'summary']
    rows = []
    for i, source in enumerate(source_rows, 1):
        row = {'conversion_gate_id': f"p805::{source.get('integrity_gate_id')}", 'conversion_gate_order': i, 'created_at': created, 'boundary': source.get('boundary'), 'source_p804_id': source.get('integrity_gate_id'), 'gate_status': 'empty_no_verified_result_review_to_decision', 'blocker_reason': 'No authentic execution result, reviewer, anomaly assessment, remediation decision, or linked evidence exists.', 'operator_action': 'Do not review or convert absent results into a formal decision.', 'policy': 'P805 is read-only and fail-closed.'}
        row.update({field: False for field in FIELDS})
        rows.append(row)
    zero = {field + '_rows': 0 for field in FIELDS}
    summary = {'conversion_gate_id': 'p805::summary', 'conversion_gate_order': len(rows) + 1, 'created_at': created, 'boundary': 'summary', 'conversion_gate_rows': len(rows), **zero}
    OUT.write_text(''.join(json.dumps(row, ensure_ascii=False, sort_keys=True) + '\n' for row in rows + [summary]), encoding='utf-8')
    REPORT.write_text(json.dumps({'manifest_id': 'P805', 'created_at': created, 'local_only': True, 'conversion_gate_rows': len(rows), **zero}, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    MD.write_text(f'# P805 execution result review/decision conversion gate\n\nRows: `{len(rows)}`. Formal decisions: `0`.\n', encoding='utf-8')
    print(json.dumps({'manifest_id': 'P805', 'conversion_gate_rows': len(rows), 'formal_decision_written_rows': 0, 'formal_decision_ready_rows': 0}, ensure_ascii=False))
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
