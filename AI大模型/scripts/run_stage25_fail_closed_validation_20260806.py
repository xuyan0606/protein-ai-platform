#!/usr/bin/env python3
"""Run the Stage 25 fail-closed validation chain."""

from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
ENZYME_DB_ROOT = Path("/Users/keweibo/科为博/05自动化程序/04研发工作区/酶数据库")
BACKEND_PYTHON = AI_ROOT.parent / "backend/.venv/bin/python"
DEFAULT_OUTPUT = AI_ROOT / "reports" / "stage25_fail_closed_validation_run_report_20260806.json"
LOCK_PATH = AI_ROOT / "reports" / "stage25_fail_closed_validation_run_20260806.lock"
COMMAND_CONTRACT_VERSION = "stage25-fail-closed-validation-commands-v1"
DEFERRED_BOOTSTRAP_INITIAL = "build_release_benchmark_stage25_fail_closed_summary"
DEFERRED_BOOTSTRAP_FINAL = "rebuild_release_benchmark_stage25_summary_after_operator_docs_sync"


COMMANDS = [
    {
        "name": "new_paper_importer_tests",
        "cwd": ENZYME_DB_ROOT,
        "cmd": [sys.executable, "-m", "pytest", "test_new_paper_candidates_dry_run_importer_20260805.py", "-q"],
    },
    {
        "name": "new_paper_dry_run_xylanase",
        "cwd": ENZYME_DB_ROOT,
        "cmd": [sys.executable, "new_paper_candidates_dry_run_importer_20260805.py", "--family", "xylanase"],
        "json_stdout": True,
        "expected_proposal_count": 2,
    },
    {
        "name": "new_paper_dry_run_lipase",
        "cwd": ENZYME_DB_ROOT,
        "cmd": [sys.executable, "new_paper_candidates_dry_run_importer_20260805.py", "--family", "lipase"],
        "json_stdout": True,
        "expected_proposal_count": 2,
    },
    {
        "name": "new_paper_dry_run_amylase",
        "cwd": ENZYME_DB_ROOT,
        "cmd": [sys.executable, "new_paper_candidates_dry_run_importer_20260805.py", "--family", "amylase"],
        "json_stdout": True,
        "expected_proposal_count": 2,
    },
    {
        "name": "new_paper_apply_blocked",
        "cwd": ENZYME_DB_ROOT,
        "cmd": [sys.executable, "new_paper_candidates_dry_run_importer_20260805.py", "--apply"],
        "expected_returncode": 1,
        "expected_stderr_contains": "blocked: this importer is dry-run only",
    },
    {
        "name": "new_paper_paper_only_apply_plan",
        "cwd": ENZYME_DB_ROOT,
        "cmd": [sys.executable, "new_paper_candidates_dry_run_importer_20260805.py", "--paper-only-apply-dry-run", "--apply-plan", "stage25_paper_only_apply_plan_20260806.json"],
    },
    {
        "name": "validate_stage25_paper_only_apply_plan",
        "cwd": ENZYME_DB_ROOT,
        "cmd": [sys.executable, "validate_stage25_paper_only_apply_plan_20260806.py"],
    },
    {
        "name": "build_stage25_sqlite_backup_preflight",
        "cwd": ENZYME_DB_ROOT,
        "cmd": [sys.executable, "build_stage25_sqlite_backup_preflight_20260806.py"],
    },
    {
        "name": "validate_stage25_sqlite_backup_preflight",
        "cwd": ENZYME_DB_ROOT,
        "cmd": [sys.executable, "validate_stage25_sqlite_backup_preflight_20260806.py"],
    },
    {
        "name": "validate_new_paper_allowlist_identity_migration_report",
        "cwd": ENZYME_DB_ROOT,
        "cmd": [sys.executable, "validate_new_paper_allowlist_identity_migration_report_20260806.py"],
    },
    {
        "name": "validate_new_paper_allowlist_identity_patch_draft",
        "cwd": ENZYME_DB_ROOT,
        "cmd": [sys.executable, "validate_new_paper_allowlist_identity_patch_draft_20260806.py"],
    },
    {
        "name": "validate_new_paper_fulltext_gap_worklist",
        "cwd": ENZYME_DB_ROOT,
        "cmd": [sys.executable, "validate_new_paper_fulltext_gap_worklist_20260806.py"],
    },
    {
        "name": "validate_new_paper_proposal_set_consistency",
        "cwd": ENZYME_DB_ROOT,
        "cmd": [sys.executable, "validate_new_paper_proposal_set_consistency_20260806.py"],
    },
    {
        "name": "build_stage25_paper_metadata_only_plan",
        "cwd": ENZYME_DB_ROOT,
        "cmd": [sys.executable, "build_stage25_paper_metadata_only_plan_20260806.py"],
    },
    {
        "name": "validate_stage25_paper_metadata_only_plan",
        "cwd": AI_ROOT,
        "cmd": [sys.executable, "scripts/validate_stage25_paper_metadata_only_plan_20260806.py"],
    },
    {
        "name": "run_stage25_approved_apply_execute_requested",
        "cwd": ENZYME_DB_ROOT,
        "cmd": [sys.executable, "run_stage25_approved_apply_20260806.py", "--execute"],
        "expected_returncode": 1,
    },
    {
        "name": "validate_stage25_approved_apply_report",
        "cwd": ENZYME_DB_ROOT,
        "cmd": [sys.executable, "validate_stage25_approved_apply_report_20260806.py"],
    },
    {
        "name": "build_stage25_execute_blocker_detail",
        "cwd": AI_ROOT,
        "cmd": [sys.executable, "scripts/build_stage25_execute_blocker_detail_20260806.py"],
    },
    {
        "name": "validate_stage25_execute_blocker_detail",
        "cwd": AI_ROOT,
        "cmd": [sys.executable, "scripts/validate_stage25_execute_blocker_detail_20260806.py"],
    },
    {
        "name": "build_stage25_execute_closeout_checklist",
        "cwd": AI_ROOT,
        "cmd": [sys.executable, "scripts/build_stage25_execute_closeout_checklist_20260806.py"],
    },
    {
        "name": "validate_stage25_execute_closeout_checklist",
        "cwd": AI_ROOT,
        "cmd": [sys.executable, "scripts/validate_stage25_execute_closeout_checklist_20260806.py"],
    },
    {
        "name": "build_stage25_execute_closeout_reviewer_intake",
        "cwd": AI_ROOT,
        "cmd": [sys.executable, "scripts/build_stage25_execute_closeout_reviewer_intake_20260806.py"],
    },
    {
        "name": "validate_stage25_execute_closeout_reviewer_intake",
        "cwd": AI_ROOT,
        "cmd": [sys.executable, "scripts/validate_stage25_execute_closeout_reviewer_intake_20260806.py"],
    },
    {
        "name": "build_stage25_execute_closeout_reviewer_packet",
        "cwd": AI_ROOT,
        "cmd": [sys.executable, "scripts/build_stage25_execute_closeout_reviewer_packet_20260806.py"],
    },
    {
        "name": "validate_stage25_execute_closeout_reviewer_packet",
        "cwd": AI_ROOT,
        "cmd": [sys.executable, "scripts/validate_stage25_execute_closeout_reviewer_packet_20260806.py"],
    },
    {
        "name": "build_local_release_manifest",
        "cwd": AI_ROOT,
        "cmd": [sys.executable, "scripts/build_local_release_manifest.py"],
    },
    {
        "name": "build_new_paper_stage25_fail_closed_validation_summary",
        "cwd": ENZYME_DB_ROOT,
        "cmd": [sys.executable, "build_new_paper_stage25_fail_closed_validation_summary_20260806.py"],
    },
    {
        "name": "validate_release_benchmark_human_decision_worklist",
        "cwd": AI_ROOT,
        "cmd": [sys.executable, "scripts/validate_release_benchmark_human_decision_worklist_20260806.py"],
    },
    {
        "name": "build_release_benchmark_stage25_fail_closed_summary",
        "cwd": AI_ROOT,
        "cmd": [sys.executable, "scripts/build_release_benchmark_stage25_fail_closed_summary_20260806.py"],
    },
    {
        "name": "validate_local_release_consistency_semantic_policy",
        "cwd": AI_ROOT,
        "cmd": [sys.executable, "scripts/validate_local_release_consistency_semantic_policy.py"],
    },
    {
        "name": "validate_local_release_consistency_semantic_policy_regression",
        "cwd": AI_ROOT,
        "cmd": [sys.executable, "scripts/validate_local_release_consistency_semantic_policy_regression.py"],
    },
    {
        "name": "validate_local_release_consistency_semantic_policy_current",
        "cwd": AI_ROOT,
        "cmd": [sys.executable, "scripts/validate_local_release_consistency_semantic_policy_current.py"],
    },
    {
        "name": "validate_local_release_consistency_semantic_policy_current_regression",
        "cwd": AI_ROOT,
        "cmd": [sys.executable, "scripts/validate_local_release_consistency_semantic_policy_current_regression.py"],
    },
    {
        "name": "validate_local_release_consistency_semantic_policy_atomicity_regression",
        "cwd": AI_ROOT,
        "cmd": [sys.executable, "scripts/validate_local_release_consistency_semantic_policy_atomicity_regression.py"],
    },
    {
        "name": "validate_enzyme_agent_controlled_release_guard_order",
        "cwd": AI_ROOT,
        "cmd": [sys.executable, "scripts/validate_enzyme_agent_controlled_release_guard_order.py"],
    },
    {
        "name": "validate_enzyme_agent_controlled_release_guard_order_regression",
        "cwd": AI_ROOT,
        "cmd": [sys.executable, "scripts/validate_enzyme_agent_controlled_release_guard_order_regression.py"],
    },
    {
        "name": "validate_enzyme_agent_controlled_release_guard_order_current",
        "cwd": AI_ROOT,
        "cmd": [sys.executable, "scripts/validate_enzyme_agent_controlled_release_guard_order_current.py"],
    },
    {
        "name": "validate_enzyme_agent_controlled_release_guard_order_current_regression",
        "cwd": AI_ROOT,
        "cmd": [sys.executable, "scripts/validate_enzyme_agent_controlled_release_guard_order_current_regression.py"],
    },
    {
        "name": "validate_enzyme_agent_controlled_release_guard_order_atomicity_regression",
        "cwd": AI_ROOT,
        "cmd": [sys.executable, "scripts/validate_enzyme_agent_controlled_release_guard_order_atomicity_regression.py"],
    },
    {
        "name": "validate_enzyme_agent_controlled_execution_wave_pair_atomicity_regression",
        "cwd": AI_ROOT,
        "cmd": [sys.executable, "scripts/validate_enzyme_agent_controlled_execution_wave_pair_atomicity_regression.py"],
    },
    {
        "name": "validate_enzyme_agent_execution_receipt_proof_current",
        "cwd": AI_ROOT,
        "cmd": [sys.executable, "scripts/validate_enzyme_agent_execution_receipt_proof_current.py"],
    },
    {
        "name": "validate_enzyme_agent_execution_receipt_proof_current_regression",
        "cwd": AI_ROOT,
        "cmd": [sys.executable, "scripts/validate_enzyme_agent_execution_receipt_proof_current_regression.py"],
    },
    {
        "name": "validate_local_release_safety_guard_links_atomicity_regression",
        "cwd": AI_ROOT,
        "cmd": [sys.executable, "scripts/validate_local_release_safety_guard_links_atomicity_regression.py"],
    },
    {
        "name": "validate_local_release_safety_guard_links_current_regression_atomicity_regression",
        "cwd": AI_ROOT,
        "cmd": [sys.executable, "scripts/validate_local_release_safety_guard_links_current_regression_atomicity_regression.py"],
    },
    {
        "name": "validate_stage25_operator_docs_sync_contract_policy",
        "cwd": AI_ROOT,
        "cmd": [sys.executable, "scripts/validate_stage25_operator_docs_sync_contract_policy.py"],
    },
    {
        "name": "validate_safe_training_pipeline_current_receipt",
        "cwd": AI_ROOT,
        "cmd": [sys.executable, "scripts/validate_safe_training_pipeline_current_receipt.py"],
    },
    {
        "name": "validate_safe_training_pipeline_current_receipt_regression",
        "cwd": AI_ROOT,
        "cmd": [sys.executable, "scripts/validate_safe_training_pipeline_current_receipt_regression.py"],
    },
    {
        "name": "validate_local_release_terminal_defer_mode_regression",
        "cwd": AI_ROOT,
        "cmd": [sys.executable, "scripts/validate_local_release_terminal_defer_mode_regression.py"],
    },
    {
        "name": "validate_stage25_operator_docs_sync_contract_policy_regression",
        "cwd": AI_ROOT,
        "cmd": [sys.executable, "scripts/validate_stage25_operator_docs_sync_contract_policy_regression.py"],
    },
    {
        "name": "sync_stage25_operator_docs_dynamic_status",
        "cwd": AI_ROOT,
        "cmd": [sys.executable, "scripts/sync_stage25_operator_docs_dynamic_status.py"],
    },
    {
        "name": "validate_stage25_operator_docs_dynamic_status_sync_regression",
        "cwd": AI_ROOT,
        "cmd": [sys.executable, "scripts/validate_stage25_operator_docs_dynamic_status_sync_regression.py"],
    },
    {
        "name": "validate_stage25_operator_docs_dynamic_status_sync_regression_current",
        "cwd": AI_ROOT,
        "cmd": [sys.executable, "scripts/validate_stage25_operator_docs_dynamic_status_sync_regression_current.py"],
    },
    {
        "name": "validate_stage25_operator_docs_dynamic_status_sync_regression_current_regression",
        "cwd": AI_ROOT,
        "cmd": [sys.executable, "scripts/validate_stage25_operator_docs_dynamic_status_sync_regression_current_regression.py"],
    },
    {
        "name": "validate_stage25_operator_docs_dynamic_status_sync_regression_atomicity_regression",
        "cwd": AI_ROOT,
        "cmd": [sys.executable, "scripts/validate_stage25_operator_docs_dynamic_status_sync_regression_atomicity_regression.py"],
    },
    {
        "name": "validate_stage25_operator_docs_sync_current_receipt",
        "cwd": AI_ROOT,
        "cmd": [sys.executable, "scripts/validate_stage25_operator_docs_sync_current_receipt.py"],
    },
    {
        "name": "validate_stage25_operator_docs_sync_current_receipt_regression",
        "cwd": AI_ROOT,
        "cmd": [sys.executable, "scripts/validate_stage25_operator_docs_sync_current_receipt_regression.py"],
    },
    {
        "name": "validate_stage25_operator_docs_sync_terminal_recovery_regression",
        "cwd": AI_ROOT,
        "cmd": [sys.executable, "scripts/validate_stage25_operator_docs_sync_terminal_recovery_regression.py"],
    },
    {
        "name": "validate_stage25_markdown_operator_docs",
        "cwd": AI_ROOT,
        "cmd": [sys.executable, "scripts/validate_stage25_markdown_operator_docs_20260806.py"],
    },
    {
        "name": "validate_claim_readiness_policy_anchor",
        "cwd": AI_ROOT,
        "cmd": [sys.executable, "scripts/validate_claim_readiness_policy_anchor.py"],
    },
    {
        "name": "validate_claim_readiness_policy_anchor_regression",
        "cwd": AI_ROOT,
        "cmd": [sys.executable, "scripts/validate_claim_readiness_policy_anchor_regression.py"],
    },
    {
        "name": "validate_claim_readiness_matrix_fail_closed_policy",
        "cwd": AI_ROOT,
        "cmd": [sys.executable, "scripts/validate_claim_readiness_matrix_fail_closed_policy.py"],
    },
    {
        "name": "validate_claim_readiness_matrix_fail_closed_policy_current",
        "cwd": AI_ROOT,
        "cmd": [sys.executable, "scripts/validate_claim_readiness_matrix_fail_closed_policy_current.py"],
    },
    {
        "name": "validate_claim_readiness_matrix_fail_closed_policy_current_regression",
        "cwd": AI_ROOT,
        "cmd": [sys.executable, "scripts/validate_claim_readiness_matrix_fail_closed_policy_current_regression.py"],
    },
    {
        "name": "validate_claim_promotion_decisions",
        "cwd": AI_ROOT,
        "cmd": [sys.executable, "scripts/validate_claim_promotion_decisions.py"],
    },
    {
        "name": "rebuild_data_lake_manifest_after_operator_docs_sync",
        "cwd": AI_ROOT,
        "cmd": [sys.executable, "scripts/build_data_lake_manifest.py"],
    },
    {
        "name": "validate_data_lake_live_content_after_operator_docs_sync",
        "cwd": AI_ROOT,
        "cmd": [sys.executable, "scripts/validate_data_lake_live_content_integrity.py"],
    },
    {
        "name": "rebuild_local_release_manifest_after_operator_docs_sync",
        "cwd": AI_ROOT,
        "cmd": [sys.executable, "scripts/build_local_release_manifest.py"],
    },
    {
        "name": "validate_local_release_consistency_receipt_atomicity_regression",
        "cwd": AI_ROOT,
        "cmd": [sys.executable, "scripts/validate_local_release_consistency_receipt_atomicity_regression.py"],
    },
    {
        "name": "validate_local_release_manifest_fail_closed_consistency",
        "cwd": AI_ROOT,
        "cmd": [sys.executable, "scripts/validate_local_release_manifest_fail_closed_consistency.py"],
    },
    {
        "name": "validate_local_release_consistency_receipt_current",
        "cwd": AI_ROOT,
        "cmd": [sys.executable, "scripts/validate_local_release_consistency_receipt_current.py"],
    },
    {
        "name": "validate_local_release_consistency_receipt_current_regression",
        "cwd": AI_ROOT,
        "cmd": [sys.executable, "scripts/validate_local_release_consistency_receipt_current_regression.py"],
    },
    {
        "name": "rebuild_data_lake_manifest_after_consistency_current",
        "cwd": AI_ROOT,
        "cmd": [sys.executable, "scripts/build_data_lake_manifest.py"],
    },
    {
        "name": "validate_data_lake_live_after_consistency_current",
        "cwd": AI_ROOT,
        "cmd": [sys.executable, "scripts/validate_data_lake_live_content_integrity.py"],
    },
    {
        "name": "rebuild_local_release_after_consistency_current",
        "cwd": AI_ROOT,
        "cmd": [sys.executable, "scripts/build_local_release_manifest.py"],
    },
    {
        "name": "validate_local_release_safety_guard_links",
        "cwd": AI_ROOT,
        "cmd": [sys.executable, "scripts/validate_local_release_safety_guard_links.py"],
    },
    {
        "name": "validate_local_release_safety_guard_links_current",
        "cwd": AI_ROOT,
        "cmd": [sys.executable, "scripts/validate_local_release_safety_guard_links_current.py"],
    },
    {
        "name": "validate_local_release_safety_guard_links_current_regression",
        "cwd": AI_ROOT,
        "cmd": [sys.executable, "scripts/validate_local_release_safety_guard_links_current_regression.py"],
    },
    {
        "name": "rebuild_release_benchmark_stage25_summary_after_operator_docs_sync",
        "cwd": AI_ROOT,
        "cmd": [sys.executable, "scripts/build_release_benchmark_stage25_fail_closed_summary_20260806.py"],
    },
    {
        "name": "validate_stage25_user_authorization_receipts",
        "cwd": AI_ROOT,
        "cmd": [sys.executable, "scripts/validate_stage25_user_authorization_receipts_20260806.py"],
    },
    {
        "name": "validate_stage25_breakthrough_attempt_receipts",
        "cwd": AI_ROOT,
        "cmd": [sys.executable, "scripts/validate_stage25_breakthrough_attempt_receipts_20260806.py"],
    },
    {
        "name": "validate_stage25_unblock_operator_packets",
        "cwd": AI_ROOT,
        "cmd": [sys.executable, "scripts/validate_stage25_unblock_operator_packets_20260806.py"],
    },
    {
        "name": "validate_stage25_source_drop_manifest",
        "cwd": AI_ROOT,
        "cmd": [sys.executable, "scripts/validate_stage25_source_drop_manifest_20260806.py"],
    },
    {
        "name": "build_stage25_source_drop_inventory",
        "cwd": AI_ROOT,
        "cmd": [sys.executable, "scripts/build_stage25_source_drop_inventory_20260806.py"],
    },
    {
        "name": "validate_stage25_source_drop_inventory",
        "cwd": AI_ROOT,
        "cmd": [sys.executable, "scripts/validate_stage25_source_drop_inventory_20260806.py"],
    },
    {
        "name": "validate_stage25_source_acquisition_receipts",
        "cwd": AI_ROOT,
        "cmd": [sys.executable, "scripts/validate_stage25_source_acquisition_receipts_20260807.py"],
    },
    {
        "name": "validate_stage25_source_extraction_candidates",
        "cwd": AI_ROOT,
        "cmd": [sys.executable, "scripts/validate_stage25_source_extraction_candidates_20260807.py"],
    },
    {
        "name": "validate_stage25_source_extraction_candidate_reviewer_packet",
        "cwd": AI_ROOT,
        "cmd": [sys.executable, "scripts/validate_stage25_source_extraction_candidate_reviewer_packet_20260807.py"],
    },
    {
        "name": "validate_stage25_source_extraction_reviewer_closure_checklist",
        "cwd": AI_ROOT,
        "cmd": [sys.executable, "scripts/validate_stage25_source_extraction_reviewer_closure_checklist_20260807.py"],
    },
    {
        "name": "build_stage25_cm5_codon262_cross_read_audit",
        "cwd": AI_ROOT,
        "cmd": [str(BACKEND_PYTHON), "scripts/build_stage25_cm5_codon262_cross_read_audit_20260807.py"],
    },
    {
        "name": "validate_stage25_cm5_codon262_cross_read_audit",
        "cwd": AI_ROOT,
        "cmd": [sys.executable, "scripts/validate_stage25_cm5_codon262_cross_read_audit_20260807.py"],
    },
    {
        "name": "build_stage25_cm5_codon262_sequence_quality_evidence_audit",
        "cwd": AI_ROOT,
        "cmd": [sys.executable, "scripts/build_stage25_cm5_codon262_sequence_quality_evidence_audit_20260807.py"],
    },
    {
        "name": "validate_stage25_cm5_codon262_sequence_quality_evidence_audit",
        "cwd": AI_ROOT,
        "cmd": [sys.executable, "scripts/validate_stage25_cm5_codon262_sequence_quality_evidence_audit_20260807.py"],
    },
    {
        "name": "build_stage25_cm5_l262v_discrepancy_adjudication_packet",
        "cwd": AI_ROOT,
        "cmd": [sys.executable, "scripts/build_stage25_cm5_l262v_discrepancy_adjudication_packet_20260807.py"],
    },
    {
        "name": "validate_stage25_cm5_l262v_discrepancy_adjudication_packet",
        "cwd": AI_ROOT,
        "cmd": [sys.executable, "scripts/validate_stage25_cm5_l262v_discrepancy_adjudication_packet_20260807.py"],
    },
    {
        "name": "build_stage25_cm5_l262v_adjudication_evidence_intake",
        "cwd": AI_ROOT,
        "cmd": [sys.executable, "scripts/build_stage25_cm5_l262v_adjudication_evidence_intake_20260807.py"],
    },
    {
        "name": "validate_stage25_cm5_l262v_adjudication_evidence_intake",
        "cwd": AI_ROOT,
        "cmd": [sys.executable, "scripts/validate_stage25_cm5_l262v_adjudication_evidence_intake_20260807.py"],
    },
    {
        "name": "validate_stage25_cm5_l262v_public_source_probe_receipt",
        "cwd": AI_ROOT,
        "cmd": [sys.executable, "scripts/validate_stage25_cm5_l262v_public_source_probe_receipt_20260807.py"],
    },
    {
        "name": "build_stage25_cm5_l262v_external_evidence_request_packet",
        "cwd": AI_ROOT,
        "cmd": [sys.executable, "scripts/build_stage25_cm5_l262v_external_evidence_request_packet_20260807.py"],
    },
    {
        "name": "validate_stage25_cm5_l262v_external_evidence_request_packet",
        "cwd": AI_ROOT,
        "cmd": [sys.executable, "scripts/validate_stage25_cm5_l262v_external_evidence_request_packet_20260807.py"],
    },
    {
        "name": "validate_stage25_cm5_l262v_external_evidence_receipts",
        "cwd": AI_ROOT,
        "cmd": [sys.executable, "scripts/validate_stage25_cm5_l262v_external_evidence_receipts_20260807.py"],
    },
    {
        "name": "validate_stage25_cm5_l262v_external_evidence_reviews",
        "cwd": AI_ROOT,
        "cmd": [sys.executable, "scripts/validate_stage25_cm5_l262v_external_evidence_reviews_20260807.py"],
    },
    {
        "name": "validate_stage25_cm5_l262v_adjudication_decision_intake",
        "cwd": AI_ROOT,
        "cmd": [sys.executable, "scripts/validate_stage25_cm5_l262v_adjudication_decision_intake_20260807.py"],
    },
    {
        "name": "test_stage25_cm5_l262v_adjudication_review_binding",
        "cwd": AI_ROOT,
        "cmd": [sys.executable, "scripts/test_stage25_cm5_l262v_adjudication_review_binding_20260807.py"],
    },
    {
        "name": "test_stage25_cm5_l262v_adjudication_review_binding_tamper",
        "cwd": AI_ROOT,
        "cmd": [sys.executable, "scripts/test_stage25_cm5_l262v_adjudication_review_binding_tamper_20260807.py"],
    },
    {
        "name": "test_stage25_cm5_l262v_adjudication_evidence_path_safety",
        "cwd": AI_ROOT,
        "cmd": [sys.executable, "scripts/test_stage25_cm5_l262v_adjudication_evidence_path_safety_20260807.py"],
    },
    {
        "name": "test_stage25_cm5_l262v_adjudication_upstream_review_provenance",
        "cwd": AI_ROOT,
        "cmd": [sys.executable, "scripts/test_stage25_cm5_l262v_adjudication_upstream_review_provenance_20260807.py"],
    },
    {
        "name": "test_stage25_cm5_l262v_adjudication_upstream_packet_provenance",
        "cwd": AI_ROOT,
        "cmd": [sys.executable, "scripts/test_stage25_cm5_l262v_adjudication_upstream_packet_provenance_20260807.py"],
    },
    {
        "name": "build_stage25_cm5_l262v_external_request_message_drafts",
        "cwd": AI_ROOT,
        "cmd": [sys.executable, "scripts/build_stage25_cm5_l262v_external_request_message_drafts_20260807.py"],
    },
    {
        "name": "validate_stage25_cm5_l262v_external_request_message_drafts",
        "cwd": AI_ROOT,
        "cmd": [sys.executable, "scripts/validate_stage25_cm5_l262v_external_request_message_drafts_20260807.py"],
    },
    {
        "name": "validate_stage25_cm5_l262v_external_request_authorizations",
        "cwd": AI_ROOT,
        "cmd": [sys.executable, "scripts/validate_stage25_cm5_l262v_external_request_authorizations_20260807.py"],
    },
    {
        "name": "build_stage25_cm5_l262v_external_request_send_guard",
        "cwd": AI_ROOT,
        "cmd": [sys.executable, "scripts/build_stage25_cm5_l262v_external_request_send_guard_20260807.py"],
    },
    {
        "name": "validate_stage25_cm5_l262v_external_request_send_guard",
        "cwd": AI_ROOT,
        "cmd": [sys.executable, "scripts/validate_stage25_cm5_l262v_external_request_send_guard_20260807.py"],
    },
    {
        "name": "test_stage25_cm5_l262v_external_request_authorization_safety",
        "cwd": AI_ROOT,
        "cmd": [sys.executable, "scripts/test_stage25_cm5_l262v_external_request_authorization_safety_20260807.py"],
    },
    {
        "name": "build_stage25_source_acquisition_shortlist",
        "cwd": AI_ROOT,
        "cmd": [sys.executable, "scripts/build_stage25_source_acquisition_shortlist_20260806.py"],
    },
    {
        "name": "validate_stage25_source_acquisition_shortlist",
        "cwd": AI_ROOT,
        "cmd": [sys.executable, "scripts/validate_stage25_source_acquisition_shortlist_20260806.py"],
    },
    {
        "name": "build_stage25_literature_web_search_receipt",
        "cwd": AI_ROOT,
        "cmd": [sys.executable, "scripts/build_stage25_literature_web_search_receipt_20260806.py"],
    },
    {
        "name": "validate_stage25_literature_web_search_receipt",
        "cwd": AI_ROOT,
        "cmd": [sys.executable, "scripts/validate_stage25_literature_web_search_receipt_20260806.py"],
    },
    {
        "name": "build_stage25_source_drop_extraction_readiness_candidate",
        "cwd": AI_ROOT,
        "cmd": [sys.executable, "scripts/build_stage25_source_drop_extraction_readiness_candidate_20260806.py"],
    },
    {
        "name": "validate_stage25_source_drop_extraction_readiness_candidates",
        "cwd": AI_ROOT,
        "cmd": [sys.executable, "scripts/validate_stage25_source_drop_extraction_readiness_candidates_20260806.py"],
    },
    {
        "name": "validate_stage25_family_apply_importer_design",
        "cwd": AI_ROOT,
        "cmd": [sys.executable, "scripts/validate_stage25_family_apply_importer_design_20260806.py"],
    },
    {
        "name": "build_stage25_family_apply_transaction_plan",
        "cwd": AI_ROOT,
        "cmd": [sys.executable, "scripts/build_stage25_family_apply_transaction_plan_20260806.py"],
    },
    {
        "name": "validate_stage25_family_apply_transaction_plans",
        "cwd": AI_ROOT,
        "cmd": [sys.executable, "scripts/validate_stage25_family_apply_transaction_plans_20260806.py"],
    },
    {
        "name": "validate_stage25_foldx_provision_manifest",
        "cwd": AI_ROOT,
        "cmd": [sys.executable, "scripts/validate_stage25_foldx_provision_manifest_20260806.py"],
    },
    {
        "name": "validate_stage25_foldx_technical_smoke",
        "cwd": AI_ROOT,
        "cmd": [sys.executable, "scripts/validate_stage25_foldx_technical_smoke_20260806.py"],
    },
    {
        "name": "build_stage25_foldx_provision_manifest_candidate",
        "cwd": AI_ROOT,
        "cmd": [sys.executable, "scripts/build_stage25_foldx_provision_manifest_candidate_20260806.py"],
    },
    {
        "name": "validate_stage25_foldx_provision_manifest_candidate",
        "cwd": AI_ROOT,
        "cmd": [sys.executable, "scripts/validate_stage25_foldx_provision_manifest_candidate_20260806.py"],
    },
    {
        "name": "validate_stage25_foldx_runtime_receipt_candidate_drafts",
        "cwd": AI_ROOT,
        "cmd": [sys.executable, "scripts/validate_stage25_foldx_runtime_receipt_candidate_drafts_20260806.py"],
    },
    {
        "name": "validate_stage25_foldx_benchmark_bridge_isolation",
        "cwd": AI_ROOT,
        "cmd": [sys.executable, "scripts/validate_stage25_foldx_benchmark_bridge_isolation_20260806.py"],
    },
    {
        "name": "build_stage25_foldx_execution_plan_blocker",
        "cwd": AI_ROOT,
        "cmd": [sys.executable, "scripts/build_stage25_foldx_execution_plan_blocker_20260806.py"],
    },
    {
        "name": "validate_stage25_foldx_execution_plan_blocker",
        "cwd": AI_ROOT,
        "cmd": [sys.executable, "scripts/validate_stage25_foldx_execution_plan_blocker_20260806.py"],
    },
    {
        "name": "validate_stage25_benchmark_unblock_design",
        "cwd": AI_ROOT,
        "cmd": [sys.executable, "scripts/validate_stage25_benchmark_unblock_design_20260806.py"],
    },
    {
        "name": "build_stage25_hard_gate_formal_decision_draft_package",
        "cwd": AI_ROOT,
        "cmd": [sys.executable, "scripts/build_stage25_hard_gate_formal_decision_draft_package_20260806.py"],
    },
    {
        "name": "validate_stage25_hard_gate_formal_decision_draft_package",
        "cwd": AI_ROOT,
        "cmd": [sys.executable, "scripts/validate_stage25_hard_gate_formal_decision_draft_package_20260806.py"],
    },
    {
        "name": "validate_stage25_new_paper_extraction_templates",
        "cwd": AI_ROOT,
        "cmd": [sys.executable, "scripts/validate_stage25_new_paper_extraction_templates_20260806.py"],
    },
    {
        "name": "validate_stage25_reviewed_extraction_output_drafts",
        "cwd": AI_ROOT,
        "cmd": [sys.executable, "scripts/validate_stage25_reviewed_extraction_output_drafts_20260806.py"],
    },
    {
        "name": "validate_stage25_claim_release_consistency",
        "cwd": AI_ROOT,
        "cmd": [sys.executable, "scripts/validate_stage25_claim_release_consistency_20260806.py"],
    },
    {
        "name": "build_stage25_remaining_blocker_closure_matrix",
        "cwd": AI_ROOT,
        "cmd": [sys.executable, "scripts/build_stage25_remaining_blocker_closure_matrix_20260806.py"],
    },
    {
        "name": "validate_stage25_remaining_blocker_closure_matrix",
        "cwd": AI_ROOT,
        "cmd": [sys.executable, "scripts/validate_stage25_remaining_blocker_closure_matrix_20260806.py"],
    },
    {
        "name": "build_stage25_post_source_drop_rerun_receipt",
        "cwd": AI_ROOT,
        "cmd": [sys.executable, "scripts/build_stage25_post_source_drop_rerun_receipt_20260806.py"],
    },
    {
        "name": "validate_stage25_post_source_drop_rerun_receipt",
        "cwd": AI_ROOT,
        "cmd": [sys.executable, "scripts/validate_stage25_post_source_drop_rerun_receipt_20260806.py"],
    },
    {
        "name": "validate_stage25_post_source_drop_rerun_receipt_regression",
        "cwd": AI_ROOT,
        "cmd": [sys.executable, "scripts/validate_stage25_post_source_drop_rerun_receipt_regression_20260806.py"],
    },
    {
        "name": "validate_stage25_post_source_drop_rerun_validation_current",
        "cwd": AI_ROOT,
        "cmd": [sys.executable, "scripts/validate_stage25_post_source_drop_rerun_validation_current_20260810.py"],
    },
    {
        "name": "validate_stage25_post_source_drop_rerun_validation_current_regression",
        "cwd": AI_ROOT,
        "cmd": [sys.executable, "scripts/validate_stage25_post_source_drop_rerun_validation_current_regression_20260810.py"],
    },
    {
        "name": "validate_stage25_post_source_drop_rerun_independent_policy",
        "cwd": AI_ROOT,
        "cmd": [sys.executable, "scripts/validate_stage25_post_source_drop_rerun_independent_policy_20260810.py"],
    },
    {
        "name": "validate_stage25_post_source_drop_rerun_independent_policy_regression",
        "cwd": AI_ROOT,
        "cmd": [sys.executable, "scripts/validate_stage25_post_source_drop_rerun_independent_policy_regression_20260810.py"],
    },
    {
        "name": "validate_stage25_post_source_drop_rerun_independent_policy_current",
        "cwd": AI_ROOT,
        "cmd": [sys.executable, "scripts/validate_stage25_post_source_drop_rerun_independent_policy_current_20260810.py"],
    },
    {
        "name": "validate_stage25_post_source_drop_rerun_independent_policy_current_regression",
        "cwd": AI_ROOT,
        "cmd": [sys.executable, "scripts/validate_stage25_post_source_drop_rerun_independent_policy_current_regression_20260810.py"],
    },
    {
        "name": "build_stage25_post_source_drop_rerun_dry_run_audit",
        "cwd": AI_ROOT,
        "cmd": [sys.executable, "scripts/build_stage25_post_source_drop_rerun_dry_run_audit_20260806.py"],
    },
    {
        "name": "validate_stage25_post_source_drop_rerun_dry_run_audit",
        "cwd": AI_ROOT,
        "cmd": [sys.executable, "scripts/validate_stage25_post_source_drop_rerun_dry_run_audit_20260806.py"],
    },
    {
        "name": "validate_workstream_acceptance_decisions",
        "cwd": AI_ROOT,
        "cmd": [sys.executable, "scripts/validate_workstream_acceptance_decisions.py"],
    },
    {
        "name": "build_stage25_blocker_activation_map",
        "cwd": AI_ROOT,
        "cmd": [sys.executable, "scripts/build_stage25_blocker_activation_map_20260806.py"],
    },
    {
        "name": "validate_stage25_blocker_activation_map",
        "cwd": AI_ROOT,
        "cmd": [sys.executable, "scripts/validate_stage25_blocker_activation_map_20260806.py"],
    },
    {
        "name": "build_stage25_external_input_readiness_board",
        "cwd": AI_ROOT,
        "cmd": [sys.executable, "scripts/build_stage25_external_input_readiness_board_20260806.py"],
    },
    {
        "name": "validate_stage25_external_input_readiness_board",
        "cwd": AI_ROOT,
        "cmd": [sys.executable, "scripts/validate_stage25_external_input_readiness_board_20260806.py"],
    },
    {
        "name": "build_stage25_latest_blocker_coverage_audit",
        "cwd": AI_ROOT,
        "cmd": [sys.executable, "scripts/build_stage25_latest_blocker_coverage_audit_20260806.py"],
    },
    {
        "name": "validate_stage25_latest_blocker_coverage_audit",
        "cwd": AI_ROOT,
        "cmd": [sys.executable, "scripts/validate_stage25_latest_blocker_coverage_audit_20260806.py"],
    },
    {
        "name": "validate_stage25_remaining_blocker_cross_binding",
        "cwd": AI_ROOT,
        "cmd": [sys.executable, "scripts/validate_stage25_remaining_blocker_cross_binding.py"],
    },
    {
        "name": "validate_stage25_remaining_blocker_cross_binding_regression",
        "cwd": AI_ROOT,
        "cmd": [sys.executable, "scripts/validate_stage25_remaining_blocker_cross_binding_regression.py"],
    },
    {
        "name": "build_stage25_handoff_bundle_manifest_pre_overall",
        "cwd": AI_ROOT,
        "cmd": [sys.executable, "scripts/build_stage25_handoff_bundle_manifest_20260806.py"],
    },
    {
        "name": "validate_stage25_handoff_bundle_manifest_pre_overall",
        "cwd": AI_ROOT,
        "cmd": [sys.executable, "scripts/validate_stage25_handoff_bundle_manifest_20260806.py"],
    },
    {
        "name": "rebuild_stage25_overall_fail_closed_index_after_handoff_validation",
        "cwd": AI_ROOT,
        "cmd": [sys.executable, "scripts/build_stage25_overall_fail_closed_index_20260806.py"],
    },
    {
        "name": "rebuild_stage25_handoff_bundle_manifest_after_overall",
        "cwd": AI_ROOT,
        "cmd": [sys.executable, "scripts/build_stage25_handoff_bundle_manifest_20260806.py"],
    },
    {
        "name": "validate_stage25_handoff_bundle_manifest_after_overall",
        "cwd": AI_ROOT,
        "cmd": [sys.executable, "scripts/validate_stage25_handoff_bundle_manifest_20260806.py"],
    },
]


def canonical_json_sha256(payload: Any) -> str:
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def command_contract_sha256(commands: list[dict[str, Any]]) -> str:
    payload = [
        {
            "name": command.get("name"),
            "cwd": str(command.get("cwd")),
            "cmd": command.get("cmd"),
            "expected_returncode": command.get("expected_returncode", 0),
            "expected_stderr_contains": command.get("expected_stderr_contains"),
            "json_stdout": bool(command.get("json_stdout")),
            "expected_proposal_count": command.get("expected_proposal_count"),
        }
        for command in commands
    ]
    return canonical_json_sha256({"version": COMMAND_CONTRACT_VERSION, "commands": payload})


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def fsync_directory(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def write_json_atomic(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    encoded = (json.dumps(payload, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    descriptor, temp_name = tempfile.mkstemp(prefix=f".{path.name}.receipt-", dir=path.parent)
    temp_path = Path(temp_name)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(encoded)
            handle.flush()
            os.fsync(handle.fileno())
        if path.exists():
            os.chmod(temp_path, path.stat().st_mode)
        os.replace(temp_path, path)
        fsync_directory(path.parent)
    finally:
        if temp_path.exists():
            temp_path.unlink()


def run_command(command: dict[str, Any]) -> dict[str, Any]:
    process = subprocess.run(
        command["cmd"],
        cwd=str(command["cwd"]),
        text=True,
        capture_output=True,
        check=False,
    )
    expected_returncode = command.get("expected_returncode", 0)
    success = process.returncode == expected_returncode
    if command.get("expected_stderr_contains"):
        success = success and str(command["expected_stderr_contains"]) in process.stderr
    return {
        "name": command["name"],
        "cwd": str(command["cwd"]),
        "cmd": command["cmd"],
        "returncode": process.returncode,
        "expected_returncode": expected_returncode,
        "stdout": process.stdout.strip(),
        "stderr": process.stderr.strip(),
        "success": success,
    }


def load_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return data


def parse_json_stdout(result: dict[str, Any]) -> dict[str, Any]:
    try:
        payload = json.loads(str(result.get("stdout") or ""))
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def recover_deferred_bootstrap(command_results: list[dict[str, Any]]) -> bool:
    if os.environ.get("KWB_DEFER_SAFE_PIPELINE_TERMINAL") != "1":
        return False
    by_name = {str(result.get("name")): result for result in command_results}
    initial = by_name.get(DEFERRED_BOOTSTRAP_INITIAL)
    final = by_name.get(DEFERRED_BOOTSTRAP_FINAL)
    if not initial or not final or initial.get("success") is True or final.get("success") is not True:
        return False
    initial_payload = parse_json_stdout(initial)
    final_payload = parse_json_stdout(final)
    if (
        initial_payload.get("summary_valid") is not False
        or not isinstance(initial_payload.get("failure_count"), int)
        or initial_payload.get("failure_count") <= 0
        or final_payload.get("summary_valid") is not True
        or final_payload.get("failure_count") != 0
    ):
        return False
    initial["success"] = True
    initial["deferred_bootstrap_recovered"] = True
    initial["deferred_bootstrap_recovered_by"] = DEFERRED_BOOTSTRAP_FINAL
    return True


def build_report() -> dict[str, Any]:
    command_results = [run_command(command) for command in COMMANDS]
    deferred_bootstrap_recovered = recover_deferred_bootstrap(command_results)
    failures = [
        {
            "check": "command_success",
            "command": result["name"],
            "returncode": result["returncode"],
            "stderr": result["stderr"],
        }
        for result in command_results
        if not result["success"]
    ]

    command_by_name = {result["name"]: result for result in command_results}
    dry_run_summaries = []
    for family in ("xylanase", "lipase", "amylase"):
        command_name = f"new_paper_dry_run_{family}"
        result = command_by_name.get(command_name) or {}
        if not result.get("success"):
            continue
        try:
            payload = json.loads(str(result.get("stdout") or "{}"))
        except json.JSONDecodeError as exc:
            failures.append({"check": f"{command_name}_json_stdout", "observed": str(exc), "expected": "JSON object"})
            continue
        proposals = payload.get("proposals") or []
        family_failures = []
        if payload.get("candidate_count") != 2:
            family_failures.append({"field": "candidate_count", "observed": payload.get("candidate_count"), "expected": 2})
        if payload.get("proposal_count") != 2:
            family_failures.append({"field": "proposal_count", "observed": payload.get("proposal_count"), "expected": 2})
        if payload.get("errors") != []:
            family_failures.append({"field": "errors", "observed": payload.get("errors"), "expected": []})
        if payload.get("external_sqlite_mutated") is not False:
            family_failures.append({"field": "external_sqlite_mutated", "observed": payload.get("external_sqlite_mutated"), "expected": False})
        if payload.get("export_safe_released") is not False:
            family_failures.append({"field": "export_safe_released", "observed": payload.get("export_safe_released"), "expected": False})
        for index, proposal in enumerate(proposals, start=1):
            for flag in ("ready_for_family_importer", "family_importer_gate_passed", "export_safe", "apply_allowed_now"):
                if proposal.get(flag) is not False:
                    family_failures.append({"proposal_index": index, "field": flag, "observed": proposal.get(flag), "expected": False})
            if proposal.get("release_status") != "not_released":
                family_failures.append({"proposal_index": index, "field": "release_status", "observed": proposal.get("release_status"), "expected": "not_released"})
        if family_failures:
            failures.append({"check": f"{command_name}_fail_closed_payload", "failures": family_failures})
        dry_run_summaries.append({
            "family": family,
            "candidate_count": payload.get("candidate_count"),
            "proposal_count": payload.get("proposal_count"),
            "ready_count": sum(1 for proposal in proposals if proposal.get("ready_for_family_importer") is True),
            "export_safe_count": sum(1 for proposal in proposals if proposal.get("export_safe") is True),
        })

    index_path = AI_ROOT / "reports" / "stage25_overall_fail_closed_index_20260806.json"
    index: dict[str, Any] = {}
    if index_path.exists():
        index = load_json(index_path)
    else:
        failures.append({"check": "overall_index_exists", "observed": "missing", "expected": str(index_path)})

    for flag in (
        "external_sqlite_mutated",
        "apply_executed",
        "allow_apply",
        "export_safe_released",
        "release_ready",
        "safe_for_model_claim",
        "benchmark_ready_for_model_claim",
    ):
        if flag in index and index.get(flag) is not False:
            failures.append({"check": f"overall_index_{flag}_false", "observed": index.get(flag), "expected": False})
    if index and index.get("formal_decision_rows_written") != 0:
        failures.append({"check": "overall_index_formal_decision_rows_written_zero", "observed": index.get("formal_decision_rows_written"), "expected": 0})
    if index and index.get("index_valid") is not True:
        failures.append({"check": "overall_index_valid", "observed": index.get("index_valid"), "expected": True})

    return {
        "schema_version": 1,
        "created_at": "2026-08-06",
        "mode": "read_only_stage25_fail_closed_validation_run",
        "stage": 25,
        "run_valid": not failures,
        "runner_script_path": str(Path(__file__).resolve()),
        "runner_script_sha256": sha256(Path(__file__).resolve()),
        "command_contract_version": COMMAND_CONTRACT_VERSION,
        "command_contract_sha256": command_contract_sha256(COMMANDS),
        "failure_count": len(failures),
        "failures": failures,
        "command_count": len(command_results),
        "commands": command_results,
        "deferred_bootstrap_recovered": deferred_bootstrap_recovered,
        "dry_run_summaries": dry_run_summaries,
        "overall_index": str(index_path),
        "run_lock_path": str(LOCK_PATH),
        "output_path": str(DEFAULT_OUTPUT),
        "lock_acquired": True,
        "receipt_atomic_commit": True,
        "external_sqlite_mutated": False,
        "apply_executed": False,
        "allow_apply": False,
        "export_safe_released": False,
        "formal_decision_rows_written": 0,
        "release_ready": False,
        "safe_for_model_claim": False,
        "benchmark_ready_for_model_claim": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Stage 25 fail-closed validation chain")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    LOCK_PATH.parent.mkdir(parents=True, exist_ok=True)
    with LOCK_PATH.open("w", encoding="utf-8") as lock_handle:
        fcntl.flock(lock_handle, fcntl.LOCK_EX)
        lock_handle.seek(0)
        lock_handle.truncate()
        lock_handle.write(f"pid={os.getpid()}\n")
        lock_handle.flush()
        report = build_report()
        report["output_path"] = str(args.output.resolve())
        report["run_lock_path"] = str(args.lock_path.resolve()) if hasattr(args, "lock_path") else str(LOCK_PATH.resolve())
        try:
            write_json_atomic(args.output, report)
        except Exception as exc:
            report["receipt_atomic_commit"] = False
            report["receipt_commit_error"] = f"{type(exc).__name__}:{exc}"
            print(json.dumps({"output": str(args.output), "run_valid": False, "failure_count": 1, "command_count": report.get("command_count")}, ensure_ascii=False, sort_keys=True))
            return 1
    current_validator = AI_ROOT / "scripts" / "validate_stage25_fail_closed_validation_current_receipt.py"
    current_regression = AI_ROOT / "scripts" / "validate_stage25_fail_closed_validation_current_receipt_regression.py"
    current_process = subprocess.run([sys.executable, str(current_validator)], cwd=AI_ROOT, text=True, capture_output=True, check=False)
    regression_process = subprocess.run([sys.executable, str(current_regression)], cwd=AI_ROOT, text=True, capture_output=True, check=False)
    proof_valid = current_process.returncode == 0 and regression_process.returncode == 0
    print(json.dumps({"output": str(args.output), "run_valid": report["run_valid"] and proof_valid, "failure_count": report["failure_count"], "command_count": report["command_count"], "current_receipt_valid": current_process.returncode == 0, "current_regression_valid": regression_process.returncode == 0}, ensure_ascii=False, sort_keys=True))
    return 0 if report["run_valid"] and proof_valid else 1


if __name__ == "__main__":
    raise SystemExit(main())
