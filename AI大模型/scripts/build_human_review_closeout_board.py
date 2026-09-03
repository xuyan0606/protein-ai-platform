#!/usr/bin/env python3
"""Build a fail-closed closeout board for human review launch lanes."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
LAUNCH = AI_ROOT / "datasets" / "governance" / "human_review_launch_board.jsonl"
OUT = AI_ROOT / "datasets" / "governance" / "human_review_closeout_board.jsonl"
REPORT = AI_ROOT / "reports" / "human_review_closeout_board_report.json"


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists() or path.suffix != ".json":
        return {}
    value = json.loads(path.read_text(encoding="utf-8"))
    return value if isinstance(value, dict) else {}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def count_jsonl(rel_path: str | None) -> int | None:
    if not rel_path:
        return None
    path = AI_ROOT / rel_path
    if not path.exists() or path.suffix != ".jsonl":
        return None
    return len(load_jsonl(path))


def validator_summary(rel_path: str | None) -> dict[str, Any]:
    if not rel_path:
        return {}
    data = load_json(AI_ROOT / rel_path)
    keys = [
        "success",
        "decision_rows",
        "valid_rows",
        "invalid_rows",
        "approved_for_customer_delivery_rows",
        "approved_for_ordering_rows",
        "verified_rows",
        "training_eligible_rows",
        "ready_for_customer_delivery",
        "ready_for_ordering",
    ]
    return {key: data.get(key) for key in keys if key in data}


def main() -> int:
    parser = argparse.ArgumentParser(description="Build human review closeout board")
    parser.add_argument("--launch", type=Path, default=LAUNCH)
    parser.add_argument("--output", type=Path, default=OUT)
    parser.add_argument("--report", type=Path, default=REPORT)
    args = parser.parse_args()

    launch_rows = load_jsonl(args.launch)
    rows: list[dict[str, Any]] = []
    for row in launch_rows:
        formal_rows = count_jsonl(row.get("formal_decision_target"))
        summary = validator_summary(row.get("validation_report"))
        formal_validator_report = {
            "numbering_curation": "reports/numbering_curation_validation_report.json",
            "plate_feedback_intake": "reports/experiment_feedback_plate_intake_validation_report.json",
            "external_license_review": "reports/external_license_review_decision_validation_report.json",
            "sequence_ip_fto": "reports/sequence_ip_fto_decision_validation_report.json",
            "biosecurity_screening": "reports/biosecurity_screening_decision_validation_report.json",
        }.get(str(row.get("lane_id")))
        formal_summary = validator_summary(formal_validator_report)
        closeout_ready = False
        rows.append({
            "closeout_id": f"human-review-closeout::{row.get('lane_id')}",
            "launch_id": row.get("launch_id"),
            "lane_id": row.get("lane_id"),
            "priority": row.get("priority"),
            "operator_open_first": row.get("operator_open_first"),
            "packet_rows": row.get("packet_rows"),
            "prepared_validation_report": row.get("validation_report"),
            "prepared_validation_summary": summary,
            "formal_decision_target": row.get("formal_decision_target"),
            "formal_decision_rows": formal_rows,
            "formal_validator_report": formal_validator_report,
            "formal_validator_summary": formal_summary,
            "status": "awaiting_human_decision",
            "closeout_ready": closeout_ready,
            "requires_human_input": True,
            "completion_ready": False,
            "next_action": row.get("human_action"),
            "policy": "Closeout board only. It reports current row counts and validator summaries; it does not write decisions, approve readiness, or close work.",
        })

    write_jsonl(args.output, rows)
    report = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "local_only": True,
        "closeout_rows": len(rows),
        "awaiting_human_decision_rows": sum(1 for row in rows if row["status"] == "awaiting_human_decision"),
        "closeout_ready_rows": 0,
        "completion_ready_rows": 0,
        "requires_human_input_rows": len(rows),
        "total_prepared_packet_rows": sum(int(row.get("packet_rows") or 0) for row in rows),
        "total_formal_decision_rows": sum(int(row.get("formal_decision_rows") or 0) for row in rows),
        "jsonl": str(args.output),
        "policy": "Human review closeout board only. It does not grant approvals, claims, customer delivery, ordering, training, or release readiness.",
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({
        "closeout_rows": report["closeout_rows"],
        "awaiting_human_decision_rows": report["awaiting_human_decision_rows"],
        "total_prepared_packet_rows": report["total_prepared_packet_rows"],
        "total_formal_decision_rows": report["total_formal_decision_rows"],
        "output": str(args.report),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
