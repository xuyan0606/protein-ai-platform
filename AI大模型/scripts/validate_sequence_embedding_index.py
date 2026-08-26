#!/usr/bin/env python3
"""Validate integrity of an unlabeled sequence embedding index."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from collections import Counter
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate an unlabeled sequence embedding index")
    parser.add_argument("--index", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    data = json.loads(args.index.read_text(encoding="utf-8"))
    dimension = int(data.get("embedding_dimension", 0))
    records = data.get("records", [])
    failures = []
    lengths = []
    vector_hashes = Counter()
    source_hashes = set()
    for i, record in enumerate(records):
        vector = record.get("embedding")
        if not isinstance(vector, list) or len(vector) != dimension:
            failures.append(f"record_{i}_dimension_mismatch")
            continue
        if not record.get("source_file") or not record.get("source_sha256"):
            failures.append(f"record_{i}_missing_source_provenance")
        if not isinstance(record.get("sequence_index"), int):
            failures.append(f"record_{i}_missing_sequence_index")
        if any(not isinstance(value, (int, float)) or not math.isfinite(value) for value in vector):
            failures.append(f"record_{i}_nonfinite_embedding")
        if not any(abs(float(value)) > 1e-12 for value in vector):
            failures.append(f"record_{i}_zero_embedding")
        lengths.append(int(record.get("length", 0)))
        source_hashes.add(record.get("source_sha256"))
        vector_hashes[hashlib.sha256(json.dumps(vector, separators=(",", ":")).encode()).hexdigest()] += 1
    duplicates = sum(count - 1 for count in vector_hashes.values() if count > 1)
    report = {
        "artifact_kind": "unlabeled_sequence_embedding_index_validation",
        "index": str(args.index.resolve()),
        "record_count": len(records),
        "embedding_dimension": dimension,
        "source_count": len(source_hashes),
        "length_summary": {"min": min(lengths, default=0), "max": max(lengths, default=0)},
        "duplicate_embedding_records": duplicates,
        "failures": failures,
        "success": not failures,
        "safe_for_supervised_training": False,
        "safe_for_model_claim": False,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"success": report["success"], "records": len(records), "sources": len(source_hashes), "duplicates": duplicates, "failures": len(failures)}))
    return 0 if report["success"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
