#!/usr/bin/env python3
"""Report decision coverage for domain interval curation batches."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
BATCH_DIR = AI_ROOT / "datasets" / "curation" / "domain_batches"
DECISIONS = AI_ROOT / "datasets" / "curation" / "domain_interval_decisions.jsonl"
REPORT_OUT = AI_ROOT / "reports" / "domain_interval_batch_status_report.json"


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def main() -> int:
    parser = argparse.ArgumentParser(description="Build domain interval batch status")
    parser.add_argument("--batch-dir", type=Path, default=BATCH_DIR)
    parser.add_argument("--decisions", type=Path, default=DECISIONS)
    parser.add_argument("--report", type=Path, default=REPORT_OUT)
    args = parser.parse_args()

    decisions = load_jsonl(args.decisions)
    decision_by_id = {row.get("domain_record_id"): row for row in decisions if row.get("domain_record_id") is not None}
    batch_status = []
    total_rows = 0
    total_decided = 0
    for batch_file in sorted(args.batch_dir.glob("*.jsonl")):
        rows = load_jsonl(batch_file)
        ids = [row.get("domain_record_id") for row in rows]
        decided = [domain_id for domain_id in ids if domain_id in decision_by_id]
        total_rows += len(rows)
        total_decided += len(decided)
        batch_status.append({
            "batch_id": batch_file.stem,
            "rows": len(rows),
            "decided_rows": len(decided),
            "undecided_rows": len(rows) - len(decided),
            "coverage": round(len(decided) / len(rows), 4) if rows else 0,
            "decision_counts": dict(Counter(decision_by_id[domain_id].get("decision") for domain_id in decided)),
        })
    report = {
        "batches": len(batch_status),
        "rows": total_rows,
        "decided_rows": total_decided,
        "undecided_rows": total_rows - total_decided,
        "coverage": round(total_decided / total_rows, 4) if total_rows else 0,
        "batch_status": batch_status,
        "policy": "coverage is based on reviewed domain_interval_decisions.jsonl, not templates",
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"batches": report["batches"], "rows": report["rows"], "decided_rows": report["decided_rows"], "coverage": report["coverage"], "output": str(args.report)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
