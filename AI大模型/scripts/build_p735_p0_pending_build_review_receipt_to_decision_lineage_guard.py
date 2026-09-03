#!/usr/bin/env python3
"""Build P735 receipt-to-decision lineage guard from P734."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from build_p700_p0_real_input_pending_build_checklist import load_jsonl


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "datasets/governance/p734_p0_pending_build_review_receipt_freshness_staleness_guard.jsonl"
OUT = ROOT / "datasets/governance/p735_p0_pending_build_review_receipt_to_decision_lineage_guard.jsonl"
REPORT = ROOT / "reports/p735_p0_pending_build_review_receipt_to_decision_lineage_guard_report.json"
MD = ROOT / "reports/p735_p0_pending_build_review_receipt_to_decision_lineage_guard.md"

FALSE_FIELDS = (
    "receipt_present",
    "source_evidence_linked",
    "dispatch_route_linked",
    "decision_target_linked",
    "lineage_complete",
    "lineage_validated",
    "formal_decision_written",
    "formal_decision_ready",
)


def main() -> int:
    created_at = datetime.now(timezone.utc).isoformat()
    source_rows = [row for row in load_jsonl(SOURCE) if row.get("boundary") != "summary"]
    rows = []
    for order, source in enumerate(source_rows, start=1):
        row = {
            "lineage_guard_id": f"p735::{source.get('freshness_guard_id')}",
            "lineage_guard_order": order,
            "created_at": created_at,
            "boundary": source.get("boundary"),
            "source_p734_id": source.get("freshness_guard_id"),
            "guard_status": "empty_no_receipt_lineage_to_validate",
            "blocker_reason": "No real dispatch receipt exists to link to evidence, route, or a formal decision target.",
            "operator_action": "Provide a real provenance-bearing receipt before validating any receipt-to-decision lineage.",
            "policy": "P735 records lineage readiness only; it does not infer links or write a formal decision.",
        }
        row.update({field: False for field in FALSE_FIELDS})
        rows.append(row)

    counts = {f"{field}_rows": 0 for field in FALSE_FIELDS}
    summary = {
        "lineage_guard_id": "p735::summary",
        "lineage_guard_order": len(rows) + 1,
        "created_at": created_at,
        "boundary": "summary",
        "lineage_guard_rows": len(rows),
        **counts,
        "policy": "P735 remains empty and fail-closed until a real receipt and its provenance chain exist.",
    }
    OUT.write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows + [summary]),
        encoding="utf-8",
    )
    report = {
        "manifest_id": "P735",
        "created_at": created_at,
        "local_only": True,
        "lineage_guard_rows": len(rows),
        **counts,
        "artifact_jsonl": str(OUT.relative_to(ROOT)),
        "artifact_md": str(MD.relative_to(ROOT)),
        "policy": "P735 is planning-only and fail-closed.",
    }
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    MD.write_text(
        f"# P735 receipt-to-decision lineage guard\n\nRows: `{len(rows)}`. Complete lineage: `0`. Formal decisions written: `0`.\n",
        encoding="utf-8",
    )
    print(json.dumps({"manifest_id": "P735", "lineage_guard_rows": len(rows), "lineage_complete_rows": 0, "output": str(REPORT)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
