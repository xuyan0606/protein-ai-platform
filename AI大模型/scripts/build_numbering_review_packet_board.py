#!/usr/bin/env python3
"""Build a local operator board for numbering review packets.

This board is a navigation aid only. It summarizes the review packets and
their unresolved draft decisions, but it never writes reviewed curation
decisions or supervised labels.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
PACKET_REPORT = AI_ROOT / "reports" / "numbering_review_packet_report.json"
VALIDATION_REPORT = AI_ROOT / "reports" / "numbering_review_packet_validation_report.json"
STATUS_FILE = AI_ROOT / "datasets" / "curation" / "numbering_review_packets_status.jsonl"
BOARD_OUT = AI_ROOT / "datasets" / "curation" / "numbering_review_packet_board.jsonl"
REPORT_OUT = AI_ROOT / "reports" / "numbering_review_packet_board_report.json"
MARKDOWN_OUT = AI_ROOT / "reports" / "numbering_review_packet_board.md"


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def status_by_packet_id(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {str(row.get("packet_id") or ""): row for row in rows if row.get("packet_id")}


def packet_actions(row: dict[str, Any]) -> list[str]:
    return [
        "review the original source and confirm numbering",
        "append only reviewed rows to datasets/curation/numbering_curation_decisions.jsonl",
        "validate reviewed decisions with scripts/validate_numbering_curation_decisions.py",
        "apply reviewed decisions with scripts/apply_numbering_curation.py",
        "rerun scripts/run_safe_training_pipeline.py",
    ]


def build_markdown(report: dict[str, Any], rows: list[dict[str, Any]]) -> str:
    lines = [
        "# Numbering Review Packet Board",
        "",
        f"Generated: {report['created_at']}",
        "",
        "This board is local operator tracking only. It is not a reviewed curation decision and not a supervised label source.",
        "",
        "| Order | Packet | Rows | Draft Rows | Status | Valid |",
        "|---:|---|---:|---:|---|---|",
    ]
    for row in rows:
        lines.append(
            f"| {row.get('packet_rank')} | {row.get('packet_id')} | {row.get('packet_rows')} | "
            f"{row.get('draft_rows')} | {row.get('packet_status')} | {row.get('valid_packet')} / {row.get('valid_draft')} |"
        )
    lines.extend([
        "",
        "## Commands",
        "",
        "1. `python3 scripts/validate_numbering_review_packets.py`",
        "1. `python3 scripts/validate_numbering_curation_decisions.py`",
        "1. `python3 scripts/apply_numbering_curation.py`",
        "1. `python3 scripts/run_safe_training_pipeline.py`",
        "",
        "## Policy",
        "",
        report["policy"],
        "",
    ])
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Build numbering review packet board")
    parser.add_argument("--packet-report", type=Path, default=PACKET_REPORT)
    parser.add_argument("--validation-report", type=Path, default=VALIDATION_REPORT)
    parser.add_argument("--status-file", type=Path, default=STATUS_FILE)
    parser.add_argument("--output", type=Path, default=BOARD_OUT)
    parser.add_argument("--report", type=Path, default=REPORT_OUT)
    parser.add_argument("--markdown", type=Path, default=MARKDOWN_OUT)
    args = parser.parse_args()

    packet_report = load_json(args.packet_report)
    validation_report = load_json(args.validation_report)
    status_rows = load_jsonl(args.status_file)
    status_lookup = status_by_packet_id(status_rows)

    board_rows: list[dict[str, Any]] = []
    for rank, packet in enumerate(packet_report.get("packet_reports") or [], start=1):
        packet_id = str(packet.get("packet_id") or "")
        status = status_lookup.get(packet_id, {})
        row = {
            "packet_board_id": f"numbering-review-{packet_id}",
            "packet_rank": rank,
            "packet_id": packet_id,
            "packet_rows": int(packet.get("rows") or 0),
            "draft_rows": int(packet.get("rows") or 0),
            "bucket_counts": packet.get("bucket_counts") or {},
            "packet_file": packet.get("jsonl"),
            "draft_file": packet.get("decision_draft"),
            "markdown_file": packet.get("markdown"),
            "packet_status": "open_blocked_waiting_for_human_review",
            "valid_packet": bool(status.get("valid_packet")),
            "valid_draft": bool(status.get("valid_draft")),
            "completion_ready": False,
            "requires_human_input": True,
            "decision_rows_present": 0,
            "authorized_rows": 0,
            "preflight_rows_present": 0,
            "safe_for_model_claim": False,
            "review_first_record_id": (load_jsonl(Path(packet.get("jsonl") or "")) or [{}])[0].get("record_id"),
            "operator_open_first": packet.get("jsonl"),
            "write_reviewed_decisions_to": "datasets/curation/numbering_curation_decisions.jsonl",
            "validation_command": "python3 scripts/validate_numbering_review_packets.py",
            "curation_validator_command": "python3 scripts/validate_numbering_curation_decisions.py",
            "apply_command": "python3 scripts/apply_numbering_curation.py",
            "safe_pipeline_command": "python3 scripts/run_safe_training_pipeline.py",
            "packet_actions": packet_actions(packet),
            "completion_condition": "all reviewed decisions are manually written, validated, applied, and the safe pipeline is rerun; packet board alone is never sufficient",
            "policy": "Numbering review packet board only; not a reviewed curation decision, not a supervised label, and not model claim readiness.",
        }
        board_rows.append(row)

    write_jsonl(args.output, board_rows)
    status_counts = Counter(str(row.get("packet_status") or "") for row in board_rows)
    report = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "local_only": True,
        "packet_board_rows": len(board_rows),
        "packet_count": validation_report.get("packet_count") or packet_report.get("packets") or len(board_rows),
        "packet_rows": validation_report.get("packet_rows") or packet_report.get("packet_rows") or sum(int(row.get("packet_rows") or 0) for row in board_rows),
        "valid_packet_rows": validation_report.get("valid_packet_rows") or 0,
        "valid_draft_rows": validation_report.get("valid_draft_rows") or 0,
        "invalid_packet_rows": validation_report.get("invalid_packet_rows") or 0,
        "invalid_draft_rows": validation_report.get("invalid_draft_rows") or 0,
        "open_blocked_packet_rows": status_counts.get("open_blocked_waiting_for_human_review", 0),
        "completion_ready_rows": 0,
        "requires_human_input_rows": len(board_rows),
        "ready_for_decision_rows": 0,
        "claim_eligible_rows_now": 0,
        "safe_for_model_claim": False,
        "packet_status_counts": dict(sorted(status_counts.items())),
        "validation_report": str(args.validation_report),
        "status_file": str(args.status_file),
        "output": str(args.output),
        "markdown": str(args.markdown),
        "policy": "Numbering review packet board tracks missing human review only; it never writes reviewed decisions, validates labels into training, or enables model claims.",
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    args.markdown.write_text(build_markdown(report, board_rows), encoding="utf-8")
    print(json.dumps({
        "packet_board_rows": report["packet_board_rows"],
        "open_blocked_packet_rows": report["open_blocked_packet_rows"],
        "output": str(args.report),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
