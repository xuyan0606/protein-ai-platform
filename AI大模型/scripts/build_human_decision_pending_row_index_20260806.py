#!/usr/bin/env python3
"""Index pending human-review rows without creating decision rows."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
BACKLOG = ROOT / "reports" / "human_decision_backlog_report.json"
DEFAULT_OUTPUT = ROOT / "reports" / "human_decision_pending_row_index_20260806.json"


def iter_records(path: Path) -> list[dict[str, Any]]:
    if path.is_dir():
        records: list[dict[str, Any]] = []
        for child in sorted(path.glob("*.jsonl")):
            records.extend(iter_records(child))
        return records
    if path.suffix == ".json" and path.exists():
        value = json.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(value, list) else [value]
    if path.suffix != ".jsonl" or not path.exists():
        return []
    return [
        value
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
        for value in [json.loads(line)]
        if isinstance(value, dict)
    ]


def record_id(record: dict[str, Any], index: int, source: str) -> str:
    for key in ("row_id", "packet_id", "decision_id", "candidate_id", "id", "accession"):
        if record.get(key) not in (None, ""):
            return f"{Path(source).stem}:{record[key]}:{index}"
    digest = hashlib.sha256(json.dumps(record, sort_keys=True).encode()).hexdigest()[:16]
    return f"{Path(source).stem}:{index}:{digest}"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    backlog = json.loads(BACKLOG.read_text(encoding="utf-8"))
    items = []
    missing_sources = []
    for backlog_item in backlog.get("items", []):
        source_value = backlog_item.get("review_source")
        if not source_value:
            continue
        source = ROOT / source_value
        records = iter_records(source)
        if not records and not source.exists():
            missing_sources.append({"backlog_id": backlog_item.get("backlog_id"), "source": source_value})
        for index, record in enumerate(records):
            items.append({
                "backlog_id": backlog_item.get("backlog_id"),
                "workstream": backlog_item.get("workstream"),
                "priority": backlog_item.get("priority"),
                "source": source_value,
                "row_index": index,
                "pending_row_id": record_id(record, index, source_value),
                "record_keys": sorted(record.keys()),
                "decision_status": "pending_human_input",
                "formal_decision_written": False,
                "evidence_refs": [],
            })
    package = {
        "schema_version": 1,
        "created_at": "2026-08-06",
        "mode": "human_decision_pending_row_index",
        "write_policy": "index_only; no_formal_decision_rows_written",
        "backlog_summary": {
            "backlog_items": backlog.get("backlog_items"),
            "required_rows": backlog.get("total_required_rows"),
            "completed_rows": backlog.get("total_completed_rows"),
            "missing_rows": backlog.get("total_missing_rows"),
        },
        "source_missing_count": len(missing_sources),
        "missing_sources": missing_sources,
        "indexed_rows": len(items),
        "formal_decision_rows_written": 0,
        "items": items,
        "release_flags": {
            "release_ready": False,
            "customer_delivery_ready": False,
            "safe_for_model_claim": False,
        },
    }
    args.output.write_text(json.dumps(package, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "indexed_rows": len(items),
        "missing_sources": len(missing_sources),
        "formal_decision_rows_written": 0,
        "output": str(args.output),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
