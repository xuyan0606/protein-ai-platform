#!/usr/bin/env python3
"""Build P737 authorization-to-release/model/customer-claim non-promotion guard."""
from __future__ import annotations
import json
from datetime import datetime, timezone
from pathlib import Path
from build_p700_p0_real_input_pending_build_checklist import load_jsonl

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "datasets/governance/p736_p0_pending_build_lineage_to_authorization_provenance_guard.jsonl"
OUT = ROOT / "datasets/governance/p737_p0_pending_build_authorization_to_release_claim_nonpromotion_guard.jsonl"
REPORT = ROOT / "reports/p737_p0_pending_build_authorization_to_release_claim_nonpromotion_guard_report.json"
MD = ROOT / "reports/p737_p0_pending_build_authorization_to_release_claim_nonpromotion_guard.md"
FALSE_FIELDS = ("authorization_present", "authorization_scope_validated", "release_claim_promoted", "model_claim_promoted", "customer_delivery_promoted", "nonpromotion_guard_validated")

def main() -> int:
    created = datetime.now(timezone.utc).isoformat()
    source_rows = [r for r in load_jsonl(SOURCE) if r.get("boundary") != "summary"]
    rows = []
    for order, source in enumerate(source_rows, 1):
        row = {"nonpromotion_guard_id": f"p737::{source.get('authorization_guard_id')}", "nonpromotion_guard_order": order,
               "created_at": created, "boundary": source.get("boundary"), "source_p736_id": source.get("authorization_guard_id"),
               "guard_status": "empty_no_authorization_to_promote", "blocker_reason": "No real authorization exists to support release, model claim, or customer delivery promotion.",
               "operator_action": "Do not promote claims or release readiness from planning artifacts.",
               "policy": "P737 is a non-promotion guard only; it does not authorize release, claims, delivery, or production."}
        row.update({field: False for field in FALSE_FIELDS}); rows.append(row)
    counts = {f"{field}_rows": 0 for field in FALSE_FIELDS}
    summary = {"nonpromotion_guard_id": "p737::summary", "nonpromotion_guard_order": len(rows) + 1, "created_at": created,
               "boundary": "summary", "nonpromotion_guard_rows": len(rows), **counts, "policy": "P737 remains empty and fail-closed."}
    OUT.write_text("".join(json.dumps(r, ensure_ascii=False, sort_keys=True) + "\n" for r in rows + [summary]), encoding="utf-8")
    report = {"manifest_id": "P737", "created_at": created, "local_only": True, "nonpromotion_guard_rows": len(rows), **counts,
              "artifact_jsonl": str(OUT.relative_to(ROOT)), "artifact_md": str(MD.relative_to(ROOT)), "policy": "P737 is planning-only and fail-closed."}
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    MD.write_text(f"# P737 authorization-to-claim non-promotion guard\n\nRows: `{len(rows)}`. Promotions: `0`.\n", encoding="utf-8")
    print(json.dumps({"manifest_id": "P737", "nonpromotion_guard_rows": len(rows), "release_claim_promoted_rows": 0, "output": str(REPORT)}, ensure_ascii=False))
    return 0

if __name__ == "__main__": raise SystemExit(main())
