#!/usr/bin/env python3
"""Build prioritized domain interval curation batches."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
QUEUE = AI_ROOT / "datasets" / "curation" / "domain_interval_repair_queue.jsonl"
OUT_DIR = AI_ROOT / "datasets" / "curation" / "domain_batches"
REPORT_OUT = AI_ROOT / "reports" / "domain_interval_batch_report.json"


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")


def write_markdown(path: Path, batch_id: str, rows: list[dict[str, Any]]) -> None:
    lines = [
        f"# Domain Interval Curation {batch_id}",
        "",
        "Goal: recover valid PFAM/domain start/end positions or keep unresolved.",
        "",
        "| domain_record_id | UniProt | length | PFAM | current interval | priority |",
        "|---|---|---:|---|---|---|",
    ]
    for row in rows:
        lines.append(
            "| {domain_record_id} | {uniprot_id} | {sequence_length} | {pfam_id} | {start}-{end} | {priority} |".format(
                domain_record_id=row.get("domain_record_id"),
                uniprot_id=row.get("uniprot_id"),
                sequence_length=row.get("sequence_length"),
                pfam_id=row.get("pfam_id"),
                start=row.get("current_start_pos"),
                end=row.get("current_end_pos"),
                priority=row.get("priority"),
            )
        )
    lines.extend([
        "",
        "Decision output must be appended to `datasets/curation/domain_interval_decisions.jsonl`.",
        "Use `contracts/domain_interval_curation_decision.schema.json` fields.",
    ])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Build domain interval curation batches")
    parser.add_argument("--input", type=Path, default=QUEUE)
    parser.add_argument("--out-dir", type=Path, default=OUT_DIR)
    parser.add_argument("--report", type=Path, default=REPORT_OUT)
    parser.add_argument("--batch-size", type=int, default=50)
    parser.add_argument("--max-batches", type=int, default=100)
    args = parser.parse_args()

    rows = load_jsonl(args.input)
    rows.sort(key=lambda row: (str(row.get("uniprot_id") or ""), str(row.get("pfam_id") or ""), int(row.get("domain_record_id") or 0)))
    batches = [
        rows[index:index + args.batch_size]
        for index in range(0, min(len(rows), args.batch_size * args.max_batches), args.batch_size)
    ]
    batch_reports = []
    for index, batch in enumerate(batches, start=1):
        batch_id = f"domain_batch_{index:03d}"
        jsonl_path = args.out_dir / f"{batch_id}.jsonl"
        md_path = args.out_dir / f"{batch_id}.md"
        write_jsonl(jsonl_path, batch)
        write_markdown(md_path, batch_id, batch)
        batch_reports.append({
            "batch_id": batch_id,
            "rows": len(batch),
            "jsonl": str(jsonl_path),
            "markdown": str(md_path),
            "pfam_counts": dict(Counter(row.get("pfam_id") for row in batch)),
        })
    report = {
        "available_rows": len(rows),
        "batch_size": args.batch_size,
        "batches": batch_reports,
        "covered_rows": sum(batch["rows"] for batch in batch_reports),
        "policy": "domain batches are work packages only; they do not modify the database",
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"available_rows": len(rows), "batches": len(batch_reports), "covered_rows": report["covered_rows"], "output": str(args.report)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
