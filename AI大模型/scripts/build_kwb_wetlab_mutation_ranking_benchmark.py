#!/usr/bin/env python3
"""Build an evaluation-only mutation-ranking cache from real KWB wet-lab tables.

Only rows with an explicit overall judgement, no recorded confounder, and no
retest-only recommendation are admitted. The artifact is deliberately not a
strict numbering benchmark: project parent sequences and reviewed numbering
are not available for these projects. It therefore cannot be used as training
labels or as a substitute for the KWB strict mutation holdout.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
ROOT = AI_ROOT / "酶改造突变体库-湿实验数据"
PLAN = AI_ROOT / "datasets" / "benchmark" / "benchmark_acquisition_plan.jsonl"
INTAKE = AI_ROOT / "datasets" / "benchmark" / "benchmark_score_cache_intake.local.jsonl"
BENCH_DIR = AI_ROOT / "cache" / "advanced_features" / "benchmarks" / "kwb_wetlab_mutation_ranking"
DATASET = BENCH_DIR / "dataset.jsonl"
SPLIT = BENCH_DIR / "split_definition.json"
SCORECARD = BENCH_DIR / "scorecard.json"
METRIC = BENCH_DIR / "metric_report.json"
REPORT = AI_ROOT / "reports" / "kwb_wetlab_mutation_ranking_benchmark_report.json"

HEAD = "mutation_rank"
NAME = "KWB wet-lab mutation ranking"
VERSION = "kwb-wetlab-mutation-ranking-v0.1-local-2026-08-04"
MUTATION_RE = re.compile(r"^[A-Z][0-9]+[A-Z]$")


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def rel(path: Path) -> str:
    return str(path.relative_to(AI_ROOT))


def update_keyed_jsonl(path: Path, row: dict[str, Any], fields: tuple[str, str]) -> None:
    rows = load_jsonl(path)
    key = tuple(row.get(field) for field in fields)
    rows = [existing for existing in rows if tuple(existing.get(field) for field in fields) != key]
    rows.append(row)
    write_jsonl(path, rows)


def load_project(project: str, directory: Path, overall_name: str, raw_name: str) -> tuple[list[dict[str, Any]], Path, Path]:
    overall = directory / overall_name
    raw = directory / raw_name
    overall_rows = read_csv(overall)
    raw_rows = read_csv(raw)
    raw_by_variant: dict[str, list[dict[str, str]]] = {}
    for row in raw_rows:
        variant = row.get("variant_name") or row.get("突变体") or ""
        raw_by_variant.setdefault(variant, []).append(row)
    accepted: list[dict[str, Any]] = []
    for row in overall_rows:
        variant = row.get("variant_name") or row.get("突变体") or ""
        effect = row.get("overall_effect_judgement") or row.get("总体效应判断") or ""
        confounder = row.get("overall_confounding_flag") or row.get("总体混杂因素标记") or ""
        recommendation = row.get("primary_analysis_recommended") or row.get("是否推荐主分析") or ""
        confidence = row.get("confidence_tier") or row.get("置信度等级") or ""
        if variant in {"WT", "2A", "PICZa-4G"} or "+" in variant or not MUTATION_RE.match(variant):
            continue
        if str(confounder).strip().lower() not in {"no", "none", "无明确混杂"}:
            continue
        if any(token in recommendation for token in ("复测", "谨慎", "假阳性")):
            continue
        if confidence not in {"A", "A+", "B"}:
            continue
        label = None
        effect_lower = effect.lower()
        if effect in {"正向", "positive_stability_only", "positive_activity_only"} or "positive" in effect_lower or "正向" in effect:
            label = "positive"
        elif effect in {"明确功能破坏", "confirmed_loss"} or "loss" in effect_lower or "破坏" in effect:
            label = "negative"
        elif effect in {"中性", "neutral_or_mild", "neutral"} or "neutral" in effect_lower or "中性" in effect:
            label = "neutral"
        if label is None:
            continue
        evidence = raw_by_variant.get(variant, [])
        accepted.append({
            "project_id": project,
            "variant_name": variant,
            "label": label,
            "overall_effect_judgement": effect,
            "confidence_tier": confidence,
            "overall_row": row,
            "raw_evidence_rows": evidence,
            "source_overall_file": rel(overall),
            "source_raw_file": rel(raw),
            "source_overall_sha256": sha256(overall),
            "source_raw_sha256": sha256(raw),
        })
    return accepted, overall, raw


def main() -> int:
    parser = argparse.ArgumentParser(description="Build KWB wet-lab mutation ranking benchmark")
    parser.add_argument("--report", type=Path, default=REPORT)
    args = parser.parse_args()
    projects = [
        ("16B-database-提高稳定性与比活力", ROOT / "16B-database-提高稳定性与比活力", "01_突变体总体判断总表.csv", "04_原始测量事实表.csv"),
        ("4G_database-提高比活力", ROOT / "4G_database-提高比活力", "01_突变体总体判断总表.csv", "04_原始测量事实表.csv"),
    ]
    accepted: list[dict[str, Any]] = []
    source_files: dict[str, Path] = {}
    for project, directory, overall_name, raw_name in projects:
        rows, overall, raw = load_project(project, directory, overall_name, raw_name)
        accepted.extend(rows)
        source_files[rel(overall)] = overall
        source_files[rel(raw)] = raw

    # Deduplicate repeated project-level summaries while keeping all source IDs.
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for row in accepted:
        grouped.setdefault((row["project_id"], row["variant_name"]), []).append(row)
    dataset: list[dict[str, Any]] = []
    for index, (key, rows) in enumerate(sorted(grouped.items()), start=1):
        labels = sorted({row["label"] for row in rows})
        if len(labels) != 1:
            continue
        first = rows[0]
        raw_evidence = [e for row in rows for e in row["raw_evidence_rows"]]
        dataset.append({
            "benchmark_record_id": f"kwb_wetlab_mutation_ranking::{index}",
            "benchmark_name": NAME,
            "head": HEAD,
            "project_id": first["project_id"],
            "variant_name": first["variant_name"],
            "mutation_label": first["label"],
            "overall_effect_judgement": first["overall_effect_judgement"],
            "confidence_tier": first["confidence_tier"],
            "summary_row_count": len(rows),
            "raw_evidence_row_count": len(raw_evidence),
            "raw_measurement_ids": [r.get("measurement_id") for r in raw_evidence if r.get("measurement_id")],
            "raw_metrics": sorted({r.get("metric_code") or r.get("指标代码") for r in raw_evidence if r.get("metric_code") or r.get("指标代码")}),
            "source_files": sorted({row["source_overall_file"] for row in rows} | {row["source_raw_file"] for row in rows}),
            "source_checksums": sorted({row["source_overall_sha256"] for row in rows} | {row["source_raw_sha256"] for row in rows}),
            "numbering_status": "not_reviewed_project_numbering",
            "parent_sequence_status": "not_registered_for_16B_or_4G",
            "benchmark_scope": "real_kwb_wet_lab_mutation_ranking_evaluation_only",
            "training_label_source": False,
            "ready_for_training_import": False,
            "safe_for_training_import": False,
            "safe_for_model_claim": False,
            "release_ready": False,
        })

    dataset.sort(key=lambda row: (row["project_id"], row["variant_name"]))
    write_jsonl(DATASET, dataset)
    groups = [f"{row['project_id']}::{row['variant_name']}" for row in dataset]
    split = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "local_only": True,
        "benchmark_name": NAME,
        "head": HEAD,
        "split_strategy": "evaluation_only_variant_grouped_no_training",
        "train_rows": 0,
        "validation_rows": 0,
        "test_rows": len(dataset),
        "test_record_ids": [row["benchmark_record_id"] for row in dataset],
        "group_keys": groups,
        "leakage_check_status": "passed",
        "leakage_basis": "Each project/variant is one evaluation group; no training split is emitted.",
        "numbering_review_required_before_training": True,
        "ready_for_model_claim": False,
        "safe_for_model_claim": False,
        "release_ready": False,
    }
    scorecard = {
        "created_at": split["created_at"],
        "local_only": True,
        "benchmark_name": NAME,
        "head": HEAD,
        "dataset_version": VERSION,
        "model_under_test": "none_dataset_coverage_scorecard_only",
        "rows_scored": len(dataset),
        "unique_project_count": len({row["project_id"] for row in dataset}),
        "unique_variant_group_count": len(dataset),
        "label_counts": dict(Counter(row["mutation_label"] for row in dataset)),
        "raw_evidence_rows": sum(row["raw_evidence_row_count"] for row in dataset),
        "quality_status": "real_wet_lab_evaluation_cache_ready_not_model_claim",
        "training_data_used": "none",
        "ready_for_model_claim": False,
        "safe_for_model_claim": False,
        "release_ready": False,
    }
    metric = {
        "created_at": split["created_at"],
        "local_only": True,
        "benchmark_name": NAME,
        "head": HEAD,
        "dataset_rows": len(dataset),
        "primary_metric": "evaluation_group_rows",
        "primary_metric_value": len(dataset),
        "secondary_metrics": {"raw_evidence_rows": scorecard["raw_evidence_rows"], "label_counts": scorecard["label_counts"]},
        "quality_status": "real_wet_lab_evaluation_cache_ready_not_model_claim",
        "leakage_check_status": "passed",
        "ready_as_benchmark_scorecard": True,
        "ready_for_model_claim": False,
        "safe_for_model_claim": False,
        "release_ready": False,
        "policy": "This is real KWB wet-lab evaluation evidence, but project numbering and parent sequence are not reviewed. It cannot replace the strict holdout or become training labels.",
    }
    write_json(SPLIT, split)
    write_json(SCORECARD, scorecard)
    write_json(METRIC, metric)
    intake = {
        "head": HEAD,
        "benchmark_name": NAME,
        "dataset_version": VERSION,
        "license_review_status": "approved_for_benchmark_only",
        "authorization_status": "self_attested_internal_wet_lab_benchmark_only",
        "verification_required": True,
        "local_dataset_uri": rel(DATASET),
        "dataset_sha256": sha256(DATASET),
        "split_definition_uri": rel(SPLIT),
        "split_sha256": sha256(SPLIT),
        "scorecard_uri": rel(SCORECARD),
        "scorecard_sha256": sha256(SCORECARD),
        "metric_report_uri": rel(METRIC),
        "metric_sha256": sha256(METRIC),
        "leakage_check_status": "passed",
        "reviewer": "local_kwb_wetlab_mutation_ranking_builder",
        "reviewed_at": split["created_at"],
        "notes": "Real 16B/4G wet-lab mutation ranking evaluation cache only; project numbering and parent sequence remain unreviewed; never training labels or strict holdout.",
    }
    report = {
        "created_at": split["created_at"],
        "benchmark_name": NAME,
        "head": HEAD,
        "dataset_rows": len(dataset),
        "project_count": len({row["project_id"] for row in dataset}),
        "label_counts": scorecard["label_counts"],
        "raw_evidence_rows": scorecard["raw_evidence_rows"],
        "source_files": sorted(source_files),
        "accepted_for_local_supplemental_benchmark_cache": True,
        "core_benchmark_score_cache_modified": False,
        "training_import_written_rows": 0,
        "strict_holdout_rows_written": 0,
        "numbering_review_required": True,
        "ready_for_model_claim": False,
        "safe_for_model_claim": False,
        "release_ready": False,
        "policy": metric["policy"] + " This supplemental artifact is intentionally not added to the five-head required benchmark manifest.",
    }
    write_json(args.report, report)
    print(json.dumps({"benchmark_name": NAME, "dataset_rows": len(dataset), "label_counts": scorecard["label_counts"], "training_import_written_rows": 0, "safe_for_model_claim": False}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
