#!/usr/bin/env python3
"""Build P753 decision-to-release non-promotion gates from P752."""
from __future__ import annotations
import json
from datetime import datetime, timezone
from pathlib import Path
from build_p700_p0_real_input_pending_build_checklist import load_jsonl
ROOT = Path(__file__).resolve().parents[1]; SOURCE = ROOT / "datasets/governance/p752_p0_pending_build_formal_decision_non_write_gate.jsonl"; OUT = ROOT / "datasets/governance/p753_p0_pending_build_decision_to_release_nonpromotion_gate.jsonl"; REPORT = ROOT / "reports/p753_p0_pending_build_decision_to_release_nonpromotion_gate_report.json"; MD = ROOT / "reports/p753_p0_pending_build_decision_to_release_nonpromotion_gate.md"
FIELDS = ("formal_decision_approved", "release_claim_promoted", "model_claim_promoted", "customer_delivery_promoted", "release_approval_present", "release_ready", "production_execution_allowed")
def main() -> int:
    created = datetime.now(timezone.utc).isoformat(); source = [r for r in load_jsonl(SOURCE) if r.get("boundary") != "summary"]; rows = []
    for order, src in enumerate(source, 1):
        row = {"promotion_gate_id": f"p753::{src.get('decision_gate_id')}", "promotion_gate_order": order, "created_at": created, "boundary": src.get("boundary"), "source_p752_id": src.get("decision_gate_id"), "gate_status": "empty_no_approved_decision_to_promote", "blocker_reason": "No approved formal decision or release approval exists; downstream claims and delivery remain blocked.", "operator_action": "Do not promote model claims, release claims, customer delivery, or production state from planning artifacts.", "policy": "P753 is a non-promotion gate only; it performs no release or delivery authorization."}
        row.update({field: False for field in FIELDS}); rows.append(row)
    zero = {f"{field}_rows": 0 for field in FIELDS}; summary = {"promotion_gate_id": "p753::summary", "promotion_gate_order": len(rows) + 1, "created_at": created, "boundary": "summary", "promotion_gate_rows": len(rows), **zero, "policy": "P753 remains empty and fail-closed."}
    OUT.write_text("".join(json.dumps(r, ensure_ascii=False, sort_keys=True) + "\n" for r in rows + [summary]), encoding="utf-8"); report = {"manifest_id": "P753", "created_at": created, "local_only": True, "promotion_gate_rows": len(rows), **zero, "artifact_jsonl": str(OUT.relative_to(ROOT)), "artifact_md": str(MD.relative_to(ROOT)), "policy": "P753 is planning-only and fail-closed."}; REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8"); MD.write_text(f"# P753 decision-to-release non-promotion gate\n\nRows: `{len(rows)}`. Release claims promoted: `0`.\n", encoding="utf-8"); print(json.dumps({"manifest_id": "P753", "promotion_gate_rows": len(rows), "release_claim_promoted_rows": 0, "output": str(REPORT)}, ensure_ascii=False)); return 0
if __name__ == "__main__": raise SystemExit(main())
