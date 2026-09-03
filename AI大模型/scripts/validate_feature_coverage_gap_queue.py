#!/usr/bin/env python3
"""Validate the fail-closed feature coverage gap queue."""

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
GAP_JSONL = AI_ROOT / "datasets" / "features" / "feature_coverage_gap_queue.jsonl"
GAP_REPORT = AI_ROOT / "reports" / "feature_coverage_gap_queue_report.json"
OUT = AI_ROOT / "reports" / "feature_coverage_gap_queue_validation_report.json"

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
}


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def fail_if(condition: bool, failures: list[dict[str, Any]], check: str, observed: Any, expected: Any) -> None:
    if condition:
        failures.append({"check": check, "observed": observed, "expected": expected})


def required_feature_families(head: str) -> list[str]:
    return sorted(family for family, heads in FEATURE_FAMILY_HEADS.items() if head in heads)


def expected_gap_rows(feature_rows: list[dict[str, Any]], coverage_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    feature_family_counts_by_group: dict[str, Counter[str]] = defaultdict(Counter)
    feature_ids_by_group: dict[str, list[str]] = defaultdict(list)
    for row in feature_rows:
        group_id = f"uniprot:{row.get('uniprot_id') or 'unknown_uniprot'}"
        feature_family_counts_by_group[group_id][str(row.get("feature_family"))] += 1
        if row.get("feature_index_id"):
            feature_ids_by_group[group_id].append(str(row["feature_index_id"]))

    expected_rows = []
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
        expected_rows.append({
            "gap_id": f"feature-coverage-gap::{head}::{group_id}",
            "head": head,
            "protein_group_id": group_id,
            "coverage_status": coverage.get("coverage_status"),
            "input_feature_rows": coverage.get("input_feature_rows"),
            "model_consumable_feature_rows": coverage.get("model_consumable_feature_rows"),
            "training_label_source_rows": coverage.get("training_label_source_rows"),
            "required_input_feature_families_for_head": expected_families,
            "missing_input_feature_families": missing_families,
            "available_feature_family_counts_for_group": available_counts,
            "available_feature_index_ids_for_group": sorted(feature_ids_by_group[group_id]),
        })
    return expected_rows


def main() -> int:
    feature_rows = load_jsonl(FEATURE_INDEX)
    coverage_rows = load_jsonl(COVERAGE_JSONL)
    gap_rows = load_jsonl(GAP_JSONL)
    coverage_report = load_json(COVERAGE_REPORT)
    coverage_validation = load_json(COVERAGE_VALIDATION)
    gap_report = load_json(GAP_REPORT)
    failures: list[dict[str, Any]] = []

    expected_rows = expected_gap_rows(feature_rows, coverage_rows)
    expected_gap_ids = [row["gap_id"] for row in expected_rows]
    observed_gap_ids = [row.get("gap_id") for row in gap_rows]

    fail_if(gap_report.get("source_coverage_rows") != len(coverage_rows), failures, "source_coverage_rows_bound", gap_report.get("source_coverage_rows"), len(coverage_rows))
    fail_if(gap_report.get("source_coverage_report_rows") != coverage_report.get("coverage_row_count"), failures, "source_coverage_report_rows_bound", gap_report.get("source_coverage_report_rows"), coverage_report.get("coverage_row_count"))
    fail_if(gap_report.get("source_coverage_validation_success") is not (coverage_validation.get("success") is True), failures, "source_coverage_validation_success_bound", gap_report.get("source_coverage_validation_success"), coverage_validation.get("success") is True)
    fail_if(gap_report.get("source_missing_group_count_by_head") != coverage_report.get("missing_group_count_by_head"), failures, "source_missing_group_count_by_head_bound", gap_report.get("source_missing_group_count_by_head"), coverage_report.get("missing_group_count_by_head"))
    fail_if(gap_report.get("gap_count") != len(expected_rows), failures, "gap_count_bound", gap_report.get("gap_count"), len(expected_rows))
    fail_if(observed_gap_ids != expected_gap_ids, failures, "gap_ids_exact_order", observed_gap_ids, expected_gap_ids)
    fail_if(gap_report.get("training_label_source_rows") != 0, failures, "report_training_label_source_rows_zero", gap_report.get("training_label_source_rows"), 0)
    fail_if(gap_report.get("feature_rows_counted_as_labels") != 0, failures, "report_feature_rows_counted_as_labels_zero", gap_report.get("feature_rows_counted_as_labels"), 0)

    expected_by_id = {row["gap_id"]: row for row in expected_rows}
    for idx, row in enumerate(gap_rows):
        expected = expected_by_id.get(str(row.get("gap_id")))
        if expected is None:
            continue
        for field in (
            "head",
            "protein_group_id",
            "coverage_status",
            "input_feature_rows",
            "model_consumable_feature_rows",
            "training_label_source_rows",
            "required_input_feature_families_for_head",
            "missing_input_feature_families",
            "available_feature_family_counts_for_group",
            "available_feature_index_ids_for_group",
        ):
            fail_if(row.get(field) != expected[field], failures, f"gap_row_{field}_source_bound", {"index": idx, "gap_id": row.get("gap_id"), "observed": row.get(field)}, expected[field])
        fail_if(row.get("gap_type") != "input_feature_coverage_gap", failures, "gap_type_exact", {"index": idx, "observed": row.get("gap_type")}, "input_feature_coverage_gap")
        fail_if(row.get("training_label_source_rows") != 0, failures, "gap_row_training_label_source_rows_zero", {"index": idx, "observed": row.get("training_label_source_rows")}, 0)
        fail_if(row.get("feature_rows_counted_as_labels") != 0, failures, "gap_row_feature_rows_counted_as_labels_zero", {"index": idx, "observed": row.get("feature_rows_counted_as_labels")}, 0)
        fail_if(not row.get("missing_input_feature_families"), failures, "gap_row_missing_input_feature_families_nonempty", {"index": idx, "observed": row.get("missing_input_feature_families")}, "non-empty list")
        for field in (
            "training_import_allowed",
            "safe_for_training_import",
            "safe_for_model_claim",
            "release_ready",
            "production_execution_allowed",
        ):
            fail_if(row.get(field) is not False, failures, f"gap_row_{field}_false", {"index": idx, "observed": row.get(field)}, False)

    expected_gap_count_by_head = dict(sorted(Counter(row["head"] for row in expected_rows).items()))
    fail_if(gap_report.get("gap_count_by_head") != expected_gap_count_by_head, failures, "gap_count_by_head_bound", gap_report.get("gap_count_by_head"), expected_gap_count_by_head)
    for field in (
        "training_import_allowed",
        "safe_for_training_import",
        "safe_for_model_claim",
        "release_ready",
        "production_execution_allowed",
    ):
        fail_if(gap_report.get(field) is not False, failures, f"report_{field}_false", gap_report.get(field), False)

    validation = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "local_only": True,
        "success": not failures,
        "gap_count": len(gap_rows),
        "expected_gap_count": len(expected_rows),
        "gap_count_by_head": expected_gap_count_by_head,
        "failures": failures,
        "training_import_allowed": False,
        "safe_for_training_import": False,
        "safe_for_model_claim": False,
        "release_ready": False,
        "production_execution_allowed": False,
        "policy": "Validation only. Coverage gaps are remediation planning rows and do not authorize training, claims, release, or production.",
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(validation, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "success": validation["success"],
        "gap_count": validation["gap_count"],
        "expected_gap_count": validation["expected_gap_count"],
        "gap_count_by_head": validation["gap_count_by_head"],
        "failures": len(failures),
        "safe_for_model_claim": False,
        "release_ready": False,
        "output": str(OUT),
    }, ensure_ascii=False))
    return 0 if validation["success"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
