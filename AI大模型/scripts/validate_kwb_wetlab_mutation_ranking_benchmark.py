#!/usr/bin/env python3
"""Validate the real KWB wet-lab mutation ranking evaluation cache."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
DATASET = AI_ROOT / "cache" / "advanced_features" / "benchmarks" / "kwb_wetlab_mutation_ranking" / "dataset.jsonl"
SPLIT = AI_ROOT / "cache" / "advanced_features" / "benchmarks" / "kwb_wetlab_mutation_ranking" / "split_definition.json"
METRIC = AI_ROOT / "cache" / "advanced_features" / "benchmarks" / "kwb_wetlab_mutation_ranking" / "metric_report.json"
REPORT = AI_ROOT / "reports" / "kwb_wetlab_mutation_ranking_benchmark_validation_report.json"
MUTATION_RE = re.compile(r"^[A-Z][0-9]+[A-Z]$")
LABELS = {"positive", "neutral", "negative"}


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate KWB wet-lab mutation ranking benchmark")
    parser.add_argument("--dataset", type=Path, default=DATASET)
    parser.add_argument("--split", type=Path, default=SPLIT)
    parser.add_argument("--metric", type=Path, default=METRIC)
    parser.add_argument("--report", type=Path, default=REPORT)
    args = parser.parse_args()
    rows = load_jsonl(args.dataset)
    split = load_json(args.split)
    metric = load_json(args.metric)
    failures: list[str] = []
    ids = set()
    groups = set()
    for index, row in enumerate(rows):
        prefix = f"row_{index}"
        record_id = row.get("benchmark_record_id")
        group = f"{row.get('project_id')}::{row.get('variant_name')}"
        if not record_id or record_id in ids:
            failures.append(f"{prefix}:duplicate_or_missing_record_id")
        ids.add(record_id)
        if not row.get("project_id") or not row.get("variant_name"):
            failures.append(f"{prefix}:missing_project_or_variant")
        if not MUTATION_RE.match(str(row.get("variant_name") or "")):
            failures.append(f"{prefix}:variant_not_single_substitution")
        if row.get("mutation_label") not in LABELS:
            failures.append(f"{prefix}:invalid_mutation_label")
        if not row.get("raw_evidence_row_count", 0) > 0:
            failures.append(f"{prefix}:raw_evidence_missing")
        if row.get("training_label_source") is not False or row.get("ready_for_training_import") is not False:
            failures.append(f"{prefix}:training_guard_not_closed")
        if row.get("numbering_status") != "not_reviewed_project_numbering":
            failures.append(f"{prefix}:numbering_status_changed")
        groups.add(group)
    if split.get("leakage_check_status") != "passed":
        failures.append("split:leakage_check_not_passed")
    if split.get("train_rows") != 0 or split.get("validation_rows") != 0 or split.get("test_rows") != len(rows):
        failures.append("split:unexpected_split_counts")
    if metric.get("dataset_rows") != len(rows) or metric.get("ready_as_benchmark_scorecard") is not True:
        failures.append("metric:dataset_rows_or_scorecard_status_invalid")
    report = {
        "success": not failures,
        "dataset_rows": len(rows),
        "unique_variant_groups": len(groups),
        "failures": failures,
        "training_import_written_rows": 0,
        "strict_holdout_rows_written": 0,
        "ready_for_model_claim": False,
        "safe_for_model_claim": False,
        "release_ready": False,
        "policy": "Evaluation-only real wet-lab evidence. Project numbering and parent sequence remain unreviewed; this artifact cannot become training data or the strict holdout.",
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"success": report["success"], "dataset_rows": len(rows), "failures": len(failures), "training_import_written_rows": 0}, ensure_ascii=False))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
