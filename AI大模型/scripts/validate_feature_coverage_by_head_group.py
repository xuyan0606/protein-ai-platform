#!/usr/bin/env python3
"""Validate feature coverage by five-head target and protein group."""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
FEATURE_INDEX = AI_ROOT / "datasets" / "features" / "validated_feature_index.jsonl"
FEATURE_REPORT = AI_ROOT / "reports" / "validated_feature_index_report.json"
FEATURE_VALIDATION = AI_ROOT / "reports" / "validated_feature_index_validation_report.json"
COVERAGE_JSONL = AI_ROOT / "datasets" / "features" / "feature_coverage_by_head_group.jsonl"
COVERAGE_REPORT = AI_ROOT / "reports" / "feature_coverage_by_head_group_report.json"
OUT = AI_ROOT / "reports" / "feature_coverage_by_head_group_validation_report.json"

EXPECTED_HEADS = [
    "mutation_rank",
    "stability",
    "activity_risk",
    "substrate_fit",
    "assay_success",
]

FEATURE_FAMILY_HEADS = {
    "msa_conservation": EXPECTED_HEADS,
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


def fail_if(condition: bool, failures: list[dict[str, Any]], check: str, observed: Any, expected: Any) -> None:
    if condition:
        failures.append({"check": check, "observed": observed, "expected": expected})


def protein_group_id(uniprot_id: Any) -> str:
    value = str(uniprot_id or "unknown_uniprot")
    return f"uniprot:{value}"


def expected_coverage_rows(feature_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    groups = sorted({protein_group_id(row.get("uniprot_id")) for row in feature_rows})
    features_by_group: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in feature_rows:
        features_by_group[protein_group_id(row.get("uniprot_id"))].append(row)

    expected_rows = []
    for head in EXPECTED_HEADS:
        for group_id in groups:
            supported = [
                row for row in features_by_group[group_id]
                if head in FEATURE_FAMILY_HEADS.get(str(row.get("feature_family")), [])
            ]
            expected_rows.append({
                "head": head,
                "protein_group_id": group_id,
                "input_feature_rows": len(supported),
                "model_consumable_feature_rows": sum(
                    1 for row in supported if row.get("model_consumable") is True
                ),
                "training_label_source_rows": sum(
                    1 for row in supported if row.get("training_label_source") is True
                ),
                "feature_family_counts": dict(sorted(Counter(str(row.get("feature_family")) for row in supported).items())),
                "feature_index_ids": sorted(
                    str(row.get("feature_index_id")) for row in supported if row.get("feature_index_id")
                ),
                "coverage_status": "has_input_feature_coverage" if supported else "no_input_feature_coverage",
            })
    return expected_rows


def main() -> int:
    feature_rows = load_jsonl(FEATURE_INDEX)
    coverage_rows = load_jsonl(COVERAGE_JSONL)
    report = load_json(COVERAGE_REPORT)
    feature_report = load_json(FEATURE_REPORT)
    feature_validation = load_json(FEATURE_VALIDATION)
    failures: list[dict[str, Any]] = []

    expected_rows = expected_coverage_rows(feature_rows)
    expected_keys = [(row["head"], row["protein_group_id"]) for row in expected_rows]
    observed_keys = [(row.get("head"), row.get("protein_group_id")) for row in coverage_rows]

    fail_if(report.get("expected_heads") != EXPECTED_HEADS, failures, "expected_heads_exact", report.get("expected_heads"), EXPECTED_HEADS)
    fail_if(report.get("feature_family_head_mapping") != FEATURE_FAMILY_HEADS, failures, "feature_family_head_mapping_exact", report.get("feature_family_head_mapping"), FEATURE_FAMILY_HEADS)
    fail_if(report.get("source_feature_rows") != len(feature_rows), failures, "source_feature_rows_match", report.get("source_feature_rows"), len(feature_rows))
    fail_if(report.get("source_feature_report_rows") != feature_report.get("feature_rows"), failures, "source_feature_report_rows_bound", report.get("source_feature_report_rows"), feature_report.get("feature_rows"))
    fail_if(report.get("source_feature_validation_success") is not (feature_validation.get("success") is True), failures, "source_feature_validation_success_bound", report.get("source_feature_validation_success"), feature_validation.get("success") is True)
    fail_if(report.get("source_training_label_source_rows") != 0, failures, "source_training_label_source_rows_zero", report.get("source_training_label_source_rows"), 0)
    fail_if(report.get("source_feature_rows_counted_as_labels") != 0, failures, "source_feature_rows_counted_as_labels_zero", report.get("source_feature_rows_counted_as_labels"), 0)
    fail_if(report.get("protein_group_count") != len({protein_group_id(row.get("uniprot_id")) for row in feature_rows}), failures, "protein_group_count_match", report.get("protein_group_count"), len({protein_group_id(row.get("uniprot_id")) for row in feature_rows}))
    fail_if(report.get("coverage_row_count") != len(expected_rows), failures, "coverage_row_count_match", report.get("coverage_row_count"), len(expected_rows))
    fail_if(observed_keys != expected_keys, failures, "coverage_rows_exact_head_group_order", observed_keys, expected_keys)

    expected_by_key = {(row["head"], row["protein_group_id"]): row for row in expected_rows}
    for idx, row in enumerate(coverage_rows):
        key = (row.get("head"), row.get("protein_group_id"))
        expected = expected_by_key.get(key)
        if expected is None:
            continue
        for field in (
            "input_feature_rows",
            "model_consumable_feature_rows",
            "training_label_source_rows",
            "feature_family_counts",
            "feature_index_ids",
            "coverage_status",
        ):
            fail_if(row.get(field) != expected[field], failures, f"coverage_row_{field}_source_bound", {"index": idx, "key": key, "observed": row.get(field)}, expected[field])
        fail_if(row.get("training_label_source_rows") != 0, failures, "coverage_row_training_label_source_rows_zero", {"index": idx, "key": key, "observed": row.get("training_label_source_rows")}, 0)
        fail_if(row.get("feature_rows_counted_as_labels") != 0, failures, "coverage_row_feature_rows_counted_as_labels_zero", {"index": idx, "key": key, "observed": row.get("feature_rows_counted_as_labels")}, 0)
        fail_if(row.get("input_only") is not True, failures, "coverage_row_input_only_true", {"index": idx, "key": key, "observed": row.get("input_only")}, True)
        for field in (
            "training_import_allowed",
            "safe_for_model_claim",
            "release_ready",
            "production_execution_allowed",
        ):
            fail_if(row.get(field) is not False, failures, f"coverage_row_{field}_false", {"index": idx, "key": key, "observed": row.get(field)}, False)

    expected_covered_by_head = {
        head: sum(1 for row in expected_rows if row["head"] == head and row["coverage_status"] == "has_input_feature_coverage")
        for head in EXPECTED_HEADS
    }
    expected_missing_by_head = {
        head: sum(1 for row in expected_rows if row["head"] == head and row["coverage_status"] == "no_input_feature_coverage")
        for head in EXPECTED_HEADS
    }
    expected_input_rows_by_head = {
        head: sum(row["input_feature_rows"] for row in expected_rows if row["head"] == head)
        for head in EXPECTED_HEADS
    }
    fail_if(report.get("covered_group_count_by_head") != expected_covered_by_head, failures, "covered_group_count_by_head_bound", report.get("covered_group_count_by_head"), expected_covered_by_head)
    fail_if(report.get("missing_group_count_by_head") != expected_missing_by_head, failures, "missing_group_count_by_head_bound", report.get("missing_group_count_by_head"), expected_missing_by_head)
    fail_if(report.get("input_feature_rows_by_head") != expected_input_rows_by_head, failures, "input_feature_rows_by_head_bound", report.get("input_feature_rows_by_head"), expected_input_rows_by_head)

    for field in (
        "training_import_allowed",
        "safe_for_training_import",
        "safe_for_model_claim",
        "release_ready",
        "production_execution_allowed",
    ):
        fail_if(report.get(field) is not False, failures, f"report_{field}_false", report.get(field), False)

    validation = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "local_only": True,
        "success": not failures,
        "feature_rows": len(feature_rows),
        "coverage_rows": len(coverage_rows),
        "protein_group_count": len({protein_group_id(row.get("uniprot_id")) for row in feature_rows}),
        "expected_heads": EXPECTED_HEADS,
        "failures": failures,
        "training_import_allowed": False,
        "safe_for_training_import": False,
        "safe_for_model_claim": False,
        "release_ready": False,
        "production_execution_allowed": False,
        "policy": "Validation only. Feature coverage remains input-only and cannot authorize labels, training, claims, release, or production execution.",
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(validation, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "success": validation["success"],
        "feature_rows": validation["feature_rows"],
        "coverage_rows": validation["coverage_rows"],
        "protein_group_count": validation["protein_group_count"],
        "failures": len(failures),
        "safe_for_model_claim": False,
        "release_ready": False,
        "output": str(OUT),
    }, ensure_ascii=False))
    return 0 if validation["success"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
