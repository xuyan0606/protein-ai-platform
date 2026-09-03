#!/usr/bin/env python3
"""Build P751 formal-decision authorization preflight gates from P750."""
from __future__ import annotations
import json
from datetime import datetime, timezone
from pathlib import Path
from build_p700_p0_real_input_pending_build_checklist import load_jsonl
ROOT = Path(__file__).resolve().parents[1]; SOURCE = ROOT / "datasets/governance/p750_p0_pending_build_evidence_to_decision_nonpromotion_gate.jsonl"; OUT = ROOT / "datasets/governance/p751_p0_pending_build_formal_decision_authorization_preflight_gate.jsonl"; REPORT = ROOT / "reports/p751_p0_pending_build_formal_decision_authorization_preflight_gate_report.json"; MD = ROOT / "reports/p751_p0_pending_build_formal_decision_authorization_preflight_gate.md"
FIELDS = ("real_input_verified", "evidence_chain_validated", "independent_review_completed", "authorizer_identity_verified", "authorization_scope_verified", "formal_decision_write_allowed", "formal_decision_written", "release_ready", "production_execution_allowed")
def main() -> int:
    created = datetime.now(timezone.utc).isoformat(); source = [r for r in load_jsonl(SOURCE) if r.get("boundary") != "summary"]; rows = []
    for order, src in enumerate(source, 1):
        row = {"authorization_preflight_id": f"p751::{src.get('nonpromotion_gate_id')}", "authorization_preflight_order": order, "created_at": created, "boundary": src.get("boundary"), "source_p750_id": src.get("nonpromotion_gate_id"), "gate_status": "empty_no_authorization_preflight", "blocker_reason": "Required input, evidence, review, authorizer identity, and scope are absent; formal decision writes remain prohibited.", "operator_action": "Do not infer an authorizer, scope, approval, decision, release, or production permission from local planning artifacts.", "policy": "P751 is an authorization preflight register only; it grants no authorization and writes no decision."}
        row.update({field: False for field in FIELDS}); rows.append(row)
    zero = {f"{field}_rows": 0 for field in FIELDS}; summary = {"authorization_preflight_id": "p751::summary", "authorization_preflight_order": len(rows) + 1, "created_at": created, "boundary": "summary", "authorization_preflight_rows": len(rows), **zero, "policy": "P751 remains empty and fail-closed."}
    OUT.write_text("".join(json.dumps(r, ensure_ascii=False, sort_keys=True) + "\n" for r in rows + [summary]), encoding="utf-8"); report = {"manifest_id": "P751", "created_at": created, "local_only": True, "authorization_preflight_rows": len(rows), **zero, "artifact_jsonl": str(OUT.relative_to(ROOT)), "artifact_md": str(MD.relative_to(ROOT)), "policy": "P751 is planning-only and fail-closed."}; REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8"); MD.write_text(f"# P751 formal-decision authorization preflight gate\n\nRows: `{len(rows)}`. Formal decision writes allowed: `0`.\n", encoding="utf-8"); print(json.dumps({"manifest_id": "P751", "authorization_preflight_rows": len(rows), "formal_decision_write_allowed_rows": 0, "output": str(REPORT)}, ensure_ascii=False)); return 0
if __name__ == "__main__": raise SystemExit(main())
