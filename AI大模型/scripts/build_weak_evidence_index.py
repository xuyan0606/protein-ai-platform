#!/usr/bin/env python3
"""Build a retrieval-safe weak evidence index from unverified mutation labels."""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
INPUT = AI_ROOT / "datasets" / "curated" / "enzyme_mutation_weak_evidence.jsonl"
OUTPUT = AI_ROOT / "datasets" / "curation" / "weak_evidence_index.jsonl"
REPORT_OUT = AI_ROOT / "reports" / "weak_evidence_index_report.json"


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")


def evidence_tier(row: dict[str, Any]) -> str:
    if row.get("literature_ref") and row.get("label_source_db"):
        return "literature_db_unverified_numbering"
    if row.get("label_source_db"):
        return "db_unverified_numbering"
    return "unverified_numbering"


def main() -> int:
    parser = argparse.ArgumentParser(description="Build weak mutation evidence retrieval index")
    parser.add_argument("--input", type=Path, default=INPUT)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    parser.add_argument("--report", type=Path, default=REPORT_OUT)
    args = parser.parse_args()

    rows = load_jsonl(args.input)
    index_rows = []
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        item = {
            "evidence_id": f"weak:{row.get('record_id')}",
            "uniprot_id": row.get("uniprot_id"),
            "mutation": row.get("mutation"),
            "reported_position": row.get("mutation_position"),
            "reported_wild_type": row.get("wild_type"),
            "current_sequence_residue": row.get("current_sequence_residue"),
            "label_decision": row.get("label_decision"),
            "evidence_tier": evidence_tier(row),
            "source_db": row.get("label_source_db"),
            "literature_ref": row.get("literature_ref"),
            "method": row.get("label_method"),
            "assay_ph": row.get("assay_ph"),
            "assay_temperature_c": row.get("assay_temperature_c"),
            "integrity_flags": row.get("integrity_flags"),
            "allowed_uses": [
                "retrieval_context",
                "report_evidence_with_numbering_warning",
                "curation_queue",
            ],
            "forbidden_uses": [
                "supervised_training_label",
                "automatic_go_no_go_decision",
                "structure_distance_claim",
            ],
        }
        index_rows.append(item)
        grouped[str(item["uniprot_id"])].append(item)

    write_jsonl(args.output, index_rows)
    report = {
        "rows": len(index_rows),
        "groups": len(grouped),
        "label_distribution": dict(Counter(row["label_decision"] for row in index_rows)),
        "evidence_tiers": dict(Counter(row["evidence_tier"] for row in index_rows)),
        "top_groups": [
            {"uniprot_id": key, "rows": len(value)}
            for key, value in sorted(grouped.items(), key=lambda pair: (-len(pair[1]), pair[0]))[:20]
        ],
        "output": str(args.output),
        "policy": "weak evidence is retrieval-safe only and must carry numbering warnings",
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"rows": len(index_rows), "groups": len(grouped), "output": str(args.output)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
