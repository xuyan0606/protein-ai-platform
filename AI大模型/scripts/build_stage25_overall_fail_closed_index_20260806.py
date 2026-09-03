#!/usr/bin/env python3
"""Build the read-only Stage 25 fail-closed index."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
ENZYME_DB_ROOT = Path("/Users/keweibo/科为博/05自动化程序/04研发工作区/酶数据库")
DEFAULT_OUTPUT = AI_ROOT / "reports" / "stage25_overall_fail_closed_index_20260806.json"

INPUTS = {
    "new_paper_fail_closed_summary": ENZYME_DB_ROOT / "new_paper_stage25_fail_closed_validation_summary_20260806.json",
    "paper_metadata_only_plan_validation": AI_ROOT / "reports" / "stage25_paper_metadata_only_plan_validation_20260806.json",
    "proposal_set_consistency_validation": ENZYME_DB_ROOT / "new_paper_proposal_set_consistency_validation_report_20260806.json",
    "approved_apply_report_validation": ENZYME_DB_ROOT / "stage25_approved_apply_report_validation_20260806.json",
    "execute_blocker_detail_validation": AI_ROOT / "reports" / "stage25_execute_blocker_detail_validation_20260806.json",
    "execute_closeout_checklist_validation": AI_ROOT / "reports" / "stage25_execute_closeout_checklist_validation_20260806.json",
    "execute_closeout_reviewer_intake_validation": AI_ROOT / "reports" / "stage25_execute_closeout_reviewer_intake_validation_20260806.json",
    "execute_closeout_reviewer_packet_validation": AI_ROOT / "reports" / "stage25_execute_closeout_reviewer_packet_validation_20260806.json",
    "fulltext_intake_validation": ENZYME_DB_ROOT / "fulltext_intake_validation_report_20260806.json",
    "fulltext_source_locator_review_queue_validation": ENZYME_DB_ROOT / "fulltext_source_locator_review_queue_validation_report_20260806.json",
    "fulltext_evidence_draft": ENZYME_DB_ROOT / "fulltext_evidence_draft_20260806.json",
    "stage25_reviewer_package": ENZYME_DB_ROOT / "stage25_reviewer_package_20260806.json",
    "local_release_manifest_fail_closed_consistency_validation": AI_ROOT / "reports" / "local_release_manifest_fail_closed_consistency_validation_report.json",
    "local_release_consistency_receipt_atomicity_regression": AI_ROOT / "reports" / "local_release_consistency_receipt_atomicity_regression_report.json",
    "local_release_consistency_receipt_current": AI_ROOT / "reports" / "local_release_consistency_receipt_current_validation_report.json",
    "local_release_consistency_receipt_current_regression": AI_ROOT / "reports" / "local_release_consistency_receipt_current_regression_report.json",
    "local_release_consistency_semantic_policy": AI_ROOT / "reports" / "local_release_consistency_semantic_policy_validation_report.json",
    "local_release_consistency_semantic_policy_regression": AI_ROOT / "reports" / "local_release_consistency_semantic_policy_regression_report.json",
    "local_release_consistency_semantic_policy_current": AI_ROOT / "reports" / "local_release_consistency_semantic_policy_current_validation_report.json",
    "local_release_consistency_semantic_policy_current_regression": AI_ROOT / "reports" / "local_release_consistency_semantic_policy_current_regression_report.json",
    "local_release_consistency_semantic_policy_atomicity_regression": AI_ROOT / "reports" / "local_release_consistency_semantic_policy_atomicity_regression_report.json",
    "claim_matrix_policy_current": AI_ROOT / "reports" / "claim_readiness_matrix_fail_closed_policy_current_validation_report.json",
    "claim_matrix_policy_current_regression": AI_ROOT / "reports" / "claim_readiness_matrix_fail_closed_policy_current_regression_report.json",
    "claim_policy_anchor": AI_ROOT / "reports" / "claim_readiness_policy_anchor_validation_report.json",
    "claim_policy_anchor_regression": AI_ROOT / "reports" / "claim_readiness_policy_anchor_regression_report.json",
    "claim_promotion": AI_ROOT / "reports" / "claim_promotion_decision_validation_report.json",
    "enzyme_agent_release_guard_order": AI_ROOT / "reports" / "enzyme_agent_controlled_release_guard_order_validation_report.json",
    "enzyme_agent_release_guard_order_regression": AI_ROOT / "reports" / "enzyme_agent_controlled_release_guard_order_regression_report.json",
    "enzyme_agent_release_guard_order_current": AI_ROOT / "reports" / "enzyme_agent_controlled_release_guard_order_current_validation_report.json",
    "enzyme_agent_release_guard_order_current_regression": AI_ROOT / "reports" / "enzyme_agent_controlled_release_guard_order_current_regression_report.json",
    "enzyme_agent_release_guard_order_atomicity_regression": AI_ROOT / "reports" / "enzyme_agent_controlled_release_guard_order_atomicity_regression_report.json",
    "enzyme_agent_execution_wave_pair_atomicity_regression": AI_ROOT / "reports" / "enzyme_agent_controlled_execution_wave_pair_atomicity_regression_report.json",
    "enzyme_agent_execution_receipt_proof_current": AI_ROOT / "reports" / "enzyme_agent_execution_receipt_proof_current_validation_report.json",
    "enzyme_agent_execution_receipt_proof_current_regression": AI_ROOT / "reports" / "enzyme_agent_execution_receipt_proof_current_regression_report.json",
    "local_release_safety_guard_links_atomicity_regression": AI_ROOT / "reports" / "local_release_safety_guard_links_atomicity_regression_report.json",
    "local_release_safety_guard_links_current": AI_ROOT / "reports" / "local_release_safety_guard_links_current_validation_report.json",
    "local_release_safety_guard_links_current_regression": AI_ROOT / "reports" / "local_release_safety_guard_links_current_regression_report.json",
    "local_release_safety_guard_links_current_regression_atomicity": AI_ROOT / "reports" / "local_release_safety_guard_links_current_regression_atomicity_regression_report.json",
    "operator_docs_marker_regression_current": AI_ROOT / "reports" / "stage25_operator_docs_dynamic_status_sync_regression_current_validation_report.json",
    "operator_docs_marker_regression_current_regression": AI_ROOT / "reports" / "stage25_operator_docs_dynamic_status_sync_regression_current_regression_report.json",
    "operator_docs_marker_regression_atomicity_regression": AI_ROOT / "reports" / "stage25_operator_docs_dynamic_status_sync_regression_atomicity_regression_report.json",
    "release_benchmark_fail_closed_summary": AI_ROOT / "reports" / "release_benchmark_stage25_fail_closed_summary_20260806.json",
    "markdown_operator_docs_validation": AI_ROOT / "reports" / "stage25_markdown_operator_docs_validation_20260806.json",
    "user_authorization_receipt_validation": AI_ROOT / "reports" / "stage25_user_authorization_receipt_validation_20260806.json",
    "breakthrough_attempt_receipt_validation": AI_ROOT / "reports" / "stage25_breakthrough_attempt_receipt_validation_20260806.json",
    "unblock_operator_packet_validation": AI_ROOT / "reports" / "stage25_unblock_operator_packet_validation_20260806.json",
    "source_drop_manifest_validation": AI_ROOT / "reports" / "stage25_source_drop_manifest_validation_20260806.json",
    "source_drop_inventory_validation": AI_ROOT / "reports" / "stage25_source_drop_inventory_validation_20260806.json",
    "source_acquisition_receipts_validation": AI_ROOT / "reports" / "stage25_source_acquisition_receipts_validation_20260807.json",
    "source_extraction_candidate_validation": AI_ROOT / "reports" / "stage25_source_extraction_candidate_validation_20260807.json",
    "source_extraction_candidate_reviewer_packet_validation": AI_ROOT / "reports" / "stage25_source_extraction_candidate_reviewer_packet_validation_20260807.json",
    "source_extraction_reviewer_closure_checklist_validation": AI_ROOT / "reports" / "stage25_source_extraction_reviewer_closure_checklist_validation_20260807.json",
    "cm5_codon262_cross_read_audit_validation": AI_ROOT / "reports" / "stage25_cm5_codon262_cross_read_audit_validation_20260807.json",
    "cm5_codon262_sequence_quality_evidence_audit_validation": AI_ROOT / "reports" / "stage25_cm5_codon262_sequence_quality_evidence_audit_validation_20260807.json",
    "cm5_l262v_discrepancy_adjudication_packet_validation": AI_ROOT / "reports" / "stage25_cm5_l262v_discrepancy_adjudication_packet_validation_20260807.json",
    "cm5_l262v_adjudication_decision_intake_validation": AI_ROOT / "reports" / "stage25_cm5_l262v_adjudication_decision_intake_validation_20260807.json",
    "cm5_l262v_adjudication_review_binding_regression": AI_ROOT / "reports" / "stage25_cm5_l262v_adjudication_review_binding_regression_20260807.json",
    "cm5_l262v_adjudication_review_binding_tamper_regression": AI_ROOT / "reports" / "stage25_cm5_l262v_adjudication_review_binding_tamper_regression_20260807.json",
    "cm5_l262v_adjudication_evidence_path_safety_regression": AI_ROOT / "reports" / "stage25_cm5_l262v_adjudication_evidence_path_safety_regression_20260807.json",
    "cm5_l262v_adjudication_upstream_review_provenance_regression": AI_ROOT / "reports" / "stage25_cm5_l262v_adjudication_upstream_review_provenance_regression_20260807.json",
    "cm5_l262v_adjudication_upstream_packet_provenance_regression": AI_ROOT / "reports" / "stage25_cm5_l262v_adjudication_upstream_packet_provenance_regression_20260807.json",
    "cm5_l262v_adjudication_evidence_intake_validation": AI_ROOT / "reports" / "stage25_cm5_l262v_adjudication_evidence_intake_validation_20260807.json",
    "cm5_l262v_public_source_probe_receipt_validation": AI_ROOT / "reports" / "stage25_cm5_l262v_public_source_probe_receipt_validation_20260807.json",
    "cm5_l262v_external_evidence_request_packet_validation": AI_ROOT / "reports" / "stage25_cm5_l262v_external_evidence_request_packet_validation_20260807.json",
    "cm5_l262v_external_evidence_receipt_validation": AI_ROOT / "reports" / "stage25_cm5_l262v_external_evidence_receipt_validation_20260807.json",
    "cm5_l262v_external_evidence_review_validation": AI_ROOT / "reports" / "stage25_cm5_l262v_external_evidence_review_validation_20260807.json",
    "cm5_l262v_external_request_message_drafts_validation": AI_ROOT / "reports" / "stage25_cm5_l262v_external_request_message_drafts_validation_20260807.json",
    "cm5_l262v_external_request_authorization_validation": AI_ROOT / "reports" / "stage25_cm5_l262v_external_request_authorization_validation_20260807.json",
    "cm5_l262v_external_request_send_guard_validation": AI_ROOT / "reports" / "stage25_cm5_l262v_external_request_send_guard_validation_20260807.json",
    "cm5_l262v_external_request_authorization_safety_regression": AI_ROOT / "reports" / "stage25_cm5_l262v_external_request_authorization_safety_regression_20260807.json",
    "source_acquisition_shortlist_validation": AI_ROOT / "reports" / "stage25_source_acquisition_shortlist_validation_20260806.json",
    "literature_web_search_receipt_validation": AI_ROOT / "reports" / "stage25_literature_web_search_receipt_validation_20260806.json",
    "source_drop_extraction_readiness_candidate_validation": AI_ROOT / "reports" / "stage25_source_drop_extraction_readiness_candidate_validation_20260806.json",
    "family_apply_importer_design_validation": AI_ROOT / "reports" / "stage25_family_apply_importer_design_validation_20260806.json",
    "family_apply_transaction_plan_validation": AI_ROOT / "reports" / "stage25_family_apply_transaction_plan_validation_20260806.json",
    "foldx_provision_manifest_validation": AI_ROOT / "reports" / "stage25_foldx_provision_manifest_validation_20260806.json",
    "foldx_provision_manifest_candidate_validation": AI_ROOT / "reports" / "stage25_foldx_provision_manifest_candidate_validation_20260806.json",
    "foldx_runtime_receipt_candidate_draft_validation": AI_ROOT / "reports" / "stage25_foldx_runtime_receipt_candidate_draft_validation_20260806.json",
    "foldx_technical_smoke_validation": AI_ROOT / "reports" / "stage25_foldx_technical_smoke_validation_20260806.json",
    "foldx_benchmark_bridge_isolation_validation": AI_ROOT / "reports" / "stage25_foldx_benchmark_bridge_isolation_validation_20260806.json",
    "foldx_execution_plan_blocker_validation": AI_ROOT / "reports" / "stage25_foldx_execution_plan_blocker_validation_20260806.json",
    "benchmark_unblock_design_validation": AI_ROOT / "reports" / "stage25_benchmark_unblock_design_validation_20260806.json",
    "hard_gate_formal_decision_draft_package_validation": AI_ROOT / "reports" / "stage25_hard_gate_formal_decision_draft_package_validation_20260806.json",
    "new_paper_extraction_template_validation": AI_ROOT / "reports" / "stage25_new_paper_extraction_template_validation_20260806.json",
    "reviewed_extraction_output_draft_validation": AI_ROOT / "reports" / "stage25_reviewed_extraction_output_draft_validation_20260806.json",
    "claim_release_consistency_validation": AI_ROOT / "reports" / "stage25_claim_release_consistency_validation_20260806.json",
    "remaining_blocker_closure_matrix_validation": AI_ROOT / "reports" / "stage25_remaining_blocker_closure_matrix_validation_20260806.json",
    "post_source_drop_rerun_receipt_validation": AI_ROOT / "reports" / "stage25_post_source_drop_rerun_receipt_validation_20260806.json",
    "post_source_drop_rerun_receipt_regression": AI_ROOT / "reports" / "stage25_post_source_drop_rerun_receipt_regression_20260806.json",
    "post_source_drop_rerun_validation_current": AI_ROOT / "reports" / "stage25_post_source_drop_rerun_validation_current_20260810.json",
    "post_source_drop_rerun_validation_current_regression": AI_ROOT / "reports" / "stage25_post_source_drop_rerun_validation_current_regression_20260810.json",
    "post_source_drop_rerun_independent_policy": AI_ROOT / "reports" / "stage25_post_source_drop_rerun_independent_policy_validation_20260810.json",
    "post_source_drop_rerun_independent_policy_regression": AI_ROOT / "reports" / "stage25_post_source_drop_rerun_independent_policy_regression_20260810.json",
    "post_source_drop_rerun_independent_policy_current": AI_ROOT / "reports" / "stage25_post_source_drop_rerun_independent_policy_current_20260810.json",
    "post_source_drop_rerun_independent_policy_current_regression": AI_ROOT / "reports" / "stage25_post_source_drop_rerun_independent_policy_current_regression_20260810.json",
    "post_source_drop_rerun_dry_run_audit_validation": AI_ROOT / "reports" / "stage25_post_source_drop_rerun_dry_run_audit_validation_20260806.json",
    "workstream_acceptance_decision_validation": AI_ROOT / "reports" / "workstream_acceptance_decision_validation_report.json",
    "blocker_activation_map_validation": AI_ROOT / "reports" / "stage25_blocker_activation_map_validation_20260806.json",
    "external_input_readiness_board_validation": AI_ROOT / "reports" / "stage25_external_input_readiness_board_validation_20260806.json",
    "latest_blocker_coverage_audit_validation": AI_ROOT / "reports" / "stage25_latest_blocker_coverage_audit_validation_20260806.json",
    "remaining_blocker_cross_binding_validation": AI_ROOT / "reports" / "stage25_remaining_blocker_cross_binding_validation_report.json",
    "remaining_blocker_cross_binding_regression": AI_ROOT / "reports" / "stage25_remaining_blocker_cross_binding_regression_report.json",
    "handoff_bundle_manifest_validation": AI_ROOT / "reports" / "stage25_handoff_bundle_manifest_validation_20260806.json",
}


def load_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise SystemExit(f"{path} must contain a JSON object")
    return data


def fail_if(condition: bool, failures: list[dict[str, Any]], check: str, observed: Any, expected: Any) -> None:
    if condition:
        failures.append({"check": check, "observed": observed, "expected": expected})


def build_index() -> dict[str, Any]:
    failures: list[dict[str, Any]] = []
    summaries: dict[str, dict[str, Any]] = {}
    rows = []
    for name, path in INPUTS.items():
        if not path.exists():
            failures.append({"check": f"{name}_exists", "observed": "missing", "expected": str(path)})
            continue
        summary = load_json(path)
        summaries[name] = summary
        rows.append({
            "name": name,
            "path": str(path),
            "summary_valid": summary.get("summary_valid"),
            "docs_valid": summary.get("docs_valid"),
            "receipt_valid": summary.get("receipt_valid"),
            "failure_count": summary.get("failure_count"),
            "mode": summary.get("mode"),
        })

    new_paper = summaries.get("new_paper_fail_closed_summary", {})
    fail_if(new_paper.get("summary_valid") is not True, failures, "new_paper_summary_valid", new_paper.get("summary_valid"), True)
    fail_if(new_paper.get("failure_count") != 0, failures, "new_paper_failure_count", new_paper.get("failure_count"), 0)
    fail_if(new_paper.get("external_sqlite_mutated") is not False, failures, "new_paper_external_sqlite_mutated_false", new_paper.get("external_sqlite_mutated"), False)
    fail_if(new_paper.get("allow_apply") is not False, failures, "new_paper_allow_apply_false", new_paper.get("allow_apply"), False)
    fail_if(new_paper.get("export_safe_released") is not False, failures, "new_paper_export_safe_released_false", new_paper.get("export_safe_released"), False)
    fail_if(new_paper.get("release_status") != "not_released", failures, "new_paper_release_status", new_paper.get("release_status"), "not_released")

    metadata_plan = summaries.get("paper_metadata_only_plan_validation", {})
    fail_if(metadata_plan.get("plan_valid") is not True, failures, "paper_metadata_only_plan_valid", metadata_plan.get("plan_valid"), True)
    fail_if(metadata_plan.get("failure_count") != 0, failures, "paper_metadata_only_plan_failure_count", metadata_plan.get("failure_count"), 0)
    fail_if(metadata_plan.get("plan_ready") is not True, failures, "paper_metadata_only_plan_ready_for_review", metadata_plan.get("plan_ready"), True)
    fail_if(metadata_plan.get("paper_rows") != 4, failures, "paper_metadata_only_plan_rows", metadata_plan.get("paper_rows"), 4)
    fail_if(metadata_plan.get("unique_stable_proposal_rows") != 4, failures, "paper_metadata_only_unique_stable_proposals", metadata_plan.get("unique_stable_proposal_rows"), 4)
    fail_if(metadata_plan.get("planned_metadata_review_rows") != 4, failures, "paper_metadata_only_planned_review_rows", metadata_plan.get("planned_metadata_review_rows"), 4)
    fail_if(metadata_plan.get("ready_for_metadata_review_rows") != 4, failures, "paper_metadata_only_ready_review_rows", metadata_plan.get("ready_for_metadata_review_rows"), 4)
    for field in ("paper_insert_count", "ready_for_sqlite_apply_rows", "write_operation_count", "variant_rows", "measurement_rows", "sqlite_write_sql_count", "formal_decision_rows_written"):
        fail_if(metadata_plan.get(field) != 0, failures, f"paper_metadata_only.{field}_zero", metadata_plan.get(field), 0)
    for flag in ("apply_executed", "external_sqlite_mutated", "safe_for_model_claim", "release_ready"):
        fail_if(metadata_plan.get(flag) is not False, failures, f"paper_metadata_only.{flag}_false", metadata_plan.get(flag), False)

    proposal_consistency = summaries.get("proposal_set_consistency_validation", {})
    fail_if(proposal_consistency.get("validation_success") is not True, failures, "proposal_set_validation_success", proposal_consistency.get("validation_success"), True)
    fail_if(proposal_consistency.get("proposal_sets_consistent") is not True, failures, "proposal_sets_consistent", proposal_consistency.get("proposal_sets_consistent"), True)
    fail_if(proposal_consistency.get("failure_count") != 0, failures, "proposal_set_failure_count", proposal_consistency.get("failure_count"), 0)
    fail_if(proposal_consistency.get("status") != "consistent_by_surface_policy", failures, "proposal_set_status", proposal_consistency.get("status"), "consistent_by_surface_policy")
    fail_if(proposal_consistency.get("authoritative_candidate_count") != 7, failures, "proposal_set_authoritative_candidate_count", proposal_consistency.get("authoritative_candidate_count"), 7)
    fail_if(proposal_consistency.get("expected_surface_counts") != {"allowlist": 6, "intake_manifest": 4, "locator_queue": 4, "apply_plan": 7}, failures, "proposal_set_expected_surface_counts", proposal_consistency.get("expected_surface_counts"), {"allowlist": 6, "intake_manifest": 4, "locator_queue": 4, "apply_plan": 7})
    fail_if(proposal_consistency.get("disposition_row_count") != 7, failures, "proposal_set_disposition_rows", proposal_consistency.get("disposition_row_count"), 7)
    fail_if(proposal_consistency.get("uncovered_authoritative_candidates") != [], failures, "proposal_set_uncovered_candidates_empty", proposal_consistency.get("uncovered_authoritative_candidates"), [])
    for flag in ("allow_apply", "external_sqlite_mutated", "apply_executed", "export_safe_released", "safe_for_model_claim", "release_ready"):
        fail_if(proposal_consistency.get(flag) is not False, failures, f"proposal_set.{flag}_false", proposal_consistency.get(flag), False)
    fail_if(proposal_consistency.get("formal_decision_rows_written") != 0, failures, "proposal_set_formal_decision_rows_written_zero", proposal_consistency.get("formal_decision_rows_written"), 0)

    approved_apply = summaries.get("approved_apply_report_validation", {})
    fail_if(approved_apply.get("report_valid") is not True, failures, "approved_apply_report_valid", approved_apply.get("report_valid"), True)
    fail_if(approved_apply.get("failure_count") != 0, failures, "approved_apply_failure_count", approved_apply.get("failure_count"), 0)
    fail_if(approved_apply.get("executor_status") != "blocked", failures, "approved_apply_executor_status_blocked", approved_apply.get("executor_status"), "blocked")
    fail_if(int(approved_apply.get("executor_failure_count") or 0) <= 0, failures, "approved_apply_executor_failure_count_positive", approved_apply.get("executor_failure_count"), ">0")
    fail_if(approved_apply.get("execute_requested") is not True, failures, "approved_apply_execute_requested_true", approved_apply.get("execute_requested"), True)
    for flag in ("external_sqlite_mutated", "apply_executed", "export_safe_released", "release_ready", "safe_for_model_claim"):
        fail_if(approved_apply.get(flag) is not False, failures, f"approved_apply.{flag}_false", approved_apply.get(flag), False)
    fail_if(approved_apply.get("formal_decision_rows_written") != 0, failures, "approved_apply_formal_decision_rows_written_zero", approved_apply.get("formal_decision_rows_written"), 0)

    execute_detail = summaries.get("execute_blocker_detail_validation", {})
    fail_if(execute_detail.get("detail_valid") is not True, failures, "execute_blocker_detail_valid", execute_detail.get("detail_valid"), True)
    fail_if(execute_detail.get("failure_count") != 0, failures, "execute_blocker_detail_failure_count", execute_detail.get("failure_count"), 0)
    fail_if(execute_detail.get("execute_requested") is not True, failures, "execute_blocker_detail_execute_requested_true", execute_detail.get("execute_requested"), True)
    fail_if(execute_detail.get("executor_failure_count") != 24, failures, "execute_blocker_detail_executor_failure_count", execute_detail.get("executor_failure_count"), 24)
    fail_if(execute_detail.get("proposal_blocker_rows") != 4, failures, "execute_blocker_detail_proposal_rows", execute_detail.get("proposal_blocker_rows"), 4)
    for flag in ("external_sqlite_mutated", "apply_executed", "export_safe_released", "release_ready", "safe_for_model_claim"):
        fail_if(execute_detail.get(flag) is not False, failures, f"execute_blocker_detail.{flag}_false", execute_detail.get(flag), False)

    closeout_checklist = summaries.get("execute_closeout_checklist_validation", {})
    fail_if(closeout_checklist.get("checklist_valid") is not True, failures, "execute_closeout_checklist_valid", closeout_checklist.get("checklist_valid"), True)
    fail_if(closeout_checklist.get("failure_count") != 0, failures, "execute_closeout_checklist_failure_count", closeout_checklist.get("failure_count"), 0)
    fail_if(closeout_checklist.get("proposal_rows") != 4, failures, "execute_closeout_checklist_proposal_rows", closeout_checklist.get("proposal_rows"), 4)
    fail_if(closeout_checklist.get("checklist_item_rows") != 24, failures, "execute_closeout_checklist_item_rows", closeout_checklist.get("checklist_item_rows"), 24)
    fail_if(closeout_checklist.get("closed_item_rows") != 0, failures, "execute_closeout_checklist_closed_rows_zero", closeout_checklist.get("closed_item_rows"), 0)
    fail_if(closeout_checklist.get("closeout_ready_rows") != 0, failures, "execute_closeout_checklist_ready_rows_zero", closeout_checklist.get("closeout_ready_rows"), 0)
    for flag in ("external_sqlite_mutated", "apply_executed", "export_safe_released", "release_ready", "safe_for_model_claim"):
        fail_if(closeout_checklist.get(flag) is not False, failures, f"execute_closeout_checklist.{flag}_false", closeout_checklist.get(flag), False)

    reviewer_intake = summaries.get("execute_closeout_reviewer_intake_validation", {})
    fail_if(reviewer_intake.get("intake_valid") is not True, failures, "execute_closeout_reviewer_intake_valid", reviewer_intake.get("intake_valid"), True)
    fail_if(reviewer_intake.get("failure_count") != 0, failures, "execute_closeout_reviewer_intake_failure_count", reviewer_intake.get("failure_count"), 0)
    fail_if(reviewer_intake.get("intake_rows") != 24, failures, "execute_closeout_reviewer_intake_rows", reviewer_intake.get("intake_rows"), 24)
    fail_if(reviewer_intake.get("closed_rows") != 0, failures, "execute_closeout_reviewer_intake_closed_rows_zero", reviewer_intake.get("closed_rows"), 0)
    fail_if(reviewer_intake.get("approved_rows") != 0, failures, "execute_closeout_reviewer_intake_approved_rows_zero", reviewer_intake.get("approved_rows"), 0)
    for flag in ("external_sqlite_mutated", "apply_executed", "export_safe_released", "release_ready", "safe_for_model_claim"):
        fail_if(reviewer_intake.get(flag) is not False, failures, f"execute_closeout_reviewer_intake.{flag}_false", reviewer_intake.get(flag), False)

    reviewer_packet = summaries.get("execute_closeout_reviewer_packet_validation", {})
    fail_if(reviewer_packet.get("packet_valid") is not True, failures, "execute_closeout_reviewer_packet_valid", reviewer_packet.get("packet_valid"), True)
    fail_if(reviewer_packet.get("failure_count") != 0, failures, "execute_closeout_reviewer_packet_failure_count", reviewer_packet.get("failure_count"), 0)
    fail_if(reviewer_packet.get("proposal_rows") != 4, failures, "execute_closeout_reviewer_packet_proposal_rows", reviewer_packet.get("proposal_rows"), 4)
    fail_if(reviewer_packet.get("checklist_rows") != 24, failures, "execute_closeout_reviewer_packet_checklist_rows", reviewer_packet.get("checklist_rows"), 24)
    fail_if(reviewer_packet.get("closed_rows") != 0, failures, "execute_closeout_reviewer_packet_closed_rows_zero", reviewer_packet.get("closed_rows"), 0)
    fail_if(reviewer_packet.get("approved_rows") != 0, failures, "execute_closeout_reviewer_packet_approved_rows_zero", reviewer_packet.get("approved_rows"), 0)
    for flag in ("external_sqlite_mutated", "apply_executed", "export_safe_released", "release_ready", "safe_for_model_claim"):
        fail_if(reviewer_packet.get(flag) is not False, failures, f"execute_closeout_reviewer_packet.{flag}_false", reviewer_packet.get(flag), False)

    fulltext_intake = summaries.get("fulltext_intake_validation", {})
    fail_if(fulltext_intake.get("success") is not False, failures, "fulltext_intake_blocked_until_files", fulltext_intake.get("success"), False)
    fail_if(fulltext_intake.get("failure_count") != 8, failures, "fulltext_intake_failure_count", fulltext_intake.get("failure_count"), 8)
    fail_if(fulltext_intake.get("status") != "blocked", failures, "fulltext_intake_status_blocked", fulltext_intake.get("status"), "blocked")

    fulltext_queue = summaries.get("fulltext_source_locator_review_queue_validation", {})
    fail_if(fulltext_queue.get("success") is not True, failures, "fulltext_queue_success", fulltext_queue.get("success"), True)
    fail_if(fulltext_queue.get("status") != "blocked", failures, "fulltext_queue_status_blocked", fulltext_queue.get("status"), "blocked")
    fail_if(fulltext_queue.get("item_count") != 4, failures, "fulltext_queue_item_count", fulltext_queue.get("item_count"), 4)
    fail_if(fulltext_queue.get("review_ready_count") != 0, failures, "fulltext_queue_review_ready_count_zero", fulltext_queue.get("review_ready_count"), 0)

    fulltext_draft = summaries.get("fulltext_evidence_draft", {})
    fail_if(fulltext_draft.get("success") is not False, failures, "fulltext_draft_blocked_until_pdf", fulltext_draft.get("success"), False)
    fail_if(fulltext_draft.get("failure_count") != 1, failures, "fulltext_draft_failure_count", fulltext_draft.get("failure_count"), 1)
    fail_if(fulltext_draft.get("status") != "blocked", failures, "fulltext_draft_status_blocked", fulltext_draft.get("status"), "blocked")

    reviewer_package = summaries.get("stage25_reviewer_package", {})
    reviewer_summary = reviewer_package.get("summary") or {}
    fail_if(reviewer_package.get("package_valid") is not True, failures, "reviewer_package_valid", reviewer_package.get("package_valid"), True)
    fail_if(reviewer_summary.get("paper_pdf_count") != 0, failures, "reviewer_package_paper_pdf_count_zero", reviewer_summary.get("paper_pdf_count"), 0)
    fail_if(reviewer_summary.get("source_locator_count") != 0, failures, "reviewer_package_source_locator_count_zero", reviewer_summary.get("source_locator_count"), 0)

    local_release = summaries.get("local_release_manifest_fail_closed_consistency_validation", {})
    fail_if(local_release.get("success") is not True, failures, "local_release_consistency_success", local_release.get("success"), True)
    fail_if(local_release.get("release_ready") is not False, failures, "local_release_ready_false", local_release.get("release_ready"), False)
    fail_if(int(local_release.get("artifact_count") or 0) < 1582, failures, "local_release_artifact_count_min", local_release.get("artifact_count"), ">=1582")
    fail_if(local_release.get("safe_for_model_claim") is not False, failures, "local_release_safe_for_model_claim_false", local_release.get("safe_for_model_claim"), False)
    local_release_atomicity_regression = summaries.get("local_release_consistency_receipt_atomicity_regression", {})
    fail_if(local_release_atomicity_regression.get("success") is not True, failures, "local_release_consistency_receipt_atomicity_regression_success", local_release_atomicity_regression.get("success"), True)
    fail_if(local_release_atomicity_regression.get("failed_case_count") != 0, failures, "local_release_consistency_receipt_atomicity_regression_failed_cases", local_release_atomicity_regression.get("failed_case_count"), 0)
    fail_if(local_release_atomicity_regression.get("passed_case_count") != 5, failures, "local_release_consistency_receipt_atomicity_regression_passed_cases", local_release_atomicity_regression.get("passed_case_count"), 5)
    fail_if(local_release_atomicity_regression.get("isolated_fixture") is not True, failures, "local_release_consistency_receipt_atomicity_regression_isolated_fixture", local_release_atomicity_regression.get("isolated_fixture"), True)
    fail_if(local_release_atomicity_regression.get("real_inputs_mutated") is not False, failures, "local_release_consistency_receipt_atomicity_regression_real_inputs_unchanged", local_release_atomicity_regression.get("real_inputs_mutated"), False)
    local_release_current = summaries.get("local_release_consistency_receipt_current", {})
    fail_if(local_release_current.get("success") is not True, failures, "local_release_consistency_receipt_current_success", local_release_current.get("success"), True)
    fail_if(local_release_current.get("failure_count") != 0, failures, "local_release_consistency_receipt_current_failure_count", local_release_current.get("failure_count"), 0)
    local_release_current_regression = summaries.get("local_release_consistency_receipt_current_regression", {})
    fail_if(local_release_current_regression.get("success") is not True, failures, "local_release_consistency_receipt_current_regression_success", local_release_current_regression.get("success"), True)
    fail_if(local_release_current_regression.get("failed_case_count") != 0, failures, "local_release_consistency_receipt_current_regression_failed_cases", local_release_current_regression.get("failed_case_count"), 0)
    fail_if(local_release_current_regression.get("passed_case_count") != local_release_current_regression.get("case_count"), failures, "local_release_consistency_receipt_current_regression_all_cases_pass", {"passed": local_release_current_regression.get("passed_case_count"), "cases": local_release_current_regression.get("case_count")}, "equal")
    fail_if(local_release_current_regression.get("isolated_fixture") is not True, failures, "local_release_consistency_receipt_current_regression_isolated_fixture", local_release_current_regression.get("isolated_fixture"), True)
    fail_if(local_release_current_regression.get("real_inputs_mutated") is not False, failures, "local_release_consistency_receipt_current_regression_real_inputs_unchanged", local_release_current_regression.get("real_inputs_mutated"), False)
    local_release_semantic_policy = summaries.get("local_release_consistency_semantic_policy", {})
    fail_if(local_release_semantic_policy.get("success") is not True, failures, "local_release_consistency_semantic_policy_success", local_release_semantic_policy.get("success"), True)
    fail_if(local_release_semantic_policy.get("failure_count") != 0, failures, "local_release_consistency_semantic_policy_failure_count", local_release_semantic_policy.get("failure_count"), 0)
    local_release_semantic_policy_regression = summaries.get("local_release_consistency_semantic_policy_regression", {})
    fail_if(local_release_semantic_policy_regression.get("success") is not True, failures, "local_release_consistency_semantic_policy_regression_success", local_release_semantic_policy_regression.get("success"), True)
    fail_if(local_release_semantic_policy_regression.get("failed_case_count") != 0, failures, "local_release_consistency_semantic_policy_regression_failed_cases", local_release_semantic_policy_regression.get("failed_case_count"), 0)
    fail_if(local_release_semantic_policy_regression.get("passed_case_count") != 10, failures, "local_release_consistency_semantic_policy_regression_passed_cases", local_release_semantic_policy_regression.get("passed_case_count"), 10)
    fail_if(local_release_semantic_policy_regression.get("isolated_fixture") is not True, failures, "local_release_consistency_semantic_policy_regression_isolated_fixture", local_release_semantic_policy_regression.get("isolated_fixture"), True)
    fail_if(local_release_semantic_policy_regression.get("real_inputs_mutated") is not False, failures, "local_release_consistency_semantic_policy_regression_real_inputs_unchanged", local_release_semantic_policy_regression.get("real_inputs_mutated"), False)
    local_release_semantic_policy_current = summaries.get("local_release_consistency_semantic_policy_current", {})
    fail_if(local_release_semantic_policy_current.get("success") is not True, failures, "local_release_consistency_semantic_policy_current_success", local_release_semantic_policy_current.get("success"), True)
    fail_if(local_release_semantic_policy_current.get("failure_count") != 0, failures, "local_release_consistency_semantic_policy_current_failure_count", local_release_semantic_policy_current.get("failure_count"), 0)
    local_release_semantic_policy_current_regression = summaries.get("local_release_consistency_semantic_policy_current_regression", {})
    fail_if(local_release_semantic_policy_current_regression.get("success") is not True, failures, "local_release_consistency_semantic_policy_current_regression_success", local_release_semantic_policy_current_regression.get("success"), True)
    fail_if(local_release_semantic_policy_current_regression.get("case_count") != 16, failures, "local_release_consistency_semantic_policy_current_regression_case_count", local_release_semantic_policy_current_regression.get("case_count"), 16)
    fail_if(local_release_semantic_policy_current_regression.get("passed_case_count") != 16, failures, "local_release_consistency_semantic_policy_current_regression_passed_cases", local_release_semantic_policy_current_regression.get("passed_case_count"), 16)
    fail_if(local_release_semantic_policy_current_regression.get("failed_case_count") != 0, failures, "local_release_consistency_semantic_policy_current_regression_failed_cases", local_release_semantic_policy_current_regression.get("failed_case_count"), 0)
    fail_if(local_release_semantic_policy_current_regression.get("real_inputs_mutated") is not False, failures, "local_release_consistency_semantic_policy_current_regression_real_inputs_unchanged", local_release_semantic_policy_current_regression.get("real_inputs_mutated"), False)
    local_release_semantic_policy_atomicity = summaries.get("local_release_consistency_semantic_policy_atomicity_regression", {})
    fail_if(local_release_semantic_policy_atomicity.get("success") is not True, failures, "local_release_consistency_semantic_policy_atomicity_regression_success", local_release_semantic_policy_atomicity.get("success"), True)
    fail_if(local_release_semantic_policy_atomicity.get("case_count") != 7, failures, "local_release_consistency_semantic_policy_atomicity_regression_case_count", local_release_semantic_policy_atomicity.get("case_count"), 7)
    fail_if(local_release_semantic_policy_atomicity.get("passed_case_count") != 7, failures, "local_release_consistency_semantic_policy_atomicity_regression_passed_cases", local_release_semantic_policy_atomicity.get("passed_case_count"), 7)
    fail_if(local_release_semantic_policy_atomicity.get("failed_case_count") != 0, failures, "local_release_consistency_semantic_policy_atomicity_regression_failed_cases", local_release_semantic_policy_atomicity.get("failed_case_count"), 0)
    fail_if(local_release_semantic_policy_atomicity.get("real_inputs_mutated") is not False, failures, "local_release_consistency_semantic_policy_atomicity_regression_real_inputs_unchanged", local_release_semantic_policy_atomicity.get("real_inputs_mutated"), False)

    release_guard_order = summaries.get("enzyme_agent_release_guard_order", {})
    fail_if(release_guard_order.get("success") is not True, failures, "enzyme_agent_release_guard_order_success", release_guard_order.get("success"), True)
    fail_if(release_guard_order.get("failure_count") != 0, failures, "enzyme_agent_release_guard_order_failure_count", release_guard_order.get("failure_count"), 0)
    fail_if(release_guard_order.get("observed_command_count") != 29, failures, "enzyme_agent_release_guard_order_command_count", release_guard_order.get("observed_command_count"), 29)
    release_guard_order_regression = summaries.get("enzyme_agent_release_guard_order_regression", {})
    fail_if(release_guard_order_regression.get("success") is not True, failures, "enzyme_agent_release_guard_order_regression_success", release_guard_order_regression.get("success"), True)
    fail_if(release_guard_order_regression.get("failed_rows") != 0, failures, "enzyme_agent_release_guard_order_regression_failed_rows", release_guard_order_regression.get("failed_rows"), 0)
    fail_if(release_guard_order_regression.get("passed_rows") != 8, failures, "enzyme_agent_release_guard_order_regression_passed_rows", release_guard_order_regression.get("passed_rows"), 8)
    fail_if(release_guard_order_regression.get("real_inputs_mutated") is not False, failures, "enzyme_agent_release_guard_order_regression_real_inputs_unchanged", release_guard_order_regression.get("real_inputs_mutated"), False)
    release_guard_order_current = summaries.get("enzyme_agent_release_guard_order_current", {})
    fail_if(release_guard_order_current.get("success") is not True, failures, "enzyme_agent_release_guard_order_current_success", release_guard_order_current.get("success"), True)
    fail_if(release_guard_order_current.get("failure_count") != 0, failures, "enzyme_agent_release_guard_order_current_failure_count", release_guard_order_current.get("failure_count"), 0)
    release_guard_order_current_regression = summaries.get("enzyme_agent_release_guard_order_current_regression", {})
    fail_if(release_guard_order_current_regression.get("success") is not True, failures, "enzyme_agent_release_guard_order_current_regression_success", release_guard_order_current_regression.get("success"), True)
    fail_if(release_guard_order_current_regression.get("case_count") != 17, failures, "enzyme_agent_release_guard_order_current_regression_case_count", release_guard_order_current_regression.get("case_count"), 17)
    fail_if(release_guard_order_current_regression.get("passed_case_count") != 17, failures, "enzyme_agent_release_guard_order_current_regression_passed_cases", release_guard_order_current_regression.get("passed_case_count"), 17)
    fail_if(release_guard_order_current_regression.get("failed_case_count") != 0, failures, "enzyme_agent_release_guard_order_current_regression_failed_cases", release_guard_order_current_regression.get("failed_case_count"), 0)
    fail_if(release_guard_order_current_regression.get("real_inputs_mutated") is not False, failures, "enzyme_agent_release_guard_order_current_regression_real_inputs_unchanged", release_guard_order_current_regression.get("real_inputs_mutated"), False)
    release_guard_order_atomicity = summaries.get("enzyme_agent_release_guard_order_atomicity_regression", {})
    fail_if(release_guard_order_atomicity.get("success") is not True, failures, "enzyme_agent_release_guard_order_atomicity_regression_success", release_guard_order_atomicity.get("success"), True)
    fail_if(release_guard_order_atomicity.get("case_count") != 11, failures, "enzyme_agent_release_guard_order_atomicity_regression_case_count", release_guard_order_atomicity.get("case_count"), 11)
    fail_if(release_guard_order_atomicity.get("passed_case_count") != 11, failures, "enzyme_agent_release_guard_order_atomicity_regression_passed_cases", release_guard_order_atomicity.get("passed_case_count"), 11)
    fail_if(release_guard_order_atomicity.get("failed_case_count") != 0, failures, "enzyme_agent_release_guard_order_atomicity_regression_failed_cases", release_guard_order_atomicity.get("failed_case_count"), 0)
    fail_if(release_guard_order_atomicity.get("real_inputs_mutated") is not False, failures, "enzyme_agent_release_guard_order_atomicity_regression_real_inputs_unchanged", release_guard_order_atomicity.get("real_inputs_mutated"), False)
    wave_pair_atomicity = summaries.get("enzyme_agent_execution_wave_pair_atomicity_regression", {})
    fail_if(wave_pair_atomicity.get("success") is not True, failures, "enzyme_agent_execution_wave_pair_atomicity_regression_success", wave_pair_atomicity.get("success"), True)
    fail_if(wave_pair_atomicity.get("case_count") != 5, failures, "enzyme_agent_execution_wave_pair_atomicity_regression_case_count", wave_pair_atomicity.get("case_count"), 5)
    fail_if(wave_pair_atomicity.get("passed_case_count") != 5, failures, "enzyme_agent_execution_wave_pair_atomicity_regression_passed_cases", wave_pair_atomicity.get("passed_case_count"), 5)
    fail_if(wave_pair_atomicity.get("failed_case_count") != 0, failures, "enzyme_agent_execution_wave_pair_atomicity_regression_failed_cases", wave_pair_atomicity.get("failed_case_count"), 0)
    fail_if(wave_pair_atomicity.get("real_inputs_mutated") is not False, failures, "enzyme_agent_execution_wave_pair_atomicity_regression_real_inputs_unchanged", wave_pair_atomicity.get("real_inputs_mutated"), False)
    receipt_proof_current = summaries.get("enzyme_agent_execution_receipt_proof_current", {})
    fail_if(receipt_proof_current.get("success") is not True, failures, "enzyme_agent_execution_receipt_proof_current_success", receipt_proof_current.get("success"), True)
    fail_if(receipt_proof_current.get("failure_count") != 0, failures, "enzyme_agent_execution_receipt_proof_current_failure_count", receipt_proof_current.get("failure_count"), 0)
    receipt_proof_current_regression = summaries.get("enzyme_agent_execution_receipt_proof_current_regression", {})
    fail_if(receipt_proof_current_regression.get("success") is not True, failures, "enzyme_agent_execution_receipt_proof_current_regression_success", receipt_proof_current_regression.get("success"), True)
    fail_if(receipt_proof_current_regression.get("passed_case_count") != 11, failures, "enzyme_agent_execution_receipt_proof_current_regression_passed_cases", receipt_proof_current_regression.get("passed_case_count"), 11)
    fail_if(receipt_proof_current_regression.get("failed_case_count") != 0, failures, "enzyme_agent_execution_receipt_proof_current_regression_failed_cases", receipt_proof_current_regression.get("failed_case_count"), 0)
    fail_if(receipt_proof_current_regression.get("real_inputs_mutated") is not False, failures, "enzyme_agent_execution_receipt_proof_current_regression_inputs_unchanged", receipt_proof_current_regression.get("real_inputs_mutated"), False)
    claim_policy_current = summaries.get("claim_matrix_policy_current", {})
    fail_if(claim_policy_current.get("success") is not True, failures, "claim_matrix_policy_current_success", claim_policy_current.get("success"), True)
    fail_if(claim_policy_current.get("failure_count") != 0, failures, "claim_matrix_policy_current_failure_count", claim_policy_current.get("failure_count"), 0)
    claim_policy_current_regression = summaries.get("claim_matrix_policy_current_regression", {})
    fail_if(claim_policy_current_regression.get("success") is not True, failures, "claim_matrix_policy_current_regression_success", claim_policy_current_regression.get("success"), True)
    fail_if(claim_policy_current_regression.get("passed_case_count") != 11, failures, "claim_matrix_policy_current_regression_passed_cases", claim_policy_current_regression.get("passed_case_count"), 11)
    fail_if(claim_policy_current_regression.get("failed_rows") != 0, failures, "claim_matrix_policy_current_regression_failed_rows", claim_policy_current_regression.get("failed_rows"), 0)
    fail_if(claim_policy_current_regression.get("real_inputs_mutated") is not False, failures, "claim_matrix_policy_current_regression_inputs_unchanged", claim_policy_current_regression.get("real_inputs_mutated"), False)
    claim_policy_anchor = summaries.get("claim_policy_anchor", {})
    fail_if(claim_policy_anchor.get("success") is not True, failures, "claim_policy_anchor_success", claim_policy_anchor.get("success"), True)
    fail_if(claim_policy_anchor.get("failure_count") != 0, failures, "claim_policy_anchor_failure_count", claim_policy_anchor.get("failure_count"), 0)
    claim_policy_anchor_regression = summaries.get("claim_policy_anchor_regression", {})
    fail_if(claim_policy_anchor_regression.get("success") is not True, failures, "claim_policy_anchor_regression_success", claim_policy_anchor_regression.get("success"), True)
    fail_if(claim_policy_anchor_regression.get("passed_case_count") != 8, failures, "claim_policy_anchor_regression_passed_cases", claim_policy_anchor_regression.get("passed_case_count"), 8)
    fail_if(claim_policy_anchor_regression.get("failed_rows") != 0, failures, "claim_policy_anchor_regression_failed_rows", claim_policy_anchor_regression.get("failed_rows"), 0)
    fail_if(claim_policy_anchor_regression.get("real_inputs_mutated") is not False, failures, "claim_policy_anchor_regression_inputs_unchanged", claim_policy_anchor_regression.get("real_inputs_mutated"), False)
    claim_promotion = summaries.get("claim_promotion", {})
    fail_if(claim_promotion.get("success") is not True, failures, "claim_promotion_validation_success", claim_promotion.get("success"), True)
    fail_if(claim_promotion.get("failure_count") != 0, failures, "claim_promotion_validation_failure_count", claim_promotion.get("failure_count"), 0)
    fail_if(claim_promotion.get("decision_rows") != 0, failures, "claim_promotion_decision_rows", claim_promotion.get("decision_rows"), 0)
    fail_if(claim_promotion.get("approved_rows") != 0, failures, "claim_promotion_approved_rows", claim_promotion.get("approved_rows"), 0)
    fail_if(len(claim_promotion.get("missing_promotion_decisions") or []) != 9, failures, "claim_promotion_missing_decisions", len(claim_promotion.get("missing_promotion_decisions") or []), 9)
    safety_guard_atomicity = summaries.get("local_release_safety_guard_links_atomicity_regression", {})
    fail_if(safety_guard_atomicity.get("success") is not True, failures, "local_release_safety_guard_links_atomicity_regression_success", safety_guard_atomicity.get("success"), True)
    fail_if(safety_guard_atomicity.get("passed_case_count") != 5, failures, "local_release_safety_guard_links_atomicity_regression_passed_cases", safety_guard_atomicity.get("passed_case_count"), 5)
    fail_if(safety_guard_atomicity.get("failed_case_count") != 0, failures, "local_release_safety_guard_links_atomicity_regression_failed_cases", safety_guard_atomicity.get("failed_case_count"), 0)
    fail_if(safety_guard_atomicity.get("real_inputs_mutated") is not False, failures, "local_release_safety_guard_links_atomicity_regression_inputs_unchanged", safety_guard_atomicity.get("real_inputs_mutated"), False)
    safety_guard_current = summaries.get("local_release_safety_guard_links_current", {})
    fail_if(safety_guard_current.get("success") is not True, failures, "local_release_safety_guard_links_current_success", safety_guard_current.get("success"), True)
    fail_if(safety_guard_current.get("failure_count") != 0, failures, "local_release_safety_guard_links_current_failure_count", safety_guard_current.get("failure_count"), 0)
    safety_guard_current_regression = summaries.get("local_release_safety_guard_links_current_regression", {})
    fail_if(safety_guard_current_regression.get("success") is not True, failures, "local_release_safety_guard_links_current_regression_success", safety_guard_current_regression.get("success"), True)
    fail_if(safety_guard_current_regression.get("passed_case_count") != 12, failures, "local_release_safety_guard_links_current_regression_passed_cases", safety_guard_current_regression.get("passed_case_count"), 12)
    fail_if(safety_guard_current_regression.get("failed_case_count") != 0, failures, "local_release_safety_guard_links_current_regression_failed_cases", safety_guard_current_regression.get("failed_case_count"), 0)
    safety_guard_current_regression_atomicity = summaries.get("local_release_safety_guard_links_current_regression_atomicity", {})
    fail_if(safety_guard_current_regression_atomicity.get("success") is not True, failures, "local_release_safety_guard_links_current_regression_atomicity_success", safety_guard_current_regression_atomicity.get("success"), True)
    fail_if(safety_guard_current_regression_atomicity.get("passed_case_count") != 5, failures, "local_release_safety_guard_links_current_regression_atomicity_passed_cases", safety_guard_current_regression_atomicity.get("passed_case_count"), 5)
    fail_if(safety_guard_current_regression_atomicity.get("failed_case_count") != 0, failures, "local_release_safety_guard_links_current_regression_atomicity_failed_cases", safety_guard_current_regression_atomicity.get("failed_case_count"), 0)
    fail_if(safety_guard_current_regression_atomicity.get("real_inputs_mutated") is not False, failures, "local_release_safety_guard_links_current_regression_atomicity_inputs_unchanged", safety_guard_current_regression_atomicity.get("real_inputs_mutated"), False)

    release_benchmark = summaries.get("release_benchmark_fail_closed_summary", {})
    fail_if(release_benchmark.get("summary_valid") is not True, failures, "release_benchmark_summary_valid", release_benchmark.get("summary_valid"), True)
    fail_if(release_benchmark.get("failure_count") != 0, failures, "release_benchmark_failure_count", release_benchmark.get("failure_count"), 0)
    fail_if(release_benchmark.get("release_ready") is not False, failures, "release_ready_false", release_benchmark.get("release_ready"), False)
    fail_if(release_benchmark.get("safe_for_model_claim") is not False, failures, "safe_for_model_claim_false", release_benchmark.get("safe_for_model_claim"), False)
    fail_if(release_benchmark.get("benchmark_ready_for_model_claim") is not False, failures, "benchmark_ready_for_model_claim_false", release_benchmark.get("benchmark_ready_for_model_claim"), False)
    fail_if(release_benchmark.get("formal_decision_rows_written") != 0, failures, "formal_decision_rows_written_zero", release_benchmark.get("formal_decision_rows_written"), 0)

    markdown_docs = summaries.get("markdown_operator_docs_validation", {})
    fail_if(markdown_docs.get("docs_valid") is not True, failures, "markdown_operator_docs_valid", markdown_docs.get("docs_valid"), True)
    fail_if(markdown_docs.get("failure_count") != 0, failures, "markdown_operator_docs_failure_count", markdown_docs.get("failure_count"), 0)
    fail_if(markdown_docs.get("external_sqlite_mutated") is not False, failures, "markdown_docs_external_sqlite_mutated_false", markdown_docs.get("external_sqlite_mutated"), False)
    fail_if(markdown_docs.get("allow_apply") is not False, failures, "markdown_docs_allow_apply_false", markdown_docs.get("allow_apply"), False)
    fail_if(markdown_docs.get("export_safe_released") is not False, failures, "markdown_docs_export_safe_released_false", markdown_docs.get("export_safe_released"), False)
    fail_if(markdown_docs.get("release_status") != "not_released", failures, "markdown_docs_release_status", markdown_docs.get("release_status"), "not_released")

    marker_current = summaries.get("operator_docs_marker_regression_current", {})
    marker_current_regression = summaries.get("operator_docs_marker_regression_current_regression", {})
    marker_atomicity = summaries.get("operator_docs_marker_regression_atomicity_regression", {})
    fail_if(marker_current.get("success") is not True or marker_current.get("failure_count") != 0 or marker_current.get("case_count") != 13, failures, "operator_docs_marker_regression_current_valid", {"success": marker_current.get("success"), "failure_count": marker_current.get("failure_count"), "case_count": marker_current.get("case_count")}, {"success": True, "failure_count": 0, "case_count": 13})
    fail_if(marker_current_regression.get("success") is not True or marker_current_regression.get("failure_count") != 0 or marker_current_regression.get("passed_case_count") != 14 or marker_current_regression.get("real_inputs_mutated") is not False, failures, "operator_docs_marker_regression_current_regression_valid", {"success": marker_current_regression.get("success"), "failure_count": marker_current_regression.get("failure_count"), "passed_case_count": marker_current_regression.get("passed_case_count"), "real_inputs_mutated": marker_current_regression.get("real_inputs_mutated")}, {"success": True, "failure_count": 0, "passed_case_count": 14, "real_inputs_mutated": False})
    fail_if(marker_atomicity.get("success") is not True or marker_atomicity.get("failure_count") != 0 or marker_atomicity.get("passed_case_count") != 7 or marker_atomicity.get("real_inputs_mutated") is not False, failures, "operator_docs_marker_regression_atomicity_valid", {"success": marker_atomicity.get("success"), "failure_count": marker_atomicity.get("failure_count"), "passed_case_count": marker_atomicity.get("passed_case_count"), "real_inputs_mutated": marker_atomicity.get("real_inputs_mutated")}, {"success": True, "failure_count": 0, "passed_case_count": 7, "real_inputs_mutated": False})

    authorization = summaries.get("user_authorization_receipt_validation", {})
    fail_if(authorization.get("receipt_valid") is not True, failures, "user_authorization_receipt_valid", authorization.get("receipt_valid"), True)
    fail_if(authorization.get("failure_count") != 0, failures, "user_authorization_failure_count", authorization.get("failure_count"), 0)
    fail_if(authorization.get("authorization_recorded") is not True, failures, "user_authorization_recorded", authorization.get("authorization_recorded"), True)
    fail_if(authorization.get("external_sqlite_mutated") is not False, failures, "user_authorization_external_sqlite_mutated_false", authorization.get("external_sqlite_mutated"), False)
    fail_if(authorization.get("apply_executed") is not False, failures, "user_authorization_apply_executed_false", authorization.get("apply_executed"), False)
    fail_if(authorization.get("export_safe_released") is not False, failures, "user_authorization_export_safe_released_false", authorization.get("export_safe_released"), False)
    fail_if(authorization.get("safe_for_model_claim") is not False, failures, "user_authorization_safe_for_model_claim_false", authorization.get("safe_for_model_claim"), False)
    fail_if(authorization.get("formal_decision_rows_written") != 0, failures, "user_authorization_formal_decision_rows_written_zero", authorization.get("formal_decision_rows_written"), 0)

    breakthrough = summaries.get("breakthrough_attempt_receipt_validation", {})
    fail_if(breakthrough.get("receipt_valid") is not True, failures, "breakthrough_attempt_receipt_valid", breakthrough.get("receipt_valid"), True)
    fail_if(breakthrough.get("failure_count") != 0, failures, "breakthrough_attempt_failure_count", breakthrough.get("failure_count"), 0)
    fail_if(breakthrough.get("source_access_attempt_recorded") is not True, failures, "breakthrough_source_access_attempt_recorded", breakthrough.get("source_access_attempt_recorded"), True)
    fail_if(breakthrough.get("foldx_runtime_probe_recorded") is not True, failures, "breakthrough_foldx_runtime_probe_recorded", breakthrough.get("foldx_runtime_probe_recorded"), True)
    fail_if(breakthrough.get("external_sqlite_mutated") is not False, failures, "breakthrough_external_sqlite_mutated_false", breakthrough.get("external_sqlite_mutated"), False)
    fail_if(breakthrough.get("apply_executed") is not False, failures, "breakthrough_apply_executed_false", breakthrough.get("apply_executed"), False)
    fail_if(breakthrough.get("export_safe_released") is not False, failures, "breakthrough_export_safe_released_false", breakthrough.get("export_safe_released"), False)
    fail_if(breakthrough.get("safe_for_model_claim") is not False, failures, "breakthrough_safe_for_model_claim_false", breakthrough.get("safe_for_model_claim"), False)
    fail_if(breakthrough.get("formal_decision_rows_written") != 0, failures, "breakthrough_formal_decision_rows_written_zero", breakthrough.get("formal_decision_rows_written"), 0)

    unblock_packets = summaries.get("unblock_operator_packet_validation", {})
    fail_if(unblock_packets.get("packets_valid") is not True, failures, "unblock_operator_packets_valid", unblock_packets.get("packets_valid"), True)
    fail_if(unblock_packets.get("failure_count") != 0, failures, "unblock_operator_packets_failure_count", unblock_packets.get("failure_count"), 0)
    fail_if(unblock_packets.get("source_acquisition_packets") != 4, failures, "unblock_source_acquisition_packets", unblock_packets.get("source_acquisition_packets"), 4)
    fail_if(unblock_packets.get("foldx_runtime_packets") != 1, failures, "unblock_foldx_runtime_packets", unblock_packets.get("foldx_runtime_packets"), 1)
    fail_if(unblock_packets.get("external_sqlite_mutated") is not False, failures, "unblock_external_sqlite_mutated_false", unblock_packets.get("external_sqlite_mutated"), False)
    fail_if(unblock_packets.get("export_safe_released") is not False, failures, "unblock_export_safe_released_false", unblock_packets.get("export_safe_released"), False)
    fail_if(unblock_packets.get("safe_for_model_claim") is not False, failures, "unblock_safe_for_model_claim_false", unblock_packets.get("safe_for_model_claim"), False)
    fail_if(unblock_packets.get("formal_decision_rows_written") != 0, failures, "unblock_formal_decision_rows_written_zero", unblock_packets.get("formal_decision_rows_written"), 0)

    source_drop = summaries.get("source_drop_manifest_validation", {})
    fail_if(source_drop.get("manifest_valid") is not True, failures, "source_drop_manifest_valid", source_drop.get("manifest_valid"), True)
    fail_if(source_drop.get("failure_count") != 0, failures, "source_drop_failure_count", source_drop.get("failure_count"), 0)
    fail_if(source_drop.get("source_rows") != 8, failures, "source_drop_source_rows", source_drop.get("source_rows"), 8)
    fail_if(source_drop.get("unique_source_id_rows") != 8, failures, "source_drop_unique_source_id_rows", source_drop.get("unique_source_id_rows"), 8)
    fail_if(source_drop.get("unique_expected_path_rows") != 8, failures, "source_drop_unique_expected_path_rows", source_drop.get("unique_expected_path_rows"), 8)
    fail_if(source_drop.get("exact_source_contract") is not True, failures, "source_drop_exact_source_contract", source_drop.get("exact_source_contract"), True)
    fail_if(source_drop.get("duplicate_resolved_source_paths") != [], failures, "source_drop_duplicate_resolved_paths_empty", source_drop.get("duplicate_resolved_source_paths"), [])
    fail_if(source_drop.get("external_sqlite_mutated") is not False, failures, "source_drop_external_sqlite_mutated_false", source_drop.get("external_sqlite_mutated"), False)
    fail_if(source_drop.get("export_safe_released") is not False, failures, "source_drop_export_safe_released_false", source_drop.get("export_safe_released"), False)
    fail_if(source_drop.get("safe_for_model_claim") is not False, failures, "source_drop_safe_for_model_claim_false", source_drop.get("safe_for_model_claim"), False)
    fail_if(source_drop.get("formal_decision_rows_written") != 0, failures, "source_drop_formal_decision_rows_written_zero", source_drop.get("formal_decision_rows_written"), 0)

    source_inventory = summaries.get("source_drop_inventory_validation", {})
    fail_if(source_inventory.get("inventory_valid") is not True, failures, "source_drop_inventory_valid", source_inventory.get("inventory_valid"), True)
    fail_if(source_inventory.get("failure_count") != 0, failures, "source_drop_inventory_failure_count", source_inventory.get("failure_count"), 0)
    fail_if(source_inventory.get("directory_rows") != 4, failures, "source_drop_inventory_directory_rows", source_inventory.get("directory_rows"), 4)
    fail_if(source_inventory.get("expected_file_rows") != 8, failures, "source_drop_inventory_expected_file_rows", source_inventory.get("expected_file_rows"), 8)
    fail_if(source_inventory.get("unique_expected_file_path_rows") != 8, failures, "source_drop_inventory_unique_expected_file_path_rows", source_inventory.get("unique_expected_file_path_rows"), 8)
    fail_if(source_inventory.get("unique_source_id_rows") != 8, failures, "source_drop_inventory_unique_source_id_rows", source_inventory.get("unique_source_id_rows"), 8)
    fail_if(source_inventory.get("inventory_matches_manifest") is not True, failures, "source_drop_inventory_matches_manifest", source_inventory.get("inventory_matches_manifest"), True)
    fail_if(source_inventory.get("filesystem_state_matches") is not True, failures, "source_drop_inventory_filesystem_state_matches", source_inventory.get("filesystem_state_matches"), True)
    fail_if(source_inventory.get("directory_inventory_exact") is not True, failures, "source_drop_inventory_directory_inventory_exact", source_inventory.get("directory_inventory_exact"), True)
    fail_if(source_inventory.get("ready_for_sqlite_apply_rows") != 0, failures, "source_drop_inventory_ready_for_sqlite_apply_rows_zero", source_inventory.get("ready_for_sqlite_apply_rows"), 0)
    for flag in ("external_sqlite_mutated", "apply_executed", "export_safe_released", "safe_for_model_claim", "release_ready"):
        fail_if(source_inventory.get(flag) is not False, failures, f"source_drop_inventory.{flag}_false", source_inventory.get(flag), False)
    fail_if(source_inventory.get("formal_decision_rows_written") != 0, failures, "source_drop_inventory_formal_decision_rows_written_zero", source_inventory.get("formal_decision_rows_written"), 0)

    source_acquisition = summaries.get("source_acquisition_receipts_validation", {})
    fail_if(source_acquisition.get("receipt_valid") is not True, failures, "source_acquisition_receipt_valid", source_acquisition.get("receipt_valid"), True)
    fail_if(source_acquisition.get("failure_count") != 0, failures, "source_acquisition_receipt_failure_count", source_acquisition.get("failure_count"), 0)
    fail_if(source_acquisition.get("receipt_rows") != 4, failures, "source_acquisition_receipt_rows", source_acquisition.get("receipt_rows"), 4)
    fail_if(source_acquisition.get("public_asset_rows") != 2, failures, "source_acquisition_public_asset_rows", source_acquisition.get("public_asset_rows"), 2)
    fail_if(source_acquisition.get("probe_only_rows") != 2, failures, "source_acquisition_probe_only_rows", source_acquisition.get("probe_only_rows"), 2)
    fail_if(source_acquisition.get("source_file_obtained_rows") != 2, failures, "source_acquisition_source_file_obtained_rows", source_acquisition.get("source_file_obtained_rows"), 2)
    fail_if(source_acquisition.get("source_file_not_obtained_rows") != 2, failures, "source_acquisition_source_file_not_obtained_rows", source_acquisition.get("source_file_not_obtained_rows"), 2)
    fail_if(source_acquisition.get("probe_expected_missing_path_rows") != 4, failures, "source_acquisition_probe_expected_missing_path_rows", source_acquisition.get("probe_expected_missing_path_rows"), 4)
    fail_if(source_acquisition.get("official_asset_public") is not True, failures, "source_acquisition_official_asset_public", source_acquisition.get("official_asset_public"), True)
    fail_if(source_acquisition.get("acquisition_integrity_verified") is not True, failures, "source_acquisition_integrity_verified", source_acquisition.get("acquisition_integrity_verified"), True)
    fail_if(source_acquisition.get("acquisition_integrity_verified_rows") != 2, failures, "source_acquisition_integrity_verified_rows", source_acquisition.get("acquisition_integrity_verified_rows"), 2)
    fail_if(source_acquisition.get("document_locator_candidate_rows") != 7, failures, "source_acquisition_locator_candidate_rows", source_acquisition.get("document_locator_candidate_rows"), 7)
    fail_if(source_acquisition.get("dsm4_identity_locator_candidate_rows") != 3, failures, "source_acquisition_dsm4_locator_rows", source_acquisition.get("dsm4_identity_locator_candidate_rows"), 3)
    fail_if(source_acquisition.get("structured_locator_candidate_count") != 7, failures, "source_acquisition_structured_locator_rows", source_acquisition.get("structured_locator_candidate_count"), 7)
    fail_if(source_acquisition.get("structured_locator_measurement_candidate_rows") != 3, failures, "source_acquisition_structured_measurement_locator_rows", source_acquisition.get("structured_locator_measurement_candidate_rows"), 3)
    fail_if(source_acquisition.get("structured_locator_identity_candidate_rows") != 3, failures, "source_acquisition_structured_identity_locator_rows", source_acquisition.get("structured_locator_identity_candidate_rows"), 3)
    fail_if(source_acquisition.get("structured_locator_composition_resolved_rows") != 0, failures, "source_acquisition_structured_composition_resolved_rows_zero", source_acquisition.get("structured_locator_composition_resolved_rows"), 0)
    fail_if(source_acquisition.get("dsm4_composition_resolved") is not False, failures, "source_acquisition_dsm4_composition_unresolved", source_acquisition.get("dsm4_composition_resolved"), False)
    fail_if(source_acquisition.get("zenodo_archive_integrity_verified") is not True, failures, "source_acquisition_zenodo_archive_integrity_verified", source_acquisition.get("zenodo_archive_integrity_verified"), True)
    fail_if(source_acquisition.get("cm5_sequence_member_verified") is not True, failures, "source_acquisition_cm5_sequence_member_verified", source_acquisition.get("cm5_sequence_member_verified"), True)
    fail_if(source_acquisition.get("cm5_candidate_substitutions") != ["L15R", "S45T", "K85P", "K231R"], failures, "source_acquisition_cm5_candidate_substitutions", source_acquisition.get("cm5_candidate_substitutions"), ["L15R", "S45T", "K85P", "K231R"])
    fail_if(source_acquisition.get("declared_substitutions_corroborated") is not True, failures, "source_acquisition_declared_substitutions_corroborated", source_acquisition.get("declared_substitutions_corroborated"), True)
    fail_if(source_acquisition.get("undeclared_substitution_candidates") != ["L262V"], failures, "source_acquisition_undeclared_substitution_candidates", source_acquisition.get("undeclared_substitution_candidates"), ["L262V"])
    fail_if(source_acquisition.get("nucleotide_pdb_discrepancy") is not True, failures, "source_acquisition_nucleotide_pdb_discrepancy", source_acquisition.get("nucleotide_pdb_discrepancy"), True)
    fail_if(source_acquisition.get("complete_composition_unambiguous") is not False, failures, "source_acquisition_complete_composition_unambiguous_false", source_acquisition.get("complete_composition_unambiguous"), False)
    fail_if(source_acquisition.get("cm5_composition_candidate_resolved") is not False, failures, "source_acquisition_cm5_composition_candidate_resolved_false", source_acquisition.get("cm5_composition_candidate_resolved"), False)
    for field, expected in (("codon262_sequence_member_rows", 11), ("codon262_coverage_rows", 9), ("codon262_no_coverage_rows", 2), ("codon262_wt_codon_rows", 8), ("codon262_variant_codon_rows", 1)):
        fail_if(source_acquisition.get(field) != expected, failures, f"source_acquisition.{field}", source_acquisition.get(field), expected)
    fail_if(source_acquisition.get("cm5_composition_formally_reviewed") is not False, failures, "source_acquisition_cm5_composition_formally_reviewed_false", source_acquisition.get("cm5_composition_formally_reviewed"), False)
    fail_if(source_acquisition.get("reviewed_source_locator_rows") != 0, failures, "source_acquisition_reviewed_locator_rows_zero", source_acquisition.get("reviewed_source_locator_rows"), 0)
    for flag in ("reviewed_extraction_completed", "source_evidence_ready", "ready_for_reviewed_extraction", "ready_for_sqlite_apply", "external_sqlite_mutated", "apply_executed", "export_safe_released", "safe_for_model_claim", "release_ready"):
        fail_if(source_acquisition.get(flag) is not False, failures, f"source_acquisition.{flag}_false", source_acquisition.get(flag), False)
    fail_if(source_acquisition.get("formal_decision_rows_written") != 0, failures, "source_acquisition_formal_decision_rows_written_zero", source_acquisition.get("formal_decision_rows_written"), 0)

    source_extraction = summaries.get("source_extraction_candidate_validation", {})
    fail_if(source_extraction.get("validation_success") is not True, failures, "source_extraction_candidate_valid", source_extraction.get("validation_success"), True)
    fail_if(source_extraction.get("failure_count") != 0, failures, "source_extraction_candidate_failure_count", source_extraction.get("failure_count"), 0)
    fail_if(source_extraction.get("candidate_rows") != 2, failures, "source_extraction_candidate_rows", source_extraction.get("candidate_rows"), 2)
    fail_if(source_extraction.get("source_sha256_verified") is not True, failures, "source_extraction_candidate_source_sha256", source_extraction.get("source_sha256_verified"), True)
    fail_if(source_extraction.get("document_text_extraction_succeeded") is not True, failures, "source_extraction_candidate_text_extraction", source_extraction.get("document_text_extraction_succeeded"), True)
    fail_if(source_extraction.get("table_s1_primer_rows") != 38, failures, "source_extraction_candidate_table_s1_rows", source_extraction.get("table_s1_primer_rows"), 38)
    fail_if(source_extraction.get("table_s2_disulfide_bridge_rows") != 4, failures, "source_extraction_candidate_table_s2_rows", source_extraction.get("table_s2_disulfide_bridge_rows"), 4)
    fail_if(source_extraction.get("image_ocr_numeric_rows") != 0, failures, "source_extraction_candidate_image_ocr_numeric_rows_zero", source_extraction.get("image_ocr_numeric_rows"), 0)
    fail_if(source_extraction.get("cm5_sequence_member_verified") is not True, failures, "source_extraction_cm5_sequence_member_verified", source_extraction.get("cm5_sequence_member_verified"), True)
    fail_if(source_extraction.get("cm5_pdb_wt_residue_parity_verified") is not True, failures, "source_extraction_cm5_pdb_wt_residue_parity_verified", source_extraction.get("cm5_pdb_wt_residue_parity_verified"), True)
    fail_if(source_extraction.get("cm5_candidate_substitutions") != ["L15R", "S45T", "K85P", "K231R"], failures, "source_extraction_cm5_candidate_substitutions", source_extraction.get("cm5_candidate_substitutions"), ["L15R", "S45T", "K85P", "K231R"])
    fail_if(source_extraction.get("declared_substitutions_corroborated") is not True, failures, "source_extraction_declared_substitutions_corroborated", source_extraction.get("declared_substitutions_corroborated"), True)
    fail_if(source_extraction.get("undeclared_substitution_candidates") != ["L262V"], failures, "source_extraction_undeclared_substitution_candidates", source_extraction.get("undeclared_substitution_candidates"), ["L262V"])
    fail_if(source_extraction.get("nucleotide_pdb_discrepancy_verified") is not True, failures, "source_extraction_nucleotide_pdb_discrepancy_verified", source_extraction.get("nucleotide_pdb_discrepancy_verified"), True)
    fail_if(source_extraction.get("complete_composition_unambiguous") is not False, failures, "source_extraction_complete_composition_unambiguous_false", source_extraction.get("complete_composition_unambiguous"), False)
    fail_if(source_extraction.get("cm5_composition_candidate_resolved") is not False, failures, "source_extraction_candidate_cm5_resolved_false", source_extraction.get("cm5_composition_candidate_resolved"), False)
    fail_if(source_extraction.get("codon262_cross_read_matrix_verified") is not True, failures, "source_extraction_codon262_cross_read_matrix_verified", source_extraction.get("codon262_cross_read_matrix_verified"), True)
    for field, expected in (("codon262_sequence_member_rows", 11), ("codon262_coverage_rows", 9), ("codon262_no_coverage_rows", 2), ("codon262_wt_codon_rows", 8), ("codon262_variant_codon_rows", 1)):
        fail_if(source_extraction.get(field) != expected, failures, f"source_extraction.{field}", source_extraction.get(field), expected)
    fail_if(source_extraction.get("cm5_composition_formally_reviewed") is not False, failures, "source_extraction_candidate_cm5_formally_reviewed_false", source_extraction.get("cm5_composition_formally_reviewed"), False)
    fail_if(source_extraction.get("complete_cm5_candidate_residue_rows") != 4, failures, "source_extraction_candidate_cm5_rows", source_extraction.get("complete_cm5_candidate_residue_rows"), 4)
    fail_if(source_extraction.get("mutation_effect_measurement_rows") != 0, failures, "source_extraction_candidate_cm5_measurements_zero", source_extraction.get("mutation_effect_measurement_rows"), 0)
    for field in ("dsm4_composition_resolved", "reviewed_extraction_completed", "source_evidence_ready", "ready_for_reviewed_extraction", "ready_for_sqlite_apply", "external_sqlite_mutated", "apply_executed", "export_safe_released", "safe_for_model_claim", "release_ready"):
        fail_if(source_extraction.get(field) is not False, failures, f"source_extraction.{field}_false", source_extraction.get(field), False)
    for field in ("complete_dsm4_residue_rows", "wt_absolute_baseline_rows", "measurement_locator_rows", "reviewed_source_locator_rows", "formal_decision_rows_written"):
        fail_if(source_extraction.get(field) != 0, failures, f"source_extraction.{field}_zero", source_extraction.get(field), 0)

    reviewer_packet = summaries.get("source_extraction_candidate_reviewer_packet_validation", {})
    fail_if(reviewer_packet.get("packet_valid") is not True, failures, "source_extraction_reviewer_packet_valid", reviewer_packet.get("packet_valid"), True)
    fail_if(reviewer_packet.get("reviewer_packet_valid") is not True, failures, "source_extraction_reviewer_packet_alias_valid", reviewer_packet.get("reviewer_packet_valid"), True)
    fail_if(reviewer_packet.get("failure_count") != 0, failures, "source_extraction_reviewer_packet_failure_count", reviewer_packet.get("failure_count"), 0)
    fail_if(reviewer_packet.get("packet_rows") != 2, failures, "source_extraction_reviewer_packet_rows", reviewer_packet.get("packet_rows"), 2)
    fail_if(reviewer_packet.get("reviewer_rows") != 2, failures, "source_extraction_reviewer_packet_alias_rows", reviewer_packet.get("reviewer_rows"), 2)
    fail_if(reviewer_packet.get("unique_pmid_rows") != 2, failures, "source_extraction_reviewer_packet_unique_pmid_rows", reviewer_packet.get("unique_pmid_rows"), 2)
    fail_if(reviewer_packet.get("needs_more_info_rows") != 2, failures, "source_extraction_reviewer_packet_needs_more_info_rows", reviewer_packet.get("needs_more_info_rows"), 2)
    fail_if(reviewer_packet.get("candidate_ready_for_human_review_rows") != 2, failures, "source_extraction_reviewer_packet_human_review_rows", reviewer_packet.get("candidate_ready_for_human_review_rows"), 2)
    fail_if(reviewer_packet.get("reviewer_completed_rows") != 0, failures, "source_extraction_reviewer_packet_reviewer_completed_rows_zero", reviewer_packet.get("reviewer_completed_rows"), 0)
    fail_if(reviewer_packet.get("composition_candidate_resolved_rows") != 0, failures, "source_extraction_reviewer_packet_composition_candidate_rows_zero", reviewer_packet.get("composition_candidate_resolved_rows"), 0)
    fail_if(reviewer_packet.get("dsm4_unresolved_rows") != 1, failures, "source_extraction_reviewer_packet_dsm4_unresolved_rows", reviewer_packet.get("dsm4_unresolved_rows"), 1)
    fail_if(reviewer_packet.get("cm5_composition_ambiguous_rows") != 1, failures, "source_extraction_reviewer_packet_cm5_ambiguous_rows", reviewer_packet.get("cm5_composition_ambiguous_rows"), 1)
    fail_if(reviewer_packet.get("declared_substitutions_corroborated_rows") != 1, failures, "source_extraction_reviewer_packet_declared_substitutions_rows", reviewer_packet.get("declared_substitutions_corroborated_rows"), 1)
    fail_if(reviewer_packet.get("nucleotide_pdb_discrepancy_rows") != 1, failures, "source_extraction_reviewer_packet_discrepancy_rows", reviewer_packet.get("nucleotide_pdb_discrepancy_rows"), 1)
    for field, expected in (("codon262_sequence_member_rows", 11), ("codon262_coverage_rows", 9), ("codon262_no_coverage_rows", 2), ("codon262_wt_codon_rows", 8), ("codon262_variant_codon_rows", 1)):
        fail_if(reviewer_packet.get(field) != expected, failures, f"source_extraction_reviewer_packet.{field}", reviewer_packet.get(field), expected)
    fail_if(reviewer_packet.get("approved_for_reviewed_extraction_rows") != 0, failures, "source_extraction_reviewer_packet_approved_rows_zero", reviewer_packet.get("approved_for_reviewed_extraction_rows"), 0)
    fail_if(reviewer_packet.get("formal_review_rows") != 0, failures, "source_extraction_reviewer_packet_formal_review_rows_zero", reviewer_packet.get("formal_review_rows"), 0)
    for field in ("approved_rows", "reviewed_extraction_rows", "reviewer_filled_rows", "source_locator_rows"):
        fail_if(reviewer_packet.get(field) != 0, failures, f"source_extraction_reviewer_packet.{field}_zero", reviewer_packet.get(field), 0)
    fail_if(reviewer_packet.get("required_review_field_rows") != 12, failures, "source_extraction_reviewer_packet_required_field_rows", reviewer_packet.get("required_review_field_rows"), 12)
    for field in ("reviewed_source_locator_rows", "reviewed_extraction_completed_rows", "source_evidence_ready_rows", "ready_for_sqlite_apply_rows"):
        fail_if(reviewer_packet.get(field) != 0, failures, f"source_extraction_reviewer_packet.{field}_zero", reviewer_packet.get(field), 0)
    for flag in ("external_sqlite_mutated", "apply_executed", "export_safe_released", "safe_for_model_claim", "release_ready"):
        fail_if(reviewer_packet.get(flag) is not False, failures, f"source_extraction_reviewer_packet.{flag}_false", reviewer_packet.get(flag), False)
    fail_if(reviewer_packet.get("formal_decision_rows_written") != 0, failures, "source_extraction_reviewer_packet_formal_decisions_zero", reviewer_packet.get("formal_decision_rows_written"), 0)

    reviewer_closure = summaries.get("source_extraction_reviewer_closure_checklist_validation", {})
    fail_if(reviewer_closure.get("checklist_valid") is not True, failures, "source_extraction_reviewer_closure_valid", reviewer_closure.get("checklist_valid"), True)
    fail_if(reviewer_closure.get("failure_count") != 0, failures, "source_extraction_reviewer_closure_failure_count", reviewer_closure.get("failure_count"), 0)
    for field, expected in (("checklist_rows", 12), ("unique_check_rows", 12), ("dsm4_rows", 5), ("cm5_rows", 7), ("cm5_l262v_discrepancy_rows", 1), ("missing_rows", 12), ("needs_more_info_rows", 12)):
        fail_if(reviewer_closure.get(field) != expected, failures, f"source_extraction_reviewer_closure.{field}", reviewer_closure.get(field), expected)
    for field in ("evidence_supplied_rows", "reviewed_rows", "completed_rows", "reviewer_filled_rows", "source_locator_rows", "approved_rows", "ready_for_reviewed_extraction_rows", "ready_for_sqlite_apply_rows"):
        fail_if(reviewer_closure.get(field) != 0, failures, f"source_extraction_reviewer_closure.{field}_zero", reviewer_closure.get(field), 0)
    for flag in ("external_sqlite_mutated", "apply_executed", "export_safe_released", "safe_for_model_claim", "release_ready"):
        fail_if(reviewer_closure.get(flag) is not False, failures, f"source_extraction_reviewer_closure.{flag}_false", reviewer_closure.get(flag), False)
    fail_if(reviewer_closure.get("formal_decision_rows_written") != 0, failures, "source_extraction_reviewer_closure.formal_decision_rows_written_zero", reviewer_closure.get("formal_decision_rows_written"), 0)

    codon262_audit = summaries.get("cm5_codon262_cross_read_audit_validation", {})
    fail_if(codon262_audit.get("audit_valid") is not True, failures, "cm5_codon262_cross_read_audit_valid", codon262_audit.get("audit_valid"), True)
    fail_if(codon262_audit.get("failure_count") != 0, failures, "cm5_codon262_cross_read_audit_failure_count", codon262_audit.get("failure_count"), 0)
    for field, expected in (("read_rows", 11), ("covered_rows", 9), ("not_covered_rows", 2), ("ttg_rows", 8), ("gtg_rows", 1), ("cm5_gtg_rows", 1), ("non_cm5_ttg_rows", 8)):
        fail_if(codon262_audit.get(field) != expected, failures, f"cm5_codon262_cross_read_audit.{field}", codon262_audit.get(field), expected)
    for field in ("cross_read_consensus_supports_wt_leu262", "cm5_single_read_outlier"):
        fail_if(codon262_audit.get(field) is not True, failures, f"cm5_codon262_cross_read_audit.{field}_true", codon262_audit.get(field), True)
    for field in ("discrepancy_resolved", "complete_composition_unambiguous", "reviewed_extraction_completed", "reviewer_decision_written", "ready_for_sqlite_apply", "external_sqlite_mutated", "apply_executed", "export_safe_released", "safe_for_model_claim", "release_ready"):
        fail_if(codon262_audit.get(field) is not False, failures, f"cm5_codon262_cross_read_audit.{field}_false", codon262_audit.get(field), False)
    fail_if(codon262_audit.get("formal_decision_rows_written") != 0, failures, "cm5_codon262_cross_read_audit.formal_decision_rows_written_zero", codon262_audit.get("formal_decision_rows_written"), 0)

    quality_audit = summaries.get("cm5_codon262_sequence_quality_evidence_audit_validation", {})
    fail_if(quality_audit.get("audit_valid") is not True, failures, "cm5_codon262_sequence_quality_evidence_audit_valid", quality_audit.get("audit_valid"), True)
    fail_if(quality_audit.get("failure_count") != 0, failures, "cm5_codon262_sequence_quality_evidence_audit_failure_count", quality_audit.get("failure_count"), 0)
    for field, expected in (
        ("sequencing_file_rows", 12),
        ("seq_read_rows", 11),
        ("snapgene_dna_rows", 1),
        ("sequence_text_only_rows", 11),
        ("quality_bearing_artifact_rows", 0),
        ("chromatogram_artifact_rows", 0),
        ("per_base_quality_artifact_rows", 0),
        ("cm5_codon_262_raw_text_call", "GTG"),
    ):
        fail_if(quality_audit.get(field) != expected, failures, f"cm5_codon262_sequence_quality_evidence_audit.{field}", quality_audit.get(field), expected)
    for field in ("cm5_quality_evidence_available", "sequencing_artifact_hypothesis_confirmed", "discrepancy_resolved", "complete_composition_unambiguous", "reviewed_extraction_completed", "reviewer_decision_written", "ready_for_sqlite_apply", "external_sqlite_mutated", "apply_executed", "export_safe_released", "safe_for_model_claim", "release_ready"):
        fail_if(quality_audit.get(field) is not False, failures, f"cm5_codon262_sequence_quality_evidence_audit.{field}_false", quality_audit.get(field), False)
    fail_if(quality_audit.get("formal_decision_rows_written") != 0, failures, "cm5_codon262_sequence_quality_evidence_audit.formal_decision_rows_written_zero", quality_audit.get("formal_decision_rows_written"), 0)

    l262v_adjudication = summaries.get("cm5_l262v_discrepancy_adjudication_packet_validation", {})
    fail_if(l262v_adjudication.get("packet_valid") is not True, failures, "cm5_l262v_adjudication_packet_valid", l262v_adjudication.get("packet_valid"), True)
    fail_if(l262v_adjudication.get("failure_count") != 0, failures, "cm5_l262v_adjudication_failure_count", l262v_adjudication.get("failure_count"), 0)
    for field, expected in (
        ("packet_rows", 1),
        ("evidence_rows", 11),
        ("direct_cm5_read_rows", 1),
        ("other_construct_ttg_context_rows", 8),
        ("other_construct_no_coverage_rows", 2),
        ("cm5_independent_replicate_rows", 0),
        ("reviewed_raw_trace_rows", 0),
        ("quality_bearing_artifact_rows", 0),
        ("allowed_adjudication_option_rows", 4),
        ("workflow_status", "needs_more_info"),
    ):
        fail_if(l262v_adjudication.get(field) != expected, failures, f"cm5_l262v_adjudication.{field}", l262v_adjudication.get(field), expected)
    for field in ("review_fields_empty", "cross_construct_consensus_only"):
        fail_if(l262v_adjudication.get(field) is not True, failures, f"cm5_l262v_adjudication.{field}_true", l262v_adjudication.get(field), True)
    for field in ("other_construct_context_can_resolve_cm5", "review_completed", "discrepancy_resolved", "complete_composition_unambiguous", "reviewed_extraction_completed", "ready_for_sqlite_apply", "external_sqlite_mutated", "apply_executed", "export_safe_released", "safe_for_model_claim", "release_ready"):
        fail_if(l262v_adjudication.get(field) is not False, failures, f"cm5_l262v_adjudication.{field}_false", l262v_adjudication.get(field), False)
    fail_if(l262v_adjudication.get("formal_decision_rows_written") != 0, failures, "cm5_l262v_adjudication.formal_decision_rows_written_zero", l262v_adjudication.get("formal_decision_rows_written"), 0)

    l262v_decision_intake = summaries.get("cm5_l262v_adjudication_decision_intake_validation", {})
    fail_if(l262v_decision_intake.get("intake_valid") is not True, failures, "cm5_l262v_decision_intake_valid", l262v_decision_intake.get("intake_valid"), True)
    fail_if(l262v_decision_intake.get("failure_count") != 0, failures, "cm5_l262v_decision_intake_failure_count", l262v_decision_intake.get("failure_count"), 0)
    for field in ("decision_rows", "valid_decision_rows", "invalid_decision_rows", "needs_more_info_rows", "non_needs_more_info_candidate_rows", "evidence_artifact_rows", "accepted_review_rows", "review_bound_evidence_rows", "unreviewed_evidence_artifact_rows", "slot_compatible_evidence_rows", "slot_incompatible_evidence_rows", "reviewer_bound_evidence_rows", "missing_review_reviewer_rows", "formal_decision_rows_written", "discrepancy_resolved_rows", "complete_composition_unambiguous_rows", "reviewed_extraction_completed_rows", "ready_for_sqlite_apply_rows"):
        fail_if(l262v_decision_intake.get(field) != 0, failures, f"cm5_l262v_decision_intake.{field}_zero", l262v_decision_intake.get(field), 0)
    fail_if(l262v_decision_intake.get("review_binding_valid") is not True, failures, "cm5_l262v_decision_intake.review_binding_valid_true", l262v_decision_intake.get("review_binding_valid"), True)
    fail_if(l262v_decision_intake.get("slot_binding_valid") is not True, failures, "cm5_l262v_decision_intake.slot_binding_valid_true", l262v_decision_intake.get("slot_binding_valid"), True)
    fail_if(l262v_decision_intake.get("reviewer_provenance_valid") is not True, failures, "cm5_l262v_decision_intake.reviewer_provenance_valid_true", l262v_decision_intake.get("reviewer_provenance_valid"), True)
    for field in ("external_sqlite_mutated", "apply_executed", "export_safe_released", "safe_for_model_claim", "release_ready"):
        fail_if(l262v_decision_intake.get(field) is not False, failures, f"cm5_l262v_decision_intake.{field}_false", l262v_decision_intake.get(field), False)

    l262v_review_binding_regression = summaries.get("cm5_l262v_adjudication_review_binding_regression", {})
    fail_if(l262v_review_binding_regression.get("success") is not True, failures, "cm5_l262v_review_binding_regression_success", l262v_review_binding_regression.get("success"), True)
    for field, expected in (("case_rows", 3), ("passed_rows", 3), ("failed_rows", 0), ("formal_decision_rows_written", 0)):
        fail_if(l262v_review_binding_regression.get(field) != expected, failures, f"cm5_l262v_review_binding_regression.{field}", l262v_review_binding_regression.get(field), expected)
    for field in ("real_decision_input_mutated", "discrepancy_resolved", "external_sqlite_mutated", "apply_executed", "safe_for_model_claim", "release_ready"):
        fail_if(l262v_review_binding_regression.get(field) is not False, failures, f"cm5_l262v_review_binding_regression.{field}_false", l262v_review_binding_regression.get(field), False)

    l262v_review_binding_tamper = summaries.get("cm5_l262v_adjudication_review_binding_tamper_regression", {})
    fail_if(l262v_review_binding_tamper.get("success") is not True, failures, "cm5_l262v_review_binding_tamper_success", l262v_review_binding_tamper.get("success"), True)
    for field, expected in (
        ("case_rows", 5),
        ("passed_rows", 5),
        ("failed_rows", 0),
        ("forged_sha_rejected_rows", 1),
        ("cross_bound_review_rejected_rows", 1),
        ("unsupported_option_rejected_rows", 1),
        ("slot_class_mismatch_rejected_rows", 1),
        ("invalid_decision_timestamp_rejected_rows", 1),
        ("formal_decision_rows_written", 0),
    ):
        fail_if(l262v_review_binding_tamper.get(field) != expected, failures, f"cm5_l262v_review_binding_tamper.{field}", l262v_review_binding_tamper.get(field), expected)
    for field in ("real_decision_input_mutated", "real_review_input_mutated", "real_receipt_input_mutated", "discrepancy_resolved", "external_sqlite_mutated", "apply_executed", "safe_for_model_claim", "release_ready"):
        fail_if(l262v_review_binding_tamper.get(field) is not False, failures, f"cm5_l262v_review_binding_tamper.{field}_false", l262v_review_binding_tamper.get(field), False)

    l262v_path_safety = summaries.get("cm5_l262v_adjudication_evidence_path_safety_regression", {})
    fail_if(l262v_path_safety.get("success") is not True, failures, "cm5_l262v_path_safety_success", l262v_path_safety.get("success"), True)
    for field, expected in (
        ("case_rows", 3),
        ("passed_rows", 3),
        ("failed_rows", 0),
        ("duplicate_review_id_rejected_rows", 1),
        ("unsafe_relative_path_rejected_rows", 1),
        ("missing_artifact_rejected_rows", 1),
        ("formal_decision_rows_written", 0),
    ):
        fail_if(l262v_path_safety.get(field) != expected, failures, f"cm5_l262v_path_safety.{field}", l262v_path_safety.get(field), expected)
    for field in ("real_decision_input_mutated", "real_review_input_mutated", "real_receipt_input_mutated", "discrepancy_resolved", "external_sqlite_mutated", "apply_executed", "safe_for_model_claim", "release_ready"):
        fail_if(l262v_path_safety.get(field) is not False, failures, f"cm5_l262v_path_safety.{field}_false", l262v_path_safety.get(field), False)

    l262v_upstream_provenance = summaries.get("cm5_l262v_adjudication_upstream_review_provenance_regression", {})
    fail_if(l262v_upstream_provenance.get("success") is not True, failures, "cm5_l262v_upstream_provenance_success", l262v_upstream_provenance.get("success"), True)
    for field, expected in (
        ("case_rows", 3),
        ("passed_rows", 3),
        ("failed_rows", 0),
        ("invalid_upstream_review_intake_rejected_rows", 1),
        ("stale_review_input_sha_rejected_rows", 1),
        ("stale_receipt_input_sha_rejected_rows", 1),
        ("formal_decision_rows_written", 0),
    ):
        fail_if(l262v_upstream_provenance.get(field) != expected, failures, f"cm5_l262v_upstream_provenance.{field}", l262v_upstream_provenance.get(field), expected)
    for field in ("real_decision_input_mutated", "real_review_input_mutated", "real_receipt_input_mutated", "discrepancy_resolved", "external_sqlite_mutated", "apply_executed", "safe_for_model_claim", "release_ready"):
        fail_if(l262v_upstream_provenance.get(field) is not False, failures, f"cm5_l262v_upstream_provenance.{field}_false", l262v_upstream_provenance.get(field), False)

    l262v_packet_provenance = summaries.get("cm5_l262v_adjudication_upstream_packet_provenance_regression", {})
    fail_if(l262v_packet_provenance.get("success") is not True, failures, "cm5_l262v_packet_provenance_success", l262v_packet_provenance.get("success"), True)
    for field, expected in (
        ("case_rows", 3),
        ("passed_rows", 3),
        ("failed_rows", 0),
        ("invalid_packet_validation_rejected_rows", 1),
        ("upstream_review_fields_nonempty_rejected_rows", 1),
        ("allowed_decision_set_drift_rejected_rows", 1),
        ("formal_decision_rows_written", 0),
    ):
        fail_if(l262v_packet_provenance.get(field) != expected, failures, f"cm5_l262v_packet_provenance.{field}", l262v_packet_provenance.get(field), expected)
    for field in ("real_packet_mutated", "real_packet_validation_mutated", "real_decision_input_mutated", "real_review_input_mutated", "real_receipt_input_mutated", "discrepancy_resolved", "external_sqlite_mutated", "apply_executed", "safe_for_model_claim", "release_ready"):
        fail_if(l262v_packet_provenance.get(field) is not False, failures, f"cm5_l262v_packet_provenance.{field}_false", l262v_packet_provenance.get(field), False)

    l262v_evidence_intake = summaries.get("cm5_l262v_adjudication_evidence_intake_validation", {})
    fail_if(l262v_evidence_intake.get("intake_valid") is not True, failures, "cm5_l262v_evidence_intake_valid", l262v_evidence_intake.get("intake_valid"), True)
    fail_if(l262v_evidence_intake.get("failure_count") != 0, failures, "cm5_l262v_evidence_intake_failure_count", l262v_evidence_intake.get("failure_count"), 0)
    for field, expected in (("slot_rows", 4), ("unique_path_rows", 4), ("present_rows", 0), ("missing_rows", 4), ("filesystem_parity_rows", 4), ("reviewed_evidence_rows", 0), ("ready_for_adjudication_rows", 0), ("ready_for_reviewed_extraction_rows", 0), ("ready_for_sqlite_apply_rows", 0)):
        fail_if(l262v_evidence_intake.get(field) != expected, failures, f"cm5_l262v_evidence_intake.{field}", l262v_evidence_intake.get(field), expected)
    for field in ("file_presence_is_reviewed_evidence", "discrepancy_resolved", "complete_composition_unambiguous", "external_sqlite_mutated", "apply_executed", "export_safe_released", "safe_for_model_claim", "release_ready"):
        fail_if(l262v_evidence_intake.get(field) is not False, failures, f"cm5_l262v_evidence_intake.{field}_false", l262v_evidence_intake.get(field), False)
    fail_if(l262v_evidence_intake.get("formal_decision_rows_written") != 0, failures, "cm5_l262v_evidence_intake.formal_decision_rows_written_zero", l262v_evidence_intake.get("formal_decision_rows_written"), 0)

    l262v_public_probe = summaries.get("cm5_l262v_public_source_probe_receipt_validation", {})
    fail_if(l262v_public_probe.get("receipt_valid") is not True, failures, "cm5_l262v_public_probe_valid", l262v_public_probe.get("receipt_valid"), True)
    fail_if(l262v_public_probe.get("failure_count") != 0, failures, "cm5_l262v_public_probe_failure_count", l262v_public_probe.get("failure_count"), 0)
    for field, expected in (("probe_rows", 4), ("metadata_only_rows", 3), ("zenodo_archive_only_rows", 1), ("slot_artifact_rows", 0), ("evidence_slot_rows", 4), ("evidence_slot_present_rows", 0), ("evidence_slot_missing_rows", 4)):
        fail_if(l262v_public_probe.get(field) != expected, failures, f"cm5_l262v_public_probe.{field}", l262v_public_probe.get(field), expected)
    for field in ("discrepancy_resolved", "external_sqlite_mutated", "apply_executed", "export_safe_released", "safe_for_model_claim", "release_ready"):
        fail_if(l262v_public_probe.get(field) is not False, failures, f"cm5_l262v_public_probe.{field}_false", l262v_public_probe.get(field), False)
    fail_if(l262v_public_probe.get("formal_decision_rows_written") != 0, failures, "cm5_l262v_public_probe.formal_decision_rows_written_zero", l262v_public_probe.get("formal_decision_rows_written"), 0)

    l262v_request_packet = summaries.get("cm5_l262v_external_evidence_request_packet_validation", {})
    fail_if(l262v_request_packet.get("packet_valid") is not True, failures, "cm5_l262v_request_packet_valid", l262v_request_packet.get("packet_valid"), True)
    fail_if(l262v_request_packet.get("failure_count") != 0, failures, "cm5_l262v_request_packet_failure_count", l262v_request_packet.get("failure_count"), 0)
    for field, expected in (("request_rows", 4), ("unique_request_rows", 4), ("request_sent_rows", 0), ("outbound_authorization_rows", 0), ("evidence_received_rows", 0), ("evidence_reviewed_rows", 0), ("completion_ready_rows", 0)):
        fail_if(l262v_request_packet.get(field) != expected, failures, f"cm5_l262v_request_packet.{field}", l262v_request_packet.get(field), expected)
    for field in ("discrepancy_resolved", "external_sqlite_mutated", "apply_executed", "export_safe_released", "safe_for_model_claim", "release_ready"):
        fail_if(l262v_request_packet.get(field) is not False, failures, f"cm5_l262v_request_packet.{field}_false", l262v_request_packet.get(field), False)
    fail_if(l262v_request_packet.get("formal_decision_rows_written") != 0, failures, "cm5_l262v_request_packet.formal_decision_rows_written_zero", l262v_request_packet.get("formal_decision_rows_written"), 0)

    l262v_evidence_receipts = summaries.get("cm5_l262v_external_evidence_receipt_validation", {})
    fail_if(l262v_evidence_receipts.get("intake_valid") is not True, failures, "cm5_l262v_evidence_receipts_valid", l262v_evidence_receipts.get("intake_valid"), True)
    fail_if(l262v_evidence_receipts.get("failure_count") != 0, failures, "cm5_l262v_evidence_receipts_failure_count", l262v_evidence_receipts.get("failure_count"), 0)
    for field, expected in (("request_rows", 4), ("evidence_slot_rows", 4), ("receipt_rows", 0), ("valid_receipt_rows", 0), ("present_artifact_rows", 0), ("unreceipted_present_artifact_rows", 0), ("receipt_without_artifact_rows", 0), ("evidence_reviewed_rows", 0), ("ready_for_adjudication_rows", 0)):
        fail_if(l262v_evidence_receipts.get(field) != expected, failures, f"cm5_l262v_evidence_receipts.{field}", l262v_evidence_receipts.get(field), expected)
    for field in ("discrepancy_resolved", "receipt_is_reviewed_evidence", "external_sqlite_mutated", "apply_executed", "export_safe_released", "safe_for_model_claim", "release_ready"):
        fail_if(l262v_evidence_receipts.get(field) is not False, failures, f"cm5_l262v_evidence_receipts.{field}_false", l262v_evidence_receipts.get(field), False)
    fail_if(l262v_evidence_receipts.get("formal_decision_rows_written") != 0, failures, "cm5_l262v_evidence_receipts.formal_decision_rows_written_zero", l262v_evidence_receipts.get("formal_decision_rows_written"), 0)

    l262v_evidence_reviews = summaries.get("cm5_l262v_external_evidence_review_validation", {})
    fail_if(l262v_evidence_reviews.get("intake_valid") is not True, failures, "cm5_l262v_evidence_reviews_valid", l262v_evidence_reviews.get("intake_valid"), True)
    fail_if(l262v_evidence_reviews.get("failure_count") != 0, failures, "cm5_l262v_evidence_reviews_failure_count", l262v_evidence_reviews.get("failure_count"), 0)
    for field, expected in (("valid_receipt_rows", 0), ("review_rows", 0), ("valid_review_rows", 0), ("accepted_for_adjudication_rows", 0), ("unreviewed_valid_receipt_rows", 0), ("ready_for_adjudication_rows", 0)):
        fail_if(l262v_evidence_reviews.get(field) != expected, failures, f"cm5_l262v_evidence_reviews.{field}", l262v_evidence_reviews.get(field), expected)
    for field in ("review_is_adjudication", "discrepancy_resolved", "external_sqlite_mutated", "apply_executed", "export_safe_released", "safe_for_model_claim", "release_ready"):
        fail_if(l262v_evidence_reviews.get(field) is not False, failures, f"cm5_l262v_evidence_reviews.{field}_false", l262v_evidence_reviews.get(field), False)
    fail_if(l262v_evidence_reviews.get("formal_decision_rows_written") != 0, failures, "cm5_l262v_evidence_reviews.formal_decision_rows_written_zero", l262v_evidence_reviews.get("formal_decision_rows_written"), 0)

    l262v_message_drafts = summaries.get("cm5_l262v_external_request_message_drafts_validation", {})
    fail_if(l262v_message_drafts.get("drafts_valid") is not True, failures, "cm5_l262v_message_drafts_valid", l262v_message_drafts.get("drafts_valid"), True)
    fail_if(l262v_message_drafts.get("failure_count") != 0, failures, "cm5_l262v_message_drafts_failure_count", l262v_message_drafts.get("failure_count"), 0)
    for field, expected in (("draft_rows", 4), ("unique_message_sha256_rows", 4), ("message_approved_rows", 0), ("request_sent_rows", 0), ("external_message_sent_rows", 0), ("evidence_received_rows", 0)):
        fail_if(l262v_message_drafts.get(field) != expected, failures, f"cm5_l262v_message_drafts.{field}", l262v_message_drafts.get(field), expected)
    for field in ("discrepancy_resolved", "send_executor_present", "external_sqlite_mutated", "apply_executed", "export_safe_released", "safe_for_model_claim", "release_ready"):
        fail_if(l262v_message_drafts.get(field) is not False, failures, f"cm5_l262v_message_drafts.{field}_false", l262v_message_drafts.get(field), False)
    fail_if(l262v_message_drafts.get("formal_decision_rows_written") != 0, failures, "cm5_l262v_message_drafts.formal_decision_rows_written_zero", l262v_message_drafts.get("formal_decision_rows_written"), 0)

    l262v_request_authorization = summaries.get("cm5_l262v_external_request_authorization_validation", {})
    fail_if(l262v_request_authorization.get("intake_valid") is not True, failures, "cm5_l262v_request_authorization_valid", l262v_request_authorization.get("intake_valid"), True)
    fail_if(l262v_request_authorization.get("failure_count") != 0, failures, "cm5_l262v_request_authorization_failure_count", l262v_request_authorization.get("failure_count"), 0)
    fail_if(l262v_request_authorization.get("message_draft_validation_valid") is not True, failures, "cm5_l262v_request_authorization.message_draft_validation_valid", l262v_request_authorization.get("message_draft_validation_valid"), True)
    for field, expected in (("request_rows", 4), ("message_draft_rows", 4), ("message_draft_request_rows", 4), ("authorization_rows", 0), ("valid_authorization_rows", 0), ("authorized_send_rows", 0), ("message_sha_bound_authorization_rows", 0), ("do_not_send_rows", 0), ("needs_more_info_rows", 0), ("send_ready_candidate_rows", 0), ("request_sent_rows", 0), ("evidence_received_rows", 0)):
        fail_if(l262v_request_authorization.get(field) != expected, failures, f"cm5_l262v_request_authorization.{field}", l262v_request_authorization.get(field), expected)
    for field in ("external_message_sent", "send_executor_present", "discrepancy_resolved", "external_sqlite_mutated", "apply_executed", "export_safe_released", "safe_for_model_claim", "release_ready"):
        fail_if(l262v_request_authorization.get(field) is not False, failures, f"cm5_l262v_request_authorization.{field}_false", l262v_request_authorization.get(field), False)
    fail_if(l262v_request_authorization.get("formal_decision_rows_written") != 0, failures, "cm5_l262v_request_authorization.formal_decision_rows_written_zero", l262v_request_authorization.get("formal_decision_rows_written"), 0)

    l262v_send_guard = summaries.get("cm5_l262v_external_request_send_guard_validation", {})
    fail_if(l262v_send_guard.get("guard_valid") is not True, failures, "cm5_l262v_send_guard_valid", l262v_send_guard.get("guard_valid"), True)
    fail_if(l262v_send_guard.get("failure_count") != 0, failures, "cm5_l262v_send_guard_failure_count", l262v_send_guard.get("failure_count"), 0)
    for field, expected in (("request_rows", 4), ("authorization_rows", 0), ("authorized_send_rows", 0)):
        fail_if(l262v_send_guard.get(field) != expected, failures, f"cm5_l262v_send_guard.{field}", l262v_send_guard.get(field), expected)
    fail_if(l262v_send_guard.get("execution_status") != "blocked_no_authorization_and_no_executor", failures, "cm5_l262v_send_guard.execution_status", l262v_send_guard.get("execution_status"), "blocked_no_authorization_and_no_executor")
    for field in ("send_attempted", "external_message_sent", "send_executor_present", "external_sqlite_mutated", "apply_executed", "export_safe_released", "safe_for_model_claim", "release_ready"):
        fail_if(l262v_send_guard.get(field) is not False, failures, f"cm5_l262v_send_guard.{field}_false", l262v_send_guard.get(field), False)
    fail_if(l262v_send_guard.get("formal_decision_rows_written") != 0, failures, "cm5_l262v_send_guard.formal_decision_rows_written_zero", l262v_send_guard.get("formal_decision_rows_written"), 0)

    l262v_authorization_regression = summaries.get("cm5_l262v_external_request_authorization_safety_regression", {})
    fail_if(l262v_authorization_regression.get("success") is not True, failures, "cm5_l262v_authorization_regression_success", l262v_authorization_regression.get("success"), True)
    for field, expected in (("case_rows", 2), ("passed_rows", 2), ("failed_rows", 0), ("request_sent_rows", 0)):
        fail_if(l262v_authorization_regression.get(field) != expected, failures, f"cm5_l262v_authorization_regression.{field}", l262v_authorization_regression.get(field), expected)
    for field in ("real_authorization_input_mutated", "external_message_sent", "send_executor_present", "external_sqlite_mutated", "apply_executed", "safe_for_model_claim", "release_ready"):
        fail_if(l262v_authorization_regression.get(field) is not False, failures, f"cm5_l262v_authorization_regression.{field}_false", l262v_authorization_regression.get(field), False)

    source_shortlist = summaries.get("source_acquisition_shortlist_validation", {})
    fail_if(source_shortlist.get("shortlist_valid") is not True, failures, "source_acquisition_shortlist_valid", source_shortlist.get("shortlist_valid"), True)
    fail_if(source_shortlist.get("failure_count") != 0, failures, "source_acquisition_shortlist_failure_count", source_shortlist.get("failure_count"), 0)
    fail_if(source_shortlist.get("paper_rows") != 4, failures, "source_acquisition_shortlist_paper_rows", source_shortlist.get("paper_rows"), 4)
    fail_if(source_shortlist.get("unique_pmid_rows") != 4, failures, "source_acquisition_shortlist_unique_pmid_rows", source_shortlist.get("unique_pmid_rows"), 4)
    fail_if(source_shortlist.get("required_file_rows") != 8, failures, "source_acquisition_shortlist_required_file_rows", source_shortlist.get("required_file_rows"), 8)
    fail_if(source_shortlist.get("unique_required_file_path_rows") != 8, failures, "source_acquisition_shortlist_unique_required_file_path_rows", source_shortlist.get("unique_required_file_path_rows"), 8)
    fail_if(source_shortlist.get("markdown_pmid_heading_rows") != 4, failures, "source_acquisition_shortlist_markdown_pmid_heading_rows", source_shortlist.get("markdown_pmid_heading_rows"), 4)
    fail_if(source_shortlist.get("markdown_exact_coverage") is not True, failures, "source_acquisition_shortlist_markdown_exact_coverage", source_shortlist.get("markdown_exact_coverage"), True)
    fail_if(source_shortlist.get("paper_ready_rows") != 0, failures, "source_acquisition_shortlist_paper_ready_rows_zero", source_shortlist.get("paper_ready_rows"), 0)
    fail_if(source_shortlist.get("ready_for_sqlite_apply_rows") != 0, failures, "source_acquisition_shortlist_ready_for_sqlite_apply_rows_zero", source_shortlist.get("ready_for_sqlite_apply_rows"), 0)
    for flag in ("external_sqlite_mutated", "apply_executed", "export_safe_released", "safe_for_model_claim", "release_ready"):
        fail_if(source_shortlist.get(flag) is not False, failures, f"source_acquisition_shortlist.{flag}_false", source_shortlist.get(flag), False)
    fail_if(source_shortlist.get("formal_decision_rows_written") != 0, failures, "source_acquisition_shortlist_formal_decision_rows_written_zero", source_shortlist.get("formal_decision_rows_written"), 0)

    literature_search = summaries.get("literature_web_search_receipt_validation", {})
    fail_if(literature_search.get("receipt_valid") is not True, failures, "literature_web_search_receipt_valid", literature_search.get("receipt_valid"), True)
    fail_if(literature_search.get("failure_count") != 0, failures, "literature_web_search_failure_count", literature_search.get("failure_count"), 0)
    fail_if(literature_search.get("paper_rows") != 4, failures, "literature_web_search_paper_rows", literature_search.get("paper_rows"), 4)
    fail_if(literature_search.get("source_table_locators_verified") != 0, failures, "literature_web_search_source_locators_zero", literature_search.get("source_table_locators_verified"), 0)
    fail_if(literature_search.get("ready_for_sqlite_apply_rows") != 0, failures, "literature_web_search_ready_for_sqlite_apply_rows_zero", literature_search.get("ready_for_sqlite_apply_rows"), 0)
    fail_if(literature_search.get("formal_decision_rows_written") != 0, failures, "literature_web_search_formal_decision_rows_written_zero", literature_search.get("formal_decision_rows_written"), 0)
    for flag in ("external_sqlite_mutated", "apply_executed", "export_safe_released", "safe_for_model_claim", "release_ready"):
        fail_if(literature_search.get(flag) is not False, failures, f"literature_web_search.{flag}_false", literature_search.get(flag), False)

    source_drop_extraction = summaries.get("source_drop_extraction_readiness_candidate_validation", {})
    fail_if(source_drop_extraction.get("candidates_valid") is not True, failures, "source_drop_extraction_candidates_valid", source_drop_extraction.get("candidates_valid"), True)
    fail_if(source_drop_extraction.get("failure_count") != 0, failures, "source_drop_extraction_failure_count", source_drop_extraction.get("failure_count"), 0)
    fail_if(source_drop_extraction.get("candidate_rows") != 4, failures, "source_drop_extraction_candidate_rows", source_drop_extraction.get("candidate_rows"), 4)
    fail_if(source_drop_extraction.get("ready_for_reviewed_extraction_rows") != 0, failures, "source_drop_extraction_ready_rows_zero", source_drop_extraction.get("ready_for_reviewed_extraction_rows"), 0)
    fail_if(source_drop_extraction.get("ready_for_sqlite_apply_rows") != 0, failures, "source_drop_extraction_ready_for_sqlite_apply_rows_zero", source_drop_extraction.get("ready_for_sqlite_apply_rows"), 0)
    fail_if(source_drop_extraction.get("external_sqlite_mutated") is not False, failures, "source_drop_extraction_external_sqlite_mutated_false", source_drop_extraction.get("external_sqlite_mutated"), False)

    importer_design = summaries.get("family_apply_importer_design_validation", {})
    fail_if(importer_design.get("design_valid") is not True, failures, "family_apply_importer_design_valid", importer_design.get("design_valid"), True)
    fail_if(importer_design.get("failure_count") != 0, failures, "family_apply_importer_design_failure_count", importer_design.get("failure_count"), 0)
    fail_if(importer_design.get("design_rows") != 2, failures, "family_apply_importer_design_rows", importer_design.get("design_rows"), 2)
    fail_if(importer_design.get("external_sqlite_mutated") is not False, failures, "family_apply_importer_external_sqlite_mutated_false", importer_design.get("external_sqlite_mutated"), False)
    fail_if(importer_design.get("export_safe_released") is not False, failures, "family_apply_importer_export_safe_released_false", importer_design.get("export_safe_released"), False)
    fail_if(importer_design.get("safe_for_model_claim") is not False, failures, "family_apply_importer_safe_for_model_claim_false", importer_design.get("safe_for_model_claim"), False)
    fail_if(importer_design.get("formal_decision_rows_written") != 0, failures, "family_apply_importer_formal_decision_rows_written_zero", importer_design.get("formal_decision_rows_written"), 0)

    transaction_plan = summaries.get("family_apply_transaction_plan_validation", {})
    fail_if(transaction_plan.get("plans_valid") is not True, failures, "family_apply_transaction_plans_valid", transaction_plan.get("plans_valid"), True)
    fail_if(transaction_plan.get("failure_count") != 0, failures, "family_apply_transaction_plan_failure_count", transaction_plan.get("failure_count"), 0)
    fail_if(transaction_plan.get("plan_rows") != 2, failures, "family_apply_transaction_plan_rows", transaction_plan.get("plan_rows"), 2)
    fail_if(transaction_plan.get("ready_to_apply_rows") != 0, failures, "family_apply_transaction_ready_to_apply_rows_zero", transaction_plan.get("ready_to_apply_rows"), 0)
    fail_if(transaction_plan.get("write_operation_count") != 0, failures, "family_apply_transaction_write_operation_count_zero", transaction_plan.get("write_operation_count"), 0)
    fail_if(transaction_plan.get("external_sqlite_mutated") is not False, failures, "family_apply_transaction_external_sqlite_mutated_false", transaction_plan.get("external_sqlite_mutated"), False)

    foldx_provision = summaries.get("foldx_provision_manifest_validation", {})
    fail_if(foldx_provision.get("manifest_valid") is not True, failures, "foldx_provision_manifest_valid", foldx_provision.get("manifest_valid"), True)
    fail_if(foldx_provision.get("failure_count") != 0, failures, "foldx_provision_failure_count", foldx_provision.get("failure_count"), 0)
    fail_if(foldx_provision.get("provision_rows") != 6, failures, "foldx_provision_rows", foldx_provision.get("provision_rows"), 6)
    fail_if(foldx_provision.get("formal_runtime_receipt_written") is not False, failures, "foldx_formal_runtime_receipt_written_false", foldx_provision.get("formal_runtime_receipt_written"), False)
    fail_if(foldx_provision.get("approved_for_physical_ddg_runtime") is not False, failures, "foldx_approved_for_physical_ddg_runtime_false", foldx_provision.get("approved_for_physical_ddg_runtime"), False)
    fail_if(foldx_provision.get("safe_for_model_claim") is not False, failures, "foldx_provision_safe_for_model_claim_false", foldx_provision.get("safe_for_model_claim"), False)

    foldx_provision_candidate = summaries.get("foldx_provision_manifest_candidate_validation", {})
    fail_if(foldx_provision_candidate.get("candidate_valid") is not True, failures, "foldx_provision_candidate_valid", foldx_provision_candidate.get("candidate_valid"), True)
    fail_if(foldx_provision_candidate.get("failure_count") != 0, failures, "foldx_provision_candidate_failure_count", foldx_provision_candidate.get("failure_count"), 0)
    fail_if(foldx_provision_candidate.get("candidate_rows") != 6, failures, "foldx_provision_candidate_rows", foldx_provision_candidate.get("candidate_rows"), 6)
    fail_if(foldx_provision_candidate.get("executable_present") is not True, failures, "foldx_provision_candidate_executable_present", foldx_provision_candidate.get("executable_present"), True)
    fail_if(foldx_provision_candidate.get("present_rows") != 1, failures, "foldx_provision_candidate_present_rows", foldx_provision_candidate.get("present_rows"), 1)
    fail_if(foldx_provision_candidate.get("missing_rows") != 5, failures, "foldx_provision_candidate_missing_rows", foldx_provision_candidate.get("missing_rows"), 5)
    fail_if(foldx_provision_candidate.get("technical_smoke_validation_success") is not True, failures, "foldx_provision_candidate_technical_smoke_valid", foldx_provision_candidate.get("technical_smoke_validation_success"), True)
    fail_if(foldx_provision_candidate.get("technical_smoke_only") is not True, failures, "foldx_provision_candidate_technical_smoke_only", foldx_provision_candidate.get("technical_smoke_only"), True)
    fail_if(foldx_provision_candidate.get("technical_smoke_artifact_count") != 5, failures, "foldx_provision_candidate_technical_artifact_count", foldx_provision_candidate.get("technical_smoke_artifact_count"), 5)
    fail_if(foldx_provision_candidate.get("technical_formal_path_overlap_rows") != 0, failures, "foldx_provision_candidate_path_overlap_zero", foldx_provision_candidate.get("technical_formal_path_overlap_rows"), 0)
    fail_if(foldx_provision_candidate.get("technical_evidence_substitutes_formal_provision") is not False, failures, "foldx_provision_candidate_technical_substitution_false", foldx_provision_candidate.get("technical_evidence_substitutes_formal_provision"), False)
    fail_if(foldx_provision_candidate.get("technical_smoke_evidence_present") is not True, failures, "foldx_provision_candidate_technical_smoke_evidence_present", foldx_provision_candidate.get("technical_smoke_evidence_present"), True)
    fail_if(foldx_provision_candidate.get("technical_smoke_artifact_rows") != 5, failures, "foldx_provision_candidate_technical_smoke_artifact_rows", foldx_provision_candidate.get("technical_smoke_artifact_rows"), 5)
    fail_if(foldx_provision_candidate.get("technical_smoke_checksum_verified_rows") != 5, failures, "foldx_provision_candidate_technical_smoke_checksum_rows", foldx_provision_candidate.get("technical_smoke_checksum_verified_rows"), 5)
    fail_if(foldx_provision_candidate.get("technical_smoke_substitution_allowed") is not False, failures, "foldx_provision_candidate_technical_smoke_substitution_false", foldx_provision_candidate.get("technical_smoke_substitution_allowed"), False)
    fail_if(foldx_provision_candidate.get("formal_smoke_artifact_present_rows") != 0, failures, "foldx_provision_candidate_formal_smoke_present_rows_zero", foldx_provision_candidate.get("formal_smoke_artifact_present_rows"), 0)
    fail_if(foldx_provision_candidate.get("formal_smoke_artifact_missing_rows") != 5, failures, "foldx_provision_candidate_formal_smoke_missing_rows", foldx_provision_candidate.get("formal_smoke_artifact_missing_rows"), 5)
    fail_if(foldx_provision_candidate.get("ready_for_runtime_receipt_rows") != 0, failures, "foldx_provision_candidate_ready_rows_zero", foldx_provision_candidate.get("ready_for_runtime_receipt_rows"), 0)
    fail_if(foldx_provision_candidate.get("formal_runtime_receipt_written") is not False, failures, "foldx_provision_candidate_formal_written_false", foldx_provision_candidate.get("formal_runtime_receipt_written"), False)

    foldx_receipt_draft = summaries.get("foldx_runtime_receipt_candidate_draft_validation", {})
    fail_if(foldx_receipt_draft.get("drafts_valid") is not True, failures, "foldx_runtime_receipt_candidate_drafts_valid", foldx_receipt_draft.get("drafts_valid"), True)
    fail_if(foldx_receipt_draft.get("failure_count") != 0, failures, "foldx_runtime_receipt_candidate_failure_count", foldx_receipt_draft.get("failure_count"), 0)
    fail_if(foldx_receipt_draft.get("receipt_decision") != "needs_more_info", failures, "foldx_runtime_receipt_candidate_decision", foldx_receipt_draft.get("receipt_decision"), "needs_more_info")
    fail_if(foldx_receipt_draft.get("formal_runtime_receipt_written") is not False, failures, "foldx_runtime_receipt_candidate_formal_written_false", foldx_receipt_draft.get("formal_runtime_receipt_written"), False)
    fail_if(foldx_receipt_draft.get("approved_for_physical_ddg_runtime") is not False, failures, "foldx_runtime_receipt_candidate_approved_false", foldx_receipt_draft.get("approved_for_physical_ddg_runtime"), False)

    foldx_technical_smoke = summaries.get("foldx_technical_smoke_validation", {})
    fail_if(foldx_technical_smoke.get("success") is not True, failures, "foldx_technical_smoke_validation_success", foldx_technical_smoke.get("success"), True)
    fail_if(foldx_technical_smoke.get("technical_smoke_only") is not True, failures, "foldx_technical_smoke_only", foldx_technical_smoke.get("technical_smoke_only"), True)
    fail_if(foldx_technical_smoke.get("technical_smoke_passed") is not True, failures, "foldx_technical_smoke_passed", foldx_technical_smoke.get("technical_smoke_passed"), True)
    fail_if(foldx_technical_smoke.get("parsed_rows") != 1, failures, "foldx_technical_smoke_parsed_rows", foldx_technical_smoke.get("parsed_rows"), 1)
    fail_if(foldx_technical_smoke.get("artifact_count") != 5, failures, "foldx_technical_smoke_artifact_count", foldx_technical_smoke.get("artifact_count"), 5)
    fail_if(foldx_technical_smoke.get("failures") != [], failures, "foldx_technical_smoke_failures_empty", foldx_technical_smoke.get("failures"), [])
    fail_if(foldx_technical_smoke.get("parameterization_dependency_warning_detected") is not True, failures, "foldx_technical_smoke_parameterization_warning_detected", foldx_technical_smoke.get("parameterization_dependency_warning_detected"), True)
    fail_if(foldx_technical_smoke.get("parameterization_warning_commands") != ["RepairPDB", "BuildModel"], failures, "foldx_technical_smoke_parameterization_warning_commands", foldx_technical_smoke.get("parameterization_warning_commands"), ["RepairPDB", "BuildModel"])
    fail_if(foldx_technical_smoke.get("parameterization_warning_command_count") != 2, failures, "foldx_technical_smoke_parameterization_warning_command_count", foldx_technical_smoke.get("parameterization_warning_command_count"), 2)
    fail_if(foldx_technical_smoke.get("unrecognized_molecule_diagnostic_present") is not True, failures, "foldx_technical_smoke_unrecognized_diagnostic_present", foldx_technical_smoke.get("unrecognized_molecule_diagnostic_present"), True)
    fail_if(foldx_technical_smoke.get("unrecognized_atom_rows") != 110, failures, "foldx_technical_smoke_unrecognized_atom_rows", foldx_technical_smoke.get("unrecognized_atom_rows"), 110)
    fail_if(foldx_technical_smoke.get("unrecognized_molecule_names") != ["5CM", "5NC", "SAH"], failures, "foldx_technical_smoke_unrecognized_molecule_names", foldx_technical_smoke.get("unrecognized_molecule_names"), ["5CM", "5NC", "SAH"])
    fail_if(foldx_technical_smoke.get("parameterization_review_completed") is not False, failures, "foldx_technical_smoke_parameterization_review_false", foldx_technical_smoke.get("parameterization_review_completed"), False)
    fail_if(foldx_technical_smoke.get("ddg_value_technical_only") is not True, failures, "foldx_technical_smoke_ddg_value_technical_only", foldx_technical_smoke.get("ddg_value_technical_only"), True)
    for field in ("energetic_interpretation_approved", "physical_ddg_comparable", "safe_for_benchmark_intake"):
        fail_if(foldx_technical_smoke.get(field) is not False, failures, f"foldx_technical_smoke.{field}_false", foldx_technical_smoke.get(field), False)
    for field in ("formal_runtime_receipt_written", "approved_for_physical_ddg_runtime", "safe_for_training_import", "external_sqlite_mutated", "apply_executed", "export_safe_released", "safe_for_model_claim", "release_ready"):
        fail_if(foldx_technical_smoke.get(field) is not False, failures, f"foldx_technical_smoke.{field}_false", foldx_technical_smoke.get(field), False)
    fail_if(foldx_technical_smoke.get("formal_decision_rows_written") != 0, failures, "foldx_technical_smoke_formal_decision_rows_written_zero", foldx_technical_smoke.get("formal_decision_rows_written"), 0)

    foldx_bridge_isolation = summaries.get("foldx_benchmark_bridge_isolation_validation", {})
    fail_if(foldx_bridge_isolation.get("isolation_valid") is not True, failures, "foldx_benchmark_bridge_isolation_valid", foldx_bridge_isolation.get("isolation_valid"), True)
    fail_if(foldx_bridge_isolation.get("failure_count") != 0, failures, "foldx_benchmark_bridge_isolation_failure_count", foldx_bridge_isolation.get("failure_count"), 0)
    fail_if(foldx_bridge_isolation.get("bridge_intake_rows_written") != 0, failures, "foldx_bridge_intake_rows_written_zero", foldx_bridge_isolation.get("bridge_intake_rows_written"), 0)
    fail_if(foldx_bridge_isolation.get("benchmark_completion_ready_rows") != 0, failures, "foldx_bridge_benchmark_completion_ready_rows_zero", foldx_bridge_isolation.get("benchmark_completion_ready_rows"), 0)

    foldx_execution_plan = summaries.get("foldx_execution_plan_blocker_validation", {})
    fail_if(foldx_execution_plan.get("receipt_valid") is not True, failures, "foldx_execution_plan_blocker_valid", foldx_execution_plan.get("receipt_valid"), True)
    fail_if(foldx_execution_plan.get("failure_count") != 0, failures, "foldx_execution_plan_blocker_failure_count", foldx_execution_plan.get("failure_count"), 0)
    fail_if(foldx_execution_plan.get("plan_rows") != 25, failures, "foldx_execution_plan_rows", foldx_execution_plan.get("plan_rows"), 25)
    fail_if(foldx_execution_plan.get("ready_rows") != 0, failures, "foldx_execution_plan_ready_rows_zero", foldx_execution_plan.get("ready_rows"), 0)
    fail_if(foldx_execution_plan.get("blocked_rows") != 25, failures, "foldx_execution_plan_blocked_rows", foldx_execution_plan.get("blocked_rows"), 25)
    fail_if(foldx_execution_plan.get("receipt_decision") != "blocked_execution_plan_no_ready_rows", failures, "foldx_execution_plan_decision", foldx_execution_plan.get("receipt_decision"), "blocked_execution_plan_no_ready_rows")
    fail_if(foldx_execution_plan.get("foldx_ready_for_execution") is not False, failures, "foldx_execution_plan_ready_for_execution_false", foldx_execution_plan.get("foldx_ready_for_execution"), False)
    fail_if(foldx_execution_plan.get("foldx_data_ready") is not False, failures, "foldx_execution_plan_data_ready_false", foldx_execution_plan.get("foldx_data_ready"), False)
    fail_if(foldx_execution_plan.get("foldx_buildmodel_technical_smoke_executed") is not True, failures, "foldx_execution_plan_technical_smoke_executed", foldx_execution_plan.get("foldx_buildmodel_technical_smoke_executed"), True)
    fail_if(foldx_execution_plan.get("foldx_technical_smoke_only") is not True, failures, "foldx_execution_plan_technical_smoke_only", foldx_execution_plan.get("foldx_technical_smoke_only"), True)
    fail_if(foldx_execution_plan.get("foldx_technical_smoke_artifact_count") != 5, failures, "foldx_execution_plan_technical_smoke_artifact_count", foldx_execution_plan.get("foldx_technical_smoke_artifact_count"), 5)
    fail_if(foldx_execution_plan.get("foldx_technical_smoke_satisfies_formal_provision") is not False, failures, "foldx_execution_plan_technical_smoke_formal_substitution_false", foldx_execution_plan.get("foldx_technical_smoke_satisfies_formal_provision"), False)
    for field in ("formal_runtime_receipt_written", "approved_for_physical_ddg_runtime", "foldx_buildmodel_physical_smoke_executed", "external_sqlite_mutated", "apply_executed", "export_safe_released", "safe_for_model_claim", "release_ready"):
        fail_if(foldx_execution_plan.get(field) is not False, failures, f"foldx_execution_plan.{field}_false", foldx_execution_plan.get(field), False)
    fail_if(foldx_execution_plan.get("bridge_intake_rows_written") != 0, failures, "foldx_execution_plan_bridge_intake_rows_written_zero", foldx_execution_plan.get("bridge_intake_rows_written"), 0)

    benchmark_unblock = summaries.get("benchmark_unblock_design_validation", {})
    fail_if(benchmark_unblock.get("design_valid") is not True, failures, "benchmark_unblock_design_valid", benchmark_unblock.get("design_valid"), True)
    fail_if(benchmark_unblock.get("failure_count") != 0, failures, "benchmark_unblock_failure_count", benchmark_unblock.get("failure_count"), 0)
    fail_if(benchmark_unblock.get("design_rows") != 2, failures, "benchmark_unblock_design_rows", benchmark_unblock.get("design_rows"), 2)
    fail_if(benchmark_unblock.get("completion_ready_rows") != 0, failures, "benchmark_unblock_completion_ready_rows_zero", benchmark_unblock.get("completion_ready_rows"), 0)
    fail_if(benchmark_unblock.get("formal_decision_rows_written") != 0, failures, "benchmark_unblock_formal_decision_rows_written_zero", benchmark_unblock.get("formal_decision_rows_written"), 0)
    fail_if(benchmark_unblock.get("safe_for_model_claim") is not False, failures, "benchmark_unblock_safe_for_model_claim_false", benchmark_unblock.get("safe_for_model_claim"), False)

    hard_gate_drafts = summaries.get("hard_gate_formal_decision_draft_package_validation", {})
    fail_if(hard_gate_drafts.get("draft_package_valid") is not True, failures, "hard_gate_formal_decision_draft_package_valid", hard_gate_drafts.get("draft_package_valid"), True)
    fail_if(hard_gate_drafts.get("failure_count") != 0, failures, "hard_gate_formal_decision_draft_package_failure_count", hard_gate_drafts.get("failure_count"), 0)
    fail_if(hard_gate_drafts.get("strict_draft_rows") != 3, failures, "hard_gate_strict_draft_rows", hard_gate_drafts.get("strict_draft_rows"), 3)
    fail_if(hard_gate_drafts.get("substrate_draft_rows") != 9, failures, "hard_gate_substrate_draft_rows", hard_gate_drafts.get("substrate_draft_rows"), 9)
    fail_if(hard_gate_drafts.get("formal_decision_rows_written") != 0, failures, "hard_gate_formal_decision_rows_written_zero", hard_gate_drafts.get("formal_decision_rows_written"), 0)
    fail_if(hard_gate_drafts.get("bridge_intake_rows_written") != 0, failures, "hard_gate_bridge_intake_rows_written_zero", hard_gate_drafts.get("bridge_intake_rows_written"), 0)

    extraction_templates = summaries.get("new_paper_extraction_template_validation", {})
    fail_if(extraction_templates.get("templates_valid") is not True, failures, "new_paper_extraction_templates_valid", extraction_templates.get("templates_valid"), True)
    fail_if(extraction_templates.get("failure_count") != 0, failures, "new_paper_extraction_templates_failure_count", extraction_templates.get("failure_count"), 0)
    fail_if(extraction_templates.get("template_rows") != 4, failures, "new_paper_extraction_template_rows", extraction_templates.get("template_rows"), 4)
    fail_if(extraction_templates.get("ready_for_sqlite_apply_rows") != 0, failures, "new_paper_extraction_ready_for_sqlite_apply_rows_zero", extraction_templates.get("ready_for_sqlite_apply_rows"), 0)
    fail_if(extraction_templates.get("external_sqlite_mutated") is not False, failures, "new_paper_extraction_external_sqlite_mutated_false", extraction_templates.get("external_sqlite_mutated"), False)
    fail_if(extraction_templates.get("safe_for_model_claim") is not False, failures, "new_paper_extraction_safe_for_model_claim_false", extraction_templates.get("safe_for_model_claim"), False)

    extraction_drafts = summaries.get("reviewed_extraction_output_draft_validation", {})
    fail_if(extraction_drafts.get("drafts_valid") is not True, failures, "reviewed_extraction_output_drafts_valid", extraction_drafts.get("drafts_valid"), True)
    fail_if(extraction_drafts.get("failure_count") != 0, failures, "reviewed_extraction_output_drafts_failure_count", extraction_drafts.get("failure_count"), 0)
    fail_if(extraction_drafts.get("draft_rows") != 4, failures, "reviewed_extraction_output_draft_rows", extraction_drafts.get("draft_rows"), 4)
    fail_if(extraction_drafts.get("reviewed_extraction_completed_rows") != 0, failures, "reviewed_extraction_completed_rows_zero", extraction_drafts.get("reviewed_extraction_completed_rows"), 0)
    fail_if(extraction_drafts.get("ready_for_sqlite_apply_rows") != 0, failures, "reviewed_extraction_ready_for_sqlite_apply_rows_zero", extraction_drafts.get("ready_for_sqlite_apply_rows"), 0)
    fail_if(extraction_drafts.get("external_sqlite_mutated") is not False, failures, "reviewed_extraction_external_sqlite_mutated_false", extraction_drafts.get("external_sqlite_mutated"), False)
    fail_if(extraction_drafts.get("formal_decision_rows_written") != 0, failures, "reviewed_extraction_formal_decision_rows_written_zero", extraction_drafts.get("formal_decision_rows_written"), 0)
    fail_if(extraction_drafts.get("safe_for_model_claim") is not False, failures, "reviewed_extraction_safe_for_model_claim_false", extraction_drafts.get("safe_for_model_claim"), False)

    claim_release = summaries.get("claim_release_consistency_validation", {})
    fail_if(claim_release.get("claim_release_consistent") is not True, failures, "claim_release_consistency_valid", claim_release.get("claim_release_consistent"), True)
    fail_if(claim_release.get("failure_count") != 0, failures, "claim_release_consistency_failure_count", claim_release.get("failure_count"), 0)
    for field in ("safe_for_model_claim", "release_ready", "customer_delivery_ready", "approved_for_ordering", "export_safe_released", "external_sqlite_mutated"):
        fail_if(claim_release.get(field) is not False, failures, f"claim_release.{field}_false", claim_release.get(field), False)

    blocker_matrix = summaries.get("remaining_blocker_closure_matrix_validation", {})
    fail_if(blocker_matrix.get("matrix_valid") is not True, failures, "remaining_blocker_matrix_valid", blocker_matrix.get("matrix_valid"), True)
    fail_if(blocker_matrix.get("failure_count") != 0, failures, "remaining_blocker_matrix_failure_count", blocker_matrix.get("failure_count"), 0)
    fail_if(blocker_matrix.get("blocker_rows") != 5, failures, "remaining_blocker_rows", blocker_matrix.get("blocker_rows"), 5)
    fail_if(blocker_matrix.get("completion_ready_rows") != 0, failures, "remaining_blocker_completion_ready_rows_zero", blocker_matrix.get("completion_ready_rows"), 0)

    post_source_drop = summaries.get("post_source_drop_rerun_receipt_validation", {})
    fail_if(post_source_drop.get("receipt_valid") is not True, failures, "post_source_drop_rerun_receipt_valid", post_source_drop.get("receipt_valid"), True)
    fail_if(post_source_drop.get("failure_count") != 0, failures, "post_source_drop_rerun_receipt_failure_count", post_source_drop.get("failure_count"), 0)
    post_source_command_rows = post_source_drop.get("command_rows")
    fail_if(not isinstance(post_source_command_rows, int) or isinstance(post_source_command_rows, bool) or post_source_command_rows <= 0, failures, "post_source_drop_rerun_command_rows_positive", post_source_command_rows, ">0 integer")
    fail_if(post_source_drop.get("unique_command_name_rows") != post_source_command_rows, failures, "post_source_drop_rerun_unique_command_name_rows", post_source_drop.get("unique_command_name_rows"), post_source_command_rows)
    fail_if(post_source_drop.get("duplicate_command_names") != [], failures, "post_source_drop_rerun_duplicate_command_names_empty", post_source_drop.get("duplicate_command_names"), [])
    fail_if(post_source_drop.get("command_names_exact") is not True, failures, "post_source_drop_rerun_command_names_exact", post_source_drop.get("command_names_exact"), True)
    fail_if(post_source_drop.get("command_contract_valid") is not True, failures, "post_source_drop_rerun_command_contract_valid", post_source_drop.get("command_contract_valid"), True)
    fail_if(post_source_drop.get("sqlite_write_command_rows") != 0, failures, "post_source_drop_rerun_sqlite_write_command_rows_zero", post_source_drop.get("sqlite_write_command_rows"), 0)
    post_source_regression = summaries.get("post_source_drop_rerun_receipt_regression", {})
    fail_if(post_source_regression.get("failure_count") != 0, failures, "post_source_drop_rerun_receipt_regression_failure_count", post_source_regression.get("failure_count"), 0)
    fail_if(post_source_regression.get("isolated_fixture") is not True, failures, "post_source_drop_rerun_receipt_regression_isolated_fixture", post_source_regression.get("isolated_fixture"), True)
    fail_if(post_source_regression.get("real_inputs_mutated") is not False, failures, "post_source_drop_rerun_receipt_regression_real_inputs_unchanged", post_source_regression.get("real_inputs_mutated"), False)
    fail_if(post_source_regression.get("passed_case_count") != post_source_regression.get("case_count"), failures, "post_source_drop_rerun_receipt_regression_all_cases_pass", {"passed": post_source_regression.get("passed_case_count"), "cases": post_source_regression.get("case_count")}, "equal")
    post_source_current = summaries.get("post_source_drop_rerun_validation_current", {})
    fail_if(post_source_current.get("success") is not True, failures, "post_source_drop_rerun_validation_current_success", post_source_current.get("success"), True)
    fail_if(post_source_current.get("failure_count") != 0, failures, "post_source_drop_rerun_validation_current_failure_count", post_source_current.get("failure_count"), 0)
    post_source_current_regression = summaries.get("post_source_drop_rerun_validation_current_regression", {})
    fail_if(post_source_current_regression.get("success") is not True, failures, "post_source_drop_rerun_validation_current_regression_success", post_source_current_regression.get("success"), True)
    fail_if(post_source_current_regression.get("failed_case_count") != 0, failures, "post_source_drop_rerun_validation_current_regression_failed_cases", post_source_current_regression.get("failed_case_count"), 0)
    fail_if(post_source_current_regression.get("passed_case_count") != post_source_current_regression.get("case_count"), failures, "post_source_drop_rerun_validation_current_regression_all_cases_pass", {"passed": post_source_current_regression.get("passed_case_count"), "cases": post_source_current_regression.get("case_count")}, "equal")
    fail_if(post_source_current_regression.get("real_inputs_mutated") is not False, failures, "post_source_drop_rerun_validation_current_regression_real_inputs_unchanged", post_source_current_regression.get("real_inputs_mutated"), False)
    post_source_policy = summaries.get("post_source_drop_rerun_independent_policy", {})
    fail_if(post_source_policy.get("success") is not True, failures, "post_source_drop_rerun_independent_policy_success", post_source_policy.get("success"), True)
    fail_if(post_source_policy.get("failure_count") != 0, failures, "post_source_drop_rerun_independent_policy_failure_count", post_source_policy.get("failure_count"), 0)
    post_source_policy_regression = summaries.get("post_source_drop_rerun_independent_policy_regression", {})
    fail_if(post_source_policy_regression.get("success") is not True, failures, "post_source_drop_rerun_independent_policy_regression_success", post_source_policy_regression.get("success"), True)
    fail_if(post_source_policy_regression.get("failed_case_count") != 0, failures, "post_source_drop_rerun_independent_policy_regression_failed_cases", post_source_policy_regression.get("failed_case_count"), 0)
    fail_if(post_source_policy_regression.get("passed_case_count") != post_source_policy_regression.get("case_count"), failures, "post_source_drop_rerun_independent_policy_regression_all_cases_pass", {"passed": post_source_policy_regression.get("passed_case_count"), "cases": post_source_policy_regression.get("case_count")}, "equal")
    post_source_policy_current = summaries.get("post_source_drop_rerun_independent_policy_current", {})
    fail_if(post_source_policy_current.get("success") is not True, failures, "post_source_drop_rerun_independent_policy_current_success", post_source_policy_current.get("success"), True)
    fail_if(post_source_policy_current.get("failure_count") != 0, failures, "post_source_drop_rerun_independent_policy_current_failure_count", post_source_policy_current.get("failure_count"), 0)
    post_source_policy_current_regression = summaries.get("post_source_drop_rerun_independent_policy_current_regression", {})
    fail_if(post_source_policy_current_regression.get("success") is not True, failures, "post_source_drop_rerun_independent_policy_current_regression_success", post_source_policy_current_regression.get("success"), True)
    fail_if(post_source_policy_current_regression.get("failed_case_count") != 0, failures, "post_source_drop_rerun_independent_policy_current_regression_failed_cases", post_source_policy_current_regression.get("failed_case_count"), 0)
    fail_if(post_source_policy_current_regression.get("passed_case_count") != post_source_policy_current_regression.get("case_count"), failures, "post_source_drop_rerun_independent_policy_current_regression_all_cases_pass", {"passed": post_source_policy_current_regression.get("passed_case_count"), "cases": post_source_policy_current_regression.get("case_count")}, "equal")
    fail_if(post_source_policy_current_regression.get("isolated_fixture") is not True, failures, "post_source_drop_rerun_independent_policy_current_regression_isolated_fixture", post_source_policy_current_regression.get("isolated_fixture"), True)
    fail_if(post_source_policy_current_regression.get("real_inputs_mutated") is not False, failures, "post_source_drop_rerun_independent_policy_current_regression_real_inputs_unchanged", post_source_policy_current_regression.get("real_inputs_mutated"), False)
    for flag in ("commands_executed", "source_drop_event_receipted", "outputs_freshness_verified", "rerun_completion_receipted"):
        fail_if(post_source_drop.get(flag) is not False, failures, f"post_source_drop_rerun.{flag}_false", post_source_drop.get(flag), False)
    fail_if(post_source_drop.get("commands_executed_rows") != 0, failures, "post_source_drop_rerun_commands_executed_rows_zero", post_source_drop.get("commands_executed_rows"), 0)
    for flag in ("source_evidence_ready", "ready_for_reviewed_extraction", "ready_for_sqlite_apply"):
        fail_if(post_source_drop.get(flag) is not False, failures, f"post_source_drop_rerun.{flag}_false", post_source_drop.get(flag), False)

    rerun_dry_run = summaries.get("post_source_drop_rerun_dry_run_audit_validation", {})
    fail_if(rerun_dry_run.get("audit_valid") is not True, failures, "post_source_drop_rerun_dry_run_audit_valid", rerun_dry_run.get("audit_valid"), True)
    fail_if(rerun_dry_run.get("failure_count") != 0, failures, "post_source_drop_rerun_dry_run_failure_count", rerun_dry_run.get("failure_count"), 0)
    fail_if(rerun_dry_run.get("command_rows") != post_source_command_rows, failures, "post_source_drop_rerun_dry_run_command_rows", rerun_dry_run.get("command_rows"), post_source_command_rows)
    fail_if(rerun_dry_run.get("command_contract_sha256") != post_source_drop.get("command_contract_sha256"), failures, "post_source_drop_rerun_dry_run_sha_parity", rerun_dry_run.get("command_contract_sha256"), post_source_drop.get("command_contract_sha256"))
    fail_if(rerun_dry_run.get("missing_expected_output_rows") != 0, failures, "post_source_drop_rerun_dry_run_missing_expected_outputs_zero", rerun_dry_run.get("missing_expected_output_rows"), 0)
    fail_if(rerun_dry_run.get("sqlite_write_command_rows") != 0, failures, "post_source_drop_rerun_dry_run_sqlite_write_rows_zero", rerun_dry_run.get("sqlite_write_command_rows"), 0)
    fail_if(rerun_dry_run.get("source_receipt_valid") is not True, failures, "post_source_drop_rerun_dry_run_source_receipt_valid", rerun_dry_run.get("source_receipt_valid"), True)
    fail_if(rerun_dry_run.get("command_contract_valid") is not True, failures, "post_source_drop_rerun_dry_run_command_contract_valid", rerun_dry_run.get("command_contract_valid"), True)
    fail_if(rerun_dry_run.get("rerun_recipe_operational") is not True, failures, "post_source_drop_rerun_dry_run_recipe_operational", rerun_dry_run.get("rerun_recipe_operational"), True)
    for flag in ("commands_executed", "source_drop_event_receipted", "outputs_freshness_verified", "rerun_completion_receipted", "ready_for_source_drop_rerun"):
        fail_if(rerun_dry_run.get(flag) is not False, failures, f"post_source_drop_rerun_dry_run.{flag}_false", rerun_dry_run.get(flag), False)
    fail_if(rerun_dry_run.get("commands_executed_rows") != 0, failures, "post_source_drop_rerun_dry_run_commands_executed_rows_zero", rerun_dry_run.get("commands_executed_rows"), 0)
    fail_if(rerun_dry_run.get("commands_not_executed_rows") != post_source_command_rows, failures, "post_source_drop_rerun_dry_run_commands_not_executed_rows", rerun_dry_run.get("commands_not_executed_rows"), post_source_command_rows)
    for flag in ("source_evidence_ready", "ready_for_reviewed_extraction", "ready_for_sqlite_apply"):
        fail_if(rerun_dry_run.get(flag) is not False, failures, f"post_source_drop_rerun_dry_run.{flag}_false", rerun_dry_run.get(flag), False)
    for flag in ("external_sqlite_mutated", "apply_executed", "export_safe_released", "safe_for_model_claim", "release_ready"):
        fail_if(rerun_dry_run.get(flag) is not False, failures, f"post_source_drop_rerun_dry_run.{flag}_false", rerun_dry_run.get(flag), False)
    fail_if(rerun_dry_run.get("formal_decision_rows_written") != 0, failures, "post_source_drop_rerun_dry_run_formal_decision_rows_written_zero", rerun_dry_run.get("formal_decision_rows_written"), 0)

    workstream_acceptance = summaries.get("workstream_acceptance_decision_validation", {})
    fail_if(workstream_acceptance.get("decision_rows") != 1, failures, "workstream_acceptance_decision_rows", workstream_acceptance.get("decision_rows"), 1)
    fail_if(workstream_acceptance.get("valid_rows") != 1, failures, "workstream_acceptance_valid_rows", workstream_acceptance.get("valid_rows"), 1)
    fail_if(workstream_acceptance.get("invalid_rows") != 0, failures, "workstream_acceptance_invalid_rows_zero", workstream_acceptance.get("invalid_rows"), 0)
    fail_if(workstream_acceptance.get("accepted_streams") != 0, failures, "workstream_acceptance_accepted_streams_zero", workstream_acceptance.get("accepted_streams"), 0)
    fail_if(workstream_acceptance.get("all_streams_accepted") is not False, failures, "workstream_acceptance_all_streams_accepted_false", workstream_acceptance.get("all_streams_accepted"), False)
    for field in ("accepted_for_model_claim_streams", "accepted_for_customer_delivery_streams", "accepted_for_experiment_submission_streams"):
        fail_if(workstream_acceptance.get(field) != [], failures, f"workstream_acceptance.{field}_empty", workstream_acceptance.get(field), [])

    activation_map = summaries.get("blocker_activation_map_validation", {})
    fail_if(activation_map.get("activation_map_valid") is not True, failures, "blocker_activation_map_valid", activation_map.get("activation_map_valid"), True)
    fail_if(activation_map.get("failure_count") != 0, failures, "blocker_activation_map_failure_count", activation_map.get("failure_count"), 0)
    fail_if(activation_map.get("activation_rows") != 5, failures, "blocker_activation_map_activation_rows", activation_map.get("activation_rows"), 5)
    fail_if(activation_map.get("activation_completion_ready_rows") != 0, failures, "blocker_activation_map_completion_ready_rows_zero", activation_map.get("activation_completion_ready_rows"), 0)
    fail_if(activation_map.get("all_blockers_mapped") is not True, failures, "blocker_activation_map_all_blockers_mapped", activation_map.get("all_blockers_mapped"), True)

    external_inputs = summaries.get("external_input_readiness_board_validation", {})
    fail_if(external_inputs.get("board_valid") is not True, failures, "external_input_board_valid", external_inputs.get("board_valid"), True)
    fail_if(external_inputs.get("failure_count") != 0, failures, "external_input_board_failure_count", external_inputs.get("failure_count"), 0)
    external_input_rows = external_inputs.get("input_rows")
    fail_if(not isinstance(external_input_rows, int) or isinstance(external_input_rows, bool) or external_input_rows <= 0, failures, "external_input_rows_positive", external_input_rows, ">0 integer")
    fail_if(external_inputs.get("completion_ready_rows") != 0, failures, "external_input_completion_ready_rows_zero", external_inputs.get("completion_ready_rows"), 0)
    fail_if(external_inputs.get("missing_or_needs_more_info_rows") != external_input_rows, failures, "external_input_missing_rows", external_inputs.get("missing_or_needs_more_info_rows"), external_input_rows)
    for flag in ("external_sqlite_mutated", "apply_executed", "export_safe_released", "release_ready", "safe_for_model_claim"):
        fail_if(external_inputs.get(flag) is not False, failures, f"external_input_board.{flag}_false", external_inputs.get(flag), False)
    fail_if(external_inputs.get("formal_decision_rows_written") != 0, failures, "external_input_formal_decision_rows_written_zero", external_inputs.get("formal_decision_rows_written"), 0)

    coverage_audit = summaries.get("latest_blocker_coverage_audit_validation", {})
    fail_if(coverage_audit.get("audit_valid") is not True, failures, "latest_blocker_coverage_audit_valid", coverage_audit.get("audit_valid"), True)
    fail_if(coverage_audit.get("failure_count") != 0, failures, "latest_blocker_coverage_audit_failure_count", coverage_audit.get("failure_count"), 0)
    fail_if(coverage_audit.get("blocker_rows") != 5, failures, "latest_blocker_coverage_audit_blocker_rows", coverage_audit.get("blocker_rows"), 5)
    fail_if(coverage_audit.get("uncovered_blockers") != [], failures, "latest_blocker_coverage_audit_uncovered_empty", coverage_audit.get("uncovered_blockers"), [])
    for field in ("covered_by_current_receipt_rows", "covered_by_overall_index_rows", "covered_by_handoff_manifest_rows", "covered_by_operator_docs_rows", "covered_by_runner_or_rerun_rows"):
        fail_if(coverage_audit.get(field) != 5, failures, f"latest_blocker_coverage_audit_{field}", coverage_audit.get(field), 5)
    for field, expected in (
        ("expected_overall_term_count", 12),
        ("matched_overall_term_count", 12),
        ("missing_overall_term_count", 0),
        ("expected_runner_term_count", 13),
        ("matched_runner_term_count", 13),
        ("missing_runner_term_count", 0),
        ("expected_doc_term_count", 13),
        ("matched_doc_term_count", 13),
        ("missing_doc_term_count", 0),
    ):
        fail_if(coverage_audit.get(field) != expected, failures, f"latest_blocker_coverage_audit_{field}", coverage_audit.get(field), expected)
    for flag in ("external_sqlite_mutated", "apply_executed", "export_safe_released", "release_ready", "safe_for_model_claim"):
        fail_if(coverage_audit.get(flag) is not False, failures, f"latest_blocker_coverage_audit.{flag}_false", coverage_audit.get(flag), False)
    fail_if(coverage_audit.get("formal_decision_rows_written") != 0, failures, "latest_blocker_coverage_audit_formal_decision_rows_written_zero", coverage_audit.get("formal_decision_rows_written"), 0)

    blocker_cross_binding = summaries.get("remaining_blocker_cross_binding_validation", {})
    fail_if(blocker_cross_binding.get("success") is not True, failures, "remaining_blocker_cross_binding_success", blocker_cross_binding.get("success"), True)
    fail_if(blocker_cross_binding.get("failure_count") != 0, failures, "remaining_blocker_cross_binding_failure_count", blocker_cross_binding.get("failure_count"), 0)
    fail_if(blocker_cross_binding.get("shared_blocker_rows") != 5, failures, "remaining_blocker_cross_binding_shared_rows", blocker_cross_binding.get("shared_blocker_rows"), 5)
    fail_if(blocker_cross_binding.get("coverage_complete_rows") != 5, failures, "remaining_blocker_cross_binding_coverage_complete_rows", blocker_cross_binding.get("coverage_complete_rows"), 5)
    fail_if(blocker_cross_binding.get("exact_current_receipt_rows") != 5, failures, "remaining_blocker_cross_binding_exact_current_receipt_rows", blocker_cross_binding.get("exact_current_receipt_rows"), 5)
    fail_if(blocker_cross_binding.get("exact_closure_condition_rows") != 5, failures, "remaining_blocker_cross_binding_exact_closure_condition_rows", blocker_cross_binding.get("exact_closure_condition_rows"), 5)
    fail_if(blocker_cross_binding.get("uncovered_blockers") != [], failures, "remaining_blocker_cross_binding_uncovered_empty", blocker_cross_binding.get("uncovered_blockers"), [])

    blocker_cross_binding_regression = summaries.get("remaining_blocker_cross_binding_regression", {})
    fail_if(blocker_cross_binding_regression.get("success") is not True, failures, "remaining_blocker_cross_binding_regression_success", blocker_cross_binding_regression.get("success"), True)
    fail_if(blocker_cross_binding_regression.get("failed_rows") != 0, failures, "remaining_blocker_cross_binding_regression_failed_rows", blocker_cross_binding_regression.get("failed_rows"), 0)
    fail_if(blocker_cross_binding_regression.get("rejected_negative_cases") != 5, failures, "remaining_blocker_cross_binding_regression_rejected_negative_cases", blocker_cross_binding_regression.get("rejected_negative_cases"), 5)
    fail_if(blocker_cross_binding_regression.get("control_valid") is not True, failures, "remaining_blocker_cross_binding_regression_control_valid", blocker_cross_binding_regression.get("control_valid"), True)
    fail_if(blocker_cross_binding_regression.get("real_inputs_mutated") is not False, failures, "remaining_blocker_cross_binding_regression_real_inputs_mutated_false", blocker_cross_binding_regression.get("real_inputs_mutated"), False)

    handoff = summaries.get("handoff_bundle_manifest_validation", {})
    fail_if(handoff.get("bundle_valid") is not True, failures, "handoff_bundle_manifest_valid", handoff.get("bundle_valid"), True)
    fail_if(handoff.get("failure_count") != 0, failures, "handoff_bundle_manifest_failure_count", handoff.get("failure_count"), 0)
    handoff_bundle_rows = handoff.get("bundle_rows")
    fail_if(not isinstance(handoff_bundle_rows, int) or isinstance(handoff_bundle_rows, bool) or handoff_bundle_rows <= 0, failures, "handoff_bundle_rows_positive", handoff_bundle_rows, ">0 integer")
    fail_if(handoff.get("missing_rows") != 0, failures, "handoff_bundle_missing_rows_zero", handoff.get("missing_rows"), 0)
    fail_if(handoff.get("unique_path_rows") != handoff_bundle_rows, failures, "handoff_unique_path_rows", handoff.get("unique_path_rows"), handoff_bundle_rows)
    fail_if(handoff.get("duplicate_paths") != [], failures, "handoff_duplicate_paths_empty", handoff.get("duplicate_paths"), [])
    handoff_freshness_verified = handoff.get("freshness_verified_rows")
    handoff_freshness_exempt = handoff.get("freshness_exempt_rows")
    freshness_decomposition_valid = (
        isinstance(handoff_freshness_verified, int)
        and not isinstance(handoff_freshness_verified, bool)
        and isinstance(handoff_freshness_exempt, int)
        and not isinstance(handoff_freshness_exempt, bool)
        and handoff_freshness_verified + handoff_freshness_exempt == handoff_bundle_rows
    )
    fail_if(not freshness_decomposition_valid, failures, "handoff_freshness_row_decomposition", {"verified": handoff_freshness_verified, "exempt": handoff_freshness_exempt}, handoff_bundle_rows)
    fail_if(handoff.get("freshness_exempt_rows") != 1, failures, "handoff_freshness_exempt_rows", handoff.get("freshness_exempt_rows"), 1)
    fail_if(handoff.get("freshness_mismatch_rows") != 0, failures, "handoff_freshness_mismatch_rows_zero", handoff.get("freshness_mismatch_rows"), 0)
    fail_if(handoff.get("root_path_mismatch_rows") != 0, failures, "handoff_root_path_mismatch_rows_zero", handoff.get("root_path_mismatch_rows"), 0)
    fail_if(handoff.get("self_referential_rows") != 0, failures, "handoff_self_referential_rows_zero", handoff.get("self_referential_rows"), 0)
    fail_if(handoff.get("filesystem_integrity_valid") is not True, failures, "handoff_filesystem_integrity_valid", handoff.get("filesystem_integrity_valid"), True)

    return {
        "schema_version": 1,
        "created_at": "2026-08-06",
        "mode": "read_only_stage25_overall_fail_closed_index",
        "stage": 25,
        "index_valid": not failures,
        "failure_count": len(failures),
        "failures": failures,
        "summaries": rows,
        "new_paper_summary_valid": new_paper.get("summary_valid") is True,
        "approved_apply_report_valid": approved_apply.get("report_valid") is True,
        "approved_apply_executor_status": approved_apply.get("executor_status"),
        "approved_apply_executor_failure_count": approved_apply.get("executor_failure_count"),
        "execute_blocker_detail_valid": execute_detail.get("detail_valid") is True,
        "paper_metadata_only_plan_valid": metadata_plan.get("plan_valid") is True,
        "paper_metadata_only_ready_for_metadata_review_rows": metadata_plan.get("ready_for_metadata_review_rows"),
        "paper_metadata_only_paper_insert_count": metadata_plan.get("paper_insert_count"),
        "paper_metadata_only_ready_for_sqlite_apply_rows": metadata_plan.get("ready_for_sqlite_apply_rows"),
        "proposal_sets_consistent": proposal_consistency.get("proposal_sets_consistent"),
        "proposal_set_status": proposal_consistency.get("status"),
        "proposal_set_authoritative_candidate_count": proposal_consistency.get("authoritative_candidate_count"),
        "proposal_set_expected_surface_counts": proposal_consistency.get("expected_surface_counts"),
        "proposal_set_disposition_row_count": proposal_consistency.get("disposition_row_count"),
        "proposal_set_allow_apply": proposal_consistency.get("allow_apply"),
        "execute_blocker_executor_failure_count": execute_detail.get("executor_failure_count"),
        "execute_blocker_proposal_rows": execute_detail.get("proposal_blocker_rows"),
        "execute_closeout_checklist_valid": closeout_checklist.get("checklist_valid") is True,
        "execute_closeout_checklist_item_rows": closeout_checklist.get("checklist_item_rows"),
        "execute_closeout_ready_rows": closeout_checklist.get("closeout_ready_rows"),
        "execute_closeout_reviewer_intake_valid": reviewer_intake.get("intake_valid") is True,
        "execute_closeout_reviewer_intake_rows": reviewer_intake.get("intake_rows"),
        "execute_closeout_reviewer_intake_closed_rows": reviewer_intake.get("closed_rows"),
        "execute_closeout_reviewer_packet_valid": reviewer_packet.get("packet_valid") is True,
        "execute_closeout_reviewer_packet_rows": reviewer_packet.get("checklist_rows"),
        "execute_closeout_reviewer_packet_closed_rows": reviewer_packet.get("closed_rows"),
        "local_release_consistency_success": local_release.get("success") is True,
        "local_release_consistency_receipt_atomicity_regression_success": local_release_atomicity_regression.get("success") is True,
        "local_release_consistency_receipt_current_success": local_release_current.get("success") is True,
        "local_release_consistency_receipt_current_regression_success": local_release_current_regression.get("success") is True,
        "local_release_consistency_semantic_policy_success": local_release_semantic_policy.get("success") is True,
        "local_release_consistency_semantic_policy_regression_success": local_release_semantic_policy_regression.get("success") is True,
        "local_release_consistency_semantic_policy_current_success": local_release_semantic_policy_current.get("success") is True,
        "local_release_consistency_semantic_policy_current_regression_success": local_release_semantic_policy_current_regression.get("success") is True,
        "local_release_consistency_semantic_policy_atomicity_regression_success": local_release_semantic_policy_atomicity.get("success") is True,
        "enzyme_agent_release_guard_order_success": release_guard_order.get("success") is True,
        "enzyme_agent_release_guard_order_regression_success": release_guard_order_regression.get("success") is True,
        "enzyme_agent_release_guard_order_current_success": release_guard_order_current.get("success") is True,
        "enzyme_agent_release_guard_order_current_regression_success": release_guard_order_current_regression.get("success") is True,
        "enzyme_agent_release_guard_order_atomicity_regression_success": release_guard_order_atomicity.get("success") is True,
        "enzyme_agent_execution_wave_pair_atomicity_regression_success": wave_pair_atomicity.get("success") is True,
        "enzyme_agent_execution_receipt_proof_current_success": receipt_proof_current.get("success") is True,
        "enzyme_agent_execution_receipt_proof_current_regression_success": receipt_proof_current_regression.get("success") is True,
        "claim_matrix_policy_current_success": claim_policy_current.get("success") is True,
        "claim_matrix_policy_current_regression_success": claim_policy_current_regression.get("success") is True,
        "claim_policy_anchor_success": claim_policy_anchor.get("success") is True,
        "claim_policy_anchor_regression_success": claim_policy_anchor_regression.get("success") is True,
        "claim_promotion_validation_success": claim_promotion.get("success") is True,
        "local_release_safety_guard_links_atomicity_regression_success": safety_guard_atomicity.get("success") is True,
        "local_release_safety_guard_links_current_success": safety_guard_current.get("success") is True,
        "local_release_safety_guard_links_current_regression_success": safety_guard_current_regression.get("success") is True,
        "local_release_safety_guard_links_current_regression_atomicity_success": safety_guard_current_regression_atomicity.get("success") is True,
        "local_release_artifact_count": local_release.get("artifact_count"),
        "release_benchmark_summary_valid": release_benchmark.get("summary_valid") is True,
        "markdown_operator_docs_valid": markdown_docs.get("docs_valid") is True,
        "operator_docs_marker_regression_current_success": marker_current.get("success") is True,
        "operator_docs_marker_regression_current_regression_success": marker_current_regression.get("success") is True,
        "operator_docs_marker_regression_atomicity_success": marker_atomicity.get("success") is True,
        "user_authorization_receipt_valid": authorization.get("receipt_valid") is True,
        "user_authorization_recorded": authorization.get("authorization_recorded") is True,
        "breakthrough_attempt_receipt_valid": breakthrough.get("receipt_valid") is True,
        "source_access_attempt_recorded": breakthrough.get("source_access_attempt_recorded") is True,
        "foldx_runtime_probe_recorded": breakthrough.get("foldx_runtime_probe_recorded") is True,
        "unblock_operator_packets_valid": unblock_packets.get("packets_valid") is True,
        "source_acquisition_packets": unblock_packets.get("source_acquisition_packets"),
        "foldx_runtime_packets": unblock_packets.get("foldx_runtime_packets"),
        "source_drop_manifest_valid": source_drop.get("manifest_valid") is True,
        "source_drop_exact_source_contract": source_drop.get("exact_source_contract"),
        "source_drop_unique_expected_path_rows": source_drop.get("unique_expected_path_rows"),
        "source_drop_ready_for_extraction_rows": source_drop.get("ready_for_extraction_rows"),
        "source_drop_inventory_valid": source_inventory.get("inventory_valid") is True,
        "source_drop_inventory_matches_manifest": source_inventory.get("inventory_matches_manifest"),
        "source_drop_inventory_filesystem_state_matches": source_inventory.get("filesystem_state_matches"),
        "source_drop_inventory_present_expected_file_rows": source_inventory.get("present_expected_file_rows"),
        "source_drop_inventory_missing_expected_file_rows": source_inventory.get("missing_expected_file_rows"),
        "source_acquisition_shortlist_valid": source_shortlist.get("shortlist_valid") is True,
        "source_acquisition_receipt_valid": source_acquisition.get("receipt_valid") is True,
        "source_acquisition_receipt_rows": source_acquisition.get("receipt_rows"),
        "source_acquisition_public_asset_rows": source_acquisition.get("public_asset_rows"),
        "source_acquisition_probe_only_rows": source_acquisition.get("probe_only_rows"),
        "source_acquisition_source_file_obtained_rows": source_acquisition.get("source_file_obtained_rows"),
        "source_acquisition_source_file_not_obtained_rows": source_acquisition.get("source_file_not_obtained_rows"),
        "source_acquisition_integrity_verified": source_acquisition.get("acquisition_integrity_verified"),
        "source_acquisition_dsm4_composition_resolved": source_acquisition.get("dsm4_composition_resolved"),
        "source_acquisition_zenodo_archive_integrity_verified": source_acquisition.get("zenodo_archive_integrity_verified"),
        "source_acquisition_cm5_sequence_member_verified": source_acquisition.get("cm5_sequence_member_verified"),
        "source_acquisition_cm5_candidate_substitutions": source_acquisition.get("cm5_candidate_substitutions"),
        "source_acquisition_declared_substitutions_corroborated": source_acquisition.get("declared_substitutions_corroborated"),
        "source_acquisition_undeclared_substitution_candidates": source_acquisition.get("undeclared_substitution_candidates"),
        "source_acquisition_nucleotide_pdb_discrepancy": source_acquisition.get("nucleotide_pdb_discrepancy"),
        "source_acquisition_complete_composition_unambiguous": source_acquisition.get("complete_composition_unambiguous"),
        "source_acquisition_cm5_composition_candidate_resolved": source_acquisition.get("cm5_composition_candidate_resolved"),
        "source_acquisition_codon262_sequence_member_rows": source_acquisition.get("codon262_sequence_member_rows"),
        "source_acquisition_codon262_coverage_rows": source_acquisition.get("codon262_coverage_rows"),
        "source_acquisition_codon262_wt_codon_rows": source_acquisition.get("codon262_wt_codon_rows"),
        "source_acquisition_codon262_variant_codon_rows": source_acquisition.get("codon262_variant_codon_rows"),
        "source_acquisition_cm5_undeclared_substitution_candidates": source_acquisition.get("undeclared_substitution_candidates"),
        "source_acquisition_cm5_nucleotide_pdb_discrepancy": source_acquisition.get("nucleotide_pdb_discrepancy"),
        "source_acquisition_cm5_complete_composition_unambiguous": source_acquisition.get("complete_composition_unambiguous"),
        "source_acquisition_cm5_composition_formally_reviewed": source_acquisition.get("cm5_composition_formally_reviewed"),
        "source_acquisition_reviewed_locator_rows": source_acquisition.get("reviewed_source_locator_rows"),
        "source_extraction_candidate_valid": source_extraction.get("validation_success") is True,
        "source_extraction_candidate_table_s1_primer_rows": source_extraction.get("table_s1_primer_rows"),
        "source_extraction_candidate_table_s2_disulfide_bridge_rows": source_extraction.get("table_s2_disulfide_bridge_rows"),
        "source_extraction_candidate_dsm4_composition_resolved": source_extraction.get("dsm4_composition_resolved"),
        "source_extraction_candidate_complete_dsm4_residue_rows": source_extraction.get("complete_dsm4_residue_rows"),
        "source_extraction_candidate_wt_absolute_baseline_rows": source_extraction.get("wt_absolute_baseline_rows"),
        "source_extraction_candidate_measurement_locator_rows": source_extraction.get("measurement_locator_rows"),
        "source_extraction_candidate_reviewed_locator_rows": source_extraction.get("reviewed_source_locator_rows"),
        "source_extraction_candidate_cm5_sequence_member_verified": source_extraction.get("cm5_sequence_member_verified"),
        "source_extraction_candidate_cm5_pdb_wt_residue_parity_verified": source_extraction.get("cm5_pdb_wt_residue_parity_verified"),
        "source_extraction_candidate_cm5_candidate_substitutions": source_extraction.get("cm5_candidate_substitutions"),
        "source_extraction_candidate_declared_substitutions_corroborated": source_extraction.get("declared_substitutions_corroborated"),
        "source_extraction_candidate_undeclared_substitution_candidates": source_extraction.get("undeclared_substitution_candidates"),
        "source_extraction_candidate_nucleotide_pdb_discrepancy_verified": source_extraction.get("nucleotide_pdb_discrepancy_verified"),
        "source_extraction_candidate_complete_composition_unambiguous": source_extraction.get("complete_composition_unambiguous"),
        "source_extraction_candidate_codon262_cross_read_matrix_verified": source_extraction.get("codon262_cross_read_matrix_verified"),
        "source_extraction_candidate_codon262_sequence_member_rows": source_extraction.get("codon262_sequence_member_rows"),
        "source_extraction_candidate_codon262_coverage_rows": source_extraction.get("codon262_coverage_rows"),
        "source_extraction_candidate_codon262_no_coverage_rows": source_extraction.get("codon262_no_coverage_rows"),
        "source_extraction_candidate_codon262_wt_codon_rows": source_extraction.get("codon262_wt_codon_rows"),
        "source_extraction_candidate_codon262_variant_codon_rows": source_extraction.get("codon262_variant_codon_rows"),
        "source_extraction_candidate_reviewer_packet_valid": reviewer_packet.get("packet_valid") is True,
        "source_extraction_candidate_reviewer_packet_alias_valid": reviewer_packet.get("reviewer_packet_valid") is True,
        "source_extraction_candidate_reviewer_packet_rows": reviewer_packet.get("packet_rows"),
        "source_extraction_candidate_reviewer_rows": reviewer_packet.get("reviewer_rows"),
        "source_extraction_candidate_reviewer_packet_needs_more_info_rows": reviewer_packet.get("needs_more_info_rows"),
        "source_extraction_candidate_reviewer_packet_human_review_rows": reviewer_packet.get("candidate_ready_for_human_review_rows"),
        "source_extraction_candidate_reviewer_packet_reviewer_completed_rows": reviewer_packet.get("reviewer_completed_rows"),
        "source_extraction_candidate_reviewer_packet_composition_candidate_resolved_rows": reviewer_packet.get("composition_candidate_resolved_rows"),
        "source_extraction_candidate_reviewer_packet_dsm4_unresolved_rows": reviewer_packet.get("dsm4_unresolved_rows"),
        "source_extraction_candidate_reviewer_packet_cm5_ambiguous_rows": reviewer_packet.get("cm5_composition_ambiguous_rows"),
        "source_extraction_candidate_reviewer_packet_declared_substitutions_rows": reviewer_packet.get("declared_substitutions_corroborated_rows"),
        "source_extraction_candidate_reviewer_packet_nucleotide_pdb_discrepancy_rows": reviewer_packet.get("nucleotide_pdb_discrepancy_rows"),
        "source_extraction_candidate_reviewer_packet_codon262_sequence_member_rows": reviewer_packet.get("codon262_sequence_member_rows"),
        "source_extraction_candidate_reviewer_packet_codon262_coverage_rows": reviewer_packet.get("codon262_coverage_rows"),
        "source_extraction_candidate_reviewer_packet_codon262_no_coverage_rows": reviewer_packet.get("codon262_no_coverage_rows"),
        "source_extraction_candidate_reviewer_packet_codon262_wt_codon_rows": reviewer_packet.get("codon262_wt_codon_rows"),
        "source_extraction_candidate_reviewer_packet_codon262_variant_codon_rows": reviewer_packet.get("codon262_variant_codon_rows"),
        "source_extraction_candidate_reviewer_packet_approved_rows": reviewer_packet.get("approved_for_reviewed_extraction_rows"),
        "source_extraction_candidate_reviewer_packet_formal_review_rows": reviewer_packet.get("formal_review_rows"),
        "source_extraction_candidate_reviewer_packet_reviewed_extraction_rows": reviewer_packet.get("reviewed_extraction_rows"),
        "source_extraction_candidate_reviewer_packet_reviewer_filled_rows": reviewer_packet.get("reviewer_filled_rows"),
        "source_extraction_candidate_reviewer_packet_source_locator_rows": reviewer_packet.get("source_locator_rows"),
        "source_extraction_candidate_reviewer_packet_required_review_field_rows": reviewer_packet.get("required_review_field_rows"),
        "source_extraction_reviewer_closure_checklist_valid": reviewer_closure.get("checklist_valid") is True,
        "source_extraction_reviewer_closure_checklist_rows": reviewer_closure.get("checklist_rows"),
        "source_extraction_reviewer_closure_dsm4_rows": reviewer_closure.get("dsm4_rows"),
        "source_extraction_reviewer_closure_cm5_rows": reviewer_closure.get("cm5_rows"),
        "source_extraction_reviewer_closure_cm5_l262v_discrepancy_rows": reviewer_closure.get("cm5_l262v_discrepancy_rows"),
        "source_extraction_reviewer_closure_missing_rows": reviewer_closure.get("missing_rows"),
        "source_extraction_reviewer_closure_completed_rows": reviewer_closure.get("completed_rows"),
        "source_extraction_reviewer_closure_approved_rows": reviewer_closure.get("approved_rows"),
        "source_extraction_reviewer_closure_ready_for_sqlite_apply_rows": reviewer_closure.get("ready_for_sqlite_apply_rows"),
        "cm5_codon262_cross_read_audit_valid": codon262_audit.get("audit_valid") is True,
        "cm5_codon262_cross_read_read_rows": codon262_audit.get("read_rows"),
        "cm5_codon262_cross_read_covered_rows": codon262_audit.get("covered_rows"),
        "cm5_codon262_cross_read_not_covered_rows": codon262_audit.get("not_covered_rows"),
        "cm5_codon262_cross_read_ttg_rows": codon262_audit.get("ttg_rows"),
        "cm5_codon262_cross_read_gtg_rows": codon262_audit.get("gtg_rows"),
        "cm5_codon262_cross_read_consensus_supports_wt_leu262": codon262_audit.get("cross_read_consensus_supports_wt_leu262"),
        "cm5_codon262_cross_read_cm5_single_read_outlier": codon262_audit.get("cm5_single_read_outlier"),
        "cm5_codon262_cross_read_discrepancy_resolved": codon262_audit.get("discrepancy_resolved"),
        "cm5_codon262_sequence_quality_evidence_audit_valid": quality_audit.get("audit_valid") is True,
        "cm5_codon262_sequence_quality_sequencing_file_rows": quality_audit.get("sequencing_file_rows"),
        "cm5_codon262_sequence_quality_seq_read_rows": quality_audit.get("seq_read_rows"),
        "cm5_codon262_sequence_quality_text_only_rows": quality_audit.get("sequence_text_only_rows"),
        "cm5_codon262_sequence_quality_artifact_rows": quality_audit.get("quality_bearing_artifact_rows"),
        "cm5_codon262_sequence_quality_chromatogram_rows": quality_audit.get("chromatogram_artifact_rows"),
        "cm5_codon262_sequence_quality_per_base_quality_rows": quality_audit.get("per_base_quality_artifact_rows"),
        "cm5_codon262_sequence_quality_raw_text_call": quality_audit.get("cm5_codon_262_raw_text_call"),
        "cm5_codon262_sequence_quality_evidence_available": quality_audit.get("cm5_quality_evidence_available"),
        "cm5_codon262_sequence_artifact_hypothesis_confirmed": quality_audit.get("sequencing_artifact_hypothesis_confirmed"),
        "cm5_codon262_sequence_quality_discrepancy_resolved": quality_audit.get("discrepancy_resolved"),
        "cm5_l262v_adjudication_packet_valid": l262v_adjudication.get("packet_valid") is True,
        "cm5_l262v_adjudication_packet_rows": l262v_adjudication.get("packet_rows"),
        "cm5_l262v_adjudication_evidence_rows": l262v_adjudication.get("evidence_rows"),
        "cm5_l262v_adjudication_allowed_option_rows": l262v_adjudication.get("allowed_adjudication_option_rows"),
        "cm5_l262v_adjudication_workflow_status": l262v_adjudication.get("workflow_status"),
        "cm5_l262v_adjudication_review_fields_empty": l262v_adjudication.get("review_fields_empty"),
        "cm5_l262v_adjudication_other_construct_ttg_context_rows": l262v_adjudication.get("other_construct_ttg_context_rows"),
        "cm5_l262v_adjudication_independent_cm5_replicate_rows": l262v_adjudication.get("cm5_independent_replicate_rows"),
        "cm5_l262v_adjudication_other_construct_context_can_resolve_cm5": l262v_adjudication.get("other_construct_context_can_resolve_cm5"),
        "cm5_l262v_adjudication_discrepancy_resolved": l262v_adjudication.get("discrepancy_resolved"),
        "cm5_l262v_decision_intake_valid": l262v_decision_intake.get("intake_valid") is True,
        "cm5_l262v_decision_intake_decision_rows": l262v_decision_intake.get("decision_rows"),
        "cm5_l262v_decision_intake_valid_decision_rows": l262v_decision_intake.get("valid_decision_rows"),
        "cm5_l262v_decision_intake_evidence_artifact_rows": l262v_decision_intake.get("evidence_artifact_rows"),
        "cm5_l262v_decision_intake_accepted_review_rows": l262v_decision_intake.get("accepted_review_rows"),
        "cm5_l262v_decision_intake_review_bound_evidence_rows": l262v_decision_intake.get("review_bound_evidence_rows"),
        "cm5_l262v_decision_intake_unreviewed_evidence_artifact_rows": l262v_decision_intake.get("unreviewed_evidence_artifact_rows"),
        "cm5_l262v_decision_intake_review_binding_valid": l262v_decision_intake.get("review_binding_valid"),
        "cm5_l262v_decision_intake_slot_compatible_evidence_rows": l262v_decision_intake.get("slot_compatible_evidence_rows"),
        "cm5_l262v_decision_intake_slot_incompatible_evidence_rows": l262v_decision_intake.get("slot_incompatible_evidence_rows"),
        "cm5_l262v_decision_intake_slot_binding_valid": l262v_decision_intake.get("slot_binding_valid"),
        "cm5_l262v_decision_intake_reviewer_bound_evidence_rows": l262v_decision_intake.get("reviewer_bound_evidence_rows"),
        "cm5_l262v_decision_intake_missing_review_reviewer_rows": l262v_decision_intake.get("missing_review_reviewer_rows"),
        "cm5_l262v_decision_intake_reviewer_provenance_valid": l262v_decision_intake.get("reviewer_provenance_valid"),
        "cm5_l262v_decision_intake_discrepancy_resolved_rows": l262v_decision_intake.get("discrepancy_resolved_rows"),
        "cm5_l262v_adjudication_review_binding_regression_success": l262v_review_binding_regression.get("success"),
        "cm5_l262v_adjudication_review_binding_regression_passed_rows": l262v_review_binding_regression.get("passed_rows"),
        "cm5_l262v_adjudication_review_binding_tamper_success": l262v_review_binding_tamper.get("success"),
        "cm5_l262v_adjudication_review_binding_tamper_passed_rows": l262v_review_binding_tamper.get("passed_rows"),
        "cm5_l262v_adjudication_review_binding_tamper_real_inputs_mutated": any(l262v_review_binding_tamper.get(field) is True for field in ("real_decision_input_mutated", "real_review_input_mutated", "real_receipt_input_mutated")),
        "cm5_l262v_adjudication_evidence_path_safety_success": l262v_path_safety.get("success"),
        "cm5_l262v_adjudication_evidence_path_safety_passed_rows": l262v_path_safety.get("passed_rows"),
        "cm5_l262v_adjudication_evidence_path_safety_real_inputs_mutated": any(l262v_path_safety.get(field) is True for field in ("real_decision_input_mutated", "real_review_input_mutated", "real_receipt_input_mutated")),
        "cm5_l262v_adjudication_upstream_review_provenance_success": l262v_upstream_provenance.get("success"),
        "cm5_l262v_adjudication_upstream_review_provenance_passed_rows": l262v_upstream_provenance.get("passed_rows"),
        "cm5_l262v_adjudication_upstream_review_provenance_real_inputs_mutated": any(l262v_upstream_provenance.get(field) is True for field in ("real_decision_input_mutated", "real_review_input_mutated", "real_receipt_input_mutated")),
        "cm5_l262v_adjudication_upstream_packet_provenance_success": l262v_packet_provenance.get("success"),
        "cm5_l262v_adjudication_upstream_packet_provenance_passed_rows": l262v_packet_provenance.get("passed_rows"),
        "cm5_l262v_adjudication_upstream_packet_provenance_real_inputs_mutated": any(l262v_packet_provenance.get(field) is True for field in ("real_packet_mutated", "real_packet_validation_mutated", "real_decision_input_mutated", "real_review_input_mutated", "real_receipt_input_mutated")),
        "cm5_l262v_evidence_intake_valid": l262v_evidence_intake.get("intake_valid") is True,
        "cm5_l262v_evidence_intake_slot_rows": l262v_evidence_intake.get("slot_rows"),
        "cm5_l262v_evidence_intake_present_rows": l262v_evidence_intake.get("present_rows"),
        "cm5_l262v_evidence_intake_missing_rows": l262v_evidence_intake.get("missing_rows"),
        "cm5_l262v_evidence_intake_filesystem_parity_rows": l262v_evidence_intake.get("filesystem_parity_rows"),
        "cm5_l262v_evidence_intake_reviewed_rows": l262v_evidence_intake.get("reviewed_evidence_rows"),
        "cm5_l262v_evidence_intake_ready_for_adjudication_rows": l262v_evidence_intake.get("ready_for_adjudication_rows"),
        "cm5_l262v_evidence_intake_file_presence_is_reviewed_evidence": l262v_evidence_intake.get("file_presence_is_reviewed_evidence"),
        "cm5_l262v_public_probe_valid": l262v_public_probe.get("receipt_valid") is True,
        "cm5_l262v_public_probe_rows": l262v_public_probe.get("probe_rows"),
        "cm5_l262v_public_probe_slot_artifact_rows": l262v_public_probe.get("slot_artifact_rows"),
        "cm5_l262v_public_probe_evidence_slot_missing_rows": l262v_public_probe.get("evidence_slot_missing_rows"),
        "cm5_l262v_evidence_receipts_valid": l262v_evidence_receipts.get("intake_valid") is True,
        "cm5_l262v_evidence_receipt_rows": l262v_evidence_receipts.get("receipt_rows"),
        "cm5_l262v_evidence_valid_receipt_rows": l262v_evidence_receipts.get("valid_receipt_rows"),
        "cm5_l262v_evidence_present_artifact_rows": l262v_evidence_receipts.get("present_artifact_rows"),
        "cm5_l262v_evidence_unreceipted_present_artifact_rows": l262v_evidence_receipts.get("unreceipted_present_artifact_rows"),
        "cm5_l262v_evidence_receipt_is_reviewed_evidence": l262v_evidence_receipts.get("receipt_is_reviewed_evidence"),
        "cm5_l262v_evidence_reviews_valid": l262v_evidence_reviews.get("intake_valid") is True,
        "cm5_l262v_evidence_review_rows": l262v_evidence_reviews.get("review_rows"),
        "cm5_l262v_evidence_valid_review_rows": l262v_evidence_reviews.get("valid_review_rows"),
        "cm5_l262v_evidence_accepted_for_adjudication_rows": l262v_evidence_reviews.get("accepted_for_adjudication_rows"),
        "cm5_l262v_evidence_unreviewed_valid_receipt_rows": l262v_evidence_reviews.get("unreviewed_valid_receipt_rows"),
        "cm5_l262v_evidence_ready_for_adjudication_rows": l262v_evidence_reviews.get("ready_for_adjudication_rows"),
        "cm5_l262v_evidence_review_is_adjudication": l262v_evidence_reviews.get("review_is_adjudication"),
        "cm5_l262v_message_drafts_valid": l262v_message_drafts.get("drafts_valid") is True,
        "cm5_l262v_message_draft_rows": l262v_message_drafts.get("draft_rows"),
        "cm5_l262v_message_draft_unique_sha_rows": l262v_message_drafts.get("unique_message_sha256_rows"),
        "cm5_l262v_message_draft_approved_rows": l262v_message_drafts.get("message_approved_rows"),
        "cm5_l262v_request_authorization_valid": l262v_request_authorization.get("intake_valid") is True,
        "cm5_l262v_request_authorization_message_drafts_valid": l262v_request_authorization.get("message_draft_validation_valid"),
        "cm5_l262v_request_authorization_message_draft_rows": l262v_request_authorization.get("message_draft_rows"),
        "cm5_l262v_request_authorization_rows": l262v_request_authorization.get("authorization_rows"),
        "cm5_l262v_request_authorized_send_rows": l262v_request_authorization.get("authorized_send_rows"),
        "cm5_l262v_request_message_sha_bound_authorization_rows": l262v_request_authorization.get("message_sha_bound_authorization_rows"),
        "cm5_l262v_request_send_ready_candidate_rows": l262v_request_authorization.get("send_ready_candidate_rows"),
        "cm5_l262v_request_sent_rows": l262v_request_authorization.get("request_sent_rows"),
        "cm5_l262v_request_external_message_sent": l262v_request_authorization.get("external_message_sent"),
        "cm5_l262v_request_send_executor_present": l262v_request_authorization.get("send_executor_present"),
        "cm5_l262v_send_guard_valid": l262v_send_guard.get("guard_valid") is True,
        "cm5_l262v_send_guard_execution_status": l262v_send_guard.get("execution_status"),
        "cm5_l262v_send_guard_send_attempted": l262v_send_guard.get("send_attempted"),
        "source_extraction_candidate_cm5_composition_candidate_resolved": source_extraction.get("cm5_composition_candidate_resolved"),
        "source_extraction_candidate_cm5_undeclared_substitution_candidates": source_extraction.get("undeclared_substitution_candidates"),
        "source_extraction_candidate_cm5_nucleotide_pdb_discrepancy_verified": source_extraction.get("nucleotide_pdb_discrepancy_verified"),
        "source_extraction_candidate_cm5_complete_composition_unambiguous": source_extraction.get("complete_composition_unambiguous"),
        "source_extraction_candidate_cm5_composition_formally_reviewed": source_extraction.get("cm5_composition_formally_reviewed"),
        "source_extraction_candidate_complete_cm5_candidate_residue_rows": source_extraction.get("complete_cm5_candidate_residue_rows"),
        "source_extraction_candidate_mutation_effect_measurement_rows": source_extraction.get("mutation_effect_measurement_rows"),
        "source_acquisition_structured_locator_candidate_count": source_acquisition.get("structured_locator_candidate_count"),
        "source_acquisition_structured_measurement_candidate_rows": source_acquisition.get("structured_locator_measurement_candidate_rows"),
        "source_acquisition_shortlist_unique_pmid_rows": source_shortlist.get("unique_pmid_rows"),
        "source_acquisition_shortlist_unique_required_file_path_rows": source_shortlist.get("unique_required_file_path_rows"),
        "source_acquisition_shortlist_markdown_exact_coverage": source_shortlist.get("markdown_exact_coverage"),
        "source_acquisition_shortlist_paper_ready_rows": source_shortlist.get("paper_ready_rows"),
        "literature_web_search_receipt_valid": literature_search.get("receipt_valid") is True,
        "literature_web_search_secondary_lead_rows": literature_search.get("secondary_lead_rows"),
        "literature_web_search_ready_for_sqlite_apply_rows": literature_search.get("ready_for_sqlite_apply_rows"),
        "source_drop_extraction_readiness_candidates_valid": source_drop_extraction.get("candidates_valid") is True,
        "source_drop_extraction_ready_for_reviewed_extraction_rows": source_drop_extraction.get("ready_for_reviewed_extraction_rows"),
        "source_drop_extraction_ready_for_sqlite_apply_rows": source_drop_extraction.get("ready_for_sqlite_apply_rows"),
        "family_apply_importer_design_valid": importer_design.get("design_valid") is True,
        "family_apply_importer_ready_to_apply_now_rows": importer_design.get("ready_to_apply_now_rows"),
        "family_apply_transaction_plans_valid": transaction_plan.get("plans_valid") is True,
        "family_apply_transaction_ready_to_apply_rows": transaction_plan.get("ready_to_apply_rows"),
        "family_apply_transaction_write_operation_count": transaction_plan.get("write_operation_count"),
        "foldx_provision_manifest_valid": foldx_provision.get("manifest_valid") is True,
        "foldx_provision_ready_for_runtime_receipt_rows": foldx_provision.get("ready_for_runtime_receipt_rows"),
        "foldx_provision_manifest_candidate_valid": foldx_provision_candidate.get("candidate_valid") is True,
        "foldx_provision_candidate_present_rows": foldx_provision_candidate.get("present_rows"),
        "foldx_provision_candidate_missing_rows": foldx_provision_candidate.get("missing_rows"),
        "foldx_provision_candidate_executable_present": foldx_provision_candidate.get("executable_present"),
        "foldx_provision_candidate_technical_smoke_artifact_count": foldx_provision_candidate.get("technical_smoke_artifact_count"),
        "foldx_provision_candidate_technical_formal_path_overlap_rows": foldx_provision_candidate.get("technical_formal_path_overlap_rows"),
        "foldx_provision_candidate_technical_evidence_substitutes_formal_provision": foldx_provision_candidate.get("technical_evidence_substitutes_formal_provision"),
        "foldx_provision_candidate_technical_smoke_artifact_rows": foldx_provision_candidate.get("technical_smoke_artifact_rows"),
        "foldx_provision_candidate_technical_smoke_checksum_verified_rows": foldx_provision_candidate.get("technical_smoke_checksum_verified_rows"),
        "foldx_provision_candidate_technical_smoke_substitution_allowed": foldx_provision_candidate.get("technical_smoke_substitution_allowed"),
        "foldx_provision_candidate_formal_smoke_artifact_present_rows": foldx_provision_candidate.get("formal_smoke_artifact_present_rows"),
        "foldx_provision_candidate_formal_smoke_artifact_missing_rows": foldx_provision_candidate.get("formal_smoke_artifact_missing_rows"),
        "foldx_provision_candidate_ready_for_runtime_receipt_rows": foldx_provision_candidate.get("ready_for_runtime_receipt_rows"),
        "foldx_runtime_receipt_candidate_drafts_valid": foldx_receipt_draft.get("drafts_valid") is True,
        "foldx_runtime_receipt_candidate_decision": foldx_receipt_draft.get("receipt_decision"),
        "foldx_technical_smoke_validation_success": foldx_technical_smoke.get("success") is True,
        "foldx_technical_smoke_only": foldx_technical_smoke.get("technical_smoke_only"),
        "foldx_technical_smoke_passed": foldx_technical_smoke.get("technical_smoke_passed"),
        "foldx_technical_smoke_parsed_rows": foldx_technical_smoke.get("parsed_rows"),
        "foldx_technical_smoke_artifact_count": foldx_technical_smoke.get("artifact_count"),
        "foldx_parameterization_dependency_warning_detected": foldx_technical_smoke.get("parameterization_dependency_warning_detected"),
        "foldx_parameterization_warning_command_count": foldx_technical_smoke.get("parameterization_warning_command_count"),
        "foldx_unrecognized_atom_rows": foldx_technical_smoke.get("unrecognized_atom_rows"),
        "foldx_unrecognized_molecule_names": foldx_technical_smoke.get("unrecognized_molecule_names"),
        "foldx_parameterization_review_completed": foldx_technical_smoke.get("parameterization_review_completed"),
        "foldx_ddg_value_technical_only": foldx_technical_smoke.get("ddg_value_technical_only"),
        "foldx_energetic_interpretation_approved": foldx_technical_smoke.get("energetic_interpretation_approved"),
        "foldx_physical_ddg_comparable": foldx_technical_smoke.get("physical_ddg_comparable"),
        "foldx_safe_for_benchmark_intake": foldx_technical_smoke.get("safe_for_benchmark_intake"),
        "foldx_technical_smoke_formal_runtime_receipt_written": foldx_technical_smoke.get("formal_runtime_receipt_written"),
        "foldx_technical_smoke_approved_for_physical_ddg_runtime": foldx_technical_smoke.get("approved_for_physical_ddg_runtime"),
        "foldx_benchmark_bridge_isolation_valid": foldx_bridge_isolation.get("isolation_valid") is True,
        "foldx_bridge_intake_rows_written": foldx_bridge_isolation.get("bridge_intake_rows_written"),
        "foldx_execution_plan_blocker_valid": foldx_execution_plan.get("receipt_valid") is True,
        "foldx_execution_plan_ready_rows": foldx_execution_plan.get("ready_rows"),
        "foldx_execution_plan_blocked_rows": foldx_execution_plan.get("blocked_rows"),
        "foldx_ready_for_execution": foldx_execution_plan.get("foldx_ready_for_execution"),
        "foldx_buildmodel_technical_smoke_executed": foldx_execution_plan.get("foldx_buildmodel_technical_smoke_executed"),
        "foldx_buildmodel_physical_smoke_executed": foldx_execution_plan.get("foldx_buildmodel_physical_smoke_executed"),
        "foldx_technical_smoke_satisfies_formal_provision": foldx_execution_plan.get("foldx_technical_smoke_satisfies_formal_provision"),
        "benchmark_unblock_design_valid": benchmark_unblock.get("design_valid") is True,
        "benchmark_unblock_completion_ready_rows": benchmark_unblock.get("completion_ready_rows"),
        "hard_gate_formal_decision_draft_package_valid": hard_gate_drafts.get("draft_package_valid") is True,
        "hard_gate_formal_decision_rows_written": hard_gate_drafts.get("formal_decision_rows_written"),
        "hard_gate_bridge_intake_rows_written": hard_gate_drafts.get("bridge_intake_rows_written"),
        "new_paper_extraction_templates_valid": extraction_templates.get("templates_valid") is True,
        "new_paper_extraction_ready_for_sqlite_apply_rows": extraction_templates.get("ready_for_sqlite_apply_rows"),
        "reviewed_extraction_output_drafts_valid": extraction_drafts.get("drafts_valid") is True,
        "reviewed_extraction_completed_rows": extraction_drafts.get("reviewed_extraction_completed_rows"),
        "reviewed_extraction_ready_for_sqlite_apply_rows": extraction_drafts.get("ready_for_sqlite_apply_rows"),
        "claim_release_consistency_valid": claim_release.get("claim_release_consistent") is True,
        "claim_release_customer_delivery_ready": claim_release.get("customer_delivery_ready"),
        "claim_release_approved_for_ordering": claim_release.get("approved_for_ordering"),
        "remaining_blocker_closure_matrix_valid": blocker_matrix.get("matrix_valid") is True,
        "remaining_blocker_completion_ready_rows": blocker_matrix.get("completion_ready_rows"),
        "post_source_drop_rerun_receipt_valid": post_source_drop.get("receipt_valid") is True,
        "post_source_drop_rerun_command_rows": post_source_drop.get("command_rows"),
        "post_source_drop_rerun_command_contract_valid": post_source_drop.get("command_contract_valid"),
        "post_source_drop_rerun_validation_current_success": post_source_current.get("success"),
        "post_source_drop_rerun_validation_current_regression_success": post_source_current_regression.get("success"),
        "post_source_drop_rerun_independent_policy_success": post_source_policy.get("success"),
        "post_source_drop_rerun_independent_policy_regression_success": post_source_policy_regression.get("success"),
        "post_source_drop_rerun_independent_policy_current_success": post_source_policy_current.get("success"),
        "post_source_drop_rerun_independent_policy_current_regression_success": post_source_policy_current_regression.get("success"),
        "post_source_drop_rerun_commands_executed": post_source_drop.get("commands_executed"),
        "post_source_drop_rerun_outputs_freshness_verified": post_source_drop.get("outputs_freshness_verified"),
        "post_source_drop_rerun_source_evidence_ready": post_source_drop.get("source_evidence_ready"),
        "post_source_drop_rerun_ready_for_sqlite_apply": post_source_drop.get("ready_for_sqlite_apply"),
        "post_source_drop_rerun_sqlite_write_command_rows": post_source_drop.get("sqlite_write_command_rows"),
        "post_source_drop_rerun_dry_run_audit_valid": rerun_dry_run.get("audit_valid") is True,
        "post_source_drop_rerun_dry_run_command_contract_valid": rerun_dry_run.get("command_contract_valid"),
        "post_source_drop_rerun_dry_run_recipe_operational": rerun_dry_run.get("rerun_recipe_operational"),
        "post_source_drop_rerun_dry_run_commands_executed": rerun_dry_run.get("commands_executed"),
        "post_source_drop_rerun_dry_run_outputs_freshness_verified": rerun_dry_run.get("outputs_freshness_verified"),
        "post_source_drop_rerun_dry_run_rerun_completion_receipted": rerun_dry_run.get("rerun_completion_receipted"),
        "post_source_drop_rerun_dry_run_ready_for_source_drop_rerun": rerun_dry_run.get("ready_for_source_drop_rerun"),
        "post_source_drop_rerun_dry_run_source_evidence_ready": rerun_dry_run.get("source_evidence_ready"),
        "post_source_drop_rerun_dry_run_ready_for_sqlite_apply": rerun_dry_run.get("ready_for_sqlite_apply"),
        "workstream_acceptance_decision_rows": workstream_acceptance.get("decision_rows"),
        "workstream_acceptance_accepted_streams": workstream_acceptance.get("accepted_streams"),
        "workstream_acceptance_all_streams_accepted": workstream_acceptance.get("all_streams_accepted"),
        "blocker_activation_map_valid": activation_map.get("activation_map_valid") is True,
        "blocker_activation_rows": activation_map.get("activation_rows"),
        "blocker_activation_completion_ready_rows": activation_map.get("activation_completion_ready_rows"),
        "external_input_readiness_board_valid": external_inputs.get("board_valid") is True,
        "external_input_rows": external_inputs.get("input_rows"),
        "external_input_completion_ready_rows": external_inputs.get("completion_ready_rows"),
        "latest_blocker_coverage_audit_valid": coverage_audit.get("audit_valid") is True,
        "latest_blocker_coverage_uncovered_blockers": coverage_audit.get("uncovered_blockers"),
        "latest_blocker_coverage_expected_overall_term_count": coverage_audit.get("expected_overall_term_count"),
        "latest_blocker_coverage_expected_runner_term_count": coverage_audit.get("expected_runner_term_count"),
        "latest_blocker_coverage_expected_doc_term_count": coverage_audit.get("expected_doc_term_count"),
        "remaining_blocker_cross_binding_success": blocker_cross_binding.get("success") is True,
        "remaining_blocker_cross_binding_shared_rows": blocker_cross_binding.get("shared_blocker_rows"),
        "remaining_blocker_cross_binding_exact_current_receipt_rows": blocker_cross_binding.get("exact_current_receipt_rows"),
        "remaining_blocker_cross_binding_regression_success": blocker_cross_binding_regression.get("success") is True,
        "remaining_blocker_cross_binding_regression_rejected_negative_cases": blocker_cross_binding_regression.get("rejected_negative_cases"),
        "handoff_bundle_manifest_valid": handoff.get("bundle_valid") is True,
        "handoff_bundle_rows": handoff.get("bundle_rows"),
        "handoff_unique_path_rows": handoff.get("unique_path_rows"),
        "handoff_freshness_verified_rows": handoff.get("freshness_verified_rows"),
        "handoff_freshness_exempt_rows": handoff.get("freshness_exempt_rows"),
        "handoff_filesystem_integrity_valid": handoff.get("filesystem_integrity_valid"),
        "external_sqlite_mutated": False,
        "apply_executed": False,
        "allow_apply": False,
        "export_safe_released": False,
        "formal_decision_rows_written": 0,
        "release_ready": False,
        "safe_for_model_claim": False,
        "benchmark_ready_for_model_claim": False,
        "release_status": "not_released",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Build Stage 25 overall fail-closed index")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    index = build_index()
    args.output.write_text(json.dumps(index, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(args.output), "index_valid": index["index_valid"], "failure_count": index["failure_count"], "summary_count": len(index["summaries"])}, ensure_ascii=False, sort_keys=True))
    return 0 if index["index_valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
