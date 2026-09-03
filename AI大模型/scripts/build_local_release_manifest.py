#!/usr/bin/env python3
"""Build a local release manifest for P30-style review packages."""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
ENZYME_DB_ROOT = Path("/Users/keweibo/科为博/05自动化程序/04研发工作区/酶数据库")
OUT = AI_ROOT / "reports" / "local_release_manifest.json"


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def sha256(path: Path) -> str | None:
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None


def validation_success_fail_closed(report: dict[str, Any]) -> bool:
    if report.get("success") is True:
        return True
    failures = report.get("failures")
    return (
        report.get("contract_valid") is True
        and report.get("failure_count") == 0
        and isinstance(failures, list)
        and len(failures) == 0
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Build local release manifest")
    parser.add_argument("--output", type=Path, default=OUT)
    args = parser.parse_args()

    data_manifest = load_json(AI_ROOT / "reports" / "data_lake_manifest.json")
    master = load_json(AI_ROOT / "reports" / "master_readiness_board.json")
    governance = load_json(AI_ROOT / "reports" / "governance_readiness_report.json")
    biosecurity = load_json(AI_ROOT / "reports" / "biosecurity_readiness_report.json")
    customer = load_json(AI_ROOT / "reports" / "customer_delivery_readiness_report.json")
    benchmark = load_json(AI_ROOT / "reports" / "benchmark_matrix_report.json")
    benchmark_plan = load_json(AI_ROOT / "reports" / "benchmark_acquisition_plan_report.json")
    operator_queue = load_json(AI_ROOT / "reports" / "operator_review_action_queue_report.json")
    operator_status = load_json(AI_ROOT / "reports" / "operator_review_status_report.json")
    operator_action_validation = load_json(AI_ROOT / "reports" / "operator_review_action_decision_validation_report.json")
    workstream_acceptance_decisions = load_json(AI_ROOT / "reports" / "workstream_acceptance_decision_validation_report.json")
    license_decisions = load_json(AI_ROOT / "reports" / "external_license_review_decision_validation_report.json")
    biosecurity_decisions = load_json(AI_ROOT / "reports" / "biosecurity_screening_decision_validation_report.json")
    ip_decisions = load_json(AI_ROOT / "reports" / "sequence_ip_fto_decision_validation_report.json")
    provenance = load_json(AI_ROOT / "reports" / "provenance_graph_report.json")
    claim_matrix = load_json(AI_ROOT / "reports" / "claim_readiness_matrix.json")
    claim_policy_anchor = load_json(AI_ROOT / "reports" / "claim_readiness_policy_anchor_validation_report.json")
    claim_policy_anchor_regression = load_json(AI_ROOT / "reports" / "claim_readiness_policy_anchor_regression_report.json")
    claim_promotion = load_json(AI_ROOT / "reports" / "claim_promotion_decision_validation_report.json")
    claim_matrix_fail_closed_policy = load_json(AI_ROOT / "reports" / "claim_readiness_matrix_fail_closed_policy_validation_report.json")
    claim_matrix_policy_current = load_json(AI_ROOT / "reports" / "claim_readiness_matrix_fail_closed_policy_current_validation_report.json")
    claim_matrix_policy_current_regression = load_json(AI_ROOT / "reports" / "claim_readiness_matrix_fail_closed_policy_current_regression_report.json")
    human_backlog = load_json(AI_ROOT / "reports" / "human_decision_backlog_report.json")
    human_backlog_fail_closed_consistency = load_json(AI_ROOT / "reports" / "human_decision_backlog_fail_closed_consistency_validation_report.json")
    human_decision_reviewer_input_package = load_json(AI_ROOT / "reports" / "human_decision_reviewer_input_package_20260806.json")
    human_decision_pending_row_index = load_json(AI_ROOT / "reports" / "human_decision_pending_row_index_20260806.json")
    human_decision_review_batches = load_json(AI_ROOT / "reports" / "human_decision_review_batches_20260806.json")
    human_decision_review_batches_validation = load_json(AI_ROOT / "reports" / "human_decision_review_batches_validation_report_20260806.json")
    human_decision_priority_queue = load_json(AI_ROOT / "reports" / "human_decision_priority_queue_20260806.json")
    human_decision_batch_session_board = load_json(AI_ROOT / "reports" / "human_decision_batch_session_board_20260806.json")
    human_decision_batch_session_board_validation = load_json(AI_ROOT / "reports" / "human_decision_batch_session_board_validation_report_20260806.json")
    human_decision_release_blocker_matrix = load_json(AI_ROOT / "reports" / "human_decision_release_blocker_matrix_20260806.json")
    human_decision_next_closeout_package = load_json(AI_ROOT / "reports" / "human_decision_next_closeout_package_20260806.json")
    human_decision_first_assignment_wave = load_json(AI_ROOT / "reports" / "human_decision_first_assignment_wave_20260806.json")
    human_decision_first_assignment_wave_validation = load_json(AI_ROOT / "reports" / "human_decision_first_assignment_wave_validation_report_20260806.json")
    human_review_launch = load_json(AI_ROOT / "reports" / "human_review_launch_board_report.json")
    human_review_launch_validation = load_json(AI_ROOT / "reports" / "human_review_launch_board_validation_report.json")
    human_review_closeout = load_json(AI_ROOT / "reports" / "human_review_closeout_board_report.json")
    human_review_closeout_validation = load_json(AI_ROOT / "reports" / "human_review_closeout_board_validation_report.json")
    human_review_release_consistency = load_json(AI_ROOT / "reports" / "human_review_release_consistency_validation_report.json")
    governance_review_bundle = load_json(AI_ROOT / "reports" / "governance_review_bundle_report.json")
    governance_review_bundle_validation = load_json(AI_ROOT / "reports" / "governance_review_bundle_validation_report.json")
    p478_governance_review_bundle_gap_audit = load_json(AI_ROOT / "reports" / "p478_governance_review_bundle_gap_audit_report.json")
    p478_governance_review_bundle_gap_audit_validation = load_json(AI_ROOT / "reports" / "p478_governance_review_bundle_gap_audit_validation_report.json")
    p479_customer_delivery_readiness_gap_audit = load_json(AI_ROOT / "reports" / "p479_customer_delivery_readiness_gap_audit_report.json")
    p479_customer_delivery_readiness_gap_audit_validation = load_json(AI_ROOT / "reports" / "p479_customer_delivery_readiness_gap_audit_validation_report.json")
    p480_claim_readiness_blocker_gap_audit = load_json(AI_ROOT / "reports" / "p480_claim_readiness_blocker_gap_audit_report.json")
    p480_claim_readiness_blocker_gap_audit_validation = load_json(AI_ROOT / "reports" / "p480_claim_readiness_blocker_gap_audit_validation_report.json")
    p481_local_release_blocked_capability_gap_audit = load_json(AI_ROOT / "reports" / "p481_local_release_blocked_capability_gap_audit_report.json")
    p481_local_release_blocked_capability_gap_audit_validation = load_json(AI_ROOT / "reports" / "p481_local_release_blocked_capability_gap_audit_validation_report.json")
    p482_master_readiness_stream_gap_audit = load_json(AI_ROOT / "reports" / "p482_master_readiness_stream_gap_audit_report.json")
    p482_master_readiness_stream_gap_audit_validation = load_json(AI_ROOT / "reports" / "p482_master_readiness_stream_gap_audit_validation_report.json")
    p483_next_unlock_execution_gap_audit = load_json(AI_ROOT / "reports" / "p483_next_unlock_execution_gap_audit_report.json")
    p483_next_unlock_execution_gap_audit_validation = load_json(AI_ROOT / "reports" / "p483_next_unlock_execution_gap_audit_validation_report.json")
    p484_next_unlock_operator_navigation_gap_audit = load_json(AI_ROOT / "reports" / "p484_next_unlock_operator_navigation_gap_audit_report.json")
    p484_next_unlock_operator_navigation_gap_audit_validation = load_json(AI_ROOT / "reports" / "p484_next_unlock_operator_navigation_gap_audit_validation_report.json")
    p485_next_unlock_blocker_matrix_gap_audit = load_json(AI_ROOT / "reports" / "p485_next_unlock_blocker_matrix_gap_audit_report.json")
    p485_next_unlock_blocker_matrix_gap_audit_validation = load_json(AI_ROOT / "reports" / "p485_next_unlock_blocker_matrix_gap_audit_validation_report.json")
    p486_next_unlock_remediation_queue_gap_audit = load_json(AI_ROOT / "reports" / "p486_next_unlock_remediation_queue_gap_audit_report.json")
    p486_next_unlock_remediation_queue_gap_audit_validation = load_json(AI_ROOT / "reports" / "p486_next_unlock_remediation_queue_gap_audit_validation_report.json")
    p487_next_unlock_multi_agent_launch_gap_audit = load_json(AI_ROOT / "reports" / "p487_next_unlock_multi_agent_launch_gap_audit_report.json")
    p487_next_unlock_multi_agent_launch_gap_audit_validation = load_json(AI_ROOT / "reports" / "p487_next_unlock_multi_agent_launch_gap_audit_validation_report.json")
    p488_next_unlock_agent_lane_status_gap_audit = load_json(AI_ROOT / "reports" / "p488_next_unlock_agent_lane_status_gap_audit_report.json")
    p488_next_unlock_agent_lane_status_gap_audit_validation = load_json(AI_ROOT / "reports" / "p488_next_unlock_agent_lane_status_gap_audit_validation_report.json")
    p489_next_unlock_lane_dispatch_gap_audit = load_json(AI_ROOT / "reports" / "p489_next_unlock_lane_dispatch_gap_audit_report.json")
    p489_next_unlock_lane_dispatch_gap_audit_validation = load_json(AI_ROOT / "reports" / "p489_next_unlock_lane_dispatch_gap_audit_validation_report.json")
    p490_next_unlock_action_checklist_gap_audit = load_json(AI_ROOT / "reports" / "p490_next_unlock_action_checklist_gap_audit_report.json")
    p490_next_unlock_action_checklist_gap_audit_validation = load_json(AI_ROOT / "reports" / "p490_next_unlock_action_checklist_gap_audit_validation_report.json")
    p491_next_unlock_operator_work_ledger_gap_audit = load_json(AI_ROOT / "reports" / "p491_next_unlock_operator_work_ledger_gap_audit_report.json")
    p491_next_unlock_operator_work_ledger_gap_audit_validation = load_json(AI_ROOT / "reports" / "p491_next_unlock_operator_work_ledger_gap_audit_validation_report.json")
    p492_next_unlock_operator_work_receipt_gap_audit = load_json(AI_ROOT / "reports" / "p492_next_unlock_operator_work_receipt_gap_audit_report.json")
    p492_next_unlock_operator_work_receipt_gap_audit_validation = load_json(AI_ROOT / "reports" / "p492_next_unlock_operator_work_receipt_gap_audit_validation_report.json")
    p493_human_review_closeout_gap_audit = load_json(AI_ROOT / "reports" / "p493_human_review_closeout_gap_audit_report.json")
    p493_human_review_closeout_gap_audit_validation = load_json(AI_ROOT / "reports" / "p493_human_review_closeout_gap_audit_validation_report.json")
    p494_operator_work_receipt_manifest_consistency_gap_audit = load_json(AI_ROOT / "reports" / "p494_operator_work_receipt_manifest_consistency_gap_audit_report.json")
    p494_operator_work_receipt_manifest_consistency_gap_audit_validation = load_json(AI_ROOT / "reports" / "p494_operator_work_receipt_manifest_consistency_gap_audit_validation_report.json")
    next_unlock = load_json(AI_ROOT / "reports" / "next_unlock_plan.json")
    next_unlock_execution = load_json(AI_ROOT / "reports" / "next_unlock_execution_board.json")
    next_unlock_validation = load_json(AI_ROOT / "reports" / "next_unlock_execution_validation_report.json")
    next_unlock_operator_index = load_json(AI_ROOT / "reports" / "next_unlock_operator_index.json")
    next_unlock_blockers = load_json(AI_ROOT / "reports" / "next_unlock_blocker_matrix.json")
    next_unlock_remediation = load_json(AI_ROOT / "reports" / "next_unlock_remediation_queue.json")
    next_unlock_multi_agent = load_json(AI_ROOT / "reports" / "next_unlock_multi_agent_launch_board.json")
    next_unlock_multi_agent_validation = load_json(AI_ROOT / "reports" / "next_unlock_multi_agent_launch_validation_report.json")
    pending_stage_all_started = load_json(AI_ROOT / "reports" / "pending_stage_all_started_board.json")
    pending_stage_all_started_validation = load_json(AI_ROOT / "reports" / "pending_stage_all_started_board_validation_report.json")
    active_stage_execution_matrix = load_json(AI_ROOT / "reports" / "active_stage_execution_matrix_report.json")
    active_stage_execution_matrix_validation = load_json(AI_ROOT / "reports" / "active_stage_execution_matrix_validation_report.json")
    next_unlock_agent_lanes = load_json(AI_ROOT / "reports" / "next_unlock_agent_lane_status_report.json")
    next_unlock_lane_dispatch = load_json(AI_ROOT / "reports" / "next_unlock_lane_dispatch_packet_report.json")
    next_unlock_lane_dispatch_validation = load_json(AI_ROOT / "reports" / "next_unlock_lane_dispatch_validation_report.json")
    next_unlock_action_checklist = load_json(AI_ROOT / "reports" / "next_unlock_action_checklist_report.json")
    next_unlock_action_checklist_validation = load_json(AI_ROOT / "reports" / "next_unlock_action_checklist_validation_report.json")
    next_unlock_operator_work_ledger = load_json(AI_ROOT / "reports" / "next_unlock_operator_work_ledger_report.json")
    next_unlock_operator_work_ledger_validation = load_json(AI_ROOT / "reports" / "next_unlock_operator_work_ledger_validation_report.json")
    next_unlock_operator_work_receipts = load_json(AI_ROOT / "reports" / "next_unlock_operator_work_receipt_report.json")
    next_unlock_operator_work_receipt_validation = load_json(AI_ROOT / "reports" / "next_unlock_operator_work_receipt_validation_report.json")
    operator_work_receipt_manifest_consistency = load_json(
        AI_ROOT / "reports" / "operator_work_receipt_manifest_consistency_validation_report.json"
    )
    enzyme_analysis_policy = load_json(AI_ROOT / "reports" / "enzyme_analysis_constraint_policy_report.json")
    model_quality_unlock = load_json(AI_ROOT / "reports" / "model_quality_unlock_requirements_report.json")
    advanced_model = load_json(AI_ROOT / "reports" / "advanced_model_architecture_report.json")
    advanced_model_regression = load_json(AI_ROOT / "reports" / "advanced_model_scaffold_regression_report.json")
    advanced_feature_cache = load_json(AI_ROOT / "reports" / "advanced_feature_cache_plan_report.json")
    enzyme_action_space = load_json(AI_ROOT / "reports" / "enzyme_action_space_registry_report.json")
    enzyme_tool_contract_validation = load_json(AI_ROOT / "reports" / "enzyme_tool_contract_validation_report.json")
    enzyme_resource_retrieval = load_json(AI_ROOT / "reports" / "enzyme_resource_retrieval_plan_report.json")
    enzyme_resource_retrieval_validation = load_json(AI_ROOT / "reports" / "enzyme_resource_retrieval_plan_validation_report.json")
    enzyme_agent_result = load_json(AI_ROOT / "reports" / "enzyme_agent_result_template.json")
    enzyme_agent_result_validation = load_json(AI_ROOT / "reports" / "enzyme_agent_result_validation_report.json")
    enzyme_agent_result_regression = load_json(AI_ROOT / "reports" / "enzyme_agent_result_safety_regression_report.json")
    enzyme_agent_trace = load_json(AI_ROOT / "reports" / "enzyme_agent_trace_audit_report.json")
    enzyme_agent_trace_validation = load_json(AI_ROOT / "reports" / "enzyme_agent_trace_audit_validation_report.json")
    enzyme_agent_release_guard_order = load_json(AI_ROOT / "reports" / "enzyme_agent_controlled_release_guard_order_validation_report.json")
    enzyme_agent_release_guard_order_regression = load_json(AI_ROOT / "reports" / "enzyme_agent_controlled_release_guard_order_regression_report.json")
    enzyme_agent_release_guard_order_current = load_json(AI_ROOT / "reports" / "enzyme_agent_controlled_release_guard_order_current_validation_report.json")
    enzyme_agent_release_guard_order_current_regression = load_json(AI_ROOT / "reports" / "enzyme_agent_controlled_release_guard_order_current_regression_report.json")
    enzyme_agent_release_guard_order_atomicity_regression = load_json(AI_ROOT / "reports" / "enzyme_agent_controlled_release_guard_order_atomicity_regression_report.json")
    enzyme_agent_execution_wave_pair_atomicity_regression = load_json(AI_ROOT / "reports" / "enzyme_agent_controlled_execution_wave_pair_atomicity_regression_report.json")
    enzyme_agent_execution_receipt_proof_current = load_json(AI_ROOT / "reports" / "enzyme_agent_execution_receipt_proof_current_validation_report.json")
    enzyme_agent_execution_receipt_proof_current_regression = load_json(AI_ROOT / "reports" / "enzyme_agent_execution_receipt_proof_current_regression_report.json")
    stage25_remaining_blocker_cross_binding = load_json(AI_ROOT / "reports" / "stage25_remaining_blocker_cross_binding_validation_report.json")
    stage25_remaining_blocker_cross_binding_regression = load_json(AI_ROOT / "reports" / "stage25_remaining_blocker_cross_binding_regression_report.json")
    enzyme_agent_execution_receipts = load_json(AI_ROOT / "reports" / "enzyme_agent_execution_receipt_gate_report.json")
    enzyme_agent_execution_receipts_validation = load_json(AI_ROOT / "reports" / "enzyme_agent_execution_receipt_gate_validation_report.json")
    enzyme_agent_execution_receipts_lineage = load_json(AI_ROOT / "reports" / "enzyme_agent_execution_receipt_lineage_validation_report.json")
    enzyme_agent_execution_receipts_regression = load_json(AI_ROOT / "reports" / "enzyme_agent_execution_receipt_safety_regression_report.json")
    enzyme_agent_execution_eligibility = load_json(AI_ROOT / "reports" / "enzyme_agent_execution_eligibility_matrix_report.json")
    enzyme_agent_execution_eligibility_validation = load_json(AI_ROOT / "reports" / "enzyme_agent_execution_eligibility_matrix_validation_report.json")
    enzyme_agent_execution_eligibility_regression = load_json(AI_ROOT / "reports" / "enzyme_agent_execution_eligibility_safety_regression_report.json")
    enzyme_agent_execution_outcome = load_json(AI_ROOT / "reports" / "enzyme_agent_execution_outcome_dashboard_report.json")
    enzyme_agent_execution_outcome_validation = load_json(AI_ROOT / "reports" / "enzyme_agent_execution_outcome_dashboard_validation_report.json")
    validated_feature_index = load_json(AI_ROOT / "reports" / "validated_feature_index_report.json")
    validated_feature_index_validation = load_json(AI_ROOT / "reports" / "validated_feature_index_validation_report.json")
    advanced_model_feature_contract = load_json(AI_ROOT / "reports" / "advanced_model_feature_contract_report.json")
    advanced_model_feature_contract_validation = load_json(AI_ROOT / "reports" / "advanced_model_feature_contract_validation_report.json")
    google_github_research = load_json(AI_ROOT / "reports" / "google_github_advanced_model_research_2026_07_28.json")
    proteinmcp_research = load_json(AI_ROOT / "reports" / "proteinmcp_deep_research_2026_07_31.json")
    proteinmcp_download_audit = load_json(AI_ROOT / "reports" / "proteinmcp_source_download_audit_2026_07_31.json")
    kwb_tool_lifecycle = load_json(AI_ROOT / "reports" / "kwb_tool_lifecycle_registry_report.json")
    kwb_tool_lifecycle_validation = load_json(AI_ROOT / "reports" / "kwb_tool_lifecycle_registry_validation_report.json")
    kwb_workflow_skills = load_json(AI_ROOT / "reports" / "kwb_workflow_skill_registry_report.json")
    kwb_workflow_skills_validation = load_json(AI_ROOT / "reports" / "kwb_workflow_skill_registry_validation_report.json")
    mcp_wrapper_staging = load_json(AI_ROOT / "reports" / "mcp_wrapper_staging_gate_report.json")
    mcp_wrapper_staging_validation = load_json(AI_ROOT / "reports" / "mcp_wrapper_staging_gate_validation_report.json")
    top_tier_execution = load_json(AI_ROOT / "reports" / "top_tier_model_execution_board.json")
    top_tier_validation = load_json(AI_ROOT / "reports" / "top_tier_model_execution_validation_report.json")
    top_tier_ready_receipts = load_json(AI_ROOT / "reports" / "top_tier_model_ready_to_verify_receipt_report.json")
    top_tier_ready_receipt_validation = load_json(AI_ROOT / "reports" / "top_tier_model_ready_to_verify_receipt_validation_report.json")
    p495_top_tier_ready_to_verify_receipt_gap_audit = load_json(AI_ROOT / "reports" / "p495_top_tier_ready_to_verify_receipt_gap_audit_report.json")
    p495_top_tier_ready_to_verify_receipt_gap_audit_validation = load_json(AI_ROOT / "reports" / "p495_top_tier_ready_to_verify_receipt_gap_audit_validation_report.json")
    non_human_construction = load_json(AI_ROOT / "reports" / "non_human_construction_board.json")
    non_human_construction_validation = load_json(AI_ROOT / "reports" / "non_human_construction_validation_report.json")
    non_human_ready_receipts = load_json(AI_ROOT / "reports" / "non_human_ready_to_verify_receipt_report.json")
    non_human_ready_receipt_validation = load_json(AI_ROOT / "reports" / "non_human_ready_to_verify_receipt_validation_report.json")
    p496_non_human_ready_to_verify_receipt_gap_audit = load_json(AI_ROOT / "reports" / "p496_non_human_ready_to_verify_receipt_gap_audit_report.json")
    p496_non_human_ready_to_verify_receipt_gap_audit_validation = load_json(AI_ROOT / "reports" / "p496_non_human_ready_to_verify_receipt_gap_audit_validation_report.json")
    ready_to_verify_promotion = load_json(AI_ROOT / "reports" / "ready_to_verify_promotion_board.json")
    ready_to_verify_promotion_validation = load_json(AI_ROOT / "reports" / "ready_to_verify_promotion_validation_report.json")
    ready_to_verify_promotion_regression = load_json(AI_ROOT / "reports" / "ready_to_verify_promotion_safety_regression_report.json")
    ready_to_verify_promotion_release_summary_regression = load_json(AI_ROOT / "reports" / "local_release_promotion_summary_safety_regression_report.json")
    data_lake_artifact_integrity_regression = load_json(AI_ROOT / "reports" / "data_lake_artifact_integrity_regression_report.json")
    local_release_high_risk_summary_regression = load_json(AI_ROOT / "reports" / "local_release_high_risk_summary_safety_regression_report.json")
    local_release_high_risk_coverage_regression = load_json(AI_ROOT / "reports" / "local_release_high_risk_coverage_safety_regression_report.json")
    data_lake_live_content_integrity = load_json(AI_ROOT / "reports" / "data_lake_live_content_integrity_validation_report.json")
    data_lake_live_content_integrity_regression = load_json(AI_ROOT / "reports" / "data_lake_live_content_integrity_regression_report.json")
    data_lake_volatile_exemption_regression = load_json(AI_ROOT / "reports" / "data_lake_volatile_exemption_safety_regression_report.json")
    local_release_live_integrity_binding_regression = load_json(AI_ROOT / "reports" / "local_release_live_integrity_binding_regression_report.json")
    release_input_contract_policy = load_json(AI_ROOT / "reports" / "data_lake_release_input_contract_policy_validation_report.json")
    release_input_contract_policy_regression = load_json(AI_ROOT / "reports" / "data_lake_release_input_contract_policy_regression_report.json")
    local_release_contract_policy_binding_regression = load_json(AI_ROOT / "reports" / "local_release_contract_policy_binding_regression_report.json")
    stage25_docs_sync = load_json(AI_ROOT / "reports" / "stage25_operator_docs_dynamic_status_sync_report.json")
    stage25_docs_sync_regression = load_json(AI_ROOT / "reports" / "stage25_operator_docs_dynamic_status_sync_regression_report.json")
    stage25_docs_sync_regression_current = load_json(AI_ROOT / "reports" / "stage25_operator_docs_dynamic_status_sync_regression_current_validation_report.json")
    stage25_docs_sync_regression_current_regression = load_json(AI_ROOT / "reports" / "stage25_operator_docs_dynamic_status_sync_regression_current_regression_report.json")
    stage25_docs_sync_regression_atomicity = load_json(AI_ROOT / "reports" / "stage25_operator_docs_dynamic_status_sync_regression_atomicity_regression_report.json")
    stage25_docs_sync_policy = load_json(AI_ROOT / "reports" / "stage25_operator_docs_sync_contract_policy_validation_report.json")
    stage25_docs_sync_policy_regression = load_json(AI_ROOT / "reports" / "stage25_operator_docs_sync_contract_policy_regression_report.json")
    stage25_docs_sync_current = load_json(AI_ROOT / "reports" / "stage25_operator_docs_sync_current_receipt_validation_report.json")
    stage25_docs_sync_current_regression = load_json(AI_ROOT / "reports" / "stage25_operator_docs_sync_current_receipt_regression_report.json")
    stage25_docs_sync_terminal_regression = load_json(AI_ROOT / "reports" / "stage25_operator_docs_sync_terminal_recovery_regression_report.json")
    p497_stage25_operator_docs_sync_receipt_gap_audit = load_json(AI_ROOT / "reports" / "p497_stage25_operator_docs_sync_receipt_gap_audit_report.json")
    p497_stage25_operator_docs_sync_receipt_gap_audit_validation = load_json(AI_ROOT / "reports" / "p497_stage25_operator_docs_sync_receipt_gap_audit_validation_report.json")
    p498_safe_training_pipeline_current_receipt_gap_audit = load_json(AI_ROOT / "reports" / "p498_safe_training_pipeline_current_receipt_gap_audit_report.json")
    p498_safe_training_pipeline_current_receipt_gap_audit_validation = load_json(AI_ROOT / "reports" / "p498_safe_training_pipeline_current_receipt_gap_audit_validation_report.json")
    p499_local_release_consistency_receipt_gap_audit = load_json(AI_ROOT / "reports" / "p499_local_release_consistency_receipt_gap_audit_report.json")
    p499_local_release_consistency_receipt_gap_audit_validation = load_json(AI_ROOT / "reports" / "p499_local_release_consistency_receipt_gap_audit_validation_report.json")
    p500_stage25_fail_closed_validation_current_receipt_gap_audit = load_json(AI_ROOT / "reports" / "p500_stage25_fail_closed_validation_current_receipt_gap_audit_report.json")
    p500_stage25_fail_closed_validation_current_receipt_gap_audit_validation = load_json(AI_ROOT / "reports" / "p500_stage25_fail_closed_validation_current_receipt_gap_audit_validation_report.json")
    p501_ready_to_verify_promotion_gap_audit = load_json(AI_ROOT / "reports" / "p501_ready_to_verify_promotion_gap_audit_report.json")
    p501_ready_to_verify_promotion_gap_audit_validation = load_json(AI_ROOT / "reports" / "p501_ready_to_verify_promotion_gap_audit_validation_report.json")
    p502_local_release_safety_guard_link_gap_audit = load_json(AI_ROOT / "reports" / "p502_local_release_safety_guard_link_gap_audit_report.json")
    p502_local_release_safety_guard_link_audit_validation = load_json(AI_ROOT / "reports" / "p502_local_release_safety_guard_link_gap_audit_validation_report.json")
    p503_safe_training_pipeline_receipt_atomicity_gap_audit = load_json(AI_ROOT / "reports" / "p503_safe_training_pipeline_receipt_atomicity_gap_audit_report.json")
    p503_safe_training_pipeline_receipt_atomicity_gap_audit_validation = load_json(AI_ROOT / "reports" / "p503_safe_training_pipeline_receipt_atomicity_gap_audit_validation_report.json")
    p504_local_release_consistency_receipt_atomicity_gap_audit = load_json(AI_ROOT / "reports" / "p504_local_release_consistency_receipt_atomicity_gap_audit_report.json")
    p504_local_release_consistency_receipt_atomicity_gap_audit_validation = load_json(AI_ROOT / "reports" / "p504_local_release_consistency_receipt_atomicity_gap_audit_validation_report.json")
    p505_local_release_terminal_defer_mode_gap_audit = load_json(AI_ROOT / "reports" / "p505_local_release_terminal_defer_mode_gap_audit_report.json")
    p505_local_release_terminal_defer_mode_gap_audit_validation = load_json(AI_ROOT / "reports" / "p505_local_release_terminal_defer_mode_gap_audit_validation_report.json")
    p506_local_release_consistency_semantic_policy_current_gap_audit = load_json(AI_ROOT / "reports" / "p506_local_release_consistency_semantic_policy_current_gap_audit_report.json")
    p506_local_release_consistency_semantic_policy_current_gap_audit_validation = load_json(AI_ROOT / "reports" / "p506_local_release_consistency_semantic_policy_current_gap_audit_validation_report.json")
    p507_data_lake_artifact_integrity_gap_audit = load_json(AI_ROOT / "reports" / "p507_data_lake_artifact_integrity_gap_audit_report.json")
    p507_data_lake_artifact_integrity_gap_audit_validation = load_json(AI_ROOT / "reports" / "p507_data_lake_artifact_integrity_gap_audit_validation_report.json")
    p508_local_release_safety_guard_link_atomicity_gap_audit = load_json(AI_ROOT / "reports" / "p508_local_release_safety_guard_link_atomicity_gap_audit_report.json")
    p508_local_release_safety_guard_link_atomicity_gap_audit_validation = load_json(AI_ROOT / "reports" / "p508_local_release_safety_guard_link_atomicity_gap_audit_validation_report.json")
    p509_local_release_safety_guard_link_current_atomicity_gap_audit = load_json(AI_ROOT / "reports" / "p509_local_release_safety_guard_link_current_atomicity_gap_audit_report.json")
    p509_local_release_safety_guard_link_current_atomicity_gap_audit_validation = load_json(AI_ROOT / "reports" / "p509_local_release_safety_guard_link_current_atomicity_gap_audit_validation_report.json")
    p510_data_lake_volatile_exemption_gap_audit = load_json(AI_ROOT / "reports" / "p510_data_lake_volatile_exemption_gap_audit_report.json")
    p510_data_lake_volatile_exemption_gap_audit_validation = load_json(AI_ROOT / "reports" / "p510_data_lake_volatile_exemption_gap_audit_validation_report.json")
    p511_data_lake_live_content_integrity_gap_audit = load_json(AI_ROOT / "reports" / "p511_data_lake_live_content_integrity_gap_audit_report.json")
    p511_data_lake_live_content_integrity_gap_audit_validation = load_json(AI_ROOT / "reports" / "p511_data_lake_live_content_integrity_gap_audit_validation_report.json")
    p512_local_release_live_integrity_binding_gap_audit = load_json(AI_ROOT / "reports" / "p512_local_release_live_integrity_binding_gap_audit_report.json")
    p512_local_release_live_integrity_binding_gap_audit_validation = load_json(AI_ROOT / "reports" / "p512_local_release_live_integrity_binding_gap_audit_validation_report.json")
    p513_data_lake_release_input_contract_policy_gap_audit = load_json(AI_ROOT / "reports" / "p513_data_lake_release_input_contract_policy_gap_audit_report.json")
    p513_data_lake_release_input_contract_policy_gap_audit_validation = load_json(AI_ROOT / "reports" / "p513_data_lake_release_input_contract_policy_gap_audit_validation_report.json")
    p514_data_lake_release_input_contract_policy_regression_gap_audit = load_json(AI_ROOT / "reports" / "p514_data_lake_release_input_contract_policy_regression_gap_audit_report.json")
    p514_data_lake_release_input_contract_policy_regression_gap_audit_validation = load_json(AI_ROOT / "reports" / "p514_data_lake_release_input_contract_policy_regression_gap_audit_validation_report.json")
    p515_local_release_contract_policy_binding_gap_audit = load_json(AI_ROOT / "reports" / "p515_local_release_contract_policy_binding_gap_audit_report.json")
    p515_local_release_contract_policy_binding_gap_audit_validation = load_json(AI_ROOT / "reports" / "p515_local_release_contract_policy_binding_gap_audit_validation_report.json")
    p516_safe_training_pipeline_bootstrap_release_consistency_gap_audit = load_json(AI_ROOT / "reports" / "p516_safe_training_pipeline_bootstrap_release_consistency_gap_audit_report.json")
    p516_safe_training_pipeline_bootstrap_release_consistency_gap_audit_validation = load_json(AI_ROOT / "reports" / "p516_safe_training_pipeline_bootstrap_release_consistency_gap_audit_validation_report.json")
    p517_local_release_high_risk_summary_safety_gap_audit = load_json(AI_ROOT / "reports" / "p517_local_release_high_risk_summary_safety_gap_audit_report.json")
    p517_local_release_high_risk_summary_safety_gap_audit_validation = load_json(AI_ROOT / "reports" / "p517_local_release_high_risk_summary_safety_gap_audit_validation_report.json")
    p518_local_release_high_risk_coverage_safety_gap_audit = load_json(AI_ROOT / "reports" / "p518_local_release_high_risk_coverage_safety_gap_audit_report.json")
    p518_local_release_high_risk_coverage_safety_gap_audit_validation = load_json(AI_ROOT / "reports" / "p518_local_release_high_risk_coverage_safety_gap_audit_validation_report.json")
    p519_safe_training_pipeline_current_receipt_regression_gap_audit = load_json(AI_ROOT / "reports" / "p519_safe_training_pipeline_current_receipt_regression_gap_audit_report.json")
    p519_safe_training_pipeline_current_receipt_regression_gap_audit_validation = load_json(AI_ROOT / "reports" / "p519_safe_training_pipeline_current_receipt_regression_gap_audit_validation_report.json")
    p520_local_release_consistency_receipt_current_regression_gap_audit = load_json(AI_ROOT / "reports" / "p520_local_release_consistency_receipt_current_regression_gap_audit_report.json")
    p520_local_release_consistency_receipt_current_regression_gap_audit_validation = load_json(AI_ROOT / "reports" / "p520_local_release_consistency_receipt_current_regression_gap_audit_validation_report.json")
    p521_local_release_consistency_semantic_policy_regression_gap_audit = load_json(AI_ROOT / "reports" / "p521_local_release_consistency_semantic_policy_regression_gap_audit_report.json")
    p521_local_release_consistency_semantic_policy_regression_gap_audit_validation = load_json(AI_ROOT / "reports" / "p521_local_release_consistency_semantic_policy_regression_gap_audit_validation_report.json")
    p522_local_release_consistency_semantic_policy_atomicity_regression_gap_audit = load_json(AI_ROOT / "reports" / "p522_local_release_consistency_semantic_policy_atomicity_regression_gap_audit_report.json")
    p522_local_release_consistency_semantic_policy_atomicity_regression_gap_audit_validation = load_json(AI_ROOT / "reports" / "p522_local_release_consistency_semantic_policy_atomicity_regression_gap_audit_validation_report.json")
    p523_stage25_operator_docs_sync_contract_policy_gap_audit = load_json(AI_ROOT / "reports" / "p523_stage25_operator_docs_sync_contract_policy_gap_audit_report.json")
    p523_stage25_operator_docs_sync_contract_policy_gap_audit_validation = load_json(AI_ROOT / "reports" / "p523_stage25_operator_docs_sync_contract_policy_gap_audit_validation_report.json")
    p524_stage25_operator_docs_dynamic_status_sync_gap_audit = load_json(AI_ROOT / "reports" / "p524_stage25_operator_docs_dynamic_status_sync_gap_audit_report.json")
    p524_stage25_operator_docs_dynamic_status_sync_gap_audit_validation = load_json(AI_ROOT / "reports" / "p524_stage25_operator_docs_dynamic_status_sync_gap_audit_validation_report.json")
    p525_stage25_operator_docs_dynamic_status_sync_current_gap_audit = load_json(AI_ROOT / "reports" / "p525_stage25_operator_docs_dynamic_status_sync_current_gap_audit_report.json")
    p525_stage25_operator_docs_dynamic_status_sync_current_gap_audit_validation = load_json(AI_ROOT / "reports" / "p525_stage25_operator_docs_dynamic_status_sync_current_gap_audit_validation_report.json")
    p526_stage25_operator_docs_dynamic_status_sync_current_regression_gap_audit = load_json(AI_ROOT / "reports" / "p526_stage25_operator_docs_dynamic_status_sync_current_regression_gap_audit_report.json")
    p526_stage25_operator_docs_dynamic_status_sync_current_regression_gap_audit_validation = load_json(AI_ROOT / "reports" / "p526_stage25_operator_docs_dynamic_status_sync_current_regression_gap_audit_validation_report.json")
    p527_stage25_operator_docs_dynamic_status_sync_atomicity_gap_audit = load_json(AI_ROOT / "reports" / "p527_stage25_operator_docs_dynamic_status_sync_atomicity_gap_audit_report.json")
    p527_stage25_operator_docs_dynamic_status_sync_atomicity_gap_audit_validation = load_json(AI_ROOT / "reports" / "p527_stage25_operator_docs_dynamic_status_sync_atomicity_gap_audit_validation_report.json")
    p528_stage25_operator_docs_sync_contract_policy_regression_gap_audit = load_json(AI_ROOT / "reports" / "p528_stage25_operator_docs_sync_contract_policy_regression_gap_audit_report.json")
    p528_stage25_operator_docs_sync_contract_policy_regression_gap_audit_validation = load_json(AI_ROOT / "reports" / "p528_stage25_operator_docs_sync_contract_policy_regression_gap_audit_validation_report.json")
    p529_stage25_operator_docs_sync_current_receipt_regression_gap_audit = load_json(AI_ROOT / "reports" / "p529_stage25_operator_docs_sync_current_receipt_regression_gap_audit_report.json")
    p529_stage25_operator_docs_sync_current_receipt_regression_gap_audit_validation = load_json(AI_ROOT / "reports" / "p529_stage25_operator_docs_sync_current_receipt_regression_gap_audit_validation_report.json")
    p530_stage25_operator_docs_sync_terminal_recovery_regression_gap_audit = load_json(AI_ROOT / "reports" / "p530_stage25_operator_docs_sync_terminal_recovery_regression_gap_audit_report.json")
    p530_stage25_operator_docs_sync_terminal_recovery_regression_gap_audit_validation = load_json(AI_ROOT / "reports" / "p530_stage25_operator_docs_sync_terminal_recovery_regression_gap_audit_validation_report.json")
    p531_controlled_release_guard_order_validation_receipt_gap_audit = load_json(AI_ROOT / "reports" / "p531_controlled_release_guard_order_validation_receipt_gap_audit_report.json")
    p531_controlled_release_guard_order_validation_receipt_gap_audit_validation = load_json(AI_ROOT / "reports" / "p531_controlled_release_guard_order_validation_receipt_gap_audit_validation_report.json")
    p532_controlled_release_guard_order_regression_gap_audit = load_json(AI_ROOT / "reports" / "p532_controlled_release_guard_order_regression_gap_audit_report.json")
    p532_controlled_release_guard_order_regression_gap_audit_validation = load_json(AI_ROOT / "reports" / "p532_controlled_release_guard_order_regression_gap_audit_validation_report.json")
    p533_controlled_release_guard_order_current_validation_receipt_gap_audit = load_json(AI_ROOT / "reports" / "p533_controlled_release_guard_order_current_validation_receipt_gap_audit_report.json")
    p533_controlled_release_guard_order_current_validation_receipt_gap_audit_validation = load_json(AI_ROOT / "reports" / "p533_controlled_release_guard_order_current_validation_receipt_gap_audit_validation_report.json")
    p534_controlled_release_guard_order_current_regression_gap_audit = load_json(AI_ROOT / "reports" / "p534_controlled_release_guard_order_current_regression_gap_audit_report.json")
    p534_controlled_release_guard_order_current_regression_gap_audit_validation = load_json(AI_ROOT / "reports" / "p534_controlled_release_guard_order_current_regression_gap_audit_validation_report.json")
    p535_controlled_release_guard_order_atomicity_regression_gap_audit = load_json(AI_ROOT / "reports" / "p535_controlled_release_guard_order_atomicity_regression_gap_audit_report.json")
    p535_controlled_release_guard_order_atomicity_regression_gap_audit_validation = load_json(AI_ROOT / "reports" / "p535_controlled_release_guard_order_atomicity_regression_gap_audit_validation_report.json")
    p536_stage25_remaining_blocker_cross_binding_gap_audit = load_json(AI_ROOT / "reports" / "p536_stage25_remaining_blocker_cross_binding_gap_audit_report.json")
    p536_stage25_remaining_blocker_cross_binding_gap_audit_validation = load_json(AI_ROOT / "reports" / "p536_stage25_remaining_blocker_cross_binding_gap_audit_validation_report.json")
    p537_stage25_remaining_blocker_cross_binding_regression_gap_audit = load_json(AI_ROOT / "reports" / "p537_stage25_remaining_blocker_cross_binding_regression_gap_audit_report.json")
    p537_stage25_remaining_blocker_cross_binding_regression_gap_audit_validation = load_json(AI_ROOT / "reports" / "p537_stage25_remaining_blocker_cross_binding_regression_gap_audit_validation_report.json")
    p538_controlled_execution_wave_pair_atomicity_regression_gap_audit = load_json(AI_ROOT / "reports" / "p538_controlled_execution_wave_pair_atomicity_regression_gap_audit_report.json")
    p538_controlled_execution_wave_pair_atomicity_regression_gap_audit_validation = load_json(AI_ROOT / "reports" / "p538_controlled_execution_wave_pair_atomicity_regression_gap_audit_validation_report.json")
    p539_enzyme_agent_execution_receipt_gate_gap_audit = load_json(AI_ROOT / "reports" / "p539_enzyme_agent_execution_receipt_gate_gap_audit_report.json")
    p539_enzyme_agent_execution_receipt_gate_gap_audit_validation = load_json(AI_ROOT / "reports" / "p539_enzyme_agent_execution_receipt_gate_gap_audit_validation_report.json")
    p540_enzyme_agent_execution_receipt_lineage_gap_audit = load_json(AI_ROOT / "reports" / "p540_enzyme_agent_execution_receipt_lineage_gap_audit_report.json")
    p540_enzyme_agent_execution_receipt_lineage_gap_audit_validation = load_json(AI_ROOT / "reports" / "p540_enzyme_agent_execution_receipt_lineage_gap_audit_validation_report.json")
    p541_enzyme_agent_execution_receipt_proof_current_gap_audit = load_json(AI_ROOT / "reports" / "p541_enzyme_agent_execution_receipt_proof_current_gap_audit_report.json")
    p541_enzyme_agent_execution_receipt_proof_current_gap_audit_validation = load_json(AI_ROOT / "reports" / "p541_enzyme_agent_execution_receipt_proof_current_gap_audit_validation_report.json")
    p542_enzyme_agent_execution_receipt_proof_current_regression_gap_audit = load_json(AI_ROOT / "reports" / "p542_enzyme_agent_execution_receipt_proof_current_regression_gap_audit_report.json")
    p542_enzyme_agent_execution_receipt_proof_current_regression_gap_audit_validation = load_json(AI_ROOT / "reports" / "p542_enzyme_agent_execution_receipt_proof_current_regression_gap_audit_validation_report.json")
    p543_enzyme_agent_execution_receipt_safety_regression_gap_audit = load_json(AI_ROOT / "reports" / "p543_enzyme_agent_execution_receipt_safety_regression_gap_audit_report.json")
    p543_enzyme_agent_execution_receipt_safety_regression_gap_audit_validation = load_json(AI_ROOT / "reports" / "p543_enzyme_agent_execution_receipt_safety_regression_gap_audit_validation_report.json")
    p544_enzyme_agent_execution_eligibility_matrix_gap_audit = load_json(AI_ROOT / "reports" / "p544_enzyme_agent_execution_eligibility_matrix_gap_audit_report.json")
    p544_enzyme_agent_execution_eligibility_matrix_gap_audit_validation = load_json(AI_ROOT / "reports" / "p544_enzyme_agent_execution_eligibility_matrix_gap_audit_validation_report.json")
    p545_enzyme_agent_execution_eligibility_safety_regression_gap_audit = load_json(AI_ROOT / "reports" / "p545_enzyme_agent_execution_eligibility_safety_regression_gap_audit_report.json")
    p545_enzyme_agent_execution_eligibility_safety_regression_gap_audit_validation = load_json(AI_ROOT / "reports" / "p545_enzyme_agent_execution_eligibility_safety_regression_gap_audit_validation_report.json")
    p546_enzyme_agent_execution_outcome_dashboard_gap_audit = load_json(AI_ROOT / "reports" / "p546_enzyme_agent_execution_outcome_dashboard_gap_audit_report.json")
    p546_enzyme_agent_execution_outcome_dashboard_gap_audit_validation = load_json(AI_ROOT / "reports" / "p546_enzyme_agent_execution_outcome_dashboard_gap_audit_validation_report.json")
    p547_top_tier_model_execution_board_gap_audit = load_json(AI_ROOT / "reports" / "p547_top_tier_model_execution_board_gap_audit_report.json")
    p547_top_tier_model_execution_board_gap_audit_validation = load_json(AI_ROOT / "reports" / "p547_top_tier_model_execution_board_gap_audit_validation_report.json")
    p548_non_human_construction_board_gap_audit = load_json(AI_ROOT / "reports" / "p548_non_human_construction_board_gap_audit_report.json")
    p548_non_human_construction_board_gap_audit_validation = load_json(AI_ROOT / "reports" / "p548_non_human_construction_board_gap_audit_validation_report.json")
    p549_parallel_hard_gate_execution_receipts_gap_audit = load_json(AI_ROOT / "reports" / "p549_parallel_hard_gate_execution_receipts_gap_audit_report.json")
    p549_parallel_hard_gate_execution_receipts_gap_audit_validation = load_json(AI_ROOT / "reports" / "p549_parallel_hard_gate_execution_receipts_gap_audit_validation_report.json")
    p550_execution_receipt_artifact_freshness_gap_audit = load_json(AI_ROOT / "reports" / "p550_execution_receipt_artifact_freshness_gap_audit_report.json")
    p550_execution_receipt_artifact_freshness_gap_audit_validation = load_json(AI_ROOT / "reports" / "p550_execution_receipt_artifact_freshness_gap_audit_validation_report.json")
    p551_execution_receipt_artifact_hash_coverage_gap_audit = load_json(AI_ROOT / "reports" / "p551_execution_receipt_artifact_hash_coverage_gap_audit_report.json")
    p551_execution_receipt_artifact_hash_coverage_gap_audit_validation = load_json(AI_ROOT / "reports" / "p551_execution_receipt_artifact_hash_coverage_gap_audit_validation_report.json")
    p552_top_tier_model_execution_board_claim_boundary_gap_audit = load_json(AI_ROOT / "reports" / "p552_top_tier_model_execution_board_claim_boundary_gap_audit_report.json")
    p552_top_tier_model_execution_board_claim_boundary_gap_audit_validation = load_json(AI_ROOT / "reports" / "p552_top_tier_model_execution_board_claim_boundary_gap_audit_validation_report.json")
    p553_non_human_construction_board_claim_boundary_gap_audit = load_json(AI_ROOT / "reports" / "p553_non_human_construction_board_claim_boundary_gap_audit_report.json")
    p553_non_human_construction_board_claim_boundary_gap_audit_validation = load_json(AI_ROOT / "reports" / "p553_non_human_construction_board_claim_boundary_gap_audit_validation_report.json")
    p554_enzyme_agent_execution_outcome_formal_boundary_gap_audit = load_json(AI_ROOT / "reports" / "p554_enzyme_agent_execution_outcome_formal_boundary_gap_audit_report.json")
    p554_enzyme_agent_execution_outcome_formal_boundary_gap_audit_validation = load_json(AI_ROOT / "reports" / "p554_enzyme_agent_execution_outcome_formal_boundary_gap_audit_validation_report.json")
    p555_parallel_hard_gate_execution_decision_boundary_gap_audit = load_json(AI_ROOT / "reports" / "p555_parallel_hard_gate_execution_decision_boundary_gap_audit_report.json")
    p555_parallel_hard_gate_execution_decision_boundary_gap_audit_validation = load_json(AI_ROOT / "reports" / "p555_parallel_hard_gate_execution_decision_boundary_gap_audit_validation_report.json")
    p556_top_tier_ready_receipt_completion_boundary_gap_audit = load_json(AI_ROOT / "reports" / "p556_top_tier_ready_receipt_completion_boundary_gap_audit_report.json")
    p556_top_tier_ready_receipt_completion_boundary_gap_audit_validation = load_json(AI_ROOT / "reports" / "p556_top_tier_ready_receipt_completion_boundary_gap_audit_validation_report.json")
    p557_non_human_ready_receipt_completion_boundary_gap_audit = load_json(AI_ROOT / "reports" / "p557_non_human_ready_receipt_completion_boundary_gap_audit_report.json")
    p557_non_human_ready_receipt_completion_boundary_gap_audit_validation = load_json(AI_ROOT / "reports" / "p557_non_human_ready_receipt_completion_boundary_gap_audit_validation_report.json")
    p558_ready_to_verify_promotion_boundary_gap_audit = load_json(AI_ROOT / "reports" / "p558_ready_to_verify_promotion_boundary_gap_audit_report.json")
    p558_ready_to_verify_promotion_boundary_gap_audit_validation = load_json(AI_ROOT / "reports" / "p558_ready_to_verify_promotion_boundary_gap_audit_validation_report.json")
    p559_data_lake_live_integrity_boundary_gap_audit = load_json(AI_ROOT / "reports" / "p559_data_lake_live_integrity_boundary_gap_audit_report.json")
    p559_data_lake_live_integrity_boundary_gap_audit_validation = load_json(AI_ROOT / "reports" / "p559_data_lake_live_integrity_boundary_gap_audit_validation_report.json")
    p560_local_release_consistency_boundary_gap_audit = load_json(AI_ROOT / "reports" / "p560_local_release_consistency_boundary_gap_audit_report.json")
    p560_local_release_consistency_boundary_gap_audit_validation = load_json(AI_ROOT / "reports" / "p560_local_release_consistency_boundary_gap_audit_validation_report.json")
    p561_reviewed_numbering_hard_boundary_gap_audit = load_json(AI_ROOT / "reports" / "p561_reviewed_numbering_hard_boundary_gap_audit_report.json")
    p561_reviewed_numbering_hard_boundary_gap_audit_validation = load_json(AI_ROOT / "reports" / "p561_reviewed_numbering_hard_boundary_gap_audit_validation_report.json")
    p562_wet_lab_feedback_numeric_eligibility_boundary_gap_audit = load_json(AI_ROOT / "reports" / "p562_wet_lab_feedback_numeric_eligibility_boundary_gap_audit_report.json")
    p562_wet_lab_feedback_numeric_eligibility_boundary_gap_audit_validation = load_json(AI_ROOT / "reports" / "p562_wet_lab_feedback_numeric_eligibility_boundary_gap_audit_validation_report.json")
    p563_physics_ddg_backend_readiness_boundary_gap_audit = load_json(AI_ROOT / "reports" / "p563_physics_ddg_backend_readiness_boundary_gap_audit_report.json")
    p563_physics_ddg_backend_readiness_boundary_gap_audit_validation = load_json(AI_ROOT / "reports" / "p563_physics_ddg_backend_readiness_boundary_gap_audit_validation_report.json")
    p564_claim_readiness_matrix_hard_boundary_gap_audit = load_json(AI_ROOT / "reports" / "p564_claim_readiness_matrix_hard_boundary_gap_audit_report.json")
    p564_claim_readiness_matrix_hard_boundary_gap_audit_validation = load_json(AI_ROOT / "reports" / "p564_claim_readiness_matrix_hard_boundary_gap_audit_validation_report.json")
    p565_production_release_authorization_boundary_gap_audit = load_json(AI_ROOT / "reports" / "p565_production_release_authorization_boundary_gap_audit_report.json")
    p565_production_release_authorization_boundary_gap_audit_validation = load_json(AI_ROOT / "reports" / "p565_production_release_authorization_boundary_gap_audit_validation_report.json")
    p566_five_head_training_execution_boundary_gap_audit = load_json(AI_ROOT / "reports" / "p566_five_head_training_execution_boundary_gap_audit_report.json")
    p566_five_head_training_execution_boundary_gap_audit_validation = load_json(AI_ROOT / "reports" / "p566_five_head_training_execution_boundary_gap_audit_validation_report.json")
    p567_validated_feature_index_training_label_boundary_gap_audit = load_json(AI_ROOT / "reports" / "p567_validated_feature_index_training_label_boundary_gap_audit_report.json")
    p567_validated_feature_index_training_label_boundary_gap_audit_validation = load_json(AI_ROOT / "reports" / "p567_validated_feature_index_training_label_boundary_gap_audit_validation_report.json")
    p568_model_artifact_claim_boundary_gap_audit = load_json(AI_ROOT / "reports" / "p568_model_artifact_claim_boundary_gap_audit_report.json")
    p568_model_artifact_claim_boundary_gap_audit_validation = load_json(AI_ROOT / "reports" / "p568_model_artifact_claim_boundary_gap_audit_validation_report.json")
    p569_local_release_guard_coverage_boundary_gap_audit = load_json(AI_ROOT / "reports" / "p569_local_release_guard_coverage_boundary_gap_audit_report.json")
    p569_local_release_guard_coverage_boundary_gap_audit_validation = load_json(AI_ROOT / "reports" / "p569_local_release_guard_coverage_boundary_gap_audit_validation_report.json")
    p570_training_readiness_quality_boundary_gap_audit = load_json(AI_ROOT / "reports" / "p570_training_readiness_quality_boundary_gap_audit_report.json")
    p570_training_readiness_quality_boundary_gap_audit_validation = load_json(AI_ROOT / "reports" / "p570_training_readiness_quality_boundary_gap_audit_validation_report.json")
    p571_five_head_training_execution_contract_boundary_gap_audit = load_json(AI_ROOT / "reports" / "p571_five_head_training_execution_contract_boundary_gap_audit_report.json")
    p571_five_head_training_execution_contract_boundary_gap_audit_validation = load_json(AI_ROOT / "reports" / "p571_five_head_training_execution_contract_boundary_gap_audit_validation_report.json")
    p572_model_quality_hard_gate_contract_boundary_gap_audit = load_json(AI_ROOT / "reports" / "p572_model_quality_hard_gate_contract_boundary_gap_audit_report.json")
    p572_model_quality_hard_gate_contract_boundary_gap_audit_validation = load_json(AI_ROOT / "reports" / "p572_model_quality_hard_gate_contract_boundary_gap_audit_validation_report.json")
    p573_tool_lane_evidence_boundary_gap_audit = load_json(AI_ROOT / "reports" / "p573_tool_lane_evidence_boundary_gap_audit_report.json")
    p573_tool_lane_evidence_boundary_gap_audit_validation = load_json(AI_ROOT / "reports" / "p573_tool_lane_evidence_boundary_gap_audit_validation_report.json")
    p574_human_target_source_runtime_boundary_gap_audit = load_json(AI_ROOT / "reports" / "p574_human_target_source_runtime_boundary_gap_audit_report.json")
    p574_human_target_source_runtime_boundary_gap_audit_validation = load_json(AI_ROOT / "reports" / "p574_human_target_source_runtime_boundary_gap_audit_validation_report.json")
    p575_human_target_source_unlock_checklist_boundary_gap_audit = load_json(AI_ROOT / "reports" / "p575_human_target_source_unlock_checklist_boundary_gap_audit_report.json")
    p575_human_target_source_unlock_checklist_boundary_gap_audit_validation = load_json(AI_ROOT / "reports" / "p575_human_target_source_unlock_checklist_boundary_gap_audit_validation_report.json")
    p576_training_label_import_contract_boundary_gap_audit = load_json(AI_ROOT / "reports" / "p576_training_label_import_contract_boundary_gap_audit_report.json")
    p576_training_label_import_contract_boundary_gap_audit_validation = load_json(AI_ROOT / "reports" / "p576_training_label_import_contract_boundary_gap_audit_validation_report.json")
    p577_wet_lab_feedback_authorization_contract_boundary_gap_audit = load_json(AI_ROOT / "reports" / "p577_wet_lab_feedback_authorization_contract_boundary_gap_audit_report.json")
    p577_wet_lab_feedback_authorization_contract_boundary_gap_audit_validation = load_json(AI_ROOT / "reports" / "p577_wet_lab_feedback_authorization_contract_boundary_gap_audit_validation_report.json")
    p578_ddg_model_consumption_contract_boundary_gap_audit = load_json(AI_ROOT / "reports" / "p578_ddg_model_consumption_contract_boundary_gap_audit_report.json")
    p578_ddg_model_consumption_contract_boundary_gap_audit_validation = load_json(AI_ROOT / "reports" / "p578_ddg_model_consumption_contract_boundary_gap_audit_validation_report.json")
    p579_structure_feature_model_contract_boundary_gap_audit = load_json(AI_ROOT / "reports" / "p579_structure_feature_model_contract_boundary_gap_audit_report.json")
    p579_structure_feature_model_contract_boundary_gap_audit_validation = load_json(AI_ROOT / "reports" / "p579_structure_feature_model_contract_boundary_gap_audit_validation_report.json")
    p580_advanced_model_feature_contract_boundary_gap_audit = load_json(AI_ROOT / "reports" / "p580_advanced_model_feature_contract_boundary_gap_audit_report.json")
    p580_advanced_model_feature_contract_boundary_gap_audit_validation = load_json(AI_ROOT / "reports" / "p580_advanced_model_feature_contract_boundary_gap_audit_validation_report.json")
    p581_active_learning_trial_readiness_boundary_gap_audit = load_json(AI_ROOT / "reports" / "p581_active_learning_trial_readiness_boundary_gap_audit_report.json")
    p581_active_learning_trial_readiness_boundary_gap_audit_validation = load_json(AI_ROOT / "reports" / "p581_active_learning_trial_readiness_boundary_gap_audit_validation_report.json")
    p582_benchmark_readiness_packet_boundary_gap_audit = load_json(AI_ROOT / "reports" / "p582_benchmark_readiness_packet_boundary_gap_audit_report.json")
    p582_benchmark_readiness_packet_boundary_gap_audit_validation = load_json(AI_ROOT / "reports" / "p582_benchmark_readiness_packet_boundary_gap_audit_validation_report.json")
    p583_enzyme_tool_contract_boundary_gap_audit = load_json(AI_ROOT / "reports" / "p583_enzyme_tool_contract_boundary_gap_audit_report.json")
    p583_enzyme_tool_contract_boundary_gap_audit_validation = load_json(AI_ROOT / "reports" / "p583_enzyme_tool_contract_boundary_gap_audit_validation_report.json")
    p584_foreign_tool_readiness_boundary_gap_audit = load_json(AI_ROOT / "reports" / "p584_foreign_tool_readiness_boundary_gap_audit_report.json")
    p584_foreign_tool_readiness_boundary_gap_audit_validation = load_json(AI_ROOT / "reports" / "p584_foreign_tool_readiness_boundary_gap_audit_validation_report.json")
    p585_msa_runtime_readiness_boundary_gap_audit = load_json(AI_ROOT / "reports" / "p585_msa_runtime_readiness_boundary_gap_audit_report.json")
    p585_msa_runtime_readiness_boundary_gap_audit_validation = load_json(AI_ROOT / "reports" / "p585_msa_runtime_readiness_boundary_gap_audit_validation_report.json")
    p586_enzyme_resource_retrieval_plan_boundary_gap_audit = load_json(AI_ROOT / "reports" / "p586_enzyme_resource_retrieval_plan_boundary_gap_audit_report.json")
    p586_enzyme_resource_retrieval_plan_boundary_gap_audit_validation = load_json(AI_ROOT / "reports" / "p586_enzyme_resource_retrieval_plan_boundary_gap_audit_validation_report.json")
    p587_enzyme_agent_result_validation_boundary_gap_audit = load_json(AI_ROOT / "reports" / "p587_enzyme_agent_result_validation_boundary_gap_audit_report.json")
    p587_enzyme_agent_result_validation_boundary_gap_audit_validation = load_json(AI_ROOT / "reports" / "p587_enzyme_agent_result_validation_boundary_gap_audit_validation_report.json")
    p588_enzyme_agent_result_safety_regression_boundary_gap_audit = load_json(AI_ROOT / "reports" / "p588_enzyme_agent_result_safety_regression_boundary_gap_audit_report.json")
    p588_enzyme_agent_result_safety_regression_boundary_gap_audit_validation = load_json(AI_ROOT / "reports" / "p588_enzyme_agent_result_safety_regression_boundary_gap_audit_validation_report.json")
    p589_enzyme_agent_trace_audit_boundary_gap_audit = load_json(AI_ROOT / "reports" / "p589_enzyme_agent_trace_audit_boundary_gap_audit_report.json")
    p589_enzyme_agent_trace_audit_boundary_gap_audit_validation = load_json(AI_ROOT / "reports" / "p589_enzyme_agent_trace_audit_boundary_gap_audit_validation_report.json")
    p590_enzyme_agent_controlled_release_order_current_boundary_gap_audit = load_json(AI_ROOT / "reports" / "p590_enzyme_agent_controlled_release_order_current_boundary_gap_audit_report.json")
    p590_enzyme_agent_controlled_release_order_current_boundary_gap_audit_validation = load_json(AI_ROOT / "reports" / "p590_enzyme_agent_controlled_release_order_current_boundary_gap_audit_validation_report.json")
    p591_governance_readiness_boundary_gap_audit = load_json(AI_ROOT / "reports" / "p591_governance_readiness_boundary_gap_audit_report.json")
    p591_governance_readiness_boundary_gap_audit_validation = load_json(AI_ROOT / "reports" / "p591_governance_readiness_boundary_gap_audit_validation_report.json")
    p592_biosecurity_readiness_boundary_gap_audit = load_json(AI_ROOT / "reports" / "p592_biosecurity_readiness_boundary_gap_audit_report.json")
    p592_biosecurity_readiness_boundary_gap_audit_validation = load_json(AI_ROOT / "reports" / "p592_biosecurity_readiness_boundary_gap_audit_validation_report.json")
    p593_workstream_acceptance_boundary_gap_audit = load_json(AI_ROOT / "reports" / "p593_workstream_acceptance_boundary_gap_audit_report.json")
    p593_workstream_acceptance_boundary_gap_audit_validation = load_json(AI_ROOT / "reports" / "p593_workstream_acceptance_boundary_gap_audit_validation_report.json")
    p594_sequence_ip_fto_decision_boundary_gap_audit = load_json(AI_ROOT / "reports" / "p594_sequence_ip_fto_decision_boundary_gap_audit_report.json")
    p594_sequence_ip_fto_decision_boundary_gap_audit_validation = load_json(AI_ROOT / "reports" / "p594_sequence_ip_fto_decision_boundary_gap_audit_validation_report.json")
    p595_model_claim_fail_closed_consistency_boundary_gap_audit = load_json(AI_ROOT / "reports" / "p595_model_claim_fail_closed_consistency_boundary_gap_audit_report.json")
    p595_model_claim_fail_closed_consistency_boundary_gap_audit_validation = load_json(AI_ROOT / "reports" / "p595_model_claim_fail_closed_consistency_boundary_gap_audit_validation_report.json")
    p596_external_data_source_registry_boundary_gap_audit = load_json(AI_ROOT / "reports" / "p596_external_data_source_registry_boundary_gap_audit_report.json")
    p596_external_data_source_registry_boundary_gap_audit_validation = load_json(AI_ROOT / "reports" / "p596_external_data_source_registry_boundary_gap_audit_validation_report.json")
    p597_operator_review_status_boundary_gap_audit = load_json(AI_ROOT / "reports" / "p597_operator_review_status_boundary_gap_audit_report.json")
    p597_operator_review_status_boundary_gap_audit_validation = load_json(AI_ROOT / "reports" / "p597_operator_review_status_boundary_gap_audit_validation_report.json")
    p598_human_review_release_consistency_boundary_gap_audit = load_json(AI_ROOT / "reports" / "p598_human_review_release_consistency_boundary_gap_audit_report.json")
    p598_human_review_release_consistency_boundary_gap_audit_validation = load_json(AI_ROOT / "reports" / "p598_human_review_release_consistency_boundary_gap_audit_validation_report.json")
    p599_claim_promotion_decision_boundary_gap_audit = load_json(AI_ROOT / "reports" / "p599_claim_promotion_decision_boundary_gap_audit_report.json")
    p599_claim_promotion_decision_boundary_gap_audit_validation = load_json(AI_ROOT / "reports" / "p599_claim_promotion_decision_boundary_gap_audit_validation_report.json")
    p600_claim_readiness_policy_current_boundary_gap_audit = load_json(AI_ROOT / "reports" / "p600_claim_readiness_policy_current_boundary_gap_audit_report.json")
    p600_claim_readiness_policy_current_boundary_gap_audit_validation = load_json(AI_ROOT / "reports" / "p600_claim_readiness_policy_current_boundary_gap_audit_validation_report.json")
    p601_structure_feature_hard_gate_operator_packet_boundary_gap_audit = load_json(AI_ROOT / "reports" / "p601_structure_feature_hard_gate_operator_packet_boundary_gap_audit_report.json")
    p601_structure_feature_hard_gate_operator_packet_boundary_gap_audit_validation = load_json(AI_ROOT / "reports" / "p601_structure_feature_hard_gate_operator_packet_boundary_gap_audit_validation_report.json")
    p602_wet_lab_hard_gate_operator_packet_boundary_gap_audit = load_json(AI_ROOT / "reports" / "p602_wet_lab_hard_gate_operator_packet_boundary_gap_audit_report.json")
    p602_wet_lab_hard_gate_operator_packet_boundary_gap_audit_validation = load_json(AI_ROOT / "reports" / "p602_wet_lab_hard_gate_operator_packet_boundary_gap_audit_validation_report.json")
    p603_benchmark_hard_gate_operator_packet_boundary_gap_audit = load_json(AI_ROOT / "reports" / "p603_benchmark_hard_gate_operator_packet_boundary_gap_audit_report.json")
    p603_benchmark_hard_gate_operator_packet_boundary_gap_audit_validation = load_json(AI_ROOT / "reports" / "p603_benchmark_hard_gate_operator_packet_boundary_gap_audit_validation_report.json")
    p604_substrate_fit_hard_gate_operator_packet_boundary_gap_audit = load_json(AI_ROOT / "reports" / "p604_substrate_fit_hard_gate_operator_packet_boundary_gap_audit_report.json")
    p604_substrate_fit_hard_gate_operator_packet_boundary_gap_audit_validation = load_json(AI_ROOT / "reports" / "p604_substrate_fit_hard_gate_operator_packet_boundary_gap_audit_validation_report.json")
    p605_review_draft_formal_boundary_gap_audit = load_json(AI_ROOT / "reports" / "p605_review_draft_formal_boundary_gap_audit_report.json")
    p605_review_draft_formal_boundary_gap_audit_validation = load_json(AI_ROOT / "reports" / "p605_review_draft_formal_boundary_gap_audit_validation_report.json")
    p606_activity_risk_formal_label_decision_boundary_gap_audit = load_json(AI_ROOT / "reports" / "p606_activity_risk_formal_label_decision_boundary_gap_audit_report.json")
    p606_activity_risk_formal_label_decision_boundary_gap_audit_validation = load_json(AI_ROOT / "reports" / "p606_activity_risk_formal_label_decision_boundary_gap_audit_validation_report.json")
    p607_activity_risk_training_lineage_boundary_gap_audit = load_json(AI_ROOT / "reports" / "p607_activity_risk_training_lineage_boundary_gap_audit_report.json")
    p607_activity_risk_training_lineage_boundary_gap_audit_validation = load_json(AI_ROOT / "reports" / "p607_activity_risk_training_lineage_boundary_gap_audit_validation_report.json")
    p608_feedback_training_import_semantic_guard_boundary_gap_audit = load_json(AI_ROOT / "reports" / "p608_feedback_training_import_semantic_guard_boundary_gap_audit_report.json")
    p608_feedback_training_import_semantic_guard_boundary_gap_audit_validation = load_json(AI_ROOT / "reports" / "p608_feedback_training_import_semantic_guard_boundary_gap_audit_validation_report.json")
    p609_wet_lab_feedback_import_reconciliation_boundary_gap_audit = load_json(AI_ROOT / "reports" / "p609_wet_lab_feedback_import_reconciliation_boundary_gap_audit_report.json")
    p609_wet_lab_feedback_import_reconciliation_boundary_gap_audit_validation = load_json(AI_ROOT / "reports" / "p609_wet_lab_feedback_import_reconciliation_boundary_gap_audit_validation_report.json")
    p610_positive_claim_gate_quarantine_boundary_gap_audit = load_json(AI_ROOT / "reports" / "p610_positive_claim_gate_quarantine_boundary_gap_audit_report.json")
    p610_positive_claim_gate_quarantine_boundary_gap_audit_validation = load_json(AI_ROOT / "reports" / "p610_positive_claim_gate_quarantine_boundary_gap_audit_validation_report.json")
    p611_activity_risk_training_import_label_boundary_gap_audit = load_json(AI_ROOT / "reports" / "p611_activity_risk_training_import_label_boundary_gap_audit_report.json")
    p611_activity_risk_training_import_label_boundary_gap_audit_validation = load_json(AI_ROOT / "reports" / "p611_activity_risk_training_import_label_boundary_gap_audit_validation_report.json")
    p612_activity_risk_label_replicate_preflight_boundary_gap_audit = load_json(AI_ROOT / "reports" / "p612_activity_risk_label_replicate_preflight_boundary_gap_audit_report.json")
    p612_activity_risk_label_replicate_preflight_boundary_gap_audit_validation = load_json(AI_ROOT / "reports" / "p612_activity_risk_label_replicate_preflight_boundary_gap_audit_validation_report.json")
    p613_feature_coverage_by_head_group_boundary_gap_audit = load_json(AI_ROOT / "reports" / "p613_feature_coverage_by_head_group_boundary_gap_audit_report.json")
    p613_feature_coverage_by_head_group_boundary_gap_audit_validation = load_json(AI_ROOT / "reports" / "p613_feature_coverage_by_head_group_boundary_gap_audit_validation_report.json")
    p614_feature_coverage_gap_queue_boundary_gap_audit = load_json(AI_ROOT / "reports" / "p614_feature_coverage_gap_queue_boundary_gap_audit_report.json")
    p614_feature_coverage_gap_queue_boundary_gap_audit_validation = load_json(AI_ROOT / "reports" / "p614_feature_coverage_gap_queue_boundary_gap_audit_validation_report.json")
    p615_feature_label_boundary_quarantine_gap_audit = load_json(AI_ROOT / "reports" / "p615_feature_label_boundary_quarantine_gap_audit_report.json")
    p615_feature_label_boundary_quarantine_gap_audit_validation = load_json(AI_ROOT / "reports" / "p615_feature_label_boundary_quarantine_gap_audit_validation_report.json")
    p616_benchmark_score_cache_validation_boundary_gap_audit = load_json(AI_ROOT / "reports" / "p616_benchmark_score_cache_validation_boundary_gap_audit_report.json")
    p616_benchmark_score_cache_validation_boundary_gap_audit_validation = load_json(AI_ROOT / "reports" / "p616_benchmark_score_cache_validation_boundary_gap_audit_validation_report.json")
    p617_benchmark_coverage_dashboard_boundary_gap_audit = load_json(AI_ROOT / "reports" / "p617_benchmark_coverage_dashboard_boundary_gap_audit_report.json")
    p617_benchmark_coverage_dashboard_boundary_gap_audit_validation = load_json(AI_ROOT / "reports" / "p617_benchmark_coverage_dashboard_boundary_gap_audit_validation_report.json")
    p618_five_head_benchmark_gap_plan_boundary_gap_audit = load_json(AI_ROOT / "reports" / "p618_five_head_benchmark_gap_plan_boundary_gap_audit_report.json")
    p618_five_head_benchmark_gap_plan_boundary_gap_audit_validation = load_json(AI_ROOT / "reports" / "p618_five_head_benchmark_gap_plan_boundary_gap_audit_validation_report.json")
    p619_benchmark_lane_machine_prereview_boundary_gap_audit = load_json(AI_ROOT / "reports" / "p619_benchmark_lane_machine_prereview_boundary_gap_audit_report.json")
    p619_benchmark_lane_machine_prereview_boundary_gap_audit_validation = load_json(AI_ROOT / "reports" / "p619_benchmark_lane_machine_prereview_boundary_gap_audit_validation_report.json")
    p620_benchmark_lane_status_aggregate_boundary_gap_audit = load_json(AI_ROOT / "reports" / "p620_benchmark_lane_status_aggregate_boundary_gap_audit_report.json")
    p620_benchmark_lane_status_aggregate_boundary_gap_audit_validation = load_json(AI_ROOT / "reports" / "p620_benchmark_lane_status_aggregate_boundary_gap_audit_validation_report.json")
    p621_ddg_executable_probe_boundary_gap_audit = load_json(AI_ROOT / "reports" / "p621_ddg_executable_probe_boundary_gap_audit_report.json")
    p621_ddg_executable_probe_boundary_gap_audit_validation = load_json(AI_ROOT / "reports" / "p621_ddg_executable_probe_boundary_gap_audit_validation_report.json")
    p622_pyrosetta_physical_smoke_boundary_gap_audit = load_json(AI_ROOT / "reports" / "p622_pyrosetta_physical_smoke_boundary_gap_audit_report.json")
    p622_pyrosetta_physical_smoke_boundary_gap_audit_validation = load_json(AI_ROOT / "reports" / "p622_pyrosetta_physical_smoke_boundary_gap_audit_validation_report.json")
    p623_pyrosetta_verified_ddg_feature_boundary_gap_audit = load_json(AI_ROOT / "reports" / "p623_pyrosetta_verified_ddg_feature_boundary_gap_audit_report.json")
    p623_pyrosetta_verified_ddg_feature_boundary_gap_audit_validation = load_json(AI_ROOT / "reports" / "p623_pyrosetta_verified_ddg_feature_boundary_gap_audit_validation_report.json")
    p624_foldx_physical_smoke_boundary_gap_audit = load_json(AI_ROOT / "reports" / "p624_foldx_physical_smoke_boundary_gap_audit_report.json")
    p624_foldx_physical_smoke_boundary_gap_audit_validation = load_json(AI_ROOT / "reports" / "p624_foldx_physical_smoke_boundary_gap_audit_validation_report.json")
    p625_ddg_backend_operator_packet_boundary_gap_audit = load_json(AI_ROOT / "reports" / "p625_ddg_backend_operator_packet_boundary_gap_audit_report.json")
    p625_ddg_backend_operator_packet_boundary_gap_audit_validation = load_json(AI_ROOT / "reports" / "p625_ddg_backend_operator_packet_boundary_gap_audit_validation_report.json")
    p626_rosetta_physical_smoke_boundary_gap_audit = load_json(AI_ROOT / "reports" / "p626_rosetta_physical_smoke_boundary_gap_audit_report.json")
    p626_rosetta_physical_smoke_boundary_gap_audit_validation = load_json(AI_ROOT / "reports" / "p626_rosetta_physical_smoke_boundary_gap_audit_validation_report.json")
    p627_pyrosetta_verified_mutation_ddg_concordance_boundary_gap_audit = load_json(AI_ROOT / "reports" / "p627_pyrosetta_verified_mutation_ddg_concordance_boundary_gap_audit_report.json")
    p627_pyrosetta_verified_mutation_ddg_concordance_boundary_gap_audit_validation = load_json(AI_ROOT / "reports" / "p627_pyrosetta_verified_mutation_ddg_concordance_boundary_gap_audit_validation_report.json")
    p628_pyrosetta_local_install_probe_boundary_gap_audit = load_json(AI_ROOT / "reports" / "p628_pyrosetta_local_install_probe_boundary_gap_audit_report.json")
    p628_pyrosetta_local_install_probe_boundary_gap_audit_validation = load_json(AI_ROOT / "reports" / "p628_pyrosetta_local_install_probe_boundary_gap_audit_validation_report.json")
    p629_ddg_physical_runtime_receipt_preflight_boundary_gap_audit = load_json(AI_ROOT / "reports" / "p629_ddg_physical_runtime_receipt_preflight_boundary_gap_audit_report.json")
    p629_ddg_physical_runtime_receipt_preflight_boundary_gap_audit_validation = load_json(AI_ROOT / "reports" / "p629_ddg_physical_runtime_receipt_preflight_boundary_gap_audit_validation_report.json")
    p630_ddg_backend_runtime_receipt_validation_boundary_gap_audit = load_json(AI_ROOT / "reports" / "p630_ddg_backend_runtime_receipt_validation_boundary_gap_audit_report.json")
    p630_ddg_backend_runtime_receipt_validation_boundary_gap_audit_validation = load_json(AI_ROOT / "reports" / "p630_ddg_backend_runtime_receipt_validation_boundary_gap_audit_validation_report.json")
    p631_ddg_physical_smoke_harness_boundary_gap_audit = load_json(AI_ROOT / "reports" / "p631_ddg_physical_smoke_harness_boundary_gap_audit_report.json")
    p631_ddg_physical_smoke_harness_boundary_gap_audit_validation = load_json(AI_ROOT / "reports" / "p631_ddg_physical_smoke_harness_boundary_gap_audit_validation_report.json")
    p632_ddg_proxy_physics_claim_boundary_gap_audit = load_json(AI_ROOT / "reports" / "p632_ddg_proxy_physics_claim_boundary_gap_audit_report.json")
    p632_ddg_proxy_physics_claim_boundary_gap_audit_validation = load_json(AI_ROOT / "reports" / "p632_ddg_proxy_physics_claim_boundary_gap_audit_validation_report.json")
    p633_execution_receipt_freshness_boundary_gap_audit = load_json(AI_ROOT / "reports" / "p633_execution_receipt_freshness_boundary_gap_audit_report.json")
    p633_execution_receipt_freshness_boundary_gap_audit_validation = load_json(AI_ROOT / "reports" / "p633_execution_receipt_freshness_boundary_gap_audit_validation_report.json")
    p634_parallel_hard_gate_execution_boundary_gap_audit = load_json(AI_ROOT / "reports" / "p634_parallel_hard_gate_execution_boundary_gap_audit_report.json")
    p634_parallel_hard_gate_execution_boundary_gap_audit_validation = load_json(AI_ROOT / "reports" / "p634_parallel_hard_gate_execution_boundary_gap_audit_validation_report.json")
    p635_ddg_backend_failure_boundary_gap_audit = load_json(AI_ROOT / "reports" / "p635_ddg_backend_failure_boundary_gap_audit_report.json")
    p635_ddg_backend_failure_boundary_gap_audit_validation = load_json(AI_ROOT / "reports" / "p635_ddg_backend_failure_boundary_gap_audit_validation_report.json")
    p636_human_review_closeout_current_boundary_gap_audit = load_json(AI_ROOT / "reports" / "p636_human_review_closeout_current_boundary_gap_audit_report.json")
    p636_human_review_closeout_current_boundary_gap_audit_validation = load_json(AI_ROOT / "reports" / "p636_human_review_closeout_current_boundary_gap_audit_validation_report.json")
    p637_operator_work_receipt_manifest_current_boundary_gap_audit = load_json(AI_ROOT / "reports" / "p637_operator_work_receipt_manifest_current_boundary_gap_audit_report.json")
    p637_operator_work_receipt_manifest_current_boundary_gap_audit_validation = load_json(AI_ROOT / "reports" / "p637_operator_work_receipt_manifest_current_boundary_gap_audit_validation_report.json")
    p638_top_tier_ready_to_verify_current_boundary_gap_audit = load_json(AI_ROOT / "reports" / "p638_top_tier_ready_to_verify_current_boundary_gap_audit_report.json")
    p638_top_tier_ready_to_verify_current_boundary_gap_audit_validation = load_json(AI_ROOT / "reports" / "p638_top_tier_ready_to_verify_current_boundary_gap_audit_validation_report.json")
    p639_non_human_ready_to_verify_current_boundary_gap_audit = load_json(AI_ROOT / "reports" / "p639_non_human_ready_to_verify_current_boundary_gap_audit_report.json")
    p639_non_human_ready_to_verify_current_boundary_gap_audit_validation = load_json(AI_ROOT / "reports" / "p639_non_human_ready_to_verify_current_boundary_gap_audit_validation_report.json")
    p640_ready_to_verify_promotion_current_boundary_gap_audit = load_json(AI_ROOT / "reports" / "p640_ready_to_verify_promotion_current_boundary_gap_audit_report.json")
    p640_ready_to_verify_promotion_current_boundary_gap_audit_validation = load_json(AI_ROOT / "reports" / "p640_ready_to_verify_promotion_current_boundary_gap_audit_validation_report.json")
    p641_p0_today_closeout_plan = load_json(AI_ROOT / "reports" / "p641_p0_today_closeout_plan_report.json")
    p641_p0_today_closeout_plan_validation = load_json(AI_ROOT / "reports" / "p641_p0_today_closeout_plan_validation_report.json")
    p642_p0_external_input_packet_manifest = load_json(AI_ROOT / "reports" / "p642_p0_external_input_packet_manifest_report.json")
    p642_p0_external_input_packet_manifest_validation = load_json(AI_ROOT / "reports" / "p642_p0_external_input_packet_manifest_validation_report.json")
    p643_p0_external_input_dispatch_board = load_json(AI_ROOT / "reports" / "p643_p0_external_input_dispatch_board_report.json")
    p643_p0_external_input_dispatch_board_validation = load_json(AI_ROOT / "reports" / "p643_p0_external_input_dispatch_board_validation_report.json")
    p644_p0_external_input_handoff_receipt_board = load_json(AI_ROOT / "reports" / "p644_p0_external_input_handoff_receipt_board_report.json")
    p644_p0_external_input_handoff_receipt_board_validation = load_json(AI_ROOT / "reports" / "p644_p0_external_input_handoff_receipt_board_validation_report.json")
    p645_p0_external_input_response_slot_registry = load_json(AI_ROOT / "reports" / "p645_p0_external_input_response_slot_registry_report.json")
    p645_p0_external_input_response_slot_registry_validation = load_json(AI_ROOT / "reports" / "p645_p0_external_input_response_slot_registry_validation_report.json")
    p646_p0_external_input_response_intake_queue = load_json(AI_ROOT / "reports" / "p646_p0_external_input_response_intake_queue_report.json")
    p646_p0_external_input_response_intake_queue_validation = load_json(AI_ROOT / "reports" / "p646_p0_external_input_response_intake_queue_validation_report.json")
    p647_p0_external_input_response_validation_preflight = load_json(AI_ROOT / "reports" / "p647_p0_external_input_response_validation_preflight_report.json")
    p647_p0_external_input_response_validation_preflight_validation = load_json(AI_ROOT / "reports" / "p647_p0_external_input_response_validation_preflight_validation_report.json")
    p648_p0_external_input_response_schema_contract = load_json(AI_ROOT / "reports" / "p648_p0_external_input_response_schema_contract_report.json")
    p648_p0_external_input_response_schema_contract_validation = load_json(AI_ROOT / "reports" / "p648_p0_external_input_response_schema_contract_validation_report.json")
    p649_p0_external_input_response_evidence_quarantine = load_json(AI_ROOT / "reports" / "p649_p0_external_input_response_evidence_quarantine_report.json")
    p649_p0_external_input_response_evidence_quarantine_validation = load_json(AI_ROOT / "reports" / "p649_p0_external_input_response_evidence_quarantine_validation_report.json")
    p650_p0_external_input_response_decision_routing = load_json(AI_ROOT / "reports" / "p650_p0_external_input_response_decision_routing_report.json")
    p650_p0_external_input_response_decision_routing_validation = load_json(AI_ROOT / "reports" / "p650_p0_external_input_response_decision_routing_validation_report.json")
    p651_p0_external_input_formal_intake_dry_run_guard = load_json(AI_ROOT / "reports" / "p651_p0_external_input_formal_intake_dry_run_guard_report.json")
    p651_p0_external_input_formal_intake_dry_run_guard_validation = load_json(AI_ROOT / "reports" / "p651_p0_external_input_formal_intake_dry_run_guard_validation_report.json")
    p652_p0_external_input_closeout_readiness_gate = load_json(AI_ROOT / "reports" / "p652_p0_external_input_closeout_readiness_gate_report.json")
    p652_p0_external_input_closeout_readiness_gate_validation = load_json(AI_ROOT / "reports" / "p652_p0_external_input_closeout_readiness_gate_validation_report.json")
    p653_p0_external_input_closeout_blocker_ledger = load_json(AI_ROOT / "reports" / "p653_p0_external_input_closeout_blocker_ledger_report.json")
    p653_p0_external_input_closeout_blocker_ledger_validation = load_json(AI_ROOT / "reports" / "p653_p0_external_input_closeout_blocker_ledger_validation_report.json")
    p654_p0_external_input_blocker_escalation_queue = load_json(AI_ROOT / "reports" / "p654_p0_external_input_blocker_escalation_queue_report.json")
    p654_p0_external_input_blocker_escalation_queue_validation = load_json(AI_ROOT / "reports" / "p654_p0_external_input_blocker_escalation_queue_validation_report.json")
    p655_p0_external_input_blocker_escalation_status_board = load_json(AI_ROOT / "reports" / "p655_p0_external_input_blocker_escalation_status_board_report.json")
    p655_p0_external_input_blocker_escalation_status_board_validation = load_json(AI_ROOT / "reports" / "p655_p0_external_input_blocker_escalation_status_board_validation_report.json")
    p656_p0_external_input_blocker_escalation_watchlist = load_json(AI_ROOT / "reports" / "p656_p0_external_input_blocker_escalation_watchlist_report.json")
    p656_p0_external_input_blocker_escalation_watchlist_validation = load_json(AI_ROOT / "reports" / "p656_p0_external_input_blocker_escalation_watchlist_validation_report.json")
    p657_p0_external_input_blocker_escalation_review_queue = load_json(AI_ROOT / "reports" / "p657_p0_external_input_blocker_escalation_review_queue_report.json")
    p657_p0_external_input_blocker_escalation_review_queue_validation = load_json(AI_ROOT / "reports" / "p657_p0_external_input_blocker_escalation_review_queue_validation_report.json")
    p658_p0_external_input_blocker_escalation_review_status_board = load_json(AI_ROOT / "reports" / "p658_p0_external_input_blocker_escalation_review_status_board_report.json")
    p658_p0_external_input_blocker_escalation_review_status_board_validation = load_json(AI_ROOT / "reports" / "p658_p0_external_input_blocker_escalation_review_status_board_validation_report.json")
    p659_p0_external_input_blocker_escalation_review_watchlist = load_json(AI_ROOT / "reports" / "p659_p0_external_input_blocker_escalation_review_watchlist_report.json")
    p659_p0_external_input_blocker_escalation_review_watchlist_validation = load_json(AI_ROOT / "reports" / "p659_p0_external_input_blocker_escalation_review_watchlist_validation_report.json")
    p660_p0_external_input_blocker_review_watchlist_aging_audit = load_json(AI_ROOT / "reports" / "p660_p0_external_input_blocker_review_watchlist_aging_audit_report.json")
    p660_p0_external_input_blocker_review_watchlist_aging_audit_validation = load_json(AI_ROOT / "reports" / "p660_p0_external_input_blocker_review_watchlist_aging_audit_validation_report.json")
    p661_p0_external_input_blocker_review_owner_assignment_gap_audit = load_json(AI_ROOT / "reports" / "p661_p0_external_input_blocker_review_owner_assignment_gap_audit_report.json")
    p661_p0_external_input_blocker_review_owner_assignment_gap_audit_validation = load_json(AI_ROOT / "reports" / "p661_p0_external_input_blocker_review_owner_assignment_gap_audit_validation_report.json")
    p662_p0_external_input_evidence_missing_matrix = load_json(AI_ROOT / "reports" / "p662_p0_external_input_evidence_missing_matrix_report.json")
    p662_p0_external_input_evidence_missing_matrix_validation = load_json(AI_ROOT / "reports" / "p662_p0_external_input_evidence_missing_matrix_validation_report.json")
    p663_p0_formal_decision_readiness_false_positive_guard = load_json(AI_ROOT / "reports" / "p663_p0_formal_decision_readiness_false_positive_guard_report.json")
    p663_p0_formal_decision_readiness_false_positive_guard_validation = load_json(AI_ROOT / "reports" / "p663_p0_formal_decision_readiness_false_positive_guard_validation_report.json")
    p664_p0_closeout_non_approval_receipt_audit = load_json(AI_ROOT / "reports" / "p664_p0_closeout_non_approval_receipt_audit_report.json")
    p664_p0_closeout_non_approval_receipt_audit_validation = load_json(AI_ROOT / "reports" / "p664_p0_closeout_non_approval_receipt_audit_validation_report.json")
    p665_p0_closeout_non_approval_watchlist = load_json(AI_ROOT / "reports" / "p665_p0_closeout_non_approval_watchlist_report.json")
    p665_p0_closeout_non_approval_watchlist_validation = load_json(AI_ROOT / "reports" / "p665_p0_closeout_non_approval_watchlist_validation_report.json")
    p666_p0_closeout_owner_review_queue = load_json(AI_ROOT / "reports" / "p666_p0_closeout_owner_review_queue_report.json")
    p666_p0_closeout_owner_review_queue_validation = load_json(AI_ROOT / "reports" / "p666_p0_closeout_owner_review_queue_validation_report.json")
    p667_p0_formal_intake_non_write_guard_audit = load_json(AI_ROOT / "reports" / "p667_p0_formal_intake_non_write_guard_audit_report.json")
    p667_p0_formal_intake_non_write_guard_audit_validation = load_json(AI_ROOT / "reports" / "p667_p0_formal_intake_non_write_guard_audit_validation_report.json")
    p668_p0_training_label_non_import_guard_audit = load_json(AI_ROOT / "reports" / "p668_p0_training_label_non_import_guard_audit_report.json")
    p668_p0_training_label_non_import_guard_audit_validation = load_json(AI_ROOT / "reports" / "p668_p0_training_label_non_import_guard_audit_validation_report.json")
    p669_p0_release_claim_non_promotion_guard_audit = load_json(AI_ROOT / "reports" / "p669_p0_release_claim_non_promotion_guard_audit_report.json")
    p669_p0_release_claim_non_promotion_guard_audit_validation = load_json(AI_ROOT / "reports" / "p669_p0_release_claim_non_promotion_guard_audit_validation_report.json")
    p670_p0_release_claim_non_promotion_status_board = load_json(AI_ROOT / "reports" / "p670_p0_release_claim_non_promotion_status_board_report.json")
    p670_p0_release_claim_non_promotion_status_board_validation = load_json(AI_ROOT / "reports" / "p670_p0_release_claim_non_promotion_status_board_validation_report.json")
    p671_p0_model_claim_non_assertion_guard_audit = load_json(AI_ROOT / "reports" / "p671_p0_model_claim_non_assertion_guard_audit_report.json")
    p671_p0_model_claim_non_assertion_guard_audit_validation = load_json(AI_ROOT / "reports" / "p671_p0_model_claim_non_assertion_guard_audit_validation_report.json")
    p672_p0_customer_delivery_non_authorization_guard_audit = load_json(AI_ROOT / "reports" / "p672_p0_customer_delivery_non_authorization_guard_audit_report.json")
    p672_p0_customer_delivery_non_authorization_guard_audit_validation = load_json(AI_ROOT / "reports" / "p672_p0_customer_delivery_non_authorization_guard_audit_validation_report.json")
    p673_p0_production_execution_non_authorization_guard_audit = load_json(AI_ROOT / "reports" / "p673_p0_production_execution_non_authorization_guard_audit_report.json")
    p673_p0_production_execution_non_authorization_guard_audit_validation = load_json(AI_ROOT / "reports" / "p673_p0_production_execution_non_authorization_guard_audit_validation_report.json")
    p674_p0_terminal_blocked_state_rollup_audit = load_json(AI_ROOT / "reports" / "p674_p0_terminal_blocked_state_rollup_audit_report.json")
    p674_p0_terminal_blocked_state_rollup_audit_validation = load_json(AI_ROOT / "reports" / "p674_p0_terminal_blocked_state_rollup_audit_validation_report.json")
    p687_p0_real_input_closeout_readiness_gate = load_json(AI_ROOT / "reports" / "p687_p0_real_input_closeout_readiness_gate_report.json")
    p687_p0_real_input_closeout_readiness_gate_validation = load_json(AI_ROOT / "reports" / "p687_p0_real_input_closeout_readiness_gate_validation_report.json")
    p688_p0_real_input_closeout_blocker_ledger = load_json(AI_ROOT / "reports" / "p688_p0_real_input_closeout_blocker_ledger_report.json")
    p688_p0_real_input_closeout_blocker_ledger_validation = load_json(AI_ROOT / "reports" / "p688_p0_real_input_closeout_blocker_ledger_validation_report.json")
    p689_p0_real_input_blocker_escalation_queue = load_json(AI_ROOT / "reports" / "p689_p0_real_input_blocker_escalation_queue_report.json")
    p689_p0_real_input_blocker_escalation_queue_validation = load_json(AI_ROOT / "reports" / "p689_p0_real_input_blocker_escalation_queue_validation_report.json")
    p690_p0_real_input_blocker_escalation_status_board = load_json(AI_ROOT / "reports" / "p690_p0_real_input_blocker_escalation_status_board_report.json")
    p690_p0_real_input_blocker_escalation_status_board_validation = load_json(AI_ROOT / "reports" / "p690_p0_real_input_blocker_escalation_status_board_validation_report.json")
    p691_p0_real_input_blocker_escalation_watchlist = load_json(AI_ROOT / "reports" / "p691_p0_real_input_blocker_escalation_watchlist_report.json")
    p691_p0_real_input_blocker_escalation_watchlist_validation = load_json(AI_ROOT / "reports" / "p691_p0_real_input_blocker_escalation_watchlist_validation_report.json")
    p692_p0_real_input_blocker_escalation_review_queue = load_json(AI_ROOT / "reports" / "p692_p0_real_input_blocker_escalation_review_queue_report.json")
    p692_p0_real_input_blocker_escalation_review_queue_validation = load_json(AI_ROOT / "reports" / "p692_p0_real_input_blocker_escalation_review_queue_validation_report.json")
    p693_p0_real_input_blocker_escalation_review_status_board = load_json(AI_ROOT / "reports" / "p693_p0_real_input_blocker_escalation_review_status_board_report.json")
    p693_p0_real_input_blocker_escalation_review_status_board_validation = load_json(AI_ROOT / "reports" / "p693_p0_real_input_blocker_escalation_review_status_board_validation_report.json")
    p694_p0_real_input_blocker_escalation_review_watchlist = load_json(AI_ROOT / "reports" / "p694_p0_real_input_blocker_escalation_review_watchlist_report.json")
    p694_p0_real_input_blocker_escalation_review_watchlist_validation = load_json(AI_ROOT / "reports" / "p694_p0_real_input_blocker_escalation_review_watchlist_validation_report.json")
    p695_p0_real_input_blocker_escalation_review_watchlist_aging_audit = load_json(AI_ROOT / "reports" / "p695_p0_real_input_blocker_escalation_review_watchlist_aging_audit_report.json")
    p695_p0_real_input_blocker_escalation_review_watchlist_aging_audit_validation = load_json(AI_ROOT / "reports" / "p695_p0_real_input_blocker_escalation_review_watchlist_aging_audit_validation_report.json")
    p696_p0_real_input_blocker_escalation_review_owner_assignment_gap_audit = load_json(AI_ROOT / "reports" / "p696_p0_real_input_blocker_escalation_review_owner_assignment_gap_audit_report.json")
    p696_p0_real_input_blocker_escalation_review_owner_assignment_gap_audit_validation = load_json(AI_ROOT / "reports" / "p696_p0_real_input_blocker_escalation_review_owner_assignment_gap_audit_validation_report.json")
    p697_p0_real_input_blocker_escalation_review_evidence_missing_matrix = load_json(AI_ROOT / "reports" / "p697_p0_real_input_blocker_escalation_review_evidence_missing_matrix_report.json")
    p697_p0_real_input_blocker_escalation_review_evidence_missing_matrix_validation = load_json(AI_ROOT / "reports" / "p697_p0_real_input_blocker_escalation_review_evidence_missing_matrix_validation_report.json")
    p698_p0_real_input_formal_decision_readiness_false_positive_guard = load_json(AI_ROOT / "reports" / "p698_p0_real_input_formal_decision_readiness_false_positive_guard_report.json")
    p698_p0_real_input_formal_decision_readiness_false_positive_guard_validation = load_json(AI_ROOT / "reports" / "p698_p0_real_input_formal_decision_readiness_false_positive_guard_validation_report.json")
    p699_p0_real_input_formal_decision_readiness_status_board = load_json(AI_ROOT / "reports" / "p699_p0_real_input_formal_decision_readiness_status_board_report.json")
    p699_p0_real_input_formal_decision_readiness_status_board_validation = load_json(AI_ROOT / "reports" / "p699_p0_real_input_formal_decision_readiness_status_board_validation_report.json")
    p700_p0_real_input_pending_build_checklist = load_json(AI_ROOT / "reports" / "p700_p0_real_input_pending_build_checklist_report.json")
    p700_p0_real_input_pending_build_checklist_validation = load_json(AI_ROOT / "reports" / "p700_p0_real_input_pending_build_checklist_validation_report.json")
    safe_pipeline_receipt_atomicity_regression = load_json(AI_ROOT / "reports" / "safe_training_pipeline_receipt_atomicity_regression_report.json")
    safe_pipeline_current_receipt = load_json(AI_ROOT / "reports" / "safe_training_pipeline_current_receipt_validation_report.json")
    safe_pipeline_current_receipt_regression = load_json(AI_ROOT / "reports" / "safe_training_pipeline_current_receipt_regression_report.json")
    safe_pipeline_bootstrap_release_regression = load_json(AI_ROOT / "reports" / "safe_training_pipeline_bootstrap_release_consistency_regression_report.json")
    terminal_defer_mode_regression = load_json(AI_ROOT / "reports" / "local_release_terminal_defer_mode_regression_report.json")
    stage25_current_receipt = load_json(AI_ROOT / "reports" / "stage25_fail_closed_validation_current_receipt_validation_report.json")
    stage25_current_regression = load_json(AI_ROOT / "reports" / "stage25_fail_closed_validation_current_receipt_regression_report.json")
    post_source_receipt_validation = load_json(AI_ROOT / "reports" / "stage25_post_source_drop_rerun_receipt_validation_20260806.json")
    post_source_receipt_regression = load_json(AI_ROOT / "reports" / "stage25_post_source_drop_rerun_receipt_regression_20260806.json")
    post_source_validation_current = load_json(AI_ROOT / "reports" / "stage25_post_source_drop_rerun_validation_current_20260810.json")
    post_source_validation_current_regression = load_json(AI_ROOT / "reports" / "stage25_post_source_drop_rerun_validation_current_regression_20260810.json")
    post_source_independent_policy = load_json(AI_ROOT / "reports" / "stage25_post_source_drop_rerun_independent_policy_validation_20260810.json")
    post_source_independent_policy_regression = load_json(AI_ROOT / "reports" / "stage25_post_source_drop_rerun_independent_policy_regression_20260810.json")
    post_source_independent_policy_current = load_json(AI_ROOT / "reports" / "stage25_post_source_drop_rerun_independent_policy_current_20260810.json")
    post_source_independent_policy_current_regression = load_json(AI_ROOT / "reports" / "stage25_post_source_drop_rerun_independent_policy_current_regression_20260810.json")
    model_claim_fail_closed_consistency = load_json(AI_ROOT / "reports" / "model_claim_fail_closed_consistency_report.json")
    local_release_fail_closed_consistency = load_json(AI_ROOT / "reports" / "local_release_manifest_fail_closed_consistency_validation_report.json")
    local_release_consistency_atomicity_regression = load_json(AI_ROOT / "reports" / "local_release_consistency_receipt_atomicity_regression_report.json")
    local_release_consistency_current = load_json(AI_ROOT / "reports" / "local_release_consistency_receipt_current_validation_report.json")
    local_release_consistency_current_regression = load_json(AI_ROOT / "reports" / "local_release_consistency_receipt_current_regression_report.json")
    local_release_consistency_semantic_policy = load_json(AI_ROOT / "reports" / "local_release_consistency_semantic_policy_validation_report.json")
    local_release_consistency_semantic_policy_regression = load_json(AI_ROOT / "reports" / "local_release_consistency_semantic_policy_regression_report.json")
    local_release_consistency_semantic_policy_current = load_json(AI_ROOT / "reports" / "local_release_consistency_semantic_policy_current_validation_report.json")
    local_release_consistency_semantic_policy_current_regression = load_json(AI_ROOT / "reports" / "local_release_consistency_semantic_policy_current_regression_report.json")
    local_release_consistency_semantic_policy_atomicity_regression = load_json(AI_ROOT / "reports" / "local_release_consistency_semantic_policy_atomicity_regression_report.json")
    local_release_safety_guard_links = load_json(AI_ROOT / "reports" / "local_release_safety_guard_link_validation_report.json")
    local_release_safety_guard_links_atomicity = load_json(AI_ROOT / "reports" / "local_release_safety_guard_links_atomicity_regression_report.json")
    local_release_safety_guard_links_current = load_json(AI_ROOT / "reports" / "local_release_safety_guard_links_current_validation_report.json")
    local_release_safety_guard_links_current_regression = load_json(AI_ROOT / "reports" / "local_release_safety_guard_links_current_regression_report.json")
    local_release_safety_guard_links_current_regression_atomicity = load_json(AI_ROOT / "reports" / "local_release_safety_guard_links_current_regression_atomicity_regression_report.json")
    review_draft_formal_boundary = load_json(AI_ROOT / "reports" / "review_draft_formal_boundary_validation_report.json")
    no_review_draft_training_leakage = load_json(AI_ROOT / "reports" / "no_review_draft_training_leakage_validation_report.json")
    draft_namespace_isolation = load_json(AI_ROOT / "reports" / "draft_namespace_isolation_validation_report.json")
    no_unreviewed_positive_gate_flags = load_json(AI_ROOT / "reports" / "no_unreviewed_positive_gate_flags_validation_report.json")
    report_positive_claim_gate_quarantine = load_json(AI_ROOT / "reports" / "report_positive_claim_gate_quarantine_validation_report.json")
    reviewed_structure_graph = load_json(AI_ROOT / "reports" / "reviewed_structure_graph_feature_report.json")
    reviewed_structure_graph_validation = load_json(AI_ROOT / "reports" / "reviewed_structure_graph_validation_report.json")
    structure_feature_model_contract = load_json(AI_ROOT / "reports" / "structure_feature_model_contract_report.json")
    structure_feature_model_contract_validation = load_json(AI_ROOT / "reports" / "structure_feature_model_contract_validation_report.json")
    msa_trusted_cache_intake = load_json(AI_ROOT / "reports" / "msa_trusted_cache_intake_report.json")
    msa_cache_validation = load_json(AI_ROOT / "reports" / "msa_conservation_cache_validation_report.json")
    mmseqs2_local_runtime = load_json(AI_ROOT / "reports" / "mmseqs2_local_runtime_report.json")
    mmseqs_homolog_database = load_json(AI_ROOT / "reports" / "mmseqs_homolog_database_report.json")
    msa_runtime = load_json(AI_ROOT / "reports" / "msa_runtime_readiness_report.json")
    msa_mmseqs_cache_build = load_json(AI_ROOT / "reports" / "msa_mmseqs_swissprot_cache_build_report.json")
    benchmark_score_cache_intake = load_json(AI_ROOT / "reports" / "benchmark_score_cache_intake_report.json")
    benchmark_score_cache_validation = load_json(AI_ROOT / "reports" / "benchmark_score_cache_validation_report.json")
    kwb_activity_risk_smoke_benchmark = load_json(AI_ROOT / "reports" / "kwb_activity_risk_smoke_benchmark_report.json")
    kwb_activity_risk_smoke_benchmark_validation = load_json(AI_ROOT / "reports" / "kwb_activity_risk_smoke_benchmark_validation_report.json")
    fireprot_protherm_stability_benchmark = load_json(AI_ROOT / "reports" / "fireprot_protherm_stability_benchmark_report.json")
    atom3d_msp_benchmark = load_json(AI_ROOT / "reports" / "atom3d_msp_benchmark_report.json")
    atom3d_msp_benchmark_validation = load_json(AI_ROOT / "reports" / "atom3d_msp_benchmark_validation_report.json")
    catpred_gotenzymes_reference_benchmark = load_json(
        AI_ROOT / "reports" / "catpred_gotenzymes_reference_benchmark_report.json"
    )
    catpred_gotenzymes_reference_benchmark_validation = load_json(
        AI_ROOT / "reports" / "catpred_gotenzymes_reference_benchmark_validation_report.json"
    )
    posebusters_pose_plausibility_benchmark = load_json(
        AI_ROOT / "reports" / "posebusters_pose_plausibility_benchmark_report.json"
    )
    posebusters_pose_plausibility_benchmark_validation = load_json(
        AI_ROOT / "reports" / "posebusters_pose_plausibility_benchmark_validation_report.json"
    )
    benchmark_coverage_dashboard = load_json(AI_ROOT / "reports" / "benchmark_coverage_dashboard.json")
    benchmark_coverage_dashboard_validation = load_json(AI_ROOT / "reports" / "benchmark_coverage_dashboard_validation_report.json")
    benchmark_readiness_packet = load_json(AI_ROOT / "reports" / "benchmark_readiness_packet_report.json")
    benchmark_readiness_packet_validation = load_json(AI_ROOT / "reports" / "benchmark_readiness_packet_validation_report.json")
    benchmark_readiness_summary = benchmark_readiness_packet.get("summary") or {}
    proteingym_local_source = load_json(AI_ROOT / "reports" / "proteingym_local_source_report.json")
    external_stability_label_sources = load_json(AI_ROOT / "reports" / "external_stability_label_source_audit_report.json")
    pyrosetta_local_install_probe = load_json(AI_ROOT / "reports" / "pyrosetta_local_install_probe_report.json")
    pyrosetta_local_install_probe_validation = load_json(AI_ROOT / "reports" / "pyrosetta_local_install_probe_validation_report.json")
    pyrosetta_physical_smoke_bootstrap = load_json(AI_ROOT / "reports" / "pyrosetta_physical_smoke_bootstrap_report.json")
    rosetta_physical_smoke_bootstrap = load_json(AI_ROOT / "reports" / "rosetta_physical_smoke_bootstrap_report.json")
    verified_mutation_structure_candidates = load_json(AI_ROOT / "reports" / "verified_mutation_structure_candidate_report.json")
    verified_mutation_structure_mapping = load_json(AI_ROOT / "reports" / "verified_mutation_structure_mapping_candidate_report.json")
    verified_mutation_structure_mapping_validation = load_json(
        AI_ROOT / "reports" / "verified_mutation_structure_mapping_candidate_validation_report.json"
    )
    pyrosetta_verified_mutation_ddg_features = load_json(
        AI_ROOT / "reports" / "pyrosetta_verified_mutation_ddg_feature_report.json"
    )
    pyrosetta_verified_mutation_ddg_features_validation = load_json(
        AI_ROOT / "reports" / "pyrosetta_verified_mutation_ddg_feature_validation_report.json"
    )
    pyrosetta_multichain_ddg_concordance = load_json(
        AI_ROOT / "reports" / "pyrosetta_verified_mutation_ddg_concordance_report.json"
    )
    pyrosetta_multichain_ddg_concordance_validation = load_json(
        AI_ROOT / "reports" / "pyrosetta_verified_mutation_ddg_concordance_validation_report.json"
    )
    ddg_executable_probe = load_json(AI_ROOT / "reports" / "ddg_executable_probe_report.json")
    fireprot_import_receipt = load_json(AI_ROOT / "reports" / "fireprot_curated_stability_import_candidate_receipt.json")
    fireprot_import_leakage = load_json(AI_ROOT / "reports" / "fireprot_curated_stability_import_leakage_report.json")
    fireprot_direction = load_json(AI_ROOT / "reports" / "fireprot_curated_stability_direction_normalization_report.json")
    fireprot_schema_mapping = load_json(AI_ROOT / "reports" / "fireprot_curated_kwb_schema_mapping_report.json")
    fireprot_leakage_review = load_json(AI_ROOT / "reports" / "fireprot_curated_import_leakage_review_report.json")
    fireprot_dedup = load_json(AI_ROOT / "reports" / "fireprot_curated_dedup_aggregation_report.json")
    fireprot_dedup_review = load_json(AI_ROOT / "reports" / "fireprot_dedup_review_packet_report.json")
    fireprot_dedup_decisions = load_json(AI_ROOT / "reports" / "fireprot_dedup_review_decision_validation_report.json")
    fireprot_reviewed_import = load_json(AI_ROOT / "reports" / "fireprot_reviewed_import_candidate_report.json")
    ddg_backend = load_json(AI_ROOT / "reports" / "ddg_backend_readiness_report.json")
    ddg_failure_diagnostic = load_json(AI_ROOT / "reports" / "ddg_backend_failure_diagnostic_report.json")
    ddg_proxy_not_physics = load_json(AI_ROOT / "reports" / "ddg_proxy_not_physics_claim_validation_report.json")
    ddg_model_consumption_contract = load_json(AI_ROOT / "reports" / "ddg_model_consumption_contract_report.json")
    ddg_model_consumption_contract_validation = load_json(AI_ROOT / "reports" / "ddg_model_consumption_contract_validation_report.json")
    ddg_local_runtime_discovery = load_json(AI_ROOT / "reports" / "ddg_local_runtime_discovery_report.json")
    ddg_backend_operator_packets = load_json(AI_ROOT / "reports" / "ddg_backend_operator_packet_report.json")
    ddg_backend_operator_packet_validation = load_json(AI_ROOT / "reports" / "ddg_backend_operator_packet_validation_report.json")
    ddg_backend_runtime_receipts = load_json(AI_ROOT / "reports" / "ddg_backend_runtime_receipt_validation_report.json")
    ddg_physical_runtime_receipt_preflight_validation = load_json(AI_ROOT / "reports" / "ddg_physical_runtime_receipt_preflight_validation_report.json")
    ddg_physical_smoke_harness = load_json(AI_ROOT / "reports" / "ddg_physical_smoke_harness_report.json")
    ddg_physical_smoke_harness_validation = load_json(AI_ROOT / "reports" / "ddg_physical_smoke_harness_validation_report.json")
    foldx_parser_contract = load_json(AI_ROOT / "reports" / "foldx_buildmodel_parser_contract_report.json")
    foldx_parser_contract_validation = load_json(AI_ROOT / "reports" / "foldx_buildmodel_parser_contract_validation_report.json")
    foldx_physical_smoke_bootstrap = load_json(AI_ROOT / "reports" / "foldx_physical_smoke_bootstrap_report.json")
    foldx_physical_smoke_bootstrap_validation = load_json(AI_ROOT / "reports" / "foldx_physical_smoke_bootstrap_validation_report.json")
    foldx_execution_plan_blocker = load_json(AI_ROOT / "reports" / "stage25_foldx_execution_plan_blocker_validation_20260806.json")
    qc_fail_rate_calibration = load_json(AI_ROOT / "reports" / "kwb_qc_fail_rate_calibration_benchmark_report.json")
    qc_fail_rate_calibration_validation = load_json(AI_ROOT / "reports" / "kwb_qc_fail_rate_calibration_benchmark_validation_report.json")
    plate_level_feedback_benchmark = load_json(AI_ROOT / "reports" / "kwb_plate_level_feedback_benchmark_report.json")
    plate_level_feedback_benchmark_validation = load_json(AI_ROOT / "reports" / "kwb_plate_level_feedback_benchmark_validation_report.json")
    activity_risk_plate_feedback_benchmark = load_json(AI_ROOT / "reports" / "kwb_activity_risk_plate_feedback_benchmark_report.json")
    activity_risk_plate_feedback_benchmark_validation = load_json(AI_ROOT / "reports" / "kwb_activity_risk_plate_feedback_benchmark_validation_report.json")
    thermompnn_local_source = load_json(AI_ROOT / "reports" / "thermompnn_local_source_report.json")
    thermompnn_smoke = load_json(AI_ROOT / "reports" / "thermompnn_venus15b_smoke_report.json")
    feedback_trainability = load_json(AI_ROOT / "reports" / "experiment_feedback_trainability_audit_report.json")
    feedback_source_decisions = load_json(AI_ROOT / "reports" / "experiment_feedback_source_review_decision_validation_report.json")
    feedback_source_intake_candidates = load_json(AI_ROOT / "reports" / "experiment_feedback_source_intake_candidate_report.json")
    venus15b_asset_audit = load_json(AI_ROOT / "reports" / "venus15b_experiment_asset_audit_report.json")
    venus15b_feedback = load_json(AI_ROOT / "reports" / "venus15b_feedback_import_report.json")
    venus15b_strict_candidate = load_json(AI_ROOT / "reports" / "kwb_venus15b_strict_holdout_candidate_audit_report.json")
    substrate_identity_candidates = load_json(AI_ROOT / "reports" / "substrate_identity_evidence_candidate_report.json")
    substrate_identity_validation = load_json(AI_ROOT / "reports" / "substrate_identity_evidence_candidate_validation_report.json")
    hard_gate_review_packets = load_json(AI_ROOT / "reports" / "hard_gate_review_packet_report.json")
    hard_gate_review_packet_validation = load_json(AI_ROOT / "reports" / "hard_gate_review_packet_validation_report.json")
    hard_gate_decision_bridge = load_json(AI_ROOT / "reports" / "hard_gate_decision_benchmark_bridge_report.json")
    hard_gate_decision_bridge_validation = load_json(AI_ROOT / "reports" / "hard_gate_decision_benchmark_bridge_validation_report.json")
    benchmark_lane_machine_prereview = load_json(AI_ROOT / "reports" / "benchmark_lane_machine_prereview_report.json")
    benchmark_lane_status_aggregate = load_json(AI_ROOT / "reports" / "benchmark_lane_status_aggregate_report.json")
    wet_lab_mutant_library_assets = load_json(AI_ROOT / "reports" / "wet_lab_mutant_library_asset_audit_report.json")
    wet_lab_mutant_library_feedback = load_json(AI_ROOT / "reports" / "wet_lab_mutant_library_feedback_candidate_report.json")
    wet_lab_mutant_library_feedback_qc = load_json(AI_ROOT / "reports" / "wet_lab_mutant_library_feedback_qc_matrix_report.json")
    wet_lab_mutant_library_sequence_evidence = load_json(AI_ROOT / "reports" / "wet_lab_mutant_library_sequence_evidence_audit_report.json")
    wet_lab_mutant_library_sequence_intake = load_json(AI_ROOT / "reports" / "wet_lab_mutant_library_project_sequence_intake_validation_report.json")
    wet_lab_mutant_library_numbering_audit = load_json(AI_ROOT / "reports" / "wet_lab_mutant_library_numbering_audit_from_project_sequences_report.json")
    wet_lab_mutant_library_authorization = load_json(AI_ROOT / "reports" / "wet_lab_mutant_library_feedback_authorization_validation_report.json")
    wet_lab_mutant_library_authorization_worklist = load_json(AI_ROOT / "reports" / "wet_lab_mutant_library_feedback_authorization_worklist_report.json")
    wet_lab_mutant_library_authorization_worklist_validation = load_json(AI_ROOT / "reports" / "wet_lab_mutant_library_feedback_authorization_worklist_validation_report.json")
    wet_lab_mutant_library_authorization_dashboard = load_json(AI_ROOT / "reports" / "wet_lab_mutant_library_feedback_authorization_dashboard.json")
    wet_lab_mutant_library_authorization_dashboard_validation = load_json(AI_ROOT / "reports" / "wet_lab_mutant_library_feedback_authorization_dashboard_validation_report.json")
    wet_lab_mutant_library_authorization_gap_matrix = load_json(AI_ROOT / "reports" / "wet_lab_mutant_library_feedback_authorization_gap_matrix_report.json")
    wet_lab_mutant_library_authorization_gap_matrix_validation = load_json(AI_ROOT / "reports" / "wet_lab_mutant_library_feedback_authorization_gap_matrix_validation_report.json")
    wet_lab_mutant_library_authorization_operator_checklist = load_json(AI_ROOT / "reports" / "wet_lab_mutant_library_feedback_authorization_operator_checklist_report.json")
    wet_lab_mutant_library_authorization_operator_checklist_validation = load_json(AI_ROOT / "reports" / "wet_lab_mutant_library_feedback_authorization_operator_checklist_validation_report.json")
    wet_lab_mutant_library_authorization_operator_receipts = load_json(AI_ROOT / "reports" / "wet_lab_mutant_library_feedback_authorization_operator_receipt_report.json")
    wet_lab_mutant_library_authorization_operator_receipt_validation = load_json(AI_ROOT / "reports" / "wet_lab_mutant_library_feedback_authorization_operator_receipt_validation_report.json")
    wet_lab_mutant_library_authorization_execution_queue = load_json(AI_ROOT / "reports" / "wet_lab_mutant_library_feedback_authorization_execution_queue_report.json")
    wet_lab_mutant_library_authorization_execution_queue_validation = load_json(AI_ROOT / "reports" / "wet_lab_mutant_library_feedback_authorization_execution_queue_validation_report.json")
    wet_lab_mutant_library_authorization_execution_queue_operator_packets = load_json(AI_ROOT / "reports" / "wet_lab_mutant_library_feedback_authorization_execution_queue_operator_packet_report.json")
    wet_lab_mutant_library_authorization_execution_queue_operator_packet_validation = load_json(AI_ROOT / "reports" / "wet_lab_mutant_library_feedback_authorization_execution_queue_operator_packet_validation_report.json")
    wet_lab_mutant_library_authorization_execution_queue_operator_packet_receipts = load_json(AI_ROOT / "reports" / "wet_lab_mutant_library_feedback_authorization_execution_queue_operator_packet_receipt_report.json")
    wet_lab_mutant_library_authorization_execution_queue_operator_packet_receipt_validation = load_json(AI_ROOT / "reports" / "wet_lab_mutant_library_feedback_authorization_execution_queue_operator_packet_receipt_validation_report.json")
    wet_lab_mutant_library_authorization_closeout_board = load_json(AI_ROOT / "reports" / "wet_lab_mutant_library_feedback_authorization_closeout_board_report.json")
    wet_lab_mutant_library_authorization_closeout_board_validation = load_json(AI_ROOT / "reports" / "wet_lab_mutant_library_feedback_authorization_closeout_board_validation_report.json")
    wet_lab_mutant_library_authorization_closeout_operator_packets = load_json(AI_ROOT / "reports" / "wet_lab_mutant_library_feedback_authorization_closeout_operator_packet_report.json")
    wet_lab_mutant_library_authorization_closeout_operator_packet_validation = load_json(AI_ROOT / "reports" / "wet_lab_mutant_library_feedback_authorization_closeout_operator_packet_validation_report.json")
    numbering_review_packet_validation = load_json(AI_ROOT / "reports" / "numbering_review_packet_validation_report.json")
    numbering_review_packet_board = load_json(AI_ROOT / "reports" / "numbering_review_packet_board_report.json")
    numbering_review_briefing = load_json(AI_ROOT / "reports" / "numbering_review_briefing.json")
    numbering_review_briefing_validation = load_json(AI_ROOT / "reports" / "numbering_review_briefing_validation_report.json")
    numbering_review_briefing_status = load_json(AI_ROOT / "reports" / "numbering_review_briefing_status_board_report.json")
    numbering_review_briefing_status_validation = load_json(AI_ROOT / "reports" / "numbering_review_briefing_status_board_validation_report.json")
    numbering_deep_audit = load_json(AI_ROOT / "reports" / "numbering_deep_audit_report.json")
    numbering_semantic_conflict = load_json(AI_ROOT / "reports" / "numbering_decision_semantic_conflict_report.json")
    numbering_operator_queue = load_json(AI_ROOT / "reports" / "numbering_review_operator_queue.json")
    wet_lab_mutant_library_preflight = load_json(AI_ROOT / "reports" / "wet_lab_mutant_library_feedback_preflight_report.json")
    wet_lab_feedback_authorization_contract = load_json(AI_ROOT / "reports" / "wet_lab_feedback_authorization_contract_report.json")
    wet_lab_feedback_authorization_contract_validation = load_json(AI_ROOT / "reports" / "wet_lab_feedback_authorization_contract_validation_report.json")
    wet_lab_mutant_library_apply_plan = load_json(AI_ROOT / "reports" / "wet_lab_mutant_library_feedback_intake_apply_plan_report.json")
    wet_lab_feedback_apply_duplicate_audit = load_json(AI_ROOT / "reports" / "wet_lab_feedback_apply_duplicate_audit_report.json")
    wet_lab_feedback_apply_duplicate_audit_validation = load_json(AI_ROOT / "reports" / "wet_lab_feedback_apply_duplicate_audit_validation_report.json")
    wet_lab_mutant_library_operator_packets = load_json(AI_ROOT / "reports" / "wet_lab_mutant_library_operator_packet_report.json")
    wet_lab_mutant_library_operator_packet_validation = load_json(AI_ROOT / "reports" / "wet_lab_mutant_library_operator_packet_validation_report.json")
    wet_lab_mutant_library_unlock_status = load_json(AI_ROOT / "reports" / "wet_lab_mutant_library_unlock_status_report.json")
    strict_msa_features = load_json(AI_ROOT / "reports" / "strict_msa_site_feature_report.json")
    msa_baseline = load_json(AI_ROOT / "reports" / "repaired_supervised_msa_baseline_eval.json")
    domain_multi_occurrence = load_json(AI_ROOT / "reports" / "domain_multi_occurrence_feature_report.json")
    domain_interpro_packets = load_json(AI_ROOT / "reports" / "domain_interpro_review_packet_report.json")
    label_provenance = load_json(AI_ROOT / "reports" / "label_provenance_audit_report.json")
    feedback_training_import_semantic_guard = load_json(AI_ROOT / "reports" / "feedback_training_import_semantic_guard_report.json")
    feedback_training_import_semantic_guard_validation = load_json(AI_ROOT / "reports" / "feedback_training_import_semantic_guard_validation_report.json")
    training_label_import_contract = load_json(AI_ROOT / "reports" / "training_label_import_contract_report.json")
    training_label_import_contract_validation = load_json(AI_ROOT / "reports" / "training_label_import_contract_validation_report.json")
    wet_lab_feedback_import_reconciliation = load_json(AI_ROOT / "reports" / "wet_lab_feedback_import_reconciliation_report.json")
    wet_lab_feedback_import_reconciliation_validation = load_json(AI_ROOT / "reports" / "wet_lab_feedback_import_reconciliation_validation_report.json")
    parallel_hard_gate_workstreams = load_json(AI_ROOT / "reports" / "parallel_hard_gate_workstreams_board_report.json")
    parallel_hard_gate_workstreams_validation = load_json(AI_ROOT / "reports" / "parallel_hard_gate_workstreams_board_validation_report.json")
    human_preflight_package = load_json(AI_ROOT / "reports" / "human_preflight_package_report.json")
    human_preflight_package_validation = load_json(AI_ROOT / "reports" / "human_preflight_package_validation_report.json")
    parallel_hard_gate_execution_receipts = load_json(AI_ROOT / "reports" / "parallel_hard_gate_execution_receipts_report.json")
    parallel_hard_gate_execution_receipts_validation = load_json(AI_ROOT / "reports" / "parallel_hard_gate_execution_receipts_validation_report.json")
    next_hard_gate_attack_wave = load_json(AI_ROOT / "reports" / "next_hard_gate_attack_wave_report.json")
    next_hard_gate_attack_wave_validation = load_json(AI_ROOT / "reports" / "next_hard_gate_attack_wave_validation_report.json")
    five_head_training_execution_contract = load_json(AI_ROOT / "reports" / "five_head_training_execution_contract_report.json")
    five_head_training_execution_contract_validation = load_json(AI_ROOT / "reports" / "five_head_training_execution_contract_validation_report.json")
    five_head_training_threshold = load_json(AI_ROOT / "reports" / "five_head_training_threshold_report.json")
    five_head_training_threshold_validation = load_json(AI_ROOT / "reports" / "five_head_training_threshold_validation_report.json")
    five_head_training_sample_gap_queue = load_json(AI_ROOT / "reports" / "five_head_training_sample_gap_queue_report.json")
    five_head_training_sample_gap_queue_validation = load_json(AI_ROOT / "reports" / "five_head_training_sample_gap_queue_validation_report.json")
    proteingym_benchmark_scorecard = load_json(AI_ROOT / "reports" / "proteingym_benchmark_scorecard_report.json")
    flip2_amylase_benchmark = load_json(AI_ROOT / "reports" / "flip2_amylase_benchmark_report.json")
    flip2_amylase_benchmark_validation = load_json(AI_ROOT / "reports" / "flip2_amylase_benchmark_validation_report.json")
    activity_risk_label_replicate_preflight = load_json(AI_ROOT / "reports" / "activity_risk_label_replicate_preflight_report.json")
    activity_risk_label_replicate_preflight_validation = load_json(AI_ROOT / "reports" / "activity_risk_label_replicate_preflight_validation_report.json")
    activity_risk_formal_label_decision = load_json(AI_ROOT / "reports" / "activity_risk_formal_label_decision_report.json")
    activity_risk_formal_label_decision_validation = load_json(AI_ROOT / "reports" / "activity_risk_formal_label_decision_validation_report.json")
    activity_risk_training_import_label = load_json(AI_ROOT / "reports" / "activity_risk_training_import_label_report.json")
    activity_risk_training_import_label_validation = load_json(AI_ROOT / "reports" / "activity_risk_training_import_label_validation_report.json")
    model_quality_hard_gate_contract = load_json(AI_ROOT / "reports" / "model_quality_hard_gate_contract_report.json")
    model_quality_hard_gate_contract_validation = load_json(AI_ROOT / "reports" / "model_quality_hard_gate_contract_validation_report.json")
    model_artifact_claim_guard = load_json(AI_ROOT / "reports" / "model_artifact_claim_guard_report.json")
    model_artifact_claim_guard_validation = load_json(AI_ROOT / "reports" / "model_artifact_claim_guard_validation_report.json")
    execution_receipt_artifact_freshness = load_json(AI_ROOT / "reports" / "execution_receipt_artifact_freshness_validation_report.json")
    feature_label_boundary_quarantine = load_json(AI_ROOT / "reports" / "feature_label_boundary_quarantine_report.json")
    tool_lane_evidence = load_json(AI_ROOT / "reports" / "tool_lane_evidence_pack.json")
    tool_lane_evidence_validation = load_json(AI_ROOT / "reports" / "tool_lane_evidence_pack_validation_report.json")
    human_target_gap = load_json(AI_ROOT / "reports" / "human_target_contract_gap_report.json")
    human_target_gap_validation = load_json(AI_ROOT / "reports" / "human_target_contract_gap_validation_report.json")
    human_target_source_runtime = load_json(AI_ROOT / "reports" / "human_target_source_runtime_manifest.json")
    human_target_source_runtime_validation = load_json(AI_ROOT / "reports" / "human_target_source_runtime_manifest_validation_report.json")
    human_target_blocked_source_index = load_json(AI_ROOT / "reports" / "human_target_blocked_source_manifest_index.json")
    human_target_blocked_source_index_validation = load_json(AI_ROOT / "reports" / "human_target_blocked_source_manifest_index_validation_report.json")
    human_target_source_unlock_checklist = load_json(AI_ROOT / "reports" / "human_target_source_unlock_checklist_report.json")
    human_target_source_unlock_checklist_validation = load_json(AI_ROOT / "reports" / "human_target_source_unlock_checklist_validation_report.json")
    fulltext_intake = load_json(ENZYME_DB_ROOT / "fulltext_intake_validation_report_20260806.json")
    fulltext_queue = load_json(ENZYME_DB_ROOT / "fulltext_source_locator_review_queue_validation_report_20260806.json")
    fulltext_draft = load_json(ENZYME_DB_ROOT / "fulltext_evidence_draft_20260806.json")
    reviewer_package = load_json(ENZYME_DB_ROOT / "stage25_reviewer_package_20260806.json")
    local_release_guard_coverage = load_json(AI_ROOT / "reports" / "local_release_guard_coverage_validation_report.json")
    human_target_projection_checks = local_release_guard_coverage.get("human_target_projection_checks") or {}
    artifacts = data_manifest.get("artifacts", [])
    missing = [artifact.get("path") for artifact in artifacts if not artifact.get("exists")]
    blocked_capabilities = [
        "model_quality_claim",
        "customer_delivery",
        "approved_for_ordering",
        "IP/FTO conclusion",
        "external tool production use",
        "advanced feature cache execution",
    ]
    p648_p652_summary: dict[str, Any] = {}
    for prefix, layer_report, layer_validation, count_fields, extra_zero_fields in (
        (
            "p648_p0_external_input_response_schema_contract",
            p648_p0_external_input_response_schema_contract,
            p648_p0_external_input_response_schema_contract_validation,
            ("schema_contract_rows", "open_schema_contract_rows", "empty_schema_contract_rows", "blocked_schema_contract_rows"),
            ("schema_contract_approved_rows",),
        ),
        (
            "p649_p0_external_input_response_evidence_quarantine",
            p649_p0_external_input_response_evidence_quarantine,
            p649_p0_external_input_response_evidence_quarantine_validation,
            ("evidence_quarantine_rows", "open_evidence_quarantine_rows", "empty_evidence_quarantine_rows", "blocked_evidence_quarantine_rows"),
            ("evidence_quarantine_released_rows", "evidence_promoted_to_decision_rows"),
        ),
        (
            "p650_p0_external_input_response_decision_routing",
            p650_p0_external_input_response_decision_routing,
            p650_p0_external_input_response_decision_routing_validation,
            ("decision_routing_rows", "open_decision_routing_rows", "empty_decision_routing_rows", "blocked_decision_routing_rows"),
            ("decision_route_executed_rows", "routed_to_formal_review_rows"),
        ),
        (
            "p651_p0_external_input_formal_intake_dry_run_guard",
            p651_p0_external_input_formal_intake_dry_run_guard,
            p651_p0_external_input_formal_intake_dry_run_guard_validation,
            ("formal_intake_dry_run_rows", "open_formal_intake_dry_run_rows", "empty_formal_intake_dry_run_rows", "blocked_formal_intake_dry_run_rows"),
            ("formal_intake_dry_run_executed_rows", "formal_intake_dry_run_passed_rows"),
        ),
        (
            "p652_p0_external_input_closeout_readiness_gate",
            p652_p0_external_input_closeout_readiness_gate,
            p652_p0_external_input_closeout_readiness_gate_validation,
            ("closeout_gate_rows", "open_closeout_gate_rows", "empty_closeout_gate_rows", "blocked_closeout_gate_rows"),
            ("closeout_ready_rows", "completion_ready_observed_rows"),
        ),
        (
            "p653_p0_external_input_closeout_blocker_ledger",
            p653_p0_external_input_closeout_blocker_ledger,
            p653_p0_external_input_closeout_blocker_ledger_validation,
            ("blocker_ledger_rows", "open_blocker_ledger_rows", "empty_blocker_ledger_rows", "blocked_blocker_ledger_rows"),
            ("blocker_resolved_rows", "closeout_ready_rows", "completion_ready_observed_rows"),
        ),
        (
            "p654_p0_external_input_blocker_escalation_queue",
            p654_p0_external_input_blocker_escalation_queue,
            p654_p0_external_input_blocker_escalation_queue_validation,
            ("blocker_escalation_rows", "open_blocker_escalation_rows", "empty_blocker_escalation_rows", "blocked_blocker_escalation_rows"),
            ("escalation_sent_rows", "escalation_acknowledged_rows", "blocker_resolved_rows", "closeout_ready_rows", "completion_ready_observed_rows"),
        ),
        (
            "p655_p0_external_input_blocker_escalation_status_board",
            p655_p0_external_input_blocker_escalation_status_board,
            p655_p0_external_input_blocker_escalation_status_board_validation,
            ("blocker_status_rows", "open_blocker_status_rows", "empty_blocker_status_rows", "blocked_blocker_status_rows"),
            ("escalation_sent_rows", "escalation_acknowledged_rows", "blocker_resolved_rows", "closeout_ready_rows", "completion_ready_observed_rows"),
        ),
        (
            "p656_p0_external_input_blocker_escalation_watchlist",
            p656_p0_external_input_blocker_escalation_watchlist,
            p656_p0_external_input_blocker_escalation_watchlist_validation,
            ("blocker_watch_rows", "open_blocker_watch_rows", "empty_blocker_watch_rows", "blocked_blocker_watch_rows"),
            ("escalation_sent_rows", "escalation_acknowledged_rows", "blocker_resolved_rows", "closeout_ready_rows", "completion_ready_observed_rows"),
        ),
        (
            "p657_p0_external_input_blocker_escalation_review_queue",
            p657_p0_external_input_blocker_escalation_review_queue,
            p657_p0_external_input_blocker_escalation_review_queue_validation,
            ("blocker_review_rows", "open_blocker_review_rows", "empty_blocker_review_rows", "blocked_blocker_review_rows"),
            ("escalation_reviewed_rows", "escalation_sent_rows", "escalation_acknowledged_rows", "blocker_resolved_rows", "closeout_ready_rows", "completion_ready_observed_rows"),
        ),
        (
            "p658_p0_external_input_blocker_escalation_review_status_board",
            p658_p0_external_input_blocker_escalation_review_status_board,
            p658_p0_external_input_blocker_escalation_review_status_board_validation,
            ("blocker_review_status_rows", "open_blocker_review_status_rows", "empty_blocker_review_status_rows", "blocked_blocker_review_status_rows"),
            ("escalation_reviewed_rows", "escalation_sent_rows", "escalation_acknowledged_rows", "blocker_resolved_rows", "closeout_ready_rows", "completion_ready_observed_rows"),
        ),
        (
            "p659_p0_external_input_blocker_escalation_review_watchlist",
            p659_p0_external_input_blocker_escalation_review_watchlist,
            p659_p0_external_input_blocker_escalation_review_watchlist_validation,
            ("blocker_review_watch_rows", "open_blocker_review_watch_rows", "empty_blocker_review_watch_rows", "blocked_blocker_review_watch_rows"),
            ("escalation_reviewed_rows", "escalation_sent_rows", "escalation_acknowledged_rows", "blocker_resolved_rows", "closeout_ready_rows", "completion_ready_observed_rows"),
        ),
        (
            "p660_p0_external_input_blocker_review_watchlist_aging_audit",
            p660_p0_external_input_blocker_review_watchlist_aging_audit,
            p660_p0_external_input_blocker_review_watchlist_aging_audit_validation,
            ("blocker_review_aging_rows", "open_blocker_review_aging_rows", "empty_blocker_review_aging_rows", "blocked_blocker_review_aging_rows"),
            ("aging_reviewed_rows", "staleness_resolved_rows", "escalation_reviewed_rows", "escalation_sent_rows", "escalation_acknowledged_rows", "blocker_resolved_rows", "closeout_ready_rows", "completion_ready_observed_rows"),
        ),
        (
            "p661_p0_external_input_blocker_review_owner_assignment_gap_audit",
            p661_p0_external_input_blocker_review_owner_assignment_gap_audit,
            p661_p0_external_input_blocker_review_owner_assignment_gap_audit_validation,
            ("blocker_review_owner_gap_rows", "open_blocker_review_owner_gap_rows", "empty_blocker_review_owner_gap_rows", "blocked_blocker_review_owner_gap_rows"),
            ("owner_assigned_rows", "owner_acknowledged_rows", "aging_reviewed_rows", "staleness_resolved_rows", "escalation_reviewed_rows", "escalation_sent_rows", "escalation_acknowledged_rows", "blocker_resolved_rows", "closeout_ready_rows", "completion_ready_observed_rows"),
        ),
        (
            "p662_p0_external_input_evidence_missing_matrix",
            p662_p0_external_input_evidence_missing_matrix,
            p662_p0_external_input_evidence_missing_matrix_validation,
            ("evidence_missing_rows", "open_evidence_missing_rows", "empty_evidence_missing_rows", "blocked_evidence_missing_rows"),
            ("evidence_received_rows", "evidence_validated_rows", "owner_assigned_rows", "owner_acknowledged_rows", "aging_reviewed_rows", "staleness_resolved_rows", "escalation_reviewed_rows", "escalation_sent_rows", "escalation_acknowledged_rows", "blocker_resolved_rows", "closeout_ready_rows", "completion_ready_observed_rows"),
        ),
        (
            "p663_p0_formal_decision_readiness_false_positive_guard",
            p663_p0_formal_decision_readiness_false_positive_guard,
            p663_p0_formal_decision_readiness_false_positive_guard_validation,
            ("formal_decision_false_positive_guard_rows", "open_formal_decision_false_positive_guard_rows", "empty_formal_decision_false_positive_guard_rows", "blocked_formal_decision_false_positive_guard_rows"),
            ("formal_decision_ready_rows", "false_positive_cleared_rows", "evidence_received_rows", "evidence_validated_rows", "owner_assigned_rows", "owner_acknowledged_rows", "aging_reviewed_rows", "staleness_resolved_rows", "escalation_reviewed_rows", "escalation_sent_rows", "escalation_acknowledged_rows", "blocker_resolved_rows", "closeout_ready_rows", "completion_ready_observed_rows"),
        ),
        (
            "p664_p0_closeout_non_approval_receipt_audit",
            p664_p0_closeout_non_approval_receipt_audit,
            p664_p0_closeout_non_approval_receipt_audit_validation,
            ("closeout_non_approval_receipt_rows", "open_closeout_non_approval_receipt_rows", "empty_closeout_non_approval_receipt_rows", "blocked_closeout_non_approval_receipt_rows"),
            ("closeout_approved_rows", "closeout_approval_written_rows", "formal_decision_ready_rows", "false_positive_cleared_rows", "evidence_received_rows", "evidence_validated_rows", "owner_assigned_rows", "owner_acknowledged_rows", "aging_reviewed_rows", "staleness_resolved_rows", "escalation_reviewed_rows", "escalation_sent_rows", "escalation_acknowledged_rows", "blocker_resolved_rows", "closeout_ready_rows", "completion_ready_observed_rows"),
        ),
        (
            "p665_p0_closeout_non_approval_watchlist",
            p665_p0_closeout_non_approval_watchlist,
            p665_p0_closeout_non_approval_watchlist_validation,
            ("closeout_non_approval_watch_rows", "open_closeout_non_approval_watch_rows", "empty_closeout_non_approval_watch_rows", "blocked_closeout_non_approval_watch_rows"),
            ("closeout_watch_reviewed_rows", "closeout_approved_rows", "closeout_approval_written_rows", "formal_decision_ready_rows", "false_positive_cleared_rows", "evidence_received_rows", "evidence_validated_rows", "owner_assigned_rows", "owner_acknowledged_rows", "aging_reviewed_rows", "staleness_resolved_rows", "escalation_reviewed_rows", "escalation_sent_rows", "escalation_acknowledged_rows", "blocker_resolved_rows", "closeout_ready_rows", "completion_ready_observed_rows"),
        ),
        (
            "p666_p0_closeout_owner_review_queue",
            p666_p0_closeout_owner_review_queue,
            p666_p0_closeout_owner_review_queue_validation,
            ("closeout_owner_review_rows", "open_closeout_owner_review_rows", "empty_closeout_owner_review_rows", "blocked_closeout_owner_review_rows"),
            ("closeout_owner_assigned_rows", "closeout_owner_reviewed_rows", "closeout_watch_reviewed_rows", "closeout_approved_rows", "closeout_approval_written_rows", "formal_decision_ready_rows", "false_positive_cleared_rows", "evidence_received_rows", "evidence_validated_rows", "owner_assigned_rows", "owner_acknowledged_rows", "aging_reviewed_rows", "staleness_resolved_rows", "escalation_reviewed_rows", "escalation_sent_rows", "escalation_acknowledged_rows", "blocker_resolved_rows", "closeout_ready_rows", "completion_ready_observed_rows"),
        ),
        (
            "p667_p0_formal_intake_non_write_guard_audit",
            p667_p0_formal_intake_non_write_guard_audit,
            p667_p0_formal_intake_non_write_guard_audit_validation,
            ("formal_intake_non_write_guard_rows", "open_formal_intake_non_write_guard_rows", "empty_formal_intake_non_write_guard_rows", "blocked_formal_intake_non_write_guard_rows"),
            ("formal_intake_guard_reviewed_rows", "formal_intake_write_authorized_rows", "closeout_owner_assigned_rows", "closeout_owner_reviewed_rows", "closeout_watch_reviewed_rows", "closeout_approved_rows", "closeout_approval_written_rows", "formal_decision_ready_rows", "false_positive_cleared_rows", "evidence_received_rows", "evidence_validated_rows", "owner_assigned_rows", "owner_acknowledged_rows", "aging_reviewed_rows", "staleness_resolved_rows", "escalation_reviewed_rows", "escalation_sent_rows", "escalation_acknowledged_rows", "blocker_resolved_rows", "closeout_ready_rows", "completion_ready_observed_rows"),
        ),
        (
            "p668_p0_training_label_non_import_guard_audit",
            p668_p0_training_label_non_import_guard_audit,
            p668_p0_training_label_non_import_guard_audit_validation,
            ("training_label_non_import_guard_rows", "open_training_label_non_import_guard_rows", "empty_training_label_non_import_guard_rows", "blocked_training_label_non_import_guard_rows"),
            ("training_label_guard_reviewed_rows", "training_label_import_authorized_rows", "formal_intake_guard_reviewed_rows", "formal_intake_write_authorized_rows", "closeout_owner_assigned_rows", "closeout_owner_reviewed_rows", "closeout_watch_reviewed_rows", "closeout_approved_rows", "closeout_approval_written_rows", "formal_decision_ready_rows", "false_positive_cleared_rows", "evidence_received_rows", "evidence_validated_rows", "owner_assigned_rows", "owner_acknowledged_rows", "aging_reviewed_rows", "staleness_resolved_rows", "escalation_reviewed_rows", "escalation_sent_rows", "escalation_acknowledged_rows", "blocker_resolved_rows", "closeout_ready_rows", "completion_ready_observed_rows"),
        ),
        (
            "p669_p0_release_claim_non_promotion_guard_audit",
            p669_p0_release_claim_non_promotion_guard_audit,
            p669_p0_release_claim_non_promotion_guard_audit_validation,
            ("release_claim_non_promotion_guard_rows", "open_release_claim_non_promotion_guard_rows", "empty_release_claim_non_promotion_guard_rows", "blocked_release_claim_non_promotion_guard_rows"),
            ("release_claim_guard_reviewed_rows", "release_claim_promoted_rows", "training_label_guard_reviewed_rows", "training_label_import_authorized_rows", "formal_intake_guard_reviewed_rows", "formal_intake_write_authorized_rows", "closeout_owner_assigned_rows", "closeout_owner_reviewed_rows", "closeout_watch_reviewed_rows", "closeout_approved_rows", "closeout_approval_written_rows", "formal_decision_ready_rows", "false_positive_cleared_rows", "evidence_received_rows", "evidence_validated_rows", "owner_assigned_rows", "owner_acknowledged_rows", "aging_reviewed_rows", "staleness_resolved_rows", "escalation_reviewed_rows", "escalation_sent_rows", "escalation_acknowledged_rows", "blocker_resolved_rows", "closeout_ready_rows", "completion_ready_observed_rows"),
        ),
        (
            "p670_p0_release_claim_non_promotion_status_board",
            p670_p0_release_claim_non_promotion_status_board,
            p670_p0_release_claim_non_promotion_status_board_validation,
            ("release_claim_non_promotion_status_rows", "open_release_claim_non_promotion_status_rows", "empty_release_claim_non_promotion_status_rows", "blocked_release_claim_non_promotion_status_rows"),
            ("release_claim_status_reviewed_rows", "release_claim_guard_reviewed_rows", "release_claim_promoted_rows", "training_label_guard_reviewed_rows", "training_label_import_authorized_rows", "formal_intake_guard_reviewed_rows", "formal_intake_write_authorized_rows", "closeout_owner_assigned_rows", "closeout_owner_reviewed_rows", "closeout_watch_reviewed_rows", "closeout_approved_rows", "closeout_approval_written_rows", "formal_decision_ready_rows", "false_positive_cleared_rows", "evidence_received_rows", "evidence_validated_rows", "owner_assigned_rows", "owner_acknowledged_rows", "aging_reviewed_rows", "staleness_resolved_rows", "escalation_reviewed_rows", "escalation_sent_rows", "escalation_acknowledged_rows", "blocker_resolved_rows", "closeout_ready_rows", "completion_ready_observed_rows"),
        ),
        (
            "p671_p0_model_claim_non_assertion_guard_audit",
            p671_p0_model_claim_non_assertion_guard_audit,
            p671_p0_model_claim_non_assertion_guard_audit_validation,
            ("model_claim_non_assertion_guard_rows", "open_model_claim_non_assertion_guard_rows", "empty_model_claim_non_assertion_guard_rows", "blocked_model_claim_non_assertion_guard_rows"),
            ("model_claim_guard_reviewed_rows", "model_claim_asserted_rows", "release_claim_status_reviewed_rows", "release_claim_guard_reviewed_rows", "release_claim_promoted_rows", "training_label_guard_reviewed_rows", "training_label_import_authorized_rows", "formal_intake_guard_reviewed_rows", "formal_intake_write_authorized_rows", "closeout_owner_assigned_rows", "closeout_owner_reviewed_rows", "closeout_watch_reviewed_rows", "closeout_approved_rows", "closeout_approval_written_rows", "formal_decision_ready_rows", "false_positive_cleared_rows", "evidence_received_rows", "evidence_validated_rows", "owner_assigned_rows", "owner_acknowledged_rows", "aging_reviewed_rows", "staleness_resolved_rows", "escalation_reviewed_rows", "escalation_sent_rows", "escalation_acknowledged_rows", "blocker_resolved_rows", "closeout_ready_rows", "completion_ready_observed_rows"),
        ),
        (
            "p672_p0_customer_delivery_non_authorization_guard_audit",
            p672_p0_customer_delivery_non_authorization_guard_audit,
            p672_p0_customer_delivery_non_authorization_guard_audit_validation,
            ("customer_delivery_non_authorization_guard_rows", "open_customer_delivery_non_authorization_guard_rows", "empty_customer_delivery_non_authorization_guard_rows", "blocked_customer_delivery_non_authorization_guard_rows"),
            ("customer_delivery_guard_reviewed_rows", "customer_delivery_authorized_rows", "model_claim_guard_reviewed_rows", "model_claim_asserted_rows", "release_claim_status_reviewed_rows", "release_claim_guard_reviewed_rows", "release_claim_promoted_rows", "training_label_guard_reviewed_rows", "training_label_import_authorized_rows", "formal_intake_guard_reviewed_rows", "formal_intake_write_authorized_rows", "closeout_owner_assigned_rows", "closeout_owner_reviewed_rows", "closeout_watch_reviewed_rows", "closeout_approved_rows", "closeout_approval_written_rows", "formal_decision_ready_rows", "false_positive_cleared_rows", "evidence_received_rows", "evidence_validated_rows", "owner_assigned_rows", "owner_acknowledged_rows", "aging_reviewed_rows", "staleness_resolved_rows", "escalation_reviewed_rows", "escalation_sent_rows", "escalation_acknowledged_rows", "blocker_resolved_rows", "closeout_ready_rows", "completion_ready_observed_rows"),
        ),
        (
            "p673_p0_production_execution_non_authorization_guard_audit",
            p673_p0_production_execution_non_authorization_guard_audit,
            p673_p0_production_execution_non_authorization_guard_audit_validation,
            ("production_execution_non_authorization_guard_rows", "open_production_execution_non_authorization_guard_rows", "empty_production_execution_non_authorization_guard_rows", "blocked_production_execution_non_authorization_guard_rows"),
            ("production_execution_guard_reviewed_rows", "production_execution_authorized_rows", "customer_delivery_guard_reviewed_rows", "customer_delivery_authorized_rows", "model_claim_guard_reviewed_rows", "model_claim_asserted_rows", "release_claim_status_reviewed_rows", "release_claim_guard_reviewed_rows", "release_claim_promoted_rows", "training_label_guard_reviewed_rows", "training_label_import_authorized_rows", "formal_intake_guard_reviewed_rows", "formal_intake_write_authorized_rows", "closeout_owner_assigned_rows", "closeout_owner_reviewed_rows", "closeout_watch_reviewed_rows", "closeout_approved_rows", "closeout_approval_written_rows", "formal_decision_ready_rows", "false_positive_cleared_rows", "evidence_received_rows", "evidence_validated_rows", "owner_assigned_rows", "owner_acknowledged_rows", "aging_reviewed_rows", "staleness_resolved_rows", "escalation_reviewed_rows", "escalation_sent_rows", "escalation_acknowledged_rows", "blocker_resolved_rows", "closeout_ready_rows", "completion_ready_observed_rows"),
        ),
        (
            "p674_p0_terminal_blocked_state_rollup_audit",
            p674_p0_terminal_blocked_state_rollup_audit,
            p674_p0_terminal_blocked_state_rollup_audit_validation,
            ("terminal_blocked_state_rollup_rows", "open_terminal_blocked_state_rollup_rows", "empty_terminal_blocked_state_rollup_rows", "blocked_terminal_blocked_state_rollup_rows"),
            ("terminal_blocked_state_reviewed_rows", "p0_terminal_unblocked_rows", "production_execution_guard_reviewed_rows", "production_execution_authorized_rows", "customer_delivery_guard_reviewed_rows", "customer_delivery_authorized_rows", "model_claim_guard_reviewed_rows", "model_claim_asserted_rows", "release_claim_status_reviewed_rows", "release_claim_guard_reviewed_rows", "release_claim_promoted_rows", "training_label_guard_reviewed_rows", "training_label_import_authorized_rows", "formal_intake_guard_reviewed_rows", "formal_intake_write_authorized_rows", "closeout_owner_assigned_rows", "closeout_owner_reviewed_rows", "closeout_watch_reviewed_rows", "closeout_approved_rows", "closeout_approval_written_rows", "formal_decision_ready_rows", "false_positive_cleared_rows", "evidence_received_rows", "evidence_validated_rows", "owner_assigned_rows", "owner_acknowledged_rows", "aging_reviewed_rows", "staleness_resolved_rows", "escalation_reviewed_rows", "escalation_sent_rows", "escalation_acknowledged_rows", "blocker_resolved_rows", "closeout_ready_rows", "completion_ready_observed_rows"),
        ),
        (
            "p687_p0_real_input_closeout_readiness_gate",
            p687_p0_real_input_closeout_readiness_gate,
            p687_p0_real_input_closeout_readiness_gate_validation,
            ("closeout_gate_rows", "open_closeout_gate_rows", "empty_closeout_gate_rows", "blocked_closeout_gate_rows"),
            ("formal_intake_dry_run_executed_rows", "formal_intake_dry_run_passed_rows", "formal_intake_written_rows", "closeout_ready_rows", "completion_ready_observed_rows", "completion_ready_rows"),
        ),
        (
            "p688_p0_real_input_closeout_blocker_ledger",
            p688_p0_real_input_closeout_blocker_ledger,
            p688_p0_real_input_closeout_blocker_ledger_validation,
            ("blocker_ledger_rows", "open_blocker_ledger_rows", "empty_blocker_ledger_rows", "blocked_blocker_ledger_rows"),
            ("formal_intake_dry_run_executed_rows", "formal_intake_dry_run_passed_rows", "blocker_resolved_rows", "closeout_ready_rows", "completion_ready_observed_rows"),
        ),
        (
            "p689_p0_real_input_blocker_escalation_queue",
            p689_p0_real_input_blocker_escalation_queue,
            p689_p0_real_input_blocker_escalation_queue_validation,
            ("blocker_escalation_rows", "open_blocker_escalation_rows", "empty_blocker_escalation_rows", "blocked_blocker_escalation_rows"),
            ("formal_intake_dry_run_executed_rows", "formal_intake_dry_run_passed_rows", "escalation_sent_rows", "escalation_acknowledged_rows", "blocker_resolved_rows", "closeout_ready_rows", "completion_ready_observed_rows"),
        ),
        (
            "p690_p0_real_input_blocker_escalation_status_board",
            p690_p0_real_input_blocker_escalation_status_board,
            p690_p0_real_input_blocker_escalation_status_board_validation,
            ("blocker_status_rows", "open_blocker_status_rows", "empty_blocker_status_rows", "blocked_blocker_status_rows"),
            ("formal_intake_dry_run_executed_rows", "formal_intake_dry_run_passed_rows", "escalation_sent_rows", "escalation_acknowledged_rows", "blocker_resolved_rows", "closeout_ready_rows", "completion_ready_observed_rows"),
        ),
        (
            "p691_p0_real_input_blocker_escalation_watchlist",
            p691_p0_real_input_blocker_escalation_watchlist,
            p691_p0_real_input_blocker_escalation_watchlist_validation,
            ("blocker_watch_rows", "open_blocker_watch_rows", "empty_blocker_watch_rows", "blocked_blocker_watch_rows"),
            ("formal_intake_dry_run_executed_rows", "formal_intake_dry_run_passed_rows", "escalation_sent_rows", "escalation_acknowledged_rows", "blocker_resolved_rows", "closeout_ready_rows", "completion_ready_observed_rows"),
        ),
        (
            "p692_p0_real_input_blocker_escalation_review_queue",
            p692_p0_real_input_blocker_escalation_review_queue,
            p692_p0_real_input_blocker_escalation_review_queue_validation,
            ("blocker_review_rows", "open_blocker_review_rows", "empty_blocker_review_rows", "blocked_blocker_review_rows"),
            ("formal_intake_dry_run_executed_rows", "formal_intake_dry_run_passed_rows", "escalation_reviewed_rows", "escalation_sent_rows", "escalation_acknowledged_rows", "blocker_resolved_rows", "closeout_ready_rows", "completion_ready_observed_rows"),
        ),
        (
            "p693_p0_real_input_blocker_escalation_review_status_board",
            p693_p0_real_input_blocker_escalation_review_status_board,
            p693_p0_real_input_blocker_escalation_review_status_board_validation,
            ("blocker_review_status_rows", "open_blocker_review_status_rows", "empty_blocker_review_status_rows", "blocked_blocker_review_status_rows"),
            ("formal_intake_dry_run_executed_rows", "formal_intake_dry_run_passed_rows", "escalation_reviewed_rows", "escalation_sent_rows", "escalation_acknowledged_rows", "blocker_resolved_rows", "closeout_ready_rows", "completion_ready_observed_rows"),
        ),
        (
            "p694_p0_real_input_blocker_escalation_review_watchlist",
            p694_p0_real_input_blocker_escalation_review_watchlist,
            p694_p0_real_input_blocker_escalation_review_watchlist_validation,
            ("blocker_review_watch_rows", "open_blocker_review_watch_rows", "empty_blocker_review_watch_rows", "blocked_blocker_review_watch_rows"),
            ("formal_intake_dry_run_executed_rows", "formal_intake_dry_run_passed_rows", "escalation_reviewed_rows", "escalation_sent_rows", "escalation_acknowledged_rows", "blocker_resolved_rows", "closeout_ready_rows", "completion_ready_observed_rows"),
        ),
        (
            "p695_p0_real_input_blocker_escalation_review_watchlist_aging_audit",
            p695_p0_real_input_blocker_escalation_review_watchlist_aging_audit,
            p695_p0_real_input_blocker_escalation_review_watchlist_aging_audit_validation,
            ("blocker_review_aging_rows", "open_blocker_review_aging_rows", "empty_blocker_review_aging_rows", "blocked_blocker_review_aging_rows"),
            ("formal_intake_dry_run_executed_rows", "formal_intake_dry_run_passed_rows", "aging_reviewed_rows", "staleness_resolved_rows", "escalation_reviewed_rows", "escalation_sent_rows", "escalation_acknowledged_rows", "blocker_resolved_rows", "closeout_ready_rows", "completion_ready_observed_rows"),
        ),
        (
            "p696_p0_real_input_blocker_escalation_review_owner_assignment_gap_audit",
            p696_p0_real_input_blocker_escalation_review_owner_assignment_gap_audit,
            p696_p0_real_input_blocker_escalation_review_owner_assignment_gap_audit_validation,
            ("owner_assignment_gap_rows", "open_owner_assignment_gap_rows", "empty_owner_assignment_gap_rows", "blocked_owner_assignment_gap_rows"),
            ("formal_intake_dry_run_executed_rows", "formal_intake_dry_run_passed_rows", "owner_assigned_rows", "owner_acknowledged_rows", "aging_reviewed_rows", "staleness_resolved_rows", "escalation_reviewed_rows", "escalation_sent_rows", "escalation_acknowledged_rows", "blocker_resolved_rows", "closeout_ready_rows", "completion_ready_observed_rows"),
        ),
        (
            "p697_p0_real_input_blocker_escalation_review_evidence_missing_matrix",
            p697_p0_real_input_blocker_escalation_review_evidence_missing_matrix,
            p697_p0_real_input_blocker_escalation_review_evidence_missing_matrix_validation,
            ("evidence_missing_matrix_rows", "open_evidence_missing_matrix_rows", "empty_evidence_missing_matrix_rows", "blocked_evidence_missing_matrix_rows"),
            ("formal_intake_dry_run_executed_rows", "formal_intake_dry_run_passed_rows", "evidence_received_rows", "evidence_validated_rows", "evidence_released_rows", "evidence_promoted_to_decision_rows", "owner_assigned_rows", "owner_acknowledged_rows", "aging_reviewed_rows", "staleness_resolved_rows", "escalation_reviewed_rows", "escalation_sent_rows", "escalation_acknowledged_rows", "blocker_resolved_rows", "closeout_ready_rows", "completion_ready_observed_rows"),
        ),
        (
            "p698_p0_real_input_formal_decision_readiness_false_positive_guard",
            p698_p0_real_input_formal_decision_readiness_false_positive_guard,
            p698_p0_real_input_formal_decision_readiness_false_positive_guard_validation,
            (
                "formal_decision_false_positive_guard_rows",
                "open_formal_decision_false_positive_guard_rows",
                "empty_formal_decision_false_positive_guard_rows",
                "blocked_formal_decision_false_positive_guard_rows",
            ),
            (
                "formal_intake_dry_run_executed_rows",
                "formal_intake_dry_run_passed_rows",
                "formal_decision_ready_rows",
                "false_positive_cleared_rows",
                "evidence_received_rows",
                "evidence_validated_rows",
                "owner_assigned_rows",
                "owner_acknowledged_rows",
                "aging_reviewed_rows",
                "staleness_resolved_rows",
                "escalation_reviewed_rows",
                "escalation_sent_rows",
                "escalation_acknowledged_rows",
                "blocker_resolved_rows",
                "closeout_ready_rows",
                "completion_ready_observed_rows",
            ),
        ),
        (
            "p699_p0_real_input_formal_decision_readiness_status_board",
            p699_p0_real_input_formal_decision_readiness_status_board,
            p699_p0_real_input_formal_decision_readiness_status_board_validation,
            (
                "formal_decision_readiness_status_board_rows",
                "open_formal_decision_readiness_status_board_rows",
                "empty_formal_decision_readiness_status_board_rows",
                "blocked_formal_decision_readiness_status_board_rows",
            ),
            (
                "formal_intake_dry_run_executed_rows",
                "formal_intake_dry_run_passed_rows",
                "formal_decision_ready_rows",
                "formal_decision_readiness_reviewed_rows",
                "formal_decision_readiness_approved_rows",
                "false_positive_cleared_rows",
                "evidence_received_rows",
                "evidence_validated_rows",
                "owner_assigned_rows",
                "owner_acknowledged_rows",
                "aging_reviewed_rows",
                "staleness_resolved_rows",
                "escalation_reviewed_rows",
                "escalation_sent_rows",
                "escalation_acknowledged_rows",
                "blocker_resolved_rows",
                "closeout_ready_rows",
                "completion_ready_observed_rows",
            ),
        ),
        (
            "p700_p0_real_input_pending_build_checklist",
            p700_p0_real_input_pending_build_checklist,
            p700_p0_real_input_pending_build_checklist_validation,
            ("pending_build_checklist_rows", "open_pending_build_rows", "empty_pending_build_rows", "blocked_pending_build_rows"),
            ("formal_intake_dry_run_executed_rows", "formal_intake_dry_run_passed_rows", "pending_build_ready_rows"),
        ),
    ):
        for field in count_fields:
            p648_p652_summary[f"{prefix}_{field}"] = layer_report.get(field)
        for field in (
            "queue_dequeued_rows",
            "response_received_rows",
            "response_validated_rows",
            "real_input_received_rows",
            "reviewed_decision_written_rows",
            "formal_intake_written_rows",
            "runtime_receipt_written_rows",
            "training_label_written_rows",
            *extra_zero_fields,
        ):
            p648_p652_summary[f"{prefix}_{field}"] = layer_report.get(field)
        p648_p652_summary[f"{prefix}_p0_unblocked"] = layer_report.get("p0_unblocked")
        p648_p652_summary[f"{prefix}_p0_completion_ready"] = layer_report.get("p0_completion_ready", layer_report.get("completion_ready"))
        p648_p652_summary[f"{prefix}_validation_success"] = bool(layer_validation.get("success"))
    p648_p652_summary.update({
        "p687_p0_real_input_closeout_readiness_gate_training_import_allowed": p687_p0_real_input_closeout_readiness_gate.get("training_import_allowed"),
        "p687_p0_real_input_closeout_readiness_gate_safe_for_training_import": p687_p0_real_input_closeout_readiness_gate.get("safe_for_training_import"),
        "p687_p0_real_input_closeout_readiness_gate_safe_for_model_claim": p687_p0_real_input_closeout_readiness_gate.get("safe_for_model_claim"),
        "p687_p0_real_input_closeout_readiness_gate_customer_delivery_ready": p687_p0_real_input_closeout_readiness_gate.get("customer_delivery_ready"),
        "p687_p0_real_input_closeout_readiness_gate_release_ready": p687_p0_real_input_closeout_readiness_gate.get("release_ready"),
        "p687_p0_real_input_closeout_readiness_gate_production_execution_allowed": p687_p0_real_input_closeout_readiness_gate.get("production_execution_allowed"),
        "p687_p0_real_input_closeout_readiness_gate_closeout_ready": p687_p0_real_input_closeout_readiness_gate.get("closeout_ready"),
        "p687_p0_real_input_closeout_readiness_gate_completion_ready_observed": p687_p0_real_input_closeout_readiness_gate.get("completion_ready_observed"),
        "p687_p0_real_input_closeout_readiness_gate_completion_ready": p687_p0_real_input_closeout_readiness_gate.get("completion_ready"),
        "p688_p0_real_input_closeout_blocker_ledger_training_import_allowed": p688_p0_real_input_closeout_blocker_ledger.get("training_import_allowed"),
        "p688_p0_real_input_closeout_blocker_ledger_safe_for_training_import": p688_p0_real_input_closeout_blocker_ledger.get("safe_for_training_import"),
        "p688_p0_real_input_closeout_blocker_ledger_safe_for_model_claim": p688_p0_real_input_closeout_blocker_ledger.get("safe_for_model_claim"),
        "p688_p0_real_input_closeout_blocker_ledger_customer_delivery_ready": p688_p0_real_input_closeout_blocker_ledger.get("customer_delivery_ready"),
        "p688_p0_real_input_closeout_blocker_ledger_release_ready": p688_p0_real_input_closeout_blocker_ledger.get("release_ready"),
        "p688_p0_real_input_closeout_blocker_ledger_production_execution_allowed": p688_p0_real_input_closeout_blocker_ledger.get("production_execution_allowed"),
        "p688_p0_real_input_closeout_blocker_ledger_blocker_resolved": p688_p0_real_input_closeout_blocker_ledger.get("blocker_resolved"),
        "p688_p0_real_input_closeout_blocker_ledger_closeout_ready": p688_p0_real_input_closeout_blocker_ledger.get("closeout_ready"),
        "p688_p0_real_input_closeout_blocker_ledger_completion_ready_observed": p688_p0_real_input_closeout_blocker_ledger.get("completion_ready_observed"),
        "p688_p0_real_input_closeout_blocker_ledger_completion_ready": p688_p0_real_input_closeout_blocker_ledger.get("completion_ready"),
        "p689_p0_real_input_blocker_escalation_queue_training_import_allowed": p689_p0_real_input_blocker_escalation_queue.get("training_import_allowed"),
        "p689_p0_real_input_blocker_escalation_queue_safe_for_training_import": p689_p0_real_input_blocker_escalation_queue.get("safe_for_training_import"),
        "p689_p0_real_input_blocker_escalation_queue_safe_for_model_claim": p689_p0_real_input_blocker_escalation_queue.get("safe_for_model_claim"),
        "p689_p0_real_input_blocker_escalation_queue_customer_delivery_ready": p689_p0_real_input_blocker_escalation_queue.get("customer_delivery_ready"),
        "p689_p0_real_input_blocker_escalation_queue_release_ready": p689_p0_real_input_blocker_escalation_queue.get("release_ready"),
        "p689_p0_real_input_blocker_escalation_queue_production_execution_allowed": p689_p0_real_input_blocker_escalation_queue.get("production_execution_allowed"),
        "p689_p0_real_input_blocker_escalation_queue_escalation_sent": p689_p0_real_input_blocker_escalation_queue.get("escalation_sent"),
        "p689_p0_real_input_blocker_escalation_queue_escalation_acknowledged": p689_p0_real_input_blocker_escalation_queue.get("escalation_acknowledged"),
        "p689_p0_real_input_blocker_escalation_queue_blocker_resolved": p689_p0_real_input_blocker_escalation_queue.get("blocker_resolved"),
        "p689_p0_real_input_blocker_escalation_queue_closeout_ready": p689_p0_real_input_blocker_escalation_queue.get("closeout_ready"),
        "p689_p0_real_input_blocker_escalation_queue_completion_ready_observed": p689_p0_real_input_blocker_escalation_queue.get("completion_ready_observed"),
        "p689_p0_real_input_blocker_escalation_queue_completion_ready": p689_p0_real_input_blocker_escalation_queue.get("completion_ready"),
        "p690_p0_real_input_blocker_escalation_status_board_training_import_allowed": p690_p0_real_input_blocker_escalation_status_board.get("training_import_allowed"),
        "p690_p0_real_input_blocker_escalation_status_board_safe_for_training_import": p690_p0_real_input_blocker_escalation_status_board.get("safe_for_training_import"),
        "p690_p0_real_input_blocker_escalation_status_board_safe_for_model_claim": p690_p0_real_input_blocker_escalation_status_board.get("safe_for_model_claim"),
        "p690_p0_real_input_blocker_escalation_status_board_customer_delivery_ready": p690_p0_real_input_blocker_escalation_status_board.get("customer_delivery_ready"),
        "p690_p0_real_input_blocker_escalation_status_board_release_ready": p690_p0_real_input_blocker_escalation_status_board.get("release_ready"),
        "p690_p0_real_input_blocker_escalation_status_board_production_execution_allowed": p690_p0_real_input_blocker_escalation_status_board.get("production_execution_allowed"),
        "p690_p0_real_input_blocker_escalation_status_board_escalation_sent": p690_p0_real_input_blocker_escalation_status_board.get("escalation_sent"),
        "p690_p0_real_input_blocker_escalation_status_board_escalation_acknowledged": p690_p0_real_input_blocker_escalation_status_board.get("escalation_acknowledged"),
        "p690_p0_real_input_blocker_escalation_status_board_blocker_resolved": p690_p0_real_input_blocker_escalation_status_board.get("blocker_resolved"),
        "p690_p0_real_input_blocker_escalation_status_board_closeout_ready": p690_p0_real_input_blocker_escalation_status_board.get("closeout_ready"),
        "p690_p0_real_input_blocker_escalation_status_board_completion_ready_observed": p690_p0_real_input_blocker_escalation_status_board.get("completion_ready_observed"),
        "p690_p0_real_input_blocker_escalation_status_board_completion_ready": p690_p0_real_input_blocker_escalation_status_board.get("completion_ready"),
        "p691_p0_real_input_blocker_escalation_watchlist_training_import_allowed": p691_p0_real_input_blocker_escalation_watchlist.get("training_import_allowed"),
        "p691_p0_real_input_blocker_escalation_watchlist_safe_for_training_import": p691_p0_real_input_blocker_escalation_watchlist.get("safe_for_training_import"),
        "p691_p0_real_input_blocker_escalation_watchlist_safe_for_model_claim": p691_p0_real_input_blocker_escalation_watchlist.get("safe_for_model_claim"),
        "p691_p0_real_input_blocker_escalation_watchlist_customer_delivery_ready": p691_p0_real_input_blocker_escalation_watchlist.get("customer_delivery_ready"),
        "p691_p0_real_input_blocker_escalation_watchlist_release_ready": p691_p0_real_input_blocker_escalation_watchlist.get("release_ready"),
        "p691_p0_real_input_blocker_escalation_watchlist_production_execution_allowed": p691_p0_real_input_blocker_escalation_watchlist.get("production_execution_allowed"),
        "p691_p0_real_input_blocker_escalation_watchlist_escalation_sent": p691_p0_real_input_blocker_escalation_watchlist.get("escalation_sent"),
        "p691_p0_real_input_blocker_escalation_watchlist_escalation_acknowledged": p691_p0_real_input_blocker_escalation_watchlist.get("escalation_acknowledged"),
        "p691_p0_real_input_blocker_escalation_watchlist_blocker_resolved": p691_p0_real_input_blocker_escalation_watchlist.get("blocker_resolved"),
        "p691_p0_real_input_blocker_escalation_watchlist_closeout_ready": p691_p0_real_input_blocker_escalation_watchlist.get("closeout_ready"),
        "p691_p0_real_input_blocker_escalation_watchlist_completion_ready_observed": p691_p0_real_input_blocker_escalation_watchlist.get("completion_ready_observed"),
        "p691_p0_real_input_blocker_escalation_watchlist_completion_ready": p691_p0_real_input_blocker_escalation_watchlist.get("completion_ready"),
        "p692_p0_real_input_blocker_escalation_review_queue_training_import_allowed": p692_p0_real_input_blocker_escalation_review_queue.get("training_import_allowed"),
        "p692_p0_real_input_blocker_escalation_review_queue_safe_for_training_import": p692_p0_real_input_blocker_escalation_review_queue.get("safe_for_training_import"),
        "p692_p0_real_input_blocker_escalation_review_queue_safe_for_model_claim": p692_p0_real_input_blocker_escalation_review_queue.get("safe_for_model_claim"),
        "p692_p0_real_input_blocker_escalation_review_queue_customer_delivery_ready": p692_p0_real_input_blocker_escalation_review_queue.get("customer_delivery_ready"),
        "p692_p0_real_input_blocker_escalation_review_queue_release_ready": p692_p0_real_input_blocker_escalation_review_queue.get("release_ready"),
        "p692_p0_real_input_blocker_escalation_review_queue_production_execution_allowed": p692_p0_real_input_blocker_escalation_review_queue.get("production_execution_allowed"),
        "p692_p0_real_input_blocker_escalation_review_queue_escalation_reviewed": p692_p0_real_input_blocker_escalation_review_queue.get("escalation_reviewed"),
        "p692_p0_real_input_blocker_escalation_review_queue_escalation_sent": p692_p0_real_input_blocker_escalation_review_queue.get("escalation_sent"),
        "p692_p0_real_input_blocker_escalation_review_queue_escalation_acknowledged": p692_p0_real_input_blocker_escalation_review_queue.get("escalation_acknowledged"),
        "p692_p0_real_input_blocker_escalation_review_queue_blocker_resolved": p692_p0_real_input_blocker_escalation_review_queue.get("blocker_resolved"),
        "p692_p0_real_input_blocker_escalation_review_queue_closeout_ready": p692_p0_real_input_blocker_escalation_review_queue.get("closeout_ready"),
        "p692_p0_real_input_blocker_escalation_review_queue_completion_ready_observed": p692_p0_real_input_blocker_escalation_review_queue.get("completion_ready_observed"),
        "p692_p0_real_input_blocker_escalation_review_queue_completion_ready": p692_p0_real_input_blocker_escalation_review_queue.get("completion_ready"),
        "p693_p0_real_input_blocker_escalation_review_status_board_training_import_allowed": p693_p0_real_input_blocker_escalation_review_status_board.get("training_import_allowed"),
        "p693_p0_real_input_blocker_escalation_review_status_board_safe_for_training_import": p693_p0_real_input_blocker_escalation_review_status_board.get("safe_for_training_import"),
        "p693_p0_real_input_blocker_escalation_review_status_board_safe_for_model_claim": p693_p0_real_input_blocker_escalation_review_status_board.get("safe_for_model_claim"),
        "p693_p0_real_input_blocker_escalation_review_status_board_customer_delivery_ready": p693_p0_real_input_blocker_escalation_review_status_board.get("customer_delivery_ready"),
        "p693_p0_real_input_blocker_escalation_review_status_board_release_ready": p693_p0_real_input_blocker_escalation_review_status_board.get("release_ready"),
        "p693_p0_real_input_blocker_escalation_review_status_board_production_execution_allowed": p693_p0_real_input_blocker_escalation_review_status_board.get("production_execution_allowed"),
        "p693_p0_real_input_blocker_escalation_review_status_board_escalation_reviewed": p693_p0_real_input_blocker_escalation_review_status_board.get("escalation_reviewed"),
        "p693_p0_real_input_blocker_escalation_review_status_board_escalation_sent": p693_p0_real_input_blocker_escalation_review_status_board.get("escalation_sent"),
        "p693_p0_real_input_blocker_escalation_review_status_board_escalation_acknowledged": p693_p0_real_input_blocker_escalation_review_status_board.get("escalation_acknowledged"),
        "p693_p0_real_input_blocker_escalation_review_status_board_blocker_resolved": p693_p0_real_input_blocker_escalation_review_status_board.get("blocker_resolved"),
        "p693_p0_real_input_blocker_escalation_review_status_board_closeout_ready": p693_p0_real_input_blocker_escalation_review_status_board.get("closeout_ready"),
        "p693_p0_real_input_blocker_escalation_review_status_board_completion_ready_observed": p693_p0_real_input_blocker_escalation_review_status_board.get("completion_ready_observed"),
        "p693_p0_real_input_blocker_escalation_review_status_board_completion_ready": p693_p0_real_input_blocker_escalation_review_status_board.get("completion_ready"),
        "p694_p0_real_input_blocker_escalation_review_watchlist_training_import_allowed": p694_p0_real_input_blocker_escalation_review_watchlist.get("training_import_allowed"),
        "p694_p0_real_input_blocker_escalation_review_watchlist_safe_for_training_import": p694_p0_real_input_blocker_escalation_review_watchlist.get("safe_for_training_import"),
        "p694_p0_real_input_blocker_escalation_review_watchlist_safe_for_model_claim": p694_p0_real_input_blocker_escalation_review_watchlist.get("safe_for_model_claim"),
        "p694_p0_real_input_blocker_escalation_review_watchlist_customer_delivery_ready": p694_p0_real_input_blocker_escalation_review_watchlist.get("customer_delivery_ready"),
        "p694_p0_real_input_blocker_escalation_review_watchlist_release_ready": p694_p0_real_input_blocker_escalation_review_watchlist.get("release_ready"),
        "p694_p0_real_input_blocker_escalation_review_watchlist_production_execution_allowed": p694_p0_real_input_blocker_escalation_review_watchlist.get("production_execution_allowed"),
        "p694_p0_real_input_blocker_escalation_review_watchlist_escalation_reviewed": p694_p0_real_input_blocker_escalation_review_watchlist.get("escalation_reviewed"),
        "p694_p0_real_input_blocker_escalation_review_watchlist_escalation_sent": p694_p0_real_input_blocker_escalation_review_watchlist.get("escalation_sent"),
        "p694_p0_real_input_blocker_escalation_review_watchlist_escalation_acknowledged": p694_p0_real_input_blocker_escalation_review_watchlist.get("escalation_acknowledged"),
        "p694_p0_real_input_blocker_escalation_review_watchlist_blocker_resolved": p694_p0_real_input_blocker_escalation_review_watchlist.get("blocker_resolved"),
        "p694_p0_real_input_blocker_escalation_review_watchlist_closeout_ready": p694_p0_real_input_blocker_escalation_review_watchlist.get("closeout_ready"),
        "p694_p0_real_input_blocker_escalation_review_watchlist_completion_ready_observed": p694_p0_real_input_blocker_escalation_review_watchlist.get("completion_ready_observed"),
        "p694_p0_real_input_blocker_escalation_review_watchlist_completion_ready": p694_p0_real_input_blocker_escalation_review_watchlist.get("completion_ready"),
        "p695_p0_real_input_blocker_escalation_review_watchlist_aging_audit_training_import_allowed": p695_p0_real_input_blocker_escalation_review_watchlist_aging_audit.get("training_import_allowed"),
        "p695_p0_real_input_blocker_escalation_review_watchlist_aging_audit_safe_for_training_import": p695_p0_real_input_blocker_escalation_review_watchlist_aging_audit.get("safe_for_training_import"),
        "p695_p0_real_input_blocker_escalation_review_watchlist_aging_audit_safe_for_model_claim": p695_p0_real_input_blocker_escalation_review_watchlist_aging_audit.get("safe_for_model_claim"),
        "p695_p0_real_input_blocker_escalation_review_watchlist_aging_audit_customer_delivery_ready": p695_p0_real_input_blocker_escalation_review_watchlist_aging_audit.get("customer_delivery_ready"),
        "p695_p0_real_input_blocker_escalation_review_watchlist_aging_audit_release_ready": p695_p0_real_input_blocker_escalation_review_watchlist_aging_audit.get("release_ready"),
        "p695_p0_real_input_blocker_escalation_review_watchlist_aging_audit_production_execution_allowed": p695_p0_real_input_blocker_escalation_review_watchlist_aging_audit.get("production_execution_allowed"),
        "p695_p0_real_input_blocker_escalation_review_watchlist_aging_audit_aging_reviewed": p695_p0_real_input_blocker_escalation_review_watchlist_aging_audit.get("aging_reviewed"),
        "p695_p0_real_input_blocker_escalation_review_watchlist_aging_audit_staleness_resolved": p695_p0_real_input_blocker_escalation_review_watchlist_aging_audit.get("staleness_resolved"),
        "p695_p0_real_input_blocker_escalation_review_watchlist_aging_audit_escalation_reviewed": p695_p0_real_input_blocker_escalation_review_watchlist_aging_audit.get("escalation_reviewed"),
        "p695_p0_real_input_blocker_escalation_review_watchlist_aging_audit_escalation_sent": p695_p0_real_input_blocker_escalation_review_watchlist_aging_audit.get("escalation_sent"),
        "p695_p0_real_input_blocker_escalation_review_watchlist_aging_audit_escalation_acknowledged": p695_p0_real_input_blocker_escalation_review_watchlist_aging_audit.get("escalation_acknowledged"),
        "p695_p0_real_input_blocker_escalation_review_watchlist_aging_audit_blocker_resolved": p695_p0_real_input_blocker_escalation_review_watchlist_aging_audit.get("blocker_resolved"),
        "p695_p0_real_input_blocker_escalation_review_watchlist_aging_audit_closeout_ready": p695_p0_real_input_blocker_escalation_review_watchlist_aging_audit.get("closeout_ready"),
        "p695_p0_real_input_blocker_escalation_review_watchlist_aging_audit_completion_ready_observed": p695_p0_real_input_blocker_escalation_review_watchlist_aging_audit.get("completion_ready_observed"),
        "p695_p0_real_input_blocker_escalation_review_watchlist_aging_audit_completion_ready": p695_p0_real_input_blocker_escalation_review_watchlist_aging_audit.get("completion_ready"),
        "p695_p0_real_input_blocker_escalation_review_watchlist_aging_audit_p0_unblocked": p695_p0_real_input_blocker_escalation_review_watchlist_aging_audit.get("p0_unblocked"),
        "p695_p0_real_input_blocker_escalation_review_watchlist_aging_audit_p0_completion_ready": p695_p0_real_input_blocker_escalation_review_watchlist_aging_audit.get("p0_completion_ready"),
        "p696_p0_real_input_blocker_escalation_review_owner_assignment_gap_audit_training_import_allowed": p696_p0_real_input_blocker_escalation_review_owner_assignment_gap_audit.get("training_import_allowed"),
        "p696_p0_real_input_blocker_escalation_review_owner_assignment_gap_audit_safe_for_training_import": p696_p0_real_input_blocker_escalation_review_owner_assignment_gap_audit.get("safe_for_training_import"),
        "p696_p0_real_input_blocker_escalation_review_owner_assignment_gap_audit_safe_for_model_claim": p696_p0_real_input_blocker_escalation_review_owner_assignment_gap_audit.get("safe_for_model_claim"),
        "p696_p0_real_input_blocker_escalation_review_owner_assignment_gap_audit_customer_delivery_ready": p696_p0_real_input_blocker_escalation_review_owner_assignment_gap_audit.get("customer_delivery_ready"),
        "p696_p0_real_input_blocker_escalation_review_owner_assignment_gap_audit_release_ready": p696_p0_real_input_blocker_escalation_review_owner_assignment_gap_audit.get("release_ready"),
        "p696_p0_real_input_blocker_escalation_review_owner_assignment_gap_audit_production_execution_allowed": p696_p0_real_input_blocker_escalation_review_owner_assignment_gap_audit.get("production_execution_allowed"),
        "p696_p0_real_input_blocker_escalation_review_owner_assignment_gap_audit_owner_assigned": p696_p0_real_input_blocker_escalation_review_owner_assignment_gap_audit.get("owner_assigned"),
        "p696_p0_real_input_blocker_escalation_review_owner_assignment_gap_audit_owner_acknowledged": p696_p0_real_input_blocker_escalation_review_owner_assignment_gap_audit.get("owner_acknowledged"),
        "p696_p0_real_input_blocker_escalation_review_owner_assignment_gap_audit_aging_reviewed": p696_p0_real_input_blocker_escalation_review_owner_assignment_gap_audit.get("aging_reviewed"),
        "p696_p0_real_input_blocker_escalation_review_owner_assignment_gap_audit_staleness_resolved": p696_p0_real_input_blocker_escalation_review_owner_assignment_gap_audit.get("staleness_resolved"),
        "p696_p0_real_input_blocker_escalation_review_owner_assignment_gap_audit_escalation_reviewed": p696_p0_real_input_blocker_escalation_review_owner_assignment_gap_audit.get("escalation_reviewed"),
        "p696_p0_real_input_blocker_escalation_review_owner_assignment_gap_audit_escalation_sent": p696_p0_real_input_blocker_escalation_review_owner_assignment_gap_audit.get("escalation_sent"),
        "p696_p0_real_input_blocker_escalation_review_owner_assignment_gap_audit_escalation_acknowledged": p696_p0_real_input_blocker_escalation_review_owner_assignment_gap_audit.get("escalation_acknowledged"),
        "p696_p0_real_input_blocker_escalation_review_owner_assignment_gap_audit_blocker_resolved": p696_p0_real_input_blocker_escalation_review_owner_assignment_gap_audit.get("blocker_resolved"),
        "p696_p0_real_input_blocker_escalation_review_owner_assignment_gap_audit_closeout_ready": p696_p0_real_input_blocker_escalation_review_owner_assignment_gap_audit.get("closeout_ready"),
        "p696_p0_real_input_blocker_escalation_review_owner_assignment_gap_audit_completion_ready_observed": p696_p0_real_input_blocker_escalation_review_owner_assignment_gap_audit.get("completion_ready_observed"),
        "p696_p0_real_input_blocker_escalation_review_owner_assignment_gap_audit_completion_ready": p696_p0_real_input_blocker_escalation_review_owner_assignment_gap_audit.get("completion_ready"),
        "p696_p0_real_input_blocker_escalation_review_owner_assignment_gap_audit_p0_unblocked": p696_p0_real_input_blocker_escalation_review_owner_assignment_gap_audit.get("p0_unblocked"),
        "p696_p0_real_input_blocker_escalation_review_owner_assignment_gap_audit_p0_completion_ready": p696_p0_real_input_blocker_escalation_review_owner_assignment_gap_audit.get("p0_completion_ready"),
        "p697_p0_real_input_blocker_escalation_review_evidence_missing_matrix_training_import_allowed": p697_p0_real_input_blocker_escalation_review_evidence_missing_matrix.get("training_import_allowed"),
        "p697_p0_real_input_blocker_escalation_review_evidence_missing_matrix_safe_for_training_import": p697_p0_real_input_blocker_escalation_review_evidence_missing_matrix.get("safe_for_training_import"),
        "p697_p0_real_input_blocker_escalation_review_evidence_missing_matrix_safe_for_model_claim": p697_p0_real_input_blocker_escalation_review_evidence_missing_matrix.get("safe_for_model_claim"),
        "p697_p0_real_input_blocker_escalation_review_evidence_missing_matrix_customer_delivery_ready": p697_p0_real_input_blocker_escalation_review_evidence_missing_matrix.get("customer_delivery_ready"),
        "p697_p0_real_input_blocker_escalation_review_evidence_missing_matrix_release_ready": p697_p0_real_input_blocker_escalation_review_evidence_missing_matrix.get("release_ready"),
        "p697_p0_real_input_blocker_escalation_review_evidence_missing_matrix_production_execution_allowed": p697_p0_real_input_blocker_escalation_review_evidence_missing_matrix.get("production_execution_allowed"),
        "p697_p0_real_input_blocker_escalation_review_evidence_missing_matrix_evidence_received": p697_p0_real_input_blocker_escalation_review_evidence_missing_matrix.get("evidence_received"),
        "p697_p0_real_input_blocker_escalation_review_evidence_missing_matrix_evidence_validated": p697_p0_real_input_blocker_escalation_review_evidence_missing_matrix.get("evidence_validated"),
        "p697_p0_real_input_blocker_escalation_review_evidence_missing_matrix_evidence_released": p697_p0_real_input_blocker_escalation_review_evidence_missing_matrix.get("evidence_released"),
        "p697_p0_real_input_blocker_escalation_review_evidence_missing_matrix_evidence_promoted_to_decision": p697_p0_real_input_blocker_escalation_review_evidence_missing_matrix.get("evidence_promoted_to_decision"),
        "p697_p0_real_input_blocker_escalation_review_evidence_missing_matrix_owner_assigned": p697_p0_real_input_blocker_escalation_review_evidence_missing_matrix.get("owner_assigned"),
        "p697_p0_real_input_blocker_escalation_review_evidence_missing_matrix_owner_acknowledged": p697_p0_real_input_blocker_escalation_review_evidence_missing_matrix.get("owner_acknowledged"),
        "p697_p0_real_input_blocker_escalation_review_evidence_missing_matrix_aging_reviewed": p697_p0_real_input_blocker_escalation_review_evidence_missing_matrix.get("aging_reviewed"),
        "p697_p0_real_input_blocker_escalation_review_evidence_missing_matrix_staleness_resolved": p697_p0_real_input_blocker_escalation_review_evidence_missing_matrix.get("staleness_resolved"),
        "p697_p0_real_input_blocker_escalation_review_evidence_missing_matrix_escalation_reviewed": p697_p0_real_input_blocker_escalation_review_evidence_missing_matrix.get("escalation_reviewed"),
        "p697_p0_real_input_blocker_escalation_review_evidence_missing_matrix_escalation_sent": p697_p0_real_input_blocker_escalation_review_evidence_missing_matrix.get("escalation_sent"),
        "p697_p0_real_input_blocker_escalation_review_evidence_missing_matrix_escalation_acknowledged": p697_p0_real_input_blocker_escalation_review_evidence_missing_matrix.get("escalation_acknowledged"),
        "p697_p0_real_input_blocker_escalation_review_evidence_missing_matrix_blocker_resolved": p697_p0_real_input_blocker_escalation_review_evidence_missing_matrix.get("blocker_resolved"),
        "p697_p0_real_input_blocker_escalation_review_evidence_missing_matrix_closeout_ready": p697_p0_real_input_blocker_escalation_review_evidence_missing_matrix.get("closeout_ready"),
        "p697_p0_real_input_blocker_escalation_review_evidence_missing_matrix_completion_ready_observed": p697_p0_real_input_blocker_escalation_review_evidence_missing_matrix.get("completion_ready_observed"),
        "p697_p0_real_input_blocker_escalation_review_evidence_missing_matrix_completion_ready": p697_p0_real_input_blocker_escalation_review_evidence_missing_matrix.get("completion_ready"),
        "p697_p0_real_input_blocker_escalation_review_evidence_missing_matrix_p0_unblocked": p697_p0_real_input_blocker_escalation_review_evidence_missing_matrix.get("p0_unblocked"),
        "p697_p0_real_input_blocker_escalation_review_evidence_missing_matrix_p0_completion_ready": p697_p0_real_input_blocker_escalation_review_evidence_missing_matrix.get("p0_completion_ready"),
        "p698_p0_real_input_formal_decision_readiness_false_positive_guard_training_import_allowed": p698_p0_real_input_formal_decision_readiness_false_positive_guard.get("training_import_allowed"),
        "p698_p0_real_input_formal_decision_readiness_false_positive_guard_safe_for_training_import": p698_p0_real_input_formal_decision_readiness_false_positive_guard.get("safe_for_training_import"),
        "p698_p0_real_input_formal_decision_readiness_false_positive_guard_safe_for_model_claim": p698_p0_real_input_formal_decision_readiness_false_positive_guard.get("safe_for_model_claim"),
        "p698_p0_real_input_formal_decision_readiness_false_positive_guard_customer_delivery_ready": p698_p0_real_input_formal_decision_readiness_false_positive_guard.get("customer_delivery_ready"),
        "p698_p0_real_input_formal_decision_readiness_false_positive_guard_release_ready": p698_p0_real_input_formal_decision_readiness_false_positive_guard.get("release_ready"),
        "p698_p0_real_input_formal_decision_readiness_false_positive_guard_production_execution_allowed": p698_p0_real_input_formal_decision_readiness_false_positive_guard.get("production_execution_allowed"),
        "p698_p0_real_input_formal_decision_readiness_false_positive_guard_formal_decision_ready": p698_p0_real_input_formal_decision_readiness_false_positive_guard.get("formal_decision_ready"),
        "p698_p0_real_input_formal_decision_readiness_false_positive_guard_false_positive_cleared": p698_p0_real_input_formal_decision_readiness_false_positive_guard.get("false_positive_cleared"),
        "p698_p0_real_input_formal_decision_readiness_false_positive_guard_evidence_received": p698_p0_real_input_formal_decision_readiness_false_positive_guard.get("evidence_received"),
        "p698_p0_real_input_formal_decision_readiness_false_positive_guard_evidence_validated": p698_p0_real_input_formal_decision_readiness_false_positive_guard.get("evidence_validated"),
        "p698_p0_real_input_formal_decision_readiness_false_positive_guard_owner_assigned": p698_p0_real_input_formal_decision_readiness_false_positive_guard.get("owner_assigned"),
        "p698_p0_real_input_formal_decision_readiness_false_positive_guard_owner_acknowledged": p698_p0_real_input_formal_decision_readiness_false_positive_guard.get("owner_acknowledged"),
        "p698_p0_real_input_formal_decision_readiness_false_positive_guard_aging_reviewed": p698_p0_real_input_formal_decision_readiness_false_positive_guard.get("aging_reviewed"),
        "p698_p0_real_input_formal_decision_readiness_false_positive_guard_staleness_resolved": p698_p0_real_input_formal_decision_readiness_false_positive_guard.get("staleness_resolved"),
        "p698_p0_real_input_formal_decision_readiness_false_positive_guard_escalation_reviewed": p698_p0_real_input_formal_decision_readiness_false_positive_guard.get("escalation_reviewed"),
        "p698_p0_real_input_formal_decision_readiness_false_positive_guard_escalation_sent": p698_p0_real_input_formal_decision_readiness_false_positive_guard.get("escalation_sent"),
        "p698_p0_real_input_formal_decision_readiness_false_positive_guard_escalation_acknowledged": p698_p0_real_input_formal_decision_readiness_false_positive_guard.get("escalation_acknowledged"),
        "p698_p0_real_input_formal_decision_readiness_false_positive_guard_blocker_resolved": p698_p0_real_input_formal_decision_readiness_false_positive_guard.get("blocker_resolved"),
        "p698_p0_real_input_formal_decision_readiness_false_positive_guard_closeout_ready": p698_p0_real_input_formal_decision_readiness_false_positive_guard.get("closeout_ready"),
        "p698_p0_real_input_formal_decision_readiness_false_positive_guard_completion_ready_observed": p698_p0_real_input_formal_decision_readiness_false_positive_guard.get("completion_ready_observed"),
        "p698_p0_real_input_formal_decision_readiness_false_positive_guard_completion_ready": p698_p0_real_input_formal_decision_readiness_false_positive_guard.get("completion_ready"),
        "p698_p0_real_input_formal_decision_readiness_false_positive_guard_p0_unblocked": p698_p0_real_input_formal_decision_readiness_false_positive_guard.get("p0_unblocked"),
        "p698_p0_real_input_formal_decision_readiness_false_positive_guard_p0_completion_ready": p698_p0_real_input_formal_decision_readiness_false_positive_guard.get("p0_completion_ready"),
        "p699_p0_real_input_formal_decision_readiness_status_board_training_import_allowed": p699_p0_real_input_formal_decision_readiness_status_board.get("training_import_allowed"),
        "p699_p0_real_input_formal_decision_readiness_status_board_safe_for_training_import": p699_p0_real_input_formal_decision_readiness_status_board.get("safe_for_training_import"),
        "p699_p0_real_input_formal_decision_readiness_status_board_safe_for_model_claim": p699_p0_real_input_formal_decision_readiness_status_board.get("safe_for_model_claim"),
        "p699_p0_real_input_formal_decision_readiness_status_board_customer_delivery_ready": p699_p0_real_input_formal_decision_readiness_status_board.get("customer_delivery_ready"),
        "p699_p0_real_input_formal_decision_readiness_status_board_release_ready": p699_p0_real_input_formal_decision_readiness_status_board.get("release_ready"),
        "p699_p0_real_input_formal_decision_readiness_status_board_production_execution_allowed": p699_p0_real_input_formal_decision_readiness_status_board.get("production_execution_allowed"),
        "p699_p0_real_input_formal_decision_readiness_status_board_formal_decision_ready": p699_p0_real_input_formal_decision_readiness_status_board.get("formal_decision_ready"),
        "p699_p0_real_input_formal_decision_readiness_status_board_formal_decision_readiness_reviewed": p699_p0_real_input_formal_decision_readiness_status_board.get("formal_decision_readiness_reviewed"),
        "p699_p0_real_input_formal_decision_readiness_status_board_formal_decision_readiness_approved": p699_p0_real_input_formal_decision_readiness_status_board.get("formal_decision_readiness_approved"),
        "p699_p0_real_input_formal_decision_readiness_status_board_false_positive_cleared": p699_p0_real_input_formal_decision_readiness_status_board.get("false_positive_cleared"),
        "p699_p0_real_input_formal_decision_readiness_status_board_evidence_received": p699_p0_real_input_formal_decision_readiness_status_board.get("evidence_received"),
        "p699_p0_real_input_formal_decision_readiness_status_board_evidence_validated": p699_p0_real_input_formal_decision_readiness_status_board.get("evidence_validated"),
        "p699_p0_real_input_formal_decision_readiness_status_board_owner_assigned": p699_p0_real_input_formal_decision_readiness_status_board.get("owner_assigned"),
        "p699_p0_real_input_formal_decision_readiness_status_board_owner_acknowledged": p699_p0_real_input_formal_decision_readiness_status_board.get("owner_acknowledged"),
        "p699_p0_real_input_formal_decision_readiness_status_board_aging_reviewed": p699_p0_real_input_formal_decision_readiness_status_board.get("aging_reviewed"),
        "p699_p0_real_input_formal_decision_readiness_status_board_staleness_resolved": p699_p0_real_input_formal_decision_readiness_status_board.get("staleness_resolved"),
        "p699_p0_real_input_formal_decision_readiness_status_board_escalation_reviewed": p699_p0_real_input_formal_decision_readiness_status_board.get("escalation_reviewed"),
        "p699_p0_real_input_formal_decision_readiness_status_board_escalation_sent": p699_p0_real_input_formal_decision_readiness_status_board.get("escalation_sent"),
        "p699_p0_real_input_formal_decision_readiness_status_board_escalation_acknowledged": p699_p0_real_input_formal_decision_readiness_status_board.get("escalation_acknowledged"),
        "p699_p0_real_input_formal_decision_readiness_status_board_blocker_resolved": p699_p0_real_input_formal_decision_readiness_status_board.get("blocker_resolved"),
        "p699_p0_real_input_formal_decision_readiness_status_board_closeout_ready": p699_p0_real_input_formal_decision_readiness_status_board.get("closeout_ready"),
        "p699_p0_real_input_formal_decision_readiness_status_board_completion_ready_observed": p699_p0_real_input_formal_decision_readiness_status_board.get("completion_ready_observed"),
        "p699_p0_real_input_formal_decision_readiness_status_board_completion_ready": p699_p0_real_input_formal_decision_readiness_status_board.get("completion_ready"),
        "p699_p0_real_input_formal_decision_readiness_status_board_p0_unblocked": p699_p0_real_input_formal_decision_readiness_status_board.get("p0_unblocked"),
        "p699_p0_real_input_formal_decision_readiness_status_board_p0_completion_ready": p699_p0_real_input_formal_decision_readiness_status_board.get("p0_completion_ready"),
        "p700_p0_real_input_pending_build_checklist_pending_build_checklist_rows": p700_p0_real_input_pending_build_checklist.get("pending_build_checklist_rows"),
        "p700_p0_real_input_pending_build_checklist_open_pending_build_rows": p700_p0_real_input_pending_build_checklist.get("open_pending_build_rows"),
        "p700_p0_real_input_pending_build_checklist_empty_pending_build_rows": p700_p0_real_input_pending_build_checklist.get("empty_pending_build_rows"),
        "p700_p0_real_input_pending_build_checklist_blocked_pending_build_rows": p700_p0_real_input_pending_build_checklist.get("blocked_pending_build_rows"),
        "p700_p0_real_input_pending_build_checklist_pending_build_ready": p700_p0_real_input_pending_build_checklist.get("pending_build_ready"),
        "p700_p0_real_input_pending_build_checklist_pending_build_ready_rows": p700_p0_real_input_pending_build_checklist.get("pending_build_ready_rows"),
    })
    report = {
        "release_id": "KWB-EnzymeDesigner-local-review-2026-07-27",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "local_only": True,
        "artifact_manifest": "reports/data_lake_manifest.json",
        "artifact_count": len(artifacts),
        "missing_artifacts": missing,
        "readiness_summary": {
            "master_overall_status": master.get("overall_status"),
            "ready_streams": master.get("ready_streams"),
            "total_streams": master.get("total_streams"),
            "governance_ready": bool(governance.get("ready")),
            "biosecurity_ready_for_ordering": bool(biosecurity.get("ready_for_ordering")),
            "customer_delivery_ready": bool(customer.get("ready")),
            "benchmark_ready_for_model_claim": bool(benchmark.get("ready_for_model_claim")),
            "benchmark_plan_rows": benchmark_plan.get("plan_rows"),
            "operator_review_action_rows": operator_queue.get("action_rows"),
            "operator_review_decision_rows": operator_action_validation.get("decision_rows"),
            "operator_review_completed_rows": operator_action_validation.get("completed_rows"),
            "operator_review_all_actions_completed": bool(operator_action_validation.get("all_actions_completed")),
            "operator_review_status_ready": bool(operator_status.get("ready")),
            "workstream_acceptance_decision_rows": workstream_acceptance_decisions.get("decision_rows"),
            "workstream_human_accepted_streams": workstream_acceptance_decisions.get("accepted_streams"),
            "workstream_all_human_accepted": bool(workstream_acceptance_decisions.get("all_streams_accepted")),
            "license_decision_rows": license_decisions.get("decision_rows"),
            "license_ready_for_customer_delivery": bool(license_decisions.get("ready_for_customer_delivery")),
            "biosecurity_decision_rows": biosecurity_decisions.get("decision_rows"),
            "biosecurity_decision_ready_for_ordering": bool(biosecurity_decisions.get("ready_for_ordering")),
            "sequence_ip_fto_decision_rows": ip_decisions.get("decision_rows"),
            "sequence_ip_fto_approved_for_delivery": ip_decisions.get("approved_for_customer_delivery_rows"),
            "sequence_ip_fto_ready_for_delivery": bool(ip_decisions.get("ready_for_customer_delivery")),
            "provenance_ready": bool(provenance.get("ready_for_release_traceability")),
            "claim_matrix_allowed_claims": claim_matrix.get("claims_allowed"),
            "claim_matrix_blocked_claims": claim_matrix.get("claims_blocked"),
            "claim_promotion_decision_success": claim_promotion.get("ready_for_claim_promotion") is True,
            "claim_promotion_decision_validation_success": claim_promotion.get("success") is True,
            "claim_promotion_decision_validation_failures": claim_promotion.get("failure_count"),
            "claim_promotion_template_rows": claim_promotion.get("template_rows"),
            "claim_promotion_template_matches_expected_contract": claim_promotion.get("template_matches_expected_contract") is True,
            "claim_promotion_target_claim_rows": claim_promotion.get("target_claim_rows"),
            "claim_promotion_requirement_name": claim_promotion.get("claim_promotion_requirement_name"),
            "claim_promotion_target_claim_rows_with_contract_requirement": claim_promotion.get("target_claim_rows_with_promotion_contract_requirement"),
            "claim_promotion_target_claim_rows_with_contract_requirement_passed": claim_promotion.get("target_claim_rows_with_promotion_contract_requirement_passed"),
            "claim_promotion_target_claim_contract_requirement_complete": claim_promotion.get("target_claim_promotion_contract_requirement_complete") is True,
            "claim_promotion_target_claim_rows_with_contract_requirement_evidence": claim_promotion.get("target_claim_rows_with_promotion_contract_requirement_evidence"),
            "claim_promotion_target_claim_contract_requirement_evidence_complete": claim_promotion.get("target_claim_promotion_contract_requirement_evidence_complete") is True,
            "claim_promotion_required_evidence_artifact_count": claim_promotion.get("required_evidence_artifact_count"),
            "claim_promotion_required_evidence_artifacts": claim_promotion.get("required_evidence_artifacts"),
            "claim_promotion_required_validation_report_count": claim_promotion.get("required_validation_report_count"),
            "claim_promotion_required_validation_reports": claim_promotion.get("required_validation_reports"),
            "claim_promotion_decision_rows": claim_promotion.get("decision_rows"),
            "claim_promotion_approved_rows": claim_promotion.get("approved_rows"),
            "claim_promotion_missing_decisions": len(claim_promotion.get("missing_promotion_decisions") or []),
            "claim_promotion_validation_failures": len(claim_promotion.get("error_counts") or {}),
            "claim_policy_anchor_success": bool(claim_policy_anchor.get("success")),
            "claim_policy_anchor_failures": claim_policy_anchor.get("failure_count"),
            "claim_policy_anchor_regression_success": bool(claim_policy_anchor_regression.get("success")),
            "claim_policy_anchor_regression_passed_cases": claim_policy_anchor_regression.get("passed_case_count"),
            "claim_policy_anchor_regression_failed_rows": claim_policy_anchor_regression.get("failed_rows"),
            "claim_policy_anchor_regression_real_inputs_mutated": claim_policy_anchor_regression.get("real_inputs_mutated"),
            "claim_policy_version": claim_matrix_fail_closed_policy.get("policy_version"),
            "claim_policy_canonical_sha256": claim_matrix_fail_closed_policy.get("canonical_policy_sha256"),
            "claim_policy_test_vector_sha256": claim_matrix_fail_closed_policy.get("policy_test_vector_sha256"),
            "claim_matrix_fail_closed_policy_success": bool(claim_matrix_fail_closed_policy.get("success")),
            "claim_matrix_fail_closed_policy_failures": len(claim_matrix_fail_closed_policy.get("failures") or []),
            "claim_matrix_fail_closed_policy_allowed_claim_ids": claim_matrix_fail_closed_policy.get("allowed_claim_ids"),
            "claim_matrix_fail_closed_policy_blocked_claim_ids": claim_matrix_fail_closed_policy.get("blocked_claim_ids"),
            "claim_matrix_source_parity_success": bool(claim_matrix_fail_closed_policy.get("source_parity_success")),
            "claim_matrix_canonical_claim_ids": claim_matrix_fail_closed_policy.get("canonical_claim_ids"),
            "claim_matrix_all_claims_ready": bool(claim_matrix_fail_closed_policy.get("all_claims_ready")),
            "claim_matrix_not_ready_claim_ids": claim_matrix_fail_closed_policy.get("not_ready_claim_ids"),
            "claim_matrix_promotion_policy_allows_all_claims": bool(claim_matrix_fail_closed_policy.get("promotion_policy_allows_all_claims")),
            "claim_matrix_policy_current_success": bool(claim_matrix_policy_current.get("success")),
            "claim_matrix_policy_current_failures": claim_matrix_policy_current.get("failure_count"),
            "claim_matrix_policy_current_regression_success": bool(claim_matrix_policy_current_regression.get("success")),
            "claim_matrix_policy_current_regression_passed_cases": claim_matrix_policy_current_regression.get("passed_case_count"),
            "claim_matrix_policy_current_regression_failed_rows": claim_matrix_policy_current_regression.get("failed_rows"),
            "claim_matrix_policy_current_regression_real_inputs_mutated": claim_matrix_policy_current_regression.get("real_inputs_mutated"),
            "human_decision_backlog_open_items": human_backlog.get("open_items"),
            "human_decision_backlog_missing_rows": human_backlog.get("total_missing_rows"),
            "human_decision_backlog_fail_closed_consistency_success": bool(human_backlog_fail_closed_consistency.get("success")),
            "human_decision_backlog_fail_closed_consistency_failures": len(human_backlog_fail_closed_consistency.get("failures") or []),
            "human_decision_backlog_fail_closed_consistency_open_items": human_backlog_fail_closed_consistency.get("open_items"),
            "human_decision_backlog_fail_closed_consistency_missing_rows": human_backlog_fail_closed_consistency.get("total_missing_rows"),
            "human_decision_reviewer_input_backlog_items": (human_decision_reviewer_input_package.get("backlog_summary") or {}).get("backlog_items"),
            "human_decision_reviewer_input_missing_rows": (human_decision_reviewer_input_package.get("backlog_summary") or {}).get("missing_rows"),
            "human_decision_pending_index_rows": human_decision_pending_row_index.get("indexed_rows"),
            "human_decision_pending_index_formal_decision_rows_written": human_decision_pending_row_index.get("formal_decision_rows_written"),
            "human_decision_review_batch_count": (human_decision_review_batches.get("summary") or {}).get("batch_count"),
            "human_decision_review_batches_validation_success": bool(human_decision_review_batches_validation.get("success")),
            "human_decision_review_batches_validation_failures": human_decision_review_batches_validation.get("failure_count"),
            "human_decision_priority_queue_batches": (human_decision_priority_queue.get("summary") or {}).get("batch_count"),
            "human_decision_priority_queue_p0_batches": (human_decision_priority_queue.get("summary") or {}).get("p0_batch_count"),
            "human_decision_batch_session_count": (human_decision_batch_session_board.get("summary") or {}).get("session_count"),
            "human_decision_batch_session_assigned_count": (human_decision_batch_session_board.get("summary") or {}).get("assigned_count"),
            "human_decision_batch_session_validation_success": bool(human_decision_batch_session_board_validation.get("success")),
            "human_decision_release_blocker_rows": (human_decision_release_blocker_matrix.get("summary") or {}).get("rows"),
            "human_decision_release_blocker_missing_rows": (human_decision_release_blocker_matrix.get("summary") or {}).get("missing_rows"),
            "human_decision_next_closeout_target_blockers": (human_decision_next_closeout_package.get("summary") or {}).get("target_blockers"),
            "human_decision_next_closeout_missing_rows_in_scope": (human_decision_next_closeout_package.get("summary") or {}).get("total_missing_rows_in_scope"),
            "human_decision_first_assignment_count": (human_decision_first_assignment_wave.get("summary") or {}).get("assignment_count"),
            "human_decision_first_assignment_target_rows": (human_decision_first_assignment_wave.get("summary") or {}).get("target_rows"),
            "human_decision_first_assignment_validation_success": bool(human_decision_first_assignment_wave_validation.get("success")),
            "human_decision_control_plane_validation_success": bool(
                load_json(AI_ROOT / "reports" / "local_release_human_decision_control_plane_validation_report_20260806.json").get("success")
            ),
            "human_review_launch_rows": human_review_launch.get("launch_rows"),
            "human_review_launch_ready_for_review_rows": human_review_launch.get("ready_for_human_review_rows"),
            "human_review_launch_total_packet_rows": human_review_launch.get("total_packet_rows"),
            "human_review_launch_completion_ready_rows": human_review_launch.get("completion_ready_rows"),
            "human_review_launch_validation_success": bool(human_review_launch_validation.get("success")),
            "human_review_closeout_rows": human_review_closeout.get("closeout_rows"),
            "human_review_closeout_awaiting_decision_rows": human_review_closeout.get("awaiting_human_decision_rows"),
            "human_review_closeout_total_prepared_packet_rows": human_review_closeout.get("total_prepared_packet_rows"),
            "human_review_closeout_total_formal_decision_rows": human_review_closeout.get("total_formal_decision_rows"),
            "human_review_closeout_completion_ready_rows": human_review_closeout.get("completion_ready_rows"),
            "human_review_closeout_validation_success": bool(human_review_closeout_validation.get("success")),
            "human_review_release_consistency_success": bool(human_review_release_consistency.get("success")),
            "human_review_release_consistency_failures": len(human_review_release_consistency.get("failures") or []),
            "governance_review_bundle_rows": governance_review_bundle.get("bundle_rows"),
            "governance_review_bundle_open_rows": governance_review_bundle.get("open_rows"),
            "governance_review_bundle_completion_ready_rows": governance_review_bundle.get("completion_ready_rows"),
            "governance_review_bundle_ready": bool(governance_review_bundle.get("ready")),
            "governance_review_bundle_valid_rows": governance_review_bundle_validation.get("valid_rows"),
            "governance_review_bundle_all_source_rows_covered": bool(governance_review_bundle_validation.get("all_source_rows_covered")),
            "governance_review_bundle_validation_ready": bool(governance_review_bundle_validation.get("ready")),
            "p478_governance_review_bundle_gap_audit_rows": p478_governance_review_bundle_gap_audit.get("audit_rows"),
            "p478_governance_review_bundle_gap_audit_open_rows": p478_governance_review_bundle_gap_audit.get("open_rows"),
            "p478_governance_review_bundle_gap_audit_completion_ready_rows": p478_governance_review_bundle_gap_audit.get("completion_ready_rows"),
            "p478_governance_review_bundle_gap_audit_validation_success": bool(p478_governance_review_bundle_gap_audit_validation.get("success")),
            "p479_customer_delivery_readiness_gap_audit_rows": p479_customer_delivery_readiness_gap_audit.get("audit_rows"),
            "p479_customer_delivery_readiness_gap_audit_blocker_rows": p479_customer_delivery_readiness_gap_audit.get("blocker_audit_rows"),
            "p479_customer_delivery_readiness_gap_audit_failed_checks": p479_customer_delivery_readiness_gap_audit.get("failed_checks"),
            "p479_customer_delivery_readiness_gap_audit_validation_success": bool(p479_customer_delivery_readiness_gap_audit_validation.get("success")),
            "p480_claim_readiness_blocker_gap_audit_rows": p480_claim_readiness_blocker_gap_audit.get("audit_rows"),
            "p480_claim_readiness_blocker_gap_audit_blocked_rows": p480_claim_readiness_blocker_gap_audit.get("blocked_claim_rows"),
            "p480_claim_readiness_blocker_gap_audit_validation_success": bool(p480_claim_readiness_blocker_gap_audit_validation.get("success")),
            "p481_blocked_capability_gap_audit_rows": p481_local_release_blocked_capability_gap_audit.get("audit_rows"),
            "p481_blocked_capability_gap_audit_blocked_rows": p481_local_release_blocked_capability_gap_audit.get("blocked_capability_rows"),
            "p481_blocked_capability_gap_audit_validation_success": bool(p481_local_release_blocked_capability_gap_audit_validation.get("success")),
            "p482_master_stream_gap_audit_rows": p482_master_readiness_stream_gap_audit.get("audit_rows"),
            "p482_master_stream_gap_audit_blocked_rows": p482_master_readiness_stream_gap_audit.get("blocked_stream_rows"),
            "p482_master_stream_gap_audit_validation_success": bool(p482_master_readiness_stream_gap_audit_validation.get("success")),
            "p483_next_unlock_gap_audit_rows": p483_next_unlock_execution_gap_audit.get("audit_rows"),
            "p483_next_unlock_gap_audit_blocked_rows": p483_next_unlock_execution_gap_audit.get("blocked_gap_rows"),
            "p483_next_unlock_gap_audit_validation_success": bool(p483_next_unlock_execution_gap_audit_validation.get("success")),
            "p484_operator_navigation_gap_audit_rows": p484_next_unlock_operator_navigation_gap_audit.get("audit_rows"),
            "p484_operator_navigation_gap_audit_open_rows": p484_next_unlock_operator_navigation_gap_audit.get("open_item_rows"),
            "p484_operator_navigation_gap_audit_validation_success": bool(p484_next_unlock_operator_navigation_gap_audit_validation.get("success")),
            "p485_blocker_matrix_gap_audit_rows": p485_next_unlock_blocker_matrix_gap_audit.get("audit_rows"),
            "p485_blocker_matrix_gap_audit_open_rows": p485_next_unlock_blocker_matrix_gap_audit.get("open_blocker_rows"),
            "p485_blocker_matrix_gap_audit_validation_success": bool(p485_next_unlock_blocker_matrix_gap_audit_validation.get("success")),
            "p486_remediation_queue_gap_audit_rows": p486_next_unlock_remediation_queue_gap_audit.get("audit_rows"),
            "p486_remediation_queue_gap_audit_open_rows": p486_next_unlock_remediation_queue_gap_audit.get("open_rows"),
            "p486_remediation_queue_gap_audit_validation_success": bool(p486_next_unlock_remediation_queue_gap_audit_validation.get("success")),
            "p487_multi_agent_launch_gap_audit_rows": p487_next_unlock_multi_agent_launch_gap_audit.get("audit_rows"),
            "p487_multi_agent_launch_gap_audit_open_rows": p487_next_unlock_multi_agent_launch_gap_audit.get("open_blocked_rows"),
            "p487_multi_agent_launch_gap_audit_validation_success": bool(p487_next_unlock_multi_agent_launch_gap_audit_validation.get("success")),
            "p488_agent_lane_status_gap_audit_rows": p488_next_unlock_agent_lane_status_gap_audit.get("audit_rows"),
            "p488_agent_lane_status_gap_audit_open_rows": p488_next_unlock_agent_lane_status_gap_audit.get("started_blocked_lanes"),
            "p488_agent_lane_status_gap_audit_validation_success": bool(p488_next_unlock_agent_lane_status_gap_audit_validation.get("success")),
            "p489_lane_dispatch_gap_audit_rows": p489_next_unlock_lane_dispatch_gap_audit.get("audit_rows"),
            "p489_lane_dispatch_gap_audit_open_rows": p489_next_unlock_lane_dispatch_gap_audit.get("dispatch_ready_blocked_packets"),
            "p489_lane_dispatch_gap_audit_validation_success": bool(p489_next_unlock_lane_dispatch_gap_audit_validation.get("success")),
            "p490_action_checklist_gap_audit_rows": p490_next_unlock_action_checklist_gap_audit.get("audit_rows"),
            "p490_action_checklist_gap_audit_open_rows": p490_next_unlock_action_checklist_gap_audit.get("open_blocked_checklist_rows"),
            "p490_action_checklist_gap_audit_validation_success": bool(p490_next_unlock_action_checklist_gap_audit_validation.get("success")),
            "p491_operator_work_ledger_gap_audit_rows": p491_next_unlock_operator_work_ledger_gap_audit.get("audit_rows"),
            "p491_operator_work_ledger_gap_audit_open_rows": p491_next_unlock_operator_work_ledger_gap_audit.get("open_blocked_ledger_rows"),
            "p491_operator_work_ledger_gap_audit_validation_success": bool(p491_next_unlock_operator_work_ledger_gap_audit_validation.get("success")),
            "p492_operator_work_receipt_gap_audit_rows": p492_next_unlock_operator_work_receipt_gap_audit.get("audit_rows"),
            "p492_operator_work_receipt_gap_audit_open_rows": p492_next_unlock_operator_work_receipt_gap_audit.get("open_blocked_receipt_rows"),
            "p492_operator_work_receipt_gap_audit_validation_success": bool(p492_next_unlock_operator_work_receipt_gap_audit_validation.get("success")),
            "p493_human_review_closeout_gap_audit_rows": p493_human_review_closeout_gap_audit.get("audit_rows"),
            "p493_human_review_closeout_gap_audit_open_rows": p493_human_review_closeout_gap_audit.get("awaiting_human_decision_rows"),
            "p493_human_review_closeout_gap_audit_validation_success": bool(p493_human_review_closeout_gap_audit_validation.get("success")),
            "p494_operator_work_receipt_manifest_gap_audit_rows": p494_operator_work_receipt_manifest_consistency_gap_audit.get("audit_rows"),
            "p494_operator_work_receipt_manifest_gap_audit_open_rows": p494_operator_work_receipt_manifest_consistency_gap_audit.get("open_blocked_receipt_rows"),
            "p494_operator_work_receipt_manifest_gap_audit_validation_success": bool(p494_operator_work_receipt_manifest_consistency_gap_audit_validation.get("success")),
            "next_unlock_blocked_unlocks": next_unlock.get("blocked_unlocks"),
            "next_unlock_action_rows": next_unlock.get("action_rows"),
            "next_unlock_capability_unlocks_ready": next_unlock.get("capability_unlocks_ready"),
            "next_unlock_started_actions": next_unlock_execution.get("started_actions"),
            "next_unlock_not_started_actions": next_unlock_execution.get("not_started_actions"),
            "next_unlock_completion_ready_actions": next_unlock_execution.get("completion_ready_actions"),
            "next_unlock_validated_completion_ready_actions": next_unlock_validation.get("completion_ready_actions"),
            "next_unlock_validated_blocked_actions": next_unlock_validation.get("blocked_actions"),
            "next_unlock_validated_completion_ready_stages": next_unlock_validation.get("completion_ready_stage_count"),
            "next_unlock_operator_index_rows": next_unlock_operator_index.get("total_actions"),
            "next_unlock_operator_index_open_items": next_unlock_operator_index.get("open_items"),
            "next_unlock_operator_index_completion_ready_items": next_unlock_operator_index.get("completion_ready_items"),
            "next_unlock_blocker_rows": next_unlock_blockers.get("blocker_rows"),
            "next_unlock_critical_blockers": next_unlock_blockers.get("critical_blockers"),
            "next_unlock_high_blockers": next_unlock_blockers.get("high_blockers"),
            "next_unlock_remediation_queue_rows": next_unlock_remediation.get("queue_rows"),
            "next_unlock_remediation_open_items": next_unlock_remediation.get("open_items"),
            "next_unlock_remediation_ready_to_start_items": next_unlock_remediation.get("ready_to_start_items"),
            "next_unlock_multi_agent_launch_items": next_unlock_multi_agent.get("total_launch_items"),
            "next_unlock_multi_agent_launch_rows": next_unlock_multi_agent.get("launch_rows"),
            "next_unlock_multi_agent_started_items": next_unlock_multi_agent.get("started_items"),
            "next_unlock_multi_agent_ready_to_launch_items": next_unlock_multi_agent.get("ready_to_launch_items"),
            "next_unlock_multi_agent_blocked_launch_items": next_unlock_multi_agent.get("blocked_launch_items"),
            "next_unlock_multi_agent_completion_ready_items": next_unlock_multi_agent.get("completion_ready_items"),
            "next_unlock_multi_agent_requires_human_input_items": next_unlock_multi_agent.get("requires_human_input_items"),
            "next_unlock_multi_agent_lanes": next_unlock_multi_agent.get("local_agent_lanes"),
            "next_unlock_multi_agent_agent_count": next_unlock_multi_agent.get("agent_count"),
            "next_unlock_multi_agent_parallel_groups": next_unlock_multi_agent.get("parallel_groups"),
            "next_unlock_multi_agent_validated_launch_rows": next_unlock_multi_agent_validation.get("validated_launch_rows"),
            "next_unlock_multi_agent_invalid_launch_rows": next_unlock_multi_agent_validation.get("invalid_launch_rows"),
            "pending_stage_all_started_success": bool(pending_stage_all_started_validation.get("success")),
            "pending_stage_all_started_stage_count": pending_stage_all_started.get("stage_count"),
            "pending_stage_all_started_started_stage_count": pending_stage_all_started.get("started_stage_count"),
            "pending_stage_all_started_agent_delegated_stage_count": pending_stage_all_started.get("agent_delegated_stage_count"),
            "active_stage_execution_matrix_success": bool(active_stage_execution_matrix_validation.get("success")),
            "active_stage_execution_matrix_stage_count": active_stage_execution_matrix.get("stage_count"),
            "active_stage_execution_matrix_production_execution_allowed": bool(active_stage_execution_matrix.get("production_execution_allowed")),
            "next_unlock_agent_lane_rows": next_unlock_agent_lanes.get("lane_rows"),
            "next_unlock_agent_started_blocked_lanes": next_unlock_agent_lanes.get("started_blocked_lanes"),
            "next_unlock_agent_invalid_lanes": next_unlock_agent_lanes.get("invalid_lanes"),
            "next_unlock_agent_lane_completion_ready_items": next_unlock_agent_lanes.get("completion_ready_items"),
            "next_unlock_lane_dispatch_packets": next_unlock_lane_dispatch.get("dispatch_packets"),
            "next_unlock_lane_dispatch_ready_blocked_packets": next_unlock_lane_dispatch.get("dispatch_ready_blocked_packets"),
            "next_unlock_lane_dispatch_invalid_packets": next_unlock_lane_dispatch.get("invalid_dispatch_packets"),
            "next_unlock_lane_dispatch_missing_local_material_packets": next_unlock_lane_dispatch.get("dispatch_packets_missing_local_materials"),
            "next_unlock_lane_dispatch_completion_ready_items": next_unlock_lane_dispatch.get("completion_ready_items"),
            "next_unlock_lane_dispatch_validated_packets": next_unlock_lane_dispatch_validation.get("validated_dispatch_packets"),
            "next_unlock_lane_dispatch_validation_invalid_packets": next_unlock_lane_dispatch_validation.get("invalid_dispatch_packets"),
            "next_unlock_lane_dispatch_validation_missing_local_material_packets": next_unlock_lane_dispatch_validation.get("missing_local_material_packets"),
            "next_unlock_action_checklist_rows": next_unlock_action_checklist.get("checklist_rows"),
            "next_unlock_action_checklist_open_blocked_rows": next_unlock_action_checklist.get("open_blocked_checklist_rows"),
            "next_unlock_action_checklist_ready_for_local_operator_rows": next_unlock_action_checklist.get("ready_for_local_operator_rows"),
            "next_unlock_action_checklist_completion_ready_items": next_unlock_action_checklist.get("completion_ready_items"),
            "next_unlock_action_checklist_missing_local_material_rows": next_unlock_action_checklist.get("missing_local_material_rows"),
            "next_unlock_action_checklist_validated_rows": next_unlock_action_checklist_validation.get("validated_checklist_rows"),
            "next_unlock_action_checklist_invalid_rows": next_unlock_action_checklist_validation.get("invalid_checklist_rows"),
            "next_unlock_action_checklist_validation_completion_ready_items": next_unlock_action_checklist_validation.get("completion_ready_items"),
            "next_unlock_action_checklist_validation_missing_local_material_rows": next_unlock_action_checklist_validation.get("missing_local_material_rows"),
            "next_unlock_operator_work_ledger_rows": next_unlock_operator_work_ledger.get("ledger_rows"),
            "next_unlock_operator_work_ledger_open_blocked_rows": next_unlock_operator_work_ledger.get("open_blocked_ledger_rows"),
            "next_unlock_operator_work_ledger_ready_for_local_operator_work_rows": next_unlock_operator_work_ledger.get("ready_for_local_operator_work_rows"),
            "next_unlock_operator_work_ledger_completion_ready_items": next_unlock_operator_work_ledger.get("completion_ready_items"),
            "next_unlock_operator_work_ledger_requires_human_input_items": next_unlock_operator_work_ledger.get("requires_human_input_items"),
            "next_unlock_operator_work_ledger_linked_human_backlog_rows": next_unlock_operator_work_ledger.get("linked_human_backlog_rows"),
            "next_unlock_operator_work_ledger_unlinked_human_backlog_rows": next_unlock_operator_work_ledger.get("unlinked_human_backlog_rows"),
            "next_unlock_operator_work_ledger_validated_rows": next_unlock_operator_work_ledger_validation.get("validated_ledger_rows"),
            "next_unlock_operator_work_ledger_invalid_rows": next_unlock_operator_work_ledger_validation.get("invalid_ledger_rows"),
            "next_unlock_operator_work_ledger_validation_completion_ready_items": next_unlock_operator_work_ledger_validation.get("completion_ready_items"),
            "next_unlock_operator_work_ledger_validation_requires_human_input_items": next_unlock_operator_work_ledger_validation.get("requires_human_input_items"),
            "next_unlock_operator_work_receipt_rows": next_unlock_operator_work_receipts.get("receipt_rows"),
            "next_unlock_operator_work_receipt_open_blocked_rows": next_unlock_operator_work_receipts.get("open_blocked_receipt_rows"),
            "next_unlock_operator_work_receipt_completion_ready_items": next_unlock_operator_work_receipts.get("completion_ready_items"),
            "next_unlock_operator_work_receipt_requires_human_input_items": next_unlock_operator_work_receipts.get("requires_human_input_items"),
            "next_unlock_operator_work_receipt_observed_decision_input_rows": next_unlock_operator_work_receipts.get("observed_decision_input_rows"),
            "next_unlock_operator_work_receipt_target_rows_met_items": next_unlock_operator_work_receipts.get("target_rows_met_items"),
            "next_unlock_operator_work_receipt_validated_rows": next_unlock_operator_work_receipt_validation.get("validated_receipt_rows"),
            "next_unlock_operator_work_receipt_invalid_rows": next_unlock_operator_work_receipt_validation.get("invalid_receipt_rows"),
            "next_unlock_operator_work_receipt_validation_completion_ready_items": next_unlock_operator_work_receipt_validation.get("completion_ready_items"),
            "next_unlock_operator_work_receipt_validation_target_rows_met_items": next_unlock_operator_work_receipt_validation.get("target_rows_met_items"),
            "next_unlock_operator_work_receipt_validation_target_rows_met_completion_ready_items": next_unlock_operator_work_receipt_validation.get("target_rows_met_completion_ready_items"),
            "operator_work_receipt_manifest_consistency_success": bool(operator_work_receipt_manifest_consistency.get("success")),
            "operator_work_receipt_manifest_consistency_failures": len(operator_work_receipt_manifest_consistency.get("failures") or []),
            "operator_work_receipt_manifest_consistency_release_ready": operator_work_receipt_manifest_consistency.get("release_ready"),
            "enzyme_analysis_policy_version": enzyme_analysis_policy.get("version"),
            "enzyme_analysis_policy_tool_steps": len(enzyme_analysis_policy.get("tool_sequence") or []),
            "enzyme_analysis_policy_requires_confirmation": bool((enzyme_analysis_policy.get("tool_call_display") or {}).get("user_confirmation_required_before_execution")),
            "enzyme_analysis_policy_rosetta_status": (enzyme_analysis_policy.get("rosetta_integration_status") or {}).get("status"),
            "enzyme_analysis_policy_safe_for_model_claim": bool((enzyme_analysis_policy.get("release_gate") or {}).get("safe_for_model_claim")),
            "model_quality_unlock_rows": model_quality_unlock.get("requirement_rows"),
            "model_quality_unlock_blocked_rows": model_quality_unlock.get("blocked_requirements"),
            "model_quality_unlock_ready_to_verify_rows": model_quality_unlock.get("ready_to_verify_requirements"),
            "model_quality_unlock_complete_rows": model_quality_unlock.get("complete_requirements"),
            "model_quality_unlock_model_quality_ready": model_quality_unlock.get("model_quality_ready"),
            "advanced_model_version": advanced_model.get("version"),
            "advanced_model_status": advanced_model.get("status"),
            "advanced_model_demo_candidate_count": advanced_model.get("demo_candidate_count"),
            "advanced_model_safe_for_model_claim": advanced_model.get("safe_for_model_claim"),
            "advanced_model_scaffold_regression_success": bool(advanced_model_regression.get("success")),
            "advanced_model_scaffold_regression_failures": len(advanced_model_regression.get("failures") or []),
            "advanced_model_scaffold_regression_candidate_rows": advanced_model_regression.get("candidate_rows"),
            "advanced_feature_family_rows": advanced_feature_cache.get("feature_family_rows"),
            "advanced_feature_adapter_requirement_rows": advanced_feature_cache.get("adapter_requirement_rows"),
            "advanced_feature_blocked_adapter_rows": advanced_feature_cache.get("blocked_adapter_rows"),
            "advanced_feature_ready_adapter_rows": advanced_feature_cache.get("ready_adapter_rows"),
            "advanced_feature_manifest": advanced_feature_cache.get("manifest"),
            "advanced_feature_current_state_is_top_tier": bool((advanced_feature_cache.get("top_tier_assessment") or {}).get("current_state_is_top_tier")),
            "enzyme_action_space_action_rows": enzyme_action_space.get("action_rows"),
            "enzyme_action_space_contract_rows": enzyme_action_space.get("contract_rows"),
            "enzyme_action_space_training_write_actions": enzyme_action_space.get("training_write_actions"),
            "enzyme_action_space_safe_for_model_claim_actions": enzyme_action_space.get("safe_for_model_claim_actions"),
            "enzyme_tool_contract_validation_success": bool(enzyme_tool_contract_validation.get("success")),
            "enzyme_tool_contract_validation_failures": len(enzyme_tool_contract_validation.get("failures") or []),
            "enzyme_tool_contract_validation_safe_for_controlled_agent_planning": bool(enzyme_tool_contract_validation.get("safe_for_controlled_agent_planning")),
            "enzyme_resource_retrieval_action_rows": enzyme_resource_retrieval.get("summary", {}).get("action_rows"),
            "enzyme_resource_retrieval_read_only_rows": enzyme_resource_retrieval.get("summary", {}).get("recommended_read_only_rows"),
            "enzyme_resource_retrieval_executable_after_confirmation_rows": enzyme_resource_retrieval.get("summary", {}).get("executable_after_user_confirmation_rows"),
            "enzyme_resource_retrieval_blocked_rows": enzyme_resource_retrieval.get("summary", {}).get("blocked_requires_human_decision_rows"),
            "enzyme_resource_retrieval_forbidden_rows": enzyme_resource_retrieval.get("summary", {}).get("forbidden_for_current_request_rows"),
            "enzyme_resource_retrieval_validation_success": bool(enzyme_resource_retrieval_validation.get("success")),
            "enzyme_resource_retrieval_validation_failures": len(enzyme_resource_retrieval_validation.get("failures") or []),
            "enzyme_resource_retrieval_safe_for_execution": bool(enzyme_resource_retrieval.get("safe_for_execution")),
            "enzyme_agent_result_selected_variants": len(enzyme_agent_result.get("selected_variants") or []),
            "enzyme_agent_result_manual_review_required": bool(enzyme_agent_result.get("manual_review_required")),
            "enzyme_agent_result_validation_success": bool(enzyme_agent_result_validation.get("success")),
            "enzyme_agent_result_validation_failures": len(enzyme_agent_result_validation.get("failures") or []),
            "enzyme_agent_result_safe_for_training_import": bool(enzyme_agent_result.get("safe_for_training_import")),
            "enzyme_agent_result_safe_for_model_claim": bool(enzyme_agent_result.get("safe_for_model_claim")),
            "enzyme_agent_result_safety_regression_success": bool(enzyme_agent_result_regression.get("success")),
            "enzyme_agent_result_safety_regression_cases": enzyme_agent_result_regression.get("case_rows"),
            "enzyme_agent_result_safety_regression_rejected_negative_cases": enzyme_agent_result_regression.get("actual_rejected_negative_cases"),
            "enzyme_agent_result_safety_regression_failed_cases": enzyme_agent_result_regression.get("failed_regression_cases"),
            "enzyme_agent_trace_rows": enzyme_agent_trace.get("trace_rows"),
            "enzyme_agent_trace_executed_action_count": enzyme_agent_trace.get("executed_action_count"),
            "enzyme_agent_trace_validation_success": bool(enzyme_agent_trace_validation.get("success")),
            "enzyme_agent_trace_validation_failures": len(enzyme_agent_trace_validation.get("failures") or []),
            "enzyme_agent_release_guard_order_success": bool(enzyme_agent_release_guard_order.get("success")),
            "enzyme_agent_release_guard_order_failures": len(enzyme_agent_release_guard_order.get("failures") or []),
            "enzyme_agent_release_guard_order_command_count": enzyme_agent_release_guard_order.get("observed_command_count"),
            "enzyme_agent_release_guard_order_regression_success": bool(enzyme_agent_release_guard_order_regression.get("success")),
            "enzyme_agent_release_guard_order_regression_failed_rows": enzyme_agent_release_guard_order_regression.get("failed_rows"),
            "enzyme_agent_release_guard_order_regression_rejected_negative_cases": enzyme_agent_release_guard_order_regression.get("rejected_negative_cases"),
            "enzyme_agent_release_guard_order_current_success": bool(enzyme_agent_release_guard_order_current.get("success")),
            "enzyme_agent_release_guard_order_current_failures": enzyme_agent_release_guard_order_current.get("failure_count"),
            "enzyme_agent_release_guard_order_current_regression_success": bool(enzyme_agent_release_guard_order_current_regression.get("success")),
            "enzyme_agent_release_guard_order_current_regression_failed_rows": enzyme_agent_release_guard_order_current_regression.get("failed_case_count"),
            "enzyme_agent_release_guard_order_atomicity_regression_success": bool(enzyme_agent_release_guard_order_atomicity_regression.get("success")),
            "enzyme_agent_release_guard_order_atomicity_regression_failed_rows": enzyme_agent_release_guard_order_atomicity_regression.get("failed_case_count"),
            "enzyme_agent_execution_wave_pair_atomicity_regression_success": bool(enzyme_agent_execution_wave_pair_atomicity_regression.get("success")),
            "enzyme_agent_execution_wave_pair_atomicity_regression_failed_rows": enzyme_agent_execution_wave_pair_atomicity_regression.get("failed_case_count"),
            "enzyme_agent_execution_receipt_proof_current_success": bool(enzyme_agent_execution_receipt_proof_current.get("success")),
            "enzyme_agent_execution_receipt_proof_current_failures": enzyme_agent_execution_receipt_proof_current.get("failure_count"),
            "enzyme_agent_execution_receipt_proof_current_sha256": sha256(AI_ROOT / "reports" / "enzyme_agent_execution_receipt_proof_current_validation_report.json"),
            "enzyme_agent_execution_receipt_proof_current_regression_success": bool(enzyme_agent_execution_receipt_proof_current_regression.get("success")),
            "enzyme_agent_execution_receipt_proof_current_regression_failed_rows": enzyme_agent_execution_receipt_proof_current_regression.get("failed_case_count"),
            "enzyme_agent_execution_receipt_proof_current_regression_sha256": sha256(AI_ROOT / "reports" / "enzyme_agent_execution_receipt_proof_current_regression_report.json"),
            "stage25_remaining_blocker_cross_binding_success": bool(stage25_remaining_blocker_cross_binding.get("success")),
            "stage25_remaining_blocker_cross_binding_failures": stage25_remaining_blocker_cross_binding.get("failure_count"),
            "stage25_remaining_blocker_cross_binding_shared_rows": stage25_remaining_blocker_cross_binding.get("shared_blocker_rows"),
            "stage25_remaining_blocker_cross_binding_coverage_complete_rows": stage25_remaining_blocker_cross_binding.get("coverage_complete_rows"),
            "stage25_remaining_blocker_cross_binding_regression_success": bool(stage25_remaining_blocker_cross_binding_regression.get("success")),
            "stage25_remaining_blocker_cross_binding_regression_failed_rows": stage25_remaining_blocker_cross_binding_regression.get("failed_rows"),
            "stage25_remaining_blocker_cross_binding_regression_rejected_negative_cases": stage25_remaining_blocker_cross_binding_regression.get("rejected_negative_cases"),
            "enzyme_agent_execution_receipt_rows": enzyme_agent_execution_receipts.get("receipt_rows"),
            "enzyme_agent_execution_receipt_missing_actions": len(enzyme_agent_execution_receipts.get("missing_receipt_action_ids") or []),
            "enzyme_agent_execution_receipt_validation_success": bool(enzyme_agent_execution_receipts_validation.get("success")),
            "enzyme_agent_execution_receipt_validation_failures": len(enzyme_agent_execution_receipts_validation.get("failures") or []),
            "enzyme_agent_execution_receipt_lineage_success": bool(enzyme_agent_execution_receipts_lineage.get("success")),
            "enzyme_agent_execution_receipt_lineage_failures": len(enzyme_agent_execution_receipts_lineage.get("failures") or []),
            "enzyme_agent_execution_receipt_safety_regression_success": bool(enzyme_agent_execution_receipts_regression.get("success")),
            "enzyme_agent_execution_receipt_safety_regression_cases": enzyme_agent_execution_receipts_regression.get("case_rows"),
            "enzyme_agent_execution_receipt_safety_regression_rejected_negative_cases": enzyme_agent_execution_receipts_regression.get("actual_rejected_negative_cases"),
            "enzyme_agent_execution_receipt_safety_regression_failed_cases": enzyme_agent_execution_receipts_regression.get("failed_regression_cases"),
            "enzyme_agent_execution_eligibility_action_rows": enzyme_agent_execution_eligibility.get("action_rows"),
            "enzyme_agent_execution_eligibility_allowed_rows": enzyme_agent_execution_eligibility.get("current_execution_allowed_rows"),
            "enzyme_agent_execution_eligibility_validation_success": bool(enzyme_agent_execution_eligibility_validation.get("success")),
            "enzyme_agent_execution_eligibility_validation_failures": len(enzyme_agent_execution_eligibility_validation.get("failures") or []),
            "enzyme_agent_execution_eligibility_safety_regression_success": bool(enzyme_agent_execution_eligibility_regression.get("success")),
            "enzyme_agent_execution_eligibility_safety_regression_cases": enzyme_agent_execution_eligibility_regression.get("case_rows"),
            "enzyme_agent_execution_eligibility_safety_regression_rejected_negative_cases": enzyme_agent_execution_eligibility_regression.get("actual_rejected_negative_cases"),
            "enzyme_agent_execution_eligibility_safety_regression_failed_cases": enzyme_agent_execution_eligibility_regression.get("failed_regression_cases"),
            "enzyme_agent_execution_outcome_action_rows": enzyme_agent_execution_outcome.get("action_rows"),
            "enzyme_agent_execution_outcome_engineering_ready_rows": enzyme_agent_execution_outcome.get("engineering_ready_rows"),
            "enzyme_agent_execution_outcome_hard_gate_unlocked_rows": enzyme_agent_execution_outcome.get("hard_gate_unlocked_rows"),
            "enzyme_agent_execution_outcome_validation_success": bool(enzyme_agent_execution_outcome_validation.get("success")),
            "enzyme_agent_execution_outcome_validation_failures": len(enzyme_agent_execution_outcome_validation.get("failures") or []),
            "enzyme_agent_execution_outcome_physics_ddg_ready": bool(enzyme_agent_execution_outcome.get("rosetta_pyrosetta_foldx_physics_ddg_ready")),
            "enzyme_agent_execution_outcome_benchmark_ready_for_model_claim": bool(enzyme_agent_execution_outcome.get("benchmark_ready_for_model_claim")),
            "validated_feature_index_rows": validated_feature_index.get("feature_rows"),
            "validated_feature_index_model_consumable_rows": validated_feature_index.get("model_consumable_rows"),
            "validated_feature_index_training_label_source_rows": validated_feature_index.get("training_label_source_rows"),
            "validated_feature_index_validation_success": bool(validated_feature_index_validation.get("success")),
            "validated_feature_index_validation_failures": len(validated_feature_index_validation.get("failures") or []),
            "advanced_model_feature_contract_feature_refs": (advanced_model_feature_contract.get("feature_index_contract") or {}).get("feature_ref_count"),
            "advanced_model_feature_contract_ready_feature_refs": (advanced_model_feature_contract.get("feature_index_contract") or {}).get("advanced_model_ready_feature_ref_count"),
            "advanced_model_feature_contract_training_label_source_refs": (advanced_model_feature_contract.get("feature_index_contract") or {}).get("training_label_source_feature_ref_count"),
            "advanced_model_feature_contract_scaffold_status": (advanced_model_feature_contract.get("advanced_model_contract") or {}).get("status"),
            "advanced_model_feature_contract_safe_for_model_claim": bool(advanced_model_feature_contract.get("safe_for_model_claim")),
            "advanced_model_feature_contract_validation_success": bool(advanced_model_feature_contract_validation.get("success")),
            "advanced_model_feature_contract_validation_failures": len(advanced_model_feature_contract_validation.get("failures") or []),
            "google_github_research_current_state_is_top_tier": bool(google_github_research.get("current_state_is_top_tier")),
            "google_github_research_tool_rows": len(google_github_research.get("tools") or []),
            "google_github_research_safe_for_model_claim": bool(google_github_research.get("safe_for_model_claim")),
            "proteinmcp_research_borrowable_patterns": len(proteinmcp_research.get("borrowable_patterns") or []),
            "proteinmcp_research_recommended_phases": len(proteinmcp_research.get("recommended_kwb_phases") or []),
            "proteinmcp_research_safe_for_model_claim": bool(proteinmcp_research.get("safe_for_model_claim")),
            "proteinmcp_download_attempted": bool(proteinmcp_download_audit.get("user_authorized_temporary_download")),
            "proteinmcp_download_succeeded": bool(proteinmcp_download_audit.get("temporary_download_succeeded")),
            "proteinmcp_download_cleanup_performed": bool(proteinmcp_download_audit.get("cleanup_performed")),
            "proteinmcp_source_code_retained": bool(proteinmcp_download_audit.get("source_code_retained")),
            "kwb_tool_lifecycle_tool_rows": kwb_tool_lifecycle.get("tool_rows"),
            "kwb_tool_lifecycle_validation_success": bool(kwb_tool_lifecycle_validation.get("success")),
            "kwb_tool_lifecycle_production_allowed_rows": kwb_tool_lifecycle.get("production_allowed_rows"),
            "kwb_tool_lifecycle_agent_exposure_allowed_rows": kwb_tool_lifecycle.get("agent_exposure_allowed_rows"),
            "kwb_tool_lifecycle_safe_for_model_claim": bool(kwb_tool_lifecycle.get("safe_for_model_claim")),
            "kwb_workflow_skill_rows": kwb_workflow_skills.get("skill_rows"),
            "kwb_workflow_skill_files_written": kwb_workflow_skills.get("skill_files_written"),
            "kwb_workflow_skill_validation_success": bool(kwb_workflow_skills_validation.get("success")),
            "kwb_workflow_skill_production_execution_allowed_rows": kwb_workflow_skills.get("production_execution_allowed_rows"),
            "kwb_workflow_skill_safe_for_model_claim": bool(kwb_workflow_skills.get("safe_for_model_claim")),
            "mcp_wrapper_staging_queue_rows": mcp_wrapper_staging.get("queue_rows"),
            "mcp_wrapper_staging_ready_rows": mcp_wrapper_staging.get("staging_ready_rows"),
            "mcp_wrapper_staging_validation_success": bool(mcp_wrapper_staging_validation.get("success")),
            "mcp_wrapper_staging_production_allowed_rows": mcp_wrapper_staging.get("production_allowed_rows"),
            "mcp_wrapper_staging_agent_exposure_allowed_rows": mcp_wrapper_staging.get("agent_exposure_allowed_rows"),
            "mcp_wrapper_staging_safe_for_model_claim": bool(mcp_wrapper_staging.get("safe_for_model_claim")),
            "top_tier_model_total_workstreams": top_tier_execution.get("total_workstreams"),
            "top_tier_model_started_workstreams": top_tier_execution.get("started_workstreams"),
            "top_tier_model_blocked_workstreams": top_tier_execution.get("blocked_workstreams"),
            "top_tier_model_ready_to_verify_workstreams": top_tier_execution.get("ready_to_verify_workstreams"),
            "top_tier_model_completion_ready_workstreams": top_tier_execution.get("completion_ready_workstreams"),
            "top_tier_model_validation_success": bool(top_tier_validation.get("success")),
            "top_tier_model_validation_failed_checks": top_tier_validation.get("failed_checks"),
            "top_tier_model_ready_receipt_rows": top_tier_ready_receipts.get("receipt_rows"),
            "p495_top_tier_ready_receipt_gap_audit_rows": p495_top_tier_ready_to_verify_receipt_gap_audit.get("audit_rows"),
            "p495_top_tier_ready_receipt_gap_audit_open_rows": p495_top_tier_ready_to_verify_receipt_gap_audit.get("receipt_audit_rows"),
            "p495_top_tier_ready_receipt_gap_audit_validation_success": bool(p495_top_tier_ready_to_verify_receipt_gap_audit_validation.get("success")),
            "top_tier_model_ready_receipt_valid_rows": top_tier_ready_receipt_validation.get("valid_receipt_rows"),
            "top_tier_model_ready_receipt_invalid_rows": top_tier_ready_receipt_validation.get("invalid_receipt_rows"),
            "top_tier_model_ready_receipt_validation_success": bool(top_tier_ready_receipt_validation.get("success")),
            "top_tier_model_ready_receipts_safe_for_training_import": bool(top_tier_ready_receipts.get("safe_for_training_import")),
            "top_tier_model_ready_receipts_safe_for_model_claim": bool(top_tier_ready_receipts.get("safe_for_model_claim")),
            "non_human_construction_total_workstreams": non_human_construction.get("total_workstreams"),
            "non_human_construction_started_workstreams": non_human_construction.get("started_workstreams"),
            "non_human_construction_ready_to_verify_workstreams": non_human_construction.get("started_ready_to_verify_workstreams"),
            "non_human_construction_blocked_workstreams": non_human_construction.get("started_blocked_workstreams"),
            "non_human_construction_validation_success": bool(non_human_construction_validation.get("success")),
            "non_human_construction_validation_failed_checks": non_human_construction_validation.get("failed_checks"),
            "non_human_ready_receipt_rows": non_human_ready_receipts.get("receipt_rows"),
            "p496_non_human_ready_receipt_gap_audit_rows": p496_non_human_ready_to_verify_receipt_gap_audit.get("audit_rows"),
            "p496_non_human_ready_receipt_gap_audit_open_rows": p496_non_human_ready_to_verify_receipt_gap_audit.get("receipt_audit_rows"),
            "p496_non_human_ready_receipt_gap_audit_validation_success": bool(p496_non_human_ready_to_verify_receipt_gap_audit_validation.get("success")),
            "non_human_ready_receipt_verification_passed_workstreams": non_human_ready_receipts.get("verification_passed_workstreams"),
            "non_human_ready_receipt_blocked_workstreams_not_executed": bool(non_human_ready_receipts.get("blocked_workstreams_not_executed")),
            "non_human_ready_receipt_validation_success": bool(non_human_ready_receipt_validation.get("success")),
            "non_human_ready_receipt_validation_failed_checks": non_human_ready_receipt_validation.get("failed_checks"),
            "ready_to_verify_promotion_audit_rows": ready_to_verify_promotion.get("audit_rows"),
            "ready_to_verify_promotion_local_artifact_rows": ready_to_verify_promotion.get("local_artifact_completion_rows"),
            "ready_to_verify_promotion_verified_blocked_rows": ready_to_verify_promotion.get("verified_blocked_rows"),
            "ready_to_verify_promotion_automatic_rows": ready_to_verify_promotion.get("automatic_promotion_rows"),
            "ready_to_verify_promotion_validation_success": bool(ready_to_verify_promotion_validation.get("success")),
            "ready_to_verify_promotion_validation_failures": ready_to_verify_promotion_validation.get("failure_count"),
            "ready_to_verify_promotion_regression_success": bool(ready_to_verify_promotion_regression.get("success")),
            "ready_to_verify_promotion_regression_failed_rows": ready_to_verify_promotion_regression.get("failed_rows"),
            "ready_to_verify_promotion_release_summary_regression_success": bool(ready_to_verify_promotion_release_summary_regression.get("success")),
            "ready_to_verify_promotion_release_summary_regression_failed_rows": ready_to_verify_promotion_release_summary_regression.get("failed_rows"),
            "data_lake_artifact_integrity_regression_success": bool(data_lake_artifact_integrity_regression.get("success")),
            "data_lake_artifact_integrity_regression_failed_rows": data_lake_artifact_integrity_regression.get("failed_rows"),
            "local_release_high_risk_summary_regression_success": bool(local_release_high_risk_summary_regression.get("success")),
            "local_release_high_risk_summary_regression_failed_rows": local_release_high_risk_summary_regression.get("failed_rows"),
            "local_release_high_risk_coverage_regression_success": bool(local_release_high_risk_coverage_regression.get("success")),
            "local_release_high_risk_coverage_regression_failed_rows": local_release_high_risk_coverage_regression.get("failed_rows"),
            "data_lake_live_content_integrity_success": bool(data_lake_live_content_integrity.get("success")),
            "data_lake_live_content_integrity_failure_count": data_lake_live_content_integrity.get("failure_count"),
            "data_lake_live_content_integrity_validated_root": data_lake_live_content_integrity.get("validated_root"),
            "data_lake_live_content_integrity_validated_manifest_path": data_lake_live_content_integrity.get("validated_manifest_path"),
            "data_lake_live_content_integrity_release_input_contract_version": data_lake_live_content_integrity.get("release_input_contract_version"),
            "data_lake_live_content_integrity_release_input_contract_sha256": data_lake_live_content_integrity.get("release_input_contract_sha256"),
            "data_lake_live_content_integrity_release_input_artifact_rows": data_lake_live_content_integrity.get("release_input_artifact_rows"),
            "data_lake_live_content_integrity_release_input_excluded_paths": data_lake_live_content_integrity.get("release_input_excluded_paths"),
            "data_lake_live_content_integrity_artifact_rows": data_lake_live_content_integrity.get("artifact_rows"),
            "data_lake_live_content_integrity_strict_verified_rows": data_lake_live_content_integrity.get("strict_verified_rows"),
            "data_lake_live_content_integrity_volatile_rows": data_lake_live_content_integrity.get("volatile_existence_only_rows"),
            "data_lake_live_content_integrity_regression_success": bool(data_lake_live_content_integrity_regression.get("success")),
            "data_lake_live_content_integrity_regression_failed_rows": data_lake_live_content_integrity_regression.get("failed_rows"),
            "data_lake_volatile_exemption_regression_success": bool(data_lake_volatile_exemption_regression.get("success")),
            "data_lake_volatile_exemption_regression_failed_rows": data_lake_volatile_exemption_regression.get("failed_rows"),
            "local_release_live_integrity_binding_regression_success": bool(local_release_live_integrity_binding_regression.get("success")),
            "local_release_live_integrity_binding_regression_failed_rows": local_release_live_integrity_binding_regression.get("failed_rows"),
            "release_input_contract_policy_success": bool(release_input_contract_policy.get("success")),
            "release_input_contract_policy_failures": release_input_contract_policy.get("failure_count"),
            "release_input_contract_policy_regression_success": bool(release_input_contract_policy_regression.get("success")),
            "release_input_contract_policy_regression_failed_rows": release_input_contract_policy_regression.get("failed_rows"),
            "release_input_contract_policy_module_path": release_input_contract_policy.get("contract_module_path"),
            "release_input_contract_policy_module_sha256": release_input_contract_policy.get("contract_module_sha256"),
            "release_input_contract_policy_expected_version": release_input_contract_policy.get("expected_contract_version"),
            "release_input_contract_policy_expected_excluded_paths": release_input_contract_policy.get("expected_excluded_paths"),
            "release_input_contract_policy_expected_test_vector_sha256": release_input_contract_policy.get("expected_test_vector_sha256"),
            "local_release_contract_policy_binding_regression_success": bool(local_release_contract_policy_binding_regression.get("success")),
            "local_release_contract_policy_binding_regression_failed_rows": local_release_contract_policy_binding_regression.get("failed_rows"),
            "stage25_operator_docs_dynamic_sync_success": bool(stage25_docs_sync.get("success")),
            "stage25_operator_docs_dynamic_sync_failures": stage25_docs_sync.get("failure_count"),
            "stage25_operator_docs_dynamic_sync_target_rows": stage25_docs_sync.get("target_rows"),
            "stage25_operator_docs_dynamic_sync_contract_version": stage25_docs_sync.get("contract_version"),
            "stage25_operator_docs_dynamic_sync_contract_sha256": stage25_docs_sync.get("contract_sha256"),
            "stage25_operator_docs_dynamic_sync_provenance_rows": stage25_docs_sync.get("provenance_row_count"),
            "stage25_operator_docs_dynamic_sync_provenance_sha256": stage25_docs_sync.get("provenance_sha256"),
            "stage25_operator_docs_dynamic_sync_observed_provenance_sha256": stage25_docs_sync.get("observed_provenance_sha256"),
            "stage25_operator_docs_dynamic_sync_lock_path": stage25_docs_sync.get("lock_path"),
            "stage25_operator_docs_dynamic_sync_output_path": stage25_docs_sync.get("observed_output_path"),
            "stage25_operator_docs_dynamic_sync_regression_success": bool(stage25_docs_sync_regression.get("success")),
            "stage25_operator_docs_dynamic_sync_regression_failed_rows": stage25_docs_sync_regression.get("failed_rows"),
            "stage25_operator_docs_dynamic_sync_regression_sha256": sha256(AI_ROOT / "reports" / "stage25_operator_docs_dynamic_status_sync_regression_report.json"),
            "stage25_operator_docs_dynamic_sync_regression_current_success": bool(stage25_docs_sync_regression_current.get("success")),
            "stage25_operator_docs_dynamic_sync_regression_current_failures": stage25_docs_sync_regression_current.get("failure_count"),
            "stage25_operator_docs_dynamic_sync_regression_current_sha256": sha256(AI_ROOT / "reports" / "stage25_operator_docs_dynamic_status_sync_regression_current_validation_report.json"),
            "stage25_operator_docs_dynamic_sync_regression_current_regression_success": bool(stage25_docs_sync_regression_current_regression.get("success")),
            "stage25_operator_docs_dynamic_sync_regression_current_regression_failures": stage25_docs_sync_regression_current_regression.get("failure_count"),
            "stage25_operator_docs_dynamic_sync_regression_current_regression_sha256": sha256(AI_ROOT / "reports" / "stage25_operator_docs_dynamic_status_sync_regression_current_regression_report.json"),
            "stage25_operator_docs_dynamic_sync_regression_atomicity_success": bool(stage25_docs_sync_regression_atomicity.get("success")),
            "stage25_operator_docs_dynamic_sync_regression_atomicity_failures": stage25_docs_sync_regression_atomicity.get("failure_count"),
            "stage25_operator_docs_dynamic_sync_regression_atomicity_sha256": sha256(AI_ROOT / "reports" / "stage25_operator_docs_dynamic_status_sync_regression_atomicity_regression_report.json"),
            "stage25_operator_docs_sync_contract_policy_success": bool(stage25_docs_sync_policy.get("success")),
            "stage25_operator_docs_sync_contract_policy_failures": stage25_docs_sync_policy.get("failure_count"),
            "stage25_operator_docs_sync_contract_policy_module_path": stage25_docs_sync_policy.get("contract_module_path"),
            "stage25_operator_docs_sync_contract_policy_module_sha256": stage25_docs_sync_policy.get("contract_module_sha256"),
            "stage25_operator_docs_sync_contract_policy_expected_version": stage25_docs_sync_policy.get("expected_contract_version"),
            "stage25_operator_docs_sync_contract_policy_expected_contract_sha256": stage25_docs_sync_policy.get("expected_contract_sha256"),
            "stage25_operator_docs_sync_contract_policy_expected_semantic_projection_version": stage25_docs_sync_policy.get("expected_semantic_projection_version"),
            "stage25_operator_docs_sync_contract_policy_expected_semantic_projection_test_vector_sha256": stage25_docs_sync_policy.get("expected_semantic_projection_test_vector_sha256"),
            "stage25_operator_docs_sync_contract_policy_regression_success": bool(stage25_docs_sync_policy_regression.get("success")),
            "stage25_operator_docs_sync_contract_policy_regression_failed_rows": stage25_docs_sync_policy_regression.get("failed_rows"),
            "stage25_operator_docs_sync_current_receipt_success": bool(stage25_docs_sync_current.get("success")),
            "p497_stage25_docs_sync_receipt_gap_audit_rows": p497_stage25_operator_docs_sync_receipt_gap_audit.get("audit_rows"),
            "p497_stage25_docs_sync_receipt_gap_audit_target_rows": p497_stage25_operator_docs_sync_receipt_gap_audit.get("target_rows"),
            "p497_stage25_docs_sync_receipt_gap_audit_validation_success": bool(p497_stage25_operator_docs_sync_receipt_gap_audit_validation.get("success")),
            "p498_safe_training_pipeline_receipt_gap_audit_rows": p498_safe_training_pipeline_current_receipt_gap_audit.get("audit_rows"),
            "p498_safe_training_pipeline_receipt_gap_audit_failure_count": p498_safe_training_pipeline_current_receipt_gap_audit.get("pipeline_failure_count"),
            "p498_safe_training_pipeline_receipt_gap_audit_validation_success": bool(p498_safe_training_pipeline_current_receipt_gap_audit_validation.get("success")),
            "p499_local_release_consistency_receipt_gap_audit_rows": p499_local_release_consistency_receipt_gap_audit.get("audit_rows"),
            "p499_local_release_consistency_receipt_gap_audit_failure_count": p499_local_release_consistency_receipt_gap_audit.get("source_failure_count"),
            "p499_local_release_consistency_receipt_gap_audit_validation_success": bool(p499_local_release_consistency_receipt_gap_audit_validation.get("success")),
            "p500_stage25_fail_closed_receipt_gap_audit_rows": p500_stage25_fail_closed_validation_current_receipt_gap_audit.get("audit_rows"),
            "p500_stage25_fail_closed_receipt_gap_audit_failure_count": p500_stage25_fail_closed_validation_current_receipt_gap_audit.get("source_failure_count"),
            "p500_stage25_fail_closed_receipt_gap_audit_validation_success": bool(p500_stage25_fail_closed_validation_current_receipt_gap_audit_validation.get("success")),
            "p501_ready_to_verify_promotion_gap_audit_rows": p501_ready_to_verify_promotion_gap_audit.get("audit_rows"),
            "p501_ready_to_verify_promotion_gap_audit_blocked_rows": p501_ready_to_verify_promotion_gap_audit.get("verified_blocked_rows"),
            "p501_ready_to_verify_promotion_gap_audit_validation_success": bool(p501_ready_to_verify_promotion_gap_audit_validation.get("success")),
            "p502_safety_guard_link_gap_audit_rows": p502_local_release_safety_guard_link_gap_audit.get("audit_rows"),
            "p502_safety_guard_link_gap_audit_guard_links": p502_local_release_safety_guard_link_gap_audit.get("guard_link_count"),
            "p502_safety_guard_link_gap_audit_validation_success": bool(p502_local_release_safety_guard_link_audit_validation.get("success")),
            "p503_safe_pipeline_receipt_atomicity_gap_audit_rows": p503_safe_training_pipeline_receipt_atomicity_gap_audit.get("audit_rows"),
            "p503_safe_pipeline_receipt_atomicity_gap_audit_failed_rows": p503_safe_training_pipeline_receipt_atomicity_gap_audit.get("source_failed_rows"),
            "p503_safe_pipeline_receipt_atomicity_gap_audit_validation_success": bool(p503_safe_training_pipeline_receipt_atomicity_gap_audit_validation.get("success")),
            "p504_local_release_consistency_atomicity_gap_audit_rows": p504_local_release_consistency_receipt_atomicity_gap_audit.get("audit_rows"),
            "p504_local_release_consistency_atomicity_gap_audit_failed_rows": p504_local_release_consistency_receipt_atomicity_gap_audit.get("source_failed_rows"),
            "p504_local_release_consistency_atomicity_gap_audit_validation_success": bool(p504_local_release_consistency_receipt_atomicity_gap_audit_validation.get("success")),
            "p505_local_release_terminal_defer_gap_audit_rows": p505_local_release_terminal_defer_mode_gap_audit.get("audit_rows"),
            "p505_local_release_terminal_defer_gap_audit_failed_rows": p505_local_release_terminal_defer_mode_gap_audit.get("source_failed_rows"),
            "p505_local_release_terminal_defer_gap_audit_validation_success": bool(p505_local_release_terminal_defer_mode_gap_audit_validation.get("success")),
            "p506_local_release_semantic_policy_current_gap_audit_rows": p506_local_release_consistency_semantic_policy_current_gap_audit.get("audit_rows"),
            "p506_local_release_semantic_policy_current_gap_audit_failed_rows": p506_local_release_consistency_semantic_policy_current_gap_audit.get("source_failed_rows"),
            "p506_local_release_semantic_policy_current_gap_audit_validation_success": bool(p506_local_release_consistency_semantic_policy_current_gap_audit_validation.get("success")),
            "p507_data_lake_artifact_integrity_gap_audit_rows": p507_data_lake_artifact_integrity_gap_audit.get("audit_rows"),
            "p507_data_lake_artifact_integrity_gap_audit_failed_rows": p507_data_lake_artifact_integrity_gap_audit.get("source_failed_rows"),
            "p507_data_lake_artifact_integrity_gap_audit_validation_success": bool(p507_data_lake_artifact_integrity_gap_audit_validation.get("success")),
            "p508_safety_guard_link_atomicity_gap_audit_rows": p508_local_release_safety_guard_link_atomicity_gap_audit.get("audit_rows"),
            "p508_safety_guard_link_atomicity_gap_audit_failed_rows": p508_local_release_safety_guard_link_atomicity_gap_audit.get("source_failed_rows"),
            "p508_safety_guard_link_atomicity_gap_audit_validation_success": bool(p508_local_release_safety_guard_link_atomicity_gap_audit_validation.get("success")),
            "p509_safety_guard_link_current_atomicity_gap_audit_rows": p509_local_release_safety_guard_link_current_atomicity_gap_audit.get("audit_rows"),
            "p509_safety_guard_link_current_atomicity_gap_audit_failed_rows": p509_local_release_safety_guard_link_current_atomicity_gap_audit.get("source_failed_rows"),
            "p509_safety_guard_link_current_atomicity_gap_audit_validation_success": bool(p509_local_release_safety_guard_link_current_atomicity_gap_audit_validation.get("success")),
            "p510_data_lake_volatile_exemption_gap_audit_rows": p510_data_lake_volatile_exemption_gap_audit.get("audit_rows"),
            "p510_data_lake_volatile_exemption_gap_audit_failed_rows": p510_data_lake_volatile_exemption_gap_audit.get("source_failed_rows"),
            "p510_data_lake_volatile_exemption_gap_audit_validation_success": bool(p510_data_lake_volatile_exemption_gap_audit_validation.get("success")),
            "p511_data_lake_live_content_integrity_gap_audit_rows": p511_data_lake_live_content_integrity_gap_audit.get("audit_rows"),
            "p511_data_lake_live_content_integrity_gap_audit_failed_rows": p511_data_lake_live_content_integrity_gap_audit.get("source_failed_rows"),
            "p511_data_lake_live_content_integrity_gap_audit_validation_success": bool(p511_data_lake_live_content_integrity_gap_audit_validation.get("success")),
            "p512_local_release_live_integrity_binding_gap_audit_rows": p512_local_release_live_integrity_binding_gap_audit.get("audit_rows"),
            "p512_local_release_live_integrity_binding_gap_audit_failed_rows": p512_local_release_live_integrity_binding_gap_audit.get("source_failed_rows"),
            "p512_local_release_live_integrity_binding_gap_audit_validation_success": bool(p512_local_release_live_integrity_binding_gap_audit_validation.get("success")),
            "p513_data_lake_release_input_contract_policy_gap_audit_rows": p513_data_lake_release_input_contract_policy_gap_audit.get("audit_rows"),
            "p513_data_lake_release_input_contract_policy_gap_audit_failure_count": p513_data_lake_release_input_contract_policy_gap_audit.get("source_failure_count"),
            "p513_data_lake_release_input_contract_policy_gap_audit_validation_success": bool(p513_data_lake_release_input_contract_policy_gap_audit_validation.get("success")),
            "p514_data_lake_release_input_contract_policy_regression_gap_audit_rows": p514_data_lake_release_input_contract_policy_regression_gap_audit.get("audit_rows"),
            "p514_data_lake_release_input_contract_policy_regression_gap_audit_failed_rows": p514_data_lake_release_input_contract_policy_regression_gap_audit.get("source_failed_rows"),
            "p514_data_lake_release_input_contract_policy_regression_gap_audit_validation_success": bool(p514_data_lake_release_input_contract_policy_regression_gap_audit_validation.get("success")),
            "p515_local_release_contract_policy_binding_gap_audit_rows": p515_local_release_contract_policy_binding_gap_audit.get("audit_rows"),
            "p515_local_release_contract_policy_binding_gap_audit_failed_rows": p515_local_release_contract_policy_binding_gap_audit.get("source_failed_rows"),
            "p515_local_release_contract_policy_binding_gap_audit_validation_success": bool(p515_local_release_contract_policy_binding_gap_audit_validation.get("success")),
            "p516_safe_pipeline_bootstrap_release_consistency_gap_audit_rows": p516_safe_training_pipeline_bootstrap_release_consistency_gap_audit.get("audit_rows"),
            "p516_safe_pipeline_bootstrap_release_consistency_gap_audit_failed_rows": p516_safe_training_pipeline_bootstrap_release_consistency_gap_audit.get("source_failed_rows"),
            "p516_safe_pipeline_bootstrap_release_consistency_gap_audit_validation_success": bool(p516_safe_training_pipeline_bootstrap_release_consistency_gap_audit_validation.get("success")),
            "p517_local_release_high_risk_summary_safety_gap_audit_rows": p517_local_release_high_risk_summary_safety_gap_audit.get("audit_rows"),
            "p517_local_release_high_risk_summary_safety_gap_audit_failed_rows": p517_local_release_high_risk_summary_safety_gap_audit.get("source_failed_rows"),
            "p517_local_release_high_risk_summary_safety_gap_audit_validation_success": bool(p517_local_release_high_risk_summary_safety_gap_audit_validation.get("success")),
            "p518_local_release_high_risk_coverage_safety_gap_audit_rows": p518_local_release_high_risk_coverage_safety_gap_audit.get("audit_rows"),
            "p518_local_release_high_risk_coverage_safety_gap_audit_failed_rows": p518_local_release_high_risk_coverage_safety_gap_audit.get("source_failed_rows"),
            "p518_local_release_high_risk_coverage_safety_gap_audit_validation_success": bool(p518_local_release_high_risk_coverage_safety_gap_audit_validation.get("success")),
            "p519_safe_pipeline_current_receipt_regression_gap_audit_rows": p519_safe_training_pipeline_current_receipt_regression_gap_audit.get("audit_rows"),
            "p519_safe_pipeline_current_receipt_regression_gap_audit_failed_rows": p519_safe_training_pipeline_current_receipt_regression_gap_audit.get("source_failed_rows"),
            "p519_safe_pipeline_current_receipt_regression_gap_audit_validation_success": bool(p519_safe_training_pipeline_current_receipt_regression_gap_audit_validation.get("success")),
            "p520_local_release_consistency_current_regression_gap_audit_rows": p520_local_release_consistency_receipt_current_regression_gap_audit.get("audit_rows"),
            "p520_local_release_consistency_current_regression_gap_audit_failed_rows": p520_local_release_consistency_receipt_current_regression_gap_audit.get("source_failed_rows"),
            "p520_local_release_consistency_current_regression_gap_audit_validation_success": bool(p520_local_release_consistency_receipt_current_regression_gap_audit_validation.get("success")),
            "p521_local_release_semantic_policy_regression_gap_audit_rows": p521_local_release_consistency_semantic_policy_regression_gap_audit.get("audit_rows"),
            "p521_local_release_semantic_policy_regression_gap_audit_failed_rows": p521_local_release_consistency_semantic_policy_regression_gap_audit.get("source_failed_rows"),
            "p521_local_release_semantic_policy_regression_gap_audit_validation_success": bool(p521_local_release_consistency_semantic_policy_regression_gap_audit_validation.get("success")),
            "p522_local_release_semantic_policy_atomicity_gap_audit_rows": p522_local_release_consistency_semantic_policy_atomicity_regression_gap_audit.get("audit_rows"),
            "p522_local_release_semantic_policy_atomicity_gap_audit_failed_rows": p522_local_release_consistency_semantic_policy_atomicity_regression_gap_audit.get("source_failed_rows"),
            "p522_local_release_semantic_policy_atomicity_gap_audit_validation_success": bool(p522_local_release_consistency_semantic_policy_atomicity_regression_gap_audit_validation.get("success")),
            "p523_stage25_operator_docs_sync_contract_policy_gap_audit_rows": p523_stage25_operator_docs_sync_contract_policy_gap_audit.get("audit_rows"),
            "p523_stage25_operator_docs_sync_contract_policy_gap_audit_failure_count": p523_stage25_operator_docs_sync_contract_policy_gap_audit.get("source_failure_count"),
            "p523_stage25_operator_docs_sync_contract_policy_gap_audit_validation_success": bool(p523_stage25_operator_docs_sync_contract_policy_gap_audit_validation.get("success")),
            "p524_stage25_operator_docs_dynamic_status_sync_gap_audit_rows": p524_stage25_operator_docs_dynamic_status_sync_gap_audit.get("audit_rows"),
            "p524_stage25_operator_docs_dynamic_status_sync_gap_audit_failed_rows": p524_stage25_operator_docs_dynamic_status_sync_gap_audit.get("source_failed_rows"),
            "p524_stage25_operator_docs_dynamic_status_sync_gap_audit_validation_success": bool(p524_stage25_operator_docs_dynamic_status_sync_gap_audit_validation.get("success")),
            "p525_stage25_operator_docs_dynamic_status_sync_current_gap_audit_rows": p525_stage25_operator_docs_dynamic_status_sync_current_gap_audit.get("audit_rows"),
            "p525_stage25_operator_docs_dynamic_status_sync_current_gap_audit_failed_rows": p525_stage25_operator_docs_dynamic_status_sync_current_gap_audit.get("source_failed_rows"),
            "p525_stage25_operator_docs_dynamic_status_sync_current_gap_audit_validation_success": bool(p525_stage25_operator_docs_dynamic_status_sync_current_gap_audit_validation.get("success")),
            "p526_stage25_operator_docs_dynamic_status_sync_current_regression_gap_audit_rows": p526_stage25_operator_docs_dynamic_status_sync_current_regression_gap_audit.get("audit_rows"),
            "p526_stage25_operator_docs_dynamic_status_sync_current_regression_gap_audit_failed_rows": p526_stage25_operator_docs_dynamic_status_sync_current_regression_gap_audit.get("source_failed_rows"),
            "p526_stage25_operator_docs_dynamic_status_sync_current_regression_gap_audit_validation_success": bool(p526_stage25_operator_docs_dynamic_status_sync_current_regression_gap_audit_validation.get("success")),
            "p527_stage25_operator_docs_dynamic_status_sync_atomicity_gap_audit_rows": p527_stage25_operator_docs_dynamic_status_sync_atomicity_gap_audit.get("audit_rows"),
            "p527_stage25_operator_docs_dynamic_status_sync_atomicity_gap_audit_failed_rows": p527_stage25_operator_docs_dynamic_status_sync_atomicity_gap_audit.get("source_failed_rows"),
            "p527_stage25_operator_docs_dynamic_status_sync_atomicity_gap_audit_validation_success": bool(p527_stage25_operator_docs_dynamic_status_sync_atomicity_gap_audit_validation.get("success")),
            "p528_stage25_operator_docs_sync_contract_policy_regression_gap_audit_rows": p528_stage25_operator_docs_sync_contract_policy_regression_gap_audit.get("audit_rows"),
            "p528_stage25_operator_docs_sync_contract_policy_regression_gap_audit_failed_rows": p528_stage25_operator_docs_sync_contract_policy_regression_gap_audit.get("source_failed_rows"),
            "p528_stage25_operator_docs_sync_contract_policy_regression_gap_audit_validation_success": bool(p528_stage25_operator_docs_sync_contract_policy_regression_gap_audit_validation.get("success")),
            "p529_stage25_operator_docs_sync_current_receipt_regression_gap_audit_rows": p529_stage25_operator_docs_sync_current_receipt_regression_gap_audit.get("audit_rows"),
            "p529_stage25_operator_docs_sync_current_receipt_regression_gap_audit_failed_rows": p529_stage25_operator_docs_sync_current_receipt_regression_gap_audit.get("source_failed_rows"),
            "p529_stage25_operator_docs_sync_current_receipt_regression_gap_audit_validation_success": bool(p529_stage25_operator_docs_sync_current_receipt_regression_gap_audit_validation.get("success")),
            "p530_stage25_operator_docs_sync_terminal_recovery_regression_gap_audit_rows": p530_stage25_operator_docs_sync_terminal_recovery_regression_gap_audit.get("audit_rows"),
            "p530_stage25_operator_docs_sync_terminal_recovery_regression_gap_audit_failed_rows": p530_stage25_operator_docs_sync_terminal_recovery_regression_gap_audit.get("source_failed_rows"),
            "p530_stage25_operator_docs_sync_terminal_recovery_regression_gap_audit_validation_success": bool(p530_stage25_operator_docs_sync_terminal_recovery_regression_gap_audit_validation.get("success")),
            "p531_controlled_release_guard_order_validation_receipt_gap_audit_rows": p531_controlled_release_guard_order_validation_receipt_gap_audit.get("audit_rows"),
            "p531_controlled_release_guard_order_validation_receipt_gap_audit_failure_count": p531_controlled_release_guard_order_validation_receipt_gap_audit.get("source_failure_count"),
            "p531_controlled_release_guard_order_validation_receipt_gap_audit_validation_success": bool(p531_controlled_release_guard_order_validation_receipt_gap_audit_validation.get("success")),
            "p532_controlled_release_guard_order_regression_gap_audit_rows": p532_controlled_release_guard_order_regression_gap_audit.get("audit_rows"),
            "p532_controlled_release_guard_order_regression_gap_audit_failed_rows": p532_controlled_release_guard_order_regression_gap_audit.get("source_failed_rows"),
            "p532_controlled_release_guard_order_regression_gap_audit_validation_success": bool(p532_controlled_release_guard_order_regression_gap_audit_validation.get("success")),
            "p533_controlled_release_guard_order_current_validation_receipt_gap_audit_rows": p533_controlled_release_guard_order_current_validation_receipt_gap_audit.get("audit_rows"),
            "p533_controlled_release_guard_order_current_validation_receipt_gap_audit_failure_count": p533_controlled_release_guard_order_current_validation_receipt_gap_audit.get("source_failure_count"),
            "p533_controlled_release_guard_order_current_validation_receipt_gap_audit_validation_success": bool(p533_controlled_release_guard_order_current_validation_receipt_gap_audit_validation.get("success")),
            "p534_controlled_release_guard_order_current_regression_gap_audit_rows": p534_controlled_release_guard_order_current_regression_gap_audit.get("audit_rows"),
            "p534_controlled_release_guard_order_current_regression_gap_audit_failed_rows": p534_controlled_release_guard_order_current_regression_gap_audit.get("source_failed_rows"),
            "p534_controlled_release_guard_order_current_regression_gap_audit_validation_success": bool(p534_controlled_release_guard_order_current_regression_gap_audit_validation.get("success")),
            "p535_controlled_release_guard_order_atomicity_regression_gap_audit_rows": p535_controlled_release_guard_order_atomicity_regression_gap_audit.get("audit_rows"),
            "p535_controlled_release_guard_order_atomicity_regression_gap_audit_failed_rows": p535_controlled_release_guard_order_atomicity_regression_gap_audit.get("source_failed_rows"),
            "p535_controlled_release_guard_order_atomicity_regression_gap_audit_validation_success": bool(p535_controlled_release_guard_order_atomicity_regression_gap_audit_validation.get("success")),
            "p536_stage25_remaining_blocker_cross_binding_gap_audit_rows": p536_stage25_remaining_blocker_cross_binding_gap_audit.get("audit_rows"),
            "p536_stage25_remaining_blocker_cross_binding_gap_audit_expected_rows": p536_stage25_remaining_blocker_cross_binding_gap_audit.get("source_expected_blocker_rows"),
            "p536_stage25_remaining_blocker_cross_binding_gap_audit_validation_success": bool(p536_stage25_remaining_blocker_cross_binding_gap_audit_validation.get("success")),
            "p537_stage25_remaining_blocker_cross_binding_regression_gap_audit_rows": p537_stage25_remaining_blocker_cross_binding_regression_gap_audit.get("audit_rows"),
            "p537_stage25_remaining_blocker_cross_binding_regression_gap_audit_failed_rows": p537_stage25_remaining_blocker_cross_binding_regression_gap_audit.get("source_failed_rows"),
            "p537_stage25_remaining_blocker_cross_binding_regression_gap_audit_validation_success": bool(p537_stage25_remaining_blocker_cross_binding_regression_gap_audit_validation.get("success")),
            "p538_controlled_execution_wave_pair_atomicity_regression_gap_audit_rows": p538_controlled_execution_wave_pair_atomicity_regression_gap_audit.get("audit_rows"),
            "p538_controlled_execution_wave_pair_atomicity_regression_gap_audit_failed_rows": p538_controlled_execution_wave_pair_atomicity_regression_gap_audit.get("source_failed_rows"),
            "p538_controlled_execution_wave_pair_atomicity_regression_gap_audit_validation_success": bool(p538_controlled_execution_wave_pair_atomicity_regression_gap_audit_validation.get("success")),
            "p539_enzyme_agent_execution_receipt_gate_gap_audit_rows": p539_enzyme_agent_execution_receipt_gate_gap_audit.get("audit_rows"),
            "p539_enzyme_agent_execution_receipt_gate_gap_audit_receipt_rows": p539_enzyme_agent_execution_receipt_gate_gap_audit.get("receipt_rows"),
            "p539_enzyme_agent_execution_receipt_gate_gap_audit_validation_success": bool(p539_enzyme_agent_execution_receipt_gate_gap_audit_validation.get("success")),
            "p540_enzyme_agent_execution_receipt_lineage_gap_audit_rows": p540_enzyme_agent_execution_receipt_lineage_gap_audit.get("audit_rows"),
            "p540_enzyme_agent_execution_receipt_lineage_gap_audit_receipt_rows": p540_enzyme_agent_execution_receipt_lineage_gap_audit.get("receipt_rows"),
            "p540_enzyme_agent_execution_receipt_lineage_gap_audit_validation_success": bool(p540_enzyme_agent_execution_receipt_lineage_gap_audit_validation.get("success")),
            "p541_enzyme_agent_execution_receipt_proof_current_gap_audit_rows": p541_enzyme_agent_execution_receipt_proof_current_gap_audit.get("audit_rows"),
            "p541_enzyme_agent_execution_receipt_proof_current_gap_audit_failure_count": p541_enzyme_agent_execution_receipt_proof_current_gap_audit.get("source_failure_count"),
            "p541_enzyme_agent_execution_receipt_proof_current_gap_audit_validation_success": bool(p541_enzyme_agent_execution_receipt_proof_current_gap_audit_validation.get("success")),
            "p542_enzyme_agent_execution_receipt_proof_current_regression_gap_audit_rows": p542_enzyme_agent_execution_receipt_proof_current_regression_gap_audit.get("audit_rows"),
            "p542_enzyme_agent_execution_receipt_proof_current_regression_gap_audit_failed_rows": p542_enzyme_agent_execution_receipt_proof_current_regression_gap_audit.get("source_failed_rows"),
            "p542_enzyme_agent_execution_receipt_proof_current_regression_gap_audit_validation_success": bool(p542_enzyme_agent_execution_receipt_proof_current_regression_gap_audit_validation.get("success")),
            "p543_enzyme_agent_execution_receipt_safety_regression_gap_audit_rows": p543_enzyme_agent_execution_receipt_safety_regression_gap_audit.get("audit_rows"),
            "p543_enzyme_agent_execution_receipt_safety_regression_gap_audit_failed_cases": p543_enzyme_agent_execution_receipt_safety_regression_gap_audit.get("source_failed_regression_cases"),
            "p543_enzyme_agent_execution_receipt_safety_regression_gap_audit_validation_success": bool(p543_enzyme_agent_execution_receipt_safety_regression_gap_audit_validation.get("success")),
            "p544_enzyme_agent_execution_eligibility_matrix_gap_audit_rows": p544_enzyme_agent_execution_eligibility_matrix_gap_audit.get("audit_rows"),
            "p544_enzyme_agent_execution_eligibility_matrix_gap_audit_action_rows": p544_enzyme_agent_execution_eligibility_matrix_gap_audit.get("action_rows"),
            "p544_enzyme_agent_execution_eligibility_matrix_gap_audit_validation_success": bool(p544_enzyme_agent_execution_eligibility_matrix_gap_audit_validation.get("success")),
            "p545_enzyme_agent_execution_eligibility_safety_regression_gap_audit_rows": p545_enzyme_agent_execution_eligibility_safety_regression_gap_audit.get("audit_rows"),
            "p545_enzyme_agent_execution_eligibility_safety_regression_gap_audit_failed_cases": p545_enzyme_agent_execution_eligibility_safety_regression_gap_audit.get("source_failed_regression_cases"),
            "p545_enzyme_agent_execution_eligibility_safety_regression_gap_audit_validation_success": bool(p545_enzyme_agent_execution_eligibility_safety_regression_gap_audit_validation.get("success")),
            "p546_enzyme_agent_execution_outcome_dashboard_gap_audit_rows": p546_enzyme_agent_execution_outcome_dashboard_gap_audit.get("audit_rows"),
            "p546_enzyme_agent_execution_outcome_dashboard_gap_audit_action_rows": p546_enzyme_agent_execution_outcome_dashboard_gap_audit.get("action_rows"),
            "p546_enzyme_agent_execution_outcome_dashboard_gap_audit_engineering_ready_rows": p546_enzyme_agent_execution_outcome_dashboard_gap_audit.get("engineering_ready_rows"),
            "p546_enzyme_agent_execution_outcome_dashboard_gap_audit_hard_gate_unlocked_rows": p546_enzyme_agent_execution_outcome_dashboard_gap_audit.get("hard_gate_unlocked_rows"),
            "p546_enzyme_agent_execution_outcome_dashboard_gap_audit_validation_success": bool(p546_enzyme_agent_execution_outcome_dashboard_gap_audit_validation.get("success")),
            "p547_top_tier_model_execution_board_gap_audit_rows": p547_top_tier_model_execution_board_gap_audit.get("audit_rows"),
            "p547_top_tier_model_execution_board_gap_audit_total_workstreams": p547_top_tier_model_execution_board_gap_audit.get("total_workstreams"),
            "p547_top_tier_model_execution_board_gap_audit_blocked_workstreams": p547_top_tier_model_execution_board_gap_audit.get("blocked_workstreams"),
            "p547_top_tier_model_execution_board_gap_audit_ready_to_verify_workstreams": p547_top_tier_model_execution_board_gap_audit.get("ready_to_verify_workstreams"),
            "p547_top_tier_model_execution_board_gap_audit_validation_success": bool(p547_top_tier_model_execution_board_gap_audit_validation.get("success")),
            "p548_non_human_construction_board_gap_audit_rows": p548_non_human_construction_board_gap_audit.get("audit_rows"),
            "p548_non_human_construction_board_gap_audit_total_workstreams": p548_non_human_construction_board_gap_audit.get("total_workstreams"),
            "p548_non_human_construction_board_gap_audit_blocked_workstreams": p548_non_human_construction_board_gap_audit.get("blocked_workstreams"),
            "p548_non_human_construction_board_gap_audit_ready_to_verify_workstreams": p548_non_human_construction_board_gap_audit.get("ready_to_verify_workstreams"),
            "p548_non_human_construction_board_gap_audit_validation_success": bool(p548_non_human_construction_board_gap_audit_validation.get("success")),
            "p549_parallel_hard_gate_execution_receipts_gap_audit_rows": p549_parallel_hard_gate_execution_receipts_gap_audit.get("audit_rows"),
            "p549_parallel_hard_gate_execution_receipts_gap_audit_receipt_rows": p549_parallel_hard_gate_execution_receipts_gap_audit.get("receipt_rows"),
            "p549_parallel_hard_gate_execution_receipts_gap_audit_eligibility_changed_rows": p549_parallel_hard_gate_execution_receipts_gap_audit.get("eligibility_changed_rows"),
            "p549_parallel_hard_gate_execution_receipts_gap_audit_validation_success": bool(p549_parallel_hard_gate_execution_receipts_gap_audit_validation.get("success")),
            "p550_execution_receipt_artifact_freshness_gap_audit_rows": p550_execution_receipt_artifact_freshness_gap_audit.get("audit_rows"),
            "p550_execution_receipt_artifact_freshness_gap_audit_total_receipts": p550_execution_receipt_artifact_freshness_gap_audit.get("total_receipts"),
            "p550_execution_receipt_artifact_freshness_gap_audit_fresh_receipts": p550_execution_receipt_artifact_freshness_gap_audit.get("fresh_receipts"),
            "p550_execution_receipt_artifact_freshness_gap_audit_stale_receipts": p550_execution_receipt_artifact_freshness_gap_audit.get("stale_receipts"),
            "p550_execution_receipt_artifact_freshness_gap_audit_validation_success": bool(p550_execution_receipt_artifact_freshness_gap_audit_validation.get("success")),
            "p551_execution_receipt_artifact_hash_coverage_gap_audit_rows": p551_execution_receipt_artifact_hash_coverage_gap_audit.get("audit_rows"),
            "p551_execution_receipt_artifact_hash_coverage_gap_audit_total_receipts": p551_execution_receipt_artifact_hash_coverage_gap_audit.get("total_receipts"),
            "p551_execution_receipt_artifact_hash_coverage_gap_audit_receipts_without_hash_fields": p551_execution_receipt_artifact_hash_coverage_gap_audit.get("receipts_without_artifact_hash_fields"),
            "p551_execution_receipt_artifact_hash_coverage_gap_audit_validation_success": bool(p551_execution_receipt_artifact_hash_coverage_gap_audit_validation.get("success")),
            "p552_top_tier_model_execution_board_claim_boundary_gap_audit_rows": p552_top_tier_model_execution_board_claim_boundary_gap_audit.get("audit_rows"),
            "p552_top_tier_model_execution_board_claim_boundary_gap_audit_total_workstreams": p552_top_tier_model_execution_board_claim_boundary_gap_audit.get("total_workstreams"),
            "p552_top_tier_model_execution_board_claim_boundary_gap_audit_blocked_workstreams": p552_top_tier_model_execution_board_claim_boundary_gap_audit.get("blocked_workstreams"),
            "p552_top_tier_model_execution_board_claim_boundary_gap_audit_validation_success": bool(p552_top_tier_model_execution_board_claim_boundary_gap_audit_validation.get("success")),
            "p553_non_human_construction_board_claim_boundary_gap_audit_rows": p553_non_human_construction_board_claim_boundary_gap_audit.get("audit_rows"),
            "p553_non_human_construction_board_claim_boundary_gap_audit_total_workstreams": p553_non_human_construction_board_claim_boundary_gap_audit.get("total_workstreams"),
            "p553_non_human_construction_board_claim_boundary_gap_audit_blocked_workstreams": p553_non_human_construction_board_claim_boundary_gap_audit.get("blocked_workstreams"),
            "p553_non_human_construction_board_claim_boundary_gap_audit_validation_success": bool(p553_non_human_construction_board_claim_boundary_gap_audit_validation.get("success")),
            "p554_enzyme_agent_execution_outcome_formal_boundary_gap_audit_rows": p554_enzyme_agent_execution_outcome_formal_boundary_gap_audit.get("audit_rows"),
            "p554_enzyme_agent_execution_outcome_formal_boundary_gap_audit_action_rows": p554_enzyme_agent_execution_outcome_formal_boundary_gap_audit.get("action_rows"),
            "p554_enzyme_agent_execution_outcome_formal_boundary_gap_audit_hard_gate_unlocked_rows": p554_enzyme_agent_execution_outcome_formal_boundary_gap_audit.get("hard_gate_unlocked_rows"),
            "p554_enzyme_agent_execution_outcome_formal_boundary_gap_audit_validation_success": bool(p554_enzyme_agent_execution_outcome_formal_boundary_gap_audit_validation.get("success")),
            "p555_parallel_hard_gate_execution_decision_boundary_gap_audit_rows": p555_parallel_hard_gate_execution_decision_boundary_gap_audit.get("audit_rows"),
            "p555_parallel_hard_gate_execution_decision_boundary_gap_audit_receipt_rows": p555_parallel_hard_gate_execution_decision_boundary_gap_audit.get("receipt_rows"),
            "p555_parallel_hard_gate_execution_decision_boundary_gap_audit_eligibility_changed_rows": p555_parallel_hard_gate_execution_decision_boundary_gap_audit.get("eligibility_changed_rows"),
            "p555_parallel_hard_gate_execution_decision_boundary_gap_audit_validation_success": bool(p555_parallel_hard_gate_execution_decision_boundary_gap_audit_validation.get("success")),
            "p556_top_tier_ready_receipt_completion_boundary_gap_audit_rows": p556_top_tier_ready_receipt_completion_boundary_gap_audit.get("audit_rows"),
            "p556_top_tier_ready_receipt_completion_boundary_gap_audit_receipt_rows": p556_top_tier_ready_receipt_completion_boundary_gap_audit.get("receipt_rows"),
            "p556_top_tier_ready_receipt_completion_boundary_gap_audit_validation_success": bool(p556_top_tier_ready_receipt_completion_boundary_gap_audit_validation.get("success")),
            "p557_non_human_ready_receipt_completion_boundary_gap_audit_rows": p557_non_human_ready_receipt_completion_boundary_gap_audit.get("audit_rows"),
            "p557_non_human_ready_receipt_completion_boundary_gap_audit_receipt_rows": p557_non_human_ready_receipt_completion_boundary_gap_audit.get("receipt_rows"),
            "p557_non_human_ready_receipt_completion_boundary_gap_audit_validation_success": bool(p557_non_human_ready_receipt_completion_boundary_gap_audit_validation.get("success")),
            "p558_ready_to_verify_promotion_boundary_gap_audit_rows": p558_ready_to_verify_promotion_boundary_gap_audit.get("audit_rows"),
            "p558_ready_to_verify_promotion_boundary_gap_audit_valid_rows": p558_ready_to_verify_promotion_boundary_gap_audit.get("receipt_valid_rows"),
            "p558_ready_to_verify_promotion_boundary_gap_audit_validation_success": bool(p558_ready_to_verify_promotion_boundary_gap_audit_validation.get("success")),
            "p559_data_lake_live_integrity_boundary_gap_audit_rows": p559_data_lake_live_integrity_boundary_gap_audit.get("audit_rows"),
            "p559_data_lake_live_integrity_boundary_gap_audit_artifact_rows": p559_data_lake_live_integrity_boundary_gap_audit.get("artifact_rows"),
            "p559_data_lake_live_integrity_boundary_gap_audit_failure_count": p559_data_lake_live_integrity_boundary_gap_audit.get("failure_count"),
            "p559_data_lake_live_integrity_boundary_gap_audit_validation_success": bool(p559_data_lake_live_integrity_boundary_gap_audit_validation.get("success")),
            "p560_local_release_consistency_boundary_gap_audit_rows": p560_local_release_consistency_boundary_gap_audit.get("audit_rows"),
            "p560_local_release_consistency_boundary_gap_audit_artifact_count": p560_local_release_consistency_boundary_gap_audit.get("artifact_count"),
            "p560_local_release_consistency_boundary_gap_audit_failure_count": p560_local_release_consistency_boundary_gap_audit.get("failure_count"),
            "p560_local_release_consistency_boundary_gap_audit_validation_success": bool(p560_local_release_consistency_boundary_gap_audit_validation.get("success")),
            "p561_reviewed_numbering_hard_boundary_gap_audit_rows": p561_reviewed_numbering_hard_boundary_gap_audit.get("audit_rows"),
            "p561_reviewed_numbering_hard_boundary_gap_audit_open_numbering_rows": p561_reviewed_numbering_hard_boundary_gap_audit.get("open_numbering_rows"),
            "p561_reviewed_numbering_hard_boundary_gap_audit_validation_success": bool(p561_reviewed_numbering_hard_boundary_gap_audit_validation.get("success")),
            "p562_wet_lab_feedback_numeric_eligibility_boundary_gap_audit_rows": p562_wet_lab_feedback_numeric_eligibility_boundary_gap_audit.get("audit_rows"),
            "p562_wet_lab_feedback_numeric_eligibility_boundary_gap_audit_numeric_rows": p562_wet_lab_feedback_numeric_eligibility_boundary_gap_audit.get("numeric_training_eligible_rows"),
            "p562_wet_lab_feedback_numeric_eligibility_boundary_gap_audit_validation_success": bool(p562_wet_lab_feedback_numeric_eligibility_boundary_gap_audit_validation.get("success")),
            "p563_physics_ddg_backend_readiness_boundary_gap_audit_rows": p563_physics_ddg_backend_readiness_boundary_gap_audit.get("audit_rows"),
            "p563_physics_ddg_backend_readiness_boundary_gap_audit_ready_backend_count": p563_physics_ddg_backend_readiness_boundary_gap_audit.get("ready_backend_count"),
            "p563_physics_ddg_backend_readiness_boundary_gap_audit_validation_success": bool(p563_physics_ddg_backend_readiness_boundary_gap_audit_validation.get("success")),
            "p564_claim_readiness_matrix_hard_boundary_gap_audit_rows": p564_claim_readiness_matrix_hard_boundary_gap_audit.get("audit_rows"),
            "p564_claim_readiness_matrix_hard_boundary_gap_audit_claims_blocked": p564_claim_readiness_matrix_hard_boundary_gap_audit.get("claims_blocked"),
            "p564_claim_readiness_matrix_hard_boundary_gap_audit_validation_success": bool(p564_claim_readiness_matrix_hard_boundary_gap_audit_validation.get("success")),
            "p565_production_release_authorization_boundary_gap_audit_rows": p565_production_release_authorization_boundary_gap_audit.get("audit_rows"),
            "p565_production_release_authorization_boundary_gap_audit_artifact_count": p565_production_release_authorization_boundary_gap_audit.get("artifact_count"),
            "p565_production_release_authorization_boundary_gap_audit_validation_success": bool(p565_production_release_authorization_boundary_gap_audit_validation.get("success")),
            "p566_five_head_training_execution_boundary_gap_audit_ready_head_count": p566_five_head_training_execution_boundary_gap_audit.get("ready_head_count"),
            "p566_five_head_training_execution_boundary_gap_audit_training_execution_allowed": bool(p566_five_head_training_execution_boundary_gap_audit.get("training_execution_allowed")),
            "p566_five_head_training_execution_boundary_gap_audit_validation_success": bool(p566_five_head_training_execution_boundary_gap_audit_validation.get("success")),
            "p567_validated_feature_index_training_label_boundary_gap_audit_feature_rows": p567_validated_feature_index_training_label_boundary_gap_audit.get("feature_rows"),
            "p567_validated_feature_index_training_label_boundary_gap_audit_training_label_source_rows": p567_validated_feature_index_training_label_boundary_gap_audit.get("training_label_source_rows"),
            "p567_validated_feature_index_training_label_boundary_gap_audit_validation_success": bool(p567_validated_feature_index_training_label_boundary_gap_audit_validation.get("success")),
            "p568_model_artifact_claim_boundary_gap_audit_artifact_count": p568_model_artifact_claim_boundary_gap_audit.get("artifact_count"),
            "p568_model_artifact_claim_boundary_gap_audit_claimable_artifact_count": p568_model_artifact_claim_boundary_gap_audit.get("claimable_model_artifact_count"),
            "p568_model_artifact_claim_boundary_gap_audit_validation_success": bool(p568_model_artifact_claim_boundary_gap_audit_validation.get("success")),
            "p569_local_release_guard_coverage_boundary_gap_audit_guard_coverage_count": p569_local_release_guard_coverage_boundary_gap_audit.get("guard_coverage_count"),
            "p569_local_release_guard_coverage_boundary_gap_audit_validation_success": bool(p569_local_release_guard_coverage_boundary_gap_audit_validation.get("success")),
            "p570_training_readiness_quality_boundary_gap_audit_quality_score": p570_training_readiness_quality_boundary_gap_audit.get("quality_score"),
            "p570_training_readiness_quality_boundary_gap_audit_ready_for_small_model_claim": bool(p570_training_readiness_quality_boundary_gap_audit.get("ready_for_supervised_small_model_claim")),
            "p570_training_readiness_quality_boundary_gap_audit_validation_success": bool(p570_training_readiness_quality_boundary_gap_audit_validation.get("success")),
            "p571_five_head_contract_ready_heads": p571_five_head_training_execution_contract_boundary_gap_audit.get("ready_head_count"),
            "p571_five_head_contract_total_rows": p571_five_head_training_execution_contract_boundary_gap_audit.get("total_head_training_rows"),
            "p571_five_head_contract_validation_success": bool(p571_five_head_training_execution_contract_boundary_gap_audit_validation.get("success")),
            "p572_model_quality_contract_gate_count": p572_model_quality_hard_gate_contract_boundary_gap_audit.get("hard_gate_count"),
            "p572_model_quality_contract_unlocked_gate_count": p572_model_quality_hard_gate_contract_boundary_gap_audit.get("unlocked_gate_count"),
            "p572_model_quality_contract_validation_success": bool(p572_model_quality_hard_gate_contract_boundary_gap_audit_validation.get("success")),
            "p573_tool_lane_boundary_total_lanes": p573_tool_lane_evidence_boundary_gap_audit.get("total_lanes"),
            "p573_tool_lane_boundary_blocked_lanes": p573_tool_lane_evidence_boundary_gap_audit.get("blocked_lanes"),
            "p573_tool_lane_boundary_validation_success": bool(p573_tool_lane_evidence_boundary_gap_audit_validation.get("success")),
            "p574_human_target_runtime_total_sources": p574_human_target_source_runtime_boundary_gap_audit.get("total_sources"),
            "p574_human_target_runtime_blocked_sources": p574_human_target_source_runtime_boundary_gap_audit.get("blocked_sources"),
            "p574_human_target_runtime_validation_success": bool(p574_human_target_source_runtime_boundary_gap_audit_validation.get("success")),
            "p575_human_target_unlock_checklist_rows": p575_human_target_source_unlock_checklist_boundary_gap_audit.get("checklist_rows"),
            "p575_human_target_unlock_ready_rows": p575_human_target_source_unlock_checklist_boundary_gap_audit.get("ready_to_unlock_rows"),
            "p575_human_target_unlock_validation_success": bool(p575_human_target_source_unlock_checklist_boundary_gap_audit_validation.get("success")),
            "p576_label_contract_eligible_rows": p576_training_label_import_contract_boundary_gap_audit.get("training_import_eligible_rows"),
            "p576_label_contract_claim_rows": p576_training_label_import_contract_boundary_gap_audit.get("claim_eligible_rows"),
            "p576_label_contract_validation_success": bool(p576_training_label_import_contract_boundary_gap_audit_validation.get("success")),
            "p577_wetlab_contract_candidate_rows": p577_wet_lab_feedback_authorization_contract_boundary_gap_audit.get("candidate_rows"),
            "p577_wetlab_contract_ready_rows": p577_wet_lab_feedback_authorization_contract_boundary_gap_audit.get("ready_for_training_import_rows"),
            "p577_wetlab_contract_validation_success": bool(p577_wet_lab_feedback_authorization_contract_boundary_gap_audit_validation.get("success")),
            "p578_ddg_contract_proxy_rows": p578_ddg_model_consumption_contract_boundary_gap_audit.get("thermompnn_proxy_rows"),
            "p578_ddg_contract_physics_rows": p578_ddg_model_consumption_contract_boundary_gap_audit.get("pyrosetta_physics_rows"),
            "p578_ddg_contract_validation_success": bool(p578_ddg_model_consumption_contract_boundary_gap_audit_validation.get("success")),
            "p579_structure_contract_reviewed_rows": p579_structure_feature_model_contract_boundary_gap_audit.get("model_consumable_reviewed_graph_rows"),
            "p579_structure_contract_excluded_rows": p579_structure_feature_model_contract_boundary_gap_audit.get("unreviewed_coordinate_rows_excluded"),
            "p579_structure_contract_validation_success": bool(p579_structure_feature_model_contract_boundary_gap_audit_validation.get("success")),
            "p580_advanced_feature_contract_ready_refs": p580_advanced_model_feature_contract_boundary_gap_audit.get("ready_feature_ref_count"),
            "p580_advanced_feature_contract_label_refs": p580_advanced_model_feature_contract_boundary_gap_audit.get("training_label_source_feature_ref_count"),
            "p580_advanced_feature_contract_validation_success": bool(p580_advanced_model_feature_contract_boundary_gap_audit_validation.get("success")),
            "p581_active_learning_boundary_draft_rows": p581_active_learning_trial_readiness_boundary_gap_audit.get("draft_rows"),
            "p581_active_learning_boundary_blocker_count": p581_active_learning_trial_readiness_boundary_gap_audit.get("blocker_count"),
            "p581_active_learning_boundary_validation_success": bool(p581_active_learning_trial_readiness_boundary_gap_audit_validation.get("success")),
            "p582_benchmark_packet_boundary_rows": p582_benchmark_readiness_packet_boundary_gap_audit.get("packet_rows"),
            "p582_benchmark_packet_boundary_gap_rows": p582_benchmark_readiness_packet_boundary_gap_audit.get("invalid_gap_rows"),
            "p582_benchmark_packet_boundary_validation_success": bool(p582_benchmark_readiness_packet_boundary_gap_audit_validation.get("success")),
            "p583_enzyme_tool_contract_boundary_rows": p583_enzyme_tool_contract_boundary_gap_audit.get("contract_rows"),
            "p583_enzyme_tool_contract_boundary_zero_write_actions": p583_enzyme_tool_contract_boundary_gap_audit.get("training_write_actions"),
            "p583_enzyme_tool_contract_boundary_validation_success": bool(p583_enzyme_tool_contract_boundary_gap_audit_validation.get("success")),
            "p584_foreign_tool_boundary_total_rows": p584_foreign_tool_readiness_boundary_gap_audit.get("tool_rows"),
            "p584_foreign_tool_boundary_local_eval_rows": p584_foreign_tool_readiness_boundary_gap_audit.get("ready_for_local_evaluation_rows"),
            "p584_foreign_tool_boundary_validation_success": bool(p584_foreign_tool_readiness_boundary_gap_audit_validation.get("success")),
            "p585_msa_runtime_boundary_target_rows": p585_msa_runtime_readiness_boundary_gap_audit.get("target_rows"),
            "p585_msa_runtime_boundary_blocker_count": p585_msa_runtime_readiness_boundary_gap_audit.get("blocker_count"),
            "p585_msa_runtime_boundary_validation_success": bool(p585_msa_runtime_readiness_boundary_gap_audit_validation.get("success")),
            "p586_resource_retrieval_boundary_action_rows": p586_enzyme_resource_retrieval_plan_boundary_gap_audit.get("action_rows"),
            "p586_resource_retrieval_boundary_human_decision_rows": p586_enzyme_resource_retrieval_plan_boundary_gap_audit.get("blocked_requires_human_decision_rows"),
            "p586_resource_retrieval_boundary_validation_success": bool(p586_enzyme_resource_retrieval_plan_boundary_gap_audit_validation.get("success")),
            "p587_agent_result_boundary_artifact_refs": p587_enzyme_agent_result_validation_boundary_gap_audit.get("artifact_ref_count"),
            "p587_agent_result_boundary_selected_rows": p587_enzyme_agent_result_validation_boundary_gap_audit.get("selected_variant_rows"),
            "p587_agent_result_boundary_validation_success": bool(p587_enzyme_agent_result_validation_boundary_gap_audit_validation.get("success")),
            "p588_agent_result_regression_boundary_cases": p588_enzyme_agent_result_safety_regression_boundary_gap_audit.get("case_rows"),
            "p588_agent_result_regression_boundary_failed_cases": p588_enzyme_agent_result_safety_regression_boundary_gap_audit.get("failed_regression_cases"),
            "p588_agent_result_regression_boundary_validation_success": bool(p588_enzyme_agent_result_safety_regression_boundary_gap_audit_validation.get("success")),
            "p589_agent_trace_boundary_rows": p589_enzyme_agent_trace_audit_boundary_gap_audit.get("trace_rows"),
            "p589_agent_trace_boundary_executed_actions": p589_enzyme_agent_trace_audit_boundary_gap_audit.get("executed_action_count"),
            "p589_agent_trace_boundary_validation_success": bool(p589_enzyme_agent_trace_audit_boundary_gap_audit_validation.get("success")),
            "p590_release_order_current_boundary_failures": p590_enzyme_agent_controlled_release_order_current_boundary_gap_audit.get("failure_count"),
            "p590_release_order_current_boundary_hash_matches": bool(p590_enzyme_agent_controlled_release_order_current_boundary_gap_audit.get("action_contract_hash_matches")),
            "p590_release_order_current_boundary_validation_success": bool(p590_enzyme_agent_controlled_release_order_current_boundary_gap_audit_validation.get("success")),
            "p591_governance_boundary_external_source_rows": p591_governance_readiness_boundary_gap_audit.get("external_source_rows"),
            "p591_governance_boundary_blocker_count": p591_governance_readiness_boundary_gap_audit.get("governance_blocker_count"),
            "p591_governance_boundary_validation_success": bool(p591_governance_readiness_boundary_gap_audit_validation.get("success")),
            "p592_biosecurity_boundary_decision_rows": p592_biosecurity_readiness_boundary_gap_audit.get("decision_rows"),
            "p592_biosecurity_boundary_order_output_count": p592_biosecurity_readiness_boundary_gap_audit.get("order_ready_outputs_detected"),
            "p592_biosecurity_boundary_validation_success": bool(p592_biosecurity_readiness_boundary_gap_audit_validation.get("success")),
            "p593_acceptance_boundary_stream_count": p593_workstream_acceptance_boundary_gap_audit.get("total_streams"),
            "p593_acceptance_boundary_missing_decision_count": p593_workstream_acceptance_boundary_gap_audit.get("missing_stream_decision_rows"),
            "p593_acceptance_boundary_validation_success": bool(p593_workstream_acceptance_boundary_gap_audit_validation.get("success")),
            "p594_ip_fto_boundary_packet_count": p594_sequence_ip_fto_decision_boundary_gap_audit.get("packet_rows"),
            "p594_ip_fto_boundary_decision_count": p594_sequence_ip_fto_decision_boundary_gap_audit.get("decision_rows"),
            "p594_ip_fto_boundary_validation_success": bool(p594_sequence_ip_fto_decision_boundary_gap_audit_validation.get("success")),
            "p595_claim_boundary_strict_row_count": p595_model_claim_fail_closed_consistency_boundary_gap_audit.get("strict_rows"),
            "p595_claim_boundary_blocked_claim_count": p595_model_claim_fail_closed_consistency_boundary_gap_audit.get("blocked_claim_count"),
            "p595_claim_boundary_validation_success": bool(p595_model_claim_fail_closed_consistency_boundary_gap_audit_validation.get("success")),
            "p596_external_registry_boundary_source_rows": p596_external_data_source_registry_boundary_gap_audit.get("registry_source_rows"),
            "p596_external_registry_boundary_not_ready_source_count": p596_external_data_source_registry_boundary_gap_audit.get("registry_not_ready_source_count"),
            "p596_external_registry_boundary_validation_success": bool(p596_external_data_source_registry_boundary_gap_audit_validation.get("success")),
            "p597_operator_status_boundary_action_rows": p597_operator_review_status_boundary_gap_audit.get("operator_action_rows"),
            "p597_operator_status_boundary_open_action_rows": p597_operator_review_status_boundary_gap_audit.get("operator_open_action_rows"),
            "p597_operator_status_boundary_validation_success": bool(p597_operator_review_status_boundary_gap_audit_validation.get("success")),
            "p598_human_review_consistency_boundary_closeout_rows": p598_human_review_release_consistency_boundary_gap_audit.get("human_review_consistency_closeout_rows"),
            "p598_human_review_consistency_boundary_open_closeout_rows": p598_human_review_release_consistency_boundary_gap_audit.get("human_review_consistency_open_closeout_rows"),
            "p598_human_review_consistency_boundary_validation_success": bool(p598_human_review_release_consistency_boundary_gap_audit_validation.get("success")),
            "p599_claim_promotion_boundary_target_count": p599_claim_promotion_decision_boundary_gap_audit.get("claim_promotion_target_count"),
            "p599_claim_promotion_boundary_missing_decision_count": p599_claim_promotion_decision_boundary_gap_audit.get("claim_promotion_missing_decision_count"),
            "p599_claim_promotion_boundary_validation_success": bool(p599_claim_promotion_decision_boundary_gap_audit_validation.get("success")),
            "p600_claim_policy_current_boundary_failure_count": p600_claim_readiness_policy_current_boundary_gap_audit.get("claim_policy_current_failure_count"),
            "p600_claim_policy_current_boundary_validation_success": bool(p600_claim_readiness_policy_current_boundary_gap_audit_validation.get("success")),
            "p601_structure_feature_operator_packet_boundary_packet_rows": p601_structure_feature_hard_gate_operator_packet_boundary_gap_audit.get("structure_feature_packet_rows"),
            "p601_structure_feature_operator_packet_boundary_completion_ready_rows": p601_structure_feature_hard_gate_operator_packet_boundary_gap_audit.get("structure_feature_completion_ready_rows"),
            "p601_structure_feature_operator_packet_boundary_validation_success": bool(p601_structure_feature_hard_gate_operator_packet_boundary_gap_audit_validation.get("success")),
            "p602_wet_lab_hard_gate_operator_packet_boundary_packet_rows": p602_wet_lab_hard_gate_operator_packet_boundary_gap_audit.get("wet_lab_hard_gate_packet_rows"),
            "p602_wet_lab_hard_gate_operator_packet_boundary_completion_ready_rows": p602_wet_lab_hard_gate_operator_packet_boundary_gap_audit.get("wet_lab_hard_gate_completion_ready_rows"),
            "p602_wet_lab_hard_gate_operator_packet_boundary_validation_success": bool(p602_wet_lab_hard_gate_operator_packet_boundary_gap_audit_validation.get("success")),
            "p603_benchmark_hard_gate_operator_packet_boundary_packet_rows": p603_benchmark_hard_gate_operator_packet_boundary_gap_audit.get("benchmark_hard_gate_packet_rows"),
            "p603_benchmark_hard_gate_operator_packet_boundary_completion_ready_rows": p603_benchmark_hard_gate_operator_packet_boundary_gap_audit.get("benchmark_hard_gate_completion_ready_rows"),
            "p603_benchmark_hard_gate_operator_packet_boundary_validation_success": bool(p603_benchmark_hard_gate_operator_packet_boundary_gap_audit_validation.get("success")),
            "p604_substrate_fit_hard_gate_operator_packet_boundary_packet_rows": p604_substrate_fit_hard_gate_operator_packet_boundary_gap_audit.get("substrate_fit_hard_gate_packet_rows"),
            "p604_substrate_fit_hard_gate_operator_packet_boundary_completion_ready_rows": p604_substrate_fit_hard_gate_operator_packet_boundary_gap_audit.get("substrate_fit_hard_gate_completion_ready_rows"),
            "p604_substrate_fit_hard_gate_operator_packet_boundary_validation_success": bool(p604_substrate_fit_hard_gate_operator_packet_boundary_gap_audit_validation.get("success")),
            "p605_review_draft_formal_boundary_review_draft_rows": p605_review_draft_formal_boundary_gap_audit.get("review_draft_total_rows"),
            "p605_review_draft_formal_boundary_drafts_counted_as_formal_decisions": p605_review_draft_formal_boundary_gap_audit.get("review_draft_rows_counted_as_formal_decisions"),
            "p605_review_draft_formal_boundary_validation_success": bool(p605_review_draft_formal_boundary_gap_audit_validation.get("success")),
            "p606_activity_risk_formal_label_boundary_formal_decision_rows": p606_activity_risk_formal_label_decision_boundary_gap_audit.get("activity_risk_formal_decision_rows"),
            "p606_activity_risk_formal_label_boundary_ready_for_training_import_rows": p606_activity_risk_formal_label_decision_boundary_gap_audit.get("activity_risk_ready_for_training_import_rows"),
            "p606_activity_risk_formal_label_boundary_audit_safe_for_training_import": p606_activity_risk_formal_label_decision_boundary_gap_audit.get("safe_for_training_import"),
            "p606_activity_risk_formal_label_boundary_audit_safe_for_model_claim": p606_activity_risk_formal_label_decision_boundary_gap_audit.get("safe_for_model_claim"),
            "p606_activity_risk_formal_label_boundary_validation_success": bool(p606_activity_risk_formal_label_decision_boundary_gap_audit_validation.get("success")),
            "p607_activity_risk_training_lineage_boundary_ledger_rows": p607_activity_risk_training_lineage_boundary_gap_audit.get("activity_risk_lineage_ledger_rows"),
            "p607_activity_risk_training_lineage_boundary_import_eligible_rows": p607_activity_risk_training_lineage_boundary_gap_audit.get("activity_risk_lineage_training_import_eligible_rows_from_contract"),
            "p607_activity_risk_training_lineage_boundary_training_execution_allowed": p607_activity_risk_training_lineage_boundary_gap_audit.get("activity_risk_lineage_training_execution_allowed"),
            "p607_activity_risk_training_lineage_boundary_audit_safe_for_model_claim": p607_activity_risk_training_lineage_boundary_gap_audit.get("safe_for_model_claim"),
            "p607_activity_risk_training_lineage_boundary_validation_success": bool(p607_activity_risk_training_lineage_boundary_gap_audit_validation.get("success")),
            "p608_feedback_training_import_guard_boundary_numeric_eligible_rows": p608_feedback_training_import_semantic_guard_boundary_gap_audit.get("feedback_training_guard_numeric_training_import_eligible"),
            "p608_feedback_training_import_guard_boundary_strict_supervised_rows": p608_feedback_training_import_semantic_guard_boundary_gap_audit.get("feedback_training_guard_strict_supervised_rows"),
            "p608_feedback_training_import_guard_boundary_claim_eligible_rows": p608_feedback_training_import_semantic_guard_boundary_gap_audit.get("feedback_training_guard_claim_eligible_rows"),
            "p608_feedback_training_import_guard_boundary_audit_safe_for_model_claim": p608_feedback_training_import_semantic_guard_boundary_gap_audit.get("safe_for_model_claim"),
            "p608_feedback_training_import_guard_boundary_validation_success": bool(p608_feedback_training_import_semantic_guard_boundary_gap_audit_validation.get("success")),
            "p609_wet_lab_feedback_import_reconciliation_boundary_contract_eligible_rows": p609_wet_lab_feedback_import_reconciliation_boundary_gap_audit.get("wet_lab_import_reconciliation_contract_training_import_eligible_rows"),
            "p609_wet_lab_feedback_import_reconciliation_boundary_model_quality_import_rows": p609_wet_lab_feedback_import_reconciliation_boundary_gap_audit.get("wet_lab_import_reconciliation_model_quality_training_import_eligible_rows"),
            "p609_wet_lab_feedback_import_reconciliation_boundary_claim_eligible_rows": p609_wet_lab_feedback_import_reconciliation_boundary_gap_audit.get("wet_lab_import_reconciliation_claim_eligible_rows"),
            "p609_wet_lab_feedback_import_reconciliation_boundary_audit_safe_for_model_claim": p609_wet_lab_feedback_import_reconciliation_boundary_gap_audit.get("safe_for_model_claim"),
            "p609_wet_lab_feedback_import_reconciliation_boundary_validation_success": bool(p609_wet_lab_feedback_import_reconciliation_boundary_gap_audit_validation.get("success")),
            "p610_positive_claim_gate_quarantine_boundary_scanned_report_count": p610_positive_claim_gate_quarantine_boundary_gap_audit.get("positive_claim_gate_scanned_report_count"),
            "p610_positive_claim_gate_quarantine_boundary_disallowed_true_hit_count": p610_positive_claim_gate_quarantine_boundary_gap_audit.get("positive_claim_gate_disallowed_true_hit_count"),
            "p610_positive_claim_gate_quarantine_boundary_audit_safe_for_training_import": p610_positive_claim_gate_quarantine_boundary_gap_audit.get("safe_for_training_import"),
            "p610_positive_claim_gate_quarantine_boundary_audit_safe_for_model_claim": p610_positive_claim_gate_quarantine_boundary_gap_audit.get("safe_for_model_claim"),
            "p610_positive_claim_gate_quarantine_boundary_validation_success": bool(p610_positive_claim_gate_quarantine_boundary_gap_audit_validation.get("success")),
            "p611_activity_risk_import_label_boundary_label_rows": p611_activity_risk_training_import_label_boundary_gap_audit.get("activity_risk_import_label_rows"),
            "p611_activity_risk_import_label_boundary_written_rows": p611_activity_risk_training_import_label_boundary_gap_audit.get("activity_risk_import_written_rows"),
            "p611_activity_risk_import_label_boundary_training_execution_allowed": p611_activity_risk_training_import_label_boundary_gap_audit.get("activity_risk_import_training_execution_allowed"),
            "p611_activity_risk_import_label_boundary_audit_safe_for_model_claim": p611_activity_risk_training_import_label_boundary_gap_audit.get("safe_for_model_claim"),
            "p611_activity_risk_import_label_boundary_validation_success": bool(p611_activity_risk_training_import_label_boundary_gap_audit_validation.get("success")),
            "p612_activity_risk_replicate_preflight_boundary_preflight_rows": p612_activity_risk_label_replicate_preflight_boundary_gap_audit.get("activity_risk_replicate_preflight_rows"),
            "p612_activity_risk_replicate_preflight_boundary_formal_decision_rows": p612_activity_risk_label_replicate_preflight_boundary_gap_audit.get("activity_risk_replicate_formal_decision_rows"),
            "p612_activity_risk_replicate_preflight_boundary_ready_for_training_import_rows": p612_activity_risk_label_replicate_preflight_boundary_gap_audit.get("activity_risk_replicate_ready_for_training_import_rows"),
            "p612_activity_risk_replicate_preflight_boundary_audit_safe_for_model_claim": p612_activity_risk_label_replicate_preflight_boundary_gap_audit.get("safe_for_model_claim"),
            "p612_activity_risk_replicate_preflight_boundary_validation_success": bool(p612_activity_risk_label_replicate_preflight_boundary_gap_audit_validation.get("success")),
            "p613_feature_coverage_by_head_group_boundary_coverage_rows": p613_feature_coverage_by_head_group_boundary_gap_audit.get("feature_coverage_by_head_group_coverage_rows"),
            "p613_feature_coverage_by_head_group_boundary_training_label_source_rows": p613_feature_coverage_by_head_group_boundary_gap_audit.get("feature_coverage_by_head_group_training_label_source_rows"),
            "p613_feature_coverage_by_head_group_boundary_feature_rows_counted_as_labels": p613_feature_coverage_by_head_group_boundary_gap_audit.get("feature_coverage_by_head_group_feature_rows_counted_as_labels"),
            "p613_feature_coverage_by_head_group_boundary_training_execution_allowed": p613_feature_coverage_by_head_group_boundary_gap_audit.get("feature_coverage_by_head_group_training_execution_allowed"),
            "p613_feature_coverage_by_head_group_boundary_audit_safe_for_model_claim": p613_feature_coverage_by_head_group_boundary_gap_audit.get("safe_for_model_claim"),
            "p613_feature_coverage_by_head_group_boundary_validation_success": bool(p613_feature_coverage_by_head_group_boundary_gap_audit_validation.get("success")),
            "p614_feature_coverage_gap_queue_boundary_gap_count": p614_feature_coverage_gap_queue_boundary_gap_audit.get("feature_coverage_gap_queue_gap_count"),
            "p614_feature_coverage_gap_queue_boundary_training_label_source_rows": p614_feature_coverage_gap_queue_boundary_gap_audit.get("feature_coverage_gap_queue_training_label_source_rows"),
            "p614_feature_coverage_gap_queue_boundary_feature_rows_counted_as_labels": p614_feature_coverage_gap_queue_boundary_gap_audit.get("feature_coverage_gap_queue_feature_rows_counted_as_labels"),
            "p614_feature_coverage_gap_queue_boundary_audit_safe_for_model_claim": p614_feature_coverage_gap_queue_boundary_gap_audit.get("safe_for_model_claim"),
            "p614_feature_coverage_gap_queue_boundary_validation_success": bool(p614_feature_coverage_gap_queue_boundary_gap_audit_validation.get("success")),
            "p615_feature_label_boundary_quarantine_audit_label_contaminated_artifacts": p615_feature_label_boundary_quarantine_gap_audit.get("feature_label_boundary_quarantine_label_contaminated_artifact_count"),
            "p615_feature_label_boundary_quarantine_audit_label_contaminated_records": p615_feature_label_boundary_quarantine_gap_audit.get("feature_label_boundary_quarantine_label_contaminated_record_count"),
            "p615_feature_label_boundary_quarantine_audit_excluded_from_index_artifacts": p615_feature_label_boundary_quarantine_gap_audit.get("feature_label_boundary_quarantine_excluded_from_index_artifact_count"),
            "p615_feature_label_boundary_quarantine_audit_safe_for_model_claim": p615_feature_label_boundary_quarantine_gap_audit.get("safe_for_model_claim"),
            "p615_feature_label_boundary_quarantine_validation_success": bool(p615_feature_label_boundary_quarantine_gap_audit_validation.get("success")),
            "p616_benchmark_score_cache_validation_boundary_benchmark_rows": p616_benchmark_score_cache_validation_boundary_gap_audit.get("benchmark_score_cache_validation_benchmark_rows"),
            "p616_benchmark_score_cache_validation_boundary_valid_rows": p616_benchmark_score_cache_validation_boundary_gap_audit.get("benchmark_score_cache_validation_valid_rows"),
            "p616_benchmark_score_cache_validation_boundary_invalid_rows": p616_benchmark_score_cache_validation_boundary_gap_audit.get("benchmark_score_cache_validation_invalid_rows"),
            "p616_benchmark_score_cache_validation_boundary_heads_ready": p616_benchmark_score_cache_validation_boundary_gap_audit.get("benchmark_score_cache_validation_heads_ready"),
            "p616_benchmark_score_cache_validation_boundary_ready_for_model_claim": p616_benchmark_score_cache_validation_boundary_gap_audit.get("benchmark_score_cache_validation_ready_for_model_claim"),
            "p616_benchmark_score_cache_validation_boundary_audit_safe_for_model_claim": p616_benchmark_score_cache_validation_boundary_gap_audit.get("safe_for_model_claim"),
            "p616_benchmark_score_cache_validation_boundary_validation_success": bool(p616_benchmark_score_cache_validation_boundary_gap_audit_validation.get("success")),
            "p617_benchmark_coverage_dashboard_boundary_benchmark_rows": p617_benchmark_coverage_dashboard_boundary_gap_audit.get("benchmark_coverage_dashboard_benchmark_rows"),
            "p617_benchmark_coverage_dashboard_boundary_valid_rows": p617_benchmark_coverage_dashboard_boundary_gap_audit.get("benchmark_coverage_dashboard_valid_rows"),
            "p617_benchmark_coverage_dashboard_boundary_invalid_rows": p617_benchmark_coverage_dashboard_boundary_gap_audit.get("benchmark_coverage_dashboard_invalid_rows"),
            "p617_benchmark_coverage_dashboard_boundary_heads_ready": p617_benchmark_coverage_dashboard_boundary_gap_audit.get("benchmark_coverage_dashboard_heads_ready"),
            "p617_benchmark_coverage_dashboard_boundary_ready_for_model_claim": p617_benchmark_coverage_dashboard_boundary_gap_audit.get("benchmark_coverage_dashboard_ready_for_model_claim"),
            "p617_benchmark_coverage_dashboard_boundary_audit_safe_for_model_claim": p617_benchmark_coverage_dashboard_boundary_gap_audit.get("safe_for_model_claim"),
            "p617_benchmark_coverage_dashboard_boundary_validation_success": bool(p617_benchmark_coverage_dashboard_boundary_gap_audit_validation.get("success")),
            "p618_five_head_benchmark_gap_plan_boundary_action_rows": p618_five_head_benchmark_gap_plan_boundary_gap_audit.get("five_head_benchmark_gap_plan_action_rows"),
            "p618_five_head_benchmark_gap_plan_boundary_required_benchmarks": p618_five_head_benchmark_gap_plan_boundary_gap_audit.get("five_head_benchmark_gap_plan_required_benchmarks"),
            "p618_five_head_benchmark_gap_plan_boundary_cache_validated_benchmarks": p618_five_head_benchmark_gap_plan_boundary_gap_audit.get("five_head_benchmark_gap_plan_cache_validated_benchmarks"),
            "p618_five_head_benchmark_gap_plan_boundary_heads_with_complete_scorecards": p618_five_head_benchmark_gap_plan_boundary_gap_audit.get("five_head_benchmark_gap_plan_heads_with_complete_scorecards"),
            "p618_five_head_benchmark_gap_plan_boundary_ready_for_model_claim": p618_five_head_benchmark_gap_plan_boundary_gap_audit.get("five_head_benchmark_gap_plan_ready_for_model_claim"),
            "p618_five_head_benchmark_gap_plan_boundary_audit_safe_for_model_claim": p618_five_head_benchmark_gap_plan_boundary_gap_audit.get("safe_for_model_claim"),
            "p618_five_head_benchmark_gap_plan_boundary_validation_success": bool(p618_five_head_benchmark_gap_plan_boundary_gap_audit_validation.get("success")),
            "p619_benchmark_lane_machine_prereview_boundary_lane_count": p619_benchmark_lane_machine_prereview_boundary_gap_audit.get("benchmark_lane_machine_prereview_lane_count"),
            "p619_benchmark_lane_machine_prereview_boundary_formal_decision_rows_observed": p619_benchmark_lane_machine_prereview_boundary_gap_audit.get("benchmark_lane_machine_prereview_formal_decision_rows_observed"),
            "p619_benchmark_lane_machine_prereview_boundary_training_import_written_rows": p619_benchmark_lane_machine_prereview_boundary_gap_audit.get("benchmark_lane_machine_prereview_training_import_written_rows"),
            "p619_benchmark_lane_machine_prereview_boundary_audit_safe_for_model_claim": p619_benchmark_lane_machine_prereview_boundary_gap_audit.get("safe_for_model_claim"),
            "p619_benchmark_lane_machine_prereview_boundary_validation_success": bool(p619_benchmark_lane_machine_prereview_boundary_gap_audit_validation.get("success")),
            "p620_benchmark_lane_status_aggregate_boundary_lane_count": p620_benchmark_lane_status_aggregate_boundary_gap_audit.get("benchmark_lane_status_aggregate_lane_count"),
            "p620_benchmark_lane_status_aggregate_boundary_training_import_written_rows": p620_benchmark_lane_status_aggregate_boundary_gap_audit.get("benchmark_lane_status_aggregate_training_import_written_rows"),
            "p620_benchmark_lane_status_aggregate_boundary_claim_release_gate": p620_benchmark_lane_status_aggregate_boundary_gap_audit.get("benchmark_lane_status_aggregate_claim_release_gate"),
            "p620_benchmark_lane_status_aggregate_boundary_audit_safe_for_model_claim": p620_benchmark_lane_status_aggregate_boundary_gap_audit.get("safe_for_model_claim"),
            "p620_benchmark_lane_status_aggregate_boundary_validation_success": bool(p620_benchmark_lane_status_aggregate_boundary_gap_audit_validation.get("success")),
            "p621_ddg_executable_probe_boundary_backend_rows": p621_ddg_executable_probe_boundary_gap_audit.get("ddg_executable_probe_backend_rows"),
            "p621_ddg_executable_probe_boundary_ready_for_execution_rows": p621_ddg_executable_probe_boundary_gap_audit.get("ddg_executable_probe_ready_for_ddg_execution_rows"),
            "p621_ddg_executable_probe_boundary_physics_ddg_ready": p621_ddg_executable_probe_boundary_gap_audit.get("ddg_executable_probe_physics_ddg_ready"),
            "p621_ddg_executable_probe_boundary_ddg_smoke_job_executed": p621_ddg_executable_probe_boundary_gap_audit.get("ddg_executable_probe_ddg_smoke_job_executed"),
            "p621_ddg_executable_probe_boundary_claim_eligible_rows": p621_ddg_executable_probe_boundary_gap_audit.get("ddg_executable_probe_claim_eligible_rows_now"),
            "p621_ddg_executable_probe_boundary_audit_safe_for_model_claim": p621_ddg_executable_probe_boundary_gap_audit.get("safe_for_model_claim"),
            "p621_ddg_executable_probe_boundary_validation_success": bool(p621_ddg_executable_probe_boundary_gap_audit_validation.get("success")),
            "p622_pyrosetta_physical_smoke_boundary_ddg_table_rows": p622_pyrosetta_physical_smoke_boundary_gap_audit.get("pyrosetta_physical_smoke_ddg_table_rows"),
            "p622_pyrosetta_physical_smoke_boundary_training_label_rows": p622_pyrosetta_physical_smoke_boundary_gap_audit.get("pyrosetta_physical_smoke_training_label_rows"),
            "p622_pyrosetta_physical_smoke_boundary_manual_review_required_rows": p622_pyrosetta_physical_smoke_boundary_gap_audit.get("pyrosetta_physical_smoke_manual_review_required_rows"),
            "p622_pyrosetta_physical_smoke_boundary_physical_smoke_passed": p622_pyrosetta_physical_smoke_boundary_gap_audit.get("pyrosetta_physical_smoke_physical_smoke_passed"),
            "p622_pyrosetta_physical_smoke_boundary_audit_safe_for_model_claim": p622_pyrosetta_physical_smoke_boundary_gap_audit.get("safe_for_model_claim"),
            "p622_pyrosetta_physical_smoke_boundary_validation_success": bool(p622_pyrosetta_physical_smoke_boundary_gap_audit_validation.get("success")),
            "p623_pyrosetta_verified_ddg_feature_boundary_computed_feature_rows": p623_pyrosetta_verified_ddg_feature_boundary_gap_audit.get("pyrosetta_verified_ddg_feature_computed_feature_rows"),
            "p623_pyrosetta_verified_ddg_feature_boundary_quality_passed_rows": p623_pyrosetta_verified_ddg_feature_boundary_gap_audit.get("pyrosetta_verified_ddg_feature_quality_passed_rows"),
            "p623_pyrosetta_verified_ddg_feature_boundary_quality_blocked_rows": p623_pyrosetta_verified_ddg_feature_boundary_gap_audit.get("pyrosetta_verified_ddg_feature_quality_blocked_rows"),
            "p623_pyrosetta_verified_ddg_feature_boundary_scientific_validity_claim": p623_pyrosetta_verified_ddg_feature_boundary_gap_audit.get("pyrosetta_verified_ddg_feature_scientific_validity_claim"),
            "p623_pyrosetta_verified_ddg_feature_boundary_audit_safe_for_model_claim": p623_pyrosetta_verified_ddg_feature_boundary_gap_audit.get("safe_for_model_claim"),
            "p623_pyrosetta_verified_ddg_feature_boundary_validation_success": bool(p623_pyrosetta_verified_ddg_feature_boundary_gap_audit_validation.get("success")),
            "p624_foldx_physical_smoke_boundary_blocker_count": p624_foldx_physical_smoke_boundary_gap_audit.get("foldx_physical_smoke_blocker_count"),
            "p624_foldx_physical_smoke_boundary_ready_execution_plan_rows": p624_foldx_physical_smoke_boundary_gap_audit.get("foldx_physical_smoke_ready_execution_plan_rows"),
            "p624_foldx_physical_smoke_boundary_physical_smoke_passed": p624_foldx_physical_smoke_boundary_gap_audit.get("foldx_physical_smoke_physical_smoke_passed"),
            "p624_foldx_physical_smoke_boundary_runtime_receipt_ready": p624_foldx_physical_smoke_boundary_gap_audit.get("foldx_physical_smoke_runtime_receipt_ready"),
            "p624_foldx_physical_smoke_boundary_audit_safe_for_model_claim": p624_foldx_physical_smoke_boundary_gap_audit.get("safe_for_model_claim"),
            "p624_foldx_physical_smoke_boundary_validation_success": bool(p624_foldx_physical_smoke_boundary_gap_audit_validation.get("success")),
            "p625_ddg_backend_operator_packet_boundary_packet_rows": p625_ddg_backend_operator_packet_boundary_gap_audit.get("ddg_backend_operator_packet_packet_rows"),
            "p625_ddg_backend_operator_packet_boundary_ready_for_execution_rows": p625_ddg_backend_operator_packet_boundary_gap_audit.get("ddg_backend_operator_packet_ready_for_execution_now_rows"),
            "p625_ddg_backend_operator_packet_boundary_requires_human_input_rows": p625_ddg_backend_operator_packet_boundary_gap_audit.get("ddg_backend_operator_packet_requires_human_input_rows"),
            "p625_ddg_backend_operator_packet_boundary_completion_ready_rows": p625_ddg_backend_operator_packet_boundary_gap_audit.get("ddg_backend_operator_packet_completion_ready_rows"),
            "p625_ddg_backend_operator_packet_boundary_audit_safe_for_model_claim": p625_ddg_backend_operator_packet_boundary_gap_audit.get("safe_for_model_claim"),
            "p625_ddg_backend_operator_packet_boundary_validation_success": bool(p625_ddg_backend_operator_packet_boundary_gap_audit_validation.get("success")),
            "p626_rosetta_physical_smoke_boundary_artifact_count": p626_rosetta_physical_smoke_boundary_gap_audit.get("rosetta_physical_smoke_artifact_count"),
            "p626_rosetta_physical_smoke_boundary_physical_smoke_passed": p626_rosetta_physical_smoke_boundary_gap_audit.get("rosetta_physical_smoke_physical_smoke_passed"),
            "p626_rosetta_physical_smoke_boundary_ddg_protocol_executed": p626_rosetta_physical_smoke_boundary_gap_audit.get("rosetta_physical_smoke_ddg_protocol_executed"),
            "p626_rosetta_physical_smoke_boundary_audit_safe_for_model_claim": p626_rosetta_physical_smoke_boundary_gap_audit.get("safe_for_model_claim"),
            "p626_rosetta_physical_smoke_boundary_validation_success": bool(p626_rosetta_physical_smoke_boundary_gap_audit_validation.get("success")),
            "p627_pyrosetta_concordance_boundary_input_feature_rows": p627_pyrosetta_verified_mutation_ddg_concordance_boundary_gap_audit.get("pyrosetta_concordance_input_feature_rows"),
            "p627_pyrosetta_concordance_boundary_multi_chain_candidate_rows": p627_pyrosetta_verified_mutation_ddg_concordance_boundary_gap_audit.get("pyrosetta_concordance_multi_chain_candidate_rows"),
            "p627_pyrosetta_concordance_boundary_quality_passed_rows": p627_pyrosetta_verified_mutation_ddg_concordance_boundary_gap_audit.get("pyrosetta_concordance_quality_passed_rows"),
            "p627_pyrosetta_concordance_boundary_quality_blocked_rows": p627_pyrosetta_verified_mutation_ddg_concordance_boundary_gap_audit.get("pyrosetta_concordance_quality_blocked_rows"),
            "p627_pyrosetta_concordance_boundary_quality_gate_status": p627_pyrosetta_verified_mutation_ddg_concordance_boundary_gap_audit.get("pyrosetta_concordance_quality_gate_status"),
            "p627_pyrosetta_concordance_boundary_audit_safe_for_model_claim": p627_pyrosetta_verified_mutation_ddg_concordance_boundary_gap_audit.get("safe_for_model_claim"),
            "p627_pyrosetta_concordance_boundary_validation_success": bool(p627_pyrosetta_verified_mutation_ddg_concordance_boundary_gap_audit_validation.get("success")),
            "p628_pyrosetta_install_probe_boundary_wheel_present": p628_pyrosetta_local_install_probe_boundary_gap_audit.get("pyrosetta_install_probe_wheel_present"),
            "p628_pyrosetta_install_probe_boundary_module_spec_available": p628_pyrosetta_local_install_probe_boundary_gap_audit.get("pyrosetta_install_probe_module_spec_available"),
            "p628_pyrosetta_install_probe_boundary_import_succeeded": p628_pyrosetta_local_install_probe_boundary_gap_audit.get("pyrosetta_install_probe_import_succeeded"),
            "p628_pyrosetta_install_probe_boundary_approved_for_physical_ddg_runtime": p628_pyrosetta_local_install_probe_boundary_gap_audit.get("pyrosetta_install_probe_approved_for_physical_ddg_runtime"),
            "p628_pyrosetta_install_probe_boundary_physics_ddg_ready": p628_pyrosetta_local_install_probe_boundary_gap_audit.get("pyrosetta_install_probe_physics_ddg_ready"),
            "p628_pyrosetta_install_probe_boundary_audit_safe_for_model_claim": p628_pyrosetta_local_install_probe_boundary_gap_audit.get("safe_for_model_claim"),
            "p628_pyrosetta_install_probe_boundary_validation_success": bool(p628_pyrosetta_local_install_probe_boundary_gap_audit_validation.get("success")),
            "p629_ddg_runtime_preflight_boundary_physical_backend_rows": p629_ddg_physical_runtime_receipt_preflight_boundary_gap_audit.get("ddg_runtime_preflight_physical_backend_rows"),
            "p629_ddg_runtime_preflight_boundary_ready_backend_rows": p629_ddg_physical_runtime_receipt_preflight_boundary_gap_audit.get("ddg_runtime_preflight_ready_physical_backend_rows"),
            "p629_ddg_runtime_preflight_boundary_blocked_backend_rows": p629_ddg_physical_runtime_receipt_preflight_boundary_gap_audit.get("ddg_runtime_preflight_blocked_physical_backend_rows"),
            "p629_ddg_runtime_preflight_boundary_approved_runtime_receipt_rows": p629_ddg_physical_runtime_receipt_preflight_boundary_gap_audit.get("ddg_runtime_preflight_approved_runtime_receipt_rows"),
            "p629_ddg_runtime_preflight_boundary_capability_status": p629_ddg_physical_runtime_receipt_preflight_boundary_gap_audit.get("ddg_runtime_preflight_capability_status"),
            "p629_ddg_runtime_preflight_boundary_safe_pipeline_manifest_connected": p629_ddg_physical_runtime_receipt_preflight_boundary_gap_audit.get("ddg_runtime_preflight_safe_pipeline_manifest_connected"),
            "p629_ddg_runtime_preflight_boundary_audit_safe_for_model_claim": p629_ddg_physical_runtime_receipt_preflight_boundary_gap_audit.get("safe_for_model_claim"),
            "p629_ddg_runtime_preflight_boundary_validation_success": bool(p629_ddg_physical_runtime_receipt_preflight_boundary_gap_audit_validation.get("success")),
            "p630_ddg_runtime_receipt_boundary_receipt_rows": p630_ddg_backend_runtime_receipt_validation_boundary_gap_audit.get("ddg_runtime_receipt_receipt_rows"),
            "p630_ddg_runtime_receipt_boundary_valid_receipt_rows": p630_ddg_backend_runtime_receipt_validation_boundary_gap_audit.get("ddg_runtime_receipt_valid_receipt_rows"),
            "p630_ddg_runtime_receipt_boundary_approved_runtime_rows": p630_ddg_backend_runtime_receipt_validation_boundary_gap_audit.get("ddg_runtime_receipt_approved_runtime_rows"),
            "p630_ddg_runtime_receipt_boundary_missing_backend_rows": p630_ddg_backend_runtime_receipt_validation_boundary_gap_audit.get("ddg_runtime_receipt_missing_backend_rows"),
            "p630_ddg_runtime_receipt_boundary_all_physical_backends_ready": p630_ddg_backend_runtime_receipt_validation_boundary_gap_audit.get("ddg_runtime_receipt_all_physical_backends_ready"),
            "p630_ddg_runtime_receipt_boundary_capability_status": p630_ddg_backend_runtime_receipt_validation_boundary_gap_audit.get("ddg_runtime_receipt_capability_status"),
            "p630_ddg_runtime_receipt_boundary_audit_safe_for_model_claim": p630_ddg_backend_runtime_receipt_validation_boundary_gap_audit.get("safe_for_model_claim"),
            "p630_ddg_runtime_receipt_boundary_validation_success": bool(p630_ddg_backend_runtime_receipt_validation_boundary_gap_audit_validation.get("success")),
            "p631_ddg_physical_smoke_harness_boundary_contract_rows": p631_ddg_physical_smoke_harness_boundary_gap_audit.get("ddg_physical_smoke_harness_contract_rows"),
            "p631_ddg_physical_smoke_harness_boundary_passed_rows": p631_ddg_physical_smoke_harness_boundary_gap_audit.get("ddg_physical_smoke_harness_passed_rows"),
            "p631_ddg_physical_smoke_harness_boundary_can_execute_now_rows": p631_ddg_physical_smoke_harness_boundary_gap_audit.get("ddg_physical_smoke_harness_can_execute_now_rows"),
            "p631_ddg_physical_smoke_harness_boundary_ready_execution_plan_rows": p631_ddg_physical_smoke_harness_boundary_gap_audit.get("ddg_physical_smoke_harness_ready_execution_plan_rows"),
            "p631_ddg_physical_smoke_harness_boundary_physics_ddg_ready_observed": p631_ddg_physical_smoke_harness_boundary_gap_audit.get("ddg_physical_smoke_harness_physics_ddg_ready_observed"),
            "p631_ddg_physical_smoke_harness_boundary_audit_safe_for_model_claim": p631_ddg_physical_smoke_harness_boundary_gap_audit.get("safe_for_model_claim"),
            "p631_ddg_physical_smoke_harness_boundary_validation_success": bool(p631_ddg_physical_smoke_harness_boundary_gap_audit_validation.get("success")),
            "p632_ddg_proxy_physics_claim_boundary_proxy_backend_ready": p632_ddg_proxy_physics_claim_boundary_gap_audit.get("ddg_proxy_physics_proxy_backend_ready"),
            "p632_ddg_proxy_physics_claim_boundary_proxy_is_physics": p632_ddg_proxy_physics_claim_boundary_gap_audit.get("ddg_proxy_physics_proxy_is_physics"),
            "p632_ddg_proxy_physics_claim_boundary_physics_ddg_ready": p632_ddg_proxy_physics_claim_boundary_gap_audit.get("ddg_proxy_physics_physics_ddg_ready"),
            "p632_ddg_proxy_physics_claim_boundary_audit_safe_for_model_claim": p632_ddg_proxy_physics_claim_boundary_gap_audit.get("safe_for_model_claim"),
            "p632_ddg_proxy_physics_claim_boundary_validation_success": bool(p632_ddg_proxy_physics_claim_boundary_gap_audit_validation.get("success")),
            "p633_execution_receipt_freshness_boundary_total_receipts": p633_execution_receipt_freshness_boundary_gap_audit.get("execution_receipt_freshness_total_receipts"),
            "p633_execution_receipt_freshness_boundary_stale_receipts": p633_execution_receipt_freshness_boundary_gap_audit.get("execution_receipt_freshness_stale_receipts"),
            "p633_execution_receipt_freshness_boundary_missing_artifacts": p633_execution_receipt_freshness_boundary_gap_audit.get("execution_receipt_freshness_missing_artifacts"),
            "p633_execution_receipt_freshness_boundary_receipts_without_hash_fields": p633_execution_receipt_freshness_boundary_gap_audit.get("execution_receipt_freshness_receipts_without_hash_fields"),
            "p633_execution_receipt_freshness_boundary_audit_safe_for_model_claim": p633_execution_receipt_freshness_boundary_gap_audit.get("safe_for_model_claim"),
            "p633_execution_receipt_freshness_boundary_validation_success": bool(p633_execution_receipt_freshness_boundary_gap_audit_validation.get("success")),
            "p634_parallel_hard_gate_execution_boundary_receipt_rows": p634_parallel_hard_gate_execution_boundary_gap_audit.get("parallel_hard_gate_execution_receipt_rows"),
            "p634_parallel_hard_gate_execution_boundary_eligibility_changed_rows": p634_parallel_hard_gate_execution_boundary_gap_audit.get("parallel_hard_gate_execution_eligibility_changed_rows"),
            "p634_parallel_hard_gate_execution_boundary_formal_decision_written_rows": p634_parallel_hard_gate_execution_boundary_gap_audit.get("parallel_hard_gate_execution_formal_decision_written_rows"),
            "p634_parallel_hard_gate_execution_boundary_training_import_written_rows": p634_parallel_hard_gate_execution_boundary_gap_audit.get("parallel_hard_gate_execution_training_import_written_rows"),
            "p634_parallel_hard_gate_execution_boundary_audit_safe_for_model_claim": p634_parallel_hard_gate_execution_boundary_gap_audit.get("safe_for_model_claim"),
            "p634_parallel_hard_gate_execution_boundary_validation_success": bool(p634_parallel_hard_gate_execution_boundary_gap_audit_validation.get("success")),
            "p635_ddg_backend_failure_boundary_capability_status": p635_ddg_backend_failure_boundary_gap_audit.get("ddg_backend_failure_capability_status"),
            "p635_ddg_backend_failure_boundary_physics_ddg_ready": p635_ddg_backend_failure_boundary_gap_audit.get("ddg_backend_failure_physics_ddg_ready"),
            "p635_ddg_backend_failure_boundary_ready_backend_count": p635_ddg_backend_failure_boundary_gap_audit.get("ddg_backend_failure_ready_backend_count"),
            "p635_ddg_backend_failure_boundary_proxy_is_physics": p635_ddg_backend_failure_boundary_gap_audit.get("ddg_backend_failure_proxy_is_physics"),
            "p635_ddg_backend_failure_boundary_training_labels_written": p635_ddg_backend_failure_boundary_gap_audit.get("ddg_backend_failure_training_labels_written"),
            "p635_ddg_backend_failure_boundary_audit_safe_for_model_claim": p635_ddg_backend_failure_boundary_gap_audit.get("safe_for_model_claim"),
            "p635_ddg_backend_failure_boundary_validation_success": bool(p635_ddg_backend_failure_boundary_gap_audit_validation.get("success")),
            "p636_human_review_closeout_current_boundary_closeout_rows": p636_human_review_closeout_current_boundary_gap_audit.get("closeout_current_rows"),
            "p636_human_review_closeout_current_boundary_awaiting_human_decision_rows": p636_human_review_closeout_current_boundary_gap_audit.get("closeout_current_awaiting_human_decision_rows"),
            "p636_human_review_closeout_current_boundary_completion_ready_rows": p636_human_review_closeout_current_boundary_gap_audit.get("closeout_current_completion_ready_rows"),
            "p636_human_review_closeout_current_boundary_validation_success": bool(p636_human_review_closeout_current_boundary_gap_audit_validation.get("success")),
            "p637_operator_work_receipt_manifest_current_boundary_receipt_rows": p637_operator_work_receipt_manifest_current_boundary_gap_audit.get("receipt_manifest_current_receipt_rows"),
            "p637_operator_work_receipt_manifest_current_boundary_open_blocked_receipt_rows": p637_operator_work_receipt_manifest_current_boundary_gap_audit.get("receipt_manifest_current_open_blocked_receipt_rows"),
            "p637_operator_work_receipt_manifest_current_boundary_completion_ready_items": p637_operator_work_receipt_manifest_current_boundary_gap_audit.get("receipt_manifest_current_completion_ready_items"),
            "p637_operator_work_receipt_manifest_current_boundary_release_ready": p637_operator_work_receipt_manifest_current_boundary_gap_audit.get("receipt_manifest_current_release_ready"),
            "p637_operator_work_receipt_manifest_current_boundary_validation_success": bool(p637_operator_work_receipt_manifest_current_boundary_gap_audit_validation.get("success")),
            "p638_top_tier_ready_to_verify_current_boundary_receipt_rows": p638_top_tier_ready_to_verify_current_boundary_gap_audit.get("ready_receipt_current_receipt_rows"),
            "p638_top_tier_ready_to_verify_current_boundary_valid_receipt_rows": p638_top_tier_ready_to_verify_current_boundary_gap_audit.get("ready_receipt_current_valid_receipt_rows"),
            "p638_top_tier_ready_to_verify_current_boundary_invalid_receipt_rows": p638_top_tier_ready_to_verify_current_boundary_gap_audit.get("ready_receipt_current_invalid_receipt_rows"),
            "p638_top_tier_ready_to_verify_current_boundary_release_ready": p638_top_tier_ready_to_verify_current_boundary_gap_audit.get("ready_receipt_current_release_ready"),
            "p638_top_tier_ready_to_verify_current_boundary_safe_for_training_import": p638_top_tier_ready_to_verify_current_boundary_gap_audit.get("ready_receipt_current_safe_for_training_import"),
            "p638_top_tier_ready_to_verify_current_boundary_audit_safe_for_model_claim": p638_top_tier_ready_to_verify_current_boundary_gap_audit.get("safe_for_model_claim"),
            "p638_top_tier_ready_to_verify_current_boundary_validation_success": bool(p638_top_tier_ready_to_verify_current_boundary_gap_audit_validation.get("success")),
            "p639_non_human_ready_to_verify_current_boundary_receipt_rows": p639_non_human_ready_to_verify_current_boundary_gap_audit.get("ready_receipt_current_receipt_rows"),
            "p639_non_human_ready_to_verify_current_boundary_valid_receipt_rows": p639_non_human_ready_to_verify_current_boundary_gap_audit.get("ready_receipt_current_valid_receipt_rows"),
            "p639_non_human_ready_to_verify_current_boundary_invalid_receipt_rows": p639_non_human_ready_to_verify_current_boundary_gap_audit.get("ready_receipt_current_invalid_receipt_rows"),
            "p639_non_human_ready_to_verify_current_boundary_release_ready": p639_non_human_ready_to_verify_current_boundary_gap_audit.get("ready_receipt_current_release_ready"),
            "p639_non_human_ready_to_verify_current_boundary_safe_for_training_import": p639_non_human_ready_to_verify_current_boundary_gap_audit.get("ready_receipt_current_safe_for_training_import"),
            "p639_non_human_ready_to_verify_current_boundary_audit_safe_for_model_claim": p639_non_human_ready_to_verify_current_boundary_gap_audit.get("safe_for_model_claim"),
            "p639_non_human_ready_to_verify_current_boundary_validation_success": bool(p639_non_human_ready_to_verify_current_boundary_gap_audit_validation.get("success")),
            "p640_ready_to_verify_promotion_current_boundary_audit_rows": p640_ready_to_verify_promotion_current_boundary_gap_audit.get("source_audit_rows"),
            "p640_ready_to_verify_promotion_current_boundary_local_artifact_completion_rows": p640_ready_to_verify_promotion_current_boundary_gap_audit.get("local_artifact_completion_rows"),
            "p640_ready_to_verify_promotion_current_boundary_verified_blocked_rows": p640_ready_to_verify_promotion_current_boundary_gap_audit.get("verified_blocked_rows"),
            "p640_ready_to_verify_promotion_current_boundary_automatic_promotion_rows": p640_ready_to_verify_promotion_current_boundary_gap_audit.get("automatic_promotion_rows"),
            "p640_ready_to_verify_promotion_current_boundary_release_ready": p640_ready_to_verify_promotion_current_boundary_gap_audit.get("release_ready"),
            "p640_ready_to_verify_promotion_current_boundary_safe_for_training_import": p640_ready_to_verify_promotion_current_boundary_gap_audit.get("safe_for_training_import"),
            "p640_ready_to_verify_promotion_current_boundary_audit_safe_for_model_claim": p640_ready_to_verify_promotion_current_boundary_gap_audit.get("safe_for_model_claim"),
            "p640_ready_to_verify_promotion_current_boundary_validation_success": bool(p640_ready_to_verify_promotion_current_boundary_gap_audit_validation.get("success")),
            "p641_p0_today_closeout_plan_rows": p641_p0_today_closeout_plan.get("plan_rows"),
            "p641_p0_today_closeout_plan_blocked_rows": p641_p0_today_closeout_plan.get("blocked_rows"),
            "p641_p0_today_closeout_plan_requires_human_or_external_input_rows": p641_p0_today_closeout_plan.get("requires_human_or_external_input_rows"),
            "p641_p0_today_closeout_plan_p0_local_closeout_package_ready": p641_p0_today_closeout_plan.get("p0_local_closeout_package_ready"),
            "p641_p0_today_closeout_plan_p0_unblocked": p641_p0_today_closeout_plan.get("p0_unblocked"),
            "p641_p0_today_closeout_plan_p0_completion_ready": p641_p0_today_closeout_plan.get("p0_completion_ready"),
            "p641_p0_today_closeout_plan_validation_success": bool(p641_p0_today_closeout_plan_validation.get("success")),
            "p642_p0_external_input_packet_manifest_packet_rows": p642_p0_external_input_packet_manifest.get("packet_rows"),
            "p642_p0_external_input_packet_manifest_open_blocked_packet_rows": p642_p0_external_input_packet_manifest.get("open_blocked_packet_rows"),
            "p642_p0_external_input_packet_manifest_ready_for_dispatch_rows": p642_p0_external_input_packet_manifest.get("packet_ready_for_dispatch_rows"),
            "p642_p0_external_input_packet_manifest_real_input_received_rows": p642_p0_external_input_packet_manifest.get("real_input_received_rows"),
            "p642_p0_external_input_packet_manifest_reviewed_decision_written_rows": p642_p0_external_input_packet_manifest.get("reviewed_decision_written_rows"),
            "p642_p0_external_input_packet_manifest_formal_intake_written_rows": p642_p0_external_input_packet_manifest.get("formal_intake_written_rows"),
            "p642_p0_external_input_packet_manifest_runtime_receipt_written_rows": p642_p0_external_input_packet_manifest.get("runtime_receipt_written_rows"),
            "p642_p0_external_input_packet_manifest_p0_unblocked": p642_p0_external_input_packet_manifest.get("p0_unblocked"),
            "p642_p0_external_input_packet_manifest_p0_completion_ready": p642_p0_external_input_packet_manifest.get("p0_completion_ready"),
            "p642_p0_external_input_packet_manifest_validation_success": bool(p642_p0_external_input_packet_manifest_validation.get("success")),
            "p643_p0_external_input_dispatch_board_dispatch_rows": p643_p0_external_input_dispatch_board.get("dispatch_rows"),
            "p643_p0_external_input_dispatch_board_open_blocked_dispatch_rows": p643_p0_external_input_dispatch_board.get("open_blocked_dispatch_rows"),
            "p643_p0_external_input_dispatch_board_dispatch_ready_rows": p643_p0_external_input_dispatch_board.get("dispatch_ready_rows"),
            "p643_p0_external_input_dispatch_board_real_input_received_rows": p643_p0_external_input_dispatch_board.get("real_input_received_rows"),
            "p643_p0_external_input_dispatch_board_reviewed_decision_written_rows": p643_p0_external_input_dispatch_board.get("reviewed_decision_written_rows"),
            "p643_p0_external_input_dispatch_board_formal_intake_written_rows": p643_p0_external_input_dispatch_board.get("formal_intake_written_rows"),
            "p643_p0_external_input_dispatch_board_runtime_receipt_written_rows": p643_p0_external_input_dispatch_board.get("runtime_receipt_written_rows"),
            "p643_p0_external_input_dispatch_board_p0_unblocked": p643_p0_external_input_dispatch_board.get("p0_unblocked"),
            "p643_p0_external_input_dispatch_board_p0_completion_ready": p643_p0_external_input_dispatch_board.get("p0_completion_ready"),
            "p643_p0_external_input_dispatch_board_validation_success": bool(p643_p0_external_input_dispatch_board_validation.get("success")),
            "p644_p0_external_input_handoff_receipt_board_handoff_rows": p644_p0_external_input_handoff_receipt_board.get("handoff_rows"),
            "p644_p0_external_input_handoff_receipt_board_prepared_handoff_rows": p644_p0_external_input_handoff_receipt_board.get("prepared_handoff_rows"),
            "p644_p0_external_input_handoff_receipt_board_open_blocked_handoff_rows": p644_p0_external_input_handoff_receipt_board.get("open_blocked_handoff_rows"),
            "p644_p0_external_input_handoff_receipt_board_handoff_sent_rows": p644_p0_external_input_handoff_receipt_board.get("handoff_sent_rows"),
            "p644_p0_external_input_handoff_receipt_board_operator_acknowledged_rows": p644_p0_external_input_handoff_receipt_board.get("operator_acknowledged_rows"),
            "p644_p0_external_input_handoff_receipt_board_external_input_acknowledged_rows": p644_p0_external_input_handoff_receipt_board.get("external_input_acknowledged_rows"),
            "p644_p0_external_input_handoff_receipt_board_real_input_received_rows": p644_p0_external_input_handoff_receipt_board.get("real_input_received_rows"),
            "p644_p0_external_input_handoff_receipt_board_reviewed_decision_written_rows": p644_p0_external_input_handoff_receipt_board.get("reviewed_decision_written_rows"),
            "p644_p0_external_input_handoff_receipt_board_formal_intake_written_rows": p644_p0_external_input_handoff_receipt_board.get("formal_intake_written_rows"),
            "p644_p0_external_input_handoff_receipt_board_runtime_receipt_written_rows": p644_p0_external_input_handoff_receipt_board.get("runtime_receipt_written_rows"),
            "p644_p0_external_input_handoff_receipt_board_p0_unblocked": p644_p0_external_input_handoff_receipt_board.get("p0_unblocked"),
            "p644_p0_external_input_handoff_receipt_board_p0_completion_ready": p644_p0_external_input_handoff_receipt_board.get("p0_completion_ready"),
            "p644_p0_external_input_handoff_receipt_board_validation_success": bool(p644_p0_external_input_handoff_receipt_board_validation.get("success")),
            "p645_p0_external_input_response_slot_registry_response_slot_rows": p645_p0_external_input_response_slot_registry.get("response_slot_rows"),
            "p645_p0_external_input_response_slot_registry_open_response_slot_rows": p645_p0_external_input_response_slot_registry.get("open_response_slot_rows"),
            "p645_p0_external_input_response_slot_registry_empty_response_slot_rows": p645_p0_external_input_response_slot_registry.get("empty_response_slot_rows"),
            "p645_p0_external_input_response_slot_registry_response_received_rows": p645_p0_external_input_response_slot_registry.get("response_received_rows"),
            "p645_p0_external_input_response_slot_registry_response_validated_rows": p645_p0_external_input_response_slot_registry.get("response_validated_rows"),
            "p645_p0_external_input_response_slot_registry_operator_acknowledged_rows": p645_p0_external_input_response_slot_registry.get("operator_acknowledged_rows"),
            "p645_p0_external_input_response_slot_registry_external_input_acknowledged_rows": p645_p0_external_input_response_slot_registry.get("external_input_acknowledged_rows"),
            "p645_p0_external_input_response_slot_registry_real_input_received_rows": p645_p0_external_input_response_slot_registry.get("real_input_received_rows"),
            "p645_p0_external_input_response_slot_registry_reviewed_decision_written_rows": p645_p0_external_input_response_slot_registry.get("reviewed_decision_written_rows"),
            "p645_p0_external_input_response_slot_registry_formal_intake_written_rows": p645_p0_external_input_response_slot_registry.get("formal_intake_written_rows"),
            "p645_p0_external_input_response_slot_registry_runtime_receipt_written_rows": p645_p0_external_input_response_slot_registry.get("runtime_receipt_written_rows"),
            "p645_p0_external_input_response_slot_registry_training_label_written_rows": p645_p0_external_input_response_slot_registry.get("training_label_written_rows"),
            "p645_p0_external_input_response_slot_registry_p0_unblocked": p645_p0_external_input_response_slot_registry.get("p0_unblocked"),
            "p645_p0_external_input_response_slot_registry_p0_completion_ready": p645_p0_external_input_response_slot_registry.get("p0_completion_ready"),
            "p645_p0_external_input_response_slot_registry_validation_success": bool(p645_p0_external_input_response_slot_registry_validation.get("success")),
            "p646_p0_external_input_response_intake_queue_queue_rows": p646_p0_external_input_response_intake_queue.get("queue_rows"),
            "p646_p0_external_input_response_intake_queue_open_queue_rows": p646_p0_external_input_response_intake_queue.get("open_queue_rows"),
            "p646_p0_external_input_response_intake_queue_empty_queue_rows": p646_p0_external_input_response_intake_queue.get("empty_queue_rows"),
            "p646_p0_external_input_response_intake_queue_enqueued_rows": p646_p0_external_input_response_intake_queue.get("enqueued_rows"),
            "p646_p0_external_input_response_intake_queue_dequeued_rows": p646_p0_external_input_response_intake_queue.get("dequeued_rows"),
            "p646_p0_external_input_response_intake_queue_response_received_rows": p646_p0_external_input_response_intake_queue.get("response_received_rows"),
            "p646_p0_external_input_response_intake_queue_response_validated_rows": p646_p0_external_input_response_intake_queue.get("response_validated_rows"),
            "p646_p0_external_input_response_intake_queue_operator_acknowledged_rows": p646_p0_external_input_response_intake_queue.get("operator_acknowledged_rows"),
            "p646_p0_external_input_response_intake_queue_external_input_acknowledged_rows": p646_p0_external_input_response_intake_queue.get("external_input_acknowledged_rows"),
            "p646_p0_external_input_response_intake_queue_real_input_received_rows": p646_p0_external_input_response_intake_queue.get("real_input_received_rows"),
            "p646_p0_external_input_response_intake_queue_reviewed_decision_written_rows": p646_p0_external_input_response_intake_queue.get("reviewed_decision_written_rows"),
            "p646_p0_external_input_response_intake_queue_formal_intake_written_rows": p646_p0_external_input_response_intake_queue.get("formal_intake_written_rows"),
            "p646_p0_external_input_response_intake_queue_runtime_receipt_written_rows": p646_p0_external_input_response_intake_queue.get("runtime_receipt_written_rows"),
            "p646_p0_external_input_response_intake_queue_training_label_written_rows": p646_p0_external_input_response_intake_queue.get("training_label_written_rows"),
            "p646_p0_external_input_response_intake_queue_p0_unblocked": p646_p0_external_input_response_intake_queue.get("p0_unblocked"),
            "p646_p0_external_input_response_intake_queue_p0_completion_ready": p646_p0_external_input_response_intake_queue.get("p0_completion_ready"),
            "p646_p0_external_input_response_intake_queue_validation_success": bool(p646_p0_external_input_response_intake_queue_validation.get("success")),
            "p647_p0_external_input_response_validation_preflight_preflight_rows": p647_p0_external_input_response_validation_preflight.get("preflight_rows"),
            "p647_p0_external_input_response_validation_preflight_open_preflight_rows": p647_p0_external_input_response_validation_preflight.get("open_preflight_rows"),
            "p647_p0_external_input_response_validation_preflight_empty_preflight_rows": p647_p0_external_input_response_validation_preflight.get("empty_preflight_rows"),
            "p647_p0_external_input_response_validation_preflight_preflight_executed_rows": p647_p0_external_input_response_validation_preflight.get("preflight_executed_rows"),
            "p647_p0_external_input_response_validation_preflight_queue_dequeued_rows": p647_p0_external_input_response_validation_preflight.get("queue_dequeued_rows"),
            "p647_p0_external_input_response_validation_preflight_response_received_rows": p647_p0_external_input_response_validation_preflight.get("response_received_rows"),
            "p647_p0_external_input_response_validation_preflight_response_validated_rows": p647_p0_external_input_response_validation_preflight.get("response_validated_rows"),
            "p647_p0_external_input_response_validation_preflight_real_input_received_rows": p647_p0_external_input_response_validation_preflight.get("real_input_received_rows"),
            "p647_p0_external_input_response_validation_preflight_reviewed_decision_written_rows": p647_p0_external_input_response_validation_preflight.get("reviewed_decision_written_rows"),
            "p647_p0_external_input_response_validation_preflight_formal_intake_written_rows": p647_p0_external_input_response_validation_preflight.get("formal_intake_written_rows"),
            "p647_p0_external_input_response_validation_preflight_runtime_receipt_written_rows": p647_p0_external_input_response_validation_preflight.get("runtime_receipt_written_rows"),
            "p647_p0_external_input_response_validation_preflight_training_label_written_rows": p647_p0_external_input_response_validation_preflight.get("training_label_written_rows"),
            "p647_p0_external_input_response_validation_preflight_p0_unblocked": p647_p0_external_input_response_validation_preflight.get("p0_unblocked"),
            "p647_p0_external_input_response_validation_preflight_p0_completion_ready": p647_p0_external_input_response_validation_preflight.get("p0_completion_ready"),
            "p647_p0_external_input_response_validation_preflight_validation_success": bool(p647_p0_external_input_response_validation_preflight_validation.get("success")),
            **p648_p652_summary,
            "stage25_operator_docs_sync_current_receipt_failures": stage25_docs_sync_current.get("failure_count"),
            "stage25_operator_docs_sync_current_receipt_target_rows": stage25_docs_sync_current.get("target_rows"),
            "stage25_operator_docs_sync_current_receipt_stale_rows": stage25_docs_sync_current.get("stale_rows"),
            "stage25_operator_docs_sync_current_receipt_provenance_rows": stage25_docs_sync_current.get("provenance_rows"),
            "stage25_operator_docs_sync_current_receipt_semantic_provenance_rows": stage25_docs_sync_current.get("semantic_provenance_rows"),
            "stage25_operator_docs_sync_current_receipt_semantic_projection_version": stage25_docs_sync_current.get("semantic_projection_version"),
            "stage25_operator_docs_sync_current_receipt_semantic_projection_test_vector_sha256": stage25_docs_sync_current.get("semantic_projection_test_vector_sha256"),
            "stage25_operator_docs_sync_current_receipt_path": stage25_docs_sync_current.get("receipt_path"),
            "stage25_operator_docs_sync_current_receipt_sha256": stage25_docs_sync_current.get("receipt_sha256"),
            "stage25_operator_docs_sync_current_receipt_contract_version": stage25_docs_sync_current.get("contract_version"),
            "stage25_operator_docs_sync_current_receipt_contract_sha256": stage25_docs_sync_current.get("contract_sha256"),
            "stage25_operator_docs_sync_current_receipt_regression_success": bool(stage25_docs_sync_current_regression.get("success")),
            "stage25_operator_docs_sync_current_receipt_regression_failed_rows": stage25_docs_sync_current_regression.get("failed_rows"),
            "stage25_operator_docs_sync_terminal_recovery_regression_success": bool(stage25_docs_sync_terminal_regression.get("success")),
            "stage25_operator_docs_sync_terminal_recovery_regression_failed_rows": stage25_docs_sync_terminal_regression.get("failed_rows"),
            "safe_training_pipeline_receipt_atomicity_regression_success": bool(safe_pipeline_receipt_atomicity_regression.get("success")),
            "safe_training_pipeline_receipt_atomicity_regression_failed_rows": safe_pipeline_receipt_atomicity_regression.get("failed_rows"),
            "safe_training_pipeline_current_receipt_success": bool(safe_pipeline_current_receipt.get("success")),
            "safe_training_pipeline_current_receipt_failures": safe_pipeline_current_receipt.get("failure_count"),
            "safe_training_pipeline_current_receipt_command_rows": safe_pipeline_current_receipt.get("command_rows"),
            "safe_training_pipeline_current_receipt_path": safe_pipeline_current_receipt.get("receipt_path"),
            "safe_training_pipeline_current_receipt_sha256": safe_pipeline_current_receipt.get("receipt_sha256"),
            "safe_training_pipeline_current_receipt_runner_sha256": safe_pipeline_current_receipt.get("runner_script_sha256"),
            "safe_training_pipeline_current_receipt_contract_version": safe_pipeline_current_receipt.get("command_contract_version"),
            "safe_training_pipeline_current_receipt_contract_sha256": safe_pipeline_current_receipt.get("command_contract_sha256"),
            "safe_training_pipeline_bootstrap_release_regression_success": bool(safe_pipeline_bootstrap_release_regression.get("success")),
            "safe_training_pipeline_bootstrap_release_regression_failed_rows": safe_pipeline_bootstrap_release_regression.get("failed_rows"),
            "local_release_terminal_defer_mode_regression_success": bool(terminal_defer_mode_regression.get("success")),
            "local_release_terminal_defer_mode_regression_failed_rows": terminal_defer_mode_regression.get("failed_rows"),
            "stage25_fail_closed_validation_current_receipt_validation_success": bool(stage25_current_receipt.get("success")),
            "stage25_fail_closed_validation_current_receipt_validation_failures": stage25_current_receipt.get("failure_count"),
            "stage25_fail_closed_validation_current_receipt_command_rows": stage25_current_receipt.get("command_rows"),
            "stage25_fail_closed_validation_current_receipt_regression_success": bool(stage25_current_regression.get("success")),
            "stage25_fail_closed_validation_current_receipt_regression_failed_rows": stage25_current_regression.get("failed_rows"),
            "stage25_post_source_drop_rerun_receipt_validation_success": bool(post_source_receipt_validation.get("receipt_valid")),
            "stage25_post_source_drop_rerun_receipt_validation_failures": post_source_receipt_validation.get("failure_count"),
            "stage25_post_source_drop_rerun_receipt_regression_success": post_source_receipt_regression.get("failure_count") == 0,
            "stage25_post_source_drop_rerun_receipt_regression_failed_rows": post_source_receipt_regression.get("failure_count"),
            "stage25_post_source_drop_rerun_receipt_regression_isolated_fixture": post_source_receipt_regression.get("isolated_fixture"),
            "stage25_post_source_drop_rerun_receipt_regression_real_inputs_mutated": post_source_receipt_regression.get("real_inputs_mutated"),
            "stage25_post_source_drop_rerun_validation_current_success": bool(post_source_validation_current.get("success")),
            "stage25_post_source_drop_rerun_validation_current_failures": post_source_validation_current.get("failure_count"),
            "stage25_post_source_drop_rerun_validation_current_regression_success": bool(post_source_validation_current_regression.get("success")),
            "stage25_post_source_drop_rerun_validation_current_regression_failed_rows": post_source_validation_current_regression.get("failed_case_count"),
            "stage25_post_source_drop_rerun_independent_policy_success": bool(post_source_independent_policy.get("success")),
            "stage25_post_source_drop_rerun_independent_policy_failures": post_source_independent_policy.get("failure_count"),
            "stage25_post_source_drop_rerun_independent_policy_regression_success": bool(post_source_independent_policy_regression.get("success")),
            "stage25_post_source_drop_rerun_independent_policy_regression_failed_rows": post_source_independent_policy_regression.get("failed_case_count"),
            "stage25_post_source_drop_rerun_independent_policy_current_success": bool(post_source_independent_policy_current.get("success")),
            "stage25_post_source_drop_rerun_independent_policy_current_failures": post_source_independent_policy_current.get("failure_count"),
            "stage25_post_source_drop_rerun_independent_policy_current_regression_success": bool(post_source_independent_policy_current_regression.get("success")),
            "stage25_post_source_drop_rerun_independent_policy_current_regression_failed_rows": post_source_independent_policy_current_regression.get("failed_case_count"),
            "model_claim_fail_closed_consistency_success": bool(model_claim_fail_closed_consistency.get("success")),
            "model_claim_fail_closed_consistency_failures": len(model_claim_fail_closed_consistency.get("failures") or []),
            "model_claim_fail_closed_consistency_strict_rows": model_claim_fail_closed_consistency.get("strict_rows"),
            "model_claim_fail_closed_consistency_claim_eligible_rows": model_claim_fail_closed_consistency.get("claim_eligible_rows"),
            "local_release_fail_closed_consistency_success": bool(local_release_fail_closed_consistency.get("success")),
            "local_release_fail_closed_consistency_failures": len(local_release_fail_closed_consistency.get("failures") or []),
            "local_release_fail_closed_consistency_release_ready": local_release_fail_closed_consistency.get("release_ready"),
            "local_release_fail_closed_consistency_artifact_count": local_release_fail_closed_consistency.get("artifact_count"),
            "local_release_fail_closed_consistency_receipt_atomic_commit": local_release_fail_closed_consistency.get("receipt_atomic_commit"),
            "local_release_fail_closed_consistency_lock_acquired": local_release_fail_closed_consistency.get("lock_acquired"),
            "local_release_consistency_receipt_atomicity_regression_success": bool(local_release_consistency_atomicity_regression.get("success")),
            "local_release_consistency_receipt_atomicity_regression_failed_rows": local_release_consistency_atomicity_regression.get("failed_case_count"),
            "local_release_consistency_receipt_current_success": bool(local_release_consistency_current.get("success")),
            "local_release_consistency_receipt_current_failures": local_release_consistency_current.get("failure_count"),
            "local_release_consistency_receipt_current_regression_success": bool(local_release_consistency_current_regression.get("success")),
            "local_release_consistency_receipt_current_regression_failed_rows": local_release_consistency_current_regression.get("failed_case_count"),
            "local_release_consistency_semantic_policy_success": bool(local_release_consistency_semantic_policy.get("success")),
            "local_release_consistency_semantic_policy_failures": local_release_consistency_semantic_policy.get("failure_count"),
            "local_release_consistency_semantic_policy_version": local_release_consistency_semantic_policy.get("expected_contract_version"),
            "local_release_consistency_semantic_policy_canonical_sha256": local_release_consistency_semantic_policy.get("expected_canonical_policy_sha256"),
            "local_release_consistency_semantic_policy_test_vector_sha256": local_release_consistency_semantic_policy.get("expected_test_vector_sha256"),
            "local_release_consistency_semantic_policy_regression_success": bool(local_release_consistency_semantic_policy_regression.get("success")),
            "local_release_consistency_semantic_policy_regression_failed_rows": local_release_consistency_semantic_policy_regression.get("failed_case_count"),
            "local_release_consistency_semantic_policy_current_success": bool(local_release_consistency_semantic_policy_current.get("success")),
            "local_release_consistency_semantic_policy_current_failures": local_release_consistency_semantic_policy_current.get("failure_count"),
            "local_release_consistency_semantic_policy_current_regression_success": bool(local_release_consistency_semantic_policy_current_regression.get("success")),
            "local_release_consistency_semantic_policy_current_regression_failed_rows": local_release_consistency_semantic_policy_current_regression.get("failed_case_count"),
            "local_release_consistency_semantic_policy_atomicity_regression_success": bool(local_release_consistency_semantic_policy_atomicity_regression.get("success")),
            "local_release_consistency_semantic_policy_atomicity_regression_failed_rows": local_release_consistency_semantic_policy_atomicity_regression.get("failed_case_count"),
            "local_release_safety_guard_link_success": bool(local_release_safety_guard_links.get("success")),
            "local_release_safety_guard_link_failures": len(local_release_safety_guard_links.get("failures") or []),
            "local_release_safety_guard_link_count": local_release_safety_guard_links.get("guard_link_count"),
            "local_release_safety_guard_links_atomicity_regression_success": bool(local_release_safety_guard_links_atomicity.get("success")),
            "local_release_safety_guard_links_atomicity_regression_failed_rows": local_release_safety_guard_links_atomicity.get("failed_case_count"),
            "local_release_safety_guard_links_current_success": bool(local_release_safety_guard_links_current.get("success")),
            "local_release_safety_guard_links_current_failures": local_release_safety_guard_links_current.get("failure_count"),
            "local_release_safety_guard_links_current_regression_success": bool(local_release_safety_guard_links_current_regression.get("success")),
            "local_release_safety_guard_links_current_regression_failed_rows": local_release_safety_guard_links_current_regression.get("failed_case_count"),
            "local_release_safety_guard_links_current_regression_atomicity_regression_success": bool(local_release_safety_guard_links_current_regression_atomicity.get("success")),
            "local_release_safety_guard_links_current_regression_atomicity_regression_failed_rows": local_release_safety_guard_links_current_regression_atomicity.get("failed_case_count"),
            "review_draft_formal_boundary_success": bool(review_draft_formal_boundary.get("success")),
            "review_draft_formal_boundary_failures": len(review_draft_formal_boundary.get("failures") or []),
            "review_draft_total_rows": review_draft_formal_boundary.get("total_review_draft_rows"),
            "review_draft_formal_decision_rows": review_draft_formal_boundary.get("total_formal_decision_rows"),
            "review_draft_rows_counted_as_formal_decisions": review_draft_formal_boundary.get("draft_rows_counted_as_formal_decisions"),
            "no_review_draft_training_leakage_success": bool(no_review_draft_training_leakage.get("success")),
            "no_review_draft_training_leakage_failures": len(no_review_draft_training_leakage.get("failures") or []),
            "no_review_draft_training_leakage_strict_rows": no_review_draft_training_leakage.get("strict_rows"),
            "no_review_draft_training_leakage_claim_eligible_rows": no_review_draft_training_leakage.get("claim_eligible_rows"),
            "draft_namespace_isolation_success": bool(draft_namespace_isolation.get("success")),
            "draft_namespace_isolation_failures": len(draft_namespace_isolation.get("failures") or []),
            "draft_namespace_allowed_marker_files": draft_namespace_isolation.get("allowed_marker_file_count"),
            "draft_namespace_unexpected_marker_files": draft_namespace_isolation.get("unexpected_marker_file_count"),
            "draft_namespace_generic_reports": len(draft_namespace_isolation.get("generic_draft_namespace_reports") or {}),
            "no_unreviewed_positive_gate_flags_success": bool(no_unreviewed_positive_gate_flags.get("success")),
            "no_unreviewed_positive_gate_flags_failures": len(no_unreviewed_positive_gate_flags.get("failures") or []),
            "no_unreviewed_positive_gate_flags_true_count": no_unreviewed_positive_gate_flags.get("positive_gate_true_count"),
            "no_unreviewed_positive_gate_flags_disallowed_true_count": no_unreviewed_positive_gate_flags.get("disallowed_positive_gate_true_count"),
            "no_unreviewed_positive_gate_flags_scanned_files": no_unreviewed_positive_gate_flags.get("scanned_file_count"),
            "report_positive_claim_gate_quarantine_success": bool(report_positive_claim_gate_quarantine.get("success")),
            "report_positive_claim_gate_quarantine_failures": len(report_positive_claim_gate_quarantine.get("failures") or []),
            "report_positive_claim_gate_quarantine_risky_true_hit_count": report_positive_claim_gate_quarantine.get("risky_true_hit_count"),
            "report_positive_claim_gate_quarantine_disallowed_true_hit_count": report_positive_claim_gate_quarantine.get("disallowed_true_hit_count"),
            "report_positive_claim_gate_quarantine_scanned_reports": report_positive_claim_gate_quarantine.get("scanned_report_count"),
            "reviewed_structure_graph_rows": reviewed_structure_graph.get("graph_rows"),
            "reviewed_structure_graph_failure_rows": reviewed_structure_graph.get("failure_rows"),
            "reviewed_structure_graph_validation_ready": bool(reviewed_structure_graph_validation.get("ready_for_coordinate_feature_use")),
            "reviewed_structure_graph_valid_rows": reviewed_structure_graph_validation.get("valid_rows"),
            "reviewed_structure_graph_safe_for_model_claim": bool(reviewed_structure_graph.get("safe_for_model_claim")),
            "structure_feature_model_contract_reviewed_graph_rows": (structure_feature_model_contract.get("reviewed_chain_graph_boundary") or {}).get("reviewed_graph_index_rows"),
            "structure_feature_model_contract_coordinate_rows_parsed": (structure_feature_model_contract.get("coordinate_file_parse_evidence") or {}).get("parsed_coordinate_feature_rows"),
            "structure_feature_model_contract_unreviewed_coordinate_rows_excluded": (structure_feature_model_contract.get("model_consumption_contract") or {}).get("unreviewed_coordinate_rows_excluded_from_reviewed_graph"),
            "structure_feature_model_contract_training_label_source": bool(structure_feature_model_contract.get("training_label_source")),
            "structure_feature_model_contract_safe_for_model_claim": bool(structure_feature_model_contract.get("safe_for_model_claim")),
            "structure_feature_model_contract_validation_success": bool(structure_feature_model_contract_validation.get("success")),
            "structure_feature_model_contract_validation_failures": len(structure_feature_model_contract_validation.get("failures") or []),
            "msa_trusted_cache_intake_rows": msa_trusted_cache_intake.get("intake_rows"),
            "msa_trusted_cache_accepted_rows": msa_trusted_cache_intake.get("accepted_rows"),
            "msa_trusted_cache_missing_target_rows": msa_trusted_cache_intake.get("missing_target_rows"),
            "msa_trusted_cache_ready_to_validate": bool(msa_trusted_cache_intake.get("ready_to_validate_cache")),
            "msa_cache_validation_ready": bool(msa_cache_validation.get("ready")),
            "msa_cache_validation_valid_rows": msa_cache_validation.get("valid_rows"),
            "msa_cache_validation_invalid_rows": msa_cache_validation.get("invalid_rows"),
            "msa_mmseqs_swissprot_cache_targets_with_hits": msa_mmseqs_cache_build.get("targets_with_hits"),
            "msa_mmseqs_swissprot_cache_raw_hit_rows": msa_mmseqs_cache_build.get("raw_hit_rows"),
            "msa_mmseqs_swissprot_cache_ready_to_apply": bool(msa_mmseqs_cache_build.get("ready_to_apply_trusted_cache_intake")),
            "mmseqs2_local_runtime_binary_present": bool(mmseqs2_local_runtime.get("binary_present")),
            "mmseqs2_local_runtime_probe_ok": bool(mmseqs2_local_runtime.get("binary_executable_probe_ok")),
            "mmseqs2_local_runtime_version": mmseqs2_local_runtime.get("binary_version"),
            "mmseqs2_local_runtime_ready_as_local_binary_runtime": bool(mmseqs2_local_runtime.get("ready_as_local_binary_runtime")),
            "mmseqs2_local_runtime_ready_for_msa_search": bool(mmseqs2_local_runtime.get("ready_for_msa_search")),
            "mmseqs_homolog_database_ready": bool(mmseqs_homolog_database.get("ready_as_homolog_database")),
            "mmseqs_homolog_database_name": mmseqs_homolog_database.get("database_name"),
            "mmseqs_homolog_database_version": mmseqs_homolog_database.get("database_version"),
            "mmseqs_homolog_database_sequence_rows": mmseqs_homolog_database.get("sequence_rows_from_lookup"),
            "mmseqs_homolog_database_smoke_hit_rows": mmseqs_homolog_database.get("smoke_hit_rows"),
            "msa_runtime_ready": bool(msa_runtime.get("runtime_ready")),
            "msa_runtime_selected_runtime": msa_runtime.get("selected_runtime"),
            "msa_runtime_homolog_database_ready": bool((msa_runtime.get("homolog_database") or {}).get("ready")),
            "benchmark_score_cache_intake_rows": benchmark_score_cache_intake.get("intake_rows"),
            "benchmark_score_cache_accepted_rows": benchmark_score_cache_intake.get("accepted_rows"),
            "benchmark_score_cache_missing_rows": benchmark_score_cache_intake.get("missing_rows"),
            "benchmark_score_cache_ready_to_validate": bool(benchmark_score_cache_intake.get("ready_to_validate_cache")),
            "benchmark_score_cache_validation_ready_for_model_claim": bool(benchmark_score_cache_validation.get("ready_for_model_claim")),
            "benchmark_score_cache_valid_rows": benchmark_score_cache_validation.get("valid_rows"),
            "benchmark_score_cache_invalid_rows": benchmark_score_cache_validation.get("invalid_rows"),
            "benchmark_score_cache_heads_ready": benchmark_score_cache_validation.get("heads_ready"),
            "kwb_activity_risk_smoke_benchmark_rows": kwb_activity_risk_smoke_benchmark.get("dataset_rows"),
            "kwb_activity_risk_smoke_benchmark_quality_status": kwb_activity_risk_smoke_benchmark.get("quality_status"),
            "kwb_activity_risk_smoke_benchmark_validation_success": bool(kwb_activity_risk_smoke_benchmark_validation.get("success")),
            "kwb_activity_risk_smoke_benchmark_ready_for_model_claim": bool(kwb_activity_risk_smoke_benchmark.get("ready_for_model_claim")),
            "fireprot_protherm_stability_benchmark_rows": fireprot_protherm_stability_benchmark.get("dataset_rows"),
            "fireprot_protherm_stability_benchmark_unique_mutation_keys": fireprot_protherm_stability_benchmark.get("unique_mutation_key_count"),
            "fireprot_protherm_stability_benchmark_training_import_written_rows": fireprot_protherm_stability_benchmark.get("fireprot_training_import_written_rows"),
            "fireprot_protherm_stability_benchmark_safe_for_model_claim": bool(fireprot_protherm_stability_benchmark.get("safe_for_model_claim")),
            "atom3d_msp_benchmark_rows": atom3d_msp_benchmark.get("dataset_rows"),
            "atom3d_msp_benchmark_split_counts": atom3d_msp_benchmark.get("split_counts"),
            "atom3d_msp_benchmark_label_counts": atom3d_msp_benchmark.get("label_counts"),
            "atom3d_msp_benchmark_validation_success": bool(atom3d_msp_benchmark_validation.get("success")),
            "atom3d_msp_benchmark_training_import_written_rows": atom3d_msp_benchmark.get("training_import_written_rows"),
            "atom3d_msp_benchmark_ready_for_model_claim": bool(atom3d_msp_benchmark_validation.get("ready_for_model_claim")),
            "catpred_gotenzymes_reference_benchmark_rows": catpred_gotenzymes_reference_benchmark.get("dataset_rows"),
            "catpred_gotenzymes_reference_benchmark_source_shard_counts": catpred_gotenzymes_reference_benchmark.get("source_shard_counts"),
            "catpred_gotenzymes_reference_benchmark_validation_success": bool(catpred_gotenzymes_reference_benchmark_validation.get("success")),
            "catpred_gotenzymes_reference_benchmark_training_import_written_rows": catpred_gotenzymes_reference_benchmark.get("training_import_written_rows"),
            "catpred_gotenzymes_reference_benchmark_catpred_model_executed": bool(catpred_gotenzymes_reference_benchmark.get("catpred_model_executed")),
            "catpred_gotenzymes_reference_benchmark_ready_for_model_claim": bool(catpred_gotenzymes_reference_benchmark_validation.get("ready_for_model_claim")),
            "posebusters_pose_plausibility_benchmark_rows": posebusters_pose_plausibility_benchmark.get("dataset_rows"),
            "posebusters_pose_plausibility_benchmark_unique_complexes": posebusters_pose_plausibility_benchmark.get("unique_complexes"),
            "posebusters_pose_plausibility_benchmark_validation_success": bool(posebusters_pose_plausibility_benchmark_validation.get("success")),
            "posebusters_pose_plausibility_benchmark_training_import_written_rows": posebusters_pose_plausibility_benchmark.get("training_import_written_rows"),
            "posebusters_pose_plausibility_benchmark_runtime_executed_locally": bool(posebusters_pose_plausibility_benchmark.get("posebusters_runtime_executed_locally")),
            "posebusters_pose_plausibility_benchmark_ready_for_model_claim": bool(posebusters_pose_plausibility_benchmark_validation.get("ready_for_model_claim")),
            "benchmark_coverage_dashboard_heads_ready": benchmark_coverage_dashboard.get("heads_ready"),
            "benchmark_coverage_dashboard_missing_benchmark_rows": benchmark_coverage_dashboard.get("missing_benchmark_rows"),
            "benchmark_coverage_dashboard_ready_for_model_claim": bool(benchmark_coverage_dashboard.get("ready_for_model_claim")),
            "benchmark_coverage_dashboard_validation_success": bool(benchmark_coverage_dashboard_validation.get("success")),
            "benchmark_coverage_dashboard_validation_failures": len(benchmark_coverage_dashboard_validation.get("failures") or []),
            "benchmark_readiness_packet_rows": benchmark_readiness_summary.get("packet_rows"),
            "benchmark_readiness_ready_packet_rows": benchmark_readiness_summary.get("completion_ready_rows"),
            "benchmark_readiness_invalid_gap_rows": benchmark_readiness_summary.get("invalid_gap_rows"),
            "benchmark_readiness_score_values_recorded": benchmark_readiness_summary.get("score_values_recorded"),
            "benchmark_readiness_validation_success": validation_success_fail_closed(benchmark_readiness_packet_validation),
            "benchmark_readiness_validation_contract_valid": bool(
                benchmark_readiness_packet_validation.get("contract_valid")
            ),
            "benchmark_readiness_validation_failure_count": benchmark_readiness_packet_validation.get("failure_count"),
            "benchmark_readiness_validation_failures": len(benchmark_readiness_packet_validation.get("failures") or []),
            "proteingym_local_source_present": bool(proteingym_local_source.get("source_present")),
            "proteingym_local_source_file_count": proteingym_local_source.get("file_count"),
            "proteingym_local_source_benchmark_file_count": proteingym_local_source.get("benchmark_file_count"),
            "proteingym_local_source_ready_as_external_source_evidence": bool(proteingym_local_source.get("ready_as_external_source_evidence")),
            "proteingym_local_source_ready_as_kwb_scorecard": bool(proteingym_local_source.get("ready_as_kwb_scorecard")),
            "external_stability_label_source_file_count": external_stability_label_sources.get("source_file_count"),
            "external_stability_label_total_rows": external_stability_label_sources.get("total_rows"),
            "external_stability_label_usable_numeric_rows": external_stability_label_sources.get("total_usable_numeric_rows"),
            "external_stability_label_ready_import_candidate_files": external_stability_label_sources.get("ready_import_candidate_files"),
            "external_stability_label_claim_eligible_rows_now": external_stability_label_sources.get("claim_eligible_rows_now"),
            "fireprot_curated_import_candidate_rows": fireprot_import_receipt.get("candidate_rows"),
            "fireprot_curated_import_claim_eligible_rows_now": fireprot_import_receipt.get("claim_eligible_rows_now"),
            "fireprot_curated_import_ready_for_training": bool(fireprot_import_receipt.get("ready_for_training_import")),
            "fireprot_curated_import_strict_overlap_rows": fireprot_import_leakage.get("strict_supervised_overlap_rows"),
            "fireprot_curated_import_holdout_overlap_rows": fireprot_import_leakage.get("kwb_strict_holdout_overlap_rows"),
            "fireprot_curated_direction_normalized_rows": fireprot_direction.get("direction_normalized_rows"),
            "fireprot_curated_direction_claim_eligible_rows_now": fireprot_direction.get("claim_eligible_rows_now"),
            "fireprot_curated_direction_ready_for_training": bool(fireprot_direction.get("ready_for_training_import")),
            "fireprot_curated_schema_mapped_candidate_rows": fireprot_schema_mapping.get("mapped_candidate_rows"),
            "fireprot_curated_schema_manual_review_rows": fireprot_schema_mapping.get("manual_review_required_rows"),
            "fireprot_curated_schema_ready_for_training_rows": fireprot_schema_mapping.get("ready_for_training_import_rows"),
            "fireprot_curated_schema_claim_eligible_rows_now": fireprot_schema_mapping.get("claim_eligible_rows_now"),
            "fireprot_curated_leakage_automated_checks_passed": bool(fireprot_leakage_review.get("automated_leakage_checks_passed")),
            "fireprot_curated_leakage_policy_approved": bool(fireprot_leakage_review.get("leakage_policy_approved")),
            "fireprot_curated_leakage_duplicate_mutation_key_count": fireprot_leakage_review.get("duplicate_mutation_key_count"),
            "fireprot_curated_leakage_group_count": fireprot_leakage_review.get("group_count"),
            "fireprot_curated_dedup_duplicate_mutation_key_count": fireprot_dedup.get("duplicate_mutation_key_count"),
            "fireprot_curated_dedup_same_assay_signature_groups": fireprot_dedup.get("same_assay_signature_groups"),
            "fireprot_curated_dedup_heterogeneous_assay_signature_groups": fireprot_dedup.get("heterogeneous_assay_signature_groups"),
            "fireprot_curated_dedup_aggregation_value_candidate_groups": fireprot_dedup.get("aggregation_value_candidate_groups"),
            "fireprot_curated_dedup_policy_approved": bool(fireprot_dedup.get("dedup_policy_approved")),
            "fireprot_dedup_review_packet_rows": fireprot_dedup_review.get("packet_rows"),
            "fireprot_dedup_review_decision_rows": fireprot_dedup_review.get("decision_rows_present"),
            "fireprot_dedup_review_approved_rows": fireprot_dedup_review.get("approved_rows"),
            "fireprot_dedup_review_ready_for_training_import_rows": fireprot_dedup_review.get("ready_for_training_import_rows"),
            "fireprot_dedup_decision_valid_rows": fireprot_dedup_decisions.get("valid_decision_rows"),
            "fireprot_dedup_decision_invalid_rows": fireprot_dedup_decisions.get("invalid_decision_rows"),
            "fireprot_dedup_decision_approved_for_import_candidate_rows": fireprot_dedup_decisions.get("approved_for_import_candidate_rows"),
            "fireprot_dedup_decision_keep_separate_reviewed_rows": fireprot_dedup_decisions.get("keep_separate_reviewed_rows"),
            "fireprot_dedup_decision_excluded_rows": fireprot_dedup_decisions.get("excluded_rows"),
            "fireprot_dedup_decision_missing_review_candidate_count": fireprot_dedup_decisions.get("missing_review_candidate_count"),
            "fireprot_reviewed_import_candidate_rows": fireprot_reviewed_import.get("reviewed_import_candidate_rows"),
            "fireprot_reviewed_import_ready_for_training_import_rows": fireprot_reviewed_import.get("ready_for_training_import_rows"),
            "fireprot_reviewed_import_claim_eligible_rows_now": fireprot_reviewed_import.get("claim_eligible_rows_now"),
            "pyrosetta_local_install_wheel_present": bool((pyrosetta_local_install_probe.get("wheel") or {}).get("present")),
            "pyrosetta_local_install_path_exists": bool((pyrosetta_local_install_probe.get("install") or {}).get("path_exists")),
            "pyrosetta_local_install_module_spec_available": bool((pyrosetta_local_install_probe.get("module_spec") or {}).get("available")),
            "pyrosetta_local_install_import_succeeded": bool((pyrosetta_local_install_probe.get("import_probe") or {}).get("succeeded")),
            "pyrosetta_local_install_validation_success": bool(pyrosetta_local_install_probe_validation.get("success")),
            "pyrosetta_local_install_physics_ddg_ready": bool(pyrosetta_local_install_probe.get("physics_ddg_ready")),
            "pyrosetta_physical_smoke_passed": bool(pyrosetta_physical_smoke_bootstrap.get("physical_smoke_passed")),
            "pyrosetta_physical_smoke_init_executed": bool(pyrosetta_physical_smoke_bootstrap.get("pyrosetta_init_executed")),
            "pyrosetta_physical_smoke_ddg_protocol_executed": bool(pyrosetta_physical_smoke_bootstrap.get("ddg_protocol_executed")),
            "pyrosetta_physical_smoke_artifact_count": len(pyrosetta_physical_smoke_bootstrap.get("smoke_artifact_sha256") or {}),
            "rosetta_physical_smoke_passed": bool(rosetta_physical_smoke_bootstrap.get("physical_smoke_passed")),
            "rosetta_physical_smoke_ddg_protocol_executed": bool(rosetta_physical_smoke_bootstrap.get("ddg_protocol_executed")),
            "rosetta_physical_smoke_random_seed": rosetta_physical_smoke_bootstrap.get("random_seed"),
            "rosetta_physical_smoke_constant_seed": bool(rosetta_physical_smoke_bootstrap.get("constant_seed")),
            "rosetta_physical_smoke_artifact_count": len(rosetta_physical_smoke_bootstrap.get("artifact_sha256") or {}),
            "verified_mutation_structure_candidate_rows": verified_mutation_structure_candidates.get("candidate_rows"),
            "verified_mutation_structure_unique_structures": verified_mutation_structure_candidates.get("unique_structures"),
            "verified_mutation_structure_mapping_deterministic_rows": verified_mutation_structure_mapping.get("deterministic_input_candidate_rows"),
            "verified_mutation_structure_mapping_pose_rows": verified_mutation_structure_mapping.get("pose_position_rows"),
            "verified_mutation_structure_mapping_validation_invalid_rows": verified_mutation_structure_mapping_validation.get("invalid_rows"),
            "pyrosetta_verified_mutation_ddg_feature_rows": pyrosetta_verified_mutation_ddg_features.get("computed_feature_rows"),
            "pyrosetta_verified_mutation_ddg_feature_failed_rows": pyrosetta_verified_mutation_ddg_features.get("failed_candidate_rows"),
            "pyrosetta_verified_mutation_ddg_feature_validation_invalid_rows": pyrosetta_verified_mutation_ddg_features_validation.get("invalid_rows"),
            "pyrosetta_verified_mutation_ddg_quality_passed_rows": pyrosetta_verified_mutation_ddg_features_validation.get("quality_passed_rows"),
            "pyrosetta_verified_mutation_ddg_quality_blocked_rows": pyrosetta_verified_mutation_ddg_features_validation.get("quality_blocked_rows"),
            "pyrosetta_verified_mutation_ddg_quality_gate_status": pyrosetta_verified_mutation_ddg_features_validation.get("quality_gate_status"),
            "pyrosetta_verified_mutation_ddg_feature_input_only": (
                pyrosetta_verified_mutation_ddg_features.get("safe_for_training_import") is False
                and pyrosetta_verified_mutation_ddg_features.get("safe_for_model_claim") is False
            ),
            "pyrosetta_multichain_ddg_concordance_rows": pyrosetta_multichain_ddg_concordance.get("multi_chain_candidate_rows"),
            "pyrosetta_multichain_ddg_concordant_rows": pyrosetta_multichain_ddg_concordance.get("chain_concordant_rows"),
            "pyrosetta_multichain_ddg_context_sensitive_rows": pyrosetta_multichain_ddg_concordance.get("chain_context_sensitive_rows"),
            "pyrosetta_multichain_ddg_quality_passed_rows": pyrosetta_multichain_ddg_concordance.get("quality_passed_rows"),
            "pyrosetta_multichain_ddg_quality_blocked_rows": pyrosetta_multichain_ddg_concordance.get("quality_blocked_rows"),
            "pyrosetta_multichain_ddg_concordance_invalid_rows": pyrosetta_multichain_ddg_concordance_validation.get("invalid_rows"),
            "ddg_backend_adapter_integrated": bool(ddg_backend.get("adapter_integrated")),
            "ddg_backend_ready_backend_count": ddg_backend.get("ready_backend_count"),
            "ddg_backend_executable_ready": bool(ddg_backend.get("executable_ddg_backend_ready")),
            "ddg_backend_proxy_ready": bool(ddg_backend.get("proxy_ddg_backend_ready")),
            "ddg_backend_one_backend_ready": bool(ddg_backend.get("one_ddg_backend_ready")),
            "ddg_failure_diagnostic_physics_ready": bool(ddg_failure_diagnostic.get("physics_ddg_ready")),
            "ddg_failure_diagnostic_proxy_is_physics": bool(ddg_failure_diagnostic.get("proxy_is_physics")),
            "ddg_proxy_not_physics_validation_success": bool(ddg_proxy_not_physics.get("success")),
            "ddg_proxy_not_physics_validation_failures": len(ddg_proxy_not_physics.get("failures") or []),
            "ddg_model_consumption_contract_proxy_rows": (ddg_model_consumption_contract.get("proxy_ddg_consumption") or {}).get("mutation_row_count"),
            "ddg_model_consumption_contract_physics_ready": bool((ddg_model_consumption_contract.get("physics_ddg_state") or {}).get("physics_ddg_ready")),
            "ddg_model_consumption_contract_executable_ready": bool((ddg_model_consumption_contract.get("physics_ddg_state") or {}).get("executable_ddg_backend_ready")),
            "ddg_model_consumption_contract_proxy_is_physics": bool((ddg_model_consumption_contract.get("physics_ddg_state") or {}).get("proxy_is_physics")),
            "ddg_model_consumption_contract_safe_for_model_claim": bool(ddg_model_consumption_contract.get("safe_for_model_claim")),
            "ddg_model_consumption_contract_validation_success": bool(ddg_model_consumption_contract_validation.get("success")),
            "ddg_model_consumption_contract_validation_failures": len(ddg_model_consumption_contract_validation.get("failures") or []),
            "ddg_local_runtime_discovery_candidate_rows": ddg_local_runtime_discovery.get("candidate_rows"),
            "ddg_local_runtime_discovery_executable_candidate_rows": ddg_local_runtime_discovery.get("executable_candidate_rows"),
            "ddg_local_runtime_discovery_executable_with_xbit_rows": ddg_local_runtime_discovery.get("executable_with_xbit_rows"),
            "ddg_local_runtime_discovery_python_module_available_rows": ddg_local_runtime_discovery.get("python_module_available_rows"),
            "ddg_local_runtime_discovery_ready_for_execution_rows": ddg_local_runtime_discovery.get("ready_for_ddg_execution_rows"),
            "ddg_backend_operator_packet_rows": ddg_backend_operator_packets.get("packet_rows"),
            "ddg_backend_operator_ready_for_execution_now_rows": ddg_backend_operator_packets.get("ready_for_execution_now_rows"),
            "ddg_backend_operator_completion_ready_rows": ddg_backend_operator_packets.get("completion_ready_rows"),
            "ddg_backend_operator_valid_rows": ddg_backend_operator_packet_validation.get("valid_status_rows"),
            "ddg_backend_operator_invalid_rows": ddg_backend_operator_packet_validation.get("invalid_status_rows"),
            "ddg_backend_operator_packets_all_valid": bool(ddg_backend_operator_packet_validation.get("all_operator_packets_valid")),
            "ddg_backend_runtime_receipt_rows": ddg_backend_runtime_receipts.get("receipt_rows"),
            "ddg_backend_runtime_approved_rows": ddg_backend_runtime_receipts.get("approved_runtime_rows"),
            "ddg_backend_runtime_ready_to_enable_backend_rows": ddg_backend_runtime_receipts.get("ready_to_enable_backend_rows"),
            "ddg_backend_runtime_ready_for_smoke_rows": ddg_backend_runtime_receipts.get("ready_for_ddg_smoke_rows"),
            "ddg_backend_runtime_physics_ddg_ready": bool(ddg_backend_runtime_receipts.get("physics_ddg_ready")),
            "ddg_backend_runtime_executable_ready": bool(ddg_backend_runtime_receipts.get("executable_ddg_backend_ready")),
            "ddg_physical_runtime_receipt_preflight_validation_success": bool(ddg_physical_runtime_receipt_preflight_validation.get("success")),
            "ddg_physical_runtime_receipt_preflight_validation_failures": len(ddg_physical_runtime_receipt_preflight_validation.get("failures") or []),
            "ddg_physical_runtime_receipt_preflight_physics_ready": bool(ddg_physical_runtime_receipt_preflight_validation.get("physics_ddg_ready")),
            "ddg_physical_smoke_harness_contract_rows": ddg_physical_smoke_harness.get("harness_contract_rows"),
            "ddg_physical_smoke_harness_implemented_rows": ddg_physical_smoke_harness.get("executor_contract_implemented_rows"),
            "ddg_physical_smoke_harness_can_execute_now_rows": ddg_physical_smoke_harness.get("can_execute_physical_smoke_now_rows"),
            "ddg_physical_smoke_harness_execute_attempted_rows": ddg_physical_smoke_harness.get("execute_attempted_rows"),
            "ddg_physical_smoke_harness_passed_rows": ddg_physical_smoke_harness.get("physical_smoke_passed_rows"),
            "ddg_physical_smoke_harness_validation_success": bool(ddg_physical_smoke_harness_validation.get("success")),
            "ddg_physical_smoke_harness_validation_failures": len(ddg_physical_smoke_harness_validation.get("failures") or []),
            "foldx_buildmodel_parser_contract_ready": bool(foldx_parser_contract.get("parser_contract_ready")),
            "foldx_buildmodel_parser_parsed_rows": foldx_parser_contract.get("parsed_rows"),
            "foldx_buildmodel_parser_runtime_ready": bool(foldx_parser_contract.get("foldx_runtime_ready")),
            "foldx_buildmodel_parser_validation_success": bool(foldx_parser_contract_validation.get("success")),
            "foldx_buildmodel_parser_validation_failures": len(foldx_parser_contract_validation.get("failures") or []),
            "foldx_physical_smoke_bootstrap_status": foldx_physical_smoke_bootstrap.get("status"),
            "foldx_physical_smoke_executable_found": bool(foldx_physical_smoke_bootstrap.get("foldx_executable_found")),
            "foldx_physical_smoke_runtime_receipt_ready": bool(foldx_physical_smoke_bootstrap.get("runtime_receipt_ready")),
            "foldx_physical_smoke_parser_contract_ready": bool(foldx_physical_smoke_bootstrap.get("parser_contract_ready")),
            "foldx_physical_smoke_ready_execution_plan_rows": foldx_physical_smoke_bootstrap.get("ready_execution_plan_rows"),
            "foldx_physical_smoke_passed": bool(foldx_physical_smoke_bootstrap.get("physical_smoke_passed")),
            "foldx_physical_smoke_validation_success": bool(foldx_physical_smoke_bootstrap_validation.get("success")),
            "foldx_physical_smoke_validation_failures": len(foldx_physical_smoke_bootstrap_validation.get("failures") or []),
            "stage25_foldx_execution_plan_blocker_valid": bool(foldx_execution_plan_blocker.get("receipt_valid")),
            "stage25_foldx_execution_plan_ready_rows": foldx_execution_plan_blocker.get("ready_rows"),
            "stage25_foldx_execution_plan_blocked_rows": foldx_execution_plan_blocker.get("blocked_rows"),
            "kwb_qc_fail_rate_calibration_batch_rows": qc_fail_rate_calibration.get("batch_rows"),
            "kwb_qc_fail_rate_calibration_raw_measurement_rows": qc_fail_rate_calibration.get("raw_measurement_rows_used"),
            "kwb_qc_fail_rate_calibration_training_import_written_rows": qc_fail_rate_calibration.get("training_import_written_rows"),
            "kwb_qc_fail_rate_calibration_validation_success": bool(qc_fail_rate_calibration_validation.get("success")),
            "kwb_qc_fail_rate_calibration_ready_for_model_claim": bool(qc_fail_rate_calibration_validation.get("ready_for_model_claim")),
            "kwb_plate_level_feedback_rows": plate_level_feedback_benchmark.get("plate_level_rows"),
            "kwb_plate_level_feedback_unique_plates": plate_level_feedback_benchmark.get("unique_plates"),
            "kwb_plate_level_feedback_training_import_written_rows": plate_level_feedback_benchmark.get("training_import_written_rows"),
            "kwb_plate_level_feedback_validation_success": bool(plate_level_feedback_benchmark_validation.get("success")),
            "kwb_plate_level_feedback_ready_for_model_claim": bool(plate_level_feedback_benchmark_validation.get("ready_for_model_claim")),
            "kwb_activity_risk_plate_feedback_rows": activity_risk_plate_feedback_benchmark.get("dataset_rows"),
            "kwb_activity_risk_plate_feedback_raw_measurement_rows": activity_risk_plate_feedback_benchmark.get("raw_measurement_rows_used"),
            "kwb_activity_risk_plate_feedback_training_import_written_rows": activity_risk_plate_feedback_benchmark.get("training_import_written_rows"),
            "kwb_activity_risk_plate_feedback_validation_success": bool(activity_risk_plate_feedback_benchmark_validation.get("success")),
            "kwb_activity_risk_plate_feedback_ready_for_model_claim": bool(activity_risk_plate_feedback_benchmark_validation.get("ready_for_model_claim")),
            "ddg_executable_probe_rosetta_found": bool(ddg_executable_probe.get("rosetta_executable_found")),
            "ddg_executable_probe_foldx_found": bool(ddg_executable_probe.get("foldx_executable_found")),
            "ddg_executable_probe_pyrosetta_available": bool(ddg_executable_probe.get("pyrosetta_module_available")),
            "ddg_executable_probe_executable_backend_ready": bool(ddg_executable_probe.get("executable_ddg_backend_ready")),
            "thermompnn_source_license_model_ready": bool(thermompnn_local_source.get("source_license_model_ready")),
            "thermompnn_runtime_dependency_ready": bool(thermompnn_local_source.get("runtime_dependency_ready")),
            "thermompnn_ready_for_local_inference": bool(thermompnn_local_source.get("ready_for_local_inference")),
            "thermompnn_missing_runtime_modules": thermompnn_local_source.get("missing_runtime_modules"),
            "thermompnn_venus15b_smoke_status": thermompnn_smoke.get("status"),
            "thermompnn_venus15b_smoke_mutation_rows": (thermompnn_smoke.get("outputs") or {}).get("mutation_rows"),
            "thermompnn_venus15b_proxy_ddg_artifact_ready": bool((thermompnn_smoke.get("outputs") or {}).get("ready_as_proxy_ddg_artifact")),
            "experiment_feedback_trainability_audited_rows": feedback_trainability.get("audited_rows"),
            "experiment_feedback_trainability_training_eligible_rows": feedback_trainability.get("training_eligible_rows"),
            "experiment_feedback_trainability_ready_for_feedback_intake": bool(feedback_trainability.get("ready_for_feedback_intake")),
            "experiment_feedback_trainability_safe_to_auto_promote": bool(feedback_trainability.get("safe_to_auto_promote")),
            "experiment_feedback_source_review_candidate_rows": feedback_source_decisions.get("candidate_rows"),
            "experiment_feedback_source_review_decision_rows": feedback_source_decisions.get("decision_rows"),
            "experiment_feedback_source_review_valid_rows": feedback_source_decisions.get("valid_rows"),
            "experiment_feedback_source_review_missing_rows": feedback_source_decisions.get("missing_source_review_rows"),
            "experiment_feedback_source_approved_for_extraction_rows": feedback_source_decisions.get("approved_for_feedback_extraction_rows"),
            "experiment_feedback_source_intake_candidate_rows": feedback_source_intake_candidates.get("source_intake_candidate_rows"),
            "experiment_feedback_source_ready_for_feedback_intake_rows": feedback_source_intake_candidates.get("ready_for_feedback_intake_rows"),
            "feedback_training_import_semantic_guard_success": bool(feedback_training_import_semantic_guard.get("success")),
            "feedback_training_import_semantic_guard_qualitative_feedback_eligible": feedback_training_import_semantic_guard.get("qualitative_feedback_eligible"),
            "feedback_training_import_semantic_guard_numeric_training_import_eligible": feedback_training_import_semantic_guard.get("numeric_training_import_eligible"),
            "feedback_training_import_semantic_guard_strict_supervised_rows": feedback_training_import_semantic_guard.get("strict_supervised_rows"),
            "feedback_training_import_semantic_guard_claim_eligible_rows": feedback_training_import_semantic_guard.get("claim_eligible_rows"),
            "feedback_training_import_semantic_guard_safe_for_training_import": bool(feedback_training_import_semantic_guard.get("safe_for_training_import")),
            "feedback_training_import_semantic_guard_safe_for_model_claim": bool(feedback_training_import_semantic_guard.get("safe_for_model_claim")),
            "feedback_training_import_semantic_guard_validation_success": bool(feedback_training_import_semantic_guard_validation.get("success")),
            "feedback_training_import_semantic_guard_validation_failures": len(feedback_training_import_semantic_guard_validation.get("failures") or []),
            "wet_lab_feedback_apply_duplicate_audit_success": bool(wet_lab_feedback_apply_duplicate_audit.get("success")),
            "wet_lab_feedback_apply_duplicate_audit_already_represented_rows": wet_lab_feedback_apply_duplicate_audit.get("already_represented_rows"),
            "wet_lab_feedback_apply_duplicate_audit_new_feedback_only_rows": wet_lab_feedback_apply_duplicate_audit.get("new_feedback_only_rows"),
            "wet_lab_feedback_apply_duplicate_audit_safe_to_append_rows": wet_lab_feedback_apply_duplicate_audit.get("safe_to_append_rows"),
            "wet_lab_feedback_apply_duplicate_audit_training_import_rows": wet_lab_feedback_apply_duplicate_audit.get("training_import_eligible_from_apply_plan_rows"),
            "wet_lab_feedback_apply_duplicate_audit_validation_success": bool(wet_lab_feedback_apply_duplicate_audit_validation.get("success")),
            "wet_lab_feedback_apply_duplicate_audit_validation_failures": len(wet_lab_feedback_apply_duplicate_audit_validation.get("failures") or []),
            "training_label_import_contract_training_import_eligible_sources": (training_label_import_contract.get("contract_totals") or {}).get("training_import_eligible_label_sources"),
            "training_label_import_contract_training_import_eligible_rows": (training_label_import_contract.get("contract_totals") or {}).get("training_import_eligible_rows"),
            "training_label_import_contract_counted_as_trainable_rows": (training_label_import_contract.get("contract_totals") or {}).get("counted_as_trainable_rows"),
            "training_label_import_contract_safe_for_training_import": bool(training_label_import_contract.get("safe_for_training_import")),
            "training_label_import_contract_safe_for_model_claim": bool(training_label_import_contract.get("safe_for_model_claim")),
            "training_label_import_contract_validation_success": bool(training_label_import_contract_validation.get("success")),
            "training_label_import_contract_validation_failures": len(training_label_import_contract_validation.get("failures") or []),
            "wet_lab_feedback_import_reconciliation_success": bool(wet_lab_feedback_import_reconciliation.get("success")),
            "wet_lab_feedback_import_reconciliation_wetlab_applied_rows": ((wet_lab_feedback_import_reconciliation.get("counts") or {}).get("wetlab_applied_rows")),
            "wet_lab_feedback_import_reconciliation_numeric_training_rows": ((wet_lab_feedback_import_reconciliation.get("counts") or {}).get("semantic_numeric_training_import_eligible_rows")),
            "wet_lab_feedback_import_reconciliation_safe_for_model_claim": bool(wet_lab_feedback_import_reconciliation.get("safe_for_model_claim")),
            "wet_lab_feedback_import_reconciliation_validation_success": bool(wet_lab_feedback_import_reconciliation_validation.get("success")),
            "wet_lab_feedback_import_reconciliation_validation_failures": len(wet_lab_feedback_import_reconciliation_validation.get("failures") or []),
            "parallel_hard_gate_workstreams_lane_count": parallel_hard_gate_workstreams.get("lane_count"),
            "parallel_hard_gate_workstreams_started_lane_count": parallel_hard_gate_workstreams.get("started_lane_count"),
            "parallel_hard_gate_workstreams_validation_success": bool(parallel_hard_gate_workstreams_validation.get("success")),
            "parallel_hard_gate_workstreams_validation_failures": len(parallel_hard_gate_workstreams_validation.get("failures") or []),
            "human_preflight_package_rows": human_preflight_package.get("package_rows"),
            "human_preflight_package_valid_rows": human_preflight_package_validation.get("valid_package_rows"),
            "human_preflight_package_formal_decisions_written": bool(human_preflight_package.get("formal_decisions_written")),
            "human_preflight_package_training_rows_imported": bool(human_preflight_package.get("training_rows_imported")),
            "human_preflight_package_validation_success": bool(human_preflight_package_validation.get("success")),
            "human_preflight_package_validation_failures": len(human_preflight_package_validation.get("error_counts") or {}),
            "parallel_hard_gate_execution_receipts_rows": parallel_hard_gate_execution_receipts.get("receipt_rows"),
            "parallel_hard_gate_execution_receipts_validation_passed_rows": parallel_hard_gate_execution_receipts.get("validation_passed_rows"),
            "parallel_hard_gate_execution_receipts_eligibility_changed_rows": parallel_hard_gate_execution_receipts.get("eligibility_changed_rows"),
            "parallel_hard_gate_execution_receipts_formal_decision_written_rows": parallel_hard_gate_execution_receipts.get("formal_decision_written_rows"),
            "parallel_hard_gate_execution_receipts_runtime_receipt_written_rows": parallel_hard_gate_execution_receipts.get("runtime_receipt_written_rows"),
            "parallel_hard_gate_execution_receipts_training_import_written_rows": parallel_hard_gate_execution_receipts.get("training_import_written_rows"),
            "parallel_hard_gate_execution_receipts_validation_success": bool(parallel_hard_gate_execution_receipts_validation.get("success")),
            "parallel_hard_gate_execution_receipts_validation_failures": len(parallel_hard_gate_execution_receipts_validation.get("failures") or []),
            "next_hard_gate_attack_wave_lane_rows": next_hard_gate_attack_wave.get("lane_rows"),
            "next_hard_gate_attack_wave_executed_blocked_rows": next_hard_gate_attack_wave.get("executed_blocked_rows"),
            "next_hard_gate_attack_wave_claimed_breakthrough_rows": next_hard_gate_attack_wave.get("claimed_breakthrough_rows"),
            "next_hard_gate_attack_wave_eligibility_changed_rows": next_hard_gate_attack_wave.get("eligibility_changed_rows"),
            "next_hard_gate_attack_wave_formal_decision_written_rows": next_hard_gate_attack_wave.get("formal_decision_written_rows"),
            "next_hard_gate_attack_wave_runtime_receipt_written_rows": next_hard_gate_attack_wave.get("runtime_receipt_written_rows"),
            "next_hard_gate_attack_wave_training_import_written_rows": next_hard_gate_attack_wave.get("training_import_written_rows"),
            "next_hard_gate_attack_wave_validation_success": bool(next_hard_gate_attack_wave_validation.get("success")),
            "next_hard_gate_attack_wave_validation_failures": len(next_hard_gate_attack_wave_validation.get("failures") or []),
            "five_head_training_execution_ready_heads": five_head_training_execution_contract.get("ready_head_count"),
            "five_head_training_execution_total_rows": five_head_training_execution_contract.get("total_head_training_rows"),
            "five_head_training_execution_import_eligible_rows": (five_head_training_execution_contract.get("training_label_import") or {}).get("training_import_eligible_rows"),
            "five_head_training_execution_allowed": bool(five_head_training_execution_contract.get("training_execution_allowed")),
            "five_head_training_execution_safe_for_model_claim": bool(five_head_training_execution_contract.get("safe_for_model_claim")),
            "five_head_training_execution_validation_success": bool(five_head_training_execution_contract_validation.get("success")),
            "five_head_training_execution_validation_failures": len(five_head_training_execution_contract_validation.get("failures") or []),
            "five_head_training_threshold_ready_head_count": five_head_training_threshold.get("ready_head_count"),
            "five_head_training_threshold_candidate_heads": five_head_training_threshold.get("candidate_heads"),
            "five_head_training_threshold_validation_success": bool(five_head_training_threshold_validation.get("success")),
            "five_head_training_threshold_validation_failures": len(five_head_training_threshold_validation.get("failures") or []),
            "five_head_training_sample_gap_queue_rows": five_head_training_sample_gap_queue.get("queue_rows"),
            "five_head_training_sample_gap_queue_missing_label_rows_total": five_head_training_sample_gap_queue.get("missing_label_rows_total"),
            "five_head_training_sample_gap_queue_missing_groups_total": five_head_training_sample_gap_queue.get("missing_groups_total"),
            "five_head_training_sample_gap_queue_missing_replicates_total": five_head_training_sample_gap_queue.get("missing_replicates_total"),
            "five_head_training_sample_gap_queue_training_import_written_rows": five_head_training_sample_gap_queue.get("training_import_written_rows"),
            "five_head_training_sample_gap_queue_validation_success": bool(five_head_training_sample_gap_queue_validation.get("success")),
            "five_head_training_sample_gap_queue_validation_failures": len(five_head_training_sample_gap_queue_validation.get("failures") or []),
            "proteingym_benchmark_scorecard_source_dataset_rows": proteingym_benchmark_scorecard.get("source_dataset_rows"),
            "proteingym_benchmark_scorecard_source_summary_rows": proteingym_benchmark_scorecard.get("source_summary_rows"),
            "proteingym_benchmark_scorecard_accepted_for_local_cache": bool(proteingym_benchmark_scorecard.get("accepted_for_local_benchmark_cache_intake")),
            "proteingym_benchmark_scorecard_license_verification_required": bool(proteingym_benchmark_scorecard.get("license_verification_required")),
            "proteingym_benchmark_scorecard_training_import_written_rows": proteingym_benchmark_scorecard.get("training_import_written_rows"),
            "flip2_amylase_benchmark_dataset_rows": flip2_amylase_benchmark.get("dataset_rows"),
            "flip2_amylase_benchmark_split_counts": flip2_amylase_benchmark.get("split_counts"),
            "flip2_amylase_benchmark_validation_success": bool(flip2_amylase_benchmark_validation.get("success")),
            "flip2_amylase_benchmark_training_import_written_rows": flip2_amylase_benchmark.get("training_import_written_rows"),
            "flip2_amylase_benchmark_ready_for_model_claim": bool(flip2_amylase_benchmark_validation.get("ready_for_model_claim")),
            "activity_risk_label_replicate_preflight_rows": activity_risk_label_replicate_preflight.get("preflight_rows"),
            "activity_risk_label_replicate_template_rows": activity_risk_label_replicate_preflight.get("decision_template_rows"),
            "activity_risk_label_replicate_formal_decision_rows": activity_risk_label_replicate_preflight.get("formal_decision_rows"),
            "activity_risk_label_rows_created": activity_risk_label_replicate_preflight.get("activity_risk_label_rows_created"),
            "activity_risk_replicate_rows_counted_for_training": activity_risk_label_replicate_preflight.get("replicate_rows_counted_for_training"),
            "activity_risk_label_replicate_validation_success": bool(activity_risk_label_replicate_preflight_validation.get("success")),
            "activity_risk_label_replicate_validation_failures": len(activity_risk_label_replicate_preflight_validation.get("failures") or []),
            "activity_risk_formal_label_decision_rows": activity_risk_formal_label_decision.get("formal_decision_rows"),
            "activity_risk_formal_label_rows_created": activity_risk_formal_label_decision.get("activity_risk_label_rows_created"),
            "activity_risk_formal_label_replicate_rows_counted": activity_risk_formal_label_decision.get("replicate_rows_counted_for_training"),
            "activity_risk_formal_label_validation_success": bool(activity_risk_formal_label_decision_validation.get("success")),
            "activity_risk_formal_label_validation_failures": len(activity_risk_formal_label_decision_validation.get("failures") or []),
            "activity_risk_training_import_written_rows": activity_risk_training_import_label.get("training_import_written_rows"),
            "activity_risk_training_import_label_rows": activity_risk_training_import_label.get("training_import_label_rows"),
            "activity_risk_training_import_validation_success": bool(activity_risk_training_import_label_validation.get("success")),
            "activity_risk_training_import_validation_failures": len(activity_risk_training_import_label_validation.get("failures") or []),
            "activity_risk_training_import_training_execution_allowed": bool(activity_risk_training_import_label.get("training_execution_allowed")),
            "activity_risk_training_import_safe_for_model_claim": bool(activity_risk_training_import_label.get("safe_for_model_claim")),
            "model_quality_hard_gate_contract_success": bool(model_quality_hard_gate_contract.get("success")),
            "model_quality_hard_gate_training_import_eligible_rows": model_quality_hard_gate_contract.get("training_import_eligible_rows"),
            "model_quality_hard_gate_wetlab_authorized_rows": model_quality_hard_gate_contract.get("wetlab_authorized_rows"),
            "model_quality_hard_gate_wetlab_import_rows": model_quality_hard_gate_contract.get("wetlab_import_rows"),
            "model_quality_hard_gate_physics_ddg_ready": bool(model_quality_hard_gate_contract.get("physics_ddg_ready")),
            "model_quality_hard_gate_benchmark_ready_for_model_claim": bool(model_quality_hard_gate_contract.get("benchmark_ready_for_model_claim")),
            "model_quality_hard_gate_feature_inputs_ready": model_quality_hard_gate_contract.get("feature_inputs_ready"),
            "model_quality_hard_gate_model_quality_ready": bool(model_quality_hard_gate_contract.get("model_quality_ready")),
            "model_quality_hard_gate_safe_for_model_claim": bool(model_quality_hard_gate_contract.get("safe_for_model_claim")),
            "model_quality_hard_gate_validation_success": bool(model_quality_hard_gate_contract_validation.get("success")),
            "model_quality_hard_gate_validation_failures": len(model_quality_hard_gate_contract_validation.get("failures") or []),
            "model_artifact_claim_guard_success": bool(model_artifact_claim_guard.get("success")),
            "model_artifact_claim_guard_artifacts": model_artifact_claim_guard.get("artifact_count"),
            "model_artifact_claim_guard_claimable_artifacts": model_artifact_claim_guard.get("claimable_model_artifact_count"),
            "model_artifact_claim_guard_trained_neural_weights": model_artifact_claim_guard.get("trained_neural_weight_artifact_count"),
            "model_artifact_claim_guard_production_artifacts": model_artifact_claim_guard.get("production_model_artifact_count"),
            "model_artifact_claim_guard_safe_for_model_claim": bool(model_artifact_claim_guard.get("safe_for_model_claim")),
            "model_artifact_claim_guard_validation_success": bool(model_artifact_claim_guard_validation.get("success")),
            "model_artifact_claim_guard_validation_failures": len(model_artifact_claim_guard_validation.get("failures") or []),
            "execution_receipt_artifact_freshness_success": bool(execution_receipt_artifact_freshness.get("success")),
            "execution_receipt_artifact_freshness_fresh_receipts": execution_receipt_artifact_freshness.get("fresh_receipts"),
            "execution_receipt_artifact_freshness_stale_receipts": execution_receipt_artifact_freshness.get("stale_receipts"),
            "execution_receipt_artifact_freshness_missing_artifacts": execution_receipt_artifact_freshness.get("missing_artifacts"),
            "feature_label_boundary_quarantine_success": bool(feature_label_boundary_quarantine.get("success")),
            "feature_label_boundary_quarantine_label_contaminated_artifacts": len(feature_label_boundary_quarantine.get("label_contaminated_artifacts") or []),
            "feature_label_boundary_quarantine_boundary_safe_artifacts": len(feature_label_boundary_quarantine.get("boundary_safe_artifacts") or []),
            "feature_label_boundary_quarantine_success_flag": bool(feature_label_boundary_quarantine.get("success")),
            "tool_lane_evidence_validation_success": bool(tool_lane_evidence_validation.get("success")),
            "tool_lane_evidence_total_lanes": (tool_lane_evidence.get("summary") or {}).get("total_lanes"),
            "tool_lane_evidence_ready_lanes": (tool_lane_evidence.get("summary") or {}).get("ready_lanes"),
            "tool_lane_evidence_blocked_lanes": (tool_lane_evidence.get("summary") or {}).get("blocked_lanes"),
            "tool_lane_evidence_proxy_lanes_blocked": tool_lane_evidence_validation.get("proxy_lanes_blocked"),
            "human_target_gap_validation_success": bool(human_target_gap_validation.get("success")),
            "human_target_gap_sections": len(human_target_gap.get("product_lines") or {}),
            "human_target_gap_status": (human_target_gap.get("gate_snapshot") or {}).get("bio_specialty_ready"),
            "human_target_source_runtime_validation_success": bool(human_target_source_runtime_validation.get("success")),
            "human_target_source_runtime_total_sources": (human_target_source_runtime.get("summary") or {}).get("total_sources"),
            "human_target_source_runtime_ready_sources": (human_target_source_runtime.get("summary") or {}).get("ready_sources"),
            "human_target_source_runtime_blocked_sources": (human_target_source_runtime.get("summary") or {}).get("blocked_sources"),
            "human_target_blocked_source_index_validation_success": bool(human_target_blocked_source_index_validation.get("success")),
            "human_target_blocked_source_split_count": len(human_target_blocked_source_index.get("source_manifest_index") or []),
            "human_target_source_unlock_checklist_validation_success": bool(human_target_source_unlock_checklist_validation.get("success")),
            "human_target_source_unlock_checklist_rows": human_target_source_unlock_checklist.get("checklist_rows"),
            "human_target_source_unlock_ready_rows": human_target_source_unlock_checklist.get("ready_to_unlock_rows"),
            "stage25_fulltext_intake_status": fulltext_intake.get("status"),
            "stage25_fulltext_intake_failure_count": fulltext_intake.get("failure_count"),
            "stage25_fulltext_source_locator_review_status": fulltext_queue.get("status"),
            "stage25_fulltext_source_locator_review_ready_count": fulltext_queue.get("review_ready_count"),
            "stage25_fulltext_evidence_draft_status": fulltext_draft.get("status"),
            "stage25_fulltext_evidence_draft_pdf_count": fulltext_draft.get("pdf_count"),
            "stage25_reviewer_package_valid": bool(reviewer_package.get("package_valid")),
            "stage25_reviewer_package_paper_pdf_count": reviewer_package.get("paper_pdf_count"),
            "local_release_guard_coverage_success": bool(local_release_guard_coverage.get("success")),
            "local_release_guard_coverage_count": local_release_guard_coverage.get("guard_coverage_count"),
            "local_release_guard_coverage_failures": len(local_release_guard_coverage.get("failures") or []),
            "human_target_projection_gap_report_valid": bool(human_target_projection_checks.get("gap_report_matches_current_builder_projection")),
            "human_target_projection_runtime_manifest_valid": bool(human_target_projection_checks.get("runtime_manifest_matches_current_builder_projection")),
            "human_target_projection_runtime_receipts_valid": bool(human_target_projection_checks.get("runtime_receipts_match_current_builder_projection")),
            "human_target_projection_blocked_source_index_valid": bool(human_target_projection_checks.get("blocked_source_index_matches_current_builder_projection")),
            "human_target_projection_blocked_split_manifests_valid": bool(human_target_projection_checks.get("blocked_split_manifests_match_current_builder_projection")),
            "human_target_projection_unlock_checklist_valid": bool(human_target_projection_checks.get("unlock_checklist_matches_current_builder_projection")),
            "human_target_projection_unlock_report_valid": bool(human_target_projection_checks.get("unlock_report_matches_current_builder_projection")),
            "venus15b_asset_source_files_scanned": venus15b_asset_audit.get("source_files_scanned"),
            "venus15b_asset_qualitative_feedback_rows": venus15b_asset_audit.get("qualitative_feedback_rows"),
            "venus15b_asset_numeric_training_eligible_rows": venus15b_asset_audit.get("numeric_training_eligible_rows"),
            "venus15b_asset_plate_training_eligible_rows": venus15b_asset_audit.get("plate_training_eligible_rows"),
            "venus15b_asset_tabular_assay_file_count": venus15b_asset_audit.get("tabular_assay_file_count"),
            "venus15b_feedback_rows_after": venus15b_feedback.get("feedback_rows_after"),
            "venus15b_feedback_numbering_verified": bool((venus15b_feedback.get("evidence") or {}).get("numbering_verified")),
            "venus15b_feedback_training_eligible_under_current_validator": bool((venus15b_feedback.get("evidence") or {}).get("training_eligible_under_current_validator")),
            "venus15b_strict_candidate_variant_rows": venus15b_strict_candidate.get("candidate_variant_rows"),
            "venus15b_strict_candidate_sequence_pdb_exact_match": venus15b_strict_candidate.get("sequence_pdb_exact_match"),
            "venus15b_strict_holdout_rows_written": venus15b_strict_candidate.get("strict_holdout_rows_written"),
            "substrate_identity_candidate_rows": substrate_identity_candidates.get("candidate_rows"),
            "substrate_identity_candidate_reviewed_rows": substrate_identity_candidates.get("reviewed_rows"),
            "substrate_identity_candidate_validation_valid_rows": substrate_identity_validation.get("valid_rows"),
            "wet_lab_mutant_library_file_count": wet_lab_mutant_library_assets.get("file_count"),
            "wet_lab_mutant_library_csv_file_count": wet_lab_mutant_library_assets.get("csv_file_count"),
            "wet_lab_mutant_library_projects": wet_lab_mutant_library_assets.get("project_ids"),
            "wet_lab_mutant_library_feedback_candidate_rows": wet_lab_mutant_library_feedback.get("candidate_rows"),
            "wet_lab_mutant_library_numeric_training_candidate_rows": wet_lab_mutant_library_feedback.get("numeric_training_candidate_rows"),
            "wet_lab_mutant_library_ready_for_feedback_intake_rows": wet_lab_mutant_library_feedback.get("ready_for_feedback_intake_rows"),
            "wet_lab_mutant_library_claim_eligible_rows_now": wet_lab_mutant_library_feedback.get("claim_eligible_rows_now"),
            "wet_lab_mutant_library_parseable_mutation_rows": wet_lab_mutant_library_feedback.get("parseable_mutation_rows"),
            "wet_lab_mutant_library_feedback_qc_matrix_rows": wet_lab_mutant_library_feedback_qc.get("qc_matrix_rows"),
            "wet_lab_mutant_library_feedback_qc_conflicting_property_rows": wet_lab_mutant_library_feedback_qc.get("conflicting_property_rows"),
            "wet_lab_mutant_library_feedback_qc_critical_tradeoff_rows": wet_lab_mutant_library_feedback_qc.get("critical_tradeoff_review_rows"),
            "wet_lab_mutant_library_sequence_evidence_rows": wet_lab_mutant_library_sequence_evidence.get("sequence_evidence_rows"),
            "wet_lab_mutant_library_sequence_evidence_accepted_rows": wet_lab_mutant_library_sequence_evidence.get("accepted_sequence_evidence_rows"),
            "wet_lab_mutant_library_sequence_evidence_accepted_projects": wet_lab_mutant_library_sequence_evidence.get("accepted_projects"),
            "wet_lab_mutant_library_sequence_evidence_ready_to_update_numbering_flags": bool(wet_lab_mutant_library_sequence_evidence.get("ready_to_update_numbering_flags")),
            "wet_lab_mutant_library_16b_sequence_evidence_accepted_rows": wet_lab_mutant_library_sequence_evidence.get("project_16B_accepted_sequence_evidence_rows"),
            "wet_lab_mutant_library_4g_sequence_evidence_accepted_rows": wet_lab_mutant_library_sequence_evidence.get("project_4G_accepted_sequence_evidence_rows"),
            "wet_lab_mutant_library_project_sequence_intake_rows": wet_lab_mutant_library_sequence_intake.get("sequence_intake_rows"),
            "wet_lab_mutant_library_project_sequence_approved_rows": wet_lab_mutant_library_sequence_intake.get("approved_sequence_rows"),
            "wet_lab_mutant_library_project_sequence_approved_projects": wet_lab_mutant_library_sequence_intake.get("approved_projects"),
            "wet_lab_mutant_library_16b_ready_for_numbering_audit": bool(wet_lab_mutant_library_sequence_intake.get("project_16B_ready_for_numbering_audit")),
            "wet_lab_mutant_library_4g_ready_for_numbering_audit": bool(wet_lab_mutant_library_sequence_intake.get("project_4G_ready_for_numbering_audit")),
            "wet_lab_mutant_library_numbering_audit_rows": wet_lab_mutant_library_numbering_audit.get("audit_rows"),
            "wet_lab_mutant_library_numbering_verified_candidate_rows": wet_lab_mutant_library_numbering_audit.get("numbering_verified_candidate_rows"),
            "wet_lab_mutant_library_numbering_ready_to_update_candidate_flags": bool(wet_lab_mutant_library_numbering_audit.get("ready_to_update_candidate_numbering_flags")),
            "wet_lab_mutant_library_authorization_rows": wet_lab_mutant_library_authorization.get("authorization_rows"),
            "wet_lab_mutant_library_authorized_candidate_rows": wet_lab_mutant_library_authorization.get("authorized_candidate_rows"),
            "wet_lab_mutant_library_missing_candidate_authorization_rows": wet_lab_mutant_library_authorization.get("missing_candidate_authorization_rows"),
            "wet_lab_mutant_library_authorization_ready_for_feedback_intake_rows": wet_lab_mutant_library_authorization.get("ready_for_feedback_intake_rows"),
            "wet_lab_mutant_library_authorization_worklist_rows": wet_lab_mutant_library_authorization_worklist.get("authorization_worklist_rows"),
            "wet_lab_mutant_library_authorization_worklist_authorized_rows": wet_lab_mutant_library_authorization_worklist.get("authorized_rows"),
            "wet_lab_mutant_library_authorization_worklist_critical_tradeoff_rows": wet_lab_mutant_library_authorization_worklist.get("critical_tradeoff_worklist_rows"),
            "wet_lab_mutant_library_authorization_worklist_valid_rows": wet_lab_mutant_library_authorization_worklist_validation.get("valid_worklist_rows"),
            "wet_lab_mutant_library_authorization_worklist_invalid_rows": wet_lab_mutant_library_authorization_worklist_validation.get("invalid_worklist_rows"),
            "wet_lab_mutant_library_authorization_worklist_all_numeric_candidates_covered": bool(wet_lab_mutant_library_authorization_worklist_validation.get("all_numeric_candidates_covered")),
            "wet_lab_mutant_library_authorization_dashboard_variant_rows": wet_lab_mutant_library_authorization_dashboard.get("variant_review_rows"),
            "wet_lab_mutant_library_authorization_dashboard_requires_human_input_rows": wet_lab_mutant_library_authorization_dashboard.get("requires_human_input_rows"),
            "wet_lab_mutant_library_authorization_dashboard_valid_rows": wet_lab_mutant_library_authorization_dashboard_validation.get("valid_dashboard_rows"),
            "wet_lab_mutant_library_authorization_dashboard_invalid_rows": wet_lab_mutant_library_authorization_dashboard_validation.get("invalid_dashboard_rows"),
            "wet_lab_mutant_library_authorization_dashboard_all_rows_valid": bool(wet_lab_mutant_library_authorization_dashboard_validation.get("all_dashboard_rows_valid")),
            "wet_lab_mutant_library_authorization_gap_rows": wet_lab_mutant_library_authorization_gap_matrix.get("authorization_gap_rows"),
            "wet_lab_mutant_library_authorization_gap_blocked_rows": wet_lab_mutant_library_authorization_gap_matrix.get("blocked_missing_human_authorization_rows"),
            "wet_lab_mutant_library_authorization_gap_critical_tradeoff_rows": wet_lab_mutant_library_authorization_gap_matrix.get("critical_tradeoff_gap_rows"),
            "wet_lab_mutant_library_authorization_gap_valid_rows": wet_lab_mutant_library_authorization_gap_matrix_validation.get("valid_gap_rows"),
            "wet_lab_mutant_library_authorization_gap_invalid_rows": wet_lab_mutant_library_authorization_gap_matrix_validation.get("invalid_gap_rows"),
            "wet_lab_mutant_library_authorization_gap_all_rows_valid": bool(wet_lab_mutant_library_authorization_gap_matrix_validation.get("all_gap_rows_valid")),
            "wet_lab_feedback_authorization_contract_candidate_rows": wet_lab_feedback_authorization_contract.get("candidate_rows"),
            "wet_lab_feedback_authorization_contract_numeric_training_candidate_rows": wet_lab_feedback_authorization_contract.get("numeric_training_candidate_rows"),
            "wet_lab_feedback_authorization_contract_authorized_rows": wet_lab_feedback_authorization_contract.get("authorized_rows"),
            "wet_lab_feedback_authorization_contract_preflight_rows": wet_lab_feedback_authorization_contract.get("preflight_rows"),
            "wet_lab_feedback_authorization_contract_ready_for_training_import_rows": wet_lab_feedback_authorization_contract.get("ready_for_training_import_rows"),
            "wet_lab_feedback_authorization_contract_safe_for_model_claim": bool((wet_lab_feedback_authorization_contract.get("safety_flags") or {}).get("safe_for_model_claim")),
            "wet_lab_feedback_authorization_contract_validation_success": bool(wet_lab_feedback_authorization_contract_validation.get("success")),
            "wet_lab_feedback_authorization_contract_validation_failures": len(wet_lab_feedback_authorization_contract_validation.get("failures") or []),
            "wet_lab_mutant_library_authorization_operator_checklist_rows": wet_lab_mutant_library_authorization_operator_checklist.get("operator_checklist_rows"),
            "wet_lab_mutant_library_authorization_operator_checklist_open_blocked_rows": wet_lab_mutant_library_authorization_operator_checklist.get("open_blocked_checklist_rows"),
            "wet_lab_mutant_library_authorization_operator_checklist_tradeoff_rows": wet_lab_mutant_library_authorization_operator_checklist.get("tradeoff_review_required_rows"),
            "wet_lab_mutant_library_authorization_operator_checklist_valid_rows": wet_lab_mutant_library_authorization_operator_checklist_validation.get("valid_checklist_rows"),
            "wet_lab_mutant_library_authorization_operator_checklist_invalid_rows": wet_lab_mutant_library_authorization_operator_checklist_validation.get("invalid_checklist_rows"),
            "wet_lab_mutant_library_authorization_operator_checklist_all_rows_valid": bool(wet_lab_mutant_library_authorization_operator_checklist_validation.get("all_checklist_rows_valid")),
            "wet_lab_mutant_library_authorization_operator_receipt_rows": wet_lab_mutant_library_authorization_operator_receipts.get("operator_receipt_rows"),
            "wet_lab_mutant_library_authorization_operator_receipt_open_blocked_rows": wet_lab_mutant_library_authorization_operator_receipts.get("open_blocked_receipt_rows"),
            "wet_lab_mutant_library_authorization_operator_receipt_decision_input_rows": wet_lab_mutant_library_authorization_operator_receipts.get("decision_input_rows"),
            "wet_lab_mutant_library_authorization_operator_receipt_valid_rows": wet_lab_mutant_library_authorization_operator_receipt_validation.get("valid_receipt_rows"),
            "wet_lab_mutant_library_authorization_operator_receipt_invalid_rows": wet_lab_mutant_library_authorization_operator_receipt_validation.get("invalid_receipt_rows"),
            "wet_lab_mutant_library_authorization_operator_receipt_all_rows_valid": bool(wet_lab_mutant_library_authorization_operator_receipt_validation.get("all_receipt_rows_valid")),
            "wet_lab_mutant_library_authorization_execution_queue_rows": wet_lab_mutant_library_authorization_execution_queue.get("execution_queue_rows"),
            "wet_lab_mutant_library_authorization_execution_queue_open_blocked_rows": wet_lab_mutant_library_authorization_execution_queue.get("open_blocked_queue_rows"),
            "wet_lab_mutant_library_authorization_execution_queue_review_order": wet_lab_mutant_library_authorization_execution_queue.get("review_order"),
            "wet_lab_mutant_library_authorization_execution_queue_valid_rows": wet_lab_mutant_library_authorization_execution_queue_validation.get("valid_queue_rows"),
            "wet_lab_mutant_library_authorization_execution_queue_invalid_rows": wet_lab_mutant_library_authorization_execution_queue_validation.get("invalid_queue_rows"),
            "wet_lab_mutant_library_authorization_execution_queue_all_rows_valid": bool(wet_lab_mutant_library_authorization_execution_queue_validation.get("all_queue_rows_valid")),
            "wet_lab_mutant_library_authorization_execution_queue_operator_packet_rows": wet_lab_mutant_library_authorization_execution_queue_operator_packets.get("operator_packet_rows"),
            "wet_lab_mutant_library_authorization_execution_queue_operator_packet_open_blocked_rows": wet_lab_mutant_library_authorization_execution_queue_operator_packets.get("open_blocked_packet_rows"),
            "wet_lab_mutant_library_authorization_execution_queue_operator_packet_review_order": wet_lab_mutant_library_authorization_execution_queue_operator_packets.get("review_order"),
            "wet_lab_mutant_library_authorization_execution_queue_operator_packet_valid_rows": wet_lab_mutant_library_authorization_execution_queue_operator_packet_validation.get("valid_operator_packet_rows"),
            "wet_lab_mutant_library_authorization_execution_queue_operator_packet_invalid_rows": wet_lab_mutant_library_authorization_execution_queue_operator_packet_validation.get("invalid_operator_packet_rows"),
            "wet_lab_mutant_library_authorization_execution_queue_operator_packets_all_valid": bool(wet_lab_mutant_library_authorization_execution_queue_operator_packet_validation.get("all_operator_packets_valid")),
            "wet_lab_mutant_library_authorization_execution_queue_operator_packet_receipt_rows": wet_lab_mutant_library_authorization_execution_queue_operator_packet_receipts.get("operator_packet_receipt_rows"),
            "wet_lab_mutant_library_authorization_execution_queue_operator_packet_receipt_open_blocked_rows": wet_lab_mutant_library_authorization_execution_queue_operator_packet_receipts.get("open_blocked_packet_receipt_rows"),
            "wet_lab_mutant_library_authorization_execution_queue_operator_packet_receipt_decision_input_rows": wet_lab_mutant_library_authorization_execution_queue_operator_packet_receipts.get("decision_input_rows"),
            "wet_lab_mutant_library_authorization_execution_queue_operator_packet_receipt_valid_rows": wet_lab_mutant_library_authorization_execution_queue_operator_packet_receipt_validation.get("valid_operator_packet_receipt_rows"),
            "wet_lab_mutant_library_authorization_execution_queue_operator_packet_receipt_invalid_rows": wet_lab_mutant_library_authorization_execution_queue_operator_packet_receipt_validation.get("invalid_operator_packet_receipt_rows"),
            "wet_lab_mutant_library_authorization_execution_queue_operator_packet_receipts_all_valid": bool(wet_lab_mutant_library_authorization_execution_queue_operator_packet_receipt_validation.get("all_operator_packet_receipts_valid")),
            "wet_lab_mutant_library_authorization_closeout_board_rows": wet_lab_mutant_library_authorization_closeout_board.get("closeout_board_rows"),
            "wet_lab_mutant_library_authorization_closeout_board_missing_decision_rows": wet_lab_mutant_library_authorization_closeout_board.get("missing_decision_rows"),
            "wet_lab_mutant_library_authorization_closeout_board_open_blocked_rows": wet_lab_mutant_library_authorization_closeout_board.get("open_blocked_closeout_rows"),
            "wet_lab_mutant_library_authorization_closeout_board_valid_rows": wet_lab_mutant_library_authorization_closeout_board_validation.get("valid_closeout_board_rows"),
            "wet_lab_mutant_library_authorization_closeout_board_invalid_rows": wet_lab_mutant_library_authorization_closeout_board_validation.get("invalid_closeout_board_rows"),
            "wet_lab_mutant_library_authorization_closeout_board_all_valid": bool(wet_lab_mutant_library_authorization_closeout_board_validation.get("all_closeout_rows_valid")),
            "wet_lab_mutant_library_authorization_closeout_operator_packet_rows": wet_lab_mutant_library_authorization_closeout_operator_packets.get("closeout_operator_packet_rows"),
            "wet_lab_mutant_library_authorization_closeout_operator_packet_open_blocked_rows": wet_lab_mutant_library_authorization_closeout_operator_packets.get("open_blocked_packet_rows"),
            "wet_lab_mutant_library_authorization_closeout_operator_packet_review_order": wet_lab_mutant_library_authorization_closeout_operator_packets.get("review_order"),
            "wet_lab_mutant_library_authorization_closeout_operator_packet_valid_rows": wet_lab_mutant_library_authorization_closeout_operator_packet_validation.get("valid_closeout_operator_packet_rows"),
            "wet_lab_mutant_library_authorization_closeout_operator_packet_invalid_rows": wet_lab_mutant_library_authorization_closeout_operator_packet_validation.get("invalid_closeout_operator_packet_rows"),
            "wet_lab_mutant_library_authorization_closeout_operator_packets_all_valid": bool(wet_lab_mutant_library_authorization_closeout_operator_packet_validation.get("all_closeout_operator_packets_valid")),
            "numbering_review_briefing_rows": len(numbering_review_briefing.get("briefing_rows") or []),
            "numbering_review_briefing_valid_rows": numbering_review_briefing_validation.get("valid_rows"),
            "numbering_review_briefing_invalid_rows": numbering_review_briefing_validation.get("invalid_rows"),
            "numbering_review_briefing_status_rows": numbering_review_briefing_status.get("briefing_rows"),
            "numbering_review_briefing_status_open_blocked_rows": numbering_review_briefing_status.get("open_blocked_briefing_rows"),
            "numbering_review_briefing_status_decision_rows_present": numbering_review_briefing_status.get("decision_rows_present_for_briefing"),
            "numbering_review_briefing_status_valid_rows": numbering_review_briefing_status_validation.get("valid_status_rows"),
            "numbering_review_briefing_status_invalid_rows": numbering_review_briefing_status_validation.get("invalid_status_rows"),
            "numbering_review_briefing_status_all_valid": bool(numbering_review_briefing_status_validation.get("all_status_rows_valid")),
            "numbering_deep_audit_stability_records_checked": numbering_deep_audit.get("stability_records_checked"),
            "numbering_deep_audit_generated_source_rows": numbering_deep_audit.get("generated_source_fingerprint_rows"),
            "numbering_deep_audit_fixture_source_rows": numbering_deep_audit.get("fixture_source_rows"),
            "numbering_deep_audit_wt_mismatch_rows": numbering_deep_audit.get("current_uniprot_wt_mismatch_rows"),
            "numbering_deep_audit_ddg_dtm_conflict_rows": numbering_deep_audit.get("ddg_dtm_direction_conflict_rows"),
            "numbering_deep_audit_recommended_reject_rows": numbering_deep_audit.get("recommended_reject_label_rows"),
            "numbering_deep_audit_safe_to_map_any_record": bool(numbering_deep_audit.get("safe_to_map_any_record")),
            "numbering_deep_audit_hard_gate_status": numbering_deep_audit.get("hard_gate_status"),
            "numbering_semantic_conflict_rows": numbering_semantic_conflict.get("semantic_conflict_rows"),
            "numbering_semantic_conflict_open_rows": numbering_semantic_conflict.get("open_conflict_rows"),
            "numbering_semantic_conflict_safe_for_model_claim": bool(numbering_semantic_conflict.get("safe_for_model_claim")),
            "numbering_operator_queue_rows": numbering_operator_queue.get("queue_rows"),
            "numbering_operator_queue_open_rows": numbering_operator_queue.get("open_numbering_rows"),
            "numbering_operator_queue_conflict_rows": numbering_operator_queue.get("semantic_conflict_rows"),
            "numbering_operator_queue_reject_recommendation_rows": numbering_operator_queue.get("deep_audit_reject_recommendation_rows"),
            "wet_lab_mutant_library_preflight_rows": wet_lab_mutant_library_preflight.get("preflight_rows"),
            "wet_lab_mutant_library_preflight_ready_for_feedback_intake_rows": wet_lab_mutant_library_preflight.get("ready_for_feedback_intake_rows"),
            "wet_lab_mutant_library_feedback_apply_plan_rows": wet_lab_mutant_library_apply_plan.get("apply_plan_rows"),
            "wet_lab_mutant_library_feedback_apply_ready_if_authorized_rows": wet_lab_mutant_library_apply_plan.get("would_be_apply_ready_if_user_explicitly_authorizes_rows"),
            "wet_lab_mutant_library_feedback_applied_rows": wet_lab_mutant_library_apply_plan.get("applied_rows"),
            "wet_lab_mutant_library_sequence_request_packet_rows": wet_lab_mutant_library_operator_packets.get("sequence_request_packet_rows"),
            "wet_lab_mutant_library_feedback_review_packet_rows": wet_lab_mutant_library_operator_packets.get("feedback_review_packet_rows"),
            "wet_lab_mutant_library_unlock_action_rows": wet_lab_mutant_library_operator_packets.get("unlock_action_rows"),
            "wet_lab_mutant_library_operator_packet_valid_rows": wet_lab_mutant_library_operator_packet_validation.get("valid_status_rows"),
            "wet_lab_mutant_library_operator_packet_invalid_rows": wet_lab_mutant_library_operator_packet_validation.get("invalid_status_rows"),
            "wet_lab_mutant_library_operator_packets_all_valid": bool(wet_lab_mutant_library_operator_packet_validation.get("all_operator_packets_valid")),
            "wet_lab_mutant_library_operator_packet_completion_ready_rows": wet_lab_mutant_library_operator_packet_validation.get("completion_ready_rows"),
            "wet_lab_mutant_library_unlock_status_gate_rows": wet_lab_mutant_library_unlock_status.get("gate_rows"),
            "wet_lab_mutant_library_unlock_status_ready_to_verify_gates": wet_lab_mutant_library_unlock_status.get("ready_to_verify_gates"),
            "wet_lab_mutant_library_unlock_status_blocked_gates": wet_lab_mutant_library_unlock_status.get("blocked_gates"),
            "wet_lab_mutant_library_unlock_status_hard_blockers": wet_lab_mutant_library_unlock_status.get("hard_blockers"),
            "strict_msa_site_feature_rows": strict_msa_features.get("feature_rows"),
            "strict_msa_site_feature_missing_rows": strict_msa_features.get("missing_rows"),
            "strict_msa_site_feature_cache_validation_ready": bool(strict_msa_features.get("cache_validation_ready")),
            "strict_msa_baseline_validation_accuracy": ((msa_baseline.get("splits") or {}).get("validation") or {}).get("accuracy"),
            "strict_msa_baseline_test_accuracy": ((msa_baseline.get("splits") or {}).get("test") or {}).get("accuracy"),
            "label_provenance_strict_rows": label_provenance.get("strict_rows"),
            "label_provenance_claim_eligible_rows": label_provenance.get("claim_eligible_rows"),
            "label_provenance_synthetic_or_unreceipted_rows": label_provenance.get("synthetic_or_unreceipted_rows"),
            "label_provenance_hard_gate_status": label_provenance.get("hard_gate_status"),
            "domain_multi_occurrence_feature_rows": domain_multi_occurrence.get("feature_rows"),
            "domain_multi_occurrence_invalid_rows": domain_multi_occurrence.get("invalid_rows"),
            "domain_multi_occurrence_ready_for_feature_use": bool(domain_multi_occurrence.get("ready_for_feature_use")),
            "domain_interpro_raw_unresolved_rows": domain_interpro_packets.get("raw_unresolved_rows"),
            "domain_interpro_feature_use_unresolved_rows": domain_interpro_packets.get("unresolved_rows"),
            "domain_interpro_sidecar_resolved_rows": domain_interpro_packets.get("multi_occurrence_sidecar_resolved_rows"),
        },
        "sbom_summary": {
            "format": "local_manifest_scaffold",
            "signed": False,
            "artifact_checksums_present": sum(1 for artifact in artifacts if artifact.get("sha256")),
        },
        "blocked_capabilities": blocked_capabilities,
        "claim_readiness_matrix": "reports/claim_readiness_matrix.json",
        "claim_readiness_policy_anchor_validation_report": "reports/claim_readiness_policy_anchor_validation_report.json",
        "claim_readiness_policy_anchor_regression_report": "reports/claim_readiness_policy_anchor_regression_report.json",
        "claim_promotion_decisions": "datasets/governance/claim_promotion_decisions.jsonl",
        "claim_promotion_decisions_template": "datasets/governance/claim_promotion_decisions.template.jsonl",
        "claim_promotion_decision_validation_report": "reports/claim_promotion_decision_validation_report.json",
        "claim_readiness_matrix_fail_closed_policy_validation_report": "reports/claim_readiness_matrix_fail_closed_policy_validation_report.json",
        "claim_readiness_matrix_fail_closed_policy_current_validation_report": "reports/claim_readiness_matrix_fail_closed_policy_current_validation_report.json",
        "claim_readiness_matrix_fail_closed_policy_current_regression_report": "reports/claim_readiness_matrix_fail_closed_policy_current_regression_report.json",
        "human_decision_backlog": "reports/human_decision_backlog_report.json",
        "human_decision_backlog_fail_closed_consistency_validation_report": "reports/human_decision_backlog_fail_closed_consistency_validation_report.json",
        "p476_human_decision_backlog_gap_audit": "datasets/governance/p476_human_decision_backlog_gap_audit.jsonl",
        "p476_human_decision_backlog_gap_audit_report": "reports/p476_human_decision_backlog_gap_audit_report.json",
        "p476_human_decision_backlog_gap_audit_validation_report": "reports/p476_human_decision_backlog_gap_audit_validation_report.json",
        "p477_operator_review_action_gap_audit": "datasets/governance/p477_operator_review_action_gap_audit.jsonl",
        "p477_operator_review_action_gap_audit_report": "reports/p477_operator_review_action_gap_audit_report.json",
        "p477_operator_review_action_gap_audit_validation_report": "reports/p477_operator_review_action_gap_audit_validation_report.json",
        "p478_governance_review_bundle_gap_audit": "datasets/governance/p478_governance_review_bundle_gap_audit.jsonl",
        "p478_governance_review_bundle_gap_audit_report": "reports/p478_governance_review_bundle_gap_audit_report.json",
        "p478_governance_review_bundle_gap_audit_validation_report": "reports/p478_governance_review_bundle_gap_audit_validation_report.json",
        "p479_customer_delivery_readiness_gap_audit": "datasets/governance/p479_customer_delivery_readiness_gap_audit.jsonl",
        "p479_customer_delivery_readiness_gap_audit_report": "reports/p479_customer_delivery_readiness_gap_audit_report.json",
        "p479_customer_delivery_readiness_gap_audit_validation_report": "reports/p479_customer_delivery_readiness_gap_audit_validation_report.json",
        "p480_claim_readiness_blocker_gap_audit": "datasets/governance/p480_claim_readiness_blocker_gap_audit.jsonl",
        "p480_claim_readiness_blocker_gap_audit_report": "reports/p480_claim_readiness_blocker_gap_audit_report.json",
        "p480_claim_readiness_blocker_gap_audit_validation_report": "reports/p480_claim_readiness_blocker_gap_audit_validation_report.json",
        "p481_local_release_blocked_capability_gap_audit": "datasets/governance/p481_local_release_blocked_capability_gap_audit.jsonl",
        "p481_local_release_blocked_capability_gap_audit_report": "reports/p481_local_release_blocked_capability_gap_audit_report.json",
        "p481_local_release_blocked_capability_gap_audit_validation_report": "reports/p481_local_release_blocked_capability_gap_audit_validation_report.json",
        "p482_master_readiness_stream_gap_audit": "datasets/governance/p482_master_readiness_stream_gap_audit.jsonl",
        "p482_master_readiness_stream_gap_audit_report": "reports/p482_master_readiness_stream_gap_audit_report.json",
        "p482_master_readiness_stream_gap_audit_validation_report": "reports/p482_master_readiness_stream_gap_audit_validation_report.json",
        "p483_next_unlock_execution_gap_audit": "datasets/governance/p483_next_unlock_execution_gap_audit.jsonl",
        "p483_next_unlock_execution_gap_audit_report": "reports/p483_next_unlock_execution_gap_audit_report.json",
        "p483_next_unlock_execution_gap_audit_validation_report": "reports/p483_next_unlock_execution_gap_audit_validation_report.json",
        "p484_next_unlock_operator_navigation_gap_audit": "datasets/governance/p484_next_unlock_operator_navigation_gap_audit.jsonl",
        "p484_next_unlock_operator_navigation_gap_audit_report": "reports/p484_next_unlock_operator_navigation_gap_audit_report.json",
        "p484_next_unlock_operator_navigation_gap_audit_validation_report": "reports/p484_next_unlock_operator_navigation_gap_audit_validation_report.json",
        "p485_next_unlock_blocker_matrix_gap_audit": "datasets/governance/p485_next_unlock_blocker_matrix_gap_audit.jsonl",
        "p485_next_unlock_blocker_matrix_gap_audit_report": "reports/p485_next_unlock_blocker_matrix_gap_audit_report.json",
        "p485_next_unlock_blocker_matrix_gap_audit_validation_report": "reports/p485_next_unlock_blocker_matrix_gap_audit_validation_report.json",
        "p486_next_unlock_remediation_queue_gap_audit": "datasets/governance/p486_next_unlock_remediation_queue_gap_audit.jsonl",
        "p486_next_unlock_remediation_queue_gap_audit_report": "reports/p486_next_unlock_remediation_queue_gap_audit_report.json",
        "p486_next_unlock_remediation_queue_gap_audit_validation_report": "reports/p486_next_unlock_remediation_queue_gap_audit_validation_report.json",
        "p487_next_unlock_multi_agent_launch_gap_audit": "datasets/governance/p487_next_unlock_multi_agent_launch_gap_audit.jsonl",
        "p487_next_unlock_multi_agent_launch_gap_audit_report": "reports/p487_next_unlock_multi_agent_launch_gap_audit_report.json",
        "p487_next_unlock_multi_agent_launch_gap_audit_validation_report": "reports/p487_next_unlock_multi_agent_launch_gap_audit_validation_report.json",
        "p488_next_unlock_agent_lane_status_gap_audit": "datasets/governance/p488_next_unlock_agent_lane_status_gap_audit.jsonl",
        "p488_next_unlock_agent_lane_status_gap_audit_report": "reports/p488_next_unlock_agent_lane_status_gap_audit_report.json",
        "p488_next_unlock_agent_lane_status_gap_audit_validation_report": "reports/p488_next_unlock_agent_lane_status_gap_audit_validation_report.json",
        "p489_next_unlock_lane_dispatch_gap_audit": "datasets/governance/p489_next_unlock_lane_dispatch_gap_audit.jsonl",
        "p489_next_unlock_lane_dispatch_gap_audit_report": "reports/p489_next_unlock_lane_dispatch_gap_audit_report.json",
        "p489_next_unlock_lane_dispatch_gap_audit_validation_report": "reports/p489_next_unlock_lane_dispatch_gap_audit_validation_report.json",
        "p490_next_unlock_action_checklist_gap_audit": "datasets/governance/p490_next_unlock_action_checklist_gap_audit.jsonl",
        "p490_next_unlock_action_checklist_gap_audit_report": "reports/p490_next_unlock_action_checklist_gap_audit_report.json",
        "p490_next_unlock_action_checklist_gap_audit_validation_report": "reports/p490_next_unlock_action_checklist_gap_audit_validation_report.json",
        "p491_next_unlock_operator_work_ledger_gap_audit": "datasets/governance/p491_next_unlock_operator_work_ledger_gap_audit.jsonl",
        "p491_next_unlock_operator_work_ledger_gap_audit_report": "reports/p491_next_unlock_operator_work_ledger_gap_audit_report.json",
        "p491_next_unlock_operator_work_ledger_gap_audit_validation_report": "reports/p491_next_unlock_operator_work_ledger_gap_audit_validation_report.json",
        "p492_next_unlock_operator_work_receipt_gap_audit": "datasets/governance/p492_next_unlock_operator_work_receipt_gap_audit.jsonl",
        "p492_next_unlock_operator_work_receipt_gap_audit_report": "reports/p492_next_unlock_operator_work_receipt_gap_audit_report.json",
        "p492_next_unlock_operator_work_receipt_gap_audit_validation_report": "reports/p492_next_unlock_operator_work_receipt_gap_audit_validation_report.json",
        "p493_human_review_closeout_gap_audit": "datasets/governance/p493_human_review_closeout_gap_audit.jsonl",
        "p493_human_review_closeout_gap_audit_report": "reports/p493_human_review_closeout_gap_audit_report.json",
        "p493_human_review_closeout_gap_audit_validation_report": "reports/p493_human_review_closeout_gap_audit_validation_report.json",
        "p494_operator_work_receipt_manifest_consistency_gap_audit": "datasets/governance/p494_operator_work_receipt_manifest_consistency_gap_audit.jsonl",
        "p494_operator_work_receipt_manifest_consistency_gap_audit_report": "reports/p494_operator_work_receipt_manifest_consistency_gap_audit_report.json",
        "p494_operator_work_receipt_manifest_consistency_gap_audit_validation_report": "reports/p494_operator_work_receipt_manifest_consistency_gap_audit_validation_report.json",
        "p495_top_tier_ready_to_verify_receipt_gap_audit": "datasets/governance/p495_top_tier_ready_to_verify_receipt_gap_audit.jsonl",
        "p495_top_tier_ready_to_verify_receipt_gap_audit_report": "reports/p495_top_tier_ready_to_verify_receipt_gap_audit_report.json",
        "p495_top_tier_ready_to_verify_receipt_gap_audit_validation_report": "reports/p495_top_tier_ready_to_verify_receipt_gap_audit_validation_report.json",
        "p496_non_human_ready_to_verify_receipt_gap_audit": "datasets/governance/p496_non_human_ready_to_verify_receipt_gap_audit.jsonl",
        "p496_non_human_ready_to_verify_receipt_gap_audit_report": "reports/p496_non_human_ready_to_verify_receipt_gap_audit_report.json",
        "p496_non_human_ready_to_verify_receipt_gap_audit_validation_report": "reports/p496_non_human_ready_to_verify_receipt_gap_audit_validation_report.json",
        "p497_stage25_operator_docs_sync_receipt_gap_audit": "datasets/governance/p497_stage25_operator_docs_sync_receipt_gap_audit.jsonl",
        "p497_stage25_operator_docs_sync_receipt_gap_audit_report": "reports/p497_stage25_operator_docs_sync_receipt_gap_audit_report.json",
        "p497_stage25_operator_docs_sync_receipt_gap_audit_validation_report": "reports/p497_stage25_operator_docs_sync_receipt_gap_audit_validation_report.json",
        "p498_safe_training_pipeline_current_receipt_gap_audit": "datasets/governance/p498_safe_training_pipeline_current_receipt_gap_audit.jsonl",
        "p498_safe_training_pipeline_current_receipt_gap_audit_report": "reports/p498_safe_training_pipeline_current_receipt_gap_audit_report.json",
        "p498_safe_training_pipeline_current_receipt_gap_audit_validation_report": "reports/p498_safe_training_pipeline_current_receipt_gap_audit_validation_report.json",
        "p499_local_release_consistency_receipt_gap_audit": "datasets/governance/p499_local_release_consistency_receipt_gap_audit.jsonl",
        "p499_local_release_consistency_receipt_gap_audit_report": "reports/p499_local_release_consistency_receipt_gap_audit_report.json",
        "p499_local_release_consistency_receipt_gap_audit_validation_report": "reports/p499_local_release_consistency_receipt_gap_audit_validation_report.json",
        "p500_stage25_fail_closed_validation_current_receipt_gap_audit": "datasets/governance/p500_stage25_fail_closed_validation_current_receipt_gap_audit.jsonl",
        "p500_stage25_fail_closed_validation_current_receipt_gap_audit_report": "reports/p500_stage25_fail_closed_validation_current_receipt_gap_audit_report.json",
        "p500_stage25_fail_closed_validation_current_receipt_gap_audit_validation_report": "reports/p500_stage25_fail_closed_validation_current_receipt_gap_audit_validation_report.json",
        "p501_ready_to_verify_promotion_gap_audit": "datasets/governance/p501_ready_to_verify_promotion_gap_audit.jsonl",
        "p501_ready_to_verify_promotion_gap_audit_report": "reports/p501_ready_to_verify_promotion_gap_audit_report.json",
        "p501_ready_to_verify_promotion_gap_audit_validation_report": "reports/p501_ready_to_verify_promotion_gap_audit_validation_report.json",
        "p502_local_release_safety_guard_link_gap_audit": "datasets/governance/p502_local_release_safety_guard_link_gap_audit.jsonl",
        "p502_local_release_safety_guard_link_audit_report": "reports/p502_local_release_safety_guard_link_audit_report.json",
        "p502_local_release_safety_guard_link_audit_validation_report": "reports/p502_local_release_safety_guard_link_audit_validation_report.json",
        "p503_safe_training_pipeline_receipt_atomicity_gap_audit": "datasets/governance/p503_safe_training_pipeline_receipt_atomicity_gap_audit.jsonl",
        "p503_safe_training_pipeline_receipt_atomicity_gap_audit_report": "reports/p503_safe_training_pipeline_receipt_atomicity_gap_audit_report.json",
        "p503_safe_training_pipeline_receipt_atomicity_gap_audit_validation_report": "reports/p503_safe_training_pipeline_receipt_atomicity_gap_audit_validation_report.json",
        "p504_local_release_consistency_receipt_atomicity_gap_audit": "datasets/governance/p504_local_release_consistency_receipt_atomicity_gap_audit.jsonl",
        "p504_local_release_consistency_receipt_atomicity_gap_audit_report": "reports/p504_local_release_consistency_receipt_atomicity_gap_audit_report.json",
        "p504_local_release_consistency_receipt_atomicity_gap_audit_validation_report": "reports/p504_local_release_consistency_receipt_atomicity_gap_audit_validation_report.json",
        "p505_local_release_terminal_defer_mode_gap_audit": "datasets/governance/p505_local_release_terminal_defer_mode_gap_audit.jsonl",
        "p505_local_release_terminal_defer_mode_gap_audit_report": "reports/p505_local_release_terminal_defer_mode_gap_audit_report.json",
        "p505_local_release_terminal_defer_mode_gap_audit_validation_report": "reports/p505_local_release_terminal_defer_mode_gap_audit_validation_report.json",
        "p506_local_release_consistency_semantic_policy_current_gap_audit": "datasets/governance/p506_local_release_consistency_semantic_policy_current_gap_audit.jsonl",
        "p506_local_release_consistency_semantic_policy_current_gap_audit_report": "reports/p506_local_release_consistency_semantic_policy_current_gap_audit_report.json",
        "p506_local_release_consistency_semantic_policy_current_gap_audit_validation_report": "reports/p506_local_release_consistency_semantic_policy_current_gap_audit_validation_report.json",
        "p507_data_lake_artifact_integrity_gap_audit": "datasets/governance/p507_data_lake_artifact_integrity_gap_audit.jsonl",
        "p507_data_lake_artifact_integrity_gap_audit_report": "reports/p507_data_lake_artifact_integrity_gap_audit_report.json",
        "p507_data_lake_artifact_integrity_gap_audit_validation_report": "reports/p507_data_lake_artifact_integrity_gap_audit_validation_report.json",
        "p508_local_release_safety_guard_link_atomicity_gap_audit": "datasets/governance/p508_local_release_safety_guard_link_atomicity_gap_audit.jsonl",
        "p508_local_release_safety_guard_link_atomicity_gap_audit_report": "reports/p508_local_release_safety_guard_link_atomicity_gap_audit_report.json",
        "p508_local_release_safety_guard_link_atomicity_gap_audit_validation_report": "reports/p508_local_release_safety_guard_link_atomicity_gap_audit_validation_report.json",
        "p509_local_release_safety_guard_link_current_atomicity_gap_audit": "datasets/governance/p509_local_release_safety_guard_link_current_atomicity_gap_audit.jsonl",
        "p509_local_release_safety_guard_link_current_atomicity_gap_audit_report": "reports/p509_local_release_safety_guard_link_current_atomicity_gap_audit_report.json",
        "p509_local_release_safety_guard_link_current_atomicity_gap_audit_validation_report": "reports/p509_local_release_safety_guard_link_current_atomicity_gap_audit_validation_report.json",
        "p510_data_lake_volatile_exemption_gap_audit": "datasets/governance/p510_data_lake_volatile_exemption_gap_audit.jsonl",
        "p510_data_lake_volatile_exemption_gap_audit_report": "reports/p510_data_lake_volatile_exemption_gap_audit_report.json",
        "p510_data_lake_volatile_exemption_gap_audit_validation_report": "reports/p510_data_lake_volatile_exemption_gap_audit_validation_report.json",
        "p511_data_lake_live_content_integrity_gap_audit": "datasets/governance/p511_data_lake_live_content_integrity_gap_audit.jsonl",
        "p511_data_lake_live_content_integrity_gap_audit_report": "reports/p511_data_lake_live_content_integrity_gap_audit_report.json",
        "p511_data_lake_live_content_integrity_gap_audit_validation_report": "reports/p511_data_lake_live_content_integrity_gap_audit_validation_report.json",
        "p512_local_release_live_integrity_binding_gap_audit": "datasets/governance/p512_local_release_live_integrity_binding_gap_audit.jsonl",
        "p512_local_release_live_integrity_binding_gap_audit_report": "reports/p512_local_release_live_integrity_binding_gap_audit_report.json",
        "p512_local_release_live_integrity_binding_gap_audit_validation_report": "reports/p512_local_release_live_integrity_binding_gap_audit_validation_report.json",
        "p513_data_lake_release_input_contract_policy_gap_audit": "datasets/governance/p513_data_lake_release_input_contract_policy_gap_audit.jsonl",
        "p513_data_lake_release_input_contract_policy_gap_audit_report": "reports/p513_data_lake_release_input_contract_policy_gap_audit_report.json",
        "p513_data_lake_release_input_contract_policy_gap_audit_validation_report": "reports/p513_data_lake_release_input_contract_policy_gap_audit_validation_report.json",
        "p514_data_lake_release_input_contract_policy_regression_gap_audit": "datasets/governance/p514_data_lake_release_input_contract_policy_regression_gap_audit.jsonl",
        "p514_data_lake_release_input_contract_policy_regression_gap_audit_report": "reports/p514_data_lake_release_input_contract_policy_regression_gap_audit_report.json",
        "p514_data_lake_release_input_contract_policy_regression_gap_audit_validation_report": "reports/p514_data_lake_release_input_contract_policy_regression_gap_audit_validation_report.json",
        "p515_local_release_contract_policy_binding_gap_audit": "datasets/governance/p515_local_release_contract_policy_binding_gap_audit.jsonl",
        "p515_local_release_contract_policy_binding_gap_audit_report": "reports/p515_local_release_contract_policy_binding_gap_audit_report.json",
        "p515_local_release_contract_policy_binding_gap_audit_validation_report": "reports/p515_local_release_contract_policy_binding_gap_audit_validation_report.json",
        "p516_safe_training_pipeline_bootstrap_release_consistency_gap_audit": "datasets/governance/p516_safe_training_pipeline_bootstrap_release_consistency_gap_audit.jsonl",
        "p516_safe_training_pipeline_bootstrap_release_consistency_gap_audit_report": "reports/p516_safe_training_pipeline_bootstrap_release_consistency_gap_audit_report.json",
        "p516_safe_training_pipeline_bootstrap_release_consistency_gap_audit_validation_report": "reports/p516_safe_training_pipeline_bootstrap_release_consistency_gap_audit_validation_report.json",
        "p517_local_release_high_risk_summary_safety_gap_audit": "datasets/governance/p517_local_release_high_risk_summary_safety_gap_audit.jsonl",
        "p517_local_release_high_risk_summary_safety_gap_audit_report": "reports/p517_local_release_high_risk_summary_safety_gap_audit_report.json",
        "p517_local_release_high_risk_summary_safety_gap_audit_validation_report": "reports/p517_local_release_high_risk_summary_safety_gap_audit_validation_report.json",
        "p518_local_release_high_risk_coverage_safety_gap_audit": "datasets/governance/p518_local_release_high_risk_coverage_safety_gap_audit.jsonl",
        "p518_local_release_high_risk_coverage_safety_gap_audit_report": "reports/p518_local_release_high_risk_coverage_safety_gap_audit_report.json",
        "p518_local_release_high_risk_coverage_safety_gap_audit_validation_report": "reports/p518_local_release_high_risk_coverage_safety_gap_audit_validation_report.json",
        "p519_safe_training_pipeline_current_receipt_regression_gap_audit": "datasets/governance/p519_safe_training_pipeline_current_receipt_regression_gap_audit.jsonl",
        "p519_safe_training_pipeline_current_receipt_regression_gap_audit_report": "reports/p519_safe_training_pipeline_current_receipt_regression_gap_audit_report.json",
        "p519_safe_training_pipeline_current_receipt_regression_gap_audit_validation_report": "reports/p519_safe_training_pipeline_current_receipt_regression_gap_audit_validation_report.json",
        "p520_local_release_consistency_receipt_current_regression_gap_audit": "datasets/governance/p520_local_release_consistency_receipt_current_regression_gap_audit.jsonl",
        "p520_local_release_consistency_receipt_current_regression_gap_audit_report": "reports/p520_local_release_consistency_receipt_current_regression_gap_audit_report.json",
        "p520_local_release_consistency_receipt_current_regression_gap_audit_validation_report": "reports/p520_local_release_consistency_receipt_current_regression_gap_audit_validation_report.json",
        "p521_local_release_consistency_semantic_policy_regression_gap_audit": "datasets/governance/p521_local_release_consistency_semantic_policy_regression_gap_audit.jsonl",
        "p521_local_release_consistency_semantic_policy_regression_gap_audit_report": "reports/p521_local_release_consistency_semantic_policy_regression_gap_audit_report.json",
        "p521_local_release_consistency_semantic_policy_regression_gap_audit_validation_report": "reports/p521_local_release_consistency_semantic_policy_regression_gap_audit_validation_report.json",
        "p522_local_release_consistency_semantic_policy_atomicity_regression_gap_audit": "datasets/governance/p522_local_release_consistency_semantic_policy_atomicity_regression_gap_audit.jsonl",
        "p522_local_release_consistency_semantic_policy_atomicity_regression_gap_audit_report": "reports/p522_local_release_consistency_semantic_policy_atomicity_regression_gap_audit_report.json",
        "p522_local_release_consistency_semantic_policy_atomicity_regression_gap_audit_validation_report": "reports/p522_local_release_consistency_semantic_policy_atomicity_regression_gap_audit_validation_report.json",
        "p523_stage25_operator_docs_sync_contract_policy_gap_audit": "datasets/governance/p523_stage25_operator_docs_sync_contract_policy_gap_audit.jsonl",
        "p523_stage25_operator_docs_sync_contract_policy_gap_audit_report": "reports/p523_stage25_operator_docs_sync_contract_policy_gap_audit_report.json",
        "p523_stage25_operator_docs_sync_contract_policy_gap_audit_validation_report": "reports/p523_stage25_operator_docs_sync_contract_policy_gap_audit_validation_report.json",
        "p524_stage25_operator_docs_dynamic_status_sync_gap_audit": "datasets/governance/p524_stage25_operator_docs_dynamic_status_sync_gap_audit.jsonl",
        "p524_stage25_operator_docs_dynamic_status_sync_gap_audit_report": "reports/p524_stage25_operator_docs_dynamic_status_sync_gap_audit_report.json",
        "p524_stage25_operator_docs_dynamic_status_sync_gap_audit_validation_report": "reports/p524_stage25_operator_docs_dynamic_status_sync_gap_audit_validation_report.json",
        "p525_stage25_operator_docs_dynamic_status_sync_current_gap_audit": "datasets/governance/p525_stage25_operator_docs_dynamic_status_sync_current_gap_audit.jsonl",
        "p525_stage25_operator_docs_dynamic_status_sync_current_gap_audit_report": "reports/p525_stage25_operator_docs_dynamic_status_sync_current_gap_audit_report.json",
        "p525_stage25_operator_docs_dynamic_status_sync_current_gap_audit_validation_report": "reports/p525_stage25_operator_docs_dynamic_status_sync_current_gap_audit_validation_report.json",
        "p526_stage25_operator_docs_dynamic_status_sync_current_regression_gap_audit": "datasets/governance/p526_stage25_operator_docs_dynamic_status_sync_current_regression_gap_audit.jsonl",
        "p526_stage25_operator_docs_dynamic_status_sync_current_regression_gap_audit_report": "reports/p526_stage25_operator_docs_dynamic_status_sync_current_regression_gap_audit_report.json",
        "p526_stage25_operator_docs_dynamic_status_sync_current_regression_gap_audit_validation_report": "reports/p526_stage25_operator_docs_dynamic_status_sync_current_regression_gap_audit_validation_report.json",
        "p527_stage25_operator_docs_dynamic_status_sync_atomicity_gap_audit": "datasets/governance/p527_stage25_operator_docs_dynamic_status_sync_atomicity_gap_audit.jsonl",
        "p527_stage25_operator_docs_dynamic_status_sync_atomicity_gap_audit_report": "reports/p527_stage25_operator_docs_dynamic_status_sync_atomicity_gap_audit_report.json",
        "p527_stage25_operator_docs_dynamic_status_sync_atomicity_gap_audit_validation_report": "reports/p527_stage25_operator_docs_dynamic_status_sync_atomicity_gap_audit_validation_report.json",
        "p528_stage25_operator_docs_sync_contract_policy_regression_gap_audit": "datasets/governance/p528_stage25_operator_docs_sync_contract_policy_regression_gap_audit.jsonl",
        "p528_stage25_operator_docs_sync_contract_policy_regression_gap_audit_report": "reports/p528_stage25_operator_docs_sync_contract_policy_regression_gap_audit_report.json",
        "p528_stage25_operator_docs_sync_contract_policy_regression_gap_audit_validation_report": "reports/p528_stage25_operator_docs_sync_contract_policy_regression_gap_audit_validation_report.json",
        "p529_stage25_operator_docs_sync_current_receipt_regression_gap_audit": "datasets/governance/p529_stage25_operator_docs_sync_current_receipt_regression_gap_audit.jsonl",
        "p529_stage25_operator_docs_sync_current_receipt_regression_gap_audit_report": "reports/p529_stage25_operator_docs_sync_current_receipt_regression_gap_audit_report.json",
        "p529_stage25_operator_docs_sync_current_receipt_regression_gap_audit_validation_report": "reports/p529_stage25_operator_docs_sync_current_receipt_regression_gap_audit_validation_report.json",
        "p530_stage25_operator_docs_sync_terminal_recovery_regression_gap_audit": "datasets/governance/p530_stage25_operator_docs_sync_terminal_recovery_regression_gap_audit.jsonl",
        "p530_stage25_operator_docs_sync_terminal_recovery_regression_gap_audit_report": "reports/p530_stage25_operator_docs_sync_terminal_recovery_regression_gap_audit_report.json",
        "p530_stage25_operator_docs_sync_terminal_recovery_regression_gap_audit_validation_report": "reports/p530_stage25_operator_docs_sync_terminal_recovery_regression_gap_audit_validation_report.json",
        "p531_controlled_release_guard_order_validation_receipt_gap_audit": "datasets/governance/p531_controlled_release_guard_order_validation_receipt_gap_audit.jsonl",
        "p531_controlled_release_guard_order_validation_receipt_gap_audit_report": "reports/p531_controlled_release_guard_order_validation_receipt_gap_audit_report.json",
        "p531_controlled_release_guard_order_validation_receipt_gap_audit_validation_report": "reports/p531_controlled_release_guard_order_validation_receipt_gap_audit_validation_report.json",
        "p532_controlled_release_guard_order_regression_gap_audit": "datasets/governance/p532_controlled_release_guard_order_regression_gap_audit.jsonl",
        "p532_controlled_release_guard_order_regression_gap_audit_report": "reports/p532_controlled_release_guard_order_regression_gap_audit_report.json",
        "p532_controlled_release_guard_order_regression_gap_audit_validation_report": "reports/p532_controlled_release_guard_order_regression_gap_audit_validation_report.json",
        "p533_controlled_release_guard_order_current_validation_receipt_gap_audit": "datasets/governance/p533_controlled_release_guard_order_current_validation_receipt_gap_audit.jsonl",
        "p533_controlled_release_guard_order_current_validation_receipt_gap_audit_report": "reports/p533_controlled_release_guard_order_current_validation_receipt_gap_audit_report.json",
        "p533_controlled_release_guard_order_current_validation_receipt_gap_audit_validation_report": "reports/p533_controlled_release_guard_order_current_validation_receipt_gap_audit_validation_report.json",
        "p534_controlled_release_guard_order_current_regression_gap_audit": "datasets/governance/p534_controlled_release_guard_order_current_regression_gap_audit.jsonl",
        "p534_controlled_release_guard_order_current_regression_gap_audit_report": "reports/p534_controlled_release_guard_order_current_regression_gap_audit_report.json",
        "p534_controlled_release_guard_order_current_regression_gap_audit_validation_report": "reports/p534_controlled_release_guard_order_current_regression_gap_audit_validation_report.json",
        "p535_controlled_release_guard_order_atomicity_regression_gap_audit": "datasets/governance/p535_controlled_release_guard_order_atomicity_regression_gap_audit.jsonl",
        "p535_controlled_release_guard_order_atomicity_regression_gap_audit_report": "reports/p535_controlled_release_guard_order_atomicity_regression_gap_audit_report.json",
        "p535_controlled_release_guard_order_atomicity_regression_gap_audit_validation_report": "reports/p535_controlled_release_guard_order_atomicity_regression_gap_audit_validation_report.json",
        "p536_stage25_remaining_blocker_cross_binding_gap_audit": "datasets/governance/p536_stage25_remaining_blocker_cross_binding_gap_audit.jsonl",
        "p536_stage25_remaining_blocker_cross_binding_gap_audit_report": "reports/p536_stage25_remaining_blocker_cross_binding_gap_audit_report.json",
        "p536_stage25_remaining_blocker_cross_binding_gap_audit_validation_report": "reports/p536_stage25_remaining_blocker_cross_binding_gap_audit_validation_report.json",
        "p537_stage25_remaining_blocker_cross_binding_regression_gap_audit": "datasets/governance/p537_stage25_remaining_blocker_cross_binding_regression_gap_audit.jsonl",
        "p537_stage25_remaining_blocker_cross_binding_regression_gap_audit_report": "reports/p537_stage25_remaining_blocker_cross_binding_regression_gap_audit_report.json",
        "p537_stage25_remaining_blocker_cross_binding_regression_gap_audit_validation_report": "reports/p537_stage25_remaining_blocker_cross_binding_regression_gap_audit_validation_report.json",
        "p538_controlled_execution_wave_pair_atomicity_regression_gap_audit": "datasets/governance/p538_controlled_execution_wave_pair_atomicity_regression_gap_audit.jsonl",
        "p538_controlled_execution_wave_pair_atomicity_regression_gap_audit_report": "reports/p538_controlled_execution_wave_pair_atomicity_regression_gap_audit_report.json",
        "p538_controlled_execution_wave_pair_atomicity_regression_gap_audit_validation_report": "reports/p538_controlled_execution_wave_pair_atomicity_regression_gap_audit_validation_report.json",
        "p539_enzyme_agent_execution_receipt_gate_gap_audit": "datasets/governance/p539_enzyme_agent_execution_receipt_gate_gap_audit.jsonl",
        "p539_enzyme_agent_execution_receipt_gate_gap_audit_report": "reports/p539_enzyme_agent_execution_receipt_gate_gap_audit_report.json",
        "p539_enzyme_agent_execution_receipt_gate_gap_audit_validation_report": "reports/p539_enzyme_agent_execution_receipt_gate_gap_audit_validation_report.json",
        "p540_enzyme_agent_execution_receipt_lineage_gap_audit": "datasets/governance/p540_enzyme_agent_execution_receipt_lineage_gap_audit.jsonl",
        "p540_enzyme_agent_execution_receipt_lineage_gap_audit_report": "reports/p540_enzyme_agent_execution_receipt_lineage_gap_audit_report.json",
        "p540_enzyme_agent_execution_receipt_lineage_gap_audit_validation_report": "reports/p540_enzyme_agent_execution_receipt_lineage_gap_audit_validation_report.json",
        "p541_enzyme_agent_execution_receipt_proof_current_gap_audit": "datasets/governance/p541_enzyme_agent_execution_receipt_proof_current_gap_audit.jsonl",
        "p541_enzyme_agent_execution_receipt_proof_current_gap_audit_report": "reports/p541_enzyme_agent_execution_receipt_proof_current_gap_audit_report.json",
        "p541_enzyme_agent_execution_receipt_proof_current_gap_audit_validation_report": "reports/p541_enzyme_agent_execution_receipt_proof_current_gap_audit_validation_report.json",
        "p542_enzyme_agent_execution_receipt_proof_current_regression_gap_audit": "datasets/governance/p542_enzyme_agent_execution_receipt_proof_current_regression_gap_audit.jsonl",
        "p542_enzyme_agent_execution_receipt_proof_current_regression_gap_audit_report": "reports/p542_enzyme_agent_execution_receipt_proof_current_regression_gap_audit_report.json",
        "p542_enzyme_agent_execution_receipt_proof_current_regression_gap_audit_validation_report": "reports/p542_enzyme_agent_execution_receipt_proof_current_regression_gap_audit_validation_report.json",
        "p543_enzyme_agent_execution_receipt_safety_regression_gap_audit": "datasets/governance/p543_enzyme_agent_execution_receipt_safety_regression_gap_audit.jsonl",
        "p543_enzyme_agent_execution_receipt_safety_regression_gap_audit_report": "reports/p543_enzyme_agent_execution_receipt_safety_regression_gap_audit_report.json",
        "p543_enzyme_agent_execution_receipt_safety_regression_gap_audit_validation_report": "reports/p543_enzyme_agent_execution_receipt_safety_regression_gap_audit_validation_report.json",
        "p544_enzyme_agent_execution_eligibility_matrix_gap_audit": "datasets/governance/p544_enzyme_agent_execution_eligibility_matrix_gap_audit.jsonl",
        "p544_enzyme_agent_execution_eligibility_matrix_gap_audit_report": "reports/p544_enzyme_agent_execution_eligibility_matrix_gap_audit_report.json",
        "p544_enzyme_agent_execution_eligibility_matrix_gap_audit_validation_report": "reports/p544_enzyme_agent_execution_eligibility_matrix_gap_audit_validation_report.json",
        "p545_enzyme_agent_execution_eligibility_safety_regression_gap_audit": "datasets/governance/p545_enzyme_agent_execution_eligibility_safety_regression_gap_audit.jsonl",
        "p545_enzyme_agent_execution_eligibility_safety_regression_gap_audit_report": "reports/p545_enzyme_agent_execution_eligibility_safety_regression_gap_audit_report.json",
        "p545_enzyme_agent_execution_eligibility_safety_regression_gap_audit_validation_report": "reports/p545_enzyme_agent_execution_eligibility_safety_regression_gap_audit_validation_report.json",
        "p546_enzyme_agent_execution_outcome_dashboard_gap_audit": "datasets/governance/p546_enzyme_agent_execution_outcome_dashboard_gap_audit.jsonl",
        "p546_enzyme_agent_execution_outcome_dashboard_gap_audit_report": "reports/p546_enzyme_agent_execution_outcome_dashboard_gap_audit_report.json",
        "p546_enzyme_agent_execution_outcome_dashboard_gap_audit_validation_report": "reports/p546_enzyme_agent_execution_outcome_dashboard_gap_audit_validation_report.json",
        "p547_top_tier_model_execution_board_gap_audit": "datasets/governance/p547_top_tier_model_execution_board_gap_audit.jsonl",
        "p547_top_tier_model_execution_board_gap_audit_report": "reports/p547_top_tier_model_execution_board_gap_audit_report.json",
        "p547_top_tier_model_execution_board_gap_audit_validation_report": "reports/p547_top_tier_model_execution_board_gap_audit_validation_report.json",
        "p548_non_human_construction_board_gap_audit": "datasets/governance/p548_non_human_construction_board_gap_audit.jsonl",
        "p548_non_human_construction_board_gap_audit_report": "reports/p548_non_human_construction_board_gap_audit_report.json",
        "p548_non_human_construction_board_gap_audit_validation_report": "reports/p548_non_human_construction_board_gap_audit_validation_report.json",
        "p549_parallel_hard_gate_execution_receipts_gap_audit": "datasets/governance/p549_parallel_hard_gate_execution_receipts_gap_audit.jsonl",
        "p549_parallel_hard_gate_execution_receipts_gap_audit_report": "reports/p549_parallel_hard_gate_execution_receipts_gap_audit_report.json",
        "p549_parallel_hard_gate_execution_receipts_gap_audit_validation_report": "reports/p549_parallel_hard_gate_execution_receipts_gap_audit_validation_report.json",
        "p550_execution_receipt_artifact_freshness_gap_audit": "datasets/governance/p550_execution_receipt_artifact_freshness_gap_audit.jsonl",
        "p550_execution_receipt_artifact_freshness_gap_audit_report": "reports/p550_execution_receipt_artifact_freshness_gap_audit_report.json",
        "p550_execution_receipt_artifact_freshness_gap_audit_validation_report": "reports/p550_execution_receipt_artifact_freshness_gap_audit_validation_report.json",
        "p551_execution_receipt_artifact_hash_coverage_gap_audit": "datasets/governance/p551_execution_receipt_artifact_hash_coverage_gap_audit.jsonl",
        "p551_execution_receipt_artifact_hash_coverage_gap_audit_report": "reports/p551_execution_receipt_artifact_hash_coverage_gap_audit_report.json",
        "p551_execution_receipt_artifact_hash_coverage_gap_audit_validation_report": "reports/p551_execution_receipt_artifact_hash_coverage_gap_audit_validation_report.json",
        "p552_top_tier_model_execution_board_claim_boundary_gap_audit": "datasets/governance/p552_top_tier_model_execution_board_claim_boundary_gap_audit.jsonl",
        "p552_top_tier_model_execution_board_claim_boundary_gap_audit_report": "reports/p552_top_tier_model_execution_board_claim_boundary_gap_audit_report.json",
        "p552_top_tier_model_execution_board_claim_boundary_gap_audit_validation_report": "reports/p552_top_tier_model_execution_board_claim_boundary_gap_audit_validation_report.json",
        "p553_non_human_construction_board_claim_boundary_gap_audit": "datasets/governance/p553_non_human_construction_board_claim_boundary_gap_audit.jsonl",
        "p553_non_human_construction_board_claim_boundary_gap_audit_report": "reports/p553_non_human_construction_board_claim_boundary_gap_audit_report.json",
        "p553_non_human_construction_board_claim_boundary_gap_audit_validation_report": "reports/p553_non_human_construction_board_claim_boundary_gap_audit_validation_report.json",
        "p554_enzyme_agent_execution_outcome_formal_boundary_gap_audit": "datasets/governance/p554_enzyme_agent_execution_outcome_formal_boundary_gap_audit.jsonl",
        "p554_enzyme_agent_execution_outcome_formal_boundary_gap_audit_report": "reports/p554_enzyme_agent_execution_outcome_formal_boundary_gap_audit_report.json",
        "p554_enzyme_agent_execution_outcome_formal_boundary_gap_audit_validation_report": "reports/p554_enzyme_agent_execution_outcome_formal_boundary_gap_audit_validation_report.json",
        "p555_parallel_hard_gate_execution_decision_boundary_gap_audit": "datasets/governance/p555_parallel_hard_gate_execution_decision_boundary_gap_audit.jsonl",
        "p555_parallel_hard_gate_execution_decision_boundary_gap_audit_report": "reports/p555_parallel_hard_gate_execution_decision_boundary_gap_audit_report.json",
        "p555_parallel_hard_gate_execution_decision_boundary_gap_audit_validation_report": "reports/p555_parallel_hard_gate_execution_decision_boundary_gap_audit_validation_report.json",
        "p556_top_tier_ready_receipt_completion_boundary_gap_audit": "datasets/governance/p556_top_tier_ready_receipt_completion_boundary_gap_audit.jsonl",
        "p556_top_tier_ready_receipt_completion_boundary_gap_audit_report": "reports/p556_top_tier_ready_receipt_completion_boundary_gap_audit_report.json",
        "p556_top_tier_ready_receipt_completion_boundary_gap_audit_validation_report": "reports/p556_top_tier_ready_receipt_completion_boundary_gap_audit_validation_report.json",
        "p557_non_human_ready_receipt_completion_boundary_gap_audit": "datasets/governance/p557_non_human_ready_receipt_completion_boundary_gap_audit.jsonl",
        "p557_non_human_ready_receipt_completion_boundary_gap_audit_report": "reports/p557_non_human_ready_receipt_completion_boundary_gap_audit_report.json",
        "p557_non_human_ready_receipt_completion_boundary_gap_audit_validation_report": "reports/p557_non_human_ready_receipt_completion_boundary_gap_audit_validation_report.json",
        "p558_ready_to_verify_promotion_boundary_gap_audit": "datasets/governance/p558_ready_to_verify_promotion_boundary_gap_audit.jsonl",
        "p558_ready_to_verify_promotion_boundary_gap_audit_report": "reports/p558_ready_to_verify_promotion_boundary_gap_audit_report.json",
        "p558_ready_to_verify_promotion_boundary_gap_audit_validation_report": "reports/p558_ready_to_verify_promotion_boundary_gap_audit_validation_report.json",
        "p559_data_lake_live_integrity_boundary_gap_audit": "datasets/governance/p559_data_lake_live_integrity_boundary_gap_audit.jsonl",
        "p559_data_lake_live_integrity_boundary_gap_audit_report": "reports/p559_data_lake_live_integrity_boundary_gap_audit_report.json",
        "p559_data_lake_live_integrity_boundary_gap_audit_validation_report": "reports/p559_data_lake_live_integrity_boundary_gap_audit_validation_report.json",
        "p560_local_release_consistency_boundary_gap_audit": "datasets/governance/p560_local_release_consistency_boundary_gap_audit.jsonl",
        "p560_local_release_consistency_boundary_gap_audit_report": "reports/p560_local_release_consistency_boundary_gap_audit_report.json",
        "p560_local_release_consistency_boundary_gap_audit_validation_report": "reports/p560_local_release_consistency_boundary_gap_audit_validation_report.json",
        "p561_reviewed_numbering_hard_boundary_gap_audit": "datasets/governance/p561_reviewed_numbering_hard_boundary_gap_audit.jsonl",
        "p561_reviewed_numbering_hard_boundary_gap_audit_report": "reports/p561_reviewed_numbering_hard_boundary_gap_audit_report.json",
        "p561_reviewed_numbering_hard_boundary_gap_audit_validation_report": "reports/p561_reviewed_numbering_hard_boundary_gap_audit_validation_report.json",
        "p562_wet_lab_feedback_numeric_eligibility_boundary_gap_audit": "datasets/governance/p562_wet_lab_feedback_numeric_eligibility_boundary_gap_audit.jsonl",
        "p562_wet_lab_feedback_numeric_eligibility_boundary_gap_audit_report": "reports/p562_wet_lab_feedback_numeric_eligibility_boundary_gap_audit_report.json",
        "p562_wet_lab_feedback_numeric_eligibility_boundary_gap_audit_validation_report": "reports/p562_wet_lab_feedback_numeric_eligibility_boundary_gap_audit_validation_report.json",
        "p563_physics_ddg_backend_readiness_boundary_gap_audit": "datasets/governance/p563_physics_ddg_backend_readiness_boundary_gap_audit.jsonl",
        "p563_physics_ddg_backend_readiness_boundary_gap_audit_report": "reports/p563_physics_ddg_backend_readiness_boundary_gap_audit_report.json",
        "p563_physics_ddg_backend_readiness_boundary_gap_audit_validation_report": "reports/p563_physics_ddg_backend_readiness_boundary_gap_audit_validation_report.json",
        "p564_claim_readiness_matrix_hard_boundary_gap_audit": "datasets/governance/p564_claim_readiness_matrix_hard_boundary_gap_audit.jsonl",
        "p564_claim_readiness_matrix_hard_boundary_gap_audit_report": "reports/p564_claim_readiness_matrix_hard_boundary_gap_audit_report.json",
        "p564_claim_readiness_matrix_hard_boundary_gap_audit_validation_report": "reports/p564_claim_readiness_matrix_hard_boundary_gap_audit_validation_report.json",
        "p565_production_release_authorization_boundary_gap_audit": "datasets/governance/p565_production_release_authorization_boundary_gap_audit.jsonl",
        "p565_production_release_authorization_boundary_gap_audit_report": "reports/p565_production_release_authorization_boundary_gap_audit_report.json",
        "p565_production_release_authorization_boundary_gap_audit_validation_report": "reports/p565_production_release_authorization_boundary_gap_audit_validation_report.json",
        "p566_five_head_training_execution_boundary_gap_audit": "datasets/governance/p566_five_head_training_execution_boundary_gap_audit.jsonl",
        "p566_five_head_training_execution_boundary_gap_audit_report": "reports/p566_five_head_training_execution_boundary_gap_audit_report.json",
        "p566_five_head_training_execution_boundary_gap_audit_validation_report": "reports/p566_five_head_training_execution_boundary_gap_audit_validation_report.json",
        "p567_validated_feature_index_training_label_boundary_gap_audit": "datasets/governance/p567_validated_feature_index_training_label_boundary_gap_audit.jsonl",
        "p567_validated_feature_index_training_label_boundary_gap_audit_report": "reports/p567_validated_feature_index_training_label_boundary_gap_audit_report.json",
        "p567_validated_feature_index_training_label_boundary_gap_audit_validation_report": "reports/p567_validated_feature_index_training_label_boundary_gap_audit_validation_report.json",
        "p568_model_artifact_claim_boundary_gap_audit": "datasets/governance/p568_model_artifact_claim_boundary_gap_audit.jsonl",
        "p568_model_artifact_claim_boundary_gap_audit_report": "reports/p568_model_artifact_claim_boundary_gap_audit_report.json",
        "p568_model_artifact_claim_boundary_gap_audit_validation_report": "reports/p568_model_artifact_claim_boundary_gap_audit_validation_report.json",
        "p569_local_release_guard_coverage_boundary_gap_audit": "datasets/governance/p569_local_release_guard_coverage_boundary_gap_audit.jsonl",
        "p569_local_release_guard_coverage_boundary_gap_audit_report": "reports/p569_local_release_guard_coverage_boundary_gap_audit_report.json",
        "p569_local_release_guard_coverage_boundary_gap_audit_validation_report": "reports/p569_local_release_guard_coverage_boundary_gap_audit_validation_report.json",
        "p570_training_readiness_quality_boundary_gap_audit": "datasets/governance/p570_training_readiness_quality_boundary_gap_audit.jsonl",
        "p570_training_readiness_quality_boundary_gap_audit_report": "reports/p570_training_readiness_quality_boundary_gap_audit_report.json",
        "p570_training_readiness_quality_boundary_gap_audit_validation_report": "reports/p570_training_readiness_quality_boundary_gap_audit_validation_report.json",
        "p571_five_head_training_execution_contract_boundary_gap_audit": "datasets/governance/p571_five_head_training_execution_contract_boundary_gap_audit.jsonl",
        "p571_five_head_training_execution_contract_boundary_gap_audit_report": "reports/p571_five_head_training_execution_contract_boundary_gap_audit_report.json",
        "p571_five_head_training_execution_contract_boundary_gap_audit_validation_report": "reports/p571_five_head_training_execution_contract_boundary_gap_audit_validation_report.json",
        "p572_model_quality_hard_gate_contract_boundary_gap_audit": "datasets/governance/p572_model_quality_hard_gate_contract_boundary_gap_audit.jsonl",
        "p572_model_quality_hard_gate_contract_boundary_gap_audit_report": "reports/p572_model_quality_hard_gate_contract_boundary_gap_audit_report.json",
        "p572_model_quality_hard_gate_contract_boundary_gap_audit_validation_report": "reports/p572_model_quality_hard_gate_contract_boundary_gap_audit_validation_report.json",
        "p573_tool_lane_evidence_boundary_gap_audit": "datasets/governance/p573_tool_lane_evidence_boundary_gap_audit.jsonl",
        "p573_tool_lane_evidence_boundary_gap_audit_report": "reports/p573_tool_lane_evidence_boundary_gap_audit_report.json",
        "p573_tool_lane_evidence_boundary_gap_audit_validation_report": "reports/p573_tool_lane_evidence_boundary_gap_audit_validation_report.json",
        "p574_human_target_source_runtime_boundary_gap_audit": "datasets/governance/p574_human_target_source_runtime_boundary_gap_audit.jsonl",
        "p574_human_target_source_runtime_boundary_gap_audit_report": "reports/p574_human_target_source_runtime_boundary_gap_audit_report.json",
        "p574_human_target_source_runtime_boundary_gap_audit_validation_report": "reports/p574_human_target_source_runtime_boundary_gap_audit_validation_report.json",
        "p575_human_target_source_unlock_checklist_boundary_gap_audit": "datasets/governance/p575_human_target_source_unlock_checklist_boundary_gap_audit.jsonl",
        "p575_human_target_source_unlock_checklist_boundary_gap_audit_report": "reports/p575_human_target_source_unlock_checklist_boundary_gap_audit_report.json",
        "p575_human_target_source_unlock_checklist_boundary_gap_audit_validation_report": "reports/p575_human_target_source_unlock_checklist_boundary_gap_audit_validation_report.json",
        "p576_training_label_import_contract_boundary_gap_audit": "datasets/governance/p576_training_label_import_contract_boundary_gap_audit.jsonl",
        "p576_training_label_import_contract_boundary_gap_audit_report": "reports/p576_training_label_import_contract_boundary_gap_audit_report.json",
        "p576_training_label_import_contract_boundary_gap_audit_validation_report": "reports/p576_training_label_import_contract_boundary_gap_audit_validation_report.json",
        "p577_wet_lab_feedback_authorization_contract_boundary_gap_audit": "datasets/governance/p577_wet_lab_feedback_authorization_contract_boundary_gap_audit.jsonl",
        "p577_wet_lab_feedback_authorization_contract_boundary_gap_audit_report": "reports/p577_wet_lab_feedback_authorization_contract_boundary_gap_audit_report.json",
        "p577_wet_lab_feedback_authorization_contract_boundary_gap_audit_validation_report": "reports/p577_wet_lab_feedback_authorization_contract_boundary_gap_audit_validation_report.json",
        "p578_ddg_model_consumption_contract_boundary_gap_audit": "datasets/governance/p578_ddg_model_consumption_contract_boundary_gap_audit.jsonl",
        "p578_ddg_model_consumption_contract_boundary_gap_audit_report": "reports/p578_ddg_model_consumption_contract_boundary_gap_audit_report.json",
        "p578_ddg_model_consumption_contract_boundary_gap_audit_validation_report": "reports/p578_ddg_model_consumption_contract_boundary_gap_audit_validation_report.json",
        "p579_structure_feature_model_contract_boundary_gap_audit": "datasets/governance/p579_structure_feature_model_contract_boundary_gap_audit.jsonl",
        "p579_structure_feature_model_contract_boundary_gap_audit_report": "reports/p579_structure_feature_model_contract_boundary_gap_audit_report.json",
        "p579_structure_feature_model_contract_boundary_gap_audit_validation_report": "reports/p579_structure_feature_model_contract_boundary_gap_audit_validation_report.json",
        "p580_advanced_model_feature_contract_boundary_gap_audit": "datasets/governance/p580_advanced_model_feature_contract_boundary_gap_audit.jsonl",
        "p580_advanced_model_feature_contract_boundary_gap_audit_report": "reports/p580_advanced_model_feature_contract_boundary_gap_audit_report.json",
        "p580_advanced_model_feature_contract_boundary_gap_audit_validation_report": "reports/p580_advanced_model_feature_contract_boundary_gap_audit_validation_report.json",
        "p581_active_learning_trial_readiness_boundary_gap_audit": "datasets/governance/p581_active_learning_trial_readiness_boundary_gap_audit.jsonl",
        "p581_active_learning_trial_readiness_boundary_gap_audit_report": "reports/p581_active_learning_trial_readiness_boundary_gap_audit_report.json",
        "p581_active_learning_trial_readiness_boundary_gap_audit_validation_report": "reports/p581_active_learning_trial_readiness_boundary_gap_audit_validation_report.json",
        "p582_benchmark_readiness_packet_boundary_gap_audit": "datasets/governance/p582_benchmark_readiness_packet_boundary_gap_audit.jsonl",
        "p582_benchmark_readiness_packet_boundary_gap_audit_report": "reports/p582_benchmark_readiness_packet_boundary_gap_audit_report.json",
        "p582_benchmark_readiness_packet_boundary_gap_audit_validation_report": "reports/p582_benchmark_readiness_packet_boundary_gap_audit_validation_report.json",
        "p583_enzyme_tool_contract_boundary_gap_audit": "datasets/governance/p583_enzyme_tool_contract_boundary_gap_audit.jsonl",
        "p583_enzyme_tool_contract_boundary_gap_audit_report": "reports/p583_enzyme_tool_contract_boundary_gap_audit_report.json",
        "p583_enzyme_tool_contract_boundary_gap_audit_validation_report": "reports/p583_enzyme_tool_contract_boundary_gap_audit_validation_report.json",
        "p584_foreign_tool_readiness_boundary_gap_audit": "datasets/governance/p584_foreign_tool_readiness_boundary_gap_audit.jsonl",
        "p584_foreign_tool_readiness_boundary_gap_audit_report": "reports/p584_foreign_tool_readiness_boundary_gap_audit_report.json",
        "p584_foreign_tool_readiness_boundary_gap_audit_validation_report": "reports/p584_foreign_tool_readiness_boundary_gap_audit_validation_report.json",
        "p585_msa_runtime_readiness_boundary_gap_audit": "datasets/governance/p585_msa_runtime_readiness_boundary_gap_audit.jsonl",
        "p585_msa_runtime_readiness_boundary_gap_audit_report": "reports/p585_msa_runtime_readiness_boundary_gap_audit_report.json",
        "p585_msa_runtime_readiness_boundary_gap_audit_validation_report": "reports/p585_msa_runtime_readiness_boundary_gap_audit_validation_report.json",
        "p586_enzyme_resource_retrieval_plan_boundary_gap_audit": "datasets/governance/p586_enzyme_resource_retrieval_plan_boundary_gap_audit.jsonl",
        "p586_enzyme_resource_retrieval_plan_boundary_gap_audit_report": "reports/p586_enzyme_resource_retrieval_plan_boundary_gap_audit_report.json",
        "p586_enzyme_resource_retrieval_plan_boundary_gap_audit_validation_report": "reports/p586_enzyme_resource_retrieval_plan_boundary_gap_audit_validation_report.json",
        "p587_enzyme_agent_result_validation_boundary_gap_audit": "datasets/governance/p587_enzyme_agent_result_validation_boundary_gap_audit.jsonl",
        "p587_enzyme_agent_result_validation_boundary_gap_audit_report": "reports/p587_enzyme_agent_result_validation_boundary_gap_audit_report.json",
        "p587_enzyme_agent_result_validation_boundary_gap_audit_validation_report": "reports/p587_enzyme_agent_result_validation_boundary_gap_audit_validation_report.json",
        "p588_enzyme_agent_result_safety_regression_boundary_gap_audit": "datasets/governance/p588_enzyme_agent_result_safety_regression_boundary_gap_audit.jsonl",
        "p588_enzyme_agent_result_safety_regression_boundary_gap_audit_report": "reports/p588_enzyme_agent_result_safety_regression_boundary_gap_audit_report.json",
        "p588_enzyme_agent_result_safety_regression_boundary_gap_audit_validation_report": "reports/p588_enzyme_agent_result_safety_regression_boundary_gap_audit_validation_report.json",
        "p589_enzyme_agent_trace_audit_boundary_gap_audit": "datasets/governance/p589_enzyme_agent_trace_audit_boundary_gap_audit.jsonl",
        "p589_enzyme_agent_trace_audit_boundary_gap_audit_report": "reports/p589_enzyme_agent_trace_audit_boundary_gap_audit_report.json",
        "p589_enzyme_agent_trace_audit_boundary_gap_audit_validation_report": "reports/p589_enzyme_agent_trace_audit_boundary_gap_audit_validation_report.json",
        "p590_enzyme_agent_controlled_release_order_current_boundary_gap_audit": "datasets/governance/p590_enzyme_agent_controlled_release_order_current_boundary_gap_audit.jsonl",
        "p590_enzyme_agent_controlled_release_order_current_boundary_gap_audit_report": "reports/p590_enzyme_agent_controlled_release_order_current_boundary_gap_audit_report.json",
        "p590_enzyme_agent_controlled_release_order_current_boundary_gap_audit_validation_report": "reports/p590_enzyme_agent_controlled_release_order_current_boundary_gap_audit_validation_report.json",
        "p591_governance_readiness_boundary_gap_audit": "datasets/governance/p591_governance_readiness_boundary_gap_audit.jsonl",
        "p591_governance_readiness_boundary_gap_audit_report": "reports/p591_governance_readiness_boundary_gap_audit_report.json",
        "p591_governance_readiness_boundary_gap_audit_validation_report": "reports/p591_governance_readiness_boundary_gap_audit_validation_report.json",
        "p592_biosecurity_readiness_boundary_gap_audit": "datasets/governance/p592_biosecurity_readiness_boundary_gap_audit.jsonl",
        "p592_biosecurity_readiness_boundary_gap_audit_report": "reports/p592_biosecurity_readiness_boundary_gap_audit_report.json",
        "p592_biosecurity_readiness_boundary_gap_audit_validation_report": "reports/p592_biosecurity_readiness_boundary_gap_audit_validation_report.json",
        "p593_workstream_acceptance_boundary_gap_audit": "datasets/governance/p593_workstream_acceptance_boundary_gap_audit.jsonl",
        "p593_workstream_acceptance_boundary_gap_audit_report": "reports/p593_workstream_acceptance_boundary_gap_audit_report.json",
        "p593_workstream_acceptance_boundary_gap_audit_validation_report": "reports/p593_workstream_acceptance_boundary_gap_audit_validation_report.json",
        "p594_sequence_ip_fto_decision_boundary_gap_audit": "datasets/governance/p594_sequence_ip_fto_decision_boundary_gap_audit.jsonl",
        "p594_sequence_ip_fto_decision_boundary_gap_audit_report": "reports/p594_sequence_ip_fto_decision_boundary_gap_audit_report.json",
        "p594_sequence_ip_fto_decision_boundary_gap_audit_validation_report": "reports/p594_sequence_ip_fto_decision_boundary_gap_audit_validation_report.json",
        "p595_model_claim_fail_closed_consistency_boundary_gap_audit": "datasets/governance/p595_model_claim_fail_closed_consistency_boundary_gap_audit.jsonl",
        "p595_model_claim_fail_closed_consistency_boundary_gap_audit_report": "reports/p595_model_claim_fail_closed_consistency_boundary_gap_audit_report.json",
        "p595_model_claim_fail_closed_consistency_boundary_gap_audit_validation_report": "reports/p595_model_claim_fail_closed_consistency_boundary_gap_audit_validation_report.json",
        "p596_external_data_source_registry_boundary_gap_audit": "datasets/governance/p596_external_data_source_registry_boundary_gap_audit.jsonl",
        "p596_external_data_source_registry_boundary_gap_audit_report": "reports/p596_external_data_source_registry_boundary_gap_audit_report.json",
        "p596_external_data_source_registry_boundary_gap_audit_validation_report": "reports/p596_external_data_source_registry_boundary_gap_audit_validation_report.json",
        "p597_operator_review_status_boundary_gap_audit": "datasets/governance/p597_operator_review_status_boundary_gap_audit.jsonl",
        "p597_operator_review_status_boundary_gap_audit_report": "reports/p597_operator_review_status_boundary_gap_audit_report.json",
        "p597_operator_review_status_boundary_gap_audit_validation_report": "reports/p597_operator_review_status_boundary_gap_audit_validation_report.json",
        "p598_human_review_release_consistency_boundary_gap_audit": "datasets/governance/p598_human_review_release_consistency_boundary_gap_audit.jsonl",
        "p598_human_review_release_consistency_boundary_gap_audit_report": "reports/p598_human_review_release_consistency_boundary_gap_audit_report.json",
        "p598_human_review_release_consistency_boundary_gap_audit_validation_report": "reports/p598_human_review_release_consistency_boundary_gap_audit_validation_report.json",
        "p599_claim_promotion_decision_boundary_gap_audit": "datasets/governance/p599_claim_promotion_decision_boundary_gap_audit.jsonl",
        "p599_claim_promotion_decision_boundary_gap_audit_report": "reports/p599_claim_promotion_decision_boundary_gap_audit_report.json",
        "p599_claim_promotion_decision_boundary_gap_audit_validation_report": "reports/p599_claim_promotion_decision_boundary_gap_audit_validation_report.json",
        "p600_claim_readiness_policy_current_boundary_gap_audit": "datasets/governance/p600_claim_readiness_policy_current_boundary_gap_audit.jsonl",
        "p600_claim_readiness_policy_current_boundary_gap_audit_report": "reports/p600_claim_readiness_policy_current_boundary_gap_audit_report.json",
        "p600_claim_readiness_policy_current_boundary_gap_audit_validation_report": "reports/p600_claim_readiness_policy_current_boundary_gap_audit_validation_report.json",
        "human_review_launch_board_report": "reports/human_review_launch_board_report.json",
        "human_review_launch_board_validation_report": "reports/human_review_launch_board_validation_report.json",
        "human_review_closeout_board_report": "reports/human_review_closeout_board_report.json",
        "human_review_closeout_board_validation_report": "reports/human_review_closeout_board_validation_report.json",
        "human_review_release_consistency_validation_report": "reports/human_review_release_consistency_validation_report.json",
        "next_unlock_plan": "reports/next_unlock_plan.json",
        "next_unlock_execution_board": "reports/next_unlock_execution_board.json",
        "next_unlock_execution_validation": "reports/next_unlock_execution_validation_report.json",
        "next_unlock_operator_index": "reports/next_unlock_operator_index.json",
        "next_unlock_blocker_matrix": "reports/next_unlock_blocker_matrix.json",
        "next_unlock_remediation_queue": "reports/next_unlock_remediation_queue.json",
        "next_unlock_multi_agent_launch_board": "reports/next_unlock_multi_agent_launch_board.json",
        "next_unlock_multi_agent_launch_validation": "reports/next_unlock_multi_agent_launch_validation_report.json",
        "pending_stage_all_started_board": "reports/pending_stage_all_started_board.json",
        "pending_stage_all_started_board_validation": "reports/pending_stage_all_started_board_validation_report.json",
        "active_stage_execution_matrix": "reports/active_stage_execution_matrix_report.json",
        "active_stage_execution_matrix_validation": "reports/active_stage_execution_matrix_validation_report.json",
        "next_unlock_agent_lane_status": "reports/next_unlock_agent_lane_status_report.json",
        "next_unlock_lane_dispatch_packets": "reports/next_unlock_lane_dispatch_packet_report.json",
        "next_unlock_lane_dispatch_validation": "reports/next_unlock_lane_dispatch_validation_report.json",
        "next_unlock_action_checklist": "reports/next_unlock_action_checklist_report.json",
        "next_unlock_action_checklist_validation": "reports/next_unlock_action_checklist_validation_report.json",
        "next_unlock_operator_work_ledger": "reports/next_unlock_operator_work_ledger_report.json",
        "next_unlock_operator_work_ledger_validation": "reports/next_unlock_operator_work_ledger_validation_report.json",
        "next_unlock_operator_work_receipts": "reports/next_unlock_operator_work_receipt_report.json",
        "next_unlock_operator_work_receipt_validation": "reports/next_unlock_operator_work_receipt_validation_report.json",
        "operator_work_receipt_manifest_consistency_validation_report": "reports/operator_work_receipt_manifest_consistency_validation_report.json",
        "enzyme_analysis_constraint_policy": "reports/enzyme_analysis_constraint_policy_report.json",
        "model_quality_unlock_requirements": "reports/model_quality_unlock_requirements_report.json",
        "advanced_model_architecture": "reports/advanced_model_architecture_report.json",
        "advanced_model_scaffold_regression_report": "reports/advanced_model_scaffold_regression_report.json",
        "advanced_feature_cache_plan": "reports/advanced_feature_cache_plan_report.json",
        "advanced_feature_cache_manifest": "reports/advanced_feature_cache_manifest.json",
        "enzyme_action_space_registry": "datasets/governance/enzyme_action_space_registry.jsonl",
        "enzyme_tool_contracts": "datasets/governance/enzyme_tool_contracts.jsonl",
        "enzyme_agent_state_checkpoints": "datasets/governance/enzyme_agent_state_checkpoints.jsonl",
        "enzyme_agent_execution_protocol": "contracts/enzyme_agent_execution_protocol.md",
        "enzyme_resource_retrieval_plan_schema": "schemas/enzyme_resource_retrieval_plan.schema.json",
        "enzyme_agent_state_checkpoint_schema": "schemas/enzyme_agent_state_checkpoint.schema.json",
        "enzyme_agent_result_schema": "schemas/enzyme_agent_result.schema.json",
        "enzyme_agent_execution_receipt_schema": "schemas/enzyme_agent_execution_receipt.schema.json",
        "enzyme_action_space_registry_report": "reports/enzyme_action_space_registry_report.json",
        "enzyme_tool_contract_validation_report": "reports/enzyme_tool_contract_validation_report.json",
        "enzyme_resource_retrieval_plan_report": "reports/enzyme_resource_retrieval_plan_report.json",
        "enzyme_resource_retrieval_plan_validation_report": "reports/enzyme_resource_retrieval_plan_validation_report.json",
        "enzyme_agent_result_template": "reports/enzyme_agent_result_template.json",
        "enzyme_agent_result_validation_report": "reports/enzyme_agent_result_validation_report.json",
        "enzyme_agent_result_safety_regression_cases": "datasets/governance/enzyme_agent_result_safety_regression_cases.jsonl",
        "enzyme_agent_result_safety_regression_report": "reports/enzyme_agent_result_safety_regression_report.json",
        "enzyme_agent_trace_audit": "datasets/governance/enzyme_agent_trace_audit.jsonl",
        "enzyme_agent_trace_audit_report": "reports/enzyme_agent_trace_audit_report.json",
        "enzyme_agent_trace_audit_validation_report": "reports/enzyme_agent_trace_audit_validation_report.json",
        "enzyme_agent_controlled_release_guard_order_validation_report": "reports/enzyme_agent_controlled_release_guard_order_validation_report.json",
        "enzyme_agent_controlled_release_guard_order_regression_report": "reports/enzyme_agent_controlled_release_guard_order_regression_report.json",
        "enzyme_agent_controlled_release_guard_order_current_validation_report": "reports/enzyme_agent_controlled_release_guard_order_current_validation_report.json",
        "enzyme_agent_controlled_release_guard_order_current_regression_report": "reports/enzyme_agent_controlled_release_guard_order_current_regression_report.json",
        "enzyme_agent_controlled_release_guard_order_atomicity_regression_report": "reports/enzyme_agent_controlled_release_guard_order_atomicity_regression_report.json",
        "enzyme_agent_controlled_execution_wave_pair_atomicity_regression_report": "reports/enzyme_agent_controlled_execution_wave_pair_atomicity_regression_report.json",
        "enzyme_agent_execution_receipt_proof_current_validation_report": "reports/enzyme_agent_execution_receipt_proof_current_validation_report.json",
        "enzyme_agent_execution_receipt_proof_current_regression_report": "reports/enzyme_agent_execution_receipt_proof_current_regression_report.json",
        "enzyme_agent_controlled_execution_wave_report": "reports/enzyme_agent_controlled_execution_wave_report.json",
        "enzyme_know_how_retrieval_execution_report": "reports/enzyme_know_how_retrieval_execution_report.json",
        "enzyme_agent_execution_receipts_template": "datasets/governance/enzyme_agent_execution_receipts.template.jsonl",
        "enzyme_agent_execution_receipts_local": "datasets/governance/enzyme_agent_execution_receipts.local.jsonl",
        "enzyme_agent_execution_receipt_safety_regression_cases": "datasets/governance/enzyme_agent_execution_receipt_safety_regression_cases.jsonl",
        "enzyme_agent_execution_receipt_gate_report": "reports/enzyme_agent_execution_receipt_gate_report.json",
        "enzyme_agent_execution_receipt_gate_validation_report": "reports/enzyme_agent_execution_receipt_gate_validation_report.json",
        "enzyme_agent_execution_receipt_lineage_validation_report": "reports/enzyme_agent_execution_receipt_lineage_validation_report.json",
        "enzyme_agent_execution_receipt_safety_regression_report": "reports/enzyme_agent_execution_receipt_safety_regression_report.json",
        "enzyme_agent_execution_eligibility_matrix": "datasets/governance/enzyme_agent_execution_eligibility_matrix.jsonl",
        "enzyme_agent_execution_eligibility_safety_regression_cases": "datasets/governance/enzyme_agent_execution_eligibility_safety_regression_cases.jsonl",
        "enzyme_agent_execution_eligibility_matrix_report": "reports/enzyme_agent_execution_eligibility_matrix_report.json",
        "enzyme_agent_execution_eligibility_matrix_validation_report": "reports/enzyme_agent_execution_eligibility_matrix_validation_report.json",
        "enzyme_agent_execution_eligibility_safety_regression_report": "reports/enzyme_agent_execution_eligibility_safety_regression_report.json",
        "enzyme_agent_execution_outcome_dashboard": "datasets/governance/enzyme_agent_execution_outcome_dashboard.jsonl",
        "enzyme_agent_execution_outcome_dashboard_report": "reports/enzyme_agent_execution_outcome_dashboard_report.json",
        "enzyme_agent_execution_outcome_dashboard_validation_report": "reports/enzyme_agent_execution_outcome_dashboard_validation_report.json",
        "validated_feature_index": "datasets/features/validated_feature_index.jsonl",
        "validated_feature_index_report": "reports/validated_feature_index_report.json",
        "validated_feature_index_validation_report": "reports/validated_feature_index_validation_report.json",
        "feature_coverage_by_head_group": "datasets/features/feature_coverage_by_head_group.jsonl",
        "feature_coverage_by_head_group_report": "reports/feature_coverage_by_head_group_report.json",
        "feature_coverage_by_head_group_validation_report": "reports/feature_coverage_by_head_group_validation_report.json",
        "feature_coverage_gap_queue": "datasets/features/feature_coverage_gap_queue.jsonl",
        "feature_coverage_gap_queue_report": "reports/feature_coverage_gap_queue_report.json",
        "feature_coverage_gap_queue_validation_report": "reports/feature_coverage_gap_queue_validation_report.json",
        "p26_p31_pending_backlog_all_started_actions": "datasets/governance/p26_p31_pending_backlog_all_started_actions.jsonl",
        "p26_p31_pending_backlog_all_started_board": "reports/p26_p31_pending_backlog_all_started_board.json",
        "p26_p31_pending_backlog_all_started_board_validation_report": "reports/p26_p31_pending_backlog_all_started_board_validation_report.json",
        "p26_p31_remaining_build_start_actions": "datasets/governance/p26_p31_remaining_build_start_actions.jsonl",
        "p26_p31_remaining_build_start_board": "reports/p26_p31_remaining_build_start_board.json",
        "p26_p31_remaining_build_start_board_validation_report": "reports/p26_p31_remaining_build_start_board_validation_report.json",
        "plate_intake_schema_gap_audit": "datasets/feedback/plate_intake_schema_gap_audit.jsonl",
        "plate_intake_schema_gap_audit_report": "reports/plate_intake_schema_gap_audit_report.json",
        "plate_intake_schema_gap_audit_validation_report": "reports/plate_intake_schema_gap_audit_validation_report.json",
        "p28_feedback_intake_gap_audit": "datasets/feedback/p28_feedback_intake_gap_audit.jsonl",
        "p28_feedback_intake_gap_audit_report": "reports/p28_feedback_intake_gap_audit_report.json",
        "p28_feedback_intake_gap_audit_validation_report": "reports/p28_feedback_intake_gap_audit_validation_report.json",
        "p30_acceptance_governance_gap_audit": "datasets/governance/p30_acceptance_governance_gap_audit.jsonl",
        "p30_acceptance_governance_gap_audit_report": "reports/p30_acceptance_governance_gap_audit_report.json",
        "p30_acceptance_governance_gap_audit_validation_report": "reports/p30_acceptance_governance_gap_audit_validation_report.json",
        "p26_numbering_formal_review_gap_audit": "datasets/curation/p26_numbering_formal_review_gap_audit.jsonl",
        "p26_numbering_formal_review_gap_audit_report": "reports/p26_numbering_formal_review_gap_audit_report.json",
        "p26_numbering_formal_review_gap_audit_validation_report": "reports/p26_numbering_formal_review_gap_audit_validation_report.json",
        "p26_structure_chain_formal_review_gap_audit": "datasets/curation/p26_structure_chain_formal_review_gap_audit.jsonl",
        "p26_structure_chain_formal_review_gap_audit_report": "reports/p26_structure_chain_formal_review_gap_audit_report.json",
        "p26_structure_chain_formal_review_gap_audit_validation_report": "reports/p26_structure_chain_formal_review_gap_audit_validation_report.json",
        "p27_feature_input_boundary_gap_audit": "datasets/features/p27_feature_input_boundary_gap_audit.jsonl",
        "p27_feature_input_boundary_gap_audit_report": "reports/p27_feature_input_boundary_gap_audit_report.json",
        "p27_feature_input_boundary_gap_audit_validation_report": "reports/p27_feature_input_boundary_gap_audit_validation_report.json",
        "p28_feedback_source_review_gap_audit": "datasets/feedback/p28_feedback_source_review_gap_audit.jsonl",
        "p28_feedback_source_review_gap_audit_report": "reports/p28_feedback_source_review_gap_audit_report.json",
        "p28_feedback_source_review_gap_audit_validation_report": "reports/p28_feedback_source_review_gap_audit_validation_report.json",
        "p29_five_head_training_gap_audit": "datasets/governance/p29_five_head_training_gap_audit.jsonl",
        "p29_five_head_training_gap_audit_report": "reports/p29_five_head_training_gap_audit_report.json",
        "p29_five_head_training_gap_audit_validation_report": "reports/p29_five_head_training_gap_audit_validation_report.json",
        "p31_production_execution_gap_audit": "datasets/governance/p31_production_execution_gap_audit.jsonl",
        "p31_production_execution_gap_audit_report": "reports/p31_production_execution_gap_audit_report.json",
        "p31_production_execution_gap_audit_validation_report": "reports/p31_production_execution_gap_audit_validation_report.json",
        "advanced_model_feature_contract_report": "reports/advanced_model_feature_contract_report.json",
        "advanced_model_feature_contract_validation_report": "reports/advanced_model_feature_contract_validation_report.json",
        "google_github_advanced_model_research": "reports/google_github_advanced_model_research_2026_07_28.json",
        "proteinmcp_deep_research": "reports/proteinmcp_deep_research_2026_07_31.json",
        "proteinmcp_deep_research_markdown": "platform_integration/proteinmcp_deep_research_2026_07_31.md",
        "proteinmcp_source_download_audit": "reports/proteinmcp_source_download_audit_2026_07_31.json",
        "proteinmcp_source_download_audit_markdown": "platform_integration/proteinmcp_source_download_audit_2026_07_31.md",
        "kwb_tool_lifecycle_registry": "datasets/governance/kwb_tool_lifecycle_registry.jsonl",
        "kwb_tool_lifecycle_registry_report": "reports/kwb_tool_lifecycle_registry_report.json",
        "kwb_tool_lifecycle_registry_validation": "reports/kwb_tool_lifecycle_registry_validation_report.json",
        "kwb_workflow_skill_registry": "datasets/governance/kwb_workflow_skill_registry.jsonl",
        "kwb_workflow_skill_registry_report": "reports/kwb_workflow_skill_registry_report.json",
        "kwb_workflow_skill_registry_validation": "reports/kwb_workflow_skill_registry_validation_report.json",
        "kwb_workflow_skill_enzyme_mutation_prioritization": "platform_integration/workflow_skills/enzyme_mutation_prioritization.md",
        "kwb_workflow_skill_ddg_backend_runtime_probe": "platform_integration/workflow_skills/ddg_backend_runtime_probe.md",
        "kwb_workflow_skill_wet_lab_feedback_intake_review": "platform_integration/workflow_skills/wet_lab_feedback_intake_review.md",
        "kwb_workflow_skill_numbering_review_formalization": "platform_integration/workflow_skills/numbering_review_formalization.md",
        "kwb_workflow_skill_five_head_model_gate_review": "platform_integration/workflow_skills/five_head_model_gate_review.md",
        "mcp_wrapper_staging_schema": "contracts/mcp_wrapper_staging.schema.json",
        "mcp_wrapper_staging_queue": "datasets/governance/mcp_wrapper_staging_queue.jsonl",
        "mcp_wrapper_staging_gate_report": "reports/mcp_wrapper_staging_gate_report.json",
        "mcp_wrapper_staging_gate_validation": "reports/mcp_wrapper_staging_gate_validation_report.json",
        "top_tier_model_execution_board": "reports/top_tier_model_execution_board.json",
        "top_tier_model_execution_validation": "reports/top_tier_model_execution_validation_report.json",
        "top_tier_model_ready_to_verify_receipt_report": "reports/top_tier_model_ready_to_verify_receipt_report.json",
        "top_tier_model_ready_to_verify_receipt_validation": "reports/top_tier_model_ready_to_verify_receipt_validation_report.json",
        "non_human_construction_board": "reports/non_human_construction_board.json",
        "non_human_construction_validation": "reports/non_human_construction_validation_report.json",
        "non_human_ready_to_verify_receipt_report": "reports/non_human_ready_to_verify_receipt_report.json",
        "non_human_ready_to_verify_receipt_validation": "reports/non_human_ready_to_verify_receipt_validation_report.json",
        "ready_to_verify_promotion_board": "reports/ready_to_verify_promotion_board.json",
        "ready_to_verify_promotion_validation": "reports/ready_to_verify_promotion_validation_report.json",
        "ready_to_verify_promotion_safety_regression": "reports/ready_to_verify_promotion_safety_regression_report.json",
        "ready_to_verify_promotion_release_summary_regression": "reports/local_release_promotion_summary_safety_regression_report.json",
        "data_lake_artifact_integrity_regression": "reports/data_lake_artifact_integrity_regression_report.json",
        "local_release_high_risk_summary_safety_regression": "reports/local_release_high_risk_summary_safety_regression_report.json",
        "local_release_high_risk_coverage_safety_regression": "reports/local_release_high_risk_coverage_safety_regression_report.json",
        "data_lake_live_content_integrity_validation": "reports/data_lake_live_content_integrity_validation_report.json",
        "data_lake_live_content_integrity_regression": "reports/data_lake_live_content_integrity_regression_report.json",
        "data_lake_volatile_exemption_safety_regression": "reports/data_lake_volatile_exemption_safety_regression_report.json",
        "local_release_live_integrity_binding_regression": "reports/local_release_live_integrity_binding_regression_report.json",
        "data_lake_release_input_contract_policy_validation": "reports/data_lake_release_input_contract_policy_validation_report.json",
        "data_lake_release_input_contract_policy_regression": "reports/data_lake_release_input_contract_policy_regression_report.json",
        "local_release_contract_policy_binding_regression": "reports/local_release_contract_policy_binding_regression_report.json",
        "stage25_operator_docs_dynamic_status_sync": "reports/stage25_operator_docs_dynamic_status_sync_report.json",
        "stage25_operator_docs_dynamic_status_sync_regression": "reports/stage25_operator_docs_dynamic_status_sync_regression_report.json",
        "stage25_operator_docs_dynamic_status_sync_regression_current": "reports/stage25_operator_docs_dynamic_status_sync_regression_current_validation_report.json",
        "stage25_operator_docs_dynamic_status_sync_regression_current_regression": "reports/stage25_operator_docs_dynamic_status_sync_regression_current_regression_report.json",
        "stage25_operator_docs_dynamic_status_sync_regression_atomicity_regression": "reports/stage25_operator_docs_dynamic_status_sync_regression_atomicity_regression_report.json",
        "stage25_operator_docs_sync_contract_policy_validation": "reports/stage25_operator_docs_sync_contract_policy_validation_report.json",
        "stage25_operator_docs_sync_contract_policy_regression": "reports/stage25_operator_docs_sync_contract_policy_regression_report.json",
        "stage25_operator_docs_sync_current_receipt_validation": "reports/stage25_operator_docs_sync_current_receipt_validation_report.json",
        "stage25_operator_docs_sync_current_receipt_regression": "reports/stage25_operator_docs_sync_current_receipt_regression_report.json",
        "stage25_operator_docs_sync_terminal_recovery_regression": "reports/stage25_operator_docs_sync_terminal_recovery_regression_report.json",
        "p601_structure_feature_hard_gate_operator_packet_boundary_gap_audit_report": "reports/p601_structure_feature_hard_gate_operator_packet_boundary_gap_audit_report.json",
        "p601_structure_feature_hard_gate_operator_packet_boundary_gap_audit_validation_report": "reports/p601_structure_feature_hard_gate_operator_packet_boundary_gap_audit_validation_report.json",
        "p602_wet_lab_hard_gate_operator_packet_boundary_gap_audit_report": "reports/p602_wet_lab_hard_gate_operator_packet_boundary_gap_audit_report.json",
        "p602_wet_lab_hard_gate_operator_packet_boundary_gap_audit_validation_report": "reports/p602_wet_lab_hard_gate_operator_packet_boundary_gap_audit_validation_report.json",
        "p603_benchmark_hard_gate_operator_packet_boundary_gap_audit_report": "reports/p603_benchmark_hard_gate_operator_packet_boundary_gap_audit_report.json",
        "p603_benchmark_hard_gate_operator_packet_boundary_gap_audit_validation_report": "reports/p603_benchmark_hard_gate_operator_packet_boundary_gap_audit_validation_report.json",
        "p604_substrate_fit_hard_gate_operator_packet_boundary_gap_audit_report": "reports/p604_substrate_fit_hard_gate_operator_packet_boundary_gap_audit_report.json",
        "p604_substrate_fit_hard_gate_operator_packet_boundary_gap_audit_validation_report": "reports/p604_substrate_fit_hard_gate_operator_packet_boundary_gap_audit_validation_report.json",
        "p605_review_draft_formal_boundary_gap_audit_report": "reports/p605_review_draft_formal_boundary_gap_audit_report.json",
        "p605_review_draft_formal_boundary_gap_audit_validation_report": "reports/p605_review_draft_formal_boundary_gap_audit_validation_report.json",
        "p606_activity_risk_formal_label_decision_boundary_gap_audit": "datasets/governance/p606_activity_risk_formal_label_decision_boundary_gap_audit.jsonl",
        "p606_activity_risk_formal_label_decision_boundary_gap_audit_report": "reports/p606_activity_risk_formal_label_decision_boundary_gap_audit_report.json",
        "p606_activity_risk_formal_label_decision_boundary_gap_audit_validation_report": "reports/p606_activity_risk_formal_label_decision_boundary_gap_audit_validation_report.json",
        "p607_activity_risk_training_lineage_boundary_gap_audit": "datasets/governance/p607_activity_risk_training_lineage_boundary_gap_audit.jsonl",
        "p607_activity_risk_training_lineage_boundary_gap_audit_report": "reports/p607_activity_risk_training_lineage_boundary_gap_audit_report.json",
        "p607_activity_risk_training_lineage_boundary_gap_audit_validation_report": "reports/p607_activity_risk_training_lineage_boundary_gap_audit_validation_report.json",
        "p608_feedback_training_import_semantic_guard_boundary_gap_audit": "datasets/governance/p608_feedback_training_import_semantic_guard_boundary_gap_audit.jsonl",
        "p608_feedback_training_import_semantic_guard_boundary_gap_audit_report": "reports/p608_feedback_training_import_semantic_guard_boundary_gap_audit_report.json",
        "p608_feedback_training_import_semantic_guard_boundary_gap_audit_validation_report": "reports/p608_feedback_training_import_semantic_guard_boundary_gap_audit_validation_report.json",
        "p609_wet_lab_feedback_import_reconciliation_boundary_gap_audit": "datasets/governance/p609_wet_lab_feedback_import_reconciliation_boundary_gap_audit.jsonl",
        "p609_wet_lab_feedback_import_reconciliation_boundary_gap_audit_report": "reports/p609_wet_lab_feedback_import_reconciliation_boundary_gap_audit_report.json",
        "p609_wet_lab_feedback_import_reconciliation_boundary_gap_audit_validation_report": "reports/p609_wet_lab_feedback_import_reconciliation_boundary_gap_audit_validation_report.json",
        "p610_positive_claim_gate_quarantine_boundary_gap_audit": "datasets/governance/p610_positive_claim_gate_quarantine_boundary_gap_audit.jsonl",
        "p610_positive_claim_gate_quarantine_boundary_gap_audit_report": "reports/p610_positive_claim_gate_quarantine_boundary_gap_audit_report.json",
        "p610_positive_claim_gate_quarantine_boundary_gap_audit_validation_report": "reports/p610_positive_claim_gate_quarantine_boundary_gap_audit_validation_report.json",
        "p611_activity_risk_training_import_label_boundary_gap_audit": "datasets/governance/p611_activity_risk_training_import_label_boundary_gap_audit.jsonl",
        "p611_activity_risk_training_import_label_boundary_gap_audit_report": "reports/p611_activity_risk_training_import_label_boundary_gap_audit_report.json",
        "p611_activity_risk_training_import_label_boundary_gap_audit_validation_report": "reports/p611_activity_risk_training_import_label_boundary_gap_audit_validation_report.json",
        "p612_activity_risk_label_replicate_preflight_boundary_gap_audit": "datasets/governance/p612_activity_risk_label_replicate_preflight_boundary_gap_audit.jsonl",
        "p612_activity_risk_label_replicate_preflight_boundary_gap_audit_report": "reports/p612_activity_risk_label_replicate_preflight_boundary_gap_audit_report.json",
        "p612_activity_risk_label_replicate_preflight_boundary_gap_audit_validation_report": "reports/p612_activity_risk_label_replicate_preflight_boundary_gap_audit_validation_report.json",
        "p613_feature_coverage_by_head_group_boundary_gap_audit": "datasets/governance/p613_feature_coverage_by_head_group_boundary_gap_audit.jsonl",
        "p613_feature_coverage_by_head_group_boundary_gap_audit_report": "reports/p613_feature_coverage_by_head_group_boundary_gap_audit_report.json",
        "p613_feature_coverage_by_head_group_boundary_gap_audit_validation_report": "reports/p613_feature_coverage_by_head_group_boundary_gap_audit_validation_report.json",
        "p614_feature_coverage_gap_queue_boundary_gap_audit": "datasets/governance/p614_feature_coverage_gap_queue_boundary_gap_audit.jsonl",
        "p614_feature_coverage_gap_queue_boundary_gap_audit_report": "reports/p614_feature_coverage_gap_queue_boundary_gap_audit_report.json",
        "p614_feature_coverage_gap_queue_boundary_gap_audit_validation_report": "reports/p614_feature_coverage_gap_queue_boundary_gap_audit_validation_report.json",
        "p615_feature_label_boundary_quarantine_gap_audit": "datasets/governance/p615_feature_label_boundary_quarantine_gap_audit.jsonl",
        "p615_feature_label_boundary_quarantine_gap_audit_report": "reports/p615_feature_label_boundary_quarantine_gap_audit_report.json",
        "p615_feature_label_boundary_quarantine_gap_audit_validation_report": "reports/p615_feature_label_boundary_quarantine_gap_audit_validation_report.json",
        "p616_benchmark_score_cache_validation_boundary_gap_audit": "datasets/governance/p616_benchmark_score_cache_validation_boundary_gap_audit.jsonl",
        "p616_benchmark_score_cache_validation_boundary_gap_audit_report": "reports/p616_benchmark_score_cache_validation_boundary_gap_audit_report.json",
        "p616_benchmark_score_cache_validation_boundary_gap_audit_validation_report": "reports/p616_benchmark_score_cache_validation_boundary_gap_audit_validation_report.json",
        "p617_benchmark_coverage_dashboard_boundary_gap_audit": "datasets/governance/p617_benchmark_coverage_dashboard_boundary_gap_audit.jsonl",
        "p617_benchmark_coverage_dashboard_boundary_gap_audit_report": "reports/p617_benchmark_coverage_dashboard_boundary_gap_audit_report.json",
        "p617_benchmark_coverage_dashboard_boundary_gap_audit_validation_report": "reports/p617_benchmark_coverage_dashboard_boundary_gap_audit_validation_report.json",
        "p618_five_head_benchmark_gap_plan_boundary_gap_audit": "datasets/governance/p618_five_head_benchmark_gap_plan_boundary_gap_audit.jsonl",
        "p618_five_head_benchmark_gap_plan_boundary_gap_audit_report": "reports/p618_five_head_benchmark_gap_plan_boundary_gap_audit_report.json",
        "p618_five_head_benchmark_gap_plan_boundary_gap_audit_validation_report": "reports/p618_five_head_benchmark_gap_plan_boundary_gap_audit_validation_report.json",
        "p619_benchmark_lane_machine_prereview_boundary_gap_audit": "datasets/governance/p619_benchmark_lane_machine_prereview_boundary_gap_audit.jsonl",
        "p619_benchmark_lane_machine_prereview_boundary_gap_audit_report": "reports/p619_benchmark_lane_machine_prereview_boundary_gap_audit_report.json",
        "p619_benchmark_lane_machine_prereview_boundary_gap_audit_validation_report": "reports/p619_benchmark_lane_machine_prereview_boundary_gap_audit_validation_report.json",
        "p620_benchmark_lane_status_aggregate_boundary_gap_audit": "datasets/governance/p620_benchmark_lane_status_aggregate_boundary_gap_audit.jsonl",
        "p620_benchmark_lane_status_aggregate_boundary_gap_audit_report": "reports/p620_benchmark_lane_status_aggregate_boundary_gap_audit_report.json",
        "p620_benchmark_lane_status_aggregate_boundary_gap_audit_validation_report": "reports/p620_benchmark_lane_status_aggregate_boundary_gap_audit_validation_report.json",
        "p621_ddg_executable_probe_boundary_gap_audit": "datasets/governance/p621_ddg_executable_probe_boundary_gap_audit.jsonl",
        "p621_ddg_executable_probe_boundary_gap_audit_report": "reports/p621_ddg_executable_probe_boundary_gap_audit_report.json",
        "p621_ddg_executable_probe_boundary_gap_audit_validation_report": "reports/p621_ddg_executable_probe_boundary_gap_audit_validation_report.json",
        "p622_pyrosetta_physical_smoke_boundary_gap_audit": "datasets/governance/p622_pyrosetta_physical_smoke_boundary_gap_audit.jsonl",
        "p622_pyrosetta_physical_smoke_boundary_gap_audit_report": "reports/p622_pyrosetta_physical_smoke_boundary_gap_audit_report.json",
        "p622_pyrosetta_physical_smoke_boundary_gap_audit_validation_report": "reports/p622_pyrosetta_physical_smoke_boundary_gap_audit_validation_report.json",
        "p623_pyrosetta_verified_ddg_feature_boundary_gap_audit": "datasets/governance/p623_pyrosetta_verified_ddg_feature_boundary_gap_audit.jsonl",
        "p623_pyrosetta_verified_ddg_feature_boundary_gap_audit_report": "reports/p623_pyrosetta_verified_ddg_feature_boundary_gap_audit_report.json",
        "p623_pyrosetta_verified_ddg_feature_boundary_gap_audit_validation_report": "reports/p623_pyrosetta_verified_ddg_feature_boundary_gap_audit_validation_report.json",
        "p624_foldx_physical_smoke_boundary_gap_audit": "datasets/governance/p624_foldx_physical_smoke_boundary_gap_audit.jsonl",
        "p624_foldx_physical_smoke_boundary_gap_audit_report": "reports/p624_foldx_physical_smoke_boundary_gap_audit_report.json",
        "p624_foldx_physical_smoke_boundary_gap_audit_validation_report": "reports/p624_foldx_physical_smoke_boundary_gap_audit_validation_report.json",
        "p625_ddg_backend_operator_packet_boundary_gap_audit": "datasets/governance/p625_ddg_backend_operator_packet_boundary_gap_audit.jsonl",
        "p625_ddg_backend_operator_packet_boundary_gap_audit_report": "reports/p625_ddg_backend_operator_packet_boundary_gap_audit_report.json",
        "p625_ddg_backend_operator_packet_boundary_gap_audit_validation_report": "reports/p625_ddg_backend_operator_packet_boundary_gap_audit_validation_report.json",
        "p626_rosetta_physical_smoke_boundary_gap_audit": "datasets/governance/p626_rosetta_physical_smoke_boundary_gap_audit.jsonl",
        "p626_rosetta_physical_smoke_boundary_gap_audit_report": "reports/p626_rosetta_physical_smoke_boundary_gap_audit_report.json",
        "p626_rosetta_physical_smoke_boundary_gap_audit_validation_report": "reports/p626_rosetta_physical_smoke_boundary_gap_audit_validation_report.json",
        "p627_pyrosetta_verified_mutation_ddg_concordance_boundary_gap_audit": "datasets/governance/p627_pyrosetta_verified_mutation_ddg_concordance_boundary_gap_audit.jsonl",
        "p627_pyrosetta_verified_mutation_ddg_concordance_boundary_gap_audit_report": "reports/p627_pyrosetta_verified_mutation_ddg_concordance_boundary_gap_audit_report.json",
        "p627_pyrosetta_verified_mutation_ddg_concordance_boundary_gap_audit_validation_report": "reports/p627_pyrosetta_verified_mutation_ddg_concordance_boundary_gap_audit_validation_report.json",
        "p628_pyrosetta_local_install_probe_boundary_gap_audit": "datasets/governance/p628_pyrosetta_local_install_probe_boundary_gap_audit.jsonl",
        "p628_pyrosetta_local_install_probe_boundary_gap_audit_report": "reports/p628_pyrosetta_local_install_probe_boundary_gap_audit_report.json",
        "p628_pyrosetta_local_install_probe_boundary_gap_audit_validation_report": "reports/p628_pyrosetta_local_install_probe_boundary_gap_audit_validation_report.json",
        "p629_ddg_physical_runtime_receipt_preflight_boundary_gap_audit": "datasets/governance/p629_ddg_physical_runtime_receipt_preflight_boundary_gap_audit.jsonl",
        "p629_ddg_physical_runtime_receipt_preflight_boundary_gap_audit_report": "reports/p629_ddg_physical_runtime_receipt_preflight_boundary_gap_audit_report.json",
        "p629_ddg_physical_runtime_receipt_preflight_boundary_gap_audit_validation_report": "reports/p629_ddg_physical_runtime_receipt_preflight_boundary_gap_audit_validation_report.json",
        "p630_ddg_backend_runtime_receipt_validation_boundary_gap_audit": "datasets/governance/p630_ddg_backend_runtime_receipt_validation_boundary_gap_audit.jsonl",
        "p630_ddg_backend_runtime_receipt_validation_boundary_gap_audit_report": "reports/p630_ddg_backend_runtime_receipt_validation_boundary_gap_audit_report.json",
        "p630_ddg_backend_runtime_receipt_validation_boundary_gap_audit_validation_report": "reports/p630_ddg_backend_runtime_receipt_validation_boundary_gap_audit_validation_report.json",
        "p631_ddg_physical_smoke_harness_boundary_gap_audit": "datasets/governance/p631_ddg_physical_smoke_harness_boundary_gap_audit.jsonl",
        "p631_ddg_physical_smoke_harness_boundary_gap_audit_report": "reports/p631_ddg_physical_smoke_harness_boundary_gap_audit_report.json",
        "p631_ddg_physical_smoke_harness_boundary_gap_audit_validation_report": "reports/p631_ddg_physical_smoke_harness_boundary_gap_audit_validation_report.json",
        "p632_ddg_proxy_physics_claim_boundary_gap_audit": "datasets/governance/p632_ddg_proxy_physics_claim_boundary_gap_audit.jsonl",
        "p632_ddg_proxy_physics_claim_boundary_gap_audit_report": "reports/p632_ddg_proxy_physics_claim_boundary_gap_audit_report.json",
        "p632_ddg_proxy_physics_claim_boundary_gap_audit_validation_report": "reports/p632_ddg_proxy_physics_claim_boundary_gap_audit_validation_report.json",
        "p633_execution_receipt_freshness_boundary_gap_audit": "datasets/governance/p633_execution_receipt_freshness_boundary_gap_audit.jsonl",
        "p633_execution_receipt_freshness_boundary_gap_audit_report": "reports/p633_execution_receipt_freshness_boundary_gap_audit_report.json",
        "p633_execution_receipt_freshness_boundary_gap_audit_validation_report": "reports/p633_execution_receipt_freshness_boundary_gap_audit_validation_report.json",
        "p634_parallel_hard_gate_execution_boundary_gap_audit": "datasets/governance/p634_parallel_hard_gate_execution_boundary_gap_audit.jsonl",
        "p634_parallel_hard_gate_execution_boundary_gap_audit_report": "reports/p634_parallel_hard_gate_execution_boundary_gap_audit_report.json",
        "p634_parallel_hard_gate_execution_boundary_gap_audit_validation_report": "reports/p634_parallel_hard_gate_execution_boundary_gap_audit_validation_report.json",
        "p635_ddg_backend_failure_boundary_gap_audit": "datasets/governance/p635_ddg_backend_failure_boundary_gap_audit.jsonl",
        "p635_ddg_backend_failure_boundary_gap_audit_report": "reports/p635_ddg_backend_failure_boundary_gap_audit_report.json",
        "p635_ddg_backend_failure_boundary_gap_audit_validation_report": "reports/p635_ddg_backend_failure_boundary_gap_audit_validation_report.json",
        "p636_human_review_closeout_current_boundary_gap_audit": "datasets/governance/p636_human_review_closeout_current_boundary_gap_audit.jsonl",
        "p636_human_review_closeout_current_boundary_gap_audit_report": "reports/p636_human_review_closeout_current_boundary_gap_audit_report.json",
        "p636_human_review_closeout_current_boundary_gap_audit_validation_report": "reports/p636_human_review_closeout_current_boundary_gap_audit_validation_report.json",
        "p637_operator_work_receipt_manifest_current_boundary_gap_audit": "datasets/governance/p637_operator_work_receipt_manifest_current_boundary_gap_audit.jsonl",
        "p637_operator_work_receipt_manifest_current_boundary_gap_audit_report": "reports/p637_operator_work_receipt_manifest_current_boundary_gap_audit_report.json",
        "p637_operator_work_receipt_manifest_current_boundary_gap_audit_validation_report": "reports/p637_operator_work_receipt_manifest_current_boundary_gap_audit_validation_report.json",
        "p638_top_tier_ready_to_verify_current_boundary_gap_audit": "datasets/governance/p638_top_tier_ready_to_verify_current_boundary_gap_audit.jsonl",
        "p638_top_tier_ready_to_verify_current_boundary_gap_audit_report": "reports/p638_top_tier_ready_to_verify_current_boundary_gap_audit_report.json",
        "p638_top_tier_ready_to_verify_current_boundary_gap_audit_validation_report": "reports/p638_top_tier_ready_to_verify_current_boundary_gap_audit_validation_report.json",
        "p639_non_human_ready_to_verify_current_boundary_gap_audit": "datasets/governance/p639_non_human_ready_to_verify_current_boundary_gap_audit.jsonl",
        "p639_non_human_ready_to_verify_current_boundary_gap_audit_report": "reports/p639_non_human_ready_to_verify_current_boundary_gap_audit_report.json",
        "p639_non_human_ready_to_verify_current_boundary_gap_audit_validation_report": "reports/p639_non_human_ready_to_verify_current_boundary_gap_audit_validation_report.json",
        "p640_ready_to_verify_promotion_current_boundary_gap_audit": "datasets/governance/p640_ready_to_verify_promotion_current_boundary_gap_audit.jsonl",
        "p640_ready_to_verify_promotion_current_boundary_gap_audit_report": "reports/p640_ready_to_verify_promotion_current_boundary_gap_audit_report.json",
        "p640_ready_to_verify_promotion_current_boundary_gap_audit_validation_report": "reports/p640_ready_to_verify_promotion_current_boundary_gap_audit_validation_report.json",
        "p641_p0_today_closeout_plan": "datasets/governance/p641_p0_today_closeout_plan.jsonl",
        "p641_p0_today_closeout_plan_report": "reports/p641_p0_today_closeout_plan_report.json",
        "p641_p0_today_closeout_plan_validation_report": "reports/p641_p0_today_closeout_plan_validation_report.json",
        "p642_p0_external_input_packet_manifest": "datasets/governance/p642_p0_external_input_packet_manifest.jsonl",
        "p642_p0_external_input_packet_manifest_report": "reports/p642_p0_external_input_packet_manifest_report.json",
        "p642_p0_external_input_packet_manifest_validation_report": "reports/p642_p0_external_input_packet_manifest_validation_report.json",
        "p643_p0_external_input_dispatch_board": "datasets/governance/p643_p0_external_input_dispatch_board.jsonl",
        "p643_p0_external_input_dispatch_board_report": "reports/p643_p0_external_input_dispatch_board_report.json",
        "p643_p0_external_input_dispatch_board_validation_report": "reports/p643_p0_external_input_dispatch_board_validation_report.json",
        "p644_p0_external_input_handoff_receipt_board": "datasets/governance/p644_p0_external_input_handoff_receipt_board.jsonl",
        "p644_p0_external_input_handoff_receipt_board_report": "reports/p644_p0_external_input_handoff_receipt_board_report.json",
        "p644_p0_external_input_handoff_receipt_board_validation_report": "reports/p644_p0_external_input_handoff_receipt_board_validation_report.json",
        "p645_p0_external_input_response_slot_registry": "datasets/governance/p645_p0_external_input_response_slot_registry.jsonl",
        "p645_p0_external_input_response_slot_registry_report": "reports/p645_p0_external_input_response_slot_registry_report.json",
        "p645_p0_external_input_response_slot_registry_validation_report": "reports/p645_p0_external_input_response_slot_registry_validation_report.json",
        "p646_p0_external_input_response_intake_queue": "datasets/governance/p646_p0_external_input_response_intake_queue.jsonl",
        "p646_p0_external_input_response_intake_queue_report": "reports/p646_p0_external_input_response_intake_queue_report.json",
        "p646_p0_external_input_response_intake_queue_validation_report": "reports/p646_p0_external_input_response_intake_queue_validation_report.json",
        "p647_p0_external_input_response_validation_preflight": "datasets/governance/p647_p0_external_input_response_validation_preflight.jsonl",
        "p647_p0_external_input_response_validation_preflight_report": "reports/p647_p0_external_input_response_validation_preflight_report.json",
        "p647_p0_external_input_response_validation_preflight_validation_report": "reports/p647_p0_external_input_response_validation_preflight_validation_report.json",
        "p648_p0_external_input_response_schema_contract": "datasets/governance/p648_p0_external_input_response_schema_contract.jsonl",
        "p648_p0_external_input_response_schema_contract_report": "reports/p648_p0_external_input_response_schema_contract_report.json",
        "p648_p0_external_input_response_schema_contract_validation_report": "reports/p648_p0_external_input_response_schema_contract_validation_report.json",
        "p649_p0_external_input_response_evidence_quarantine": "datasets/governance/p649_p0_external_input_response_evidence_quarantine.jsonl",
        "p649_p0_external_input_response_evidence_quarantine_report": "reports/p649_p0_external_input_response_evidence_quarantine_report.json",
        "p649_p0_external_input_response_evidence_quarantine_validation_report": "reports/p649_p0_external_input_response_evidence_quarantine_validation_report.json",
        "p650_p0_external_input_response_decision_routing": "datasets/governance/p650_p0_external_input_response_decision_routing.jsonl",
        "p650_p0_external_input_response_decision_routing_report": "reports/p650_p0_external_input_response_decision_routing_report.json",
        "p650_p0_external_input_response_decision_routing_validation_report": "reports/p650_p0_external_input_response_decision_routing_validation_report.json",
        "p651_p0_external_input_formal_intake_dry_run_guard": "datasets/governance/p651_p0_external_input_formal_intake_dry_run_guard.jsonl",
        "p651_p0_external_input_formal_intake_dry_run_guard_report": "reports/p651_p0_external_input_formal_intake_dry_run_guard_report.json",
        "p651_p0_external_input_formal_intake_dry_run_guard_validation_report": "reports/p651_p0_external_input_formal_intake_dry_run_guard_validation_report.json",
        "p652_p0_external_input_closeout_readiness_gate": "datasets/governance/p652_p0_external_input_closeout_readiness_gate.jsonl",
        "p652_p0_external_input_closeout_readiness_gate_report": "reports/p652_p0_external_input_closeout_readiness_gate_report.json",
        "p652_p0_external_input_closeout_readiness_gate_validation_report": "reports/p652_p0_external_input_closeout_readiness_gate_validation_report.json",
        "p653_p0_external_input_closeout_blocker_ledger": "datasets/governance/p653_p0_external_input_closeout_blocker_ledger.jsonl",
        "p653_p0_external_input_closeout_blocker_ledger_report": "reports/p653_p0_external_input_closeout_blocker_ledger_report.json",
        "p653_p0_external_input_closeout_blocker_ledger_validation_report": "reports/p653_p0_external_input_closeout_blocker_ledger_validation_report.json",
        "p654_p0_external_input_blocker_escalation_queue": "datasets/governance/p654_p0_external_input_blocker_escalation_queue.jsonl",
        "p654_p0_external_input_blocker_escalation_queue_report": "reports/p654_p0_external_input_blocker_escalation_queue_report.json",
        "p654_p0_external_input_blocker_escalation_queue_validation_report": "reports/p654_p0_external_input_blocker_escalation_queue_validation_report.json",
        "p655_p0_external_input_blocker_escalation_status_board": "datasets/governance/p655_p0_external_input_blocker_escalation_status_board.jsonl",
        "p655_p0_external_input_blocker_escalation_status_board_report": "reports/p655_p0_external_input_blocker_escalation_status_board_report.json",
        "p655_p0_external_input_blocker_escalation_status_board_validation_report": "reports/p655_p0_external_input_blocker_escalation_status_board_validation_report.json",
        "p656_p0_external_input_blocker_escalation_watchlist": "datasets/governance/p656_p0_external_input_blocker_escalation_watchlist.jsonl",
        "p656_p0_external_input_blocker_escalation_watchlist_report": "reports/p656_p0_external_input_blocker_escalation_watchlist_report.json",
        "p656_p0_external_input_blocker_escalation_watchlist_validation_report": "reports/p656_p0_external_input_blocker_escalation_watchlist_validation_report.json",
        "p657_p0_external_input_blocker_escalation_review_queue": "datasets/governance/p657_p0_external_input_blocker_escalation_review_queue.jsonl",
        "p657_p0_external_input_blocker_escalation_review_queue_report": "reports/p657_p0_external_input_blocker_escalation_review_queue_report.json",
        "p657_p0_external_input_blocker_escalation_review_queue_validation_report": "reports/p657_p0_external_input_blocker_escalation_review_queue_validation_report.json",
        "p658_p0_external_input_blocker_escalation_review_status_board": "datasets/governance/p658_p0_external_input_blocker_escalation_review_status_board.jsonl",
        "p658_p0_external_input_blocker_escalation_review_status_board_report": "reports/p658_p0_external_input_blocker_escalation_review_status_board_report.json",
        "p658_p0_external_input_blocker_escalation_review_status_board_validation_report": "reports/p658_p0_external_input_blocker_escalation_review_status_board_validation_report.json",
        "p659_p0_external_input_blocker_escalation_review_watchlist": "datasets/governance/p659_p0_external_input_blocker_escalation_review_watchlist.jsonl",
        "p659_p0_external_input_blocker_escalation_review_watchlist_report": "reports/p659_p0_external_input_blocker_escalation_review_watchlist_report.json",
        "p659_p0_external_input_blocker_escalation_review_watchlist_validation_report": "reports/p659_p0_external_input_blocker_escalation_review_watchlist_validation_report.json",
        "p660_p0_external_input_blocker_review_watchlist_aging_audit": "datasets/governance/p660_p0_external_input_blocker_review_watchlist_aging_audit.jsonl",
        "p660_p0_external_input_blocker_review_watchlist_aging_audit_report": "reports/p660_p0_external_input_blocker_review_watchlist_aging_audit_report.json",
        "p660_p0_external_input_blocker_review_watchlist_aging_audit_validation_report": "reports/p660_p0_external_input_blocker_review_watchlist_aging_audit_validation_report.json",
        "p661_p0_external_input_blocker_review_owner_assignment_gap_audit": "datasets/governance/p661_p0_external_input_blocker_review_owner_assignment_gap_audit.jsonl",
        "p661_p0_external_input_blocker_review_owner_assignment_gap_audit_report": "reports/p661_p0_external_input_blocker_review_owner_assignment_gap_audit_report.json",
        "p661_p0_external_input_blocker_review_owner_assignment_gap_audit_validation_report": "reports/p661_p0_external_input_blocker_review_owner_assignment_gap_audit_validation_report.json",
        "p662_p0_external_input_evidence_missing_matrix": "datasets/governance/p662_p0_external_input_evidence_missing_matrix.jsonl",
        "p662_p0_external_input_evidence_missing_matrix_report": "reports/p662_p0_external_input_evidence_missing_matrix_report.json",
        "p662_p0_external_input_evidence_missing_matrix_validation_report": "reports/p662_p0_external_input_evidence_missing_matrix_validation_report.json",
        "p663_p0_formal_decision_readiness_false_positive_guard": "datasets/governance/p663_p0_formal_decision_readiness_false_positive_guard.jsonl",
        "p663_p0_formal_decision_readiness_false_positive_guard_report": "reports/p663_p0_formal_decision_readiness_false_positive_guard_report.json",
        "p663_p0_formal_decision_readiness_false_positive_guard_validation_report": "reports/p663_p0_formal_decision_readiness_false_positive_guard_validation_report.json",
        "p664_p0_closeout_non_approval_receipt_audit": "datasets/governance/p664_p0_closeout_non_approval_receipt_audit.jsonl",
        "p664_p0_closeout_non_approval_receipt_audit_report": "reports/p664_p0_closeout_non_approval_receipt_audit_report.json",
        "p664_p0_closeout_non_approval_receipt_audit_validation_report": "reports/p664_p0_closeout_non_approval_receipt_audit_validation_report.json",
        "p665_p0_closeout_non_approval_watchlist": "datasets/governance/p665_p0_closeout_non_approval_watchlist.jsonl",
        "p665_p0_closeout_non_approval_watchlist_report": "reports/p665_p0_closeout_non_approval_watchlist_report.json",
        "p665_p0_closeout_non_approval_watchlist_validation_report": "reports/p665_p0_closeout_non_approval_watchlist_validation_report.json",
        "p666_p0_closeout_owner_review_queue": "datasets/governance/p666_p0_closeout_owner_review_queue.jsonl",
        "p666_p0_closeout_owner_review_queue_report": "reports/p666_p0_closeout_owner_review_queue_report.json",
        "p666_p0_closeout_owner_review_queue_validation_report": "reports/p666_p0_closeout_owner_review_queue_validation_report.json",
        "p667_p0_formal_intake_non_write_guard_audit": "datasets/governance/p667_p0_formal_intake_non_write_guard_audit.jsonl",
        "p667_p0_formal_intake_non_write_guard_audit_report": "reports/p667_p0_formal_intake_non_write_guard_audit_report.json",
        "p667_p0_formal_intake_non_write_guard_audit_validation_report": "reports/p667_p0_formal_intake_non_write_guard_audit_validation_report.json",
        "p668_p0_training_label_non_import_guard_audit": "datasets/governance/p668_p0_training_label_non_import_guard_audit.jsonl",
        "p668_p0_training_label_non_import_guard_audit_report": "reports/p668_p0_training_label_non_import_guard_audit_report.json",
        "p668_p0_training_label_non_import_guard_audit_validation_report": "reports/p668_p0_training_label_non_import_guard_audit_validation_report.json",
        "p669_p0_release_claim_non_promotion_guard_audit": "datasets/governance/p669_p0_release_claim_non_promotion_guard_audit.jsonl",
        "p669_p0_release_claim_non_promotion_guard_audit_report": "reports/p669_p0_release_claim_non_promotion_guard_audit_report.json",
        "p669_p0_release_claim_non_promotion_guard_audit_validation_report": "reports/p669_p0_release_claim_non_promotion_guard_audit_validation_report.json",
        "p670_p0_release_claim_non_promotion_status_board": "datasets/governance/p670_p0_release_claim_non_promotion_status_board.jsonl",
        "p670_p0_release_claim_non_promotion_status_board_report": "reports/p670_p0_release_claim_non_promotion_status_board_report.json",
        "p670_p0_release_claim_non_promotion_status_board_validation_report": "reports/p670_p0_release_claim_non_promotion_status_board_validation_report.json",
        "p671_p0_model_claim_non_assertion_guard_audit": "datasets/governance/p671_p0_model_claim_non_assertion_guard_audit.jsonl",
        "p671_p0_model_claim_non_assertion_guard_audit_report": "reports/p671_p0_model_claim_non_assertion_guard_audit_report.json",
        "p671_p0_model_claim_non_assertion_guard_audit_validation_report": "reports/p671_p0_model_claim_non_assertion_guard_audit_validation_report.json",
        "p672_p0_customer_delivery_non_authorization_guard_audit": "datasets/governance/p672_p0_customer_delivery_non_authorization_guard_audit.jsonl",
        "p672_p0_customer_delivery_non_authorization_guard_audit_report": "reports/p672_p0_customer_delivery_non_authorization_guard_audit_report.json",
        "p672_p0_customer_delivery_non_authorization_guard_audit_validation_report": "reports/p672_p0_customer_delivery_non_authorization_guard_audit_validation_report.json",
        "p673_p0_production_execution_non_authorization_guard_audit": "datasets/governance/p673_p0_production_execution_non_authorization_guard_audit.jsonl",
        "p673_p0_production_execution_non_authorization_guard_audit_report": "reports/p673_p0_production_execution_non_authorization_guard_audit_report.json",
        "p673_p0_production_execution_non_authorization_guard_audit_validation_report": "reports/p673_p0_production_execution_non_authorization_guard_audit_validation_report.json",
        "p674_p0_terminal_blocked_state_rollup_audit": "datasets/governance/p674_p0_terminal_blocked_state_rollup_audit.jsonl",
        "p674_p0_terminal_blocked_state_rollup_audit_report": "reports/p674_p0_terminal_blocked_state_rollup_audit_report.json",
        "p674_p0_terminal_blocked_state_rollup_audit_validation_report": "reports/p674_p0_terminal_blocked_state_rollup_audit_validation_report.json",
        "p687_p0_real_input_closeout_readiness_gate": "datasets/governance/p687_p0_real_input_closeout_readiness_gate.jsonl",
        "p687_p0_real_input_closeout_readiness_gate_report": "reports/p687_p0_real_input_closeout_readiness_gate_report.json",
        "p687_p0_real_input_closeout_readiness_gate_validation_report": "reports/p687_p0_real_input_closeout_readiness_gate_validation_report.json",
        "p688_p0_real_input_closeout_blocker_ledger": "datasets/governance/p688_p0_real_input_closeout_blocker_ledger.jsonl",
        "p688_p0_real_input_closeout_blocker_ledger_report": "reports/p688_p0_real_input_closeout_blocker_ledger_report.json",
        "p688_p0_real_input_closeout_blocker_ledger_validation_report": "reports/p688_p0_real_input_closeout_blocker_ledger_validation_report.json",
        "p689_p0_real_input_blocker_escalation_queue": "datasets/governance/p689_p0_real_input_blocker_escalation_queue.jsonl",
        "p689_p0_real_input_blocker_escalation_queue_report": "reports/p689_p0_real_input_blocker_escalation_queue_report.json",
        "p689_p0_real_input_blocker_escalation_queue_validation_report": "reports/p689_p0_real_input_blocker_escalation_queue_validation_report.json",
        "p690_p0_real_input_blocker_escalation_status_board": "datasets/governance/p690_p0_real_input_blocker_escalation_status_board.jsonl",
        "p690_p0_real_input_blocker_escalation_status_board_report": "reports/p690_p0_real_input_blocker_escalation_status_board_report.json",
        "p690_p0_real_input_blocker_escalation_status_board_validation_report": "reports/p690_p0_real_input_blocker_escalation_status_board_validation_report.json",
        "p691_p0_real_input_blocker_escalation_watchlist": "datasets/governance/p691_p0_real_input_blocker_escalation_watchlist.jsonl",
        "p691_p0_real_input_blocker_escalation_watchlist_report": "reports/p691_p0_real_input_blocker_escalation_watchlist_report.json",
        "p691_p0_real_input_blocker_escalation_watchlist_validation_report": "reports/p691_p0_real_input_blocker_escalation_watchlist_validation_report.json",
        "p692_p0_real_input_blocker_escalation_review_queue": "datasets/governance/p692_p0_real_input_blocker_escalation_review_queue.jsonl",
        "p692_p0_real_input_blocker_escalation_review_queue_report": "reports/p692_p0_real_input_blocker_escalation_review_queue_report.json",
        "p692_p0_real_input_blocker_escalation_review_queue_validation_report": "reports/p692_p0_real_input_blocker_escalation_review_queue_validation_report.json",
        "p693_p0_real_input_blocker_escalation_review_status_board": "datasets/governance/p693_p0_real_input_blocker_escalation_review_status_board.jsonl",
        "p693_p0_real_input_blocker_escalation_review_status_board_report": "reports/p693_p0_real_input_blocker_escalation_review_status_board_report.json",
        "p693_p0_real_input_blocker_escalation_review_status_board_validation_report": "reports/p693_p0_real_input_blocker_escalation_review_status_board_validation_report.json",
        "p694_p0_real_input_blocker_escalation_review_watchlist": "datasets/governance/p694_p0_real_input_blocker_escalation_review_watchlist.jsonl",
        "p694_p0_real_input_blocker_escalation_review_watchlist_report": "reports/p694_p0_real_input_blocker_escalation_review_watchlist_report.json",
        "p694_p0_real_input_blocker_escalation_review_watchlist_validation_report": "reports/p694_p0_real_input_blocker_escalation_review_watchlist_validation_report.json",
        "p695_p0_real_input_blocker_escalation_review_watchlist_aging_audit": "datasets/governance/p695_p0_real_input_blocker_escalation_review_watchlist_aging_audit.jsonl",
        "p695_p0_real_input_blocker_escalation_review_watchlist_aging_audit_report": "reports/p695_p0_real_input_blocker_escalation_review_watchlist_aging_audit_report.json",
        "p695_p0_real_input_blocker_escalation_review_watchlist_aging_audit_validation_report": "reports/p695_p0_real_input_blocker_escalation_review_watchlist_aging_audit_validation_report.json",
        "p696_p0_real_input_blocker_escalation_review_owner_assignment_gap_audit": "datasets/governance/p696_p0_real_input_blocker_escalation_review_owner_assignment_gap_audit.jsonl",
        "p696_p0_real_input_blocker_escalation_review_owner_assignment_gap_audit_report": "reports/p696_p0_real_input_blocker_escalation_review_owner_assignment_gap_audit_report.json",
        "p696_p0_real_input_blocker_escalation_review_owner_assignment_gap_audit_validation_report": "reports/p696_p0_real_input_blocker_escalation_review_owner_assignment_gap_audit_validation_report.json",
        "p697_p0_real_input_blocker_escalation_review_evidence_missing_matrix": "datasets/governance/p697_p0_real_input_blocker_escalation_review_evidence_missing_matrix.jsonl",
        "p697_p0_real_input_blocker_escalation_review_evidence_missing_matrix_report": "reports/p697_p0_real_input_blocker_escalation_review_evidence_missing_matrix_report.json",
        "p697_p0_real_input_blocker_escalation_review_evidence_missing_matrix_validation_report": "reports/p697_p0_real_input_blocker_escalation_review_evidence_missing_matrix_validation_report.json",
        "p698_p0_real_input_formal_decision_readiness_false_positive_guard": "datasets/governance/p698_p0_real_input_formal_decision_readiness_false_positive_guard.jsonl",
        "p698_p0_real_input_formal_decision_readiness_false_positive_guard_report": "reports/p698_p0_real_input_formal_decision_readiness_false_positive_guard_report.json",
        "p698_p0_real_input_formal_decision_readiness_false_positive_guard_validation_report": "reports/p698_p0_real_input_formal_decision_readiness_false_positive_guard_validation_report.json",
        "p699_p0_real_input_formal_decision_readiness_status_board": "datasets/governance/p699_p0_real_input_formal_decision_readiness_status_board.jsonl",
        "p699_p0_real_input_formal_decision_readiness_status_board_report": "reports/p699_p0_real_input_formal_decision_readiness_status_board_report.json",
        "p699_p0_real_input_formal_decision_readiness_status_board_validation_report": "reports/p699_p0_real_input_formal_decision_readiness_status_board_validation_report.json",
        "p700_p0_real_input_pending_build_checklist": "datasets/governance/p700_p0_real_input_pending_build_checklist.jsonl",
        "p700_p0_real_input_pending_build_checklist_report": "reports/p700_p0_real_input_pending_build_checklist_report.json",
        "p700_p0_real_input_pending_build_checklist_validation_report": "reports/p700_p0_real_input_pending_build_checklist_validation_report.json",
        "safe_training_pipeline_receipt_atomicity_regression": "reports/safe_training_pipeline_receipt_atomicity_regression_report.json",
        "safe_training_pipeline_current_receipt_validation": "reports/safe_training_pipeline_current_receipt_validation_report.json",
        "safe_training_pipeline_current_receipt_regression": "reports/safe_training_pipeline_current_receipt_regression_report.json",
        "safe_training_pipeline_bootstrap_release_consistency_regression": "reports/safe_training_pipeline_bootstrap_release_consistency_regression_report.json",
        "local_release_terminal_defer_mode_regression": "reports/local_release_terminal_defer_mode_regression_report.json",
        "stage25_fail_closed_validation_current_receipt_validation": "reports/stage25_fail_closed_validation_current_receipt_validation_report.json",
        "stage25_fail_closed_validation_current_receipt_regression": "reports/stage25_fail_closed_validation_current_receipt_regression_report.json",
        "stage25_post_source_drop_rerun_receipt": "reports/stage25_post_source_drop_rerun_receipt_20260806.json",
        "stage25_post_source_drop_rerun_receipt_validation": "reports/stage25_post_source_drop_rerun_receipt_validation_20260806.json",
        "stage25_post_source_drop_rerun_receipt_regression": "reports/stage25_post_source_drop_rerun_receipt_regression_20260806.json",
        "stage25_post_source_drop_rerun_validation_current": "reports/stage25_post_source_drop_rerun_validation_current_20260810.json",
        "stage25_post_source_drop_rerun_validation_current_regression": "reports/stage25_post_source_drop_rerun_validation_current_regression_20260810.json",
        "stage25_post_source_drop_rerun_independent_policy": "reports/stage25_post_source_drop_rerun_independent_policy_validation_20260810.json",
        "stage25_post_source_drop_rerun_independent_policy_regression": "reports/stage25_post_source_drop_rerun_independent_policy_regression_20260810.json",
        "stage25_post_source_drop_rerun_independent_policy_current": "reports/stage25_post_source_drop_rerun_independent_policy_current_20260810.json",
        "stage25_post_source_drop_rerun_independent_policy_current_regression": "reports/stage25_post_source_drop_rerun_independent_policy_current_regression_20260810.json",
        "no_pseudo_strict_training_leakage_validation_report": "reports/no_pseudo_strict_training_leakage_validation_report.json",
        "model_claim_fail_closed_consistency_report": "reports/model_claim_fail_closed_consistency_report.json",
        "local_release_manifest_fail_closed_consistency_validation_report": "reports/local_release_manifest_fail_closed_consistency_validation_report.json",
        "local_release_consistency_receipt_atomicity_regression": "reports/local_release_consistency_receipt_atomicity_regression_report.json",
        "local_release_consistency_receipt_current": "reports/local_release_consistency_receipt_current_validation_report.json",
        "local_release_consistency_receipt_current_regression": "reports/local_release_consistency_receipt_current_regression_report.json",
        "local_release_consistency_semantic_policy_validation": "reports/local_release_consistency_semantic_policy_validation_report.json",
        "local_release_consistency_semantic_policy_regression": "reports/local_release_consistency_semantic_policy_regression_report.json",
        "local_release_consistency_semantic_policy_current": "reports/local_release_consistency_semantic_policy_current_validation_report.json",
        "local_release_consistency_semantic_policy_current_regression": "reports/local_release_consistency_semantic_policy_current_regression_report.json",
        "local_release_consistency_semantic_policy_atomicity_regression": "reports/local_release_consistency_semantic_policy_atomicity_regression_report.json",
        "local_release_safety_guard_link_validation_report": "reports/local_release_safety_guard_link_validation_report.json",
        "local_release_safety_guard_links_atomicity_regression_report": "reports/local_release_safety_guard_links_atomicity_regression_report.json",
        "local_release_safety_guard_links_current_validation_report": "reports/local_release_safety_guard_links_current_validation_report.json",
        "local_release_safety_guard_links_current_regression_report": "reports/local_release_safety_guard_links_current_regression_report.json",
        "local_release_safety_guard_links_current_regression_atomicity_regression_report": "reports/local_release_safety_guard_links_current_regression_atomicity_regression_report.json",
        "review_draft_formal_boundary_validation_report": "reports/review_draft_formal_boundary_validation_report.json",
        "no_review_draft_training_leakage_validation_report": "reports/no_review_draft_training_leakage_validation_report.json",
        "draft_namespace_isolation_validation_report": "reports/draft_namespace_isolation_validation_report.json",
        "no_unreviewed_positive_gate_flags_validation_report": "reports/no_unreviewed_positive_gate_flags_validation_report.json",
        "report_positive_claim_gate_quarantine_validation_report": "reports/report_positive_claim_gate_quarantine_validation_report.json",
        "numbering_review_platform_service": "scripts/serve_numbering_review_platform.py",
        "wet_lab_review_ui": "ui/wet_lab_review/index.html",
        "wet_lab_review_ui_styles": "ui/wet_lab_review/styles.css",
        "wet_lab_review_ui_app": "ui/wet_lab_review/app.js",
        "reviewed_structure_graph_feature_report": "reports/reviewed_structure_graph_feature_report.json",
        "reviewed_structure_graph_validation_report": "reports/reviewed_structure_graph_validation_report.json",
        "structure_feature_model_contract_report": "reports/structure_feature_model_contract_report.json",
        "structure_feature_model_contract_validation_report": "reports/structure_feature_model_contract_validation_report.json",
        "msa_trusted_cache_intake_report": "reports/msa_trusted_cache_intake_report.json",
        "msa_conservation_cache_validation_report": "reports/msa_conservation_cache_validation_report.json",
        "msa_mmseqs_swissprot_cache_build_report": "reports/msa_mmseqs_swissprot_cache_build_report.json",
        "mmseqs2_local_runtime_report": "reports/mmseqs2_local_runtime_report.json",
        "mmseqs2_local_runtime_manifest": "reports/mmseqs2_local_runtime_manifest.json",
        "mmseqs_homolog_database_report": "reports/mmseqs_homolog_database_report.json",
        "mmseqs_homolog_database_manifest": "reports/mmseqs_homolog_database_manifest.json",
        "msa_runtime_readiness_report": "reports/msa_runtime_readiness_report.json",
        "benchmark_score_cache_intake_report": "reports/benchmark_score_cache_intake_report.json",
        "benchmark_score_cache_validation_report": "reports/benchmark_score_cache_validation_report.json",
        "kwb_activity_risk_smoke_benchmark_report": "reports/kwb_activity_risk_smoke_benchmark_report.json",
        "kwb_activity_risk_smoke_benchmark_validation_report": "reports/kwb_activity_risk_smoke_benchmark_validation_report.json",
        "fireprot_protherm_stability_benchmark_report": "reports/fireprot_protherm_stability_benchmark_report.json",
        "atom3d_msp_benchmark_report": "reports/atom3d_msp_benchmark_report.json",
        "atom3d_msp_benchmark_validation_report": "reports/atom3d_msp_benchmark_validation_report.json",
        "catpred_gotenzymes_reference_benchmark_report": "reports/catpred_gotenzymes_reference_benchmark_report.json",
        "catpred_gotenzymes_reference_benchmark_validation_report": "reports/catpred_gotenzymes_reference_benchmark_validation_report.json",
        "posebusters_pose_plausibility_benchmark_report": "reports/posebusters_pose_plausibility_benchmark_report.json",
        "posebusters_pose_plausibility_benchmark_validation_report": "reports/posebusters_pose_plausibility_benchmark_validation_report.json",
        "kwb_replicate_consistency_benchmark_report": "reports/kwb_replicate_consistency_benchmark_report.json",
        "kwb_replicate_consistency_benchmark_validation_report": "reports/kwb_replicate_consistency_benchmark_validation_report.json",
        "benchmark_coverage_dashboard": "reports/benchmark_coverage_dashboard.json",
        "benchmark_coverage_dashboard_validation_report": "reports/benchmark_coverage_dashboard_validation_report.json",
        "benchmark_gap_queue": "datasets/benchmark/benchmark_gap_queue.jsonl",
        "benchmark_readiness_packet_report": "reports/benchmark_readiness_packet_report.json",
        "benchmark_readiness_packet_validation_report": "reports/benchmark_readiness_packet_validation_report.json",
        "activity_risk_training_lineage_ledger": "datasets/governance/activity_risk_training_lineage_ledger.jsonl",
        "activity_risk_training_lineage_ledger_report": "reports/activity_risk_training_lineage_ledger_report.json",
        "activity_risk_training_lineage_ledger_validation_report": "reports/activity_risk_training_lineage_ledger_validation_report.json",
        "proteingym_local_source_report": "reports/proteingym_local_source_report.json",
        "proteingym_local_source_manifest": "reports/proteingym_local_source_manifest.json",
        "flip2_amylase_benchmark_report": "reports/flip2_amylase_benchmark_report.json",
        "flip2_amylase_benchmark_validation_report": "reports/flip2_amylase_benchmark_validation_report.json",
        "external_stability_label_source_audit_report": "reports/external_stability_label_source_audit_report.json",
        "pyrosetta_local_install_probe_report": "reports/pyrosetta_local_install_probe_report.json",
        "pyrosetta_local_install_probe_validation_report": "reports/pyrosetta_local_install_probe_validation_report.json",
        "pyrosetta_local_install_probe_markdown": "reports/pyrosetta_local_install_probe.md",
        "pyrosetta_physical_smoke_bootstrap_report": "reports/pyrosetta_physical_smoke_bootstrap_report.json",
        "pyrosetta_physical_smoke_bootstrap_markdown": "reports/pyrosetta_physical_smoke_bootstrap.md",
        "rosetta_physical_smoke_bootstrap_report": "reports/rosetta_physical_smoke_bootstrap_report.json",
        "verified_mutation_structure_candidate_report": "reports/verified_mutation_structure_candidate_report.json",
        "verified_mutation_structure_download_report": "reports/verified_mutation_structure_download_report.json",
        "verified_mutation_structure_mapping_candidate_report": "reports/verified_mutation_structure_mapping_candidate_report.json",
        "verified_mutation_structure_mapping_candidate_validation_report": "reports/verified_mutation_structure_mapping_candidate_validation_report.json",
        "pyrosetta_verified_mutation_ddg_feature_report": "reports/pyrosetta_verified_mutation_ddg_feature_report.json",
        "pyrosetta_verified_mutation_ddg_feature_validation_report": "reports/pyrosetta_verified_mutation_ddg_feature_validation_report.json",
        "pyrosetta_multichain_ddg_concordance_report": "reports/pyrosetta_multichain_ddg_concordance_report.json",
        "pyrosetta_multichain_ddg_concordance_validation_report": "reports/pyrosetta_multichain_ddg_concordance_validation_report.json",
        "ddg_executable_probe_report": "reports/ddg_executable_probe_report.json",
        "ddg_local_runtime_discovery_report": "reports/ddg_local_runtime_discovery_report.json",
        "ddg_backend_failure_diagnostic_report": "reports/ddg_backend_failure_diagnostic_report.json",
        "ddg_proxy_not_physics_claim_validation_report": "reports/ddg_proxy_not_physics_claim_validation_report.json",
        "ddg_model_consumption_contract_report": "reports/ddg_model_consumption_contract_report.json",
        "ddg_model_consumption_contract_validation_report": "reports/ddg_model_consumption_contract_validation_report.json",
        "ddg_backend_operator_packet_report": "reports/ddg_backend_operator_packet_report.json",
        "ddg_backend_operator_packet_validation_report": "reports/ddg_backend_operator_packet_validation_report.json",
        "ddg_backend_runtime_receipt_validation_report": "reports/ddg_backend_runtime_receipt_validation_report.json",
        "ddg_physical_smoke_harness_plan": "datasets/governance/ddg_physical_smoke_harness_plan.jsonl",
        "ddg_physical_smoke_harness_report": "reports/ddg_physical_smoke_harness_report.json",
        "ddg_physical_smoke_harness_validation_report": "reports/ddg_physical_smoke_harness_validation_report.json",
        "ddg_physical_smoke_harness_markdown": "reports/ddg_physical_smoke_harness.md",
        "foldx_buildmodel_parser_contract_report": "reports/foldx_buildmodel_parser_contract_report.json",
        "foldx_buildmodel_parser_contract_validation_report": "reports/foldx_buildmodel_parser_contract_validation_report.json",
        "foldx_physical_smoke_bootstrap_report": "reports/foldx_physical_smoke_bootstrap_report.json",
        "foldx_physical_smoke_bootstrap_validation_report": "reports/foldx_physical_smoke_bootstrap_validation_report.json",
        "foldx_physical_smoke_bootstrap_markdown": "reports/foldx_physical_smoke_bootstrap.md",
        "kwb_qc_fail_rate_calibration_benchmark_report": "reports/kwb_qc_fail_rate_calibration_benchmark_report.json",
        "kwb_qc_fail_rate_calibration_benchmark_validation_report": "reports/kwb_qc_fail_rate_calibration_benchmark_validation_report.json",
        "kwb_plate_level_feedback_benchmark_report": "reports/kwb_plate_level_feedback_benchmark_report.json",
        "kwb_plate_level_feedback_benchmark_validation_report": "reports/kwb_plate_level_feedback_benchmark_validation_report.json",
        "kwb_activity_risk_plate_feedback_benchmark_report": "reports/kwb_activity_risk_plate_feedback_benchmark_report.json",
        "kwb_activity_risk_plate_feedback_benchmark_validation_report": "reports/kwb_activity_risk_plate_feedback_benchmark_validation_report.json",
        "fireprot_curated_stability_import_candidate_receipt": "reports/fireprot_curated_stability_import_candidate_receipt.json",
        "fireprot_curated_stability_import_leakage_report": "reports/fireprot_curated_stability_import_leakage_report.json",
        "fireprot_curated_stability_direction_normalization_report": "reports/fireprot_curated_stability_direction_normalization_report.json",
        "fireprot_curated_kwb_schema_mapping_report": "reports/fireprot_curated_kwb_schema_mapping_report.json",
        "fireprot_curated_import_leakage_review_report": "reports/fireprot_curated_import_leakage_review_report.json",
        "fireprot_curated_dedup_aggregation_report": "reports/fireprot_curated_dedup_aggregation_report.json",
        "fireprot_dedup_review_packet_report": "reports/fireprot_dedup_review_packet_report.json",
        "fireprot_dedup_review_decision_validation_report": "reports/fireprot_dedup_review_decision_validation_report.json",
        "fireprot_reviewed_import_candidate_report": "reports/fireprot_reviewed_import_candidate_report.json",
        "fireprot_supervised_import_authorization_validation_report": "reports/fireprot_supervised_import_authorization_validation_report.json",
        "fireprot_supervised_import_preflight_report": "reports/fireprot_supervised_import_preflight_report.json",
        "thermompnn_local_source_report": "reports/thermompnn_local_source_report.json",
        "thermompnn_local_source_manifest": "reports/thermompnn_local_source_manifest.json",
        "thermompnn_venus15b_smoke_report": "reports/thermompnn_venus15b_smoke_report.json",
        "experiment_feedback_trainability_audit_report": "reports/experiment_feedback_trainability_audit_report.json",
        "venus15b_experiment_asset_audit_report": "reports/venus15b_experiment_asset_audit_report.json",
        "venus15b_feedback_import_report": "reports/venus15b_feedback_import_report.json",
        "kwb_venus15b_strict_holdout_candidate_audit_report": "reports/kwb_venus15b_strict_holdout_candidate_audit_report.json",
        "substrate_identity_evidence_candidate_report": "reports/substrate_identity_evidence_candidate_report.json",
        "substrate_identity_evidence_candidate_validation_report": "reports/substrate_identity_evidence_candidate_validation_report.json",
        "hard_gate_review_packet_report": "reports/hard_gate_review_packet_report.json",
        "hard_gate_review_packet_validation_report": "reports/hard_gate_review_packet_validation_report.json",
        "hard_gate_decision_benchmark_bridge_report": "reports/hard_gate_decision_benchmark_bridge_report.json",
        "hard_gate_decision_benchmark_bridge_validation_report": "reports/hard_gate_decision_benchmark_bridge_validation_report.json",
        "release_benchmark_human_decision_worklist": "reports/release_benchmark_human_decision_worklist_20260806.json",
        "release_benchmark_human_decision_worklist_validation_report": "reports/release_benchmark_human_decision_worklist_validation_report_20260806.json",
        "release_benchmark_stage25_fail_closed_summary": "reports/release_benchmark_stage25_fail_closed_summary_20260806.json",
        "stage25_handoff_bundle_manifest": "reports/stage25_handoff_bundle_manifest_20260806.json",
        "stage25_handoff_bundle_manifest_validation": "reports/stage25_handoff_bundle_manifest_validation_20260806.json",
        "stage25_source_drop_inventory": "reports/stage25_source_drop_inventory_20260806.json",
        "stage25_source_drop_inventory_validation": "reports/stage25_source_drop_inventory_validation_20260806.json",
        "stage25_source_acquisition_shortlist": "reports/stage25_source_acquisition_shortlist_20260806.json",
        "stage25_source_acquisition_shortlist_markdown": "reports/stage25_source_acquisition_shortlist_20260806.md",
        "stage25_source_acquisition_shortlist_validation": "reports/stage25_source_acquisition_shortlist_validation_20260806.json",
        "stage25_literature_web_search_receipt": "reports/stage25_literature_web_search_receipt_20260806.json",
        "stage25_literature_web_search_receipt_validation": "reports/stage25_literature_web_search_receipt_validation_20260806.json",
        "stage25_blocker_activation_map": "reports/stage25_blocker_activation_map_20260806.json",
        "stage25_blocker_activation_map_validation": "reports/stage25_blocker_activation_map_validation_20260806.json",
        "stage25_remaining_blocker_cross_binding_validation_report": "reports/stage25_remaining_blocker_cross_binding_validation_report.json",
        "stage25_remaining_blocker_cross_binding_regression_report": "reports/stage25_remaining_blocker_cross_binding_regression_report.json",
        "stage25_execute_blocker_detail": "reports/stage25_execute_blocker_detail_20260806.json",
        "stage25_execute_blocker_detail_validation": "reports/stage25_execute_blocker_detail_validation_20260806.json",
        "stage25_execute_closeout_checklist": "reports/stage25_execute_closeout_checklist_20260806.json",
        "stage25_execute_closeout_checklist_validation": "reports/stage25_execute_closeout_checklist_validation_20260806.json",
        "stage25_post_source_drop_rerun_dry_run_audit": "reports/stage25_post_source_drop_rerun_dry_run_audit_20260806.json",
        "stage25_post_source_drop_rerun_dry_run_audit_validation": "reports/stage25_post_source_drop_rerun_dry_run_audit_validation_20260806.json",
        "stage25_unblock_operator_packet_validation": "reports/stage25_unblock_operator_packet_validation_20260806.json",
        "stage25_user_authorization_receipt_validation": "reports/stage25_user_authorization_receipt_validation_20260806.json",
        "stage25_claim_release_consistency_validation": "reports/stage25_claim_release_consistency_validation_20260806.json",
        "stage25_breakthrough_attempt_receipt_validation": "reports/stage25_breakthrough_attempt_receipt_validation_20260806.json",
        "stage25_foldx_benchmark_bridge_isolation_validation": "reports/stage25_foldx_benchmark_bridge_isolation_validation_20260806.json",
        "stage25_foldx_execution_plan_blocker": "reports/stage25_foldx_execution_plan_blocker_20260806.json",
        "stage25_foldx_execution_plan_blocker_validation": "reports/stage25_foldx_execution_plan_blocker_validation_20260806.json",
        "ddg_backend_execution_plan_foldx_stage25": "reports/ddg_backend_execution_plan_foldx_stage25_20260806.json",
        "ddg_backend_execution_plan_foldx_stage25_jsonl": "datasets/curation/ddg_backend_execution_plan.foldx_stage25_20260806.jsonl",
        "stage25_benchmark_unblock_design_validation": "reports/stage25_benchmark_unblock_design_validation_20260806.json",
        "benchmark_lane_machine_prereview_report": "reports/benchmark_lane_machine_prereview_report.json",
        "benchmark_lane_status_aggregate_report": "reports/benchmark_lane_status_aggregate_report.json",
        "wet_lab_mutant_library_asset_audit_report": "reports/wet_lab_mutant_library_asset_audit_report.json",
        "wet_lab_mutant_library_feedback_candidate_report": "reports/wet_lab_mutant_library_feedback_candidate_report.json",
        "wet_lab_mutant_library_feedback_qc_matrix_report": "reports/wet_lab_mutant_library_feedback_qc_matrix_report.json",
        "wet_lab_mutant_library_sequence_evidence_audit_report": "reports/wet_lab_mutant_library_sequence_evidence_audit_report.json",
        "wet_lab_mutant_library_project_sequence_intake_validation_report": "reports/wet_lab_mutant_library_project_sequence_intake_validation_report.json",
        "wet_lab_mutant_library_numbering_audit_from_project_sequences_report": "reports/wet_lab_mutant_library_numbering_audit_from_project_sequences_report.json",
        "wet_lab_mutant_library_feedback_authorization_validation_report": "reports/wet_lab_mutant_library_feedback_authorization_validation_report.json",
        "wet_lab_mutant_library_feedback_authorization_worklist_report": "reports/wet_lab_mutant_library_feedback_authorization_worklist_report.json",
        "wet_lab_mutant_library_feedback_authorization_worklist_validation_report": "reports/wet_lab_mutant_library_feedback_authorization_worklist_validation_report.json",
        "wet_lab_mutant_library_feedback_authorization_dashboard": "reports/wet_lab_mutant_library_feedback_authorization_dashboard.json",
        "wet_lab_mutant_library_feedback_authorization_dashboard_md": "reports/wet_lab_mutant_library_feedback_authorization_dashboard.md",
        "wet_lab_mutant_library_feedback_authorization_dashboard_validation_report": "reports/wet_lab_mutant_library_feedback_authorization_dashboard_validation_report.json",
        "wet_lab_mutant_library_feedback_authorization_gap_matrix_report": "reports/wet_lab_mutant_library_feedback_authorization_gap_matrix_report.json",
        "wet_lab_mutant_library_feedback_authorization_gap_matrix_validation_report": "reports/wet_lab_mutant_library_feedback_authorization_gap_matrix_validation_report.json",
        "wet_lab_mutant_library_feedback_authorization_operator_checklist_report": "reports/wet_lab_mutant_library_feedback_authorization_operator_checklist_report.json",
        "wet_lab_mutant_library_feedback_authorization_operator_checklist_validation_report": "reports/wet_lab_mutant_library_feedback_authorization_operator_checklist_validation_report.json",
        "wet_lab_mutant_library_feedback_authorization_operator_receipt_report": "reports/wet_lab_mutant_library_feedback_authorization_operator_receipt_report.json",
        "wet_lab_mutant_library_feedback_authorization_operator_receipt_validation_report": "reports/wet_lab_mutant_library_feedback_authorization_operator_receipt_validation_report.json",
        "wet_lab_mutant_library_feedback_authorization_execution_queue_report": "reports/wet_lab_mutant_library_feedback_authorization_execution_queue_report.json",
        "wet_lab_mutant_library_feedback_authorization_execution_queue_validation_report": "reports/wet_lab_mutant_library_feedback_authorization_execution_queue_validation_report.json",
        "wet_lab_mutant_library_feedback_authorization_execution_queue_md": "reports/wet_lab_mutant_library_feedback_authorization_execution_queue.md",
        "wet_lab_mutant_library_feedback_authorization_execution_queue_operator_packet_report": "reports/wet_lab_mutant_library_feedback_authorization_execution_queue_operator_packet_report.json",
        "wet_lab_mutant_library_feedback_authorization_execution_queue_operator_packet_validation_report": "reports/wet_lab_mutant_library_feedback_authorization_execution_queue_operator_packet_validation_report.json",
        "wet_lab_mutant_library_feedback_authorization_execution_queue_operator_packet_receipt_report": "reports/wet_lab_mutant_library_feedback_authorization_execution_queue_operator_packet_receipt_report.json",
        "wet_lab_mutant_library_feedback_authorization_execution_queue_operator_packet_receipt_validation_report": "reports/wet_lab_mutant_library_feedback_authorization_execution_queue_operator_packet_receipt_validation_report.json",
        "wet_lab_mutant_library_feedback_authorization_execution_queue_operator_packets_md": "reports/wet_lab_mutant_library_feedback_authorization_execution_queue_operator_packets.md",
        "wet_lab_mutant_library_feedback_authorization_closeout_board_report": "reports/wet_lab_mutant_library_feedback_authorization_closeout_board_report.json",
        "wet_lab_mutant_library_feedback_authorization_closeout_board_validation_report": "reports/wet_lab_mutant_library_feedback_authorization_closeout_board_validation_report.json",
        "wet_lab_mutant_library_feedback_authorization_closeout_board_md": "reports/wet_lab_mutant_library_feedback_authorization_closeout_board.md",
        "wet_lab_mutant_library_feedback_authorization_closeout_operator_packet_report": "reports/wet_lab_mutant_library_feedback_authorization_closeout_operator_packet_report.json",
        "wet_lab_mutant_library_feedback_authorization_closeout_operator_packet_validation_report": "reports/wet_lab_mutant_library_feedback_authorization_closeout_operator_packet_validation_report.json",
        "wet_lab_mutant_library_feedback_authorization_closeout_operator_packets_md": "reports/wet_lab_mutant_library_feedback_authorization_closeout_operator_packets.md",
        "numbering_review_packet_validation_report": "reports/numbering_review_packet_validation_report.json",
        "numbering_review_packet_board_report": "reports/numbering_review_packet_board_report.json",
        "numbering_review_briefing": "reports/numbering_review_briefing.json",
        "numbering_review_briefing_md": "reports/numbering_review_briefing.md",
        "numbering_review_briefing_validation_report": "reports/numbering_review_briefing_validation_report.json",
        "numbering_review_briefing_status_board": "reports/numbering_review_briefing_status_board_report.json",
        "numbering_review_briefing_status_board_md": "reports/numbering_review_briefing_status_board.md",
        "numbering_review_briefing_status_board_validation_report": "reports/numbering_review_briefing_status_board_validation_report.json",
        "numbering_deep_audit_report": "reports/numbering_deep_audit_report.json",
        "numbering_deep_audit_markdown": "reports/numbering_deep_audit_report.md",
        "numbering_semantic_conflict_report": "reports/numbering_decision_semantic_conflict_report.json",
        "numbering_semantic_conflict_markdown": "reports/numbering_decision_semantic_conflict_report.md",
        "numbering_review_operator_queue": "reports/numbering_review_operator_queue.json",
        "numbering_review_operator_queue_markdown": "reports/numbering_review_operator_queue.md",
        "wet_lab_mutant_library_feedback_preflight_report": "reports/wet_lab_mutant_library_feedback_preflight_report.json",
        "wet_lab_feedback_authorization_contract_report": "reports/wet_lab_feedback_authorization_contract_report.json",
        "wet_lab_feedback_authorization_contract_validation_report": "reports/wet_lab_feedback_authorization_contract_validation_report.json",
        "wet_lab_mutant_library_feedback_intake_apply_plan_report": "reports/wet_lab_mutant_library_feedback_intake_apply_plan_report.json",
        "wet_lab_feedback_apply_duplicate_audit_report": "reports/wet_lab_feedback_apply_duplicate_audit_report.json",
        "wet_lab_feedback_apply_duplicate_audit_validation_report": "reports/wet_lab_feedback_apply_duplicate_audit_validation_report.json",
        "wet_lab_mutant_library_operator_packet_report": "reports/wet_lab_mutant_library_operator_packet_report.json",
        "wet_lab_mutant_library_operator_packet_validation_report": "reports/wet_lab_mutant_library_operator_packet_validation_report.json",
        "wet_lab_mutant_library_unlock_status_report": "reports/wet_lab_mutant_library_unlock_status_report.json",
        "feedback_training_import_semantic_guard_report": "reports/feedback_training_import_semantic_guard_report.json",
        "feedback_training_import_semantic_guard_validation_report": "reports/feedback_training_import_semantic_guard_validation_report.json",
        "training_label_import_contract_report": "reports/training_label_import_contract_report.json",
        "training_label_import_contract_validation_report": "reports/training_label_import_contract_validation_report.json",
        "wet_lab_feedback_import_reconciliation_report": "reports/wet_lab_feedback_import_reconciliation_report.json",
        "wet_lab_feedback_import_reconciliation_validation_report": "reports/wet_lab_feedback_import_reconciliation_validation_report.json",
        "parallel_hard_gate_workstreams_board_report": "reports/parallel_hard_gate_workstreams_board_report.json",
        "parallel_hard_gate_workstreams_board_validation_report": "reports/parallel_hard_gate_workstreams_board_validation_report.json",
        "human_preflight_package_report": "reports/human_preflight_package_report.json",
        "human_preflight_package_validation_report": "reports/human_preflight_package_validation_report.json",
        "parallel_hard_gate_execution_receipts_report": "reports/parallel_hard_gate_execution_receipts_report.json",
        "parallel_hard_gate_execution_receipts_validation_report": "reports/parallel_hard_gate_execution_receipts_validation_report.json",
        "next_hard_gate_attack_wave_report": "reports/next_hard_gate_attack_wave_report.json",
        "next_hard_gate_attack_wave_validation_report": "reports/next_hard_gate_attack_wave_validation_report.json",
        "five_head_training_execution_contract_report": "reports/five_head_training_execution_contract_report.json",
        "five_head_training_execution_contract_validation_report": "reports/five_head_training_execution_contract_validation_report.json",
        "five_head_training_threshold_report": "reports/five_head_training_threshold_report.json",
        "five_head_training_threshold_validation_report": "reports/five_head_training_threshold_validation_report.json",
        "five_head_training_sample_gap_queue_report": "reports/five_head_training_sample_gap_queue_report.json",
        "five_head_training_sample_gap_queue_validation_report": "reports/five_head_training_sample_gap_queue_validation_report.json",
        "proteingym_benchmark_scorecard_report": "reports/proteingym_benchmark_scorecard_report.json",
        "activity_risk_label_replicate_preflight_report": "reports/activity_risk_label_replicate_preflight_report.json",
        "activity_risk_label_replicate_preflight_validation_report": "reports/activity_risk_label_replicate_preflight_validation_report.json",
        "activity_risk_formal_label_decision_report": "reports/activity_risk_formal_label_decision_report.json",
        "activity_risk_formal_label_decision_validation_report": "reports/activity_risk_formal_label_decision_validation_report.json",
        "activity_risk_training_import_label_report": "reports/activity_risk_training_import_label_report.json",
        "activity_risk_training_import_label_validation_report": "reports/activity_risk_training_import_label_validation_report.json",
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
        "local_release_guard_coverage_validation_report": "reports/local_release_guard_coverage_validation_report.json",
        "strict_msa_site_feature_report": "reports/strict_msa_site_feature_report.json",
        "repaired_supervised_msa_baseline_eval": "reports/repaired_supervised_msa_baseline_eval.json",
        "label_provenance_audit_report": "reports/label_provenance_audit_report.json",
        "domain_multi_occurrence_feature_report": "reports/domain_multi_occurrence_feature_report.json",
        "domain_interpro_review_packet_report": "reports/domain_interpro_review_packet_report.json",
        "allowed_claims": governance.get("allowed_claims", []) + customer.get("allowed_claims", []),
        "forbidden_claims": sorted(set(governance.get("forbidden_claims", []) + customer.get("forbidden_claims", []))),
        "release_ready": False,
        "policy": "This manifest packages local review state only; it is not a production deployment or customer release approval.",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"release_ready": False, "artifact_count": len(artifacts), "output": str(args.output)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
