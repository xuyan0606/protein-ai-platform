#!/usr/bin/env python3
"""Validate biosecurity screening drafts as fail-closed pre-decision inputs."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
DRAFTS = AI_ROOT / "datasets" / "governance" / "biosecurity_screening_drafts.jsonl"
REPORT = AI_ROOT / "reports" / "biosecurity_screening_draft_validation_report.json"


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def validate(row: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    for field in ["screening_request_id", "candidate_id", "screening_state", "synthesis_permission", "human_reviewer_decision", "approved_for_ordering"]:
        if row.get(field) in {None, ""}:
            errors.append(f"missing_{field}")
    if row.get("screening_state") != "not_requested":
        errors.append("draft_screening_state_not_not_requested")
    if row.get("synthesis_permission") != "not_requested":
        errors.append("draft_synthesis_permission_not_not_requested")
    if row.get("human_reviewer_decision") != "not_reviewed":
        errors.append("draft_human_review_not_not_reviewed")
    if row.get("approved_for_ordering") is not False:
        errors.append("draft_contains_ordering_approval")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate biosecurity screening drafts")
    parser.add_argument("--drafts", type=Path, default=DRAFTS)
    parser.add_argument("--report", type=Path, default=REPORT)
    args = parser.parse_args()

    rows = load_jsonl(args.drafts)
    records = []
    for row in rows:
        errors = validate(row)
        records.append({
            "screening_request_id": row.get("screening_request_id"),
            "candidate_id": row.get("candidate_id"),
            "valid": not errors,
            "errors": errors,
        })
    invalid_rows = sum(1 for row in records if not row["valid"])
    report = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "local_only": True,
        "drafts": str(args.drafts),
        "draft_rows": len(rows),
        "valid_rows": len(rows) - invalid_rows,
        "invalid_rows": invalid_rows,
        "approved_for_ordering_rows": 0,
        "ready_for_ordering": False,
        "records": records[:200],
        "success": invalid_rows == 0 and len(rows) > 0,
        "policy": "Draft validation only. These rows are not screening decisions and do not grant ordering approval.",
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"success": report["success"], "draft_rows": len(rows), "invalid_rows": invalid_rows, "output": str(args.report)}, ensure_ascii=False))
    return 0 if report["success"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
