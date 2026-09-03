#!/usr/bin/env python3
"""Summarize normalized kinetics observations without collapsing raw evidence."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from collections import defaultdict
from pathlib import Path
from statistics import median
from typing import Any


GROUP_FIELDS = (
    "source",
    "ec",
    "substrate",
    "organism",
    "uniprot_ids",
    "enzyme_class",
    "parameter",
    "unit",
    "ph",
    "temperature_c",
)


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def group_key(row: dict[str, Any]) -> str:
    payload = {field: row.get(field) for field in GROUP_FIELDS}
    return hashlib.sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True).encode()).hexdigest()


def summarize(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        if row.get("value") is not None and not row.get("quality_flags"):
            groups[group_key(row)].append(row)

    summaries = []
    for condition_hash, observations in sorted(groups.items()):
        values = [float(row["value"]) for row in observations]
        mean = sum(values) / len(values)
        variance = sum((value - mean) ** 2 for value in values) / len(values) if values else 0.0
        first_row = observations[0]
        summaries.append(
            {
                "condition_hash": condition_hash,
                "source": first_row.get("source"),
                "ec": first_row.get("ec"),
                "substrate": first_row.get("substrate"),
                "organism": first_row.get("organism"),
                "uniprot_ids": first_row.get("uniprot_ids"),
                "enzyme_class": first_row.get("enzyme_class"),
                "parameter": first_row.get("parameter"),
                "unit": first_row.get("unit"),
                "ph": first_row.get("ph"),
                "temperature_c": first_row.get("temperature_c"),
                "observation_count": len(values),
                "median_value": median(values),
                "mean_value": mean,
                "min_value": min(values),
                "max_value": max(values),
                "std_population": math.sqrt(variance),
                "source_rows": [
                    {
                        "source_file": row.get("source_file"),
                        "source_file_sha256": row.get("source_file_sha256"),
                        "source_row_index": row.get("source_row_index"),
                    }
                    for row in observations
                ],
                "training_eligible": False,
                "aggregation_policy": "summary_only; raw observations remain authoritative; max_value is descriptive, not the selected label",
            }
        )
    return summaries


def main() -> None:
    parser = argparse.ArgumentParser(description="Summarize normalized kinetics observations.")
    parser.add_argument("input", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    rows = load_jsonl(args.input)
    summaries = summarize(rows)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in summaries),
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "input_rows": len(rows),
                "summary_rows": len(summaries),
                "training_eligible_rows": 0,
                "raw_observations_retained": sum(row["observation_count"] for row in summaries),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
