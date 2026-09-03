#!/usr/bin/env python3
"""Apply reviewed domain interval curation decisions to local JSONL output."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
QUEUE = AI_ROOT / "datasets" / "curation" / "domain_interval_repair_queue.jsonl"
DECISIONS = AI_ROOT / "datasets" / "curation" / "domain_interval_decisions.jsonl"
OUTPUT = AI_ROOT / "datasets" / "curation" / "domain_intervals_curated.jsonl"
REPORT_OUT = AI_ROOT / "reports" / "domain_interval_apply_report.json"


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Apply domain interval curation decisions")
    parser.add_argument("--queue", type=Path, default=QUEUE)
    parser.add_argument("--decisions", type=Path, default=DECISIONS)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    parser.add_argument("--report", type=Path, default=REPORT_OUT)
    args = parser.parse_args()

    queue_rows = load_jsonl(args.queue)
    decisions = load_jsonl(args.decisions)
    decision_by_id = {row.get("domain_record_id"): row for row in decisions if row.get("domain_record_id") is not None}
    output_rows = []
    rejected = 0
    for row in queue_rows:
        decision = decision_by_id.get(row.get("domain_record_id"))
        if not decision:
            continue
        mode = decision.get("decision")
        if mode == "reject_domain_hit":
            rejected += 1
            continue
        if mode == "keep_unresolved":
            output_rows.append({**row, "curation_status": "domain_interval_unresolved", "usable_for_position_features": False, "curation_decision": decision})
        elif mode == "set_interval":
            output_rows.append({
                **row,
                "start_pos": decision.get("start_pos"),
                "end_pos": decision.get("end_pos"),
                "curation_status": "domain_interval_curated",
                "usable_for_position_features": True,
                "curation_decision": decision,
            })
    write_jsonl(args.output, output_rows)
    report = {
        "queue_rows": len(queue_rows),
        "decision_rows": len(decisions),
        "output_rows": len(output_rows),
        "rejected_rows": rejected,
        "usable_for_position_features": sum(1 for row in output_rows if row.get("usable_for_position_features")),
        "status_counts": dict(Counter(row.get("curation_status") for row in output_rows)),
        "output": str(args.output),
        "policy": "curated intervals are local JSONL only; source SQLite DB is not modified",
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"decision_rows": len(decisions), "usable_for_position_features": report["usable_for_position_features"], "output": str(args.output)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
