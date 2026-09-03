#!/usr/bin/env python3
"""Build P734 receipt freshness/staleness guard from P733."""
from __future__ import annotations
import json
from datetime import datetime, timezone
from pathlib import Path
from build_p700_p0_real_input_pending_build_checklist import load_jsonl

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "datasets/governance/p733_p0_pending_build_review_receipt_atomicity_integrity_guard.jsonl"
OUT = ROOT / "datasets/governance/p734_p0_pending_build_review_receipt_freshness_staleness_guard.jsonl"
REPORT = ROOT / "reports/p734_p0_pending_build_review_receipt_freshness_staleness_guard_report.json"
MD = ROOT / "reports/p734_p0_pending_build_review_receipt_freshness_staleness_guard.md"

FIELDS = ("receipt_fresh", "receipt_stale", "staleness_resolved", "timestamp_verified", "freshness_validated", "formal_decision_ready")

def main() -> int:
    created = datetime.now(timezone.utc).isoformat()
    source_rows = [r for r in load_jsonl(SOURCE) if r.get("boundary") != "summary"]
    rows = []
    for order, source in enumerate(source_rows, 1):
        row = {
            "freshness_guard_id": f"p734::{source.get('integrity_guard_id')}",
            "freshness_guard_order": order, "created_at": created,
            "boundary": source.get("boundary"), "source_p733_id": source.get("integrity_guard_id"),
            "guard_status": "empty_no_receipt_to_age", "blocker_reason": "No dispatch receipt exists to assess freshness or staleness.",
            "operator_action": "Do not fabricate timestamps or mark a missing receipt fresh.",
            "policy": "P734 is a freshness guard only; it does not create, refresh, or validate receipts without a real artifact.",
        }
        row.update({field: False for field in FIELDS})
        rows.append(row)
    summary = {"freshness_guard_id": "p734::summary", "freshness_guard_order": len(rows) + 1, "created_at": created,
               "boundary": "summary", "freshness_guard_rows": len(rows), "receipt_fresh_rows": 0,
               "receipt_stale_rows": 0, "staleness_resolved_rows": 0, "timestamp_verified_rows": 0,
               "freshness_validated_rows": 0, "formal_decision_ready_rows": 0,
               "policy": "P734 records empty receipt freshness checks only."}
    OUT.write_text("".join(json.dumps(r, ensure_ascii=False, sort_keys=True) + "\n" for r in rows + [summary]), encoding="utf-8")
    report = {"manifest_id": "P734", "created_at": created, "local_only": True, "freshness_guard_rows": len(rows),
              "receipt_fresh_rows": 0, "receipt_stale_rows": 0, "staleness_resolved_rows": 0,
              "timestamp_verified_rows": 0, "freshness_validated_rows": 0, "formal_decision_ready_rows": 0,
              "artifact_jsonl": str(OUT.relative_to(ROOT)), "artifact_md": str(MD.relative_to(ROOT)),
              "policy": "P734 is planning-only and fail-closed."}
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    MD.write_text(f"# P734 review receipt freshness/staleness guard\n\nRows: `{len(rows)}`. Receipts fresh: `0`.\n", encoding="utf-8")
    print(json.dumps({"manifest_id": "P734", "freshness_guard_rows": len(rows), "receipt_fresh_rows": 0, "output": str(REPORT)}, ensure_ascii=False))

if __name__ == "__main__":
    raise SystemExit(main())
