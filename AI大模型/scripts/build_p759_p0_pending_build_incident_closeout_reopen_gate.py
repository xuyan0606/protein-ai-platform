#!/usr/bin/env python3
"""Build P759 incident closeout/reopen gates from P758."""
from __future__ import annotations
import json
from datetime import datetime, timezone
from pathlib import Path
from build_p700_p0_real_input_pending_build_checklist import load_jsonl
ROOT = Path(__file__).resolve().parents[1]; SOURCE = ROOT / "datasets/governance/p758_p0_pending_build_disclosure_incident_containment_gate.jsonl"; OUT = ROOT / "datasets/governance/p759_p0_pending_build_incident_closeout_reopen_gate.jsonl"; REPORT = ROOT / "reports/p759_p0_pending_build_incident_closeout_reopen_gate_report.json"; MD = ROOT / "reports/p759_p0_pending_build_incident_closeout_reopen_gate.md"
FIELDS = ("incident_present", "evidence_archived", "residual_risk_assessed", "owner_approval_present", "closeout_approved", "reopen_requested", "reopen_authorized", "formal_decision_ready", "production_execution_allowed")
def main() -> int:
    created = datetime.now(timezone.utc).isoformat(); source = [r for r in load_jsonl(SOURCE) if r.get("boundary") != "summary"]; rows = []
    for order, src in enumerate(source, 1):
        row = {"closeout_gate_id": f"p759::{src.get('containment_gate_id')}", "closeout_gate_order": order, "created_at": created, "boundary": src.get("boundary"), "source_p758_id": src.get("containment_gate_id"), "gate_status": "empty_no_incident_to_close_or_reopen", "blocker_reason": "No incident, archived evidence, residual-risk assessment, owner approval, or reopen request exists.", "operator_action": "Do not close, reopen, or infer resolution/authorization from an empty containment record.", "policy": "P759 is a closeout/reopen gate only; it performs no incident closure or restart."}
        row.update({field: False for field in FIELDS}); rows.append(row)
    zero = {f"{field}_rows": 0 for field in FIELDS}; summary = {"closeout_gate_id": "p759::summary", "closeout_gate_order": len(rows) + 1, "created_at": created, "boundary": "summary", "closeout_gate_rows": len(rows), **zero, "policy": "P759 remains empty and fail-closed."}
    OUT.write_text("".join(json.dumps(r, ensure_ascii=False, sort_keys=True) + "\n" for r in rows + [summary]), encoding="utf-8"); report = {"manifest_id": "P759", "created_at": created, "local_only": True, "closeout_gate_rows": len(rows), **zero, "artifact_jsonl": str(OUT.relative_to(ROOT)), "artifact_md": str(MD.relative_to(ROOT)), "policy": "P759 is planning-only and fail-closed."}; REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8"); MD.write_text(f"# P759 incident closeout/reopen gate\n\nRows: `{len(rows)}`. Closeout approved: `0`. Reopen authorized: `0`.\n", encoding="utf-8"); print(json.dumps({"manifest_id": "P759", "closeout_gate_rows": len(rows), "closeout_approved_rows": 0, "reopen_authorized_rows": 0, "output": str(REPORT)}, ensure_ascii=False)); return 0
if __name__ == "__main__": raise SystemExit(main())
