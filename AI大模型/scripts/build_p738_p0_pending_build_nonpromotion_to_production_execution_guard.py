#!/usr/bin/env python3
"""Build P738 non-promotion to production execution guard."""
from __future__ import annotations
import json
from datetime import datetime, timezone
from pathlib import Path
from build_p700_p0_real_input_pending_build_checklist import load_jsonl

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "datasets/governance/p737_p0_pending_build_authorization_to_release_claim_nonpromotion_guard.jsonl"
OUT = ROOT / "datasets/governance/p738_p0_pending_build_nonpromotion_to_production_execution_guard.jsonl"
REPORT = ROOT / "reports/p738_p0_pending_build_nonpromotion_to_production_execution_guard_report.json"
MD = ROOT / "reports/p738_p0_pending_build_nonpromotion_to_production_execution_guard.md"
FIELDS = ("nonpromotion_guard_validated", "release_claim_blocked", "model_claim_blocked", "customer_delivery_blocked", "production_execution_requested", "production_execution_allowed")

def main() -> int:
    created = datetime.now(timezone.utc).isoformat(); source_rows = [r for r in load_jsonl(SOURCE) if r.get("boundary") != "summary"]; rows = []
    for order, source in enumerate(source_rows, 1):
        row = {"execution_guard_id": f"p738::{source.get('nonpromotion_guard_id')}", "execution_guard_order": order, "created_at": created, "boundary": source.get("boundary"), "source_p737_id": source.get("nonpromotion_guard_id"), "guard_status": "empty_no_promotion_to_execute", "blocker_reason": "No authorized promotion exists that could be converted into production execution.", "operator_action": "Do not execute production actions from a non-promotion planning guard.", "policy": "P738 is a production execution guard only; it never requests or permits execution."}
        row.update({f: False for f in FIELDS}); rows.append(row)
    counts = {f"{f}_rows": 0 for f in FIELDS}; summary = {"execution_guard_id": "p738::summary", "execution_guard_order": len(rows)+1, "created_at": created, "boundary": "summary", "execution_guard_rows": len(rows), **counts, "policy": "P738 remains empty and fail-closed."}
    OUT.write_text("".join(json.dumps(r, ensure_ascii=False, sort_keys=True)+"\n" for r in rows+[summary]), encoding="utf-8")
    report = {"manifest_id": "P738", "created_at": created, "local_only": True, "execution_guard_rows": len(rows), **counts, "artifact_jsonl": str(OUT.relative_to(ROOT)), "artifact_md": str(MD.relative_to(ROOT)), "policy": "P738 is planning-only and fail-closed."}
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True)+"\n", encoding="utf-8"); MD.write_text(f"# P738 non-promotion to production execution guard\n\nRows: `{len(rows)}`. Production execution allowed: `0`.\n", encoding="utf-8")
    print(json.dumps({"manifest_id":"P738","execution_guard_rows":len(rows),"production_execution_allowed_rows":0,"output":str(REPORT)}, ensure_ascii=False)); return 0
if __name__ == "__main__": raise SystemExit(main())
