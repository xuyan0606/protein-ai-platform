#!/usr/bin/env python3
"""Validate local release explicitly covers the latest model guard reports."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
RELEASE = AI_ROOT / "reports" / "local_release_manifest.json"
DATA_LAKE = AI_ROOT / "reports" / "data_lake_manifest.json"
OUT = AI_ROOT / "reports" / "local_release_guard_coverage_validation_report.json"

REQUIRED_GUARDS = {
    "five_head_training_execution_contract_report": "reports/five_head_training_execution_contract_report.json",
    "five_head_training_execution_contract_validation_report": "reports/five_head_training_execution_contract_validation_report.json",
    "five_head_training_sample_gap_queue_report": "reports/five_head_training_sample_gap_queue_report.json",
    "five_head_training_sample_gap_queue_validation_report": "reports/five_head_training_sample_gap_queue_validation_report.json",
    "model_quality_hard_gate_contract_report": "reports/model_quality_hard_gate_contract_report.json",
    "model_quality_hard_gate_contract_validation_report": "reports/model_quality_hard_gate_contract_validation_report.json",
    "model_artifact_claim_guard_report": "reports/model_artifact_claim_guard_report.json",
    "model_artifact_claim_guard_validation_report": "reports/model_artifact_claim_guard_validation_report.json",
    "execution_receipt_artifact_freshness_validation_report": "reports/execution_receipt_artifact_freshness_validation_report.json",
    "feature_label_boundary_quarantine_report": "reports/feature_label_boundary_quarantine_report.json",
    "tool_lane_evidence_pack_report": "reports/tool_lane_evidence_pack.json",
    "tool_lane_evidence_pack_validation_report": "reports/tool_lane_evidence_pack_validation_report.json",
    "human_target_contract_gap_report": "reports/human_target_contract_gap_report.json",
    "human_target_contract_gap_validation_report": "reports/human_target_contract_gap_validation_report.json",
    "human_target_source_runtime_manifest": "reports/human_target_source_runtime_manifest.json",
    "human_target_source_runtime_manifest_validation_report": "reports/human_target_source_runtime_manifest_validation_report.json",
    "human_target_blocked_source_manifest_index": "reports/human_target_blocked_source_manifest_index.json",
    "human_target_blocked_source_manifest_index_validation_report": "reports/human_target_blocked_source_manifest_index_validation_report.json",
    "human_target_source_unlock_checklist_report": "reports/human_target_source_unlock_checklist_report.json",
    "human_target_source_unlock_checklist_validation_report": "reports/human_target_source_unlock_checklist_validation_report.json",
    "advanced_model_feature_contract_report": "reports/advanced_model_feature_contract_report.json",
    "advanced_model_feature_contract_validation_report": "reports/advanced_model_feature_contract_validation_report.json",
    "validated_feature_index_report": "reports/validated_feature_index_report.json",
    "validated_feature_index_validation_report": "reports/validated_feature_index_validation_report.json",
    "ddg_backend_runtime_receipt_validation_report": "reports/ddg_backend_runtime_receipt_validation_report.json",
    "pyrosetta_physical_smoke_bootstrap_report": "reports/pyrosetta_physical_smoke_bootstrap_report.json",
    "rosetta_physical_smoke_bootstrap_report": "reports/rosetta_physical_smoke_bootstrap_report.json",
    "ddg_physical_smoke_harness_report": "reports/ddg_physical_smoke_harness_report.json",
    "ddg_physical_smoke_harness_validation_report": "reports/ddg_physical_smoke_harness_validation_report.json",
    "foldx_buildmodel_parser_contract_report": "reports/foldx_buildmodel_parser_contract_report.json",
    "foldx_buildmodel_parser_contract_validation_report": "reports/foldx_buildmodel_parser_contract_validation_report.json",
}

HUMAN_TARGET_VALIDATION_REPORTS = {
    "gap": "reports/human_target_contract_gap_validation_report.json",
    "runtime": "reports/human_target_source_runtime_manifest_validation_report.json",
    "blocked_source_index": "reports/human_target_blocked_source_manifest_index_validation_report.json",
    "unlock_checklist": "reports/human_target_source_unlock_checklist_validation_report.json",
}


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def fail_if(condition: bool, failures: list[dict[str, Any]], check: str, observed: Any, expected: Any) -> None:
    if condition:
        failures.append({"check": check, "observed": observed, "expected": expected})


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate local release guard coverage")
    parser.add_argument("--release", type=Path, default=RELEASE)
    parser.add_argument("--data-lake", type=Path, default=DATA_LAKE)
    parser.add_argument("--human-target-gap-validation", type=Path, default=AI_ROOT / HUMAN_TARGET_VALIDATION_REPORTS["gap"])
    parser.add_argument("--human-target-runtime-validation", type=Path, default=AI_ROOT / HUMAN_TARGET_VALIDATION_REPORTS["runtime"])
    parser.add_argument("--human-target-blocked-index-validation", type=Path, default=AI_ROOT / HUMAN_TARGET_VALIDATION_REPORTS["blocked_source_index"])
    parser.add_argument("--human-target-unlock-validation", type=Path, default=AI_ROOT / HUMAN_TARGET_VALIDATION_REPORTS["unlock_checklist"])
    parser.add_argument("--output", type=Path, default=OUT)
    args = parser.parse_args()

    release = load_json(args.release)
    data_lake = load_json(args.data_lake)
    summary = release.get("readiness_summary") or {}
    artifact_by_path = {
        artifact.get("path"): artifact
        for artifact in data_lake.get("artifacts") or []
        if artifact.get("path")
    }
    failures: list[dict[str, Any]] = []
    checked: list[dict[str, Any]] = []
    human_target_validations = {
        "gap": load_json(args.human_target_gap_validation),
        "runtime": load_json(args.human_target_runtime_validation),
        "blocked_source_index": load_json(args.human_target_blocked_index_validation),
        "unlock_checklist": load_json(args.human_target_unlock_validation),
    }

    for key, rel in sorted(REQUIRED_GUARDS.items()):
        observed = release.get(key)
        artifact = artifact_by_path.get(rel)
        report = load_json(AI_ROOT / rel)
        checked.append({
            "manifest_key": key,
            "path": rel,
            "release_link_present": observed == rel,
            "data_lake_artifact_present": bool(artifact),
            "data_lake_artifact_exists": bool(artifact and artifact.get("exists")),
            "report_present": bool(report),
        })
        fail_if(observed != rel, failures, "release_link_present", {"key": key, "observed": observed}, rel)
        fail_if(not report, failures, "guard_report_exists", rel, "existing JSON report")
        fail_if(not artifact, failures, "data_lake_artifact_present", rel, "artifact in data lake")
        if artifact and artifact.get("exists") is not True:
            fail_if(True, failures, "data_lake_artifact_exists", {"key": key, "observed": artifact.get("exists")}, True)

    for field in (
        "five_head_training_execution_validation_success",
        "five_head_training_sample_gap_queue_validation_success",
        "model_quality_hard_gate_validation_success",
        "model_artifact_claim_guard_validation_success",
        "ddg_physical_smoke_harness_validation_success",
        "foldx_buildmodel_parser_validation_success",
        "tool_lane_evidence_validation_success",
        "human_target_gap_validation_success",
        "human_target_source_runtime_validation_success",
        "human_target_blocked_source_index_validation_success",
        "human_target_source_unlock_checklist_validation_success",
    ):
        fail_if(summary.get(field) is not True, failures, f"release_summary_{field}_true", summary.get(field), True)
    fail_if(
        int(summary.get("human_target_gap_sections") or 0) != 2,
        failures,
        "release_summary_human_target_gap_sections_two",
        summary.get("human_target_gap_sections"),
        2,
    )
    fail_if(
        human_target_validations["gap"].get("report_matches_current_builder_projection") is not True,
        failures,
        "human_target_gap_projection_valid",
        human_target_validations["gap"].get("report_matches_current_builder_projection"),
        True,
    )
    fail_if(
        summary.get("human_target_gap_sections") != human_target_validations["gap"].get("human_target_gap_sections"),
        failures,
        "release_summary_human_target_gap_sections_match_validation",
        summary.get("human_target_gap_sections"),
        human_target_validations["gap"].get("human_target_gap_sections"),
    )
    fail_if(
        int(summary.get("human_target_source_runtime_ready_sources") or 0) != 0,
        failures,
        "release_summary_human_target_runtime_ready_sources_zero",
        summary.get("human_target_source_runtime_ready_sources"),
        0,
    )
    fail_if(
        human_target_validations["runtime"].get("manifest_matches_current_builder_projection") is not True,
        failures,
        "human_target_runtime_manifest_projection_valid",
        human_target_validations["runtime"].get("manifest_matches_current_builder_projection"),
        True,
    )
    fail_if(
        human_target_validations["runtime"].get("receipts_match_current_builder_projection") is not True,
        failures,
        "human_target_runtime_receipts_projection_valid",
        human_target_validations["runtime"].get("receipts_match_current_builder_projection"),
        True,
    )
    fail_if(
        summary.get("human_target_source_runtime_total_sources") != human_target_validations["runtime"].get("sources"),
        failures,
        "release_summary_human_target_runtime_total_sources_match_validation",
        summary.get("human_target_source_runtime_total_sources"),
        human_target_validations["runtime"].get("sources"),
    )
    fail_if(
        int(summary.get("human_target_blocked_source_split_count") or 0) != 7,
        failures,
        "release_summary_human_target_blocked_source_split_count_seven",
        summary.get("human_target_blocked_source_split_count"),
        7,
    )
    fail_if(
        human_target_validations["blocked_source_index"].get("index_matches_current_builder_projection") is not True,
        failures,
        "human_target_blocked_source_index_projection_valid",
        human_target_validations["blocked_source_index"].get("index_matches_current_builder_projection"),
        True,
    )
    fail_if(
        human_target_validations["blocked_source_index"].get("split_manifests_match_current_builder_projection") is not True,
        failures,
        "human_target_blocked_split_manifests_projection_valid",
        human_target_validations["blocked_source_index"].get("split_manifests_match_current_builder_projection"),
        True,
    )
    fail_if(
        summary.get("human_target_blocked_source_split_count") != human_target_validations["blocked_source_index"].get("split_count"),
        failures,
        "release_summary_human_target_blocked_source_split_count_match_validation",
        summary.get("human_target_blocked_source_split_count"),
        human_target_validations["blocked_source_index"].get("split_count"),
    )
    fail_if(
        int(summary.get("human_target_source_unlock_ready_rows") or 0) != 0,
        failures,
        "release_summary_human_target_source_unlock_ready_rows_zero",
        summary.get("human_target_source_unlock_ready_rows"),
        0,
    )
    fail_if(
        human_target_validations["unlock_checklist"].get("checklist_matches_current_builder_projection") is not True,
        failures,
        "human_target_unlock_checklist_projection_valid",
        human_target_validations["unlock_checklist"].get("checklist_matches_current_builder_projection"),
        True,
    )
    fail_if(
        human_target_validations["unlock_checklist"].get("report_matches_current_builder_projection") is not True,
        failures,
        "human_target_unlock_report_projection_valid",
        human_target_validations["unlock_checklist"].get("report_matches_current_builder_projection"),
        True,
    )
    fail_if(
        summary.get("human_target_source_unlock_checklist_rows") != human_target_validations["unlock_checklist"].get("checklist_rows"),
        failures,
        "release_summary_human_target_unlock_rows_match_validation",
        summary.get("human_target_source_unlock_checklist_rows"),
        human_target_validations["unlock_checklist"].get("checklist_rows"),
    )
    fail_if(
        summary.get("human_target_source_unlock_ready_rows") != human_target_validations["unlock_checklist"].get("ready_to_unlock_rows"),
        failures,
        "release_summary_human_target_unlock_ready_rows_match_validation",
        summary.get("human_target_source_unlock_ready_rows"),
        human_target_validations["unlock_checklist"].get("ready_to_unlock_rows"),
    )
    fail_if(
        int(summary.get("tool_lane_evidence_ready_lanes") or 0) != 0,
        failures,
        "release_summary_tool_lane_evidence_ready_lanes_zero",
        summary.get("tool_lane_evidence_ready_lanes"),
        0,
    )
    fail_if(
        summary.get("foldx_buildmodel_parser_runtime_ready") is not False,
        failures,
        "release_summary_foldx_parser_runtime_ready_false",
        summary.get("foldx_buildmodel_parser_runtime_ready"),
        False,
    )
    fail_if(
        int(summary.get("ddg_backend_runtime_approved_rows") or 0) < 1,
        failures,
        "release_summary_ddg_backend_runtime_approved_rows_positive",
        summary.get("ddg_backend_runtime_approved_rows"),
        ">=1",
    )
    fail_if(
        summary.get("pyrosetta_physical_smoke_passed") is not True,
        failures,
        "release_summary_pyrosetta_physical_smoke_passed_true",
        summary.get("pyrosetta_physical_smoke_passed"),
        True,
    )
    fail_if(
        int(summary.get("pyrosetta_physical_smoke_artifact_count") or 0) < 5,
        failures,
        "release_summary_pyrosetta_physical_smoke_artifact_count_complete",
        summary.get("pyrosetta_physical_smoke_artifact_count"),
        ">=5",
    )
    fail_if(
        summary.get("rosetta_physical_smoke_passed") is not True,
        failures,
        "release_summary_rosetta_physical_smoke_passed_true",
        summary.get("rosetta_physical_smoke_passed"),
        True,
    )
    fail_if(
        summary.get("rosetta_physical_smoke_constant_seed") is not True,
        failures,
        "release_summary_rosetta_physical_smoke_constant_seed_true",
        summary.get("rosetta_physical_smoke_constant_seed"),
        True,
    )
    fail_if(
        int(summary.get("rosetta_physical_smoke_artifact_count") or 0) < 5,
        failures,
        "release_summary_rosetta_physical_smoke_artifact_count_complete",
        summary.get("rosetta_physical_smoke_artifact_count"),
        ">=5",
    )

    fail_if(release.get("release_ready") is not False, failures, "release_ready_false", release.get("release_ready"), False)
    fail_if(release.get("local_only") is not True, failures, "local_only_true", release.get("local_only"), True)
    fail_if(summary.get("five_head_training_execution_allowed") is not False, failures, "five_head_training_execution_allowed_false", summary.get("five_head_training_execution_allowed"), False)
    fail_if(
        summary.get("five_head_training_sample_gap_queue_validation_success") is not True,
        failures,
        "five_head_training_sample_gap_queue_validation_success_true",
        summary.get("five_head_training_sample_gap_queue_validation_success"),
        True,
    )
    fail_if(summary.get("model_quality_hard_gate_safe_for_model_claim") is not False, failures, "model_quality_hard_gate_safe_for_model_claim_false", summary.get("model_quality_hard_gate_safe_for_model_claim"), False)
    fail_if(summary.get("model_artifact_claim_guard_safe_for_model_claim") is not False, failures, "model_artifact_claim_guard_safe_for_model_claim_false", summary.get("model_artifact_claim_guard_safe_for_model_claim"), False)

    report = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "local_only": True,
        "success": not failures,
        "guard_coverage_count": len(REQUIRED_GUARDS),
        "checked_guards": checked,
        "human_target_projection_checks": {
            "gap_report_matches_current_builder_projection": human_target_validations["gap"].get("report_matches_current_builder_projection") is True,
            "runtime_manifest_matches_current_builder_projection": human_target_validations["runtime"].get("manifest_matches_current_builder_projection") is True,
            "runtime_receipts_match_current_builder_projection": human_target_validations["runtime"].get("receipts_match_current_builder_projection") is True,
            "blocked_source_index_matches_current_builder_projection": human_target_validations["blocked_source_index"].get("index_matches_current_builder_projection") is True,
            "blocked_split_manifests_match_current_builder_projection": human_target_validations["blocked_source_index"].get("split_manifests_match_current_builder_projection") is True,
            "unlock_checklist_matches_current_builder_projection": human_target_validations["unlock_checklist"].get("checklist_matches_current_builder_projection") is True,
            "unlock_report_matches_current_builder_projection": human_target_validations["unlock_checklist"].get("report_matches_current_builder_projection") is True,
        },
        "failures": failures,
        "safe_for_training_pipeline": not failures,
        "safe_for_model_claim": False,
        "release_ready": False,
        "policy": "Local release must explicitly cover the current model guard set, but this does not make it production-ready.",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "success": report["success"],
        "guard_coverage_count": report["guard_coverage_count"],
        "failures": len(failures),
        "safe_for_model_claim": False,
        "output": str(args.output),
    }, ensure_ascii=False))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
