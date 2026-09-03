#!/usr/bin/env python3
"""Build P748 real-input non-write gates from P747."""
from __future__ import annotations
import json
from datetime import datetime, timezone
from pathlib import Path
from build_p700_p0_real_input_pending_build_checklist import load_jsonl

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "datasets/governance/p747_p0_pending_build_execution_start_non_authorization_gate.jsonl"
OUT = ROOT / "datasets/governance/p748_p0_pending_build_real_input_non_write_gate.jsonl"
REPORT = ROOT / "reports/p748_p0_pending_build_real_input_non_write_gate_report.json"
MD = ROOT / "reports/p748_p0_pending_build_real_input_non_write_gate.md"
FIELDS = ("real_input_received", "input_provenance_validated", "input_accepted", "runtime_receipt_written", "training_label_written", "formal_decision_written", "execution_started", "release_ready", "production_execution_allowed")

def main() -> int:
    created = datetime.now(timezone.utc).isoformat()
    source = [r for r in load_jsonl(SOURCE) if r.get("boundary") != "summary"]
    rows = []
    for order, src in enumerate(source, 1):
        row = {"input_gate_id": f"p748::{src.get('execution_gate_id')}", "input_gate_order": order,
               "created_at": created, "boundary": src.get("boundary"), "source_p747_id": src.get("execution_gate_id"),
               "gate_status": "empty_no_real_input_to_write", "blocker_reason": "No authenticated real input or provenance is present; all downstream writes remain prohibited.",
               "operator_action": "Do not accept, normalize, infer, or write input into runtime receipts, training labels, decisions, release artifacts, or production state.",
               "policy": "P748 is a real-input non-write gate only; it performs no intake or authorization."}
        row.update({field: False for field in FIELDS}); rows.append(row)
    zero = {f"{field}_rows": 0 for field in FIELDS}
    summary = {"input_gate_id": "p748::summary", "input_gate_order": len(rows) + 1, "created_at": created, "boundary": "summary", "input_gate_rows": len(rows), **zero, "policy": "P748 remains empty and fail-closed."}
    OUT.write_text("".join(json.dumps(r, ensure_ascii=False, sort_keys=True) + "\n" for r in rows + [summary]), encoding="utf-8")
    report = {"manifest_id": "P748", "created_at": created, "local_only": True, "input_gate_rows": len(rows), **zero, "artifact_jsonl": str(OUT.relative_to(ROOT)), "artifact_md": str(MD.relative_to(ROOT)), "policy": "P748 is planning-only and fail-closed."}
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    MD.write_text(f"# P748 real-input non-write gate\n\nRows: `{len(rows)}`. Real input received: `0`. Downstream writes: `0`.\n", encoding="utf-8")
    print(json.dumps({"manifest_id": "P748", "input_gate_rows": len(rows), "real_input_received_rows": 0, "output": str(REPORT)}, ensure_ascii=False))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
