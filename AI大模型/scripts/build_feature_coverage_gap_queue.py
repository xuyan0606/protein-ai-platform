#!/usr/bin/env python3
"""Build a fail-closed queue for head/protein-group input feature coverage gaps."""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
FEATURE_INDEX = AI_ROOT / "datasets" / "features" / "validated_feature_index.jsonl"
COVERAGE_JSONL = AI_ROOT / "datasets" / "features" / "feature_coverage_by_head_group.jsonl"
COVERAGE_REPORT = AI_ROOT / "reports" / "feature_coverage_by_head_group_report.json"
COVERAGE_VALIDATION = AI_ROOT / "reports" / "feature_coverage_by_head_group_validation_report.json"
OUT_JSONL = AI_ROOT / "datasets" / "features" / "feature_coverage_gap_queue.jsonl"
OUT_REPORT = AI_ROOT / "reports" / "feature_coverage_gap_queue_report.json"

FEATURE_FAMILY_HEADS = {
    "msa_conservation": [
        "mutation_rank",
        "stability",
        "activity_risk",
        "substrate_fit",
        "assay_success",
    ],
    "structure_graph": ["mutation_rank", "stability", "substrate_fit"],
    "pyrosetta_ddg_reu_input": ["stability"],
    "structure_site": ["mutation_rank", "stability", "substrate_fit"],
}


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )


def required_feature_families(head: str) -> list[str]:
    return sorted(family for family, heads in FEATURE_FAMILY_HEADS.items() if head in heads)


def main() -> int:
    created_at = datetime.now(timezone.utc).isoformat()
    feature_rows = load_jsonl(FEATURE_INDEX)
    coverage_rows = load_jsonl(COVERAGE_JSONL)
    coverage_report = load_json(COVERAGE_REPORT)
    coverage_validation = load_json(COVERAGE_VALIDATION)

    feature_family_counts_by_group: dict[str, Counter[str]] = defaultdict(Counter)
    feature_ids_by_group: dict[str, list[str]] = defaultdict(list)
    for row in feature_rows:
        group_id = f"uniprot:{row.get('uniprot_id') or 'unknown_uniprot'}"
        feature_family_counts_by_group[group_id][str(row.get("feature_family"))] += 1
        if row.get("feature_index_id"):
            feature_ids_by_group[group_id].append(str(row["feature_index_id"]))

    gap_rows: list[dict[str, Any]] = []
    for coverage in coverage_rows:
        if coverage.get("coverage_status") != "no_input_feature_coverage":
            continue
        head = str(coverage.get("head"))
        group_id = str(coverage.get("protein_group_id"))
        expected_families = required_feature_families(head)
        available_counts = dict(sorted(feature_family_counts_by_group[group_id].items()))
        missing_families = [
            family for family in expected_families
            if available_counts.get(family, 0) == 0
        ]
        gap_rows.append({
            "created_at": created_at,
            "local_only": True,
            "gap_id": f"feature-coverage-gap::{head}::{group_id}",
            "gap_type": "input_feature_coverage_gap",
            "head": head,
            "protein_group_id": group_id,
            "uniprot_id": coverage.get("uniprot_id"),
            "coverage_status": coverage.get("coverage_status"),
            "input_feature_rows": coverage.get("input_feature_rows"),
            "model_consumable_feature_rows": coverage.get("model_consumable_feature_rows"),
            "training_label_source_rows": coverage.get("training_label_source_rows"),
            "feature_rows_counted_as_labels": 0,
            "required_input_feature_families_for_head": expected_families,
            "missing_input_feature_families": missing_families,
            "available_feature_family_counts_for_group": available_counts,
            "available_feature_index_ids_for_group": sorted(feature_ids_by_group[group_id]),
            "remediation_action": "refresh or add reviewed input-feature evidence for the missing family without creating labels",
            "source_coverage_jsonl": "datasets/features/feature_coverage_by_head_group.jsonl",
            "source_coverage_report": "reports/feature_coverage_by_head_group_report.json",
            "source_coverage_validation_report": "reports/feature_coverage_by_head_group_validation_report.json",
            "source_feature_index": "datasets/features/validated_feature_index.jsonl",
            "training_import_allowed": False,
            "safe_for_training_import": False,
            "safe_for_model_claim": False,
            "release_ready": False,
            "production_execution_allowed": False,
            "policy": (
                "Coverage gaps are remediation work items only. They do not authorize label import, "
                "training execution, model claims, release, or production actions."
            ),
        })

    gap_count_by_head = dict(sorted(Counter(row["head"] for row in gap_rows).items()))
    report = {
        "created_at": created_at,
        "local_only": True,
        "source_coverage_rows": len(coverage_rows),
        "source_coverage_report_rows": coverage_report.get("coverage_row_count"),
        "source_coverage_validation_success": coverage_validation.get("success") is True,
        "source_missing_group_count_by_head": coverage_report.get("missing_group_count_by_head"),
        "gap_count": len(gap_rows),
        "gap_count_by_head": gap_count_by_head,
        "gap_jsonl": "datasets/features/feature_coverage_gap_queue.jsonl",
        "training_label_source_rows": sum(1 for row in gap_rows if row.get("training_label_source_rows")),
        "feature_rows_counted_as_labels": 0,
        "training_import_allowed": False,
        "safe_for_training_import": False,
        "safe_for_model_claim": False,
        "release_ready": False,
        "production_execution_allowed": False,
        "policy": (
            "Feature coverage gap queue is local remediation planning only. It keeps all model and release gates "
            "closed and does not create training labels."
        ),
    }

    write_jsonl(OUT_JSONL, gap_rows)
    OUT_REPORT.parent.mkdir(parents=True, exist_ok=True)
    OUT_REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "gap_count": report["gap_count"],
        "gap_count_by_head": report["gap_count_by_head"],
        "training_import_allowed": False,
        "safe_for_model_claim": False,
        "release_ready": False,
        "output": str(OUT_REPORT),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
