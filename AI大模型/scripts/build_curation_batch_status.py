#!/usr/bin/env python3
"""Report reviewed decision coverage for curation batches."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
BATCH_DIR = AI_ROOT / "datasets" / "curation" / "batches"
DECISIONS = AI_ROOT / "datasets" / "curation" / "numbering_curation_decisions.jsonl"
REPORT_OUT = AI_ROOT / "reports" / "curation_batch_status_report.json"


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def main() -> int:
    parser = argparse.ArgumentParser(description="Build curation batch status report")
    parser.add_argument("--batch-dir", type=Path, default=BATCH_DIR)
    parser.add_argument("--decisions", type=Path, default=DECISIONS)
    parser.add_argument("--report", type=Path, default=REPORT_OUT)
    args = parser.parse_args()

    decisions = load_jsonl(args.decisions)
    decision_by_record = {row.get("record_id"): row for row in decisions if row.get("record_id")}
    batch_reports = []
    total_rows = 0
    total_decided = 0
    for batch_file in sorted(args.batch_dir.glob("*.jsonl")):
        rows = load_jsonl(batch_file)
        record_ids = [row.get("record_id") for row in rows]
        decided = [record_id for record_id in record_ids if record_id in decision_by_record]
        decision_counts = Counter(decision_by_record[record_id].get("decision") for record_id in decided)
        total_rows += len(rows)
        total_decided += len(decided)
        batch_reports.append({
            "batch_id": batch_file.stem,
            "rows": len(rows),
            "decided_rows": len(decided),
            "undecided_rows": len(rows) - len(decided),
            "decision_counts": dict(decision_counts),
            "coverage": round(len(decided) / len(rows), 4) if rows else 0,
        })
    report = {
        "batches": len(batch_reports),
        "rows": total_rows,
        "decided_rows": total_decided,
        "undecided_rows": total_rows - total_decided,
        "coverage": round(total_decided / total_rows, 4) if total_rows else 0,
        "batch_status": batch_reports,
        "policy": "coverage is based only on reviewed numbering_curation_decisions.jsonl, not template files",
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "batches": report["batches"],
        "rows": report["rows"],
        "decided_rows": report["decided_rows"],
        "coverage": report["coverage"],
        "output": str(args.report),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
