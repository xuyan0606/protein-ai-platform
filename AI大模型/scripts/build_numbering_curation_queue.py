#!/usr/bin/env python3
"""Build a numbering curation queue from audited weak mutation evidence."""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
AUDITED_INPUT = AI_ROOT / "datasets" / "curated" / "enzyme_mutation_training_table_audited.jsonl"
REPAIR_SUGGESTIONS = AI_ROOT / "reports" / "numbering_repair_suggestions.json"
QUEUE_OUT = AI_ROOT / "datasets" / "curation" / "numbering_curation_queue.jsonl"
REPORT_OUT = AI_ROOT / "reports" / "numbering_curation_queue_report.json"


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")


def measurement_strength(row: dict[str, Any]) -> str:
    dtm = row.get("label_stability_delta_tm_c")
    ddg = row.get("label_ddg")
    if isinstance(dtm, (int, float)) and abs(float(dtm)) >= 2.0:
        return "strong"
    if isinstance(ddg, (int, float)) and abs(float(ddg)) >= 1.0:
        return "strong"
    if dtm is not None or ddg is not None:
        return "moderate"
    return "unknown"


def priority(row: dict[str, Any], group_size: int) -> str:
    strength = measurement_strength(row)
    if group_size >= 4 and strength == "strong":
        return "P0"
    if group_size >= 3 or strength == "strong":
        return "P1"
    return "P2"


def main() -> int:
    parser = argparse.ArgumentParser(description="Build numbering curation queue")
    parser.add_argument("--input", type=Path, default=AUDITED_INPUT)
    parser.add_argument("--repair-suggestions", type=Path, default=REPAIR_SUGGESTIONS)
    parser.add_argument("--queue-output", type=Path, default=QUEUE_OUT)
    parser.add_argument("--report", type=Path, default=REPORT_OUT)
    args = parser.parse_args()

    rows = [row for row in load_jsonl(args.input) if not row.get("numbering_verified_by_sequence")]
    group_counts = Counter(row.get("uniprot_id") for row in rows)
    suggestion_report = json.loads(args.repair_suggestions.read_text(encoding="utf-8")) if args.repair_suggestions.exists() else {}
    suggestion_by_record = {
        row["record_id"]: row
        for row in suggestion_report.get("suggestions_sample", [])
        if row.get("record_id")
    }

    queue = []
    for row in rows:
        record_id = row.get("record_id")
        suggestion = suggestion_by_record.get(record_id, {})
        group_size = group_counts[row.get("uniprot_id")]
        queue.append({
            "priority": priority(row, group_size),
            "record_id": record_id,
            "uniprot_id": row.get("uniprot_id"),
            "mutation": row.get("mutation"),
            "reported_position": row.get("mutation_position"),
            "reported_wild_type": row.get("wild_type"),
            "current_sequence_residue": row.get("current_sequence_residue"),
            "nearest_matches_within_window": suggestion.get("nearest_matches_within_window", []),
            "label_decision": row.get("label_decision"),
            "measurement_strength": measurement_strength(row),
            "label_stability_delta_tm_c": row.get("label_stability_delta_tm_c"),
            "label_ddg": row.get("label_ddg"),
            "source_db": row.get("label_source_db"),
            "method": row.get("label_method"),
            "literature_ref": row.get("literature_ref"),
            "uniprot_group_size": group_size,
            "curation_action": "map reported mutation to canonical UniProt sequence or mark as unresolved weak evidence",
        })
    queue.sort(key=lambda item: (item["priority"], item["uniprot_id"] or "", item["record_id"] or ""))
    write_jsonl(args.queue_output, queue)

    by_priority = Counter(item["priority"] for item in queue)
    by_source = Counter(item["source_db"] for item in queue)
    grouped = defaultdict(list)
    for item in queue:
        grouped[item["uniprot_id"]].append(item)
    top_groups = [
        {
            "uniprot_id": uniprot_id,
            "rows": len(items),
            "priority_counts": dict(Counter(item["priority"] for item in items)),
            "literature_refs": sorted({str(item.get("literature_ref")) for item in items if item.get("literature_ref")})[:10],
        }
        for uniprot_id, items in sorted(grouped.items(), key=lambda pair: (-len(pair[1]), str(pair[0])))[:20]
    ]
    report = {
        "queue_rows": len(queue),
        "priority_counts": dict(by_priority),
        "source_counts": dict(by_source),
        "top_uniprot_groups": top_groups,
        "queue_output": str(args.queue_output),
        "policy": "queue rows are weak evidence until canonical numbering is verified",
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "queue_rows": len(queue),
        "priority_counts": dict(by_priority),
        "queue_output": str(args.queue_output),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
