#!/usr/bin/env python3
"""Build row-level status for the compact numbering review briefing.

The status board is operator navigation only. It records which briefing rows
still need human reviewed numbering decisions, but it never creates curation
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
BRIEFING_JSON = AI_ROOT / "reports" / "numbering_review_briefing.json"
BRIEFING_VALIDATION = AI_ROOT / "reports" / "numbering_review_briefing_validation_report.json"
DECISIONS = AI_ROOT / "datasets" / "curation" / "numbering_curation_decisions.jsonl"
OUT_JSONL = AI_ROOT / "datasets" / "curation" / "numbering_review_briefing_status_board.jsonl"
OUT_REPORT = AI_ROOT / "reports" / "numbering_review_briefing_status_board_report.json"
OUT_MD = AI_ROOT / "reports" / "numbering_review_briefing_status_board.md"


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def review_status(decision_present: bool) -> str:
    if decision_present:
        return "reviewed_decision_present_requires_validation_apply"
    return "open_blocked_waiting_for_human_review"


def build_markdown(report: dict[str, Any], rows: list[dict[str, Any]]) -> str:
    lines = [
        "# Numbering Review Briefing Status Board",
        "",
        f"Generated: {report['created_at']}",
        "",
        "This board is local operator tracking only. It is not a reviewed numbering decision, not a training label, and not model claim readiness.",
        "",
        "| Order | Packet | Record | UniProt | Mutation | Title flag | Decision present | Status | Open first |",
        "|---:|---|---|---|---|---|---|---|---|",
    ]
    for row in rows:
        lines.append(
            f"| {row.get('execution_order')} | {row.get('packet_id')} | {row.get('record_id')} | "
            f"{row.get('uniprot_id')} | {row.get('mutation')} | {row.get('title_flag')} | "
            f"{row.get('decision_row_present')} | {row.get('briefing_status')} | {row.get('operator_open_first')} |"
        )
    lines.extend([
        "",
        "## Required Commands After Human Review",
        "",
        "1. `python3 scripts/validate_numbering_review_briefing_status_board.py`",
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
    parser = argparse.ArgumentParser(description="Build numbering review briefing status board")
    parser.add_argument("--briefing-json", type=Path, default=BRIEFING_JSON)
    parser.add_argument("--briefing-validation", type=Path, default=BRIEFING_VALIDATION)
    parser.add_argument("--decisions", type=Path, default=DECISIONS)
    parser.add_argument("--output", type=Path, default=OUT_JSONL)
    parser.add_argument("--report", type=Path, default=OUT_REPORT)
    parser.add_argument("--markdown", type=Path, default=OUT_MD)
    args = parser.parse_args()

    briefing = load_json(args.briefing_json)
    briefing_validation = load_json(args.briefing_validation)
    decision_rows = load_jsonl(args.decisions)
    decision_record_ids = {str(row.get("record_id") or "") for row in decision_rows if row.get("record_id")}

    rows: list[dict[str, Any]] = []
    for order, briefing_row in enumerate(briefing.get("briefing_rows") or [], start=1):
        record_id = str(briefing_row.get("record_id") or "")
        decision_present = record_id in decision_record_ids
        status = review_status(decision_present)
        rows.append({
            "briefing_status_id": f"numbering-briefing-status-{record_id}",
            "execution_order": order,
            "packet_id": briefing_row.get("packet_id"),
            "record_id": record_id,
            "bucket": briefing_row.get("bucket"),
            "uniprot_id": briefing_row.get("uniprot_id"),
            "mutation": briefing_row.get("mutation"),
            "current_residue": briefing_row.get("current_residue"),
            "pmid": briefing_row.get("pmid"),
            "title_flag": briefing_row.get("title_flag"),
            "briefing_status": status,
            "decision_row_present": decision_present,
            "decision_rows_present": 1 if decision_present else 0,
            "completion_ready": False,
            "requires_human_input": not decision_present,
            "claim_eligible_rows_now": 0,
            "safe_for_model_claim": False,
            "operator_open_first": "reports/numbering_review_briefing.md",
            "source_briefing_json": str(args.briefing_json),
            "write_reviewed_decisions_to": "datasets/curation/numbering_curation_decisions.jsonl",
            "validation_command": "python3 scripts/validate_numbering_review_briefing_status_board.py",
            "curation_validator_command": "python3 scripts/validate_numbering_curation_decisions.py",
            "apply_command": "python3 scripts/apply_numbering_curation.py",
            "safe_pipeline_command": "python3 scripts/run_safe_training_pipeline.py",
            "required_human_actions": [
                "confirm source protein identity and mutation in the original source",
                "confirm canonical, isoform, mature-protein, construct, or author numbering basis",
                "write a reviewed numbering decision only if evidence is sufficient",
                "validate and apply reviewed decisions before any downstream training use",
            ],
            "completion_condition": "reviewed decision row exists, passes numbering curation validation, is applied, and safe pipeline reruns; status board alone is never sufficient",
            "policy": "Navigation only; not a curation decision, not a supervised label, and not model claim readiness.",
        })

    write_jsonl(args.output, rows)
    status_counts = Counter(str(row.get("briefing_status") or "") for row in rows)
    title_flag_counts = Counter(str(row.get("title_flag") or "") for row in rows)
    packet_counts = Counter(str(row.get("packet_id") or "") for row in rows)
    report = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "local_only": True,
        "briefing_rows": len(rows),
        "briefing_validation_all_rows_valid": bool(briefing_validation.get("all_rows_valid")),
        "status_counts": dict(sorted(status_counts.items())),
        "packet_counts": dict(sorted(packet_counts.items())),
        "title_flag_counts": dict(sorted(title_flag_counts.items())),
        "decision_input_rows": len(decision_rows),
        "decision_rows_present_for_briefing": sum(1 for row in rows if row["decision_row_present"]),
        "open_blocked_briefing_rows": status_counts.get("open_blocked_waiting_for_human_review", 0),
        "completion_ready_rows": 0,
        "requires_human_input_rows": sum(1 for row in rows if row["requires_human_input"]),
        "ready_for_decision_write_rows": 0,
        "claim_eligible_rows_now": 0,
        "safe_for_model_claim": False,
        "briefing_json": str(args.briefing_json),
        "briefing_validation": str(args.briefing_validation),
        "decision_input": str(args.decisions),
        "output": str(args.output),
        "markdown": str(args.markdown),
        "policy": "Briefing status board tracks missing human numbering review only; it never writes reviewed decisions, promotes labels, or enables model claims.",
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    args.markdown.write_text(build_markdown(report, rows), encoding="utf-8")
    print(json.dumps({
        "briefing_status_rows": report["briefing_rows"],
        "open_blocked_briefing_rows": report["open_blocked_briefing_rows"],
        "decision_rows_present_for_briefing": report["decision_rows_present_for_briefing"],
        "output": str(args.report),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
