#!/usr/bin/env python3
"""Create a deterministic protein-group split for supervised mutation labels."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
INPUT = AI_ROOT / "datasets" / "curated" / "enzyme_mutation_training_table.jsonl"
OUTPUT = AI_ROOT / "reports" / "supervised_mutation_split_report.json"


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def split_for_group(group_key: str) -> str:
    digest = hashlib.sha256(group_key.encode("utf-8")).hexdigest()
    bucket = int(digest[:8], 16) % 100
    if bucket < 70:
        return "train"
    if bucket < 85:
        return "validation"
    return "test"


def main() -> int:
    parser = argparse.ArgumentParser(description="Build supervised mutation group split")
    parser.add_argument("--input", type=Path, default=INPUT)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    args = parser.parse_args()

    rows = load_jsonl(args.input)
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        groups[row.get("group_key") or f"record:{row.get('record_id')}"].append(row)

    assignments = {group: split_for_group(group) for group in sorted(groups)}
    row_split_counts = Counter(assignments[row.get("group_key") or f"record:{row.get('record_id')}"] for row in rows)
    label_by_split = {
        split: dict(Counter(row["label_decision"] for row in rows if assignments[row.get("group_key") or f"record:{row.get('record_id')}"] == split))
        for split in ("train", "validation", "test")
    }
    group_label_profiles = {
        group: dict(Counter(row["label_decision"] for row in group_rows))
        for group, group_rows in sorted(groups.items())
    }
    report = {
        "rows": len(rows),
        "groups": len(groups),
        "split_group_counts": dict(Counter(assignments.values())),
        "split_row_counts": dict(row_split_counts),
        "label_distribution_by_split": label_by_split,
        "group_leakage": [],
        "assignments": assignments,
        "group_label_profiles": group_label_profiles,
        "split_rule": "sha256(group_key) with 70/15/15 train/validation/test buckets",
        "empty_input": len(rows) == 0,
        "safe_for_model_claim": False,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"rows": len(rows), "groups": len(groups), "output": str(args.output)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
