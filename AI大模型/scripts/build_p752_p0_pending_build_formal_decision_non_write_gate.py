#!/usr/bin/env python3
"""Build P752 formal-decision non-write gates from P751."""
from __future__ import annotations
import json
from datetime import datetime, timezone
from pathlib import Path
from build_p700_p0_real_input_pending_build_checklist import load_jsonl
ROOT = Path(__file__).resolve().parents[1]; SOURCE = ROOT / "datasets/governance/p751_p0_pending_build_formal_decision_authorization_preflight_gate.jsonl"; OUT = ROOT / "datasets/governance/p752_p0_pending_build_formal_decision_non_write_gate.jsonl"; REPORT = ROOT / "reports/p752_p0_pending_build_formal_decision_non_write_gate_report.json"; MD = ROOT / "reports/p752_p0_pending_build_formal_decision_non_write_gate.md"
FIELDS = ("formal_decision_draft_present", "formal_decision_schema_validated", "formal_decision_write_authorized", "formal_decision_written", "formal_decision_approved", "model_claim_promoted", "release_ready", "production_execution_allowed")
def main() -> int:
    created = datetime.now(timezone.utc).isoformat(); source = [r for r in load_jsonl(SOURCE) if r.get("boundary") != "summary"]; rows = []
    for order, src in enumerate(source, 1):
        row = {"decision_gate_id": f"p752::{src.get('authorization_preflight_id')}", "decision_gate_order": order, "created_at": created, "boundary": src.get("boundary"), "source_p751_id": src.get("authorization_preflight_id"), "gate_status": "empty_no_authorized_decision_to_write", "blocker_reason": "No validated decision package or write authorization exists; formal decision state must remain empty.", "operator_action": "Do not write, approve, infer, or promote a formal decision from drafts, plans, placeholders, or unverified evidence.", "policy": "P752 is a formal-decision non-write gate only; it performs no decision write or authorization."}
        row.update({field: False for field in FIELDS}); rows.append(row)
    zero = {f"{field}_rows": 0 for field in FIELDS}; summary = {"decision_gate_id": "p752::summary", "decision_gate_order": len(rows) + 1, "created_at": created, "boundary": "summary", "decision_gate_rows": len(rows), **zero, "policy": "P752 remains empty and fail-closed."}
    OUT.write_text("".join(json.dumps(r, ensure_ascii=False, sort_keys=True) + "\n" for r in rows + [summary]), encoding="utf-8"); report = {"manifest_id": "P752", "created_at": created, "local_only": True, "decision_gate_rows": len(rows), **zero, "artifact_jsonl": str(OUT.relative_to(ROOT)), "artifact_md": str(MD.relative_to(ROOT)), "policy": "P752 is planning-only and fail-closed."}; REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8"); MD.write_text(f"# P752 formal-decision non-write gate\n\nRows: `{len(rows)}`. Formal decisions written: `0`.\n", encoding="utf-8"); print(json.dumps({"manifest_id": "P752", "decision_gate_rows": len(rows), "formal_decision_written_rows": 0, "output": str(REPORT)}, ensure_ascii=False)); return 0
if __name__ == "__main__": raise SystemExit(main())
