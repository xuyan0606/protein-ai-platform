#!/usr/bin/env python3
import json
from datetime import datetime, timezone
from pathlib import Path
from build_p700_p0_real_input_pending_build_checklist import load_jsonl

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "datasets/governance/p796_p0_pending_build_control_implementation_verification_gate.jsonl"
OUT = ROOT / "datasets/governance/p797_p0_pending_build_control_exception_remediation_closure_gate.jsonl"
REPORT = ROOT / "reports/p797_p0_pending_build_control_exception_remediation_closure_gate_report.json"
MD = ROOT / "reports/p797_p0_pending_build_control_exception_remediation_closure_gate.md"
FIELDS = ("exception_identified", "deviation_recorded", "exception_owner_verified", "remediation_defined", "remediation_completed", "remediation_effective", "closure_reviewed", "exception_approved", "formal_decision_ready", "production_execution_allowed")

def main():
    created = datetime.now(timezone.utc).isoformat()
    source_rows = [r for r in load_jsonl(SOURCE) if r.get("boundary") != "summary"]
    rows = []
    for i, source in enumerate(source_rows, 1):
        row = {"exception_gate_id": f"p797::{source.get('control_gate_id')}", "exception_gate_order": i, "created_at": created, "boundary": source.get("boundary"), "source_p796_id": source.get("control_gate_id"), "gate_status": "empty_no_verified_exception_or_remediation_closure", "blocker_reason": "No authorized exception, deviation record, remediation evidence, effectiveness review, or closure approval exists.", "operator_action": "Do not waive controls, close deviations, infer remediation, or unblock downstream work.", "policy": "P797 is a read-only exception/remediation closure gate; it performs no waiver, remediation, or authorization."}
        row.update({field: False for field in FIELDS})
        rows.append(row)
    zero = {field + "_rows": 0 for field in FIELDS}
    summary = {"exception_gate_id": "p797::summary", "exception_gate_order": len(rows) + 1, "created_at": created, "boundary": "summary", "exception_gate_rows": len(rows), **zero, "policy": "P797 remains empty and fail-closed."}
    OUT.write_text("".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows + [summary]), encoding="utf-8")
    report = {"manifest_id": "P797", "created_at": created, "local_only": True, "exception_gate_rows": len(rows), **zero, "artifact_jsonl": str(OUT.relative_to(ROOT)), "artifact_md": str(MD.relative_to(ROOT)), "policy": "P797 is monitoring-only and fail-closed."}
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    MD.write_text(f"# P797 control exception/remediation closure gate\n\nRows: `{len(rows)}`. Approved exceptions: `0`.\n", encoding="utf-8")
    print(json.dumps({"manifest_id": "P797", "exception_gate_rows": len(rows), "exception_approved_rows": 0, "remediation_completed_rows": 0, "output": str(REPORT)}, ensure_ascii=False))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
