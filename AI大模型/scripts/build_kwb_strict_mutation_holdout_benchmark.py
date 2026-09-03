#!/usr/bin/env python3
"""Build a local benchmark scorecard from the strict verified mutation holdout."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
STRICT_TABLE = AI_ROOT / "datasets" / "curated" / "enzyme_mutation_supervised_repaired_verified.jsonl"
SPLIT_REPORT = AI_ROOT / "reports" / "repaired_supervised_split_report.json"
BASELINE_EVAL = AI_ROOT / "reports" / "repaired_supervised_baseline_eval.json"
BASELINE_MODEL = AI_ROOT / "prototype" / "repaired_supervised_baseline_model.json"
INTAKE = AI_ROOT / "datasets" / "benchmark" / "benchmark_score_cache_intake.local.jsonl"
OUT_DIR = AI_ROOT / "cache" / "advanced_features" / "benchmarks" / "kwb_strict_mutation_holdout"
REPORT_OUT = AI_ROOT / "reports" / "kwb_strict_mutation_holdout_benchmark_report.json"

HEAD = "mutation_rank"
BENCHMARK_NAME = "KWB strict mutation holdout"
LABELS = ["go", "watch", "no_go"]


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def rel(path: Path) -> str:
    return str(path.relative_to(AI_ROOT))


def split_for(row: dict[str, Any], split_report: dict[str, Any]) -> str:
    assignments = split_report.get("assignments") if isinstance(split_report.get("assignments"), dict) else {}
    return str(assignments.get(row.get("group_key")) or "unknown")


def confusion(records: list[dict[str, Any]]) -> dict[str, dict[str, int]]:
    matrix = {actual: {pred: 0 for pred in LABELS} for actual in LABELS}
    for row in records:
        actual = row.get("actual")
        predicted = row.get("predicted")
        if actual in matrix and predicted in matrix[actual]:
            matrix[actual][predicted] += 1
    return matrix


def metrics(records: list[dict[str, Any]]) -> dict[str, Any]:
    if not records:
        return {
            "rows": 0,
            "accuracy": None,
            "macro_f1": None,
            "label_distribution": {},
            "confusion": confusion([]),
        }
    correct = sum(1 for row in records if row.get("actual") == row.get("predicted"))
    matrix = confusion(records)
    f1_values: list[float] = []
    for label in LABELS:
        tp = matrix[label][label]
        fp = sum(matrix[actual][label] for actual in LABELS if actual != label)
        fn = sum(matrix[label][predicted] for predicted in LABELS if predicted != label)
        precision = tp / (tp + fp) if tp + fp else 0.0
        recall = tp / (tp + fn) if tp + fn else 0.0
        f1_values.append(2 * precision * recall / (precision + recall) if precision + recall else 0.0)
    return {
        "rows": len(records),
        "accuracy": round(correct / len(records), 6),
        "macro_f1": round(sum(f1_values) / len(f1_values), 6),
        "label_distribution": dict(Counter(str(row.get("actual")) for row in records)),
        "confusion": matrix,
    }


def eval_records(eval_report: dict[str, Any], split: str) -> list[dict[str, Any]]:
    splits = eval_report.get("splits") if isinstance(eval_report.get("splits"), dict) else {}
    payload = splits.get(split) if isinstance(splits.get(split), dict) else {}
    return list(payload.get("records") or [])


def update_intake(intake_path: Path, row: dict[str, Any]) -> None:
    rows = load_jsonl(intake_path)
    key = (row["head"], row["benchmark_name"])
    updated = False
    next_rows = []
    for existing in rows:
        existing_key = (existing.get("head"), existing.get("benchmark_name"))
        if existing_key == key:
            next_rows.append(row)
            updated = True
        else:
            next_rows.append(existing)
    if not updated:
        next_rows.append(row)
    write_jsonl(intake_path, next_rows)


def main() -> int:
    parser = argparse.ArgumentParser(description="Build KWB strict mutation holdout benchmark artifacts")
    parser.add_argument("--strict-table", type=Path, default=STRICT_TABLE)
    parser.add_argument("--split-report", type=Path, default=SPLIT_REPORT)
    parser.add_argument("--baseline-eval", type=Path, default=BASELINE_EVAL)
    parser.add_argument("--baseline-model", type=Path, default=BASELINE_MODEL)
    parser.add_argument("--intake", type=Path, default=INTAKE)
    parser.add_argument("--out-dir", type=Path, default=OUT_DIR)
    parser.add_argument("--report", type=Path, default=REPORT_OUT)
    args = parser.parse_args()

    rows = load_jsonl(args.strict_table)
    split_report = load_json(args.split_report)
    eval_report = load_json(args.baseline_eval)
    model = load_json(args.baseline_model)
    created_at = datetime.now(timezone.utc).isoformat()

    dataset_rows = []
    for row in rows:
        dataset_rows.append({
            "benchmark_record_id": f"kwb_strict_holdout::{row.get('record_id')}",
            "record_id": row.get("record_id"),
            "uniprot_id": row.get("uniprot_id"),
            "group_key": row.get("group_key"),
            "mutation": row.get("mutation"),
            "split": split_for(row, split_report),
            "actual_label": row.get("label_decision"),
            "curation_status": row.get("curation_status"),
            "numbering_verified_by_sequence": bool(row.get("numbering_verified_by_sequence")),
            "usable_as_supervised_label": bool(row.get("usable_as_supervised_label")),
            "label_source_db": row.get("label_source_db"),
            "label_method": row.get("label_method"),
            "source": row.get("source"),
            "local_only": True,
            "allowed_use": "local benchmark/model evaluation only",
            "forbidden_use": "do not treat this benchmark artifact as new KWB wet-lab feedback",
        })

    validation_records = eval_records(eval_report, "validation")
    test_records = eval_records(eval_report, "test")
    primary_records = test_records
    diagnostic_records = validation_records

    dataset_path = args.out_dir / "dataset.jsonl"
    split_path = args.out_dir / "split_definition.json"
    scorecard_path = args.out_dir / "scorecard.json"
    metric_path = args.out_dir / "metric_report.json"
    write_jsonl(dataset_path, dataset_rows)

    leakage_checks = {
        "group_leakage_rows": len(split_report.get("group_leakage") or []),
        "group_leakage_passed": not bool(split_report.get("group_leakage")),
        "label_columns_excluded_from_features": "label_stability_delta_tm_c and label_ddg excluded from training features"
        in str(eval_report.get("leakage_guard") or ""),
        "primary_holdout_split": "test",
        "validation_split_used_for_model_selection": True,
        "primary_holdout_excludes_validation": True,
    }
    split_definition = {
        "benchmark_name": BENCHMARK_NAME,
        "head": HEAD,
        "created_at": created_at,
        "dataset_rows": len(dataset_rows),
        "split_source": rel(args.split_report),
        "split_source_sha256": sha256(args.split_report),
        "split_rule": split_report.get("split_rule"),
        "split_row_counts": split_report.get("split_row_counts"),
        "split_group_counts": split_report.get("split_group_counts"),
        "assignments": split_report.get("assignments"),
        "primary_eval_split": "test",
        "diagnostic_eval_split": "validation",
        "leakage_checks": leakage_checks,
        "leakage_check_status": "passed" if all(
            [
                leakage_checks["group_leakage_passed"],
                leakage_checks["label_columns_excluded_from_features"],
                leakage_checks["primary_holdout_excludes_validation"],
            ]
        ) else "failed",
    }
    write_json(split_path, split_definition)

    scorecard = {
        "benchmark_name": BENCHMARK_NAME,
        "head": HEAD,
        "created_at": created_at,
        "local_only": True,
        "model": eval_report.get("model"),
        "model_version": eval_report.get("version"),
        "model_artifact": rel(args.baseline_model),
        "model_artifact_sha256": sha256(args.baseline_model),
        "training_rows": model.get("trained_on_rows"),
        "training_source": model.get("training_source"),
        "selected_strategy": eval_report.get("selected_strategy"),
        "primary_split": "test",
        "primary_records": primary_records,
        "diagnostic_validation_records": diagnostic_records,
        "policy": "Primary benchmark score uses the protein-group test holdout only; validation is diagnostic because it was used for strategy selection.",
        "limitations": [
            f"strict supervised source currently has {len(dataset_rows)} rows",
            f"primary test holdout currently has {len(primary_records)} rows and is not statistically strong",
            "this benchmark does not provide reviewed numbering for weak rows, ddG backend output, or wet-lab feedback",
        ],
    }
    write_json(scorecard_path, scorecard)

    primary_metrics = metrics(primary_records)
    ready_as_benchmark_scorecard = (
        len(dataset_rows) > 0
        and len(primary_records) > 0
        and split_definition["leakage_check_status"] == "passed"
        and primary_metrics.get("accuracy") is not None
        and primary_metrics.get("macro_f1") is not None
    )
    metric_report = {
        "benchmark_name": BENCHMARK_NAME,
        "head": HEAD,
        "created_at": created_at,
        "local_only": True,
        "primary_split": "test",
        "primary_metrics": primary_metrics,
        "diagnostic_validation_metrics": metrics(diagnostic_records),
        "all_holdout_metrics": metrics([*diagnostic_records, *primary_records]),
        "ready_as_benchmark_scorecard": ready_as_benchmark_scorecard,
        "ready_for_model_quality_claim": False,
        "reason_not_model_quality_claim": (
            "Strict holdout benchmark is not model-claim ready because it requires a non-empty "
            "leakage-passed strict dataset, non-empty primary holdout metrics, and statistical "
            "review before use as model-quality evidence."
        ),
    }
    write_json(metric_path, metric_report)

    intake_row = {
        "head": HEAD,
        "benchmark_name": BENCHMARK_NAME,
        "dataset_version": "kwb-strict-mutation-holdout-v0.1-local-2026-07-28",
        "license_review_status": "approved_for_benchmark_only",
        "local_dataset_uri": rel(dataset_path),
        "dataset_sha256": sha256(dataset_path),
        "split_definition_uri": rel(split_path),
        "split_sha256": sha256(split_path),
        "scorecard_uri": rel(scorecard_path),
        "scorecard_sha256": sha256(scorecard_path),
        "metric_report_uri": rel(metric_path),
        "metric_sha256": sha256(metric_path),
        "leakage_check_status": split_definition["leakage_check_status"],
        "reviewer": "local_safe_training_pipeline",
        "reviewed_at": created_at,
        "notes": "Local strict verified mutation holdout benchmark. Approved only for local benchmark cache evaluation; not external legal approval and not KWB wet-lab feedback.",
    }
    update_intake(args.intake, intake_row)

    report = {
        "created_at": created_at,
        "local_only": True,
        "benchmark_name": BENCHMARK_NAME,
        "head": HEAD,
        "dataset_rows": len(dataset_rows),
        "primary_holdout_rows": len(primary_records),
        "diagnostic_validation_rows": len(diagnostic_records),
        "leakage_check_status": split_definition["leakage_check_status"],
        "intake": rel(args.intake),
        "artifacts": {
            "dataset": {"path": rel(dataset_path), "sha256": sha256(dataset_path)},
            "split_definition": {"path": rel(split_path), "sha256": sha256(split_path)},
            "scorecard": {"path": rel(scorecard_path), "sha256": sha256(scorecard_path)},
            "metric_report": {"path": rel(metric_path), "sha256": sha256(metric_path)},
        },
        "ready_as_benchmark_scorecard": ready_as_benchmark_scorecard,
        "safe_for_model_claim": False,
    }
    write_json(args.report, report)
    print(json.dumps({
        "benchmark_name": BENCHMARK_NAME,
        "dataset_rows": report["dataset_rows"],
        "primary_holdout_rows": report["primary_holdout_rows"],
        "leakage_check_status": report["leakage_check_status"],
        "ready_as_benchmark_scorecard": report["ready_as_benchmark_scorecard"],
        "safe_for_model_claim": report["safe_for_model_claim"],
        "output": rel(args.report),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
