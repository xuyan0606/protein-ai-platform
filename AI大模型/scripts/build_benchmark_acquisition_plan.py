#!/usr/bin/env python3
"""Build benchmark acquisition plan from the head-level benchmark matrix."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
MATRIX = AI_ROOT / "reports" / "benchmark_matrix_report.json"
OUT = AI_ROOT / "datasets" / "benchmark" / "benchmark_acquisition_plan.jsonl"
REPORT_OUT = AI_ROOT / "reports" / "benchmark_acquisition_plan_report.json"


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Build benchmark acquisition plan")
    parser.add_argument("--matrix", type=Path, default=MATRIX)
    parser.add_argument("--output", type=Path, default=OUT)
    parser.add_argument("--report", type=Path, default=REPORT_OUT)
    args = parser.parse_args()

    matrix = load_json(args.matrix)
    rows: list[dict[str, Any]] = []
    for head in matrix.get("heads", []):
        for benchmark in head.get("required_benchmarks", []):
            rows.append({
                "head": head.get("head"),
                "benchmark_name": benchmark,
                "acquisition_status": "not_configured",
                "license_review_status": "not_reviewed",
                "local_dataset_uri": None,
                "checksum": None,
                "split_strategy": "not_selected",
                "leakage_check_status": "not_run",
                "scorecard_status": "not_ready",
                "allowed_use": "benchmark planning only",
                "forbidden_use": "do not use predicted/reference benchmark data as KWB wet-lab labels",
            })
    write_jsonl(args.output, rows)
    report = {
        "local_only": True,
        "plan_rows": len(rows),
        "configured_benchmarks": 0,
        "scorecards_ready": 0,
        "ready_for_model_claim": False,
        "plan_file": str(args.output),
        "policy": "Benchmark acquisition is planned only; no datasets are downloaded or approved by this step.",
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"plan_rows": len(rows), "ready_for_model_claim": False, "output": str(args.report)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
