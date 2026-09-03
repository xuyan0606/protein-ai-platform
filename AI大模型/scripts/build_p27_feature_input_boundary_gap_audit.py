#!/usr/bin/env python3
"""Build a source-bound audit of P27 input-feature boundary gaps."""

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
OUT_JSONL = AI_ROOT / "datasets" / "features" / "p27_feature_input_boundary_gap_audit.jsonl"
OUT_REPORT = AI_ROOT / "reports" / "p27_feature_input_boundary_gap_audit_report.json"


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    value = json.loads(path.read_text(encoding="utf-8"))
    return value if isinstance(value, dict) else {}


def base(audit_id: str, gap_type: str, source_report: str, source_state: dict[str, Any], blocker: str) -> dict[str, Any]:
    return {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "local_only": True,
        "audit_id": audit_id,
        "gap_type": gap_type,
        "source_report": source_report,
        "source_state": source_state,
        "blocker": blocker,
        "input_feature_only": True,
        "training_label_source": False,
        "training_import_allowed": False,
        "safe_for_training_import": False,
        "safe_for_model_claim": False,
        "release_ready": False,
        "production_execution_allowed": False,
        "policy": "P27 input-feature boundary audit only; feature rows are model inputs, not labels, training import approval, model claims, release approval, or production authorization.",
    }


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


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
    advanced_contract = advanced.get("feature_index_contract") if isinstance(advanced.get("feature_index_contract"), dict) else {}
    advanced_validation_contract = advanced_validation.get("feature_contract") if isinstance(advanced_validation.get("feature_contract"), dict) else {}
    structure_boundary = structure.get("model_consumption_contract") if isinstance(structure.get("model_consumption_contract"), dict) else {}
    reviewed_boundary = structure.get("reviewed_chain_graph_boundary") if isinstance(structure.get("reviewed_chain_graph_boundary"), dict) else {}
    coordinate_evidence = structure.get("coordinate_file_parse_evidence") if isinstance(structure.get("coordinate_file_parse_evidence"), dict) else {}
    rows = [
        base(
            "p27-feature-index-boundary",
            "validated_feature_index_input_boundary",
            "reports/validated_feature_index_report.json",
            {
                "feature_rows": feature.get("feature_rows"),
                "model_consumable_rows": feature.get("model_consumable_rows"),
                "training_label_source_rows": feature.get("training_label_source_rows"),
                "family_counts": feature.get("family_counts"),
                "validation_success": feature_validation.get("success"),
            },
            "validated feature index contains input features only and cannot unlock training labels",
        ) | {
            "feature_rows": feature.get("feature_rows"),
            "model_consumable_rows": feature.get("model_consumable_rows"),
            "training_label_source_rows": feature.get("training_label_source_rows"),
        },
        base(
            "p27-feature-coverage-boundary",
            "feature_coverage_input_boundary",
            "reports/feature_coverage_by_head_group_report.json",
            {
                "coverage_row_count": coverage.get("coverage_row_count"),
                "protein_group_count": coverage.get("protein_group_count"),
                "source_feature_rows": coverage.get("source_feature_rows"),
                "source_training_label_source_rows": coverage.get("source_training_label_source_rows"),
                "source_feature_rows_counted_as_labels": coverage.get("source_feature_rows_counted_as_labels"),
                "covered_group_count_by_head": coverage.get("covered_group_count_by_head"),
                "missing_group_count_by_head": coverage.get("missing_group_count_by_head"),
                "validation_success": coverage_validation.get("success"),
            },
            "feature coverage rows describe availability only and do not satisfy supervised head labels",
        ) | {
            "coverage_row_count": coverage.get("coverage_row_count"),
            "protein_group_count": coverage.get("protein_group_count"),
        },
        base(
            "p27-feature-coverage-gap-summary",
            "feature_coverage_gap_remediation_boundary",
            "reports/feature_coverage_gap_queue_report.json",
            {
                "gap_count": gap.get("gap_count"),
                "gap_count_by_head": gap.get("gap_count_by_head"),
                "training_label_source_rows": gap.get("training_label_source_rows"),
                "feature_rows_counted_as_labels": gap.get("feature_rows_counted_as_labels"),
                "validation_success": gap_validation.get("success"),
            },
            "coverage gap queue is remediation planning only and cannot create labels or training rows",
        ) | {
            "gap_count": gap.get("gap_count"),
            "feature_rows_counted_as_labels": gap.get("feature_rows_counted_as_labels"),
        },
        base(
            "p27-advanced-feature-contract-boundary",
            "advanced_model_feature_contract_boundary",
            "reports/advanced_model_feature_contract_report.json",
            {
                "feature_ref_count": advanced_contract.get("feature_ref_count"),
                "advanced_model_ready_feature_ref_count": advanced_contract.get("advanced_model_ready_feature_ref_count"),
                "model_input_only_feature_ref_count": advanced_contract.get("model_input_only_feature_ref_count"),
                "training_label_source_feature_ref_count": advanced_contract.get("training_label_source_feature_ref_count"),
                "optional_physical_ddg_feature_ref_count": advanced_contract.get("optional_physical_ddg_feature_ref_count"),
                "validation_feature_refs": advanced_validation_contract.get("feature_refs"),
                "validation_training_label_source_feature_refs": advanced_validation_contract.get("training_label_source_feature_refs"),
                "validation_success": advanced_validation.get("success"),
            },
            "advanced model feature contract proves feature refs are input-only, not claimable labels",
        ) | {
            "feature_ref_count": advanced_contract.get("feature_ref_count"),
            "model_input_only_feature_ref_count": advanced_contract.get("model_input_only_feature_ref_count"),
            "training_label_source_feature_ref_count": advanced_contract.get("training_label_source_feature_ref_count"),
        },
        base(
            "p27-structure-feature-boundary",
            "structure_graph_input_boundary",
            "reports/structure_feature_model_contract_report.json",
            {
                "coordinate_manifest_rows": coordinate_evidence.get("manifest_rows"),
                "parsed_coordinate_feature_rows": coordinate_evidence.get("parsed_coordinate_feature_rows"),
                "reviewed_graph_index_rows": reviewed_boundary.get("reviewed_graph_index_rows"),
                "formal_chain_mapping_decision_rows": reviewed_boundary.get("formal_chain_mapping_decision_rows"),
                "unreviewed_coordinate_rows_excluded_from_reviewed_graph": structure_boundary.get("unreviewed_coordinate_rows_excluded_from_reviewed_graph"),
                "training_label_source_rows": structure_boundary.get("training_label_source_rows"),
                "model_consumable_role": structure_boundary.get("model_consumable_role"),
                "validation_success": structure_validation.get("success"),
            },
            "reviewed structure graph rows are input features only; unreviewed coordinates stay excluded",
        ) | {
            "reviewed_graph_rows": reviewed_boundary.get("reviewed_graph_index_rows"),
            "unreviewed_coordinate_rows_excluded": structure_boundary.get("unreviewed_coordinate_rows_excluded_from_reviewed_graph"),
        },
        base(
            "p27-feature-input-boundary-summary",
            "p27_feature_input_boundary_summary",
            "reports/five_head_training_execution_contract_report.json",
            {
                "validated_feature_rows": feature.get("feature_rows"),
                "advanced_ready_feature_refs": advanced_contract.get("advanced_model_ready_feature_ref_count"),
                "training_label_source_rows": feature.get("training_label_source_rows"),
                "feature_rows_counted_as_labels": coverage.get("source_feature_rows_counted_as_labels"),
                "five_head_ready_head_count": five_head.get("ready_head_count"),
                "five_head_training_execution_allowed": five_head.get("training_execution_allowed"),
                "feature_input_gate": five_head.get("feature_input_gate"),
            },
            "P27 feature evidence is ready only as model input; P29 training and model-claim gates remain blocked",
        ) | {
            "validated_feature_rows": feature.get("feature_rows"),
            "five_head_ready_head_count": five_head.get("ready_head_count"),
            "training_execution_allowed": False,
        },
    ]
    report = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "local_only": True,
        "audit_rows": len(rows),
        "validated_feature_rows": feature.get("feature_rows"),
        "model_consumable_rows": feature.get("model_consumable_rows"),
        "training_label_source_rows": feature.get("training_label_source_rows"),
        "coverage_rows": coverage.get("coverage_row_count"),
        "protein_group_count": coverage.get("protein_group_count"),
        "coverage_gap_count": gap.get("gap_count"),
        "advanced_feature_refs": advanced_contract.get("feature_ref_count"),
        "advanced_model_input_only_feature_refs": advanced_contract.get("model_input_only_feature_ref_count"),
        "advanced_training_label_source_feature_refs": advanced_contract.get("training_label_source_feature_ref_count"),
        "reviewed_structure_graph_rows": reviewed_boundary.get("reviewed_graph_index_rows"),
        "unreviewed_coordinate_rows_excluded": structure_boundary.get("unreviewed_coordinate_rows_excluded_from_reviewed_graph"),
        "five_head_ready_head_count": five_head.get("ready_head_count"),
        "five_head_training_execution_allowed": five_head.get("training_execution_allowed"),
        "training_import_allowed": False,
        "safe_for_training_import": False,
        "safe_for_model_claim": False,
        "release_ready": False,
        "production_execution_allowed": False,
        "audit_jsonl": "datasets/features/p27_feature_input_boundary_gap_audit.jsonl",
        "policy": "P27 audit only. Feature refs and coverage are model-input-only and cannot be counted as labels, training import, model claims, release, or production execution.",
    }
    write_jsonl(OUT_JSONL, rows)
    OUT_REPORT.parent.mkdir(parents=True, exist_ok=True)
    OUT_REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "audit_rows": report["audit_rows"],
        "validated_feature_rows": report["validated_feature_rows"],
        "training_label_source_rows": report["training_label_source_rows"],
        "coverage_gap_count": report["coverage_gap_count"],
        "safe_for_model_claim": False,
        "output": str(OUT_REPORT),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
