#!/usr/bin/env python3
"""Build a source-bound audit of P26 numbering formal-review gaps."""

from __future__ import annotations

import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
PACKET_BOARD = AI_ROOT / "datasets" / "curation" / "numbering_review_packet_board.jsonl"
PACKET_REPORT = AI_ROOT / "reports" / "numbering_review_packet_board_report.json"
BRIEFING_BOARD = AI_ROOT / "datasets" / "curation" / "numbering_review_briefing_status_board.jsonl"
BRIEFING_REPORT = AI_ROOT / "reports" / "numbering_review_briefing_status_board_report.json"
OUT_JSONL = AI_ROOT / "datasets" / "curation" / "p26_numbering_formal_review_gap_audit.jsonl"
OUT_REPORT = AI_ROOT / "reports" / "p26_numbering_formal_review_gap_audit_report.json"


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def base(audit_id: str, gap_type: str, source_report: str, source_state: dict[str, Any], blocker: str) -> dict[str, Any]:
    return {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "local_only": True,
        "audit_id": audit_id,
        "gap_type": gap_type,
        "source_report": source_report,
        "source_state": source_state,
        "blocker": blocker,
        "training_import_allowed": False,
        "safe_for_training_import": False,
        "safe_for_model_claim": False,
        "release_ready": False,
        "production_execution_allowed": False,
        "policy": "Numbering review audit only; packet/briefing status is not a formal reviewed decision, supervised label, model claim, or release approval.",
    }


def main() -> int:
    packet_rows = load_jsonl(PACKET_BOARD)
    packet_report = load_json(PACKET_REPORT)
    briefing_rows = load_jsonl(BRIEFING_BOARD)
    briefing_report = load_json(BRIEFING_REPORT)
    rows: list[dict[str, Any]] = []

    for row in packet_rows:
        rows.append(base(
            f"p26-numbering-packet::{row.get('packet_id')}",
            "numbering_review_packet",
            "reports/numbering_review_packet_board_report.json",
            {
                "packet_id": row.get("packet_id"),
                "packet_rows": row.get("packet_rows"),
                "packet_status": row.get("packet_status"),
                "decision_rows_present": row.get("decision_rows_present"),
                "completion_ready": row.get("completion_ready"),
                "requires_human_input": row.get("requires_human_input"),
            },
            "packet remains open and requires formal human numbering review",
        ) | {
            "packet_id": row.get("packet_id"),
            "packet_status": row.get("packet_status"),
            "decision_rows_present": row.get("decision_rows_present"),
            "completion_ready": row.get("completion_ready"),
        })

    for row in briefing_rows:
        rows.append(base(
            f"p26-numbering-briefing::{row.get('record_id')}",
            "numbering_review_briefing",
            "reports/numbering_review_briefing_status_board_report.json",
            {
                "record_id": row.get("record_id"),
                "briefing_status": row.get("briefing_status"),
                "decision_row_present": row.get("decision_row_present"),
                "completion_ready": row.get("completion_ready"),
                "requires_human_input": row.get("requires_human_input"),
            },
            "briefing navigation row is not a validated/applied formal numbering decision",
        ) | {
            "record_id": row.get("record_id"),
            "briefing_status": row.get("briefing_status"),
            "decision_row_present": row.get("decision_row_present"),
            "completion_ready": row.get("completion_ready"),
        })

    report = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "local_only": True,
        "audit_rows": len(rows),
        "packet_audit_rows": len(packet_rows),
        "briefing_audit_rows": len(briefing_rows),
        "packet_report_rows": packet_report.get("packet_board_rows"),
        "packet_open_blocked_rows": packet_report.get("open_blocked_packet_rows"),
        "packet_completion_ready_rows": packet_report.get("completion_ready_rows"),
        "briefing_report_rows": briefing_report.get("status_rows"),
        "briefing_open_blocked_rows": briefing_report.get("open_blocked_briefing_rows"),
        "briefing_decision_input_rows": briefing_report.get("decision_input_rows"),
        "briefing_completion_ready_rows": briefing_report.get("completion_ready_rows"),
        "packet_status_counts": dict(sorted(Counter(row.get("packet_status") for row in packet_rows).items())),
        "briefing_status_counts": dict(sorted(Counter(row.get("briefing_status") for row in briefing_rows).items())),
        "formal_review_rows": 0,
        "claim_eligible_rows_now": 0,
        "training_import_allowed": False,
        "safe_for_training_import": False,
        "safe_for_model_claim": False,
        "release_ready": False,
        "production_execution_allowed": False,
        "audit_jsonl": "datasets/curation/p26_numbering_formal_review_gap_audit.jsonl",
        "policy": "P26 numbering packet/briefing audit only. No formal decisions are written, validated, applied, or promoted by this audit.",
    }
    write_jsonl(OUT_JSONL, rows)
    OUT_REPORT.parent.mkdir(parents=True, exist_ok=True)
    OUT_REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "audit_rows": report["audit_rows"],
        "packet_audit_rows": report["packet_audit_rows"],
        "briefing_audit_rows": report["briefing_audit_rows"],
        "packet_open_blocked_rows": report["packet_open_blocked_rows"],
        "briefing_open_blocked_rows": report["briefing_open_blocked_rows"],
        "formal_review_rows": 0,
        "output": str(OUT_REPORT),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
