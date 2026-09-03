#!/usr/bin/env python3
"""Build P754 release-to-production non-authorization gates from P753."""
from __future__ import annotations
import json
from datetime import datetime, timezone
from pathlib import Path
from build_p700_p0_real_input_pending_build_checklist import load_jsonl
ROOT = Path(__file__).resolve().parents[1]; SOURCE = ROOT / "datasets/governance/p753_p0_pending_build_decision_to_release_nonpromotion_gate.jsonl"; OUT = ROOT / "datasets/governance/p754_p0_pending_build_release_to_production_non_authorization_gate.jsonl"; REPORT = ROOT / "reports/p754_p0_pending_build_release_to_production_non_authorization_gate_report.json"; MD = ROOT / "reports/p754_p0_pending_build_release_to_production_non_authorization_gate.md"
FIELDS = ("release_approved", "customer_scope_confirmed", "production_change_reviewed", "rollback_plan_validated", "execution_receipt_contract_ready", "production_execution_requested", "production_execution_authorized", "production_execution_started")
def main() -> int:
    created = datetime.now(timezone.utc).isoformat(); source = [r for r in load_jsonl(SOURCE) if r.get("boundary") != "summary"]; rows = []
    for order, src in enumerate(source, 1):
        row = {"production_gate_id": f"p754::{src.get('promotion_gate_id')}", "production_gate_order": order, "created_at": created, "boundary": src.get("boundary"), "source_p753_id": src.get("promotion_gate_id"), "gate_status": "empty_no_authorized_production_transition", "blocker_reason": "No approved release, customer scope, production review, rollback plan, or execution contract exists.", "operator_action": "Do not request, authorize, start, or simulate production execution from local planning or claim artifacts.", "policy": "P754 is a production non-authorization gate only; it performs no release or production action."}
        row.update({field: False for field in FIELDS}); rows.append(row)
    zero = {f"{field}_rows": 0 for field in FIELDS}; summary = {"production_gate_id": "p754::summary", "production_gate_order": len(rows) + 1, "created_at": created, "boundary": "summary", "production_gate_rows": len(rows), **zero, "policy": "P754 remains empty and fail-closed."}
    OUT.write_text("".join(json.dumps(r, ensure_ascii=False, sort_keys=True) + "\n" for r in rows + [summary]), encoding="utf-8"); report = {"manifest_id": "P754", "created_at": created, "local_only": True, "production_gate_rows": len(rows), **zero, "artifact_jsonl": str(OUT.relative_to(ROOT)), "artifact_md": str(MD.relative_to(ROOT)), "policy": "P754 is planning-only and fail-closed."}; REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8"); MD.write_text(f"# P754 release-to-production non-authorization gate\n\nRows: `{len(rows)}`. Production execution started: `0`.\n", encoding="utf-8"); print(json.dumps({"manifest_id": "P754", "production_gate_rows": len(rows), "production_execution_started_rows": 0, "output": str(REPORT)}, ensure_ascii=False)); return 0
if __name__ == "__main__": raise SystemExit(main())
