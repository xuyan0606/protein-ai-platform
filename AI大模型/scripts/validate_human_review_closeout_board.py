#!/usr/bin/env python3
"""Validate human review closeout board remains fail-closed."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path


AI_ROOT = Path(__file__).resolve().parents[1]
BOARD = AI_ROOT / "datasets" / "governance" / "human_review_closeout_board.jsonl"
REPORT = AI_ROOT / "reports" / "human_review_closeout_board_validation_report.json"
EXPECTED = [
    "numbering_curation",
    "plate_feedback_intake",
    "external_license_review",
    "sequence_ip_fto",
    "biosecurity_screening",
]


def load_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate human review closeout board")
    parser.add_argument("--board", type=Path, default=BOARD)
    parser.add_argument("--report", type=Path, default=REPORT)
    args = parser.parse_args()

    rows = load_jsonl(args.board)
    failures = []
    lane_ids = [row.get("lane_id") for row in rows]
    if lane_ids != EXPECTED:
        failures.append({"check": "lane_order", "observed": lane_ids, "expected": EXPECTED})
    for row in rows:
        lane = row.get("lane_id")
        if row.get("status") != "awaiting_human_decision":
            failures.append({"check": f"{lane}_status", "observed": row.get("status"), "expected": "awaiting_human_decision"})
        if row.get("requires_human_input") is not True:
            failures.append({"check": f"{lane}_requires_human_input", "observed": row.get("requires_human_input"), "expected": True})
        if row.get("completion_ready") is not False or row.get("closeout_ready") is not False:
            failures.append({"check": f"{lane}_not_ready", "observed": {"completion_ready": row.get("completion_ready"), "closeout_ready": row.get("closeout_ready")}, "expected": False})
        for field in ["operator_open_first", "formal_decision_target", "formal_validator_report"]:
            if not row.get(field):
                failures.append({"check": f"{lane}_{field}_present", "observed": row.get(field), "expected": "non-empty"})

    report = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "local_only": True,
        "success": not failures,
        "closeout_rows": len(rows),
        "awaiting_human_decision_rows": sum(1 for row in rows if row.get("status") == "awaiting_human_decision"),
        "completion_ready_rows": sum(1 for row in rows if row.get("completion_ready")),
        "failures": failures,
        "policy": "Validation only. Closeout board rows do not write decisions or grant readiness.",
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"success": report["success"], "closeout_rows": len(rows), "failures": len(failures), "output": str(args.report)}, ensure_ascii=False))
    return 0 if report["success"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
