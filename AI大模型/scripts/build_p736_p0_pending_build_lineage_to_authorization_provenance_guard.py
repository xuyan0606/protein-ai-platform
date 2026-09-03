#!/usr/bin/env python3
"""Build P736 lineage-to-authorization provenance guard from P735."""
from __future__ import annotations
import json
from datetime import datetime, timezone
from pathlib import Path
from build_p700_p0_real_input_pending_build_checklist import load_jsonl

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "datasets/governance/p735_p0_pending_build_review_receipt_to_decision_lineage_guard.jsonl"
OUT = ROOT / "datasets/governance/p736_p0_pending_build_lineage_to_authorization_provenance_guard.jsonl"
REPORT = ROOT / "reports/p736_p0_pending_build_lineage_to_authorization_provenance_guard_report.json"
MD = ROOT / "reports/p736_p0_pending_build_lineage_to_authorization_provenance_guard.md"
FALSE_FIELDS = ("authorization_provenance_present", "authorizer_identity_verified", "authorization_scope_bound", "authorization_validated", "formal_decision_authorized", "production_authorization_allowed")

def main() -> int:
    created = datetime.now(timezone.utc).isoformat()
    source_rows = [r for r in load_jsonl(SOURCE) if r.get("boundary") != "summary"]
    rows = []
    for order, source in enumerate(source_rows, 1):
        row = {"authorization_guard_id": f"p736::{source.get('lineage_guard_id')}", "authorization_guard_order": order,
               "created_at": created, "boundary": source.get("boundary"), "source_p735_id": source.get("lineage_guard_id"),
               "guard_status": "empty_no_authorization_to_validate",
               "blocker_reason": "No real formal decision or authorization provenance exists to validate.",
               "operator_action": "Do not infer an authorizer, scope, or production permission from planning artifacts.",
               "policy": "P736 records authorization provenance readiness only; it never grants or writes authorization."}
        row.update({field: False for field in FALSE_FIELDS})
        rows.append(row)
    counts = {f"{field}_rows": 0 for field in FALSE_FIELDS}
    summary = {"authorization_guard_id": "p736::summary", "authorization_guard_order": len(rows) + 1,
               "created_at": created, "boundary": "summary", "authorization_guard_rows": len(rows), **counts,
               "policy": "P736 remains empty and fail-closed until explicit authorization provenance exists."}
    OUT.write_text("".join(json.dumps(r, ensure_ascii=False, sort_keys=True) + "\n" for r in rows + [summary]), encoding="utf-8")
    report = {"manifest_id": "P736", "created_at": created, "local_only": True, "authorization_guard_rows": len(rows), **counts,
              "artifact_jsonl": str(OUT.relative_to(ROOT)), "artifact_md": str(MD.relative_to(ROOT)), "policy": "P736 is planning-only and fail-closed."}
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    MD.write_text(f"# P736 lineage-to-authorization provenance guard\n\nRows: `{len(rows)}`. Authorizations validated: `0`.\n", encoding="utf-8")
    print(json.dumps({"manifest_id": "P736", "authorization_guard_rows": len(rows), "authorization_validated_rows": 0, "output": str(REPORT)}, ensure_ascii=False))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
