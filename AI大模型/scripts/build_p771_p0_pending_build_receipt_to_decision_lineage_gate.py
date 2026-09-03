#!/usr/bin/env python3
"""Build P771 receipt-to-decision lineage gates from P770."""
from __future__ import annotations
import json
from datetime import datetime, timezone
from pathlib import Path
from build_p700_p0_real_input_pending_build_checklist import load_jsonl

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "datasets/governance/p770_p0_pending_build_review_receipt_freshness_gate.jsonl"
OUT = ROOT / "datasets/governance/p771_p0_pending_build_receipt_to_decision_lineage_gate.jsonl"
REPORT = ROOT / "reports/p771_p0_pending_build_receipt_to_decision_lineage_gate_report.json"
MD = ROOT / "reports/p771_p0_pending_build_receipt_to_decision_lineage_gate.md"
FIELDS = ("receipt_present", "evidence_linked", "review_route_linked", "decision_target_linked", "authorization_chain_linked", "lineage_complete", "formal_decision_written", "formal_decision_ready", "restart_authorized")

def main() -> int:
    created = datetime.now(timezone.utc).isoformat(); source = [row for row in load_jsonl(SOURCE) if row.get("boundary") != "summary"]; rows = []
    for order, src in enumerate(source, 1):
        row = {"lineage_gate_id": f"p771::{src.get('freshness_gate_id')}", "lineage_gate_order": order, "created_at": created, "boundary": src.get("boundary"), "source_p770_id": src.get("freshness_gate_id"), "gate_status": "empty_no_receipt_lineage_to_decide", "blocker_reason": "No authentic receipt or linked evidence, route, decision target, or authorization chain exists.", "operator_action": "Do not construct or infer decision lineage, write a formal decision, or authorize restart.", "policy": "P771 is a lineage gate only; it performs no decision write or authorization."}
        row.update({field: False for field in FIELDS}); rows.append(row)
    zero = {f"{field}_rows": 0 for field in FIELDS}; summary = {"lineage_gate_id": "p771::summary", "lineage_gate_order": len(rows) + 1, "created_at": created, "boundary": "summary", "lineage_gate_rows": len(rows), **zero, "policy": "P771 remains empty and fail-closed."}
    OUT.write_text("".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows + [summary]), encoding="utf-8")
    report = {"manifest_id": "P771", "created_at": created, "local_only": True, "lineage_gate_rows": len(rows), **zero, "artifact_jsonl": str(OUT.relative_to(ROOT)), "artifact_md": str(MD.relative_to(ROOT)), "policy": "P771 is planning-only and fail-closed."}
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8"); MD.write_text(f"# P771 receipt-to-decision lineage gate\n\nRows: `{len(rows)}`. Complete lineages: `0`.\n", encoding="utf-8")
    print(json.dumps({"manifest_id": "P771", "lineage_gate_rows": len(rows), "lineage_complete_rows": 0, "output": str(REPORT)}, ensure_ascii=False)); return 0
if __name__ == "__main__": raise SystemExit(main())
