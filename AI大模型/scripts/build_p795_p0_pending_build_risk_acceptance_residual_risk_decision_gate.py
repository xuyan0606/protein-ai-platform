#!/usr/bin/env python3
import json
from datetime import datetime, timezone
from pathlib import Path
from build_p700_p0_real_input_pending_build_checklist import load_jsonl

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "datasets/governance/p794_p0_pending_build_evidence_scope_claim_mapping_gate.jsonl"
OUT = ROOT / "datasets/governance/p795_p0_pending_build_risk_acceptance_residual_risk_decision_gate.jsonl"
REPORT = ROOT / "reports/p795_p0_pending_build_risk_acceptance_residual_risk_decision_gate_report.json"
MD = ROOT / "reports/p795_p0_pending_build_risk_acceptance_residual_risk_decision_gate.md"
FIELDS = ("risk_assessment_present", "hazards_identified", "mitigations_validated", "residual_risk_calculated", "risk_owner_verified", "risk_acceptance_authorized", "formal_decision_ready", "release_ready", "production_execution_allowed")

def main():
    created = datetime.now(timezone.utc).isoformat()
    source_rows = [r for r in load_jsonl(SOURCE) if r.get("boundary") != "summary"]
    rows = []
    for i, source in enumerate(source_rows, 1):
        row = {"risk_gate_id": f"p795::{source.get('scope_gate_id')}", "risk_gate_order": i, "created_at": created, "boundary": source.get("boundary"), "source_p794_id": source.get("scope_gate_id"), "gate_status": "empty_no_authorized_risk_acceptance", "blocker_reason": "No verified risk assessment, mitigation, residual-risk calculation, owner, or acceptance authorization exists.", "operator_action": "Do not calculate, accept, waive, or infer residual risk; keep downstream states blocked.", "policy": "P795 is a read-only risk acceptance gate; it performs no risk approval or release."}
        row.update({field: False for field in FIELDS})
        rows.append(row)
    zero = {field + "_rows": 0 for field in FIELDS}
    summary = {"risk_gate_id": "p795::summary", "risk_gate_order": len(rows) + 1, "created_at": created, "boundary": "summary", "risk_gate_rows": len(rows), **zero, "policy": "P795 remains empty and fail-closed."}
    OUT.write_text("".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows + [summary]), encoding="utf-8")
    report = {"manifest_id": "P795", "created_at": created, "local_only": True, "risk_gate_rows": len(rows), **zero, "artifact_jsonl": str(OUT.relative_to(ROOT)), "artifact_md": str(MD.relative_to(ROOT)), "policy": "P795 is monitoring-only and fail-closed."}
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    MD.write_text(f"# P795 risk acceptance/residual risk decision gate\n\nRows: `{len(rows)}`. Authorized risk acceptances: `0`.\n", encoding="utf-8")
    print(json.dumps({"manifest_id": "P795", "risk_gate_rows": len(rows), "risk_acceptance_authorized_rows": 0, "formal_decision_ready_rows": 0, "output": str(REPORT)}, ensure_ascii=False))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
