#!/usr/bin/env python3
"""Remove one accidentally registered supplemental benchmark from core inputs."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


AI_ROOT = Path(__file__).resolve().parents[1]
NAME = "KWB wet-lab mutation ranking"


def load(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write(path: Path, rows: list[dict]) -> None:
    path.write_text("".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Remove supplemental benchmark from core acquisition/intake inputs")
    parser.add_argument("--plan", type=Path, default=AI_ROOT / "datasets/benchmark/benchmark_acquisition_plan.jsonl")
    parser.add_argument("--intake", type=Path, default=AI_ROOT / "datasets/benchmark/benchmark_score_cache_intake.local.jsonl")
    args = parser.parse_args()
    for path in (args.plan, args.intake):
        rows = load(path)
        filtered = [row for row in rows if row.get("benchmark_name") != NAME]
        write(path, filtered)
        print(json.dumps({"path": str(path), "removed": len(rows) - len(filtered), "remaining": len(filtered)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
