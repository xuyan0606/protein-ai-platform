#!/usr/bin/env python3
"""Validate P735 receipt-to-decision lineage guard."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from build_p700_p0_real_input_pending_build_checklist import load_json, load_jsonl
from build_p735_p0_pending_build_review_receipt_to_decision_lineage_guard import FALSE_FIELDS


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "datasets/governance/p734_p0_pending_build_review_receipt_freshness_staleness_guard.jsonl"
BOARD = ROOT / "datasets/governance/p735_p0_pending_build_review_receipt_to_decision_lineage_guard.jsonl"
REPORT = ROOT / "reports/p735_p0_pending_build_review_receipt_to_decision_lineage_guard_report.json"
OUT = ROOT / "reports/p735_p0_pending_build_review_receipt_to_decision_lineage_guard_validation_report.json"


def main() -> int:
    source_rows = [row for row in load_jsonl(SOURCE) if row.get("boundary") != "summary"]
    rows = load_jsonl(BOARD)
    guards = rows[:-1] if rows else []
    summary = rows[-1] if rows else {}
    report = load_json(REPORT)
    failures: list[dict[str, Any]] = []

    def fail(check: str, condition: bool, observed: Any, expected: Any) -> None:
        if condition:
            failures.append({"check": check, "observed": observed, "expected": expected})

    fail("source_rows", len(source_rows) != 5, len(source_rows), 5)
    fail("guard_rows", len(guards) != 5, len(guards), 5)
    fail("summary_present", summary.get("boundary") != "summary", summary.get("boundary"), "summary")
    source_ids = {row.get("freshness_guard_id") for row in source_rows}
    observed_ids = {row.get("source_p734_id") for row in guards}
    fail("source_coverage", observed_ids != source_ids, sorted(str(value) for value in observed_ids), sorted(str(value) for value in source_ids))
    for field in FALSE_FIELDS:
        fail(f"report_{field}_rows", report.get(f"{field}_rows") != 0, report.get(f"{field}_rows"), 0)
        fail(f"summary_{field}_rows", summary.get(f"{field}_rows") != 0, summary.get(f"{field}_rows"), 0)
    for index, row in enumerate(guards, start=1):
        fail(
            f"row_{index}_status",
            row.get("guard_status") != "empty_no_receipt_lineage_to_validate",
            row.get("guard_status"),
            "empty_no_receipt_lineage_to_validate",
        )
        for field in FALSE_FIELDS:
            fail(f"row_{index}_{field}", row.get(field) is not False, row.get(field), False)

    result = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "manifest_id": "P735",
        "local_only": True,
        "success": not failures,
        "failure_count": len(failures),
        "failures": failures,
        "lineage_guard_rows": len(guards),
        **{f"{field}_rows": 0 for field in FALSE_FIELDS},
        "policy": "Validation only; no receipt-to-decision lineage exists to promote.",
    }
    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"success": result["success"], "lineage_guard_rows": len(guards), "lineage_complete_rows": 0, "formal_decision_written_rows": 0, "failures": len(failures), "output": str(OUT)}, ensure_ascii=False))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
