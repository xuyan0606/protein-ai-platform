#!/usr/bin/env python3
"""Build P758 disclosure-incident containment gates from P757."""
from __future__ import annotations
import json
from datetime import datetime, timezone
from pathlib import Path
from build_p700_p0_real_input_pending_build_checklist import load_jsonl
ROOT = Path(__file__).resolve().parents[1]; SOURCE = ROOT / "datasets/governance/p757_p0_pending_build_audit_receipt_access_nonleak_gate.jsonl"; OUT = ROOT / "datasets/governance/p758_p0_pending_build_disclosure_incident_containment_gate.jsonl"; REPORT = ROOT / "reports/p758_p0_pending_build_disclosure_incident_containment_gate_report.json"; MD = ROOT / "reports/p758_p0_pending_build_disclosure_incident_containment_gate.md"
FIELDS = ("disclosure_incident_detected", "alert_raised", "access_contained", "owner_notified", "incident_review_completed", "remediation_validated", "formal_decision_ready", "production_execution_allowed")
def main() -> int:
    created = datetime.now(timezone.utc).isoformat(); source = [r for r in load_jsonl(SOURCE) if r.get("boundary") != "summary"]; rows = []
    for order, src in enumerate(source, 1):
        row = {"containment_gate_id": f"p758::{src.get('access_gate_id')}", "containment_gate_order": order, "created_at": created, "boundary": src.get("boundary"), "source_p757_id": src.get("access_gate_id"), "gate_status": "empty_no_disclosure_incident", "blocker_reason": "No disclosure incident or sensitive-data exposure is detected; containment workflow cannot be started or fabricated.", "operator_action": "Do not invent incident evidence, alerts, containment, notifications, remediation, or closure approvals.", "policy": "P758 is an incident-containment gate only; it performs no incident response or authorization."}
        row.update({field: False for field in FIELDS}); rows.append(row)
    zero = {f"{field}_rows": 0 for field in FIELDS}; summary = {"containment_gate_id": "p758::summary", "containment_gate_order": len(rows) + 1, "created_at": created, "boundary": "summary", "containment_gate_rows": len(rows), **zero, "policy": "P758 remains empty and fail-closed."}
    OUT.write_text("".join(json.dumps(r, ensure_ascii=False, sort_keys=True) + "\n" for r in rows + [summary]), encoding="utf-8"); report = {"manifest_id": "P758", "created_at": created, "local_only": True, "containment_gate_rows": len(rows), **zero, "artifact_jsonl": str(OUT.relative_to(ROOT)), "artifact_md": str(MD.relative_to(ROOT)), "policy": "P758 is planning-only and fail-closed."}; REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8"); MD.write_text(f"# P758 disclosure-incident containment gate\n\nRows: `{len(rows)}`. Incidents detected: `0`.\n", encoding="utf-8"); print(json.dumps({"manifest_id": "P758", "containment_gate_rows": len(rows), "disclosure_incident_detected_rows": 0, "output": str(REPORT)}, ensure_ascii=False)); return 0
if __name__ == "__main__": raise SystemExit(main())
