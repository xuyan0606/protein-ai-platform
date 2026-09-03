#!/usr/bin/env python3
import json
from datetime import datetime, timezone
from pathlib import Path
from build_p700_p0_real_input_pending_build_checklist import load_jsonl

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "datasets/governance/p791_p0_pending_build_terminal_state_drift_reopen_protection_gate.jsonl"
OUT = ROOT / "datasets/governance/p792_p0_pending_build_governance_evidence_freshness_time_anchor_gate.jsonl"
REPORT = ROOT / "reports/p792_p0_pending_build_governance_evidence_freshness_time_anchor_gate_report.json"
MD = ROOT / "reports/p792_p0_pending_build_governance_evidence_freshness_time_anchor_gate.md"
FIELDS = ("time_anchor_present", "evidence_timestamp_verified", "evidence_fresh", "freshness_window_authorized", "new_input_received", "new_evidence_validated", "authorization_window_validated", "formal_decision_ready", "reopen_authorized", "production_execution_allowed")

def main():
    created = datetime.now(timezone.utc).isoformat()
    source_rows = [r for r in load_jsonl(SOURCE) if r.get("boundary") != "summary"]
    rows = []
    for i, source in enumerate(source_rows, 1):
        row = {"freshness_gate_id": f"p792::{source.get('drift_gate_id')}", "freshness_gate_order": i, "created_at": created, "boundary": source.get("boundary"), "source_p791_id": source.get("drift_gate_id"), "gate_status": "empty_no_verified_fresh_evidence_or_time_anchor", "blocker_reason": "No verified evidence timestamp, freshness window, new input, or authorization window exists to alter the terminal block.", "operator_action": "Do not infer freshness, accept unstamped evidence, reopen, or execute downstream work.", "policy": "P792 is a read-only evidence freshness/time-anchor gate; it performs no validation attestation or authorization."}
        row.update({field: False for field in FIELDS})
        rows.append(row)
    zero = {field + "_rows": 0 for field in FIELDS}
    summary = {"freshness_gate_id": "p792::summary", "freshness_gate_order": len(rows) + 1, "created_at": created, "boundary": "summary", "freshness_gate_rows": len(rows), **zero, "policy": "P792 remains empty and fail-closed."}
    OUT.write_text("".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows + [summary]), encoding="utf-8")
    report = {"manifest_id": "P792", "created_at": created, "local_only": True, "freshness_gate_rows": len(rows), **zero, "artifact_jsonl": str(OUT.relative_to(ROOT)), "artifact_md": str(MD.relative_to(ROOT)), "policy": "P792 is monitoring-only and fail-closed."}
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    MD.write_text(f"# P792 governance evidence freshness/time-anchor gate\n\nRows: `{len(rows)}`. Fresh evidence rows: `0`.\n", encoding="utf-8")
    print(json.dumps({"manifest_id": "P792", "freshness_gate_rows": len(rows), "evidence_fresh_rows": 0, "output": str(REPORT)}, ensure_ascii=False))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
