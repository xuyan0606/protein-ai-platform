#!/usr/bin/env python3
"""Validate the fail-closed human review launch board."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
BOARD = AI_ROOT / "datasets" / "governance" / "human_review_launch_board.jsonl"
REPORT = AI_ROOT / "reports" / "human_review_launch_board_validation_report.json"
EXPECTED_LANES = [
    "numbering_curation",
    "plate_feedback_intake",
    "strict_holdout",
    "substrate_identity",
    "external_license_review",
    "sequence_ip_fto",
    "biosecurity_screening",
]


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate human review launch board")
    parser.add_argument("--board", type=Path, default=BOARD)
    parser.add_argument("--report", type=Path, default=REPORT)
    args = parser.parse_args()

    rows = load_jsonl(args.board)
    failures: list[dict[str, Any]] = []
    lane_ids = [row.get("lane_id") for row in rows]
    if lane_ids != EXPECTED_LANES:
        failures.append({"check": "lane_order", "observed": lane_ids, "expected": EXPECTED_LANES})
    for row in rows:
        lane = row.get("lane_id")
        if row.get("requires_human_input") is not True:
            failures.append({"check": f"{lane}_requires_human_input", "observed": row.get("requires_human_input"), "expected": True})
        if row.get("completion_ready") is not False:
            failures.append({"check": f"{lane}_completion_ready_false", "observed": row.get("completion_ready"), "expected": False})
        if row.get("packet_rows", 0) <= 0:
            failures.append({"check": f"{lane}_packet_rows_positive", "observed": row.get("packet_rows"), "expected": ">0"})
        for field in ["operator_open_first", "prepared_report", "validation_report", "formal_decision_target", "formal_validator"]:
            if not row.get(field):
                failures.append({"check": f"{lane}_has_{field}", "observed": row.get(field), "expected": "non-empty"})
        forbidden_true_fields = ["approved_for_customer_delivery", "ready_for_ordering", "release_ready", "safe_for_model_claim"]
        for field in forbidden_true_fields:
            if row.get(field) is True:
                failures.append({"check": f"{lane}_{field}_not_true", "observed": True, "expected": "absent_or_false"})

    report = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "local_only": True,
        "board": str(args.board),
        "success": not failures,
        "launch_rows": len(rows),
        "ready_for_human_review_rows": sum(1 for row in rows if row.get("status") == "ready_for_human_review"),
        "completion_ready_rows": sum(1 for row in rows if row.get("completion_ready")),
        "failures": failures,
        "policy": "Validation only. Launch board rows are not formal decisions and do not grant approvals or readiness.",
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"success": report["success"], "launch_rows": len(rows), "failures": len(failures), "output": str(args.report)}, ensure_ascii=False))
    return 0 if report["success"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
