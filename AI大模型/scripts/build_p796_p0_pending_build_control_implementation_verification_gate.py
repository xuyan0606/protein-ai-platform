#!/usr/bin/env python3
import json
from datetime import datetime, timezone
from pathlib import Path
from build_p700_p0_real_input_pending_build_checklist import load_jsonl

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "datasets/governance/p795_p0_pending_build_risk_acceptance_residual_risk_decision_gate.jsonl"
OUT = ROOT / "datasets/governance/p796_p0_pending_build_control_implementation_verification_gate.jsonl"
REPORT = ROOT / "reports/p796_p0_pending_build_control_implementation_verification_gate_report.json"
MD = ROOT / "reports/p796_p0_pending_build_control_implementation_verification_gate.md"
FIELDS = ("control_defined", "control_owner_verified", "control_implemented", "implementation_evidence_present", "control_effectiveness_validated", "monitoring_configured", "exception_approved", "formal_decision_ready", "release_ready", "production_execution_allowed")

def main():
    created = datetime.now(timezone.utc).isoformat()
    source_rows = [r for r in load_jsonl(SOURCE) if r.get("boundary") != "summary"]
    rows = []
    for i, source in enumerate(source_rows, 1):
        row = {"control_gate_id": f"p796::{source.get('risk_gate_id')}", "control_gate_order": i, "created_at": created, "boundary": source.get("boundary"), "source_p795_id": source.get("risk_gate_id"), "gate_status": "empty_no_verified_control_implementation", "blocker_reason": "No authorized control definition, implementation evidence, effectiveness validation, monitoring, or exception approval exists.", "operator_action": "Do not claim controls are implemented or effective; keep downstream states blocked.", "policy": "P796 is a read-only control implementation/verification gate; it performs no deployment or authorization."}
        row.update({field: False for field in FIELDS})
        rows.append(row)
    zero = {field + "_rows": 0 for field in FIELDS}
    summary = {"control_gate_id": "p796::summary", "control_gate_order": len(rows) + 1, "created_at": created, "boundary": "summary", "control_gate_rows": len(rows), **zero, "policy": "P796 remains empty and fail-closed."}
    OUT.write_text("".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows + [summary]), encoding="utf-8")
    report = {"manifest_id": "P796", "created_at": created, "local_only": True, "control_gate_rows": len(rows), **zero, "artifact_jsonl": str(OUT.relative_to(ROOT)), "artifact_md": str(MD.relative_to(ROOT)), "policy": "P796 is monitoring-only and fail-closed."}
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    MD.write_text(f"# P796 control implementation/verification gate\n\nRows: `{len(rows)}`. Effective controls: `0`.\n", encoding="utf-8")
    print(json.dumps({"manifest_id": "P796", "control_gate_rows": len(rows), "control_effectiveness_validated_rows": 0, "production_execution_allowed_rows": 0, "output": str(REPORT)}, ensure_ascii=False))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
