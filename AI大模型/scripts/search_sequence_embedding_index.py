#!/usr/bin/env python3
"""Search an unlabeled sequence embedding index with cosine similarity."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path


def cosine(left: list[float], right: list[float]) -> float:
    dot = sum(a * b for a, b in zip(left, right))
    left_norm = math.sqrt(sum(value * value for value in left))
    right_norm = math.sqrt(sum(value * value for value in right))
    return dot / (left_norm * right_norm) if left_norm and right_norm else 0.0


def main() -> int:
    parser = argparse.ArgumentParser(description="Search an unlabeled sequence embedding index")
    parser.add_argument("--index", type=Path, required=True)
    parser.add_argument("--query-record", type=int, required=True)
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.top_k < 1:
        raise SystemExit("top-k must be >= 1")
    index = json.loads(args.index.read_text(encoding="utf-8"))
    records = index.get("records", [])
    if not records or not 0 <= args.query_record < len(records):
        raise SystemExit("query record is outside the embedding index")
    query = records[args.query_record]["embedding"]
    ranked = []
    for record_index, record in enumerate(records):
        if record_index == args.query_record:
            continue
        ranked.append({
            "record_index": record_index,
            "source_file": record["source_file"],
            "source_sha256": record["source_sha256"],
            "sequence_index": record["sequence_index"],
            "similarity": round(cosine(query, record["embedding"]), 8),
        })
    ranked.sort(key=lambda row: (-row["similarity"], row["record_index"]))
    payload = {
        "artifact_kind": "unlabeled_sequence_embedding_search",
        "safe_for_supervised_training": False,
        "safe_for_model_claim": False,
        "index": str(args.index.resolve()),
        "query_record": args.query_record,
        "top_k": args.top_k,
        "results": ranked[: args.top_k],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": "completed_embedding_search", "results": len(payload["results"]), "top_similarity": payload["results"][0]["similarity"] if payload["results"] else None}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
