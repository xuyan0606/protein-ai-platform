#!/usr/bin/env python3
"""Analyze duplicate embedding vectors by source and sequence metadata."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import defaultdict
from pathlib import Path


def vector_key(vector: list[float]) -> str:
    return hashlib.sha256(json.dumps(vector, separators=(",", ":")).encode()).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description="Analyze embedding collision groups")
    parser.add_argument("--index", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    data = json.loads(args.index.read_text(encoding="utf-8"))
    groups = defaultdict(list)
    for record in data.get("records", []):
        groups[vector_key(record["embedding"])].append(record)
    collisions = [rows for rows in groups.values() if len(rows) > 1]
    source_counts = defaultdict(int)
    length_counts = defaultdict(int)
    for rows in collisions:
        for row in rows:
            source_counts[row["source_file"]] += 1
            length_counts[str(row.get("length", 0))] += 1
    report = {
        "artifact_kind": "unlabeled_embedding_collision_analysis",
        "index": str(args.index.resolve()),
        "embedding_groups": len(groups),
        "collision_group_count": len(collisions),
        "collision_record_count": sum(len(rows) - 1 for rows in collisions),
        "top_collision_sources": sorted(({"source_file": key, "records": value} for key, value in source_counts.items()), key=lambda x: -x["records"])[:20],
        "top_collision_lengths": sorted(({"length": int(key), "records": value} for key, value in length_counts.items()), key=lambda x: -x["records"])[:20],
        "safe_for_model_claim": False,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: report[k] for k in ("embedding_groups", "collision_group_count", "collision_record_count")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
