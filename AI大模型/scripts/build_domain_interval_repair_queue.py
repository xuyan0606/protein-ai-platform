#!/usr/bin/env python3
"""Build a local queue for repairing invalid domain intervals."""

from __future__ import annotations

import argparse
import json
import sqlite3
from collections import Counter
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
AI_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB = PROJECT_ROOT / "backend" / "protein_ai.db"
QUEUE_OUT = AI_ROOT / "datasets" / "curation" / "domain_interval_repair_queue.jsonl"
REPORT_OUT = AI_ROOT / "reports" / "domain_interval_repair_report.json"


def connect_ro(path: Path) -> sqlite3.Connection:
    uri = f"file:{path}?mode=ro&immutable=1"
    conn = sqlite3.connect(uri, uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Build domain interval repair queue")
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    parser.add_argument("--output", type=Path, default=QUEUE_OUT)
    parser.add_argument("--report", type=Path, default=REPORT_OUT)
    parser.add_argument("--limit", type=int, default=5000)
    args = parser.parse_args()

    with connect_ro(args.db) as conn:
        total = conn.execute("SELECT COUNT(*) FROM domain_architecture").fetchone()[0]
        invalid = conn.execute(
            "SELECT COUNT(*) FROM domain_architecture WHERE start_pos <= 0 OR end_pos <= 0 OR end_pos < start_pos"
        ).fetchone()[0]
        rows = conn.execute(
            """
            SELECT
              d.id AS domain_record_id,
              e.uniprot_id,
              e.seq_length,
              p.pfam_id,
              p.name,
              p.clan,
              d.start_pos,
              d.end_pos,
              d.evalue
            FROM domain_architecture d
            JOIN enzyme_records e ON e.id = d.enzyme_id
            JOIN pfam_domains p ON p.id = d.domain_id
            WHERE d.start_pos <= 0 OR d.end_pos <= 0 OR d.end_pos < d.start_pos
            ORDER BY e.uniprot_id, p.pfam_id, d.id
            LIMIT ?
            """,
            (args.limit,),
        ).fetchall()

    queue = [
        {
            "priority": "P0" if row["pfam_id"] else "P1",
            "domain_record_id": row["domain_record_id"],
            "uniprot_id": row["uniprot_id"],
            "sequence_length": row["seq_length"],
            "pfam_id": row["pfam_id"],
            "domain_name": row["name"],
            "clan": row["clan"],
            "current_start_pos": row["start_pos"],
            "current_end_pos": row["end_pos"],
            "evalue": row["evalue"],
            "curation_action": "rerun or restore PFAM/HMMER interval and write domain interval decision",
        }
        for row in rows
    ]
    write_jsonl(args.output, queue)
    report = {
        "domain_rows": total,
        "invalid_rows": invalid,
        "queued_rows": len(queue),
        "priority_counts": dict(Counter(row["priority"] for row in queue)),
        "output": str(args.output),
        "ready_for_position_features": invalid == 0 and total > 0,
        "policy": "invalid intervals cannot be used for mutation-in-domain or domain-relative-position features",
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "domain_rows": total,
        "invalid_rows": invalid,
        "queued_rows": len(queue),
        "output": str(args.output),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
