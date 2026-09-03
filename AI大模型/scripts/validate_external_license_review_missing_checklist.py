#!/usr/bin/env python3
"""Validate external license missing checklist as a fail-closed review aid."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
CHECKLIST = AI_ROOT / "datasets" / "governance" / "external_license_review_missing_checklist.jsonl"
REPORT = AI_ROOT / "reports" / "external_license_review_missing_checklist_validation_report.json"


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def validate(row: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    for field in ["checklist_id", "review_item_id", "item_type", "decision_present", "authorization_status", "formal_decision_target"]:
        if row.get(field) in {None, ""}:
            errors.append(f"missing_{field}")
    if row.get("approved_for_customer_delivery") is True:
        errors.append("checklist_contains_customer_delivery_approval")
    if row.get("verified_authorization") is True:
        errors.append("checklist_contains_verified_authorization")
    if row.get("formal_decision_target") != "datasets/governance/external_license_review_decisions.jsonl":
        errors.append("unexpected_formal_decision_target")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate external license review missing checklist")
    parser.add_argument("--checklist", type=Path, default=CHECKLIST)
    parser.add_argument("--report", type=Path, default=REPORT)
    args = parser.parse_args()

    rows = load_jsonl(args.checklist)
    records = []
    for row in rows:
        errors = validate(row)
        records.append({
            "checklist_id": row.get("checklist_id"),
            "review_item_id": row.get("review_item_id"),
            "valid": not errors,
            "errors": errors,
        })
    invalid_rows = sum(1 for row in records if not row["valid"])
    report = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "local_only": True,
        "checklist": str(args.checklist),
        "checklist_rows": len(rows),
        "valid_rows": len(rows) - invalid_rows,
        "invalid_rows": invalid_rows,
        "verified_rows": 0,
        "approved_for_customer_delivery_rows": 0,
        "records": records[:200],
        "success": invalid_rows == 0 and len(rows) > 0,
        "policy": "Checklist validation only. These rows are not license decisions and do not grant clearance.",
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"success": report["success"], "checklist_rows": len(rows), "invalid_rows": invalid_rows, "output": str(args.report)}, ensure_ascii=False))
    return 0 if report["success"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
