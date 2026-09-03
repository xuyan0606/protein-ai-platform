#!/usr/bin/env python3
"""Build a local training table from sample and benchmark-derived cases."""

from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FEATURES_SCRIPT = ROOT / "scripts" / "extract_features.py"
BENCH_SCRIPT = ROOT / "scripts" / "run_local_benchmark.py"
SAMPLE_CASE = ROOT / "datasets" / "sample_case.json"
CASES_DIR = ROOT / "benchmarks" / "cases"
OUT_JSONL = ROOT / "datasets" / "curated" / "training_table.jsonl"


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main() -> int:
    parser = argparse.ArgumentParser(description="Build local KWB training table")
    parser.add_argument("--output", type=Path, default=OUT_JSONL)
    args = parser.parse_args()

    features = load_module(FEATURES_SCRIPT, "extract_features")
    bench = load_module(BENCH_SCRIPT, "run_local_benchmark")

    rows = []
    sample_case = json.loads(SAMPLE_CASE.read_text(encoding="utf-8"))
    rows.extend(features.extract_rows(sample_case))

    for case_file in sorted(CASES_DIR.glob("*.json")):
        bench_case = json.loads(case_file.read_text(encoding="utf-8"))
        enzyme_case = bench.case_to_enzyme_case(bench_case)
        rows.extend(features.extract_rows(enzyme_case))

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows),
        encoding="utf-8",
    )
    print(json.dumps({"rows": len(rows), "output": str(args.output)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

