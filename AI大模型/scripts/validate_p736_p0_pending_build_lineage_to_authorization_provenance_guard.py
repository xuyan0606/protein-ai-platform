#!/usr/bin/env python3
"""Validate P736 lineage-to-authorization provenance guard."""
from __future__ import annotations
import json
from datetime import datetime, timezone
from pathlib import Path
from build_p700_p0_real_input_pending_build_checklist import load_json, load_jsonl
from build_p736_p0_pending_build_lineage_to_authorization_provenance_guard import FALSE_FIELDS

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "datasets/governance/p735_p0_pending_build_review_receipt_to_decision_lineage_guard.jsonl"
BOARD = ROOT / "datasets/governance/p736_p0_pending_build_lineage_to_authorization_provenance_guard.jsonl"
REPORT = ROOT / "reports/p736_p0_pending_build_lineage_to_authorization_provenance_guard_report.json"
OUT = ROOT / "reports/p736_p0_pending_build_lineage_to_authorization_provenance_guard_validation_report.json"

def main() -> int:
    source_rows = [r for r in load_jsonl(SOURCE) if r.get("boundary") != "summary"]
    rows = load_jsonl(BOARD); guards = rows[:-1] if rows else []; summary = rows[-1] if rows else {}; report = load_json(REPORT)
    failures = []
    def fail(check, condition, observed, expected):
        if condition: failures.append({"check": check, "observed": observed, "expected": expected})
    fail("source_rows", len(source_rows) != 5, len(source_rows), 5); fail("guard_rows", len(guards) != 5, len(guards), 5)
    fail("summary_present", summary.get("boundary") != "summary", summary.get("boundary"), "summary")
    source_ids = {r.get("lineage_guard_id") for r in source_rows}; observed_ids = {r.get("source_p735_id") for r in guards}
    fail("source_coverage", observed_ids != source_ids, sorted(str(v) for v in observed_ids), sorted(str(v) for v in source_ids))
    for field in FALSE_FIELDS:
        fail(f"report_{field}_rows", report.get(f"{field}_rows") != 0, report.get(f"{field}_rows"), 0)
        fail(f"summary_{field}_rows", summary.get(f"{field}_rows") != 0, summary.get(f"{field}_rows"), 0)
    for i, row in enumerate(guards, 1):
        fail(f"row_{i}_status", row.get("guard_status") != "empty_no_authorization_to_validate", row.get("guard_status"), "empty_no_authorization_to_validate")
        for field in FALSE_FIELDS: fail(f"row_{i}_{field}", row.get(field) is not False, row.get(field), False)
    result = {"created_at": datetime.now(timezone.utc).isoformat(), "manifest_id": "P736", "local_only": True,
              "success": not failures, "failure_count": len(failures), "failures": failures,
              "authorization_guard_rows": len(guards), **{f"{field}_rows": 0 for field in FALSE_FIELDS},
              "policy": "Validation only; no authorization provenance exists to promote."}
    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"success": result["success"], "authorization_guard_rows": len(guards), "authorization_validated_rows": 0, "production_authorization_allowed_rows": 0, "failures": len(failures), "output": str(OUT)}, ensure_ascii=False))
    return 0 if not failures else 1

if __name__ == "__main__":
    raise SystemExit(main())
