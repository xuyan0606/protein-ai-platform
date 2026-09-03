#!/usr/bin/env python3
import json
from datetime import datetime, timezone
from pathlib import Path
from build_p700_p0_real_input_pending_build_checklist import load_jsonl

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "datasets/governance/p789_p0_pending_build_production_audit_receipt_access_disclosure_non_leak_gate.jsonl"
OUT = ROOT / "datasets/governance/p790_p0_pending_build_terminal_production_governance_consistency_rollup.jsonl"
REPORT = ROOT / "reports/p790_p0_pending_build_terminal_production_governance_consistency_rollup_report.json"
MD = ROOT / "reports/p790_p0_pending_build_terminal_production_governance_consistency_rollup.md"
FIELDS = ("real_input_received", "evidence_validated", "formal_decision_ready", "authorization_granted", "release_ready", "customer_delivery_ready", "production_execution_allowed", "audit_receipt_present", "receipt_retrieved", "disclosure_approved", "terminal_unblocked")

def main():
    created = datetime.now(timezone.utc).isoformat()
    source_rows = [r for r in load_jsonl(SOURCE) if r.get("boundary") != "summary"]
    rows = []
    for i, source in enumerate(source_rows, 1):
        row = {"rollup_id": f"p790::{source.get('access_gate_id')}", "rollup_order": i, "created_at": created, "boundary": source.get("boundary"), "source_p789_id": source.get("access_gate_id"), "rollup_status": "terminal_governance_blocked", "blocker_reason": "No verified input, evidence, decision, authorization, release, delivery, audit receipt, or disclosure state exists to support an unblocked terminal state.", "operator_action": "Observe and revalidate only; do not infer completion or execute downstream work.", "policy": "P790 is a read-only terminal consistency rollup; it performs no execution, authorization, release, retrieval, or disclosure."}
        row.update({field: False for field in FIELDS})
        rows.append(row)
    zero = {field + "_rows": 0 for field in FIELDS}
    summary = {"rollup_id": "p790::summary", "rollup_order": len(rows) + 1, "created_at": created, "boundary": "summary", "rollup_rows": len(rows), **zero, "policy": "P790 remains terminal and fail-closed."}
    OUT.write_text("".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows + [summary]), encoding="utf-8")
    report = {"manifest_id": "P790", "created_at": created, "local_only": True, "rollup_rows": len(rows), **zero, "artifact_jsonl": str(OUT.relative_to(ROOT)), "artifact_md": str(MD.relative_to(ROOT)), "policy": "P790 is monitoring-only and fail-closed."}
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    MD.write_text(f"# P790 terminal production governance consistency rollup\n\nRows: `{len(rows)}`. Unblocked terminal states: `0`.\n", encoding="utf-8")
    print(json.dumps({"manifest_id": "P790", "rollup_rows": len(rows), "terminal_unblocked_rows": 0, "production_execution_allowed_rows": 0, "output": str(REPORT)}, ensure_ascii=False))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
