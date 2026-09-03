#!/usr/bin/env python3
"""Build local retrieval packets for weak mutation-numbering evidence."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
QUEUE = AI_ROOT / "datasets" / "curation" / "numbering_curation_queue.jsonl"
OUT_DIR = AI_ROOT / "datasets" / "curation" / "numbering_retrieval_packets"
REPORT_OUT = AI_ROOT / "reports" / "numbering_retrieval_packet_report.json"


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")


def packet_row(row: dict[str, Any], packet_id: str) -> dict[str, Any]:
    literature_ref = row.get("literature_ref")
    return {
        "packet_id": packet_id,
        "record_id": row.get("record_id"),
        "priority": row.get("priority"),
        "uniprot_id": row.get("uniprot_id"),
        "reported_mutation": row.get("mutation"),
        "reported_position": row.get("reported_position"),
        "reported_wild_type": row.get("reported_wild_type"),
        "current_sequence_residue": row.get("current_sequence_residue"),
        "nearest_matches_within_window": row.get("nearest_matches_within_window", []),
        "literature_ref": literature_ref,
        "retrieval_tasks": [
            "retrieve_current_uniprot_entry",
            "check_isoform_and_sequence_version",
            "check_literature_variant_numbering",
            "record_mapping_decision",
        ],
        "retrieval_keys": {
            "uniprot_id": row.get("uniprot_id"),
            "literature_ref": literature_ref,
            "mutation": row.get("mutation"),
        },
        "retrieval_state": "not_fetched",
        "decision_file": "datasets/curation/numbering_curation_decisions.jsonl",
        "policy": "packet is a retrieval work item; it is not a curation decision or training label",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Build numbering retrieval packets")
    parser.add_argument("--input", type=Path, default=QUEUE)
    parser.add_argument("--out-dir", type=Path, default=OUT_DIR)
    parser.add_argument("--report", type=Path, default=REPORT_OUT)
    parser.add_argument("--packet-size", type=int, default=50)
    args = parser.parse_args()

    rows = load_jsonl(args.input)
    packets = [packet_row(row, f"numbering-{row.get('record_id')}") for row in rows]
    packet_reports = []
    for start in range(0, len(packets), args.packet_size):
        batch = packets[start:start + args.packet_size]
        packet_id = f"numbering_packet_{start // args.packet_size + 1:03d}"
        path = args.out_dir / f"{packet_id}.jsonl"
        write_jsonl(path, batch)
        packet_reports.append({
            "packet_id": packet_id,
            "rows": len(batch),
            "path": str(path),
            "priority_counts": dict(Counter(row.get("priority") for row in batch)),
        })
    report = {
        "queue_rows": len(packets),
        "packets": len(packet_reports),
        "packet_size": args.packet_size,
        "not_fetched_rows": len(packets),
        "priority_counts": dict(Counter(row.get("priority") for row in packets)),
        "packet_reports": packet_reports,
        "decision_rows": 0,
        "policy": "no network retrieval or label promotion occurs in this step",
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "queue_rows": report["queue_rows"],
        "packets": report["packets"],
        "not_fetched_rows": report["not_fetched_rows"],
        "output": str(args.report),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
