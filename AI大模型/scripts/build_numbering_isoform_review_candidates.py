#!/usr/bin/env python3
"""Build review candidates from isoform numbering evidence."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
INPUT = AI_ROOT / "datasets" / "curation" / "numbering_isoform_evidence.jsonl"
OUT = AI_ROOT / "datasets" / "curation" / "numbering_isoform_review_candidates.jsonl"
REPORT_OUT = AI_ROOT / "reports" / "numbering_isoform_review_candidate_report.json"


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Build isoform review candidates")
    parser.add_argument("--input", type=Path, default=INPUT)
    parser.add_argument("--output", type=Path, default=OUT)
    parser.add_argument("--report", type=Path, default=REPORT_OUT)
    args = parser.parse_args()

    rows = load_jsonl(args.input)
    candidates = []
    for row in rows:
        exact_isoforms = row.get("exact_isoform_position_matches") or []
        if not exact_isoforms:
            continue
        candidates.append({
            "record_id": row.get("record_id"),
            "priority": row.get("priority"),
            "uniprot_id": row.get("uniprot_id"),
            "reported_mutation": row.get("reported_mutation"),
            "reported_position": row.get("reported_position"),
            "reported_wild_type": row.get("reported_wild_type"),
            "reported_mutant": row.get("reported_mutant"),
            "literature_ref": row.get("literature_ref"),
            "candidate_decision": "map_to_canonical",
            "candidate_mapping_basis": "isoform_alignment",
            "candidate_isoforms": exact_isoforms,
            "candidate_canonical_position": row.get("reported_position"),
            "candidate_canonical_wild_type": row.get("reported_wild_type"),
            "candidate_canonical_mutant": row.get("reported_mutant"),
            "review_required": True,
            "required_checks": [
                "confirm literature uses the matched isoform numbering",
                "confirm mutant residue and assay record belong to this UniProt/isoform",
                "confirm mapping to canonical position before writing numbering_curation_decisions.jsonl",
            ],
            "policy": "candidate only; do not use as reviewed curation decision",
        })
    candidates.sort(key=lambda row: (row.get("priority") or "P9", row.get("uniprot_id") or "", row.get("record_id") or ""))
    write_jsonl(args.output, candidates)
    report = {
        "input_rows": len(rows),
        "candidate_rows": len(candidates),
        "priority_counts": dict(Counter(row.get("priority") for row in candidates)),
        "unique_uniprot_ids": len({row.get("uniprot_id") for row in candidates}),
        "output": str(args.output),
        "policy": "review candidates are not applied automatically",
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "candidate_rows": report["candidate_rows"],
        "priority_counts": report["priority_counts"],
        "output": str(args.report),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
