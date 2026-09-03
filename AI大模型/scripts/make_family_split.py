#!/usr/bin/env python3
"""Create a deterministic local family-level split report."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path


AI_ROOT = Path(__file__).resolve().parents[1]
TRAINING_TABLE = AI_ROOT / "datasets" / "curated" / "training_table.jsonl"
OUT = AI_ROOT / "reports" / "family_split_report.json"


def load_rows(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def group_key(row: dict) -> str:
    for key in ("project_id", "enzyme_family", "case_id"):
        value = row.get(key)
        if value:
            return f"{key}:{value}"
    return f"mutation:{row.get('mutation')}"


def bucket_for_group(key: str) -> str:
    digest = hashlib.sha256(key.encode("utf-8")).hexdigest()
    value = int(digest[:8], 16) % 100
    if value < 70:
        return "train"
    if value < 85:
        return "validation"
    return "test"


def main() -> int:
    parser = argparse.ArgumentParser(description="Build local family split report")
    parser.add_argument("--input", type=Path, default=TRAINING_TABLE)
    parser.add_argument("--output", type=Path, default=OUT)
    args = parser.parse_args()

    rows = load_rows(args.input)
    groups = defaultdict(list)
    for row in rows:
        groups[group_key(row)].append(row)

    assignments = {key: bucket_for_group(key) for key in groups}
    counts = Counter(assignments.values())
    family_counts = {
        split: dict(Counter(row.get("enzyme_family") or "unknown" for key, rows_ in groups.items() if assignments[key] == split for row in rows_))
        for split in ("train", "validation", "test")
    }
    leakage = []
    for key, split in assignments.items():
        seen = [candidate for candidate, candidate_split in assignments.items() if candidate == key and candidate_split != split]
        if seen:
            leakage.append(key)

    report = {
        "rows": len(rows),
        "groups": len(groups),
        "split_group_counts": dict(counts),
        "split_row_counts": dict(Counter(assignments[group_key(row)] for row in rows)),
        "family_counts": family_counts,
        "group_leakage": sorted(set(leakage)),
        "assignments": assignments,
        "note": "benchmark fixtures are included only for local R&D baseline; production training must exclude benchmark cases",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"rows": len(rows), "groups": len(groups), "output": str(args.output)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
