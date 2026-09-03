#!/usr/bin/env python3
"""Suggest local numbering repair candidates for mismatched mutation labels."""

from __future__ import annotations

import argparse
import json
import re
import sqlite3
from collections import Counter
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[2]
AI_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB = PROJECT_ROOT / "backend" / "protein_ai.db"
INPUT = AI_ROOT / "datasets" / "curated" / "enzyme_mutation_training_table_enriched.jsonl"
OUTPUT = AI_ROOT / "reports" / "numbering_repair_suggestions.json"
MUTATION_RE = re.compile(r"^([A-Z])([0-9]{1,6})([A-Z])$")


def connect_ro(path: Path) -> sqlite3.Connection:
    uri = f"file:{path}?mode=ro&immutable=1"
    conn = sqlite3.connect(uri, uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def load_sequences(conn: sqlite3.Connection, uniprot_ids: list[str]) -> dict[str, str]:
    if not uniprot_ids:
        return {}
    placeholders = ",".join("?" for _ in uniprot_ids)
    rows = conn.execute(
        f"SELECT uniprot_id, sequence FROM enzyme_records WHERE uniprot_id IN ({placeholders})",
        uniprot_ids,
    ).fetchall()
    return {row["uniprot_id"]: row["sequence"] for row in rows}


def nearest_matches(sequence: str, wt: str, pos: int, window: int) -> list[dict[str, int]]:
    matches = []
    for candidate_pos in range(max(1, pos - window), min(len(sequence), pos + window) + 1):
        if sequence[candidate_pos - 1].upper() == wt:
            matches.append({"position": candidate_pos, "offset": candidate_pos - pos})
    return sorted(matches, key=lambda item: (abs(item["offset"]), item["position"]))[:5]


def main() -> int:
    parser = argparse.ArgumentParser(description="Suggest numbering repair candidates")
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    parser.add_argument("--input", type=Path, default=INPUT)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    parser.add_argument("--window", type=int, default=20)
    args = parser.parse_args()

    rows = load_jsonl(args.input)
    uniprot_ids = sorted({row.get("uniprot_id") for row in rows if row.get("uniprot_id")})
    with connect_ro(args.db) as conn:
        sequences = load_sequences(conn, uniprot_ids)

    suggestions = []
    offset_counts = Counter()
    mismatch_count = 0
    no_local_match = 0
    exact_match = 0
    for row in rows:
        mutation = str(row.get("mutation") or "").upper()
        match = MUTATION_RE.match(mutation)
        if not match:
            continue
        wt, pos_text, _mut = match.groups()
        pos = int(pos_text)
        sequence = sequences.get(row.get("uniprot_id") or "")
        if not sequence or pos < 1 or pos > len(sequence):
            continue
        current = sequence[pos - 1].upper()
        if current == wt:
            exact_match += 1
            continue
        mismatch_count += 1
        local_matches = nearest_matches(sequence, wt, pos, args.window)
        if local_matches:
            offset_counts[local_matches[0]["offset"]] += 1
        else:
            no_local_match += 1
        if len(suggestions) < 100:
            suggestions.append({
                "record_id": row.get("record_id"),
                "uniprot_id": row.get("uniprot_id"),
                "mutation": mutation,
                "reported_position": pos,
                "reported_wild_type": wt,
                "current_sequence_residue": current,
                "nearest_matches_within_window": local_matches,
            })

    report = {
        "rows": len(rows),
        "exact_match": exact_match,
        "mismatch_count": mismatch_count,
        "window": args.window,
        "mismatches_with_no_local_match": no_local_match,
        "nearest_offset_counts": dict(offset_counts.most_common(20)),
        "suggestions_sample": suggestions,
        "interpretation": (
            "If one offset dominates, a numbering offset repair may be possible. "
            "If offsets are diffuse or absent, labels likely need UniProt version/isoform/literature remapping."
        ),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "rows": report["rows"],
        "exact_match": exact_match,
        "mismatch_count": mismatch_count,
        "mismatches_with_no_local_match": no_local_match,
        "top_offsets": dict(offset_counts.most_common(5)),
        "output": str(args.output),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
