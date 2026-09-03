#!/usr/bin/env python3
"""Build prioritized numbering curation work batches."""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
QUEUE = AI_ROOT / "datasets" / "curation" / "numbering_curation_queue.jsonl"
DECISIONS = AI_ROOT / "datasets" / "curation" / "numbering_curation_decisions.jsonl"
OUT_DIR = AI_ROOT / "datasets" / "curation" / "batches"
REPORT_OUT = AI_ROOT / "reports" / "curation_batch_report.json"


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")


def write_markdown(path: Path, batch_id: str, rows: list[dict[str, Any]]) -> None:
    lines = [
        f"# Numbering Curation {batch_id}",
        "",
        "Goal: map reported mutation numbering to canonical UniProt positions, or keep unresolved weak.",
        "",
        "| record_id | UniProt | mutation | current residue | priority | PMID | nearest matches |",
        "|---|---|---|---|---|---|---|",
    ]
    for row in rows:
        matches = ", ".join(f"{m.get('position')}({m.get('offset'):+d})" for m in row.get("nearest_matches_within_window") or [])
        lines.append(
            "| {record_id} | {uniprot_id} | {mutation} | {current_sequence_residue} | {priority} | {literature_ref} | {matches} |".format(
                record_id=row.get("record_id"),
                uniprot_id=row.get("uniprot_id"),
                mutation=row.get("mutation"),
                current_sequence_residue=row.get("current_sequence_residue"),
                priority=row.get("priority"),
                literature_ref=row.get("literature_ref") or "",
                matches=matches,
            )
        )
    lines.extend([
        "",
        "Decision output must be appended to `datasets/curation/numbering_curation_decisions.jsonl`.",
        "Use `contracts/numbering_curation_decision.schema.json` fields.",
    ])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Build numbering curation batches")
    parser.add_argument("--input", type=Path, default=QUEUE)
    parser.add_argument("--decisions", type=Path, default=DECISIONS)
    parser.add_argument("--out-dir", type=Path, default=OUT_DIR)
    parser.add_argument("--report", type=Path, default=REPORT_OUT)
    parser.add_argument("--batch-size", type=int, default=25)
    parser.add_argument("--priority", default="P0")
    parser.add_argument("--max-batches", type=int, default=5)
    args = parser.parse_args()

    decided_ids = {
        str(row.get("record_id"))
        for row in load_jsonl(args.decisions)
        if row.get("record_id")
    }
    priority_rows = [row for row in load_jsonl(args.input) if row.get("priority") == args.priority]
    rows = [row for row in priority_rows if str(row.get("record_id")) not in decided_ids]
    rows.sort(key=lambda row: (
        -(row.get("uniprot_group_size") or 0),
        str(row.get("uniprot_id") or ""),
        str(row.get("record_id") or ""),
    ))
    batches = [
        rows[index:index + args.batch_size]
        for index in range(0, min(len(rows), args.batch_size * args.max_batches), args.batch_size)
    ]
    batch_reports = []
    for index, batch in enumerate(batches, start=1):
        batch_id = f"{args.priority.lower()}_batch_{index:03d}"
        jsonl_path = args.out_dir / f"{batch_id}.jsonl"
        md_path = args.out_dir / f"{batch_id}.md"
        write_jsonl(jsonl_path, batch)
        write_markdown(md_path, batch_id, batch)
        batch_reports.append({
            "batch_id": batch_id,
            "rows": len(batch),
            "jsonl": str(jsonl_path),
            "markdown": str(md_path),
            "uniprot_counts": dict(Counter(row.get("uniprot_id") for row in batch)),
        })
    report = {
        "priority": args.priority,
        "priority_rows": len(priority_rows),
        "already_decided_rows": len(priority_rows) - len(rows),
        "available_rows": len(rows),
        "batch_size": args.batch_size,
        "batches": batch_reports,
        "covered_rows": sum(batch["rows"] for batch in batch_reports),
        "policy": "curation batches exclude already-decided records and are work packages only; they do not modify labels",
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "priority": args.priority,
        "already_decided_rows": report["already_decided_rows"],
        "available_rows": len(rows),
        "batches": len(batch_reports),
        "covered_rows": report["covered_rows"],
        "output": str(args.report),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
