#!/usr/bin/env python3
"""Validate the P27 input-feature boundary gap audit."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
FEATURE_REPORT = AI_ROOT / "reports" / "validated_feature_index_report.json"
FEATURE_VALIDATION = AI_ROOT / "reports" / "validated_feature_index_validation_report.json"
COVERAGE_REPORT = AI_ROOT / "reports" / "feature_coverage_by_head_group_report.json"
COVERAGE_VALIDATION = AI_ROOT / "reports" / "feature_coverage_by_head_group_validation_report.json"
GAP_REPORT = AI_ROOT / "reports" / "feature_coverage_gap_queue_report.json"
GAP_VALIDATION = AI_ROOT / "reports" / "feature_coverage_gap_queue_validation_report.json"
ADVANCED_REPORT = AI_ROOT / "reports" / "advanced_model_feature_contract_report.json"
ADVANCED_VALIDATION = AI_ROOT / "reports" / "advanced_model_feature_contract_validation_report.json"
STRUCTURE_REPORT = AI_ROOT / "reports" / "structure_feature_model_contract_report.json"
STRUCTURE_VALIDATION = AI_ROOT / "reports" / "structure_feature_model_contract_validation_report.json"
FIVE_HEAD = AI_ROOT / "reports" / "five_head_training_execution_contract_report.json"
AUDIT = AI_ROOT / "datasets" / "features" / "p27_feature_input_boundary_gap_audit.jsonl"
REPORT = AI_ROOT / "reports" / "p27_feature_input_boundary_gap_audit_report.json"
OUT = AI_ROOT / "reports" / "p27_feature_input_boundary_gap_audit_validation_report.json"


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    value = json.loads(path.read_text(encoding="utf-8"))
    return value if isinstance(value, dict) else {}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def fail_if(condition: bool, failures: list[dict[str, Any]], check: str, observed: Any, expected: Any) -> None:
    if condition:
        failures.append({"check": check, "observed": observed, "expected": expected})


def main() -> int:
    feature = load_json(FEATURE_REPORT)
    feature_validation = load_json(FEATURE_VALIDATION)
    coverage = load_json(COVERAGE_REPORT)
    coverage_validation = load_json(COVERAGE_VALIDATION)
    gap = load_json(GAP_REPORT)
    gap_validation = load_json(GAP_VALIDATION)
    advanced = load_json(ADVANCED_REPORT)
    advanced_validation = load_json(ADVANCED_VALIDATION)
    structure = load_json(STRUCTURE_REPORT)
    structure_validation = load_json(STRUCTURE_VALIDATION)
    five_head = load_json(FIVE_HEAD)
    audit_rows = load_jsonl(AUDIT)
    report = load_json(REPORT)
    advanced_contract = advanced.get("feature_index_contract") if isinstance(advanced.get("feature_index_contract"), dict) else {}
    structure_boundary = structure.get("model_consumption_contract") if isinstance(structure.get("model_consumption_contract"), dict) else {}
    reviewed_boundary = structure.get("reviewed_chain_graph_boundary") if isinstance(structure.get("reviewed_chain_graph_boundary"), dict) else {}
    failures: list[dict[str, Any]] = []

    fail_if(len(audit_rows) != 6, failures, "audit_rows_six", len(audit_rows), 6)
    fail_if(report.get("audit_rows") != 6, failures, "report_audit_rows_six", report.get("audit_rows"), 6)
    fail_if(feature_validation.get("success") is not True, failures, "feature_validation_success_true", feature_validation.get("success"), True)
    fail_if(coverage_validation.get("success") is not True, failures, "coverage_validation_success_true", coverage_validation.get("success"), True)
    fail_if(gap_validation.get("success") is not True, failures, "gap_validation_success_true", gap_validation.get("success"), True)
    fail_if(advanced_validation.get("success") is not True, failures, "advanced_validation_success_true", advanced_validation.get("success"), True)
    fail_if(structure_validation.get("success") is not True, failures, "structure_validation_success_true", structure_validation.get("success"), True)
    fail_if(report.get("validated_feature_rows") != feature.get("feature_rows"), failures, "validated_feature_rows_bound", report.get("validated_feature_rows"), feature.get("feature_rows"))
    fail_if(report.get("model_consumable_rows") != feature.get("model_consumable_rows"), failures, "model_consumable_rows_bound", report.get("model_consumable_rows"), feature.get("model_consumable_rows"))
    fail_if(report.get("training_label_source_rows") != 0, failures, "training_label_source_rows_zero", report.get("training_label_source_rows"), 0)
    fail_if(feature.get("training_label_source_rows") != 0, failures, "source_training_label_source_rows_zero", feature.get("training_label_source_rows"), 0)
    fail_if(report.get("coverage_rows") != coverage.get("coverage_row_count"), failures, "coverage_rows_bound", report.get("coverage_rows"), coverage.get("coverage_row_count"))
    fail_if(report.get("protein_group_count") != coverage.get("protein_group_count"), failures, "protein_group_count_bound", report.get("protein_group_count"), coverage.get("protein_group_count"))
    fail_if(report.get("coverage_gap_count") != gap.get("gap_count"), failures, "coverage_gap_count_bound", report.get("coverage_gap_count"), gap.get("gap_count"))
    fail_if(report.get("advanced_feature_refs") != advanced_contract.get("feature_ref_count"), failures, "advanced_feature_refs_bound", report.get("advanced_feature_refs"), advanced_contract.get("feature_ref_count"))
    fail_if(report.get("advanced_model_input_only_feature_refs") != advanced_contract.get("model_input_only_feature_ref_count"), failures, "advanced_model_input_only_feature_refs_bound", report.get("advanced_model_input_only_feature_refs"), advanced_contract.get("model_input_only_feature_ref_count"))
    fail_if(report.get("advanced_training_label_source_feature_refs") != 0, failures, "advanced_training_label_source_feature_refs_zero", report.get("advanced_training_label_source_feature_refs"), 0)
    fail_if(advanced_contract.get("training_label_source_feature_ref_count") != 0, failures, "source_advanced_training_label_source_feature_refs_zero", advanced_contract.get("training_label_source_feature_ref_count"), 0)
    fail_if(report.get("reviewed_structure_graph_rows") != reviewed_boundary.get("reviewed_graph_index_rows"), failures, "reviewed_structure_graph_rows_bound", report.get("reviewed_structure_graph_rows"), reviewed_boundary.get("reviewed_graph_index_rows"))
    fail_if(report.get("unreviewed_coordinate_rows_excluded") != structure_boundary.get("unreviewed_coordinate_rows_excluded_from_reviewed_graph"), failures, "unreviewed_coordinate_rows_excluded_bound", report.get("unreviewed_coordinate_rows_excluded"), structure_boundary.get("unreviewed_coordinate_rows_excluded_from_reviewed_graph"))
    fail_if(report.get("five_head_ready_head_count") != five_head.get("ready_head_count"), failures, "five_head_ready_head_count_bound", report.get("five_head_ready_head_count"), five_head.get("ready_head_count"))
    fail_if(report.get("five_head_training_execution_allowed") is not False, failures, "five_head_training_execution_allowed_false", report.get("five_head_training_execution_allowed"), False)

    allowed_types = {
        "validated_feature_index_input_boundary",
        "feature_coverage_input_boundary",
        "feature_coverage_gap_remediation_boundary",
        "advanced_model_feature_contract_boundary",
        "structure_graph_input_boundary",
        "p27_feature_input_boundary_summary",
    }
    seen = []
    for idx, row in enumerate(audit_rows):
        seen.append(row.get("gap_type"))
        fail_if(row.get("gap_type") not in allowed_types, failures, "gap_type_allowed", {"index": idx, "observed": row.get("gap_type")}, sorted(allowed_types))
        fail_if(row.get("input_feature_only") is not True, failures, "row_input_feature_only_true", {"index": idx, "observed": row.get("input_feature_only")}, True)
        fail_if(row.get("training_label_source") is not False, failures, "row_training_label_source_false", {"index": idx, "observed": row.get("training_label_source")}, False)
        for field in ("training_import_allowed", "safe_for_training_import", "safe_for_model_claim", "release_ready", "production_execution_allowed"):
            fail_if(row.get(field) is not False, failures, f"row_{field}_false", {"index": idx, "observed": row.get(field)}, False)
    for gap_type in allowed_types:
        fail_if(seen.count(gap_type) != 1, failures, f"{gap_type}_one_row", seen.count(gap_type), 1)

    for field in ("training_import_allowed", "safe_for_training_import", "safe_for_model_claim", "release_ready", "production_execution_allowed"):
        fail_if(report.get(field) is not False, failures, f"report_{field}_false", report.get(field), False)

    validation = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "local_only": True,
        "success": not failures,
        "audit_rows": len(audit_rows),
        "validated_feature_rows": feature.get("feature_rows"),
        "model_consumable_rows": feature.get("model_consumable_rows"),
        "training_label_source_rows": feature.get("training_label_source_rows"),
        "coverage_rows": coverage.get("coverage_row_count"),
        "coverage_gap_count": gap.get("gap_count"),
        "advanced_feature_refs": advanced_contract.get("feature_ref_count"),
        "reviewed_structure_graph_rows": reviewed_boundary.get("reviewed_graph_index_rows"),
        "unreviewed_coordinate_rows_excluded": structure_boundary.get("unreviewed_coordinate_rows_excluded_from_reviewed_graph"),
        "failures": failures,
        "training_import_allowed": False,
        "safe_for_training_import": False,
        "safe_for_model_claim": False,
        "release_ready": False,
        "production_execution_allowed": False,
        "policy": "Validation only. P27 feature rows remain input-only and cannot authorize training labels, model claims, release, or production execution.",
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(validation, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "success": validation["success"],
        "audit_rows": validation["audit_rows"],
        "validated_feature_rows": validation["validated_feature_rows"],
        "training_label_source_rows": validation["training_label_source_rows"],
        "failures": len(failures),
        "output": str(OUT),
    }, ensure_ascii=False))
    return 0 if validation["success"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
