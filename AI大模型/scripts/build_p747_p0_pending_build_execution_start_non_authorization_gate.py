#!/usr/bin/env python3
"""Build P747 execution-start non-authorization gates from P746."""
from __future__ import annotations
import json
from datetime import datetime, timezone
from pathlib import Path
from build_p700_p0_real_input_pending_build_checklist import load_jsonl

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "datasets/governance/p746_p0_pending_build_all_started_continuation_register.jsonl"
OUT = ROOT / "datasets/governance/p747_p0_pending_build_execution_start_non_authorization_gate.jsonl"
REPORT = ROOT / "reports/p747_p0_pending_build_execution_start_non_authorization_gate_report.json"
MD = ROOT / "reports/p747_p0_pending_build_execution_start_non_authorization_gate.md"

FIELDS = ("execution_start_requested", "execution_start_authorized", "execution_started",
          "real_input_received", "evidence_validated", "formal_decision_ready",
          "release_ready", "production_execution_allowed")

def main() -> int:
    created = datetime.now(timezone.utc).isoformat()
    source = [r for r in load_jsonl(SOURCE) if r.get("boundary") != "summary"]
    rows = []
    for order, src in enumerate(source, 1):
        row = {
            "execution_gate_id": f"p747::{src.get('register_id')}",
            "execution_gate_order": order,
            "created_at": created,
            "boundary": src.get("boundary"),
            "source_p746_id": src.get("register_id"),
            "gate_status": "planning_started_execution_blocked",
            "blocker_reason": "Planning registration alone is insufficient for execution; real input, evidence, validation, and authorization are absent.",
            "operator_action": "Keep model architecture, training-data, fine-tuning, inference-service, and evaluation work stopped until every gate is independently evidenced and authorized.",
            "policy": "P747 is a non-authorization gate only; it never starts execution or grants release/production permission.",
        }
        row.update({field: False for field in FIELDS})
        rows.append(row)
    zero = {f"{field}_rows": 0 for field in FIELDS}
    summary = {
        "execution_gate_id": "p747::summary", "execution_gate_order": len(rows) + 1,
        "created_at": created, "boundary": "summary", "execution_gate_rows": len(rows),
        **zero, "policy": "P747 remains planning-only and fail-closed."
    }
    OUT.write_text("".join(json.dumps(r, ensure_ascii=False, sort_keys=True) + "\n" for r in rows + [summary]), encoding="utf-8")
    report = {"manifest_id": "P747", "created_at": created, "local_only": True,
              "execution_gate_rows": len(rows), **zero,
              "artifact_jsonl": str(OUT.relative_to(ROOT)), "artifact_md": str(MD.relative_to(ROOT)),
              "policy": "P747 is planning-only and fail-closed."}
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    MD.write_text(f"# P747 execution-start non-authorization gate\n\nRows: `{len(rows)}`. Execution started: `0`.\n", encoding="utf-8")
    print(json.dumps({"manifest_id": "P747", "execution_gate_rows": len(rows), "execution_started_rows": 0, "output": str(REPORT)}, ensure_ascii=False))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
