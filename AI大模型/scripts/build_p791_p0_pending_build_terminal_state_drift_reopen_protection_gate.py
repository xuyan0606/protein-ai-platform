#!/usr/bin/env python3
import json
from datetime import datetime, timezone
from pathlib import Path
from build_p700_p0_real_input_pending_build_checklist import load_jsonl

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "datasets/governance/p790_p0_pending_build_terminal_production_governance_consistency_rollup.jsonl"
OUT = ROOT / "datasets/governance/p791_p0_pending_build_terminal_state_drift_reopen_protection_gate.jsonl"
REPORT = ROOT / "reports/p791_p0_pending_build_terminal_state_drift_reopen_protection_gate_report.json"
MD = ROOT / "reports/p791_p0_pending_build_terminal_state_drift_reopen_protection_gate.md"
FIELDS = ("baseline_consistent", "state_drift_detected", "reopen_requested", "new_input_received", "new_evidence_validated", "reopen_authorized", "formal_decision_ready", "release_ready", "production_execution_allowed", "terminal_unblocked")

def main():
    created = datetime.now(timezone.utc).isoformat()
    source_rows = [r for r in load_jsonl(SOURCE) if r.get("boundary") != "summary"]
    rows = []
    for i, source in enumerate(source_rows, 1):
        row = {"drift_gate_id": f"p791::{source.get('rollup_id')}", "drift_gate_order": i, "created_at": created, "boundary": source.get("boundary"), "source_p790_id": source.get("rollup_id"), "gate_status": "terminal_state_consistent_no_reopen_basis", "blocker_reason": "No verified state drift, new input, evidence, or authorization exists to reopen a terminally blocked lane.", "operator_action": "Observe and revalidate only; do not reopen, infer progress, or execute downstream work.", "policy": "P791 is a read-only state-drift and reopen-protection gate; it performs no reopen or authorization."}
        row.update({field: False for field in FIELDS})
        rows.append(row)
    zero = {field + "_rows": 0 for field in FIELDS}
    summary = {"drift_gate_id": "p791::summary", "drift_gate_order": len(rows) + 1, "created_at": created, "boundary": "summary", "drift_gate_rows": len(rows), **zero, "policy": "P791 remains terminal and fail-closed."}
    OUT.write_text("".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows + [summary]), encoding="utf-8")
    report = {"manifest_id": "P791", "created_at": created, "local_only": True, "drift_gate_rows": len(rows), **zero, "artifact_jsonl": str(OUT.relative_to(ROOT)), "artifact_md": str(MD.relative_to(ROOT)), "policy": "P791 is monitoring-only and fail-closed."}
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    MD.write_text(f"# P791 terminal state drift/reopen protection gate\n\nRows: `{len(rows)}`. Reopen-authorized states: `0`.\n", encoding="utf-8")
    print(json.dumps({"manifest_id": "P791", "drift_gate_rows": len(rows), "reopen_authorized_rows": 0, "terminal_unblocked_rows": 0, "output": str(REPORT)}, ensure_ascii=False))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
