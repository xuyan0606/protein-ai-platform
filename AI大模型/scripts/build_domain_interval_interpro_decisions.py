#!/usr/bin/env python3
"""Build program-reviewed domain interval decisions from exact InterPro evidence.

Only exact Pfam rows with one unambiguous interval are promoted to local domain
decisions. Multi-interval rows stay unresolved because the current decision
schema has one start/end interval per domain_record_id.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = AI_ROOT / "datasets" / "curation" / "domain_interpro_evidence.jsonl"
DECISIONS = AI_ROOT / "datasets" / "curation" / "domain_interval_decisions.jsonl"
REPORT_OUT = AI_ROOT / "reports" / "domain_interval_interpro_decision_report.json"


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")


def valid_single_interval(row: dict[str, Any]) -> tuple[dict[str, Any] | None, str]:
    intervals = row.get("matched_pfam_intervals") or []
    if len(intervals) != 1:
        return None, "not_single_interval"
    interval = intervals[0]
    start = interval.get("start")
    end = interval.get("end")
    seq_len = row.get("sequence_length") or interval.get("protein_length") or 0
    if not isinstance(start, int) or not isinstance(end, int):
        return None, "missing_interval"
    if start < 1 or end < start or (seq_len and end > seq_len):
        return None, "invalid_range"
    if interval.get("pfam_id") != row.get("pfam_id"):
        return None, "pfam_mismatch"
    if interval.get("source_database") not in {"reviewed", "unreviewed"}:
        return None, "missing_interpro_source"
    return interval, "ok"


def decision_for(row: dict[str, Any], interval: dict[str, Any]) -> dict[str, Any]:
    return {
        "domain_record_id": int(row["domain_record_id"]),
        "decision": "set_interval",
        "start_pos": int(interval["start"]),
        "end_pos": int(interval["end"]),
        "basis": "pfam_annotation",
        "confidence": 0.9 if interval.get("source_database") == "reviewed" else 0.8,
        "notes": (
            "Program-reviewed exact Pfam interval from InterPro API; "
            f"pfam={row.get('pfam_id')}; model={interval.get('model')}; "
            f"score={interval.get('score')}; dc_status={interval.get('dc_status')}; "
            "multi-interval rows are not auto-selected."
        ),
        "curator": "interpro-pfam-api-local-curation",
        "curated_at": "2026-07-25T00:00:00+08:00",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Build InterPro-derived domain interval decisions")
    parser.add_argument("--evidence", type=Path, default=EVIDENCE)
    parser.add_argument("--decisions", type=Path, default=DECISIONS)
    parser.add_argument("--report", type=Path, default=REPORT_OUT)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    evidence_rows = load_jsonl(args.evidence)
    existing = load_jsonl(args.decisions)
    existing_by_id = {row.get("domain_record_id"): row for row in existing if row.get("domain_record_id") is not None}

    generated = []
    skip_reasons = Counter()
    for row in evidence_rows:
        record_id = row.get("domain_record_id")
        if record_id in existing_by_id:
            skip_reasons["existing_decision_preserved"] += 1
            continue
        interval, reason = valid_single_interval(row)
        if not interval:
            skip_reasons[reason] += 1
            continue
        generated.append(decision_for(row, interval))

    merged = sorted(existing + generated, key=lambda item: int(item.get("domain_record_id") or 0))
    interpro_program_reviewed = sum(
        1
        for row in merged
        if row.get("decision") == "set_interval"
        and row.get("basis") == "pfam_annotation"
        and row.get("curator") == "interpro-pfam-api-local-curation"
    )
    if not args.dry_run:
        write_jsonl(args.decisions, merged)

    report = {
        "evidence_rows": len(evidence_rows),
        "existing_decisions_preserved": len(existing),
        "generated_decisions": len(generated),
        "merged_decision_rows": len(merged),
        "interpro_program_reviewed_decisions": interpro_program_reviewed,
        "skip_reasons": dict(skip_reasons),
        "output": str(args.decisions),
        "dry_run": args.dry_run,
        "policy": "only exact single-interval InterPro/Pfam evidence is converted; multi-interval rows require separate review",
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "generated_decisions": report["generated_decisions"],
        "merged_decision_rows": report["merged_decision_rows"],
        "dry_run": args.dry_run,
        "output": str(args.report),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
