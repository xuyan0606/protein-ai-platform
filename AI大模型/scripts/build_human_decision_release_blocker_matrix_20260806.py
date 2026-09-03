#!/usr/bin/env python3
"""Build a release-blocker matrix for human decision gates."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
BACKLOG = ROOT / "reports" / "human_decision_backlog_report.json"
DEFAULT_OUTPUT = ROOT / "reports" / "human_decision_release_blocker_matrix_20260806.json"


def load(path_value: str | None) -> dict[str, Any]:
    if not path_value:
        return {}
    path = ROOT / path_value
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() and path.suffix == ".json" else {}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    backlog = json.loads(BACKLOG.read_text(encoding="utf-8"))
    rows = []
    for item in backlog.get("items", []):
        report = load(item.get("validator_report"))
        missing = int(item.get("missing_rows") or 0)
        completed = int(item.get("completed_rows") or 0)
        valid_rows = int(item.get("current_valid_rows") or report.get("valid_rows") or 0)
        blocker_type = "manual_rows_missing" if missing else "release_acceptance_missing"
        if valid_rows and missing:
            blocker_type = "partial_valid_rows_manual_rows_missing"
        if item.get("workstream") in {"workstream_acceptance", "operator_review_actions"}:
            blocker_type = "formal_acceptance_or_action_missing"
        rows.append({
            "backlog_id": item.get("backlog_id"),
            "workstream": item.get("workstream"),
            "priority": item.get("priority"),
            "required_rows": item.get("required_rows"),
            "completed_rows": completed,
            "missing_rows": missing,
            "valid_rows": valid_rows,
            "decision_input": item.get("decision_input"),
            "validator_report": item.get("validator_report"),
            "blocker_type": blocker_type,
            "next_action": item.get("next_action"),
            "release_ready": False,
            "safe_for_model_claim": False,
        })
    output = {
        "schema_version": 1,
        "created_at": "2026-08-06",
        "mode": "human_decision_release_blocker_matrix",
        "write_policy": "matrix_only; no_formal_decision_rows_written",
        "summary": {
            "rows": len(rows),
            "open_items": backlog.get("open_items"),
            "missing_rows": backlog.get("total_missing_rows"),
            "partial_valid_blockers": sum(1 for row in rows if row["blocker_type"] == "partial_valid_rows_manual_rows_missing"),
            "acceptance_action_blockers": sum(1 for row in rows if row["blocker_type"] == "formal_acceptance_or_action_missing"),
            "formal_decision_rows_written": 0,
            "release_ready": False,
            "safe_for_model_claim": False,
        },
        "rows": rows,
    }
    args.output.write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(output["summary"], ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
