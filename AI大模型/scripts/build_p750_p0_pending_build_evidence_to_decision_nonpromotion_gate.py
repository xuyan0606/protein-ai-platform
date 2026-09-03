#!/usr/bin/env python3
"""Build P750 evidence-to-decision non-promotion gates from P749."""
from __future__ import annotations
import json
from datetime import datetime, timezone
from pathlib import Path
from build_p700_p0_real_input_pending_build_checklist import load_jsonl

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "datasets/governance/p749_p0_pending_build_input_provenance_evidence_gate.jsonl"
OUT = ROOT / "datasets/governance/p750_p0_pending_build_evidence_to_decision_nonpromotion_gate.jsonl"
REPORT = ROOT / "reports/p750_p0_pending_build_evidence_to_decision_nonpromotion_gate_report.json"
MD = ROOT / "reports/p750_p0_pending_build_evidence_to_decision_nonpromotion_gate.md"
FIELDS = ("evidence_validated", "review_completed", "evidence_released", "formal_decision_written", "formal_decision_approved", "model_claim_promoted", "release_ready", "production_execution_allowed")

def main() -> int:
    created = datetime.now(timezone.utc).isoformat(); source = [r for r in load_jsonl(SOURCE) if r.get("boundary") != "summary"]; rows = []
    for order, src in enumerate(source, 1):
        row = {"nonpromotion_gate_id": f"p750::{src.get('evidence_gate_id')}", "nonpromotion_gate_order": order, "created_at": created, "boundary": src.get("boundary"), "source_p749_id": src.get("evidence_gate_id"), "gate_status": "empty_no_validated_evidence_to_promote", "blocker_reason": "Evidence is absent and unvalidated; no formal decision or downstream claim may be promoted.", "operator_action": "Keep evidence, decisions, model claims, release, and production execution blocked; do not infer approval from planning artifacts.", "policy": "P750 is a non-promotion gate only; it writes no decision and grants no authorization."}
        row.update({field: False for field in FIELDS}); rows.append(row)
    zero = {f"{field}_rows": 0 for field in FIELDS}; summary = {"nonpromotion_gate_id": "p750::summary", "nonpromotion_gate_order": len(rows) + 1, "created_at": created, "boundary": "summary", "nonpromotion_gate_rows": len(rows), **zero, "policy": "P750 remains empty and fail-closed."}
    OUT.write_text("".join(json.dumps(r, ensure_ascii=False, sort_keys=True) + "\n" for r in rows + [summary]), encoding="utf-8")
    report = {"manifest_id": "P750", "created_at": created, "local_only": True, "nonpromotion_gate_rows": len(rows), **zero, "artifact_jsonl": str(OUT.relative_to(ROOT)), "artifact_md": str(MD.relative_to(ROOT)), "policy": "P750 is planning-only and fail-closed."}
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8"); MD.write_text(f"# P750 evidence-to-decision non-promotion gate\n\nRows: `{len(rows)}`. Formal decisions written: `0`.\n", encoding="utf-8")
    print(json.dumps({"manifest_id": "P750", "nonpromotion_gate_rows": len(rows), "formal_decision_written_rows": 0, "output": str(REPORT)}, ensure_ascii=False)); return 0
if __name__ == "__main__": raise SystemExit(main())
