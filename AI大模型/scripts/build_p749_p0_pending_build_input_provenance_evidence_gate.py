#!/usr/bin/env python3
"""Build P749 input-provenance evidence gates from P748."""
from __future__ import annotations
import json
from datetime import datetime, timezone
from pathlib import Path
from build_p700_p0_real_input_pending_build_checklist import load_jsonl

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "datasets/governance/p748_p0_pending_build_real_input_non_write_gate.jsonl"
OUT = ROOT / "datasets/governance/p749_p0_pending_build_input_provenance_evidence_gate.jsonl"
REPORT = ROOT / "reports/p749_p0_pending_build_input_provenance_evidence_gate_report.json"
MD = ROOT / "reports/p749_p0_pending_build_input_provenance_evidence_gate.md"
FIELDS = ("input_present", "provenance_attached", "integrity_validated", "evidence_chain_complete", "evidence_released", "formal_decision_ready", "execution_started", "release_ready", "production_execution_allowed")

def main() -> int:
    created = datetime.now(timezone.utc).isoformat(); source = [r for r in load_jsonl(SOURCE) if r.get("boundary") != "summary"]; rows = []
    for order, src in enumerate(source, 1):
        row = {"evidence_gate_id": f"p749::{src.get('input_gate_id')}", "evidence_gate_order": order, "created_at": created, "boundary": src.get("boundary"), "source_p748_id": src.get("input_gate_id"), "gate_status": "empty_no_provenance_evidence_to_validate", "blocker_reason": "No real input, source provenance, integrity proof, or evidence chain is available for validation or release.", "operator_action": "Do not infer provenance, validate placeholders, release evidence, or authorize downstream model work.", "policy": "P749 is an evidence-gate register only; it performs no intake, validation, release, or authorization."}
        row.update({field: False for field in FIELDS}); rows.append(row)
    zero = {f"{field}_rows": 0 for field in FIELDS}; summary = {"evidence_gate_id": "p749::summary", "evidence_gate_order": len(rows) + 1, "created_at": created, "boundary": "summary", "evidence_gate_rows": len(rows), **zero, "policy": "P749 remains empty and fail-closed."}
    OUT.write_text("".join(json.dumps(r, ensure_ascii=False, sort_keys=True) + "\n" for r in rows + [summary]), encoding="utf-8")
    report = {"manifest_id": "P749", "created_at": created, "local_only": True, "evidence_gate_rows": len(rows), **zero, "artifact_jsonl": str(OUT.relative_to(ROOT)), "artifact_md": str(MD.relative_to(ROOT)), "policy": "P749 is planning-only and fail-closed."}
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8"); MD.write_text(f"# P749 input-provenance evidence gate\n\nRows: `{len(rows)}`. Evidence chain complete: `0`.\n", encoding="utf-8")
    print(json.dumps({"manifest_id": "P749", "evidence_gate_rows": len(rows), "evidence_chain_complete_rows": 0, "output": str(REPORT)}, ensure_ascii=False)); return 0

if __name__ == "__main__": raise SystemExit(main())
