#!/usr/bin/env python3
"""Validate the master readiness board is source-bound and fail-closed."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
BOARD = AI_ROOT / "reports" / "master_readiness_board.json"
OUT = AI_ROOT / "reports" / "master_readiness_board_validation_report.json"
LOCAL_RELEASE = AI_ROOT / "reports" / "local_release_manifest.json"
EXPECTED_STREAMS = (
    "numbering_curation",
    "structure_cache",
    "domain_intervals",
    "msa_conservation",
    "kwb_experiment_feedback",
    "model_training",
    "governance_release",
    "platform_integration",
)
EXPECTED_ORDER = (
    "numbering_curation",
    "structure_cache",
    "domain_intervals",
    "kwb_experiment_feedback",
    "msa_conservation",
    "model_training",
    "governance_release",
    "platform_integration",
)


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return value if isinstance(value, dict) else {}


def fail_if(condition: bool, failures: list[dict[str, Any]], check: str, observed: Any, expected: Any) -> None:
    if condition:
        failures.append({"check": check, "observed": observed, "expected": expected})


def as_int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def stream_map(board: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        row.get("stream"): row
        for row in (board.get("streams") or [])
        if isinstance(row, dict)
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate master readiness board")
    parser.add_argument("--board", type=Path, default=BOARD)
    parser.add_argument("--local-release", type=Path, default=LOCAL_RELEASE)
    parser.add_argument("--output", type=Path, default=OUT)
    args = parser.parse_args()

    board = load_json(args.board)
    readiness = load_json(AI_ROOT / "reports" / "training_readiness_report.json")
    safe_entry = load_json(AI_ROOT / "reports" / "safe_training_entrypoint_check.json")
    multitask = load_json(AI_ROOT / "reports" / "multitask_training_readiness_report.json")
    active_learning = load_json(AI_ROOT / "reports" / "active_learning_trial_readiness_report.json")
    head_status = load_json(AI_ROOT / "reports" / "head_model_card_status_report.json")
    benchmark_plan = load_json(AI_ROOT / "reports" / "benchmark_acquisition_plan_report.json")
    governance = load_json(AI_ROOT / "reports" / "governance_readiness_report.json")
    customer_delivery = load_json(AI_ROOT / "reports" / "customer_delivery_readiness_report.json")
    local_release = load_json(args.local_release)
    local_release_summary = local_release.get("readiness_summary") if isinstance(local_release.get("readiness_summary"), dict) else {}
    parallel_execution = load_json(AI_ROOT / "reports" / "parallel_execution_board.json")
    external_data = load_json(AI_ROOT / "reports" / "external_data_source_registry_validation_report.json")
    acceptance = load_json(AI_ROOT / "reports" / "workstream_acceptance_gates.json")
    license_decisions = load_json(AI_ROOT / "reports" / "external_license_review_decision_validation_report.json")
    operator_status = load_json(AI_ROOT / "reports" / "operator_review_status_report.json")
    data_quality = load_json(AI_ROOT / "reports" / "data_quality_report.json")

    failures: list[dict[str, Any]] = []
    streams = stream_map(board)
    expected_ready_streams = sum(1 for row in streams.values() if row.get("ready") is True)

    fail_if(not board, failures, "board_present", str(args.board), "existing JSON board")
    fail_if(board.get("overall_status") != "blocked_for_model_claim", failures, "overall_status_blocked", board.get("overall_status"), "blocked_for_model_claim")
    fail_if(board.get("local_only") is not True, failures, "local_only_true", board.get("local_only"), True)
    fail_if(board.get("data_quality_score") != data_quality.get("overall_score"), failures, "data_quality_score_matches_source", board.get("data_quality_score"), data_quality.get("overall_score"))
    fail_if(set(streams) != set(EXPECTED_STREAMS), failures, "stream_set_expected", sorted(streams), sorted(EXPECTED_STREAMS))
    fail_if(as_int(board.get("total_streams")) != len(EXPECTED_STREAMS), failures, "total_streams_expected", board.get("total_streams"), len(EXPECTED_STREAMS))
    fail_if(as_int(board.get("ready_streams")) != expected_ready_streams, failures, "ready_streams_matches_stream_rows", board.get("ready_streams"), expected_ready_streams)
    fail_if(as_int(board.get("ready_streams")) != 1, failures, "ready_streams_one_only", board.get("ready_streams"), 1)
    fail_if(tuple(board.get("recommended_order") or ()) != EXPECTED_ORDER, failures, "recommended_order_expected", board.get("recommended_order"), list(EXPECTED_ORDER))

    model = streams.get("model_training", {})
    model_current = model.get("current") if isinstance(model.get("current"), dict) else {}
    fail_if(model.get("status") != "blocked", failures, "model_training_status_blocked", model.get("status"), "blocked")
    fail_if(model.get("ready") is not False, failures, "model_training_ready_false", model.get("ready"), False)
    expected_model_current = {
        "safe_for_training_pipeline": safe_entry.get("safe_for_training_pipeline"),
        "safe_for_model_claim": safe_entry.get("safe_for_model_claim"),
        "quality_score": readiness.get("quality_score"),
        "multitask_status": multitask.get("status"),
        "multitask_missing_heads": multitask.get("missing_head_labels"),
        "active_learning_ready": active_learning.get("ready"),
        "active_learning_draft_rows": active_learning.get("draft_rows"),
        "active_learning_experiment_submission_allowed": active_learning.get("experiment_submission_allowed"),
        "head_model_card_status_heads": head_status.get("heads"),
        "head_model_card_ready_heads": head_status.get("ready_heads"),
        "benchmark_acquisition_plan_rows": benchmark_plan.get("plan_rows"),
        "benchmark_scorecards_ready": benchmark_plan.get("scorecards_ready"),
    }
    for key, expected in expected_model_current.items():
        fail_if(model_current.get(key) != expected, failures, f"model_training_{key}_matches_source", model_current.get(key), expected)
    for blocker in (
        "five-head model is not training-ready",
        "head-level benchmark scorecards are not ready",
        "customer delivery gate is blocked",
    ):
        fail_if(blocker not in (model.get("blockers") or []), failures, f"model_training_blocker_{blocker}", model.get("blockers"), f"contains {blocker}")

    governance_stream = streams.get("governance_release", {})
    governance_current = governance_stream.get("current") if isinstance(governance_stream.get("current"), dict) else {}
    fail_if(governance_stream.get("status") != "blocked", failures, "governance_release_status_blocked", governance_stream.get("status"), "blocked")
    fail_if(governance_stream.get("ready") is not False, failures, "governance_release_ready_false", governance_stream.get("ready"), False)
    expected_governance_current = {
        "governance_ready": governance.get("ready"),
        "customer_delivery_ready": customer_delivery.get("ready"),
        "local_release_ready": local_release.get("release_ready"),
        "local_release_guard_coverage_success": local_release_summary.get("local_release_guard_coverage_success"),
        "local_release_guard_coverage_failures": local_release_summary.get("local_release_guard_coverage_failures"),
        "claim_promotion_decision_validation_success": local_release_summary.get("claim_promotion_decision_validation_success"),
        "claim_promotion_decision_validation_failures": local_release_summary.get("claim_promotion_decision_validation_failures"),
        "claim_promotion_template_rows": local_release_summary.get("claim_promotion_template_rows"),
        "claim_promotion_template_matches_expected_contract": local_release_summary.get("claim_promotion_template_matches_expected_contract"),
        "claim_promotion_target_claim_rows": local_release_summary.get("claim_promotion_target_claim_rows"),
        "claim_promotion_requirement_name": local_release_summary.get("claim_promotion_requirement_name"),
        "claim_promotion_target_claim_rows_with_contract_requirement": local_release_summary.get("claim_promotion_target_claim_rows_with_contract_requirement"),
        "claim_promotion_target_claim_rows_with_contract_requirement_passed": local_release_summary.get("claim_promotion_target_claim_rows_with_contract_requirement_passed"),
        "claim_promotion_target_claim_contract_requirement_complete": local_release_summary.get("claim_promotion_target_claim_contract_requirement_complete"),
        "claim_promotion_target_claim_rows_with_contract_requirement_evidence": local_release_summary.get("claim_promotion_target_claim_rows_with_contract_requirement_evidence"),
        "claim_promotion_target_claim_contract_requirement_evidence_complete": local_release_summary.get("claim_promotion_target_claim_contract_requirement_evidence_complete"),
        "claim_promotion_required_evidence_artifact_count": local_release_summary.get("claim_promotion_required_evidence_artifact_count"),
        "claim_promotion_required_evidence_artifacts": local_release_summary.get("claim_promotion_required_evidence_artifacts"),
        "claim_promotion_required_validation_report_count": local_release_summary.get("claim_promotion_required_validation_report_count"),
        "claim_promotion_required_validation_reports": local_release_summary.get("claim_promotion_required_validation_reports"),
        "claim_promotion_decision_rows": local_release_summary.get("claim_promotion_decision_rows"),
        "claim_promotion_approved_rows": local_release_summary.get("claim_promotion_approved_rows"),
        "claim_promotion_missing_decisions": local_release_summary.get("claim_promotion_missing_decisions"),
        "claim_promotion_decision_success": local_release_summary.get("claim_promotion_decision_success"),
        "claim_promotion_validation_failures": local_release_summary.get("claim_promotion_validation_failures"),
        "human_target_projection_gap_report_valid": local_release_summary.get("human_target_projection_gap_report_valid"),
        "human_target_projection_runtime_manifest_valid": local_release_summary.get("human_target_projection_runtime_manifest_valid"),
        "human_target_projection_runtime_receipts_valid": local_release_summary.get("human_target_projection_runtime_receipts_valid"),
        "human_target_projection_blocked_source_index_valid": local_release_summary.get("human_target_projection_blocked_source_index_valid"),
        "human_target_projection_blocked_split_manifests_valid": local_release_summary.get("human_target_projection_blocked_split_manifests_valid"),
        "human_target_projection_unlock_checklist_valid": local_release_summary.get("human_target_projection_unlock_checklist_valid"),
        "human_target_projection_unlock_report_valid": local_release_summary.get("human_target_projection_unlock_report_valid"),
        "parallel_execution_status": parallel_execution.get("status"),
        "external_data_registry_ready": external_data.get("ready"),
        "license_review_training_approved_rows": license_decisions.get("approved_for_training_rows"),
        "license_review_delivery_approved_rows": license_decisions.get("approved_for_customer_delivery_rows"),
        "operator_review_status_ready": operator_status.get("ready"),
        "accepted_workstreams": acceptance.get("accepted_streams"),
        "total_acceptance_gates": acceptance.get("total_streams"),
    }
    for key, expected in expected_governance_current.items():
        fail_if(governance_current.get(key) != expected, failures, f"governance_release_{key}_matches_source", governance_current.get(key), expected)
    for key in ("governance_ready", "customer_delivery_ready", "local_release_ready"):
        fail_if(governance_current.get(key) is not False, failures, f"governance_release_{key}_false", governance_current.get(key), False)
    fail_if(
        governance_current.get("local_release_guard_coverage_success") is not True,
        failures,
        "governance_release_local_release_guard_coverage_success_true",
        governance_current.get("local_release_guard_coverage_success"),
        True,
    )
    fail_if(
        as_int(governance_current.get("local_release_guard_coverage_failures")) != 0,
        failures,
        "governance_release_local_release_guard_coverage_failures_zero",
        governance_current.get("local_release_guard_coverage_failures"),
        0,
    )
    fail_if(
        governance_current.get("claim_promotion_decision_validation_success") is not True,
        failures,
        "governance_release_claim_promotion_decision_validation_success_true",
        governance_current.get("claim_promotion_decision_validation_success"),
        True,
    )
    for key in (
        "claim_promotion_decision_validation_failures",
        "claim_promotion_decision_rows",
        "claim_promotion_approved_rows",
        "claim_promotion_validation_failures",
    ):
        fail_if(as_int(governance_current.get(key)) != 0, failures, f"governance_release_{key}_zero", governance_current.get(key), 0)
    fail_if(
        governance_current.get("claim_promotion_template_rows") != 9,
        failures,
        "governance_release_claim_promotion_template_rows_expected",
        governance_current.get("claim_promotion_template_rows"),
        9,
    )
    fail_if(
        governance_current.get("claim_promotion_template_matches_expected_contract") is not True,
        failures,
        "governance_release_claim_promotion_template_matches_expected_contract_true",
        governance_current.get("claim_promotion_template_matches_expected_contract"),
        True,
    )
    fail_if(
        governance_current.get("claim_promotion_target_claim_rows") != 9,
        failures,
        "governance_release_claim_promotion_target_claim_rows_expected",
        governance_current.get("claim_promotion_target_claim_rows"),
        9,
    )
    fail_if(
        governance_current.get("claim_promotion_requirement_name") != "claim-promotion evidence contract valid",
        failures,
        "governance_release_claim_promotion_requirement_name_expected",
        governance_current.get("claim_promotion_requirement_name"),
        "claim-promotion evidence contract valid",
    )
    fail_if(
        governance_current.get("claim_promotion_target_claim_rows_with_contract_requirement") != 9,
        failures,
        "governance_release_claim_promotion_target_claim_rows_with_contract_requirement_expected",
        governance_current.get("claim_promotion_target_claim_rows_with_contract_requirement"),
        9,
    )
    fail_if(
        governance_current.get("claim_promotion_target_claim_rows_with_contract_requirement_passed") != 9,
        failures,
        "governance_release_claim_promotion_target_claim_rows_with_contract_requirement_passed_expected",
        governance_current.get("claim_promotion_target_claim_rows_with_contract_requirement_passed"),
        9,
    )
    fail_if(
        governance_current.get("claim_promotion_target_claim_contract_requirement_complete") is not True,
        failures,
        "governance_release_claim_promotion_target_claim_contract_requirement_complete_true",
        governance_current.get("claim_promotion_target_claim_contract_requirement_complete"),
        True,
    )
    fail_if(
        governance_current.get("claim_promotion_target_claim_rows_with_contract_requirement_evidence") != 9,
        failures,
        "governance_release_claim_promotion_target_claim_rows_with_contract_requirement_evidence_expected",
        governance_current.get("claim_promotion_target_claim_rows_with_contract_requirement_evidence"),
        9,
    )
    fail_if(
        governance_current.get("claim_promotion_target_claim_contract_requirement_evidence_complete") is not True,
        failures,
        "governance_release_claim_promotion_target_claim_contract_requirement_evidence_complete_true",
        governance_current.get("claim_promotion_target_claim_contract_requirement_evidence_complete"),
        True,
    )
    fail_if(
        governance_current.get("claim_promotion_required_validation_report_count") != 6,
        failures,
        "governance_release_claim_promotion_required_validation_report_count_expected",
        governance_current.get("claim_promotion_required_validation_report_count"),
        6,
    )
    fail_if(
        governance_current.get("claim_promotion_required_evidence_artifact_count") != 3,
        failures,
        "governance_release_claim_promotion_required_evidence_artifact_count_expected",
        governance_current.get("claim_promotion_required_evidence_artifact_count"),
        3,
    )
    expected_required_evidence_artifacts = [
        "reports/claim_readiness_matrix.json",
        "reports/local_release_manifest.json",
        "reports/master_readiness_board.json",
    ]
    fail_if(
        governance_current.get("claim_promotion_required_evidence_artifacts") != expected_required_evidence_artifacts,
        failures,
        "governance_release_claim_promotion_required_evidence_artifacts_expected",
        governance_current.get("claim_promotion_required_evidence_artifacts"),
        expected_required_evidence_artifacts,
    )
    fail_if(
        governance_current.get("claim_promotion_missing_decisions") != 9,
        failures,
        "governance_release_claim_promotion_missing_decisions_expected",
        governance_current.get("claim_promotion_missing_decisions"),
        9,
    )
    fail_if(
        governance_current.get("claim_promotion_decision_success") is not False,
        failures,
        "governance_release_claim_promotion_decision_success_false",
        governance_current.get("claim_promotion_decision_success"),
        False,
    )
    for key in (
        "human_target_projection_gap_report_valid",
        "human_target_projection_runtime_manifest_valid",
        "human_target_projection_runtime_receipts_valid",
        "human_target_projection_blocked_source_index_valid",
        "human_target_projection_blocked_split_manifests_valid",
        "human_target_projection_unlock_checklist_valid",
        "human_target_projection_unlock_report_valid",
    ):
        fail_if(governance_current.get(key) is not True, failures, f"governance_release_{key}_true", governance_current.get(key), True)

    platform = streams.get("platform_integration", {})
    fail_if(platform.get("status") != "local_gate_passed", failures, "platform_status_local_gate_passed", platform.get("status"), "local_gate_passed")
    fail_if(platform.get("ready") is not False, failures, "platform_ready_false", platform.get("ready"), False)
    fail_if("production platform integration is not authorized; local gate only" not in (platform.get("blockers") or []), failures, "platform_local_only_blocker_present", platform.get("blockers"), "local-only production blocker")

    validation = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "local_only": True,
        "checked_board": str(args.board),
        "expected_streams": list(EXPECTED_STREAMS),
        "overall_status": board.get("overall_status"),
        "ready_streams": board.get("ready_streams"),
        "total_streams": board.get("total_streams"),
        "failures": failures,
        "success": not failures,
        "safe_for_model_claim": False,
        "release_ready": False,
        "policy": "Fail-closed validation for the master readiness board; no stream is promoted and no model/release gate is opened.",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(validation, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({
        "success": validation["success"],
        "overall_status": validation["overall_status"],
        "ready_streams": validation["ready_streams"],
        "total_streams": validation["total_streams"],
        "failures": len(failures),
        "output": str(args.output),
    }, ensure_ascii=False))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
