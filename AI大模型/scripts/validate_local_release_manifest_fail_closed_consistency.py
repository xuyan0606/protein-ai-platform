#!/usr/bin/env python3
"""Validate local release manifest remains fail-closed and summary-consistent."""

from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import os
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any, Optional

try:
    from data_lake_release_input_contract import (
        CONTRACT_VERSION,
        RELEASE_INPUT_EXCLUDED_PATHS,
        build_release_input_contract,
    )
except ModuleNotFoundError:
    from scripts.data_lake_release_input_contract import (
        CONTRACT_VERSION,
        RELEASE_INPUT_EXCLUDED_PATHS,
        build_release_input_contract,
    )

try:
    from validate_data_lake_release_input_contract_policy import (
        EXPECTED_EXCLUDED_PATHS as POLICY_EXPECTED_EXCLUDED_PATHS,
        EXPECTED_TEST_VECTOR_SHA256 as POLICY_EXPECTED_TEST_VECTOR_SHA256,
        EXPECTED_VERSION as POLICY_EXPECTED_VERSION,
    )
except ModuleNotFoundError:
    from scripts.validate_data_lake_release_input_contract_policy import (
        EXPECTED_EXCLUDED_PATHS as POLICY_EXPECTED_EXCLUDED_PATHS,
        EXPECTED_TEST_VECTOR_SHA256 as POLICY_EXPECTED_TEST_VECTOR_SHA256,
        EXPECTED_VERSION as POLICY_EXPECTED_VERSION,
    )

try:
    from validate_stage25_operator_docs_sync_contract_policy import (
        EXPECTED_CONTRACT_SHA256 as SYNC_POLICY_EXPECTED_CONTRACT_SHA256,
        EXPECTED_LOCK_PATH_ID as SYNC_POLICY_EXPECTED_LOCK_PATH_ID,
        EXPECTED_OUTPUT_PATH_ID as SYNC_POLICY_EXPECTED_OUTPUT_PATH_ID,
        EXPECTED_SEMANTIC_PROJECTION_SPECS as SYNC_POLICY_EXPECTED_SEMANTIC_PROJECTION_SPECS,
        EXPECTED_SEMANTIC_PROJECTION_TEST_VECTOR_SHA256 as SYNC_POLICY_EXPECTED_SEMANTIC_PROJECTION_TEST_VECTOR_SHA256,
        EXPECTED_SEMANTIC_PROJECTION_VERSION as SYNC_POLICY_EXPECTED_SEMANTIC_PROJECTION_VERSION,
        EXPECTED_SLOTS as SYNC_POLICY_EXPECTED_SLOTS,
        EXPECTED_TARGET_SPECS as SYNC_POLICY_EXPECTED_TARGET_SPECS,
        EXPECTED_UPSTREAM_INPUT_SPECS as SYNC_POLICY_EXPECTED_UPSTREAM_INPUT_SPECS,
        EXPECTED_VERSION as SYNC_POLICY_EXPECTED_VERSION,
    )

except ModuleNotFoundError:
    from scripts.validate_stage25_operator_docs_sync_contract_policy import (
        EXPECTED_CONTRACT_SHA256 as SYNC_POLICY_EXPECTED_CONTRACT_SHA256,
        EXPECTED_LOCK_PATH_ID as SYNC_POLICY_EXPECTED_LOCK_PATH_ID,
        EXPECTED_OUTPUT_PATH_ID as SYNC_POLICY_EXPECTED_OUTPUT_PATH_ID,
        EXPECTED_SEMANTIC_PROJECTION_SPECS as SYNC_POLICY_EXPECTED_SEMANTIC_PROJECTION_SPECS,
        EXPECTED_SEMANTIC_PROJECTION_TEST_VECTOR_SHA256 as SYNC_POLICY_EXPECTED_SEMANTIC_PROJECTION_TEST_VECTOR_SHA256,
        EXPECTED_SEMANTIC_PROJECTION_VERSION as SYNC_POLICY_EXPECTED_SEMANTIC_PROJECTION_VERSION,
        EXPECTED_SLOTS as SYNC_POLICY_EXPECTED_SLOTS,
        EXPECTED_TARGET_SPECS as SYNC_POLICY_EXPECTED_TARGET_SPECS,
        EXPECTED_UPSTREAM_INPUT_SPECS as SYNC_POLICY_EXPECTED_UPSTREAM_INPUT_SPECS,
        EXPECTED_VERSION as SYNC_POLICY_EXPECTED_VERSION,
    )

try:
    from validate_local_release_safety_guard_links import REQUIRED_GUARD_LINKS
except ModuleNotFoundError:
    from scripts.validate_local_release_safety_guard_links import REQUIRED_GUARD_LINKS

try:
    from local_release_consistency_receipt_contract import (
        CONTRACT_VERSION as CONSISTENCY_SEMANTIC_CONTRACT_VERSION,
        build_semantic_inputs,
        test_vector_sha256 as consistency_semantic_test_vector_sha256,
    )
except ModuleNotFoundError:
    from scripts.local_release_consistency_receipt_contract import (
        CONTRACT_VERSION as CONSISTENCY_SEMANTIC_CONTRACT_VERSION,
        build_semantic_inputs,
        test_vector_sha256 as consistency_semantic_test_vector_sha256,
    )

try:
    from validate_local_release_consistency_semantic_policy import (
        EXPECTED_CANONICAL_POLICY_SHA256,
        EXPECTED_CONTRACT_POLICY_FIELDS,
        EXPECTED_DATA_LAKE_SEMANTIC_EXCLUDED_PATHS,
        EXPECTED_INPUT_ROLES,
        EXPECTED_LIVE_FIELDS,
        EXPECTED_LIVE_NORMALIZED_FIELDS,
        EXPECTED_RELEASE_SUMMARY_EXCLUDED_FIELDS,
        EXPECTED_RELEASE_SUMMARY_NORMALIZED_FIELDS,
        EXPECTED_SHARED_CONTRACT_TEST_VECTOR_SHA256,
        EXPECTED_TEST_VECTOR_SHA256,
        EXPECTED_VERSION as SEMANTIC_POLICY_EXPECTED_VERSION,
    )
except ModuleNotFoundError:
    from scripts.validate_local_release_consistency_semantic_policy import (
        EXPECTED_CANONICAL_POLICY_SHA256,
        EXPECTED_CONTRACT_POLICY_FIELDS,
        EXPECTED_DATA_LAKE_SEMANTIC_EXCLUDED_PATHS,
        EXPECTED_INPUT_ROLES,
        EXPECTED_LIVE_FIELDS,
        EXPECTED_LIVE_NORMALIZED_FIELDS,
        EXPECTED_RELEASE_SUMMARY_EXCLUDED_FIELDS,
        EXPECTED_RELEASE_SUMMARY_NORMALIZED_FIELDS,
        EXPECTED_SHARED_CONTRACT_TEST_VECTOR_SHA256,
        EXPECTED_TEST_VECTOR_SHA256,
        EXPECTED_VERSION as SEMANTIC_POLICY_EXPECTED_VERSION,
    )


AI_ROOT = Path(__file__).resolve().parents[1]
RELEASE = AI_ROOT / "reports" / "local_release_manifest.json"
DATA_LAKE = AI_ROOT / "reports" / "data_lake_manifest.json"
CLAIM_MATRIX = AI_ROOT / "reports" / "claim_readiness_matrix.json"
CLAIM_POLICY_ANCHOR = AI_ROOT / "reports" / "claim_readiness_policy_anchor_validation_report.json"
CLAIM_POLICY_ANCHOR_REGRESSION = AI_ROOT / "reports" / "claim_readiness_policy_anchor_regression_report.json"
CLAIM_PROMOTION = AI_ROOT / "reports" / "claim_promotion_decision_validation_report.json"
CLAIM_MATRIX_POLICY = AI_ROOT / "reports" / "claim_readiness_matrix_fail_closed_policy_validation_report.json"
CLAIM_MATRIX_POLICY_CURRENT = AI_ROOT / "reports" / "claim_readiness_matrix_fail_closed_policy_current_validation_report.json"
CLAIM_MATRIX_POLICY_CURRENT_REGRESSION = AI_ROOT / "reports" / "claim_readiness_matrix_fail_closed_policy_current_regression_report.json"
HUMAN_DECISION_PENDING_INDEX = AI_ROOT / "reports" / "human_decision_pending_row_index_20260806.json"
HUMAN_BACKLOG = AI_ROOT / "reports" / "human_decision_backlog_report.json"
HUMAN_BACKLOG_VALIDATION = AI_ROOT / "reports" / "human_decision_backlog_fail_closed_consistency_validation_report.json"
REVIEW_DRAFT_BOUNDARY = AI_ROOT / "reports" / "review_draft_formal_boundary_validation_report.json"
MODEL_CLAIM_CONSISTENCY = AI_ROOT / "reports" / "model_claim_fail_closed_consistency_report.json"
PROMOTION_BOARD = AI_ROOT / "reports" / "ready_to_verify_promotion_board.json"
PROMOTION_VALIDATION = AI_ROOT / "reports" / "ready_to_verify_promotion_validation_report.json"
PROMOTION_REGRESSION = AI_ROOT / "reports" / "ready_to_verify_promotion_safety_regression_report.json"
LIVE_CONTENT_INTEGRITY = AI_ROOT / "reports" / "data_lake_live_content_integrity_validation_report.json"
CONTRACT_POLICY = AI_ROOT / "reports" / "data_lake_release_input_contract_policy_validation_report.json"
SEMANTIC_POLICY = AI_ROOT / "reports" / "local_release_consistency_semantic_policy_validation_report.json"
SEMANTIC_POLICY_SCRIPT = AI_ROOT / "scripts" / "validate_local_release_consistency_semantic_policy.py"
SEMANTIC_POLICY_LOCK = AI_ROOT / "reports" / ".local_release_consistency_semantic_policy.lock"
SEMANTIC_POLICY_CURRENT = AI_ROOT / "reports" / "local_release_consistency_semantic_policy_current_validation_report.json"
SEMANTIC_POLICY_CURRENT_REGRESSION = AI_ROOT / "reports" / "local_release_consistency_semantic_policy_current_regression_report.json"
SEMANTIC_POLICY_CURRENT_SCRIPT = AI_ROOT / "scripts" / "validate_local_release_consistency_semantic_policy_current.py"
SEMANTIC_POLICY_CURRENT_REGRESSION_SCRIPT = AI_ROOT / "scripts" / "validate_local_release_consistency_semantic_policy_current_regression.py"
SEMANTIC_POLICY_ATOMICITY_REGRESSION = AI_ROOT / "reports" / "local_release_consistency_semantic_policy_atomicity_regression_report.json"
SEMANTIC_POLICY_ATOMICITY_REGRESSION_SCRIPT = AI_ROOT / "scripts" / "validate_local_release_consistency_semantic_policy_atomicity_regression.py"
RELEASE_GUARD_ORDER = AI_ROOT / "reports" / "enzyme_agent_controlled_release_guard_order_validation_report.json"
RELEASE_GUARD_ORDER_REGRESSION = AI_ROOT / "reports" / "enzyme_agent_controlled_release_guard_order_regression_report.json"
RELEASE_GUARD_ORDER_CURRENT = AI_ROOT / "reports" / "enzyme_agent_controlled_release_guard_order_current_validation_report.json"
RELEASE_GUARD_ORDER_CURRENT_REGRESSION = AI_ROOT / "reports" / "enzyme_agent_controlled_release_guard_order_current_regression_report.json"
RELEASE_GUARD_ORDER_SCRIPT = AI_ROOT / "scripts" / "validate_enzyme_agent_controlled_release_guard_order.py"
RELEASE_GUARD_ORDER_REGRESSION_SCRIPT = AI_ROOT / "scripts" / "validate_enzyme_agent_controlled_release_guard_order_regression.py"
RELEASE_GUARD_ORDER_CURRENT_SCRIPT = AI_ROOT / "scripts" / "validate_enzyme_agent_controlled_release_guard_order_current.py"
RELEASE_GUARD_ORDER_CURRENT_REGRESSION_SCRIPT = AI_ROOT / "scripts" / "validate_enzyme_agent_controlled_release_guard_order_current_regression.py"
RELEASE_GUARD_ORDER_WAVE_SCRIPT = AI_ROOT / "scripts" / "run_enzyme_agent_controlled_execution_wave.py"
RELEASE_GUARD_ORDER_ATOMICITY_REGRESSION = AI_ROOT / "reports" / "enzyme_agent_controlled_release_guard_order_atomicity_regression_report.json"
RELEASE_GUARD_ORDER_ATOMICITY_REGRESSION_SCRIPT = AI_ROOT / "scripts" / "validate_enzyme_agent_controlled_release_guard_order_atomicity_regression.py"
EXECUTION_WAVE_PAIR_ATOMICITY_REGRESSION = AI_ROOT / "reports" / "enzyme_agent_controlled_execution_wave_pair_atomicity_regression_report.json"
EXECUTION_WAVE_PAIR_ATOMICITY_REGRESSION_SCRIPT = AI_ROOT / "scripts" / "validate_enzyme_agent_controlled_execution_wave_pair_atomicity_regression.py"
EXECUTION_RECEIPT_PROOF_CURRENT = AI_ROOT / "reports" / "enzyme_agent_execution_receipt_proof_current_validation_report.json"
EXECUTION_RECEIPT_PROOF_CURRENT_REGRESSION = AI_ROOT / "reports" / "enzyme_agent_execution_receipt_proof_current_regression_report.json"
CONTRACT_MODULE = AI_ROOT / "scripts" / "data_lake_release_input_contract.py"
SYNC_RECEIPT = AI_ROOT / "reports" / "stage25_operator_docs_dynamic_status_sync_report.json"
SYNC_MARKER_REGRESSION = AI_ROOT / "reports" / "stage25_operator_docs_dynamic_status_sync_regression_report.json"
SYNC_MARKER_REGRESSION_CURRENT = AI_ROOT / "reports" / "stage25_operator_docs_dynamic_status_sync_regression_current_validation_report.json"
SYNC_MARKER_REGRESSION_CURRENT_REGRESSION = AI_ROOT / "reports" / "stage25_operator_docs_dynamic_status_sync_regression_current_regression_report.json"
SYNC_MARKER_REGRESSION_ATOMICITY = AI_ROOT / "reports" / "stage25_operator_docs_dynamic_status_sync_regression_atomicity_regression_report.json"
SYNC_MARKER_REGRESSION_SCRIPT = AI_ROOT / "scripts" / "validate_stage25_operator_docs_dynamic_status_sync_regression.py"
SYNC_MARKER_REGRESSION_CURRENT_SCRIPT = AI_ROOT / "scripts" / "validate_stage25_operator_docs_dynamic_status_sync_regression_current.py"
SYNC_MARKER_REGRESSION_CURRENT_REGRESSION_SCRIPT = AI_ROOT / "scripts" / "validate_stage25_operator_docs_dynamic_status_sync_regression_current_regression.py"
SYNC_MARKER_REGRESSION_ATOMICITY_SCRIPT = AI_ROOT / "scripts" / "validate_stage25_operator_docs_dynamic_status_sync_regression_atomicity_regression.py"
SYNC_MARKER_REGRESSION_PROOF_IO = AI_ROOT / "scripts" / "stage25_operator_docs_sync_regression_proof_io.py"
SYNC_MARKER_REGRESSION_LOCK = AI_ROOT / "reports" / ".stage25_operator_docs_sync_regression_proof.lock"
SYNC_POLICY = AI_ROOT / "reports" / "stage25_operator_docs_sync_contract_policy_validation_report.json"
SYNC_POLICY_REGRESSION = AI_ROOT / "reports" / "stage25_operator_docs_sync_contract_policy_regression_report.json"
SYNC_CURRENT = AI_ROOT / "reports" / "stage25_operator_docs_sync_current_receipt_validation_report.json"
SYNC_CURRENT_REGRESSION = AI_ROOT / "reports" / "stage25_operator_docs_sync_current_receipt_regression_report.json"
SYNC_TERMINAL_REGRESSION = AI_ROOT / "reports" / "stage25_operator_docs_sync_terminal_recovery_regression_report.json"
SAFE_PIPELINE_RECEIPT = AI_ROOT / "reports" / "safe_training_pipeline_run.json"
SAFE_PIPELINE_CURRENT = AI_ROOT / "reports" / "safe_training_pipeline_current_receipt_validation_report.json"
SAFE_PIPELINE_CURRENT_REGRESSION = AI_ROOT / "reports" / "safe_training_pipeline_current_receipt_regression_report.json"
TERMINAL_DEFER_MODE_REGRESSION = AI_ROOT / "reports" / "local_release_terminal_defer_mode_regression_report.json"
STAGE25_CURRENT_RECEIPT = AI_ROOT / "reports" / "stage25_fail_closed_validation_current_receipt_validation_report.json"
STAGE25_CURRENT_REGRESSION = AI_ROOT / "reports" / "stage25_fail_closed_validation_current_receipt_regression_report.json"
POST_SOURCE_RECEIPT_VALIDATION = AI_ROOT / "reports" / "stage25_post_source_drop_rerun_receipt_validation_20260806.json"
POST_SOURCE_RECEIPT_REGRESSION = AI_ROOT / "reports" / "stage25_post_source_drop_rerun_receipt_regression_20260806.json"
POST_SOURCE_RECEIPT = AI_ROOT / "reports" / "stage25_post_source_drop_rerun_receipt_20260806.json"
POST_SOURCE_VALIDATOR = AI_ROOT / "scripts" / "validate_stage25_post_source_drop_rerun_receipt_20260806.py"
POST_SOURCE_VALIDATION_CURRENT = AI_ROOT / "reports" / "stage25_post_source_drop_rerun_validation_current_20260810.json"
POST_SOURCE_VALIDATION_CURRENT_VALIDATOR = AI_ROOT / "scripts" / "validate_stage25_post_source_drop_rerun_validation_current_20260810.py"
POST_SOURCE_VALIDATION_CURRENT_REGRESSION = AI_ROOT / "reports" / "stage25_post_source_drop_rerun_validation_current_regression_20260810.json"
POST_SOURCE_VALIDATION_CURRENT_REGRESSION_SCRIPT = AI_ROOT / "scripts" / "validate_stage25_post_source_drop_rerun_validation_current_regression_20260810.py"
POST_SOURCE_INDEPENDENT_POLICY = AI_ROOT / "reports" / "stage25_post_source_drop_rerun_independent_policy_validation_20260810.json"
POST_SOURCE_INDEPENDENT_POLICY_SCRIPT = AI_ROOT / "scripts" / "validate_stage25_post_source_drop_rerun_independent_policy_20260810.py"
POST_SOURCE_INDEPENDENT_POLICY_REGRESSION = AI_ROOT / "reports" / "stage25_post_source_drop_rerun_independent_policy_regression_20260810.json"
POST_SOURCE_INDEPENDENT_POLICY_REGRESSION_SCRIPT = AI_ROOT / "scripts" / "validate_stage25_post_source_drop_rerun_independent_policy_regression_20260810.py"
POST_SOURCE_INDEPENDENT_POLICY_CURRENT = AI_ROOT / "reports" / "stage25_post_source_drop_rerun_independent_policy_current_20260810.json"
POST_SOURCE_INDEPENDENT_POLICY_CURRENT_VALIDATOR = AI_ROOT / "scripts" / "validate_stage25_post_source_drop_rerun_independent_policy_current_20260810.py"
POST_SOURCE_INDEPENDENT_POLICY_CURRENT_REGRESSION = AI_ROOT / "reports" / "stage25_post_source_drop_rerun_independent_policy_current_regression_20260810.json"
POST_SOURCE_INDEPENDENT_POLICY_CURRENT_REGRESSION_SCRIPT = AI_ROOT / "scripts" / "validate_stage25_post_source_drop_rerun_independent_policy_current_regression_20260810.py"
CONSISTENCY_ATOMICITY_REGRESSION = AI_ROOT / "reports" / "local_release_consistency_receipt_atomicity_regression_report.json"
CONSISTENCY_ATOMICITY_REGRESSION_SCRIPT = AI_ROOT / "scripts" / "validate_local_release_consistency_receipt_atomicity_regression.py"
CONSISTENCY_CURRENT = AI_ROOT / "reports" / "local_release_consistency_receipt_current_validation_report.json"
CONSISTENCY_CURRENT_VALIDATOR = AI_ROOT / "scripts" / "validate_local_release_consistency_receipt_current.py"
CONSISTENCY_CURRENT_REGRESSION = AI_ROOT / "reports" / "local_release_consistency_receipt_current_regression_report.json"
CONSISTENCY_CURRENT_REGRESSION_SCRIPT = AI_ROOT / "scripts" / "validate_local_release_consistency_receipt_current_regression.py"
SAFETY_GUARD_ATOMICITY_REGRESSION = AI_ROOT / "reports" / "local_release_safety_guard_links_atomicity_regression_report.json"
SAFETY_GUARD_ATOMICITY_REGRESSION_SCRIPT = AI_ROOT / "scripts" / "validate_local_release_safety_guard_links_atomicity_regression.py"
SAFETY_GUARD_CURRENT = AI_ROOT / "reports" / "local_release_safety_guard_links_current_validation_report.json"
SAFETY_GUARD_CURRENT_SCRIPT = AI_ROOT / "scripts" / "validate_local_release_safety_guard_links_current.py"
SAFETY_GUARD_CURRENT_REGRESSION = AI_ROOT / "reports" / "local_release_safety_guard_links_current_regression_report.json"
SAFETY_GUARD_CURRENT_REGRESSION_SCRIPT = AI_ROOT / "scripts" / "validate_local_release_safety_guard_links_current_regression.py"
SAFETY_GUARD_CURRENT_REGRESSION_ATOMICITY = AI_ROOT / "reports" / "local_release_safety_guard_links_current_regression_atomicity_regression_report.json"
SAFETY_GUARD_CURRENT_REGRESSION_ATOMICITY_SCRIPT = AI_ROOT / "scripts" / "validate_local_release_safety_guard_links_current_regression_atomicity_regression.py"
POST_SOURCE_LOCK = AI_ROOT / "reports" / ".stage25_post_source_drop_rerun_receipt.lock"
SAFE_PIPELINE_RUNNER = AI_ROOT / "scripts" / "run_safe_training_pipeline.py"
SYNC_CONTRACT_MODULE = AI_ROOT / "scripts" / "stage25_operator_docs_sync_contract.py"
NEXT_OPERATOR_DOC = AI_ROOT / "reports" / "next_operator_packet_20260806.md"
DAILY_OPERATOR_DOC = AI_ROOT.parent / "docs" / "manuals" / "2026-08-06-daily-report.md"
OUT = AI_ROOT / "reports" / "local_release_manifest_fail_closed_consistency_validation_report.json"
LOCK_PATH = AI_ROOT / "reports" / ".local_release_manifest_fail_closed_consistency.lock"
SEMANTIC_CONTRACT_MODULE = AI_ROOT / "scripts" / "local_release_consistency_receipt_contract.py"
MIN_EXPECTED_ARTIFACT_COUNT = 1582

REQUIRED_SUCCESS_SUMMARY_FLAGS = {
    "claim_promotion_decision_validation_success",
    "claim_promotion_template_matches_expected_contract",
    "claim_policy_anchor_success",
    "claim_policy_anchor_regression_success",
    "claim_matrix_fail_closed_policy_success",
    "claim_matrix_source_parity_success",
    "claim_matrix_policy_current_success",
    "claim_matrix_policy_current_regression_success",
    "human_decision_backlog_fail_closed_consistency_success",
    "review_draft_formal_boundary_success",
    "no_review_draft_training_leakage_success",
    "draft_namespace_isolation_success",
    "no_unreviewed_positive_gate_flags_success",
    "report_positive_claim_gate_quarantine_success",
    "model_claim_fail_closed_consistency_success",
    "top_tier_model_ready_receipt_validation_success",
    "operator_work_receipt_manifest_consistency_success",
    "human_decision_control_plane_validation_success",
    "ready_to_verify_promotion_validation_success",
    "ready_to_verify_promotion_regression_success",
    "local_release_high_risk_summary_regression_success",
    "local_release_high_risk_coverage_regression_success",
    "data_lake_volatile_exemption_regression_success",
    "local_release_live_integrity_binding_regression_success",
    "release_input_contract_policy_success",
    "release_input_contract_policy_regression_success",
    "local_release_contract_policy_binding_regression_success",
    "stage25_operator_docs_dynamic_sync_success",
    "stage25_operator_docs_sync_contract_policy_success",
    "stage25_operator_docs_sync_contract_policy_regression_success",
    "stage25_operator_docs_sync_current_receipt_success",
    "safe_training_pipeline_receipt_atomicity_regression_success",
    "stage25_fail_closed_validation_current_receipt_validation_success",
    "stage25_fail_closed_validation_current_receipt_regression_success",
    "stage25_post_source_drop_rerun_receipt_validation_success",
    "stage25_post_source_drop_rerun_receipt_regression_success",
    "stage25_post_source_drop_rerun_validation_current_success",
    "stage25_post_source_drop_rerun_validation_current_regression_success",
    "stage25_post_source_drop_rerun_independent_policy_success",
    "stage25_post_source_drop_rerun_independent_policy_regression_success",
    "stage25_post_source_drop_rerun_independent_policy_current_success",
    "stage25_post_source_drop_rerun_independent_policy_current_regression_success",
    "local_release_terminal_defer_mode_regression_success",
    "local_release_consistency_receipt_atomicity_regression_success",
    "local_release_consistency_semantic_policy_success",
    "local_release_consistency_semantic_policy_regression_success",
    "local_release_consistency_semantic_policy_current_success",
    "local_release_consistency_semantic_policy_current_regression_success",
    "local_release_consistency_semantic_policy_atomicity_regression_success",
    "enzyme_agent_release_guard_order_success",
    "enzyme_agent_release_guard_order_regression_success",
    "enzyme_agent_release_guard_order_current_success",
    "enzyme_agent_release_guard_order_current_regression_success",
    "enzyme_agent_release_guard_order_atomicity_regression_success",
    "enzyme_agent_execution_wave_pair_atomicity_regression_success",
    "enzyme_agent_execution_receipt_proof_current_success",
    "enzyme_agent_execution_receipt_proof_current_regression_success",
    "local_release_safety_guard_links_atomicity_regression_success",
    "local_release_safety_guard_links_current_success",
    "local_release_safety_guard_links_current_regression_success",
    "local_release_safety_guard_links_current_regression_atomicity_regression_success",
    "p479_customer_delivery_readiness_gap_audit_validation_success",
    "p631_ddg_physical_smoke_harness_boundary_validation_success",
    "p632_ddg_proxy_physics_claim_boundary_validation_success",
    "p633_execution_receipt_freshness_boundary_validation_success",
    "p634_parallel_hard_gate_execution_boundary_validation_success",
    "p635_ddg_backend_failure_boundary_validation_success",
    "p636_human_review_closeout_current_boundary_validation_success",
    "p637_operator_work_receipt_manifest_current_boundary_validation_success",
    "p638_top_tier_ready_to_verify_current_boundary_validation_success",
    "p639_non_human_ready_to_verify_current_boundary_validation_success",
    "p640_ready_to_verify_promotion_current_boundary_validation_success",
}

REQUIRED_ZERO_SUMMARY_FIELDS = {
    "claim_promotion_decision_validation_failures",
    "claim_promotion_decision_rows",
    "claim_promotion_approved_rows",
    "claim_promotion_validation_failures",
    "claim_policy_anchor_failures",
    "claim_policy_anchor_regression_failed_rows",
    "claim_matrix_fail_closed_policy_failures",
    "claim_matrix_policy_current_failures",
    "claim_matrix_policy_current_regression_failed_rows",
    "human_decision_backlog_fail_closed_consistency_failures",
    "review_draft_formal_boundary_failures",
    "no_review_draft_training_leakage_failures",
    "draft_namespace_isolation_failures",
    "no_unreviewed_positive_gate_flags_failures",
    "no_unreviewed_positive_gate_flags_disallowed_true_count",
    "report_positive_claim_gate_quarantine_failures",
    "report_positive_claim_gate_quarantine_disallowed_true_hit_count",
    "model_claim_fail_closed_consistency_failures",
    "top_tier_model_ready_receipt_invalid_rows",
    "operator_work_receipt_manifest_consistency_failures",
    "label_provenance_strict_rows",
    "label_provenance_claim_eligible_rows",
    "strict_msa_site_feature_rows",
    "local_release_high_risk_summary_regression_failed_rows",
    "local_release_high_risk_coverage_regression_failed_rows",
    "data_lake_volatile_exemption_regression_failed_rows",
    "local_release_live_integrity_binding_regression_failed_rows",
    "release_input_contract_policy_failures",
    "release_input_contract_policy_regression_failed_rows",
    "local_release_contract_policy_binding_regression_failed_rows",
    "stage25_operator_docs_dynamic_sync_failures",
    "stage25_operator_docs_sync_contract_policy_failures",
    "stage25_operator_docs_sync_contract_policy_regression_failed_rows",
    "stage25_operator_docs_sync_current_receipt_failures",
    "stage25_operator_docs_sync_current_receipt_stale_rows",
    "safe_training_pipeline_receipt_atomicity_regression_failed_rows",
    "stage25_fail_closed_validation_current_receipt_validation_failures",
    "stage25_fail_closed_validation_current_receipt_regression_failed_rows",
    "stage25_post_source_drop_rerun_receipt_validation_failures",
    "stage25_post_source_drop_rerun_receipt_regression_failed_rows",
    "stage25_post_source_drop_rerun_validation_current_failures",
    "stage25_post_source_drop_rerun_validation_current_regression_failed_rows",
    "stage25_post_source_drop_rerun_independent_policy_failures",
    "stage25_post_source_drop_rerun_independent_policy_regression_failed_rows",
    "stage25_post_source_drop_rerun_independent_policy_current_failures",
    "stage25_post_source_drop_rerun_independent_policy_current_regression_failed_rows",
    "local_release_terminal_defer_mode_regression_failed_rows",
    "local_release_consistency_receipt_atomicity_regression_failed_rows",
    "local_release_consistency_semantic_policy_failures",
    "local_release_consistency_semantic_policy_regression_failed_rows",
    "local_release_consistency_semantic_policy_current_failures",
    "local_release_consistency_semantic_policy_current_regression_failed_rows",
    "local_release_consistency_semantic_policy_atomicity_regression_failed_rows",
    "enzyme_agent_release_guard_order_failures",
    "enzyme_agent_release_guard_order_regression_failed_rows",
    "enzyme_agent_release_guard_order_current_failures",
    "enzyme_agent_release_guard_order_current_regression_failed_rows",
    "enzyme_agent_release_guard_order_atomicity_regression_failed_rows",
    "enzyme_agent_execution_wave_pair_atomicity_regression_failed_rows",
    "enzyme_agent_execution_receipt_proof_current_failures",
    "enzyme_agent_execution_receipt_proof_current_regression_failed_rows",
    "local_release_safety_guard_links_atomicity_regression_failed_rows",
    "local_release_safety_guard_links_current_failures",
    "local_release_safety_guard_links_current_regression_failed_rows",
    "local_release_safety_guard_links_current_regression_atomicity_regression_failed_rows",
}

REQUIRED_FALSE_RISK_SUMMARY_FIELDS = {
    "claim_promotion_decision_success",
    "claim_policy_anchor_regression_real_inputs_mutated",
    "active_stage_execution_matrix_production_execution_allowed",
    "activity_risk_training_import_safe_for_model_claim",
    "activity_risk_training_import_training_execution_allowed",
    "advanced_model_feature_contract_safe_for_model_claim",
    "advanced_model_safe_for_model_claim",
    "customer_delivery_ready",
    "claim_matrix_all_claims_ready",
    "claim_matrix_promotion_policy_allows_all_claims",
    "claim_matrix_policy_current_regression_real_inputs_mutated",
    "ddg_model_consumption_contract_safe_for_model_claim",
    "enzyme_agent_result_safe_for_model_claim",
    "enzyme_analysis_policy_safe_for_model_claim",
    "feedback_training_import_semantic_guard_safe_for_model_claim",
    "fireprot_protherm_stability_benchmark_safe_for_model_claim",
    "five_head_training_execution_allowed",
    "five_head_training_execution_safe_for_model_claim",
    "google_github_research_safe_for_model_claim",
    "human_preflight_package_formal_decisions_written",
    "kwb_tool_lifecycle_safe_for_model_claim",
    "kwb_workflow_skill_safe_for_model_claim",
    "license_ready_for_customer_delivery",
    "local_release_fail_closed_consistency_release_ready",
    "mcp_wrapper_staging_safe_for_model_claim",
    "model_artifact_claim_guard_safe_for_model_claim",
    "model_quality_hard_gate_safe_for_model_claim",
    "numbering_semantic_conflict_safe_for_model_claim",
    "operator_work_receipt_manifest_consistency_release_ready",
    "p641_p0_today_closeout_plan_p0_unblocked",
    "p641_p0_today_closeout_plan_p0_completion_ready",
    "p642_p0_external_input_packet_manifest_p0_unblocked",
    "p642_p0_external_input_packet_manifest_p0_completion_ready",
    "p643_p0_external_input_dispatch_board_p0_unblocked",
    "p643_p0_external_input_dispatch_board_p0_completion_ready",
    "p644_p0_external_input_handoff_receipt_board_p0_unblocked",
    "p644_p0_external_input_handoff_receipt_board_p0_completion_ready",
    "p645_p0_external_input_response_slot_registry_p0_unblocked",
    "p645_p0_external_input_response_slot_registry_p0_completion_ready",
    "p646_p0_external_input_response_intake_queue_p0_unblocked",
    "p646_p0_external_input_response_intake_queue_p0_completion_ready",
    "p647_p0_external_input_response_validation_preflight_p0_unblocked",
    "p647_p0_external_input_response_validation_preflight_p0_completion_ready",
    "p648_p0_external_input_response_schema_contract_p0_unblocked",
    "p648_p0_external_input_response_schema_contract_p0_completion_ready",
    "p649_p0_external_input_response_evidence_quarantine_p0_unblocked",
    "p649_p0_external_input_response_evidence_quarantine_p0_completion_ready",
    "p650_p0_external_input_response_decision_routing_p0_unblocked",
    "p650_p0_external_input_response_decision_routing_p0_completion_ready",
    "p651_p0_external_input_formal_intake_dry_run_guard_p0_unblocked",
    "p651_p0_external_input_formal_intake_dry_run_guard_p0_completion_ready",
    "p652_p0_external_input_closeout_readiness_gate_p0_unblocked",
    "p652_p0_external_input_closeout_readiness_gate_p0_completion_ready",
    "p653_p0_external_input_closeout_blocker_ledger_p0_unblocked",
    "p653_p0_external_input_closeout_blocker_ledger_p0_completion_ready",
    "p654_p0_external_input_blocker_escalation_queue_p0_unblocked",
    "p654_p0_external_input_blocker_escalation_queue_p0_completion_ready",
    "p655_p0_external_input_blocker_escalation_status_board_p0_unblocked",
    "p655_p0_external_input_blocker_escalation_status_board_p0_completion_ready",
    "p656_p0_external_input_blocker_escalation_watchlist_p0_unblocked",
    "p656_p0_external_input_blocker_escalation_watchlist_p0_completion_ready",
    "p657_p0_external_input_blocker_escalation_review_queue_p0_unblocked",
    "p657_p0_external_input_blocker_escalation_review_queue_p0_completion_ready",
    "p658_p0_external_input_blocker_escalation_review_status_board_p0_unblocked",
    "p658_p0_external_input_blocker_escalation_review_status_board_p0_completion_ready",
    "p659_p0_external_input_blocker_escalation_review_watchlist_p0_unblocked",
    "p659_p0_external_input_blocker_escalation_review_watchlist_p0_completion_ready",
    "p660_p0_external_input_blocker_review_watchlist_aging_audit_p0_unblocked",
    "p660_p0_external_input_blocker_review_watchlist_aging_audit_p0_completion_ready",
    "p661_p0_external_input_blocker_review_owner_assignment_gap_audit_p0_unblocked",
    "p661_p0_external_input_blocker_review_owner_assignment_gap_audit_p0_completion_ready",
    "p662_p0_external_input_evidence_missing_matrix_p0_unblocked",
    "p662_p0_external_input_evidence_missing_matrix_p0_completion_ready",
    "p663_p0_formal_decision_readiness_false_positive_guard_p0_unblocked",
    "p663_p0_formal_decision_readiness_false_positive_guard_p0_completion_ready",
    "p664_p0_closeout_non_approval_receipt_audit_p0_unblocked",
    "p664_p0_closeout_non_approval_receipt_audit_p0_completion_ready",
    "proteinmcp_research_safe_for_model_claim",
    "reviewed_structure_graph_safe_for_model_claim",
    "structure_feature_model_contract_safe_for_model_claim",
    "top_tier_model_ready_receipts_safe_for_model_claim",
    "top_tier_model_ready_receipts_safe_for_training_import",
    "training_label_import_contract_safe_for_model_claim",
    "wet_lab_feedback_authorization_contract_safe_for_model_claim",
    "wet_lab_feedback_import_reconciliation_safe_for_model_claim",
}

REQUIRED_ZERO_RISK_SUMMARY_FIELDS = {
    "activity_risk_label_replicate_formal_decision_rows",
    "enzyme_action_space_safe_for_model_claim_actions",
    "enzyme_agent_result_selected_variants",
    "five_head_training_execution_ready_heads",
    "five_head_training_execution_validation_failures",
    "human_decision_pending_index_formal_decision_rows_written",
    "kwb_tool_lifecycle_production_allowed_rows",
    "kwb_workflow_skill_production_execution_allowed_rows",
    "mcp_wrapper_staging_production_allowed_rows",
    "model_artifact_claim_guard_production_artifacts",
    "p642_p0_external_input_packet_manifest_real_input_received_rows",
    "p642_p0_external_input_packet_manifest_reviewed_decision_written_rows",
    "p642_p0_external_input_packet_manifest_formal_intake_written_rows",
    "p642_p0_external_input_packet_manifest_runtime_receipt_written_rows",
    "p643_p0_external_input_dispatch_board_real_input_received_rows",
    "p643_p0_external_input_dispatch_board_reviewed_decision_written_rows",
    "p643_p0_external_input_dispatch_board_formal_intake_written_rows",
    "p643_p0_external_input_dispatch_board_runtime_receipt_written_rows",
    "p644_p0_external_input_handoff_receipt_board_handoff_sent_rows",
    "p644_p0_external_input_handoff_receipt_board_operator_acknowledged_rows",
    "p644_p0_external_input_handoff_receipt_board_external_input_acknowledged_rows",
    "p644_p0_external_input_handoff_receipt_board_real_input_received_rows",
    "p644_p0_external_input_handoff_receipt_board_reviewed_decision_written_rows",
    "p644_p0_external_input_handoff_receipt_board_formal_intake_written_rows",
    "p644_p0_external_input_handoff_receipt_board_runtime_receipt_written_rows",
    "p645_p0_external_input_response_slot_registry_response_received_rows",
    "p645_p0_external_input_response_slot_registry_response_validated_rows",
    "p645_p0_external_input_response_slot_registry_operator_acknowledged_rows",
    "p645_p0_external_input_response_slot_registry_external_input_acknowledged_rows",
    "p645_p0_external_input_response_slot_registry_real_input_received_rows",
    "p645_p0_external_input_response_slot_registry_reviewed_decision_written_rows",
    "p645_p0_external_input_response_slot_registry_formal_intake_written_rows",
    "p645_p0_external_input_response_slot_registry_runtime_receipt_written_rows",
    "p645_p0_external_input_response_slot_registry_training_label_written_rows",
    "p646_p0_external_input_response_intake_queue_dequeued_rows",
    "p646_p0_external_input_response_intake_queue_response_received_rows",
    "p646_p0_external_input_response_intake_queue_response_validated_rows",
    "p646_p0_external_input_response_intake_queue_operator_acknowledged_rows",
    "p646_p0_external_input_response_intake_queue_external_input_acknowledged_rows",
    "p646_p0_external_input_response_intake_queue_real_input_received_rows",
    "p646_p0_external_input_response_intake_queue_reviewed_decision_written_rows",
    "p646_p0_external_input_response_intake_queue_formal_intake_written_rows",
    "p646_p0_external_input_response_intake_queue_runtime_receipt_written_rows",
    "p646_p0_external_input_response_intake_queue_training_label_written_rows",
    "p647_p0_external_input_response_validation_preflight_preflight_executed_rows",
    "p647_p0_external_input_response_validation_preflight_queue_dequeued_rows",
    "p647_p0_external_input_response_validation_preflight_response_received_rows",
    "p647_p0_external_input_response_validation_preflight_response_validated_rows",
    "p647_p0_external_input_response_validation_preflight_real_input_received_rows",
    "p647_p0_external_input_response_validation_preflight_reviewed_decision_written_rows",
    "p647_p0_external_input_response_validation_preflight_formal_intake_written_rows",
    "p647_p0_external_input_response_validation_preflight_runtime_receipt_written_rows",
    "p647_p0_external_input_response_validation_preflight_training_label_written_rows",
    "p648_p0_external_input_response_schema_contract_queue_dequeued_rows",
    "p648_p0_external_input_response_schema_contract_response_received_rows",
    "p648_p0_external_input_response_schema_contract_response_validated_rows",
    "p648_p0_external_input_response_schema_contract_real_input_received_rows",
    "p648_p0_external_input_response_schema_contract_reviewed_decision_written_rows",
    "p648_p0_external_input_response_schema_contract_formal_intake_written_rows",
    "p648_p0_external_input_response_schema_contract_runtime_receipt_written_rows",
    "p648_p0_external_input_response_schema_contract_training_label_written_rows",
    "p648_p0_external_input_response_schema_contract_schema_contract_approved_rows",
    "p649_p0_external_input_response_evidence_quarantine_queue_dequeued_rows",
    "p649_p0_external_input_response_evidence_quarantine_response_received_rows",
    "p649_p0_external_input_response_evidence_quarantine_response_validated_rows",
    "p649_p0_external_input_response_evidence_quarantine_real_input_received_rows",
    "p649_p0_external_input_response_evidence_quarantine_reviewed_decision_written_rows",
    "p649_p0_external_input_response_evidence_quarantine_formal_intake_written_rows",
    "p649_p0_external_input_response_evidence_quarantine_runtime_receipt_written_rows",
    "p649_p0_external_input_response_evidence_quarantine_training_label_written_rows",
    "p649_p0_external_input_response_evidence_quarantine_evidence_quarantine_released_rows",
    "p649_p0_external_input_response_evidence_quarantine_evidence_promoted_to_decision_rows",
    "p650_p0_external_input_response_decision_routing_queue_dequeued_rows",
    "p650_p0_external_input_response_decision_routing_response_received_rows",
    "p650_p0_external_input_response_decision_routing_response_validated_rows",
    "p650_p0_external_input_response_decision_routing_real_input_received_rows",
    "p650_p0_external_input_response_decision_routing_reviewed_decision_written_rows",
    "p650_p0_external_input_response_decision_routing_formal_intake_written_rows",
    "p650_p0_external_input_response_decision_routing_runtime_receipt_written_rows",
    "p650_p0_external_input_response_decision_routing_training_label_written_rows",
    "p650_p0_external_input_response_decision_routing_decision_route_executed_rows",
    "p650_p0_external_input_response_decision_routing_routed_to_formal_review_rows",
    "p651_p0_external_input_formal_intake_dry_run_guard_queue_dequeued_rows",
    "p651_p0_external_input_formal_intake_dry_run_guard_response_received_rows",
    "p651_p0_external_input_formal_intake_dry_run_guard_response_validated_rows",
    "p651_p0_external_input_formal_intake_dry_run_guard_real_input_received_rows",
    "p651_p0_external_input_formal_intake_dry_run_guard_reviewed_decision_written_rows",
    "p651_p0_external_input_formal_intake_dry_run_guard_formal_intake_written_rows",
    "p651_p0_external_input_formal_intake_dry_run_guard_runtime_receipt_written_rows",
    "p651_p0_external_input_formal_intake_dry_run_guard_training_label_written_rows",
    "p651_p0_external_input_formal_intake_dry_run_guard_formal_intake_dry_run_executed_rows",
    "p651_p0_external_input_formal_intake_dry_run_guard_formal_intake_dry_run_passed_rows",
    "p652_p0_external_input_closeout_readiness_gate_queue_dequeued_rows",
    "p652_p0_external_input_closeout_readiness_gate_response_received_rows",
    "p652_p0_external_input_closeout_readiness_gate_response_validated_rows",
    "p652_p0_external_input_closeout_readiness_gate_real_input_received_rows",
    "p652_p0_external_input_closeout_readiness_gate_reviewed_decision_written_rows",
    "p652_p0_external_input_closeout_readiness_gate_formal_intake_written_rows",
    "p652_p0_external_input_closeout_readiness_gate_runtime_receipt_written_rows",
    "p652_p0_external_input_closeout_readiness_gate_training_label_written_rows",
    "p652_p0_external_input_closeout_readiness_gate_closeout_ready_rows",
    "p652_p0_external_input_closeout_readiness_gate_completion_ready_observed_rows",
    "p653_p0_external_input_closeout_blocker_ledger_queue_dequeued_rows",
    "p653_p0_external_input_closeout_blocker_ledger_response_received_rows",
    "p653_p0_external_input_closeout_blocker_ledger_response_validated_rows",
    "p653_p0_external_input_closeout_blocker_ledger_real_input_received_rows",
    "p653_p0_external_input_closeout_blocker_ledger_reviewed_decision_written_rows",
    "p653_p0_external_input_closeout_blocker_ledger_formal_intake_written_rows",
    "p653_p0_external_input_closeout_blocker_ledger_runtime_receipt_written_rows",
    "p653_p0_external_input_closeout_blocker_ledger_training_label_written_rows",
    "p653_p0_external_input_closeout_blocker_ledger_blocker_resolved_rows",
    "p653_p0_external_input_closeout_blocker_ledger_closeout_ready_rows",
    "p653_p0_external_input_closeout_blocker_ledger_completion_ready_observed_rows",
    "p654_p0_external_input_blocker_escalation_queue_queue_dequeued_rows",
    "p654_p0_external_input_blocker_escalation_queue_response_received_rows",
    "p654_p0_external_input_blocker_escalation_queue_response_validated_rows",
    "p654_p0_external_input_blocker_escalation_queue_real_input_received_rows",
    "p654_p0_external_input_blocker_escalation_queue_reviewed_decision_written_rows",
    "p654_p0_external_input_blocker_escalation_queue_formal_intake_written_rows",
    "p654_p0_external_input_blocker_escalation_queue_runtime_receipt_written_rows",
    "p654_p0_external_input_blocker_escalation_queue_training_label_written_rows",
    "p654_p0_external_input_blocker_escalation_queue_escalation_sent_rows",
    "p654_p0_external_input_blocker_escalation_queue_escalation_acknowledged_rows",
    "p654_p0_external_input_blocker_escalation_queue_blocker_resolved_rows",
    "p654_p0_external_input_blocker_escalation_queue_closeout_ready_rows",
    "p654_p0_external_input_blocker_escalation_queue_completion_ready_observed_rows",
    "p655_p0_external_input_blocker_escalation_status_board_queue_dequeued_rows",
    "p655_p0_external_input_blocker_escalation_status_board_response_received_rows",
    "p655_p0_external_input_blocker_escalation_status_board_response_validated_rows",
    "p655_p0_external_input_blocker_escalation_status_board_real_input_received_rows",
    "p655_p0_external_input_blocker_escalation_status_board_reviewed_decision_written_rows",
    "p655_p0_external_input_blocker_escalation_status_board_formal_intake_written_rows",
    "p655_p0_external_input_blocker_escalation_status_board_runtime_receipt_written_rows",
    "p655_p0_external_input_blocker_escalation_status_board_training_label_written_rows",
    "p655_p0_external_input_blocker_escalation_status_board_escalation_sent_rows",
    "p655_p0_external_input_blocker_escalation_status_board_escalation_acknowledged_rows",
    "p655_p0_external_input_blocker_escalation_status_board_blocker_resolved_rows",
    "p655_p0_external_input_blocker_escalation_status_board_closeout_ready_rows",
    "p655_p0_external_input_blocker_escalation_status_board_completion_ready_observed_rows",
    "p656_p0_external_input_blocker_escalation_watchlist_queue_dequeued_rows",
    "p656_p0_external_input_blocker_escalation_watchlist_response_received_rows",
    "p656_p0_external_input_blocker_escalation_watchlist_response_validated_rows",
    "p656_p0_external_input_blocker_escalation_watchlist_real_input_received_rows",
    "p656_p0_external_input_blocker_escalation_watchlist_reviewed_decision_written_rows",
    "p656_p0_external_input_blocker_escalation_watchlist_formal_intake_written_rows",
    "p656_p0_external_input_blocker_escalation_watchlist_runtime_receipt_written_rows",
    "p656_p0_external_input_blocker_escalation_watchlist_training_label_written_rows",
    "p656_p0_external_input_blocker_escalation_watchlist_escalation_sent_rows",
    "p656_p0_external_input_blocker_escalation_watchlist_escalation_acknowledged_rows",
    "p656_p0_external_input_blocker_escalation_watchlist_blocker_resolved_rows",
    "p656_p0_external_input_blocker_escalation_watchlist_closeout_ready_rows",
    "p656_p0_external_input_blocker_escalation_watchlist_completion_ready_observed_rows",
    "p657_p0_external_input_blocker_escalation_review_queue_queue_dequeued_rows",
    "p657_p0_external_input_blocker_escalation_review_queue_response_received_rows",
    "p657_p0_external_input_blocker_escalation_review_queue_response_validated_rows",
    "p657_p0_external_input_blocker_escalation_review_queue_real_input_received_rows",
    "p657_p0_external_input_blocker_escalation_review_queue_reviewed_decision_written_rows",
    "p657_p0_external_input_blocker_escalation_review_queue_formal_intake_written_rows",
    "p657_p0_external_input_blocker_escalation_review_queue_runtime_receipt_written_rows",
    "p657_p0_external_input_blocker_escalation_review_queue_training_label_written_rows",
    "p657_p0_external_input_blocker_escalation_review_queue_escalation_reviewed_rows",
    "p657_p0_external_input_blocker_escalation_review_queue_escalation_sent_rows",
    "p657_p0_external_input_blocker_escalation_review_queue_escalation_acknowledged_rows",
    "p657_p0_external_input_blocker_escalation_review_queue_blocker_resolved_rows",
    "p657_p0_external_input_blocker_escalation_review_queue_closeout_ready_rows",
    "p657_p0_external_input_blocker_escalation_review_queue_completion_ready_observed_rows",
    "p658_p0_external_input_blocker_escalation_review_status_board_queue_dequeued_rows",
    "p658_p0_external_input_blocker_escalation_review_status_board_response_received_rows",
    "p658_p0_external_input_blocker_escalation_review_status_board_response_validated_rows",
    "p658_p0_external_input_blocker_escalation_review_status_board_real_input_received_rows",
    "p658_p0_external_input_blocker_escalation_review_status_board_reviewed_decision_written_rows",
    "p658_p0_external_input_blocker_escalation_review_status_board_formal_intake_written_rows",
    "p658_p0_external_input_blocker_escalation_review_status_board_runtime_receipt_written_rows",
    "p658_p0_external_input_blocker_escalation_review_status_board_training_label_written_rows",
    "p658_p0_external_input_blocker_escalation_review_status_board_escalation_reviewed_rows",
    "p658_p0_external_input_blocker_escalation_review_status_board_escalation_sent_rows",
    "p658_p0_external_input_blocker_escalation_review_status_board_escalation_acknowledged_rows",
    "p658_p0_external_input_blocker_escalation_review_status_board_blocker_resolved_rows",
    "p658_p0_external_input_blocker_escalation_review_status_board_closeout_ready_rows",
    "p658_p0_external_input_blocker_escalation_review_status_board_completion_ready_observed_rows",
    "p659_p0_external_input_blocker_escalation_review_watchlist_queue_dequeued_rows",
    "p659_p0_external_input_blocker_escalation_review_watchlist_response_received_rows",
    "p659_p0_external_input_blocker_escalation_review_watchlist_response_validated_rows",
    "p659_p0_external_input_blocker_escalation_review_watchlist_real_input_received_rows",
    "p659_p0_external_input_blocker_escalation_review_watchlist_reviewed_decision_written_rows",
    "p659_p0_external_input_blocker_escalation_review_watchlist_formal_intake_written_rows",
    "p659_p0_external_input_blocker_escalation_review_watchlist_runtime_receipt_written_rows",
    "p659_p0_external_input_blocker_escalation_review_watchlist_training_label_written_rows",
    "p659_p0_external_input_blocker_escalation_review_watchlist_escalation_reviewed_rows",
    "p659_p0_external_input_blocker_escalation_review_watchlist_escalation_sent_rows",
    "p659_p0_external_input_blocker_escalation_review_watchlist_escalation_acknowledged_rows",
    "p659_p0_external_input_blocker_escalation_review_watchlist_blocker_resolved_rows",
    "p659_p0_external_input_blocker_escalation_review_watchlist_closeout_ready_rows",
    "p659_p0_external_input_blocker_escalation_review_watchlist_completion_ready_observed_rows",
    "p660_p0_external_input_blocker_review_watchlist_aging_audit_queue_dequeued_rows",
    "p660_p0_external_input_blocker_review_watchlist_aging_audit_response_received_rows",
    "p660_p0_external_input_blocker_review_watchlist_aging_audit_response_validated_rows",
    "p660_p0_external_input_blocker_review_watchlist_aging_audit_real_input_received_rows",
    "p660_p0_external_input_blocker_review_watchlist_aging_audit_reviewed_decision_written_rows",
    "p660_p0_external_input_blocker_review_watchlist_aging_audit_formal_intake_written_rows",
    "p660_p0_external_input_blocker_review_watchlist_aging_audit_runtime_receipt_written_rows",
    "p660_p0_external_input_blocker_review_watchlist_aging_audit_training_label_written_rows",
    "p660_p0_external_input_blocker_review_watchlist_aging_audit_aging_reviewed_rows",
    "p660_p0_external_input_blocker_review_watchlist_aging_audit_staleness_resolved_rows",
    "p660_p0_external_input_blocker_review_watchlist_aging_audit_escalation_reviewed_rows",
    "p660_p0_external_input_blocker_review_watchlist_aging_audit_escalation_sent_rows",
    "p660_p0_external_input_blocker_review_watchlist_aging_audit_escalation_acknowledged_rows",
    "p660_p0_external_input_blocker_review_watchlist_aging_audit_blocker_resolved_rows",
    "p660_p0_external_input_blocker_review_watchlist_aging_audit_closeout_ready_rows",
    "p660_p0_external_input_blocker_review_watchlist_aging_audit_completion_ready_observed_rows",
    "p661_p0_external_input_blocker_review_owner_assignment_gap_audit_queue_dequeued_rows",
    "p661_p0_external_input_blocker_review_owner_assignment_gap_audit_response_received_rows",
    "p661_p0_external_input_blocker_review_owner_assignment_gap_audit_response_validated_rows",
    "p661_p0_external_input_blocker_review_owner_assignment_gap_audit_real_input_received_rows",
    "p661_p0_external_input_blocker_review_owner_assignment_gap_audit_reviewed_decision_written_rows",
    "p661_p0_external_input_blocker_review_owner_assignment_gap_audit_formal_intake_written_rows",
    "p661_p0_external_input_blocker_review_owner_assignment_gap_audit_runtime_receipt_written_rows",
    "p661_p0_external_input_blocker_review_owner_assignment_gap_audit_training_label_written_rows",
    "p661_p0_external_input_blocker_review_owner_assignment_gap_audit_owner_assigned_rows",
    "p661_p0_external_input_blocker_review_owner_assignment_gap_audit_owner_acknowledged_rows",
    "p661_p0_external_input_blocker_review_owner_assignment_gap_audit_aging_reviewed_rows",
    "p661_p0_external_input_blocker_review_owner_assignment_gap_audit_staleness_resolved_rows",
    "p661_p0_external_input_blocker_review_owner_assignment_gap_audit_escalation_reviewed_rows",
    "p661_p0_external_input_blocker_review_owner_assignment_gap_audit_escalation_sent_rows",
    "p661_p0_external_input_blocker_review_owner_assignment_gap_audit_escalation_acknowledged_rows",
    "p661_p0_external_input_blocker_review_owner_assignment_gap_audit_blocker_resolved_rows",
    "p661_p0_external_input_blocker_review_owner_assignment_gap_audit_closeout_ready_rows",
    "p661_p0_external_input_blocker_review_owner_assignment_gap_audit_completion_ready_observed_rows",
    "p662_p0_external_input_evidence_missing_matrix_queue_dequeued_rows",
    "p662_p0_external_input_evidence_missing_matrix_response_received_rows",
    "p662_p0_external_input_evidence_missing_matrix_response_validated_rows",
    "p662_p0_external_input_evidence_missing_matrix_real_input_received_rows",
    "p662_p0_external_input_evidence_missing_matrix_reviewed_decision_written_rows",
    "p662_p0_external_input_evidence_missing_matrix_formal_intake_written_rows",
    "p662_p0_external_input_evidence_missing_matrix_runtime_receipt_written_rows",
    "p662_p0_external_input_evidence_missing_matrix_training_label_written_rows",
    "p662_p0_external_input_evidence_missing_matrix_evidence_received_rows",
    "p662_p0_external_input_evidence_missing_matrix_evidence_validated_rows",
    "p662_p0_external_input_evidence_missing_matrix_owner_assigned_rows",
    "p662_p0_external_input_evidence_missing_matrix_owner_acknowledged_rows",
    "p662_p0_external_input_evidence_missing_matrix_aging_reviewed_rows",
    "p662_p0_external_input_evidence_missing_matrix_staleness_resolved_rows",
    "p662_p0_external_input_evidence_missing_matrix_escalation_reviewed_rows",
    "p662_p0_external_input_evidence_missing_matrix_escalation_sent_rows",
    "p662_p0_external_input_evidence_missing_matrix_escalation_acknowledged_rows",
    "p662_p0_external_input_evidence_missing_matrix_blocker_resolved_rows",
    "p662_p0_external_input_evidence_missing_matrix_closeout_ready_rows",
    "p662_p0_external_input_evidence_missing_matrix_completion_ready_observed_rows",
    "p663_p0_formal_decision_readiness_false_positive_guard_queue_dequeued_rows",
    "p663_p0_formal_decision_readiness_false_positive_guard_response_received_rows",
    "p663_p0_formal_decision_readiness_false_positive_guard_response_validated_rows",
    "p663_p0_formal_decision_readiness_false_positive_guard_real_input_received_rows",
    "p663_p0_formal_decision_readiness_false_positive_guard_reviewed_decision_written_rows",
    "p663_p0_formal_decision_readiness_false_positive_guard_formal_intake_written_rows",
    "p663_p0_formal_decision_readiness_false_positive_guard_runtime_receipt_written_rows",
    "p663_p0_formal_decision_readiness_false_positive_guard_training_label_written_rows",
    "p663_p0_formal_decision_readiness_false_positive_guard_formal_decision_ready_rows",
    "p663_p0_formal_decision_readiness_false_positive_guard_false_positive_cleared_rows",
    "p663_p0_formal_decision_readiness_false_positive_guard_evidence_received_rows",
    "p663_p0_formal_decision_readiness_false_positive_guard_evidence_validated_rows",
    "p663_p0_formal_decision_readiness_false_positive_guard_owner_assigned_rows",
    "p663_p0_formal_decision_readiness_false_positive_guard_owner_acknowledged_rows",
    "p663_p0_formal_decision_readiness_false_positive_guard_aging_reviewed_rows",
    "p663_p0_formal_decision_readiness_false_positive_guard_staleness_resolved_rows",
    "p663_p0_formal_decision_readiness_false_positive_guard_escalation_reviewed_rows",
    "p663_p0_formal_decision_readiness_false_positive_guard_escalation_sent_rows",
    "p663_p0_formal_decision_readiness_false_positive_guard_escalation_acknowledged_rows",
    "p663_p0_formal_decision_readiness_false_positive_guard_blocker_resolved_rows",
    "p663_p0_formal_decision_readiness_false_positive_guard_closeout_ready_rows",
    "p663_p0_formal_decision_readiness_false_positive_guard_completion_ready_observed_rows",
    "p664_p0_closeout_non_approval_receipt_audit_queue_dequeued_rows",
    "p664_p0_closeout_non_approval_receipt_audit_response_received_rows",
    "p664_p0_closeout_non_approval_receipt_audit_response_validated_rows",
    "p664_p0_closeout_non_approval_receipt_audit_real_input_received_rows",
    "p664_p0_closeout_non_approval_receipt_audit_reviewed_decision_written_rows",
    "p664_p0_closeout_non_approval_receipt_audit_formal_intake_written_rows",
    "p664_p0_closeout_non_approval_receipt_audit_runtime_receipt_written_rows",
    "p664_p0_closeout_non_approval_receipt_audit_training_label_written_rows",
    "p664_p0_closeout_non_approval_receipt_audit_closeout_approved_rows",
    "p664_p0_closeout_non_approval_receipt_audit_closeout_approval_written_rows",
    "p664_p0_closeout_non_approval_receipt_audit_formal_decision_ready_rows",
    "p664_p0_closeout_non_approval_receipt_audit_false_positive_cleared_rows",
    "p664_p0_closeout_non_approval_receipt_audit_evidence_received_rows",
    "p664_p0_closeout_non_approval_receipt_audit_evidence_validated_rows",
    "p664_p0_closeout_non_approval_receipt_audit_owner_assigned_rows",
    "p664_p0_closeout_non_approval_receipt_audit_owner_acknowledged_rows",
    "p664_p0_closeout_non_approval_receipt_audit_aging_reviewed_rows",
    "p664_p0_closeout_non_approval_receipt_audit_staleness_resolved_rows",
    "p664_p0_closeout_non_approval_receipt_audit_escalation_reviewed_rows",
    "p664_p0_closeout_non_approval_receipt_audit_escalation_sent_rows",
    "p664_p0_closeout_non_approval_receipt_audit_escalation_acknowledged_rows",
    "p664_p0_closeout_non_approval_receipt_audit_blocker_resolved_rows",
    "p664_p0_closeout_non_approval_receipt_audit_closeout_ready_rows",
    "p664_p0_closeout_non_approval_receipt_audit_completion_ready_observed_rows",
}

P665_P669_ZERO_RISK_SUMMARY_FIELDS = {
    "p665_p0_closeout_non_approval_watchlist": (
        "queue_dequeued_rows", "response_received_rows", "response_validated_rows", "real_input_received_rows",
        "reviewed_decision_written_rows", "formal_intake_written_rows", "runtime_receipt_written_rows",
        "training_label_written_rows", "closeout_watch_reviewed_rows", "closeout_approved_rows",
        "closeout_approval_written_rows", "formal_decision_ready_rows", "false_positive_cleared_rows",
        "evidence_received_rows", "evidence_validated_rows", "owner_assigned_rows", "owner_acknowledged_rows",
        "aging_reviewed_rows", "staleness_resolved_rows", "escalation_reviewed_rows", "escalation_sent_rows",
        "escalation_acknowledged_rows", "blocker_resolved_rows", "closeout_ready_rows",
        "completion_ready_observed_rows",
    ),
    "p666_p0_closeout_owner_review_queue": (
        "queue_dequeued_rows", "response_received_rows", "response_validated_rows", "real_input_received_rows",
        "reviewed_decision_written_rows", "formal_intake_written_rows", "runtime_receipt_written_rows",
        "training_label_written_rows", "closeout_owner_assigned_rows", "closeout_owner_reviewed_rows",
        "closeout_watch_reviewed_rows", "closeout_approved_rows", "closeout_approval_written_rows",
        "formal_decision_ready_rows", "false_positive_cleared_rows", "evidence_received_rows",
        "evidence_validated_rows", "owner_assigned_rows", "owner_acknowledged_rows", "aging_reviewed_rows",
        "staleness_resolved_rows", "escalation_reviewed_rows", "escalation_sent_rows",
        "escalation_acknowledged_rows", "blocker_resolved_rows", "closeout_ready_rows",
        "completion_ready_observed_rows",
    ),
    "p667_p0_formal_intake_non_write_guard_audit": (
        "queue_dequeued_rows", "response_received_rows", "response_validated_rows", "real_input_received_rows",
        "reviewed_decision_written_rows", "formal_intake_written_rows", "runtime_receipt_written_rows",
        "training_label_written_rows", "formal_intake_guard_reviewed_rows", "formal_intake_write_authorized_rows",
        "closeout_owner_assigned_rows", "closeout_owner_reviewed_rows", "closeout_watch_reviewed_rows",
        "closeout_approved_rows", "closeout_approval_written_rows", "formal_decision_ready_rows",
        "false_positive_cleared_rows", "evidence_received_rows", "evidence_validated_rows",
        "owner_assigned_rows", "owner_acknowledged_rows", "aging_reviewed_rows", "staleness_resolved_rows",
        "escalation_reviewed_rows", "escalation_sent_rows", "escalation_acknowledged_rows",
        "blocker_resolved_rows", "closeout_ready_rows", "completion_ready_observed_rows",
    ),
    "p668_p0_training_label_non_import_guard_audit": (
        "queue_dequeued_rows", "response_received_rows", "response_validated_rows", "real_input_received_rows",
        "reviewed_decision_written_rows", "formal_intake_written_rows", "runtime_receipt_written_rows",
        "training_label_written_rows", "training_label_guard_reviewed_rows", "training_label_import_authorized_rows",
        "formal_intake_guard_reviewed_rows", "formal_intake_write_authorized_rows", "closeout_owner_assigned_rows",
        "closeout_owner_reviewed_rows", "closeout_watch_reviewed_rows", "closeout_approved_rows",
        "closeout_approval_written_rows", "formal_decision_ready_rows", "false_positive_cleared_rows",
        "evidence_received_rows", "evidence_validated_rows", "owner_assigned_rows", "owner_acknowledged_rows",
        "aging_reviewed_rows", "staleness_resolved_rows", "escalation_reviewed_rows", "escalation_sent_rows",
        "escalation_acknowledged_rows", "blocker_resolved_rows", "closeout_ready_rows",
        "completion_ready_observed_rows",
    ),
    "p669_p0_release_claim_non_promotion_guard_audit": (
        "queue_dequeued_rows", "response_received_rows", "response_validated_rows", "real_input_received_rows",
        "reviewed_decision_written_rows", "formal_intake_written_rows", "runtime_receipt_written_rows",
        "training_label_written_rows", "release_claim_guard_reviewed_rows", "release_claim_promoted_rows",
        "training_label_guard_reviewed_rows", "training_label_import_authorized_rows",
        "formal_intake_guard_reviewed_rows", "formal_intake_write_authorized_rows", "closeout_owner_assigned_rows",
        "closeout_owner_reviewed_rows", "closeout_watch_reviewed_rows", "closeout_approved_rows",
        "closeout_approval_written_rows", "formal_decision_ready_rows", "false_positive_cleared_rows",
        "evidence_received_rows", "evidence_validated_rows", "owner_assigned_rows", "owner_acknowledged_rows",
        "aging_reviewed_rows", "staleness_resolved_rows", "escalation_reviewed_rows", "escalation_sent_rows",
        "escalation_acknowledged_rows", "blocker_resolved_rows", "closeout_ready_rows",
        "completion_ready_observed_rows",
    ),
}

for _p665_p669_prefix, _p665_p669_fields in P665_P669_ZERO_RISK_SUMMARY_FIELDS.items():
    REQUIRED_FALSE_RISK_SUMMARY_FIELDS.update({
        f"{_p665_p669_prefix}_p0_unblocked",
        f"{_p665_p669_prefix}_p0_completion_ready",
    })
    REQUIRED_ZERO_RISK_SUMMARY_FIELDS.update(
        f"{_p665_p669_prefix}_{field}" for field in _p665_p669_fields
    )

P670_P674_ZERO_RISK_SUMMARY_FIELDS = {
    "p670_p0_release_claim_non_promotion_status_board": (
        "queue_dequeued_rows", "response_received_rows", "response_validated_rows", "real_input_received_rows",
        "reviewed_decision_written_rows", "formal_intake_written_rows", "runtime_receipt_written_rows",
        "training_label_written_rows", "release_claim_status_reviewed_rows", "release_claim_guard_reviewed_rows",
        "release_claim_promoted_rows", "training_label_guard_reviewed_rows", "training_label_import_authorized_rows",
        "formal_intake_guard_reviewed_rows", "formal_intake_write_authorized_rows", "closeout_owner_assigned_rows",
        "closeout_owner_reviewed_rows", "closeout_watch_reviewed_rows", "closeout_approved_rows",
        "closeout_approval_written_rows", "formal_decision_ready_rows", "false_positive_cleared_rows",
        "evidence_received_rows", "evidence_validated_rows", "owner_assigned_rows", "owner_acknowledged_rows",
        "aging_reviewed_rows", "staleness_resolved_rows", "escalation_reviewed_rows", "escalation_sent_rows",
        "escalation_acknowledged_rows", "blocker_resolved_rows", "closeout_ready_rows",
        "completion_ready_observed_rows",
    ),
    "p671_p0_model_claim_non_assertion_guard_audit": (
        "queue_dequeued_rows", "response_received_rows", "response_validated_rows", "real_input_received_rows",
        "reviewed_decision_written_rows", "formal_intake_written_rows", "runtime_receipt_written_rows",
        "training_label_written_rows", "model_claim_guard_reviewed_rows", "model_claim_asserted_rows",
        "release_claim_status_reviewed_rows", "release_claim_guard_reviewed_rows", "release_claim_promoted_rows",
        "training_label_guard_reviewed_rows", "training_label_import_authorized_rows",
        "formal_intake_guard_reviewed_rows", "formal_intake_write_authorized_rows", "closeout_owner_assigned_rows",
        "closeout_owner_reviewed_rows", "closeout_watch_reviewed_rows", "closeout_approved_rows",
        "closeout_approval_written_rows", "formal_decision_ready_rows", "false_positive_cleared_rows",
        "evidence_received_rows", "evidence_validated_rows", "owner_assigned_rows", "owner_acknowledged_rows",
        "aging_reviewed_rows", "staleness_resolved_rows", "escalation_reviewed_rows", "escalation_sent_rows",
        "escalation_acknowledged_rows", "blocker_resolved_rows", "closeout_ready_rows",
        "completion_ready_observed_rows",
    ),
    "p672_p0_customer_delivery_non_authorization_guard_audit": (
        "queue_dequeued_rows", "response_received_rows", "response_validated_rows", "real_input_received_rows",
        "reviewed_decision_written_rows", "formal_intake_written_rows", "runtime_receipt_written_rows",
        "training_label_written_rows", "customer_delivery_guard_reviewed_rows", "customer_delivery_authorized_rows",
        "model_claim_guard_reviewed_rows", "model_claim_asserted_rows", "release_claim_status_reviewed_rows",
        "release_claim_guard_reviewed_rows", "release_claim_promoted_rows", "training_label_guard_reviewed_rows",
        "training_label_import_authorized_rows", "formal_intake_guard_reviewed_rows",
        "formal_intake_write_authorized_rows", "closeout_owner_assigned_rows", "closeout_owner_reviewed_rows",
        "closeout_watch_reviewed_rows", "closeout_approved_rows", "closeout_approval_written_rows",
        "formal_decision_ready_rows", "false_positive_cleared_rows", "evidence_received_rows",
        "evidence_validated_rows", "owner_assigned_rows", "owner_acknowledged_rows", "aging_reviewed_rows",
        "staleness_resolved_rows", "escalation_reviewed_rows", "escalation_sent_rows",
        "escalation_acknowledged_rows", "blocker_resolved_rows", "closeout_ready_rows",
        "completion_ready_observed_rows",
    ),
    "p673_p0_production_execution_non_authorization_guard_audit": (
        "queue_dequeued_rows", "response_received_rows", "response_validated_rows", "real_input_received_rows",
        "reviewed_decision_written_rows", "formal_intake_written_rows", "runtime_receipt_written_rows",
        "training_label_written_rows", "production_execution_guard_reviewed_rows",
        "production_execution_authorized_rows", "customer_delivery_guard_reviewed_rows",
        "customer_delivery_authorized_rows", "model_claim_guard_reviewed_rows", "model_claim_asserted_rows",
        "release_claim_status_reviewed_rows", "release_claim_guard_reviewed_rows", "release_claim_promoted_rows",
        "training_label_guard_reviewed_rows", "training_label_import_authorized_rows",
        "formal_intake_guard_reviewed_rows", "formal_intake_write_authorized_rows", "closeout_owner_assigned_rows",
        "closeout_owner_reviewed_rows", "closeout_watch_reviewed_rows", "closeout_approved_rows",
        "closeout_approval_written_rows", "formal_decision_ready_rows", "false_positive_cleared_rows",
        "evidence_received_rows", "evidence_validated_rows", "owner_assigned_rows", "owner_acknowledged_rows",
        "aging_reviewed_rows", "staleness_resolved_rows", "escalation_reviewed_rows", "escalation_sent_rows",
        "escalation_acknowledged_rows", "blocker_resolved_rows", "closeout_ready_rows",
        "completion_ready_observed_rows",
    ),
    "p674_p0_terminal_blocked_state_rollup_audit": (
        "queue_dequeued_rows", "response_received_rows", "response_validated_rows", "real_input_received_rows",
        "reviewed_decision_written_rows", "formal_intake_written_rows", "runtime_receipt_written_rows",
        "training_label_written_rows", "terminal_blocked_state_reviewed_rows", "p0_terminal_unblocked_rows",
        "production_execution_guard_reviewed_rows", "production_execution_authorized_rows",
        "customer_delivery_guard_reviewed_rows", "customer_delivery_authorized_rows",
        "model_claim_guard_reviewed_rows", "model_claim_asserted_rows", "release_claim_status_reviewed_rows",
        "release_claim_guard_reviewed_rows", "release_claim_promoted_rows", "training_label_guard_reviewed_rows",
        "training_label_import_authorized_rows", "formal_intake_guard_reviewed_rows",
        "formal_intake_write_authorized_rows", "closeout_owner_assigned_rows", "closeout_owner_reviewed_rows",
        "closeout_watch_reviewed_rows", "closeout_approved_rows", "closeout_approval_written_rows",
        "formal_decision_ready_rows", "false_positive_cleared_rows", "evidence_received_rows",
        "evidence_validated_rows", "owner_assigned_rows", "owner_acknowledged_rows", "aging_reviewed_rows",
        "staleness_resolved_rows", "escalation_reviewed_rows", "escalation_sent_rows",
        "escalation_acknowledged_rows", "blocker_resolved_rows", "closeout_ready_rows",
        "completion_ready_observed_rows",
    ),
    "p687_p0_real_input_closeout_readiness_gate": (
        "queue_dequeued_rows", "formal_intake_dry_run_executed_rows",
        "formal_intake_dry_run_passed_rows", "formal_intake_written_rows", "closeout_ready_rows",
        "completion_ready_observed_rows", "completion_ready_rows",
    ),
}

for _p670_p674_prefix, _p670_p674_fields in P670_P674_ZERO_RISK_SUMMARY_FIELDS.items():
    REQUIRED_FALSE_RISK_SUMMARY_FIELDS.update({
        f"{_p670_p674_prefix}_p0_unblocked",
        f"{_p670_p674_prefix}_p0_completion_ready",
    })
    REQUIRED_ZERO_RISK_SUMMARY_FIELDS.update(
        f"{_p670_p674_prefix}_{field}" for field in _p670_p674_fields
    )
REQUIRED_SUCCESS_SUMMARY_FLAGS.add("p687_p0_real_input_closeout_readiness_gate_validation_success")
REQUIRED_SUCCESS_SUMMARY_FLAGS.add("p688_p0_real_input_closeout_blocker_ledger_validation_success")
REQUIRED_SUCCESS_SUMMARY_FLAGS.add("p689_p0_real_input_blocker_escalation_queue_validation_success")
REQUIRED_SUCCESS_SUMMARY_FLAGS.add("p690_p0_real_input_blocker_escalation_status_board_validation_success")
REQUIRED_SUCCESS_SUMMARY_FLAGS.add("p691_p0_real_input_blocker_escalation_watchlist_validation_success")
REQUIRED_SUCCESS_SUMMARY_FLAGS.add("p692_p0_real_input_blocker_escalation_review_queue_validation_success")
REQUIRED_SUCCESS_SUMMARY_FLAGS.add("p693_p0_real_input_blocker_escalation_review_status_board_validation_success")
REQUIRED_SUCCESS_SUMMARY_FLAGS.add("p694_p0_real_input_blocker_escalation_review_watchlist_validation_success")
REQUIRED_SUCCESS_SUMMARY_FLAGS.add("p695_p0_real_input_blocker_escalation_review_watchlist_aging_audit_validation_success")
REQUIRED_SUCCESS_SUMMARY_FLAGS.add("p696_p0_real_input_blocker_escalation_review_owner_assignment_gap_audit_validation_success")
REQUIRED_SUCCESS_SUMMARY_FLAGS.add("p697_p0_real_input_blocker_escalation_review_evidence_missing_matrix_validation_success")
REQUIRED_SUCCESS_SUMMARY_FLAGS.add("p698_p0_real_input_formal_decision_readiness_false_positive_guard_validation_success")
REQUIRED_SUCCESS_SUMMARY_FLAGS.add("p699_p0_real_input_formal_decision_readiness_status_board_validation_success")
REQUIRED_SUCCESS_SUMMARY_FLAGS.add("p700_p0_real_input_pending_build_checklist_validation_success")
REQUIRED_FALSE_RISK_SUMMARY_FIELDS.update({
    "p700_p0_real_input_pending_build_checklist_pending_build_ready",
    "p687_p0_real_input_closeout_readiness_gate_training_import_allowed",
    "p687_p0_real_input_closeout_readiness_gate_safe_for_training_import",
    "p687_p0_real_input_closeout_readiness_gate_safe_for_model_claim",
    "p687_p0_real_input_closeout_readiness_gate_customer_delivery_ready",
    "p687_p0_real_input_closeout_readiness_gate_release_ready",
    "p687_p0_real_input_closeout_readiness_gate_production_execution_allowed",
    "p687_p0_real_input_closeout_readiness_gate_closeout_ready",
    "p687_p0_real_input_closeout_readiness_gate_completion_ready_observed",
    "p687_p0_real_input_closeout_readiness_gate_completion_ready",
    "p687_p0_real_input_closeout_readiness_gate_p0_unblocked",
    "p687_p0_real_input_closeout_readiness_gate_p0_completion_ready",
    "p688_p0_real_input_closeout_blocker_ledger_training_import_allowed",
    "p688_p0_real_input_closeout_blocker_ledger_safe_for_training_import",
    "p688_p0_real_input_closeout_blocker_ledger_safe_for_model_claim",
    "p688_p0_real_input_closeout_blocker_ledger_customer_delivery_ready",
    "p688_p0_real_input_closeout_blocker_ledger_release_ready",
    "p688_p0_real_input_closeout_blocker_ledger_production_execution_allowed",
    "p688_p0_real_input_closeout_blocker_ledger_blocker_resolved",
    "p688_p0_real_input_closeout_blocker_ledger_closeout_ready",
    "p688_p0_real_input_closeout_blocker_ledger_completion_ready_observed",
    "p688_p0_real_input_closeout_blocker_ledger_completion_ready",
    "p688_p0_real_input_closeout_blocker_ledger_p0_unblocked",
    "p688_p0_real_input_closeout_blocker_ledger_p0_completion_ready",
    "p689_p0_real_input_blocker_escalation_queue_training_import_allowed",
    "p689_p0_real_input_blocker_escalation_queue_safe_for_training_import",
    "p689_p0_real_input_blocker_escalation_queue_safe_for_model_claim",
    "p689_p0_real_input_blocker_escalation_queue_customer_delivery_ready",
    "p689_p0_real_input_blocker_escalation_queue_release_ready",
    "p689_p0_real_input_blocker_escalation_queue_production_execution_allowed",
    "p689_p0_real_input_blocker_escalation_queue_escalation_sent",
    "p689_p0_real_input_blocker_escalation_queue_escalation_acknowledged",
    "p689_p0_real_input_blocker_escalation_queue_blocker_resolved",
    "p689_p0_real_input_blocker_escalation_queue_closeout_ready",
    "p689_p0_real_input_blocker_escalation_queue_completion_ready_observed",
    "p689_p0_real_input_blocker_escalation_queue_completion_ready",
    "p689_p0_real_input_blocker_escalation_queue_p0_unblocked",
    "p689_p0_real_input_blocker_escalation_queue_p0_completion_ready",
    "p690_p0_real_input_blocker_escalation_status_board_training_import_allowed",
    "p690_p0_real_input_blocker_escalation_status_board_safe_for_training_import",
    "p690_p0_real_input_blocker_escalation_status_board_safe_for_model_claim",
    "p690_p0_real_input_blocker_escalation_status_board_customer_delivery_ready",
    "p690_p0_real_input_blocker_escalation_status_board_release_ready",
    "p690_p0_real_input_blocker_escalation_status_board_production_execution_allowed",
    "p690_p0_real_input_blocker_escalation_status_board_escalation_sent",
    "p690_p0_real_input_blocker_escalation_status_board_escalation_acknowledged",
    "p690_p0_real_input_blocker_escalation_status_board_blocker_resolved",
    "p690_p0_real_input_blocker_escalation_status_board_closeout_ready",
    "p690_p0_real_input_blocker_escalation_status_board_completion_ready_observed",
    "p690_p0_real_input_blocker_escalation_status_board_completion_ready",
    "p690_p0_real_input_blocker_escalation_status_board_p0_unblocked",
    "p690_p0_real_input_blocker_escalation_status_board_p0_completion_ready",
    "p691_p0_real_input_blocker_escalation_watchlist_training_import_allowed",
    "p691_p0_real_input_blocker_escalation_watchlist_safe_for_training_import",
    "p691_p0_real_input_blocker_escalation_watchlist_safe_for_model_claim",
    "p691_p0_real_input_blocker_escalation_watchlist_customer_delivery_ready",
    "p691_p0_real_input_blocker_escalation_watchlist_release_ready",
    "p691_p0_real_input_blocker_escalation_watchlist_production_execution_allowed",
    "p691_p0_real_input_blocker_escalation_watchlist_escalation_sent",
    "p691_p0_real_input_blocker_escalation_watchlist_escalation_acknowledged",
    "p691_p0_real_input_blocker_escalation_watchlist_blocker_resolved",
    "p691_p0_real_input_blocker_escalation_watchlist_closeout_ready",
    "p691_p0_real_input_blocker_escalation_watchlist_completion_ready_observed",
    "p691_p0_real_input_blocker_escalation_watchlist_completion_ready",
    "p691_p0_real_input_blocker_escalation_watchlist_p0_unblocked",
    "p691_p0_real_input_blocker_escalation_watchlist_p0_completion_ready",
    "p692_p0_real_input_blocker_escalation_review_queue_training_import_allowed",
    "p692_p0_real_input_blocker_escalation_review_queue_safe_for_training_import",
    "p692_p0_real_input_blocker_escalation_review_queue_safe_for_model_claim",
    "p692_p0_real_input_blocker_escalation_review_queue_customer_delivery_ready",
    "p692_p0_real_input_blocker_escalation_review_queue_release_ready",
    "p692_p0_real_input_blocker_escalation_review_queue_production_execution_allowed",
    "p692_p0_real_input_blocker_escalation_review_queue_escalation_reviewed",
    "p692_p0_real_input_blocker_escalation_review_queue_escalation_sent",
    "p692_p0_real_input_blocker_escalation_review_queue_escalation_acknowledged",
    "p692_p0_real_input_blocker_escalation_review_queue_blocker_resolved",
    "p692_p0_real_input_blocker_escalation_review_queue_closeout_ready",
    "p692_p0_real_input_blocker_escalation_review_queue_completion_ready_observed",
    "p692_p0_real_input_blocker_escalation_review_queue_completion_ready",
    "p692_p0_real_input_blocker_escalation_review_queue_p0_unblocked",
    "p692_p0_real_input_blocker_escalation_review_queue_p0_completion_ready",
    "p693_p0_real_input_blocker_escalation_review_status_board_training_import_allowed",
    "p693_p0_real_input_blocker_escalation_review_status_board_safe_for_training_import",
    "p693_p0_real_input_blocker_escalation_review_status_board_safe_for_model_claim",
    "p693_p0_real_input_blocker_escalation_review_status_board_customer_delivery_ready",
    "p693_p0_real_input_blocker_escalation_review_status_board_release_ready",
    "p693_p0_real_input_blocker_escalation_review_status_board_production_execution_allowed",
    "p693_p0_real_input_blocker_escalation_review_status_board_escalation_reviewed",
    "p693_p0_real_input_blocker_escalation_review_status_board_escalation_sent",
    "p693_p0_real_input_blocker_escalation_review_status_board_escalation_acknowledged",
    "p693_p0_real_input_blocker_escalation_review_status_board_blocker_resolved",
    "p693_p0_real_input_blocker_escalation_review_status_board_closeout_ready",
    "p693_p0_real_input_blocker_escalation_review_status_board_completion_ready_observed",
    "p693_p0_real_input_blocker_escalation_review_status_board_completion_ready",
    "p693_p0_real_input_blocker_escalation_review_status_board_p0_unblocked",
    "p693_p0_real_input_blocker_escalation_review_status_board_p0_completion_ready",
    "p694_p0_real_input_blocker_escalation_review_watchlist_training_import_allowed",
    "p694_p0_real_input_blocker_escalation_review_watchlist_safe_for_training_import",
    "p694_p0_real_input_blocker_escalation_review_watchlist_safe_for_model_claim",
    "p694_p0_real_input_blocker_escalation_review_watchlist_customer_delivery_ready",
    "p694_p0_real_input_blocker_escalation_review_watchlist_release_ready",
    "p694_p0_real_input_blocker_escalation_review_watchlist_production_execution_allowed",
    "p694_p0_real_input_blocker_escalation_review_watchlist_escalation_reviewed",
    "p694_p0_real_input_blocker_escalation_review_watchlist_escalation_sent",
    "p694_p0_real_input_blocker_escalation_review_watchlist_escalation_acknowledged",
    "p694_p0_real_input_blocker_escalation_review_watchlist_blocker_resolved",
    "p694_p0_real_input_blocker_escalation_review_watchlist_closeout_ready",
    "p694_p0_real_input_blocker_escalation_review_watchlist_completion_ready_observed",
    "p694_p0_real_input_blocker_escalation_review_watchlist_completion_ready",
    "p694_p0_real_input_blocker_escalation_review_watchlist_p0_unblocked",
    "p694_p0_real_input_blocker_escalation_review_watchlist_p0_completion_ready",
    "p695_p0_real_input_blocker_escalation_review_watchlist_aging_audit_training_import_allowed",
    "p695_p0_real_input_blocker_escalation_review_watchlist_aging_audit_safe_for_training_import",
    "p695_p0_real_input_blocker_escalation_review_watchlist_aging_audit_safe_for_model_claim",
    "p695_p0_real_input_blocker_escalation_review_watchlist_aging_audit_customer_delivery_ready",
    "p695_p0_real_input_blocker_escalation_review_watchlist_aging_audit_release_ready",
    "p695_p0_real_input_blocker_escalation_review_watchlist_aging_audit_production_execution_allowed",
    "p695_p0_real_input_blocker_escalation_review_watchlist_aging_audit_aging_reviewed",
    "p695_p0_real_input_blocker_escalation_review_watchlist_aging_audit_staleness_resolved",
    "p695_p0_real_input_blocker_escalation_review_watchlist_aging_audit_escalation_reviewed",
    "p695_p0_real_input_blocker_escalation_review_watchlist_aging_audit_escalation_sent",
    "p695_p0_real_input_blocker_escalation_review_watchlist_aging_audit_escalation_acknowledged",
    "p695_p0_real_input_blocker_escalation_review_watchlist_aging_audit_blocker_resolved",
    "p695_p0_real_input_blocker_escalation_review_watchlist_aging_audit_closeout_ready",
    "p695_p0_real_input_blocker_escalation_review_watchlist_aging_audit_completion_ready_observed",
    "p695_p0_real_input_blocker_escalation_review_watchlist_aging_audit_completion_ready",
    "p695_p0_real_input_blocker_escalation_review_watchlist_aging_audit_p0_unblocked",
    "p695_p0_real_input_blocker_escalation_review_watchlist_aging_audit_p0_completion_ready",
    "p696_p0_real_input_blocker_escalation_review_owner_assignment_gap_audit_training_import_allowed",
    "p696_p0_real_input_blocker_escalation_review_owner_assignment_gap_audit_safe_for_training_import",
    "p696_p0_real_input_blocker_escalation_review_owner_assignment_gap_audit_safe_for_model_claim",
    "p696_p0_real_input_blocker_escalation_review_owner_assignment_gap_audit_customer_delivery_ready",
    "p696_p0_real_input_blocker_escalation_review_owner_assignment_gap_audit_release_ready",
    "p696_p0_real_input_blocker_escalation_review_owner_assignment_gap_audit_production_execution_allowed",
    "p696_p0_real_input_blocker_escalation_review_owner_assignment_gap_audit_owner_assigned",
    "p696_p0_real_input_blocker_escalation_review_owner_assignment_gap_audit_owner_acknowledged",
    "p696_p0_real_input_blocker_escalation_review_owner_assignment_gap_audit_aging_reviewed",
    "p696_p0_real_input_blocker_escalation_review_owner_assignment_gap_audit_staleness_resolved",
    "p696_p0_real_input_blocker_escalation_review_owner_assignment_gap_audit_escalation_reviewed",
    "p696_p0_real_input_blocker_escalation_review_owner_assignment_gap_audit_escalation_sent",
    "p696_p0_real_input_blocker_escalation_review_owner_assignment_gap_audit_escalation_acknowledged",
    "p696_p0_real_input_blocker_escalation_review_owner_assignment_gap_audit_blocker_resolved",
    "p696_p0_real_input_blocker_escalation_review_owner_assignment_gap_audit_closeout_ready",
    "p696_p0_real_input_blocker_escalation_review_owner_assignment_gap_audit_completion_ready_observed",
    "p696_p0_real_input_blocker_escalation_review_owner_assignment_gap_audit_completion_ready",
    "p696_p0_real_input_blocker_escalation_review_owner_assignment_gap_audit_p0_unblocked",
    "p696_p0_real_input_blocker_escalation_review_owner_assignment_gap_audit_p0_completion_ready",
    "p697_p0_real_input_blocker_escalation_review_evidence_missing_matrix_training_import_allowed",
    "p697_p0_real_input_blocker_escalation_review_evidence_missing_matrix_safe_for_training_import",
    "p697_p0_real_input_blocker_escalation_review_evidence_missing_matrix_safe_for_model_claim",
    "p697_p0_real_input_blocker_escalation_review_evidence_missing_matrix_customer_delivery_ready",
    "p697_p0_real_input_blocker_escalation_review_evidence_missing_matrix_release_ready",
    "p697_p0_real_input_blocker_escalation_review_evidence_missing_matrix_production_execution_allowed",
    "p697_p0_real_input_blocker_escalation_review_evidence_missing_matrix_evidence_received",
    "p697_p0_real_input_blocker_escalation_review_evidence_missing_matrix_evidence_validated",
    "p697_p0_real_input_blocker_escalation_review_evidence_missing_matrix_evidence_released",
    "p697_p0_real_input_blocker_escalation_review_evidence_missing_matrix_evidence_promoted_to_decision",
    "p697_p0_real_input_blocker_escalation_review_evidence_missing_matrix_owner_assigned",
    "p697_p0_real_input_blocker_escalation_review_evidence_missing_matrix_owner_acknowledged",
    "p697_p0_real_input_blocker_escalation_review_evidence_missing_matrix_aging_reviewed",
    "p697_p0_real_input_blocker_escalation_review_evidence_missing_matrix_staleness_resolved",
    "p697_p0_real_input_blocker_escalation_review_evidence_missing_matrix_escalation_reviewed",
    "p697_p0_real_input_blocker_escalation_review_evidence_missing_matrix_escalation_sent",
    "p697_p0_real_input_blocker_escalation_review_evidence_missing_matrix_escalation_acknowledged",
    "p697_p0_real_input_blocker_escalation_review_evidence_missing_matrix_blocker_resolved",
    "p697_p0_real_input_blocker_escalation_review_evidence_missing_matrix_closeout_ready",
    "p697_p0_real_input_blocker_escalation_review_evidence_missing_matrix_completion_ready_observed",
    "p697_p0_real_input_blocker_escalation_review_evidence_missing_matrix_completion_ready",
    "p697_p0_real_input_blocker_escalation_review_evidence_missing_matrix_p0_unblocked",
    "p697_p0_real_input_blocker_escalation_review_evidence_missing_matrix_p0_completion_ready",
    "p698_p0_real_input_formal_decision_readiness_false_positive_guard_training_import_allowed",
    "p698_p0_real_input_formal_decision_readiness_false_positive_guard_safe_for_training_import",
    "p698_p0_real_input_formal_decision_readiness_false_positive_guard_safe_for_model_claim",
    "p698_p0_real_input_formal_decision_readiness_false_positive_guard_customer_delivery_ready",
    "p698_p0_real_input_formal_decision_readiness_false_positive_guard_release_ready",
    "p698_p0_real_input_formal_decision_readiness_false_positive_guard_production_execution_allowed",
    "p698_p0_real_input_formal_decision_readiness_false_positive_guard_formal_decision_ready",
    "p698_p0_real_input_formal_decision_readiness_false_positive_guard_false_positive_cleared",
    "p698_p0_real_input_formal_decision_readiness_false_positive_guard_evidence_received",
    "p698_p0_real_input_formal_decision_readiness_false_positive_guard_evidence_validated",
    "p698_p0_real_input_formal_decision_readiness_false_positive_guard_owner_assigned",
    "p698_p0_real_input_formal_decision_readiness_false_positive_guard_owner_acknowledged",
    "p698_p0_real_input_formal_decision_readiness_false_positive_guard_aging_reviewed",
    "p698_p0_real_input_formal_decision_readiness_false_positive_guard_staleness_resolved",
    "p698_p0_real_input_formal_decision_readiness_false_positive_guard_escalation_reviewed",
    "p698_p0_real_input_formal_decision_readiness_false_positive_guard_escalation_sent",
    "p698_p0_real_input_formal_decision_readiness_false_positive_guard_escalation_acknowledged",
    "p698_p0_real_input_formal_decision_readiness_false_positive_guard_blocker_resolved",
    "p698_p0_real_input_formal_decision_readiness_false_positive_guard_closeout_ready",
    "p698_p0_real_input_formal_decision_readiness_false_positive_guard_completion_ready_observed",
    "p698_p0_real_input_formal_decision_readiness_false_positive_guard_completion_ready",
    "p698_p0_real_input_formal_decision_readiness_false_positive_guard_p0_unblocked",
    "p698_p0_real_input_formal_decision_readiness_false_positive_guard_p0_completion_ready",
})
REQUIRED_FALSE_RISK_SUMMARY_FIELDS.update({
    "p699_p0_real_input_formal_decision_readiness_status_board_training_import_allowed",
    "p699_p0_real_input_formal_decision_readiness_status_board_safe_for_training_import",
    "p699_p0_real_input_formal_decision_readiness_status_board_safe_for_model_claim",
    "p699_p0_real_input_formal_decision_readiness_status_board_customer_delivery_ready",
    "p699_p0_real_input_formal_decision_readiness_status_board_release_ready",
    "p699_p0_real_input_formal_decision_readiness_status_board_production_execution_allowed",
    "p699_p0_real_input_formal_decision_readiness_status_board_formal_decision_ready",
    "p699_p0_real_input_formal_decision_readiness_status_board_formal_decision_readiness_reviewed",
    "p699_p0_real_input_formal_decision_readiness_status_board_formal_decision_readiness_approved",
    "p699_p0_real_input_formal_decision_readiness_status_board_false_positive_cleared",
    "p699_p0_real_input_formal_decision_readiness_status_board_evidence_received",
    "p699_p0_real_input_formal_decision_readiness_status_board_evidence_validated",
    "p699_p0_real_input_formal_decision_readiness_status_board_owner_assigned",
    "p699_p0_real_input_formal_decision_readiness_status_board_owner_acknowledged",
    "p699_p0_real_input_formal_decision_readiness_status_board_aging_reviewed",
    "p699_p0_real_input_formal_decision_readiness_status_board_staleness_resolved",
    "p699_p0_real_input_formal_decision_readiness_status_board_escalation_reviewed",
    "p699_p0_real_input_formal_decision_readiness_status_board_escalation_sent",
    "p699_p0_real_input_formal_decision_readiness_status_board_escalation_acknowledged",
    "p699_p0_real_input_formal_decision_readiness_status_board_blocker_resolved",
    "p699_p0_real_input_formal_decision_readiness_status_board_closeout_ready",
    "p699_p0_real_input_formal_decision_readiness_status_board_completion_ready_observed",
    "p699_p0_real_input_formal_decision_readiness_status_board_completion_ready",
    "p699_p0_real_input_formal_decision_readiness_status_board_p0_unblocked",
    "p699_p0_real_input_formal_decision_readiness_status_board_p0_completion_ready",
})
REQUIRED_ZERO_RISK_SUMMARY_FIELDS.update({
    "p700_p0_real_input_pending_build_checklist_pending_build_ready_rows",
    "p700_p0_real_input_pending_build_checklist_formal_intake_dry_run_executed_rows",
    "p700_p0_real_input_pending_build_checklist_formal_intake_dry_run_passed_rows",
    "p687_p0_real_input_closeout_readiness_gate_queue_dequeued_rows",
    "p687_p0_real_input_closeout_readiness_gate_formal_intake_dry_run_executed_rows",
    "p687_p0_real_input_closeout_readiness_gate_formal_intake_dry_run_passed_rows",
    "p687_p0_real_input_closeout_readiness_gate_formal_intake_written_rows",
    "p687_p0_real_input_closeout_readiness_gate_response_received_rows",
    "p687_p0_real_input_closeout_readiness_gate_response_validated_rows",
    "p687_p0_real_input_closeout_readiness_gate_real_input_received_rows",
    "p687_p0_real_input_closeout_readiness_gate_reviewed_decision_written_rows",
    "p687_p0_real_input_closeout_readiness_gate_runtime_receipt_written_rows",
    "p687_p0_real_input_closeout_readiness_gate_training_label_written_rows",
    "p687_p0_real_input_closeout_readiness_gate_closeout_ready_rows",
    "p687_p0_real_input_closeout_readiness_gate_completion_ready_observed_rows",
    "p687_p0_real_input_closeout_readiness_gate_completion_ready_rows",
    "p688_p0_real_input_closeout_blocker_ledger_queue_dequeued_rows",
    "p688_p0_real_input_closeout_blocker_ledger_formal_intake_dry_run_executed_rows",
    "p688_p0_real_input_closeout_blocker_ledger_formal_intake_dry_run_passed_rows",
    "p688_p0_real_input_closeout_blocker_ledger_formal_intake_written_rows",
    "p688_p0_real_input_closeout_blocker_ledger_response_received_rows",
    "p688_p0_real_input_closeout_blocker_ledger_response_validated_rows",
    "p688_p0_real_input_closeout_blocker_ledger_real_input_received_rows",
    "p688_p0_real_input_closeout_blocker_ledger_reviewed_decision_written_rows",
    "p688_p0_real_input_closeout_blocker_ledger_runtime_receipt_written_rows",
    "p688_p0_real_input_closeout_blocker_ledger_training_label_written_rows",
    "p688_p0_real_input_closeout_blocker_ledger_blocker_resolved_rows",
    "p688_p0_real_input_closeout_blocker_ledger_closeout_ready_rows",
    "p688_p0_real_input_closeout_blocker_ledger_completion_ready_observed_rows",
    "p689_p0_real_input_blocker_escalation_queue_queue_dequeued_rows",
    "p689_p0_real_input_blocker_escalation_queue_formal_intake_dry_run_executed_rows",
    "p689_p0_real_input_blocker_escalation_queue_formal_intake_dry_run_passed_rows",
    "p689_p0_real_input_blocker_escalation_queue_formal_intake_written_rows",
    "p689_p0_real_input_blocker_escalation_queue_response_received_rows",
    "p689_p0_real_input_blocker_escalation_queue_response_validated_rows",
    "p689_p0_real_input_blocker_escalation_queue_real_input_received_rows",
    "p689_p0_real_input_blocker_escalation_queue_reviewed_decision_written_rows",
    "p689_p0_real_input_blocker_escalation_queue_runtime_receipt_written_rows",
    "p689_p0_real_input_blocker_escalation_queue_training_label_written_rows",
    "p689_p0_real_input_blocker_escalation_queue_escalation_sent_rows",
    "p689_p0_real_input_blocker_escalation_queue_escalation_acknowledged_rows",
    "p689_p0_real_input_blocker_escalation_queue_blocker_resolved_rows",
    "p689_p0_real_input_blocker_escalation_queue_closeout_ready_rows",
    "p689_p0_real_input_blocker_escalation_queue_completion_ready_observed_rows",
    "p690_p0_real_input_blocker_escalation_status_board_queue_dequeued_rows",
    "p690_p0_real_input_blocker_escalation_status_board_formal_intake_dry_run_executed_rows",
    "p690_p0_real_input_blocker_escalation_status_board_formal_intake_dry_run_passed_rows",
    "p690_p0_real_input_blocker_escalation_status_board_formal_intake_written_rows",
    "p690_p0_real_input_blocker_escalation_status_board_response_received_rows",
    "p690_p0_real_input_blocker_escalation_status_board_response_validated_rows",
    "p690_p0_real_input_blocker_escalation_status_board_real_input_received_rows",
    "p690_p0_real_input_blocker_escalation_status_board_reviewed_decision_written_rows",
    "p690_p0_real_input_blocker_escalation_status_board_runtime_receipt_written_rows",
    "p690_p0_real_input_blocker_escalation_status_board_training_label_written_rows",
    "p690_p0_real_input_blocker_escalation_status_board_escalation_sent_rows",
    "p690_p0_real_input_blocker_escalation_status_board_escalation_acknowledged_rows",
    "p690_p0_real_input_blocker_escalation_status_board_blocker_resolved_rows",
    "p690_p0_real_input_blocker_escalation_status_board_closeout_ready_rows",
    "p690_p0_real_input_blocker_escalation_status_board_completion_ready_observed_rows",
    "p691_p0_real_input_blocker_escalation_watchlist_queue_dequeued_rows",
    "p691_p0_real_input_blocker_escalation_watchlist_formal_intake_dry_run_executed_rows",
    "p691_p0_real_input_blocker_escalation_watchlist_formal_intake_dry_run_passed_rows",
    "p691_p0_real_input_blocker_escalation_watchlist_formal_intake_written_rows",
    "p691_p0_real_input_blocker_escalation_watchlist_response_received_rows",
    "p691_p0_real_input_blocker_escalation_watchlist_response_validated_rows",
    "p691_p0_real_input_blocker_escalation_watchlist_real_input_received_rows",
    "p691_p0_real_input_blocker_escalation_watchlist_reviewed_decision_written_rows",
    "p691_p0_real_input_blocker_escalation_watchlist_runtime_receipt_written_rows",
    "p691_p0_real_input_blocker_escalation_watchlist_training_label_written_rows",
    "p691_p0_real_input_blocker_escalation_watchlist_escalation_sent_rows",
    "p691_p0_real_input_blocker_escalation_watchlist_escalation_acknowledged_rows",
    "p691_p0_real_input_blocker_escalation_watchlist_blocker_resolved_rows",
    "p691_p0_real_input_blocker_escalation_watchlist_closeout_ready_rows",
    "p691_p0_real_input_blocker_escalation_watchlist_completion_ready_observed_rows",
    "p692_p0_real_input_blocker_escalation_review_queue_queue_dequeued_rows",
    "p692_p0_real_input_blocker_escalation_review_queue_formal_intake_dry_run_executed_rows",
    "p692_p0_real_input_blocker_escalation_review_queue_formal_intake_dry_run_passed_rows",
    "p692_p0_real_input_blocker_escalation_review_queue_formal_intake_written_rows",
    "p692_p0_real_input_blocker_escalation_review_queue_response_received_rows",
    "p692_p0_real_input_blocker_escalation_review_queue_response_validated_rows",
    "p692_p0_real_input_blocker_escalation_review_queue_real_input_received_rows",
    "p692_p0_real_input_blocker_escalation_review_queue_reviewed_decision_written_rows",
    "p692_p0_real_input_blocker_escalation_review_queue_runtime_receipt_written_rows",
    "p692_p0_real_input_blocker_escalation_review_queue_training_label_written_rows",
    "p692_p0_real_input_blocker_escalation_review_queue_escalation_reviewed_rows",
    "p692_p0_real_input_blocker_escalation_review_queue_escalation_sent_rows",
    "p692_p0_real_input_blocker_escalation_review_queue_escalation_acknowledged_rows",
    "p692_p0_real_input_blocker_escalation_review_queue_blocker_resolved_rows",
    "p692_p0_real_input_blocker_escalation_review_queue_closeout_ready_rows",
    "p692_p0_real_input_blocker_escalation_review_queue_completion_ready_observed_rows",
    "p693_p0_real_input_blocker_escalation_review_status_board_queue_dequeued_rows",
    "p693_p0_real_input_blocker_escalation_review_status_board_formal_intake_dry_run_executed_rows",
    "p693_p0_real_input_blocker_escalation_review_status_board_formal_intake_dry_run_passed_rows",
    "p693_p0_real_input_blocker_escalation_review_status_board_formal_intake_written_rows",
    "p693_p0_real_input_blocker_escalation_review_status_board_response_received_rows",
    "p693_p0_real_input_blocker_escalation_review_status_board_response_validated_rows",
    "p693_p0_real_input_blocker_escalation_review_status_board_real_input_received_rows",
    "p693_p0_real_input_blocker_escalation_review_status_board_reviewed_decision_written_rows",
    "p693_p0_real_input_blocker_escalation_review_status_board_runtime_receipt_written_rows",
    "p693_p0_real_input_blocker_escalation_review_status_board_training_label_written_rows",
    "p693_p0_real_input_blocker_escalation_review_status_board_escalation_reviewed_rows",
    "p693_p0_real_input_blocker_escalation_review_status_board_escalation_sent_rows",
    "p693_p0_real_input_blocker_escalation_review_status_board_escalation_acknowledged_rows",
    "p693_p0_real_input_blocker_escalation_review_status_board_blocker_resolved_rows",
    "p693_p0_real_input_blocker_escalation_review_status_board_closeout_ready_rows",
    "p693_p0_real_input_blocker_escalation_review_status_board_completion_ready_observed_rows",
    "p694_p0_real_input_blocker_escalation_review_watchlist_queue_dequeued_rows",
    "p694_p0_real_input_blocker_escalation_review_watchlist_formal_intake_dry_run_executed_rows",
    "p694_p0_real_input_blocker_escalation_review_watchlist_formal_intake_dry_run_passed_rows",
    "p694_p0_real_input_blocker_escalation_review_watchlist_formal_intake_written_rows",
    "p694_p0_real_input_blocker_escalation_review_watchlist_response_received_rows",
    "p694_p0_real_input_blocker_escalation_review_watchlist_response_validated_rows",
    "p694_p0_real_input_blocker_escalation_review_watchlist_real_input_received_rows",
    "p694_p0_real_input_blocker_escalation_review_watchlist_reviewed_decision_written_rows",
    "p694_p0_real_input_blocker_escalation_review_watchlist_runtime_receipt_written_rows",
    "p694_p0_real_input_blocker_escalation_review_watchlist_training_label_written_rows",
    "p694_p0_real_input_blocker_escalation_review_watchlist_escalation_reviewed_rows",
    "p694_p0_real_input_blocker_escalation_review_watchlist_escalation_sent_rows",
    "p694_p0_real_input_blocker_escalation_review_watchlist_escalation_acknowledged_rows",
    "p694_p0_real_input_blocker_escalation_review_watchlist_blocker_resolved_rows",
    "p694_p0_real_input_blocker_escalation_review_watchlist_closeout_ready_rows",
    "p694_p0_real_input_blocker_escalation_review_watchlist_completion_ready_observed_rows",
    "p695_p0_real_input_blocker_escalation_review_watchlist_aging_audit_queue_dequeued_rows",
    "p695_p0_real_input_blocker_escalation_review_watchlist_aging_audit_formal_intake_dry_run_executed_rows",
    "p695_p0_real_input_blocker_escalation_review_watchlist_aging_audit_formal_intake_dry_run_passed_rows",
    "p695_p0_real_input_blocker_escalation_review_watchlist_aging_audit_formal_intake_written_rows",
    "p695_p0_real_input_blocker_escalation_review_watchlist_aging_audit_response_received_rows",
    "p695_p0_real_input_blocker_escalation_review_watchlist_aging_audit_response_validated_rows",
    "p695_p0_real_input_blocker_escalation_review_watchlist_aging_audit_real_input_received_rows",
    "p695_p0_real_input_blocker_escalation_review_watchlist_aging_audit_reviewed_decision_written_rows",
    "p695_p0_real_input_blocker_escalation_review_watchlist_aging_audit_runtime_receipt_written_rows",
    "p695_p0_real_input_blocker_escalation_review_watchlist_aging_audit_training_label_written_rows",
    "p695_p0_real_input_blocker_escalation_review_watchlist_aging_audit_aging_reviewed_rows",
    "p695_p0_real_input_blocker_escalation_review_watchlist_aging_audit_staleness_resolved_rows",
    "p695_p0_real_input_blocker_escalation_review_watchlist_aging_audit_escalation_reviewed_rows",
    "p695_p0_real_input_blocker_escalation_review_watchlist_aging_audit_escalation_sent_rows",
    "p695_p0_real_input_blocker_escalation_review_watchlist_aging_audit_escalation_acknowledged_rows",
    "p695_p0_real_input_blocker_escalation_review_watchlist_aging_audit_blocker_resolved_rows",
    "p695_p0_real_input_blocker_escalation_review_watchlist_aging_audit_closeout_ready_rows",
    "p695_p0_real_input_blocker_escalation_review_watchlist_aging_audit_completion_ready_observed_rows",
    "p696_p0_real_input_blocker_escalation_review_owner_assignment_gap_audit_queue_dequeued_rows",
    "p696_p0_real_input_blocker_escalation_review_owner_assignment_gap_audit_formal_intake_dry_run_executed_rows",
    "p696_p0_real_input_blocker_escalation_review_owner_assignment_gap_audit_formal_intake_dry_run_passed_rows",
    "p696_p0_real_input_blocker_escalation_review_owner_assignment_gap_audit_formal_intake_written_rows",
    "p696_p0_real_input_blocker_escalation_review_owner_assignment_gap_audit_response_received_rows",
    "p696_p0_real_input_blocker_escalation_review_owner_assignment_gap_audit_response_validated_rows",
    "p696_p0_real_input_blocker_escalation_review_owner_assignment_gap_audit_real_input_received_rows",
    "p696_p0_real_input_blocker_escalation_review_owner_assignment_gap_audit_reviewed_decision_written_rows",
    "p696_p0_real_input_blocker_escalation_review_owner_assignment_gap_audit_runtime_receipt_written_rows",
    "p696_p0_real_input_blocker_escalation_review_owner_assignment_gap_audit_training_label_written_rows",
    "p696_p0_real_input_blocker_escalation_review_owner_assignment_gap_audit_owner_assigned_rows",
    "p696_p0_real_input_blocker_escalation_review_owner_assignment_gap_audit_owner_acknowledged_rows",
    "p696_p0_real_input_blocker_escalation_review_owner_assignment_gap_audit_aging_reviewed_rows",
    "p696_p0_real_input_blocker_escalation_review_owner_assignment_gap_audit_staleness_resolved_rows",
    "p696_p0_real_input_blocker_escalation_review_owner_assignment_gap_audit_escalation_reviewed_rows",
    "p696_p0_real_input_blocker_escalation_review_owner_assignment_gap_audit_escalation_sent_rows",
    "p696_p0_real_input_blocker_escalation_review_owner_assignment_gap_audit_escalation_acknowledged_rows",
    "p696_p0_real_input_blocker_escalation_review_owner_assignment_gap_audit_blocker_resolved_rows",
    "p696_p0_real_input_blocker_escalation_review_owner_assignment_gap_audit_closeout_ready_rows",
    "p696_p0_real_input_blocker_escalation_review_owner_assignment_gap_audit_completion_ready_observed_rows",
    "p697_p0_real_input_blocker_escalation_review_evidence_missing_matrix_queue_dequeued_rows",
    "p697_p0_real_input_blocker_escalation_review_evidence_missing_matrix_formal_intake_dry_run_executed_rows",
    "p697_p0_real_input_blocker_escalation_review_evidence_missing_matrix_formal_intake_dry_run_passed_rows",
    "p697_p0_real_input_blocker_escalation_review_evidence_missing_matrix_formal_intake_written_rows",
    "p697_p0_real_input_blocker_escalation_review_evidence_missing_matrix_response_received_rows",
    "p697_p0_real_input_blocker_escalation_review_evidence_missing_matrix_response_validated_rows",
    "p697_p0_real_input_blocker_escalation_review_evidence_missing_matrix_real_input_received_rows",
    "p697_p0_real_input_blocker_escalation_review_evidence_missing_matrix_reviewed_decision_written_rows",
    "p697_p0_real_input_blocker_escalation_review_evidence_missing_matrix_runtime_receipt_written_rows",
    "p697_p0_real_input_blocker_escalation_review_evidence_missing_matrix_training_label_written_rows",
    "p697_p0_real_input_blocker_escalation_review_evidence_missing_matrix_evidence_received_rows",
    "p697_p0_real_input_blocker_escalation_review_evidence_missing_matrix_evidence_validated_rows",
    "p697_p0_real_input_blocker_escalation_review_evidence_missing_matrix_evidence_released_rows",
    "p697_p0_real_input_blocker_escalation_review_evidence_missing_matrix_evidence_promoted_to_decision_rows",
    "p697_p0_real_input_blocker_escalation_review_evidence_missing_matrix_owner_assigned_rows",
    "p697_p0_real_input_blocker_escalation_review_evidence_missing_matrix_owner_acknowledged_rows",
    "p697_p0_real_input_blocker_escalation_review_evidence_missing_matrix_aging_reviewed_rows",
    "p697_p0_real_input_blocker_escalation_review_evidence_missing_matrix_staleness_resolved_rows",
    "p697_p0_real_input_blocker_escalation_review_evidence_missing_matrix_escalation_reviewed_rows",
    "p697_p0_real_input_blocker_escalation_review_evidence_missing_matrix_escalation_sent_rows",
    "p697_p0_real_input_blocker_escalation_review_evidence_missing_matrix_escalation_acknowledged_rows",
    "p697_p0_real_input_blocker_escalation_review_evidence_missing_matrix_blocker_resolved_rows",
    "p697_p0_real_input_blocker_escalation_review_evidence_missing_matrix_closeout_ready_rows",
    "p697_p0_real_input_blocker_escalation_review_evidence_missing_matrix_completion_ready_observed_rows",
    "p698_p0_real_input_formal_decision_readiness_false_positive_guard_queue_dequeued_rows",
    "p698_p0_real_input_formal_decision_readiness_false_positive_guard_formal_intake_dry_run_executed_rows",
    "p698_p0_real_input_formal_decision_readiness_false_positive_guard_formal_intake_dry_run_passed_rows",
    "p698_p0_real_input_formal_decision_readiness_false_positive_guard_formal_intake_written_rows",
    "p698_p0_real_input_formal_decision_readiness_false_positive_guard_response_received_rows",
    "p698_p0_real_input_formal_decision_readiness_false_positive_guard_response_validated_rows",
    "p698_p0_real_input_formal_decision_readiness_false_positive_guard_real_input_received_rows",
    "p698_p0_real_input_formal_decision_readiness_false_positive_guard_reviewed_decision_written_rows",
    "p698_p0_real_input_formal_decision_readiness_false_positive_guard_runtime_receipt_written_rows",
    "p698_p0_real_input_formal_decision_readiness_false_positive_guard_training_label_written_rows",
    "p698_p0_real_input_formal_decision_readiness_false_positive_guard_formal_decision_ready_rows",
    "p698_p0_real_input_formal_decision_readiness_false_positive_guard_false_positive_cleared_rows",
    "p698_p0_real_input_formal_decision_readiness_false_positive_guard_evidence_received_rows",
    "p698_p0_real_input_formal_decision_readiness_false_positive_guard_evidence_validated_rows",
    "p698_p0_real_input_formal_decision_readiness_false_positive_guard_owner_assigned_rows",
    "p698_p0_real_input_formal_decision_readiness_false_positive_guard_owner_acknowledged_rows",
    "p698_p0_real_input_formal_decision_readiness_false_positive_guard_aging_reviewed_rows",
    "p698_p0_real_input_formal_decision_readiness_false_positive_guard_staleness_resolved_rows",
    "p698_p0_real_input_formal_decision_readiness_false_positive_guard_escalation_reviewed_rows",
    "p698_p0_real_input_formal_decision_readiness_false_positive_guard_escalation_sent_rows",
    "p698_p0_real_input_formal_decision_readiness_false_positive_guard_escalation_acknowledged_rows",
    "p698_p0_real_input_formal_decision_readiness_false_positive_guard_blocker_resolved_rows",
    "p698_p0_real_input_formal_decision_readiness_false_positive_guard_closeout_ready_rows",
    "p698_p0_real_input_formal_decision_readiness_false_positive_guard_completion_ready_observed_rows",
})
REQUIRED_ZERO_RISK_SUMMARY_FIELDS.update({
    "p699_p0_real_input_formal_decision_readiness_status_board_queue_dequeued_rows",
    "p699_p0_real_input_formal_decision_readiness_status_board_formal_intake_dry_run_executed_rows",
    "p699_p0_real_input_formal_decision_readiness_status_board_formal_intake_dry_run_passed_rows",
    "p699_p0_real_input_formal_decision_readiness_status_board_formal_intake_written_rows",
    "p699_p0_real_input_formal_decision_readiness_status_board_response_received_rows",
    "p699_p0_real_input_formal_decision_readiness_status_board_response_validated_rows",
    "p699_p0_real_input_formal_decision_readiness_status_board_real_input_received_rows",
    "p699_p0_real_input_formal_decision_readiness_status_board_reviewed_decision_written_rows",
    "p699_p0_real_input_formal_decision_readiness_status_board_runtime_receipt_written_rows",
    "p699_p0_real_input_formal_decision_readiness_status_board_training_label_written_rows",
    "p699_p0_real_input_formal_decision_readiness_status_board_formal_decision_ready_rows",
    "p699_p0_real_input_formal_decision_readiness_status_board_formal_decision_readiness_reviewed_rows",
    "p699_p0_real_input_formal_decision_readiness_status_board_formal_decision_readiness_approved_rows",
    "p699_p0_real_input_formal_decision_readiness_status_board_false_positive_cleared_rows",
    "p699_p0_real_input_formal_decision_readiness_status_board_evidence_received_rows",
    "p699_p0_real_input_formal_decision_readiness_status_board_evidence_validated_rows",
    "p699_p0_real_input_formal_decision_readiness_status_board_owner_assigned_rows",
    "p699_p0_real_input_formal_decision_readiness_status_board_owner_acknowledged_rows",
    "p699_p0_real_input_formal_decision_readiness_status_board_aging_reviewed_rows",
    "p699_p0_real_input_formal_decision_readiness_status_board_staleness_resolved_rows",
    "p699_p0_real_input_formal_decision_readiness_status_board_escalation_reviewed_rows",
    "p699_p0_real_input_formal_decision_readiness_status_board_escalation_sent_rows",
    "p699_p0_real_input_formal_decision_readiness_status_board_escalation_acknowledged_rows",
    "p699_p0_real_input_formal_decision_readiness_status_board_blocker_resolved_rows",
    "p699_p0_real_input_formal_decision_readiness_status_board_closeout_ready_rows",
    "p699_p0_real_input_formal_decision_readiness_status_board_completion_ready_observed_rows",
})

HIGH_RISK_SUMMARY_TOKENS = {
    "safe_for_model_claim",
    "release_ready",
    "production_execution_allowed",
    "production_allowed",
    "customer_delivery",
    "selected_variant",
    "formal_decision",
    "training_execution",
}

AUDITED_SOURCE_BOUND_RISK_SUMMARY_FIELDS = {
    "five_head_training_execution_import_eligible_rows",
    "five_head_training_execution_total_rows",
    "five_head_training_execution_validation_success",
    "human_review_closeout_total_formal_decision_rows",
    "next_hard_gate_attack_wave_formal_decision_written_rows",
    "p479_customer_delivery_readiness_gap_audit_blocker_rows",
    "p479_customer_delivery_readiness_gap_audit_failed_checks",
    "p479_customer_delivery_readiness_gap_audit_rows",
    "p479_customer_delivery_readiness_gap_audit_validation_success",
    "p566_five_head_training_execution_boundary_gap_audit_ready_head_count",
    "p566_five_head_training_execution_boundary_gap_audit_training_execution_allowed",
    "p566_five_head_training_execution_boundary_gap_audit_validation_success",
    "p606_activity_risk_formal_label_boundary_audit_safe_for_model_claim",
    "p606_activity_risk_formal_label_boundary_audit_safe_for_training_import",
    "p606_activity_risk_formal_label_boundary_formal_decision_rows",
    "p606_activity_risk_formal_label_boundary_ready_for_training_import_rows",
    "p606_activity_risk_formal_label_boundary_validation_success",
    "p607_activity_risk_training_lineage_boundary_audit_safe_for_model_claim",
    "p607_activity_risk_training_lineage_boundary_import_eligible_rows",
    "p607_activity_risk_training_lineage_boundary_ledger_rows",
    "p607_activity_risk_training_lineage_boundary_training_execution_allowed",
    "p607_activity_risk_training_lineage_boundary_validation_success",
    "p608_feedback_training_import_guard_boundary_audit_safe_for_model_claim",
    "p608_feedback_training_import_guard_boundary_claim_eligible_rows",
    "p608_feedback_training_import_guard_boundary_numeric_eligible_rows",
    "p663_p0_formal_decision_readiness_false_positive_guard_formal_decision_false_positive_guard_rows",
    "p663_p0_formal_decision_readiness_false_positive_guard_open_formal_decision_false_positive_guard_rows",
    "p663_p0_formal_decision_readiness_false_positive_guard_empty_formal_decision_false_positive_guard_rows",
    "p663_p0_formal_decision_readiness_false_positive_guard_blocked_formal_decision_false_positive_guard_rows",
    "p698_p0_real_input_formal_decision_readiness_false_positive_guard_formal_decision_false_positive_guard_rows",
    "p698_p0_real_input_formal_decision_readiness_false_positive_guard_open_formal_decision_false_positive_guard_rows",
    "p698_p0_real_input_formal_decision_readiness_false_positive_guard_empty_formal_decision_false_positive_guard_rows",
    "p698_p0_real_input_formal_decision_readiness_false_positive_guard_blocked_formal_decision_false_positive_guard_rows",
    "p699_p0_real_input_formal_decision_readiness_status_board_formal_decision_readiness_status_board_rows",
    "p699_p0_real_input_formal_decision_readiness_status_board_open_formal_decision_readiness_status_board_rows",
    "p699_p0_real_input_formal_decision_readiness_status_board_empty_formal_decision_readiness_status_board_rows",
    "p699_p0_real_input_formal_decision_readiness_status_board_blocked_formal_decision_readiness_status_board_rows",
    "p699_p0_real_input_formal_decision_readiness_status_board_validation_success",
    "p700_p0_real_input_pending_build_checklist_pending_build_checklist_rows",
    "p700_p0_real_input_pending_build_checklist_open_pending_build_rows",
    "p700_p0_real_input_pending_build_checklist_empty_pending_build_rows",
    "p700_p0_real_input_pending_build_checklist_blocked_pending_build_rows",
    "p700_p0_real_input_pending_build_checklist_validation_success",
    "p672_p0_customer_delivery_non_authorization_guard_audit_customer_delivery_non_authorization_guard_rows",
    "p672_p0_customer_delivery_non_authorization_guard_audit_open_customer_delivery_non_authorization_guard_rows",
    "p672_p0_customer_delivery_non_authorization_guard_audit_empty_customer_delivery_non_authorization_guard_rows",
    "p672_p0_customer_delivery_non_authorization_guard_audit_blocked_customer_delivery_non_authorization_guard_rows",
    "p673_p0_production_execution_non_authorization_guard_audit_production_execution_non_authorization_guard_rows",
    "p673_p0_production_execution_non_authorization_guard_audit_open_production_execution_non_authorization_guard_rows",
    "p673_p0_production_execution_non_authorization_guard_audit_empty_production_execution_non_authorization_guard_rows",
    "p673_p0_production_execution_non_authorization_guard_audit_blocked_production_execution_non_authorization_guard_rows",
    "p608_feedback_training_import_guard_boundary_strict_supervised_rows",
    "p608_feedback_training_import_guard_boundary_validation_success",
    "p609_wet_lab_feedback_import_reconciliation_boundary_audit_safe_for_model_claim",
    "p609_wet_lab_feedback_import_reconciliation_boundary_claim_eligible_rows",
    "p609_wet_lab_feedback_import_reconciliation_boundary_contract_eligible_rows",
    "p609_wet_lab_feedback_import_reconciliation_boundary_model_quality_import_rows",
    "p609_wet_lab_feedback_import_reconciliation_boundary_validation_success",
    "p610_positive_claim_gate_quarantine_boundary_audit_safe_for_model_claim",
    "p610_positive_claim_gate_quarantine_boundary_audit_safe_for_training_import",
    "p610_positive_claim_gate_quarantine_boundary_disallowed_true_hit_count",
    "p610_positive_claim_gate_quarantine_boundary_scanned_report_count",
    "p610_positive_claim_gate_quarantine_boundary_validation_success",
    "p611_activity_risk_import_label_boundary_audit_safe_for_model_claim",
    "p611_activity_risk_import_label_boundary_label_rows",
    "p611_activity_risk_import_label_boundary_training_execution_allowed",
    "p611_activity_risk_import_label_boundary_validation_success",
    "p611_activity_risk_import_label_boundary_written_rows",
    "p612_activity_risk_replicate_preflight_boundary_audit_safe_for_model_claim",
    "p612_activity_risk_replicate_preflight_boundary_formal_decision_rows",
    "p612_activity_risk_replicate_preflight_boundary_preflight_rows",
    "p612_activity_risk_replicate_preflight_boundary_ready_for_training_import_rows",
    "p612_activity_risk_replicate_preflight_boundary_validation_success",
    "p613_feature_coverage_by_head_group_boundary_audit_safe_for_model_claim",
    "p613_feature_coverage_by_head_group_boundary_coverage_rows",
    "p613_feature_coverage_by_head_group_boundary_feature_rows_counted_as_labels",
    "p613_feature_coverage_by_head_group_boundary_training_execution_allowed",
    "p613_feature_coverage_by_head_group_boundary_training_label_source_rows",
    "p613_feature_coverage_by_head_group_boundary_validation_success",
    "p614_feature_coverage_gap_queue_boundary_audit_safe_for_model_claim",
    "p614_feature_coverage_gap_queue_boundary_feature_rows_counted_as_labels",
    "p614_feature_coverage_gap_queue_boundary_gap_count",
    "p614_feature_coverage_gap_queue_boundary_training_label_source_rows",
    "p614_feature_coverage_gap_queue_boundary_validation_success",
    "p615_feature_label_boundary_quarantine_audit_excluded_from_index_artifacts",
    "p615_feature_label_boundary_quarantine_audit_label_contaminated_artifacts",
    "p615_feature_label_boundary_quarantine_audit_label_contaminated_records",
    "p615_feature_label_boundary_quarantine_audit_safe_for_model_claim",
    "p615_feature_label_boundary_quarantine_validation_success",
    "p616_benchmark_score_cache_validation_boundary_audit_safe_for_model_claim",
    "p616_benchmark_score_cache_validation_boundary_benchmark_rows",
    "p616_benchmark_score_cache_validation_boundary_heads_ready",
    "p616_benchmark_score_cache_validation_boundary_invalid_rows",
    "p616_benchmark_score_cache_validation_boundary_ready_for_model_claim",
    "p616_benchmark_score_cache_validation_boundary_valid_rows",
    "p616_benchmark_score_cache_validation_boundary_validation_success",
    "p617_benchmark_coverage_dashboard_boundary_audit_safe_for_model_claim",
    "p617_benchmark_coverage_dashboard_boundary_benchmark_rows",
    "p617_benchmark_coverage_dashboard_boundary_heads_ready",
    "p617_benchmark_coverage_dashboard_boundary_invalid_rows",
    "p617_benchmark_coverage_dashboard_boundary_ready_for_model_claim",
    "p617_benchmark_coverage_dashboard_boundary_valid_rows",
    "p617_benchmark_coverage_dashboard_boundary_validation_success",
    "p618_five_head_benchmark_gap_plan_boundary_action_rows",
    "p618_five_head_benchmark_gap_plan_boundary_audit_safe_for_model_claim",
    "p618_five_head_benchmark_gap_plan_boundary_cache_validated_benchmarks",
    "p618_five_head_benchmark_gap_plan_boundary_heads_with_complete_scorecards",
    "p618_five_head_benchmark_gap_plan_boundary_ready_for_model_claim",
    "p618_five_head_benchmark_gap_plan_boundary_required_benchmarks",
    "p618_five_head_benchmark_gap_plan_boundary_validation_success",
    "p619_benchmark_lane_machine_prereview_boundary_audit_safe_for_model_claim",
    "p619_benchmark_lane_machine_prereview_boundary_formal_decision_rows_observed",
    "p619_benchmark_lane_machine_prereview_boundary_lane_count",
    "p619_benchmark_lane_machine_prereview_boundary_training_import_written_rows",
    "p619_benchmark_lane_machine_prereview_boundary_validation_success",
    "p620_benchmark_lane_status_aggregate_boundary_audit_safe_for_model_claim",
    "p620_benchmark_lane_status_aggregate_boundary_claim_release_gate",
    "p620_benchmark_lane_status_aggregate_boundary_lane_count",
    "p620_benchmark_lane_status_aggregate_boundary_training_import_written_rows",
    "p620_benchmark_lane_status_aggregate_boundary_validation_success",
    "p621_ddg_executable_probe_boundary_audit_safe_for_model_claim",
    "p621_ddg_executable_probe_boundary_backend_rows",
    "p621_ddg_executable_probe_boundary_claim_eligible_rows",
    "p621_ddg_executable_probe_boundary_ddg_smoke_job_executed",
    "p621_ddg_executable_probe_boundary_physics_ddg_ready",
    "p621_ddg_executable_probe_boundary_ready_for_execution_rows",
    "p621_ddg_executable_probe_boundary_validation_success",
    "p622_pyrosetta_physical_smoke_boundary_audit_safe_for_model_claim",
    "p622_pyrosetta_physical_smoke_boundary_ddg_table_rows",
    "p622_pyrosetta_physical_smoke_boundary_manual_review_required_rows",
    "p622_pyrosetta_physical_smoke_boundary_physical_smoke_passed",
    "p622_pyrosetta_physical_smoke_boundary_training_label_rows",
    "p622_pyrosetta_physical_smoke_boundary_validation_success",
    "p623_pyrosetta_verified_ddg_feature_boundary_audit_safe_for_model_claim",
    "p623_pyrosetta_verified_ddg_feature_boundary_computed_feature_rows",
    "p623_pyrosetta_verified_ddg_feature_boundary_quality_blocked_rows",
    "p623_pyrosetta_verified_ddg_feature_boundary_quality_passed_rows",
    "p623_pyrosetta_verified_ddg_feature_boundary_scientific_validity_claim",
    "p623_pyrosetta_verified_ddg_feature_boundary_validation_success",
    "p624_foldx_physical_smoke_boundary_audit_safe_for_model_claim",
    "p624_foldx_physical_smoke_boundary_blocker_count",
    "p624_foldx_physical_smoke_boundary_physical_smoke_passed",
    "p624_foldx_physical_smoke_boundary_ready_execution_plan_rows",
    "p624_foldx_physical_smoke_boundary_runtime_receipt_ready",
    "p624_foldx_physical_smoke_boundary_validation_success",
    "p625_ddg_backend_operator_packet_boundary_audit_safe_for_model_claim",
    "p625_ddg_backend_operator_packet_boundary_completion_ready_rows",
    "p625_ddg_backend_operator_packet_boundary_packet_rows",
    "p625_ddg_backend_operator_packet_boundary_ready_for_execution_rows",
    "p625_ddg_backend_operator_packet_boundary_requires_human_input_rows",
    "p625_ddg_backend_operator_packet_boundary_validation_success",
    "p626_rosetta_physical_smoke_boundary_audit_safe_for_model_claim",
    "p626_rosetta_physical_smoke_boundary_artifact_count",
    "p626_rosetta_physical_smoke_boundary_ddg_protocol_executed",
    "p626_rosetta_physical_smoke_boundary_physical_smoke_passed",
    "p626_rosetta_physical_smoke_boundary_validation_success",
    "p627_pyrosetta_concordance_boundary_audit_safe_for_model_claim",
    "p627_pyrosetta_concordance_boundary_input_feature_rows",
    "p627_pyrosetta_concordance_boundary_multi_chain_candidate_rows",
    "p627_pyrosetta_concordance_boundary_quality_blocked_rows",
    "p627_pyrosetta_concordance_boundary_quality_gate_status",
    "p627_pyrosetta_concordance_boundary_quality_passed_rows",
    "p627_pyrosetta_concordance_boundary_validation_success",
    "p628_pyrosetta_install_probe_boundary_approved_for_physical_ddg_runtime",
    "p628_pyrosetta_install_probe_boundary_audit_safe_for_model_claim",
    "p628_pyrosetta_install_probe_boundary_import_succeeded",
    "p628_pyrosetta_install_probe_boundary_module_spec_available",
    "p628_pyrosetta_install_probe_boundary_physics_ddg_ready",
    "p628_pyrosetta_install_probe_boundary_validation_success",
    "p628_pyrosetta_install_probe_boundary_wheel_present",
    "p629_ddg_runtime_preflight_boundary_approved_runtime_receipt_rows",
    "p629_ddg_runtime_preflight_boundary_audit_safe_for_model_claim",
    "p629_ddg_runtime_preflight_boundary_blocked_backend_rows",
    "p629_ddg_runtime_preflight_boundary_capability_status",
    "p629_ddg_runtime_preflight_boundary_physical_backend_rows",
    "p629_ddg_runtime_preflight_boundary_ready_backend_rows",
    "p629_ddg_runtime_preflight_boundary_safe_pipeline_manifest_connected",
    "p629_ddg_runtime_preflight_boundary_validation_success",
    "p630_ddg_runtime_receipt_boundary_all_physical_backends_ready",
    "p630_ddg_runtime_receipt_boundary_approved_runtime_rows",
    "p630_ddg_runtime_receipt_boundary_audit_safe_for_model_claim",
    "p630_ddg_runtime_receipt_boundary_capability_status",
    "p630_ddg_runtime_receipt_boundary_missing_backend_rows",
    "p630_ddg_runtime_receipt_boundary_receipt_rows",
    "p630_ddg_runtime_receipt_boundary_valid_receipt_rows",
    "p630_ddg_runtime_receipt_boundary_validation_success",
    "p631_ddg_physical_smoke_harness_boundary_contract_rows",
    "p631_ddg_physical_smoke_harness_boundary_passed_rows",
    "p631_ddg_physical_smoke_harness_boundary_can_execute_now_rows",
    "p631_ddg_physical_smoke_harness_boundary_ready_execution_plan_rows",
    "p631_ddg_physical_smoke_harness_boundary_physics_ddg_ready_observed",
    "p631_ddg_physical_smoke_harness_boundary_audit_safe_for_model_claim",
    "p631_ddg_physical_smoke_harness_boundary_validation_success",
    "p632_ddg_proxy_physics_claim_boundary_proxy_backend_ready",
    "p632_ddg_proxy_physics_claim_boundary_proxy_is_physics",
    "p632_ddg_proxy_physics_claim_boundary_physics_ddg_ready",
    "p632_ddg_proxy_physics_claim_boundary_audit_safe_for_model_claim",
    "p632_ddg_proxy_physics_claim_boundary_validation_success",
    "p633_execution_receipt_freshness_boundary_total_receipts",
    "p633_execution_receipt_freshness_boundary_stale_receipts",
    "p633_execution_receipt_freshness_boundary_missing_artifacts",
    "p633_execution_receipt_freshness_boundary_receipts_without_hash_fields",
    "p633_execution_receipt_freshness_boundary_audit_safe_for_model_claim",
    "p633_execution_receipt_freshness_boundary_validation_success",
    "p634_parallel_hard_gate_execution_boundary_receipt_rows",
    "p634_parallel_hard_gate_execution_boundary_eligibility_changed_rows",
    "p634_parallel_hard_gate_execution_boundary_formal_decision_written_rows",
    "p634_parallel_hard_gate_execution_boundary_training_import_written_rows",
    "p634_parallel_hard_gate_execution_boundary_audit_safe_for_model_claim",
    "p634_parallel_hard_gate_execution_boundary_validation_success",
    "p635_ddg_backend_failure_boundary_capability_status",
    "p635_ddg_backend_failure_boundary_physics_ddg_ready",
    "p635_ddg_backend_failure_boundary_ready_backend_count",
    "p635_ddg_backend_failure_boundary_proxy_is_physics",
    "p635_ddg_backend_failure_boundary_training_labels_written",
    "p635_ddg_backend_failure_boundary_audit_safe_for_model_claim",
    "p635_ddg_backend_failure_boundary_validation_success",
    "p637_operator_work_receipt_manifest_current_boundary_release_ready",
    "p637_operator_work_receipt_manifest_current_boundary_validation_success",
    "p638_top_tier_ready_to_verify_current_boundary_release_ready",
    "p638_top_tier_ready_to_verify_current_boundary_safe_for_training_import",
    "p638_top_tier_ready_to_verify_current_boundary_audit_safe_for_model_claim",
    "p638_top_tier_ready_to_verify_current_boundary_validation_success",
    "p639_non_human_ready_to_verify_current_boundary_release_ready",
    "p639_non_human_ready_to_verify_current_boundary_safe_for_training_import",
    "p639_non_human_ready_to_verify_current_boundary_audit_safe_for_model_claim",
    "p639_non_human_ready_to_verify_current_boundary_validation_success",
    "p640_ready_to_verify_promotion_current_boundary_release_ready",
    "p640_ready_to_verify_promotion_current_boundary_safe_for_training_import",
    "p640_ready_to_verify_promotion_current_boundary_audit_safe_for_model_claim",
    "p640_ready_to_verify_promotion_current_boundary_validation_success",
    "p698_p0_real_input_formal_decision_readiness_false_positive_guard_validation_success",
    "p699_p0_real_input_formal_decision_readiness_status_board_validation_success",
    "p642_p0_external_input_packet_manifest_validation_success",
    "p643_p0_external_input_dispatch_board_validation_success",
    "p644_p0_external_input_handoff_receipt_board_validation_success",
    "p645_p0_external_input_response_slot_registry_validation_success",
    "p646_p0_external_input_response_intake_queue_validation_success",
    "p647_p0_external_input_response_validation_preflight_validation_success",
    "p648_p0_external_input_response_schema_contract_validation_success",
    "p649_p0_external_input_response_evidence_quarantine_validation_success",
    "p650_p0_external_input_response_decision_routing_validation_success",
    "p651_p0_external_input_formal_intake_dry_run_guard_validation_success",
    "p652_p0_external_input_closeout_readiness_gate_validation_success",
    "p653_p0_external_input_closeout_blocker_ledger_validation_success",
    "p654_p0_external_input_blocker_escalation_queue_validation_success",
    "p655_p0_external_input_blocker_escalation_status_board_validation_success",
    "p656_p0_external_input_blocker_escalation_watchlist_validation_success",
    "p657_p0_external_input_blocker_escalation_review_queue_validation_success",
    "p658_p0_external_input_blocker_escalation_review_status_board_validation_success",
    "p659_p0_external_input_blocker_escalation_review_watchlist_validation_success",
    "p660_p0_external_input_blocker_review_watchlist_aging_audit_validation_success",
    "p661_p0_external_input_blocker_review_owner_assignment_gap_audit_validation_success",
    "p662_p0_external_input_evidence_missing_matrix_validation_success",
    "p663_p0_formal_decision_readiness_false_positive_guard_validation_success",
    "p664_p0_closeout_non_approval_receipt_audit_validation_success",
    "p665_p0_closeout_non_approval_watchlist_validation_success",
    "p666_p0_closeout_owner_review_queue_validation_success",
    "p667_p0_formal_intake_non_write_guard_audit_validation_success",
    "p668_p0_training_label_non_import_guard_audit_validation_success",
    "p669_p0_release_claim_non_promotion_guard_audit_validation_success",
    "p670_p0_release_claim_non_promotion_status_board_validation_success",
    "p671_p0_model_claim_non_assertion_guard_audit_validation_success",
    "p672_p0_customer_delivery_non_authorization_guard_audit_validation_success",
    "p673_p0_production_execution_non_authorization_guard_audit_validation_success",
    "p674_p0_terminal_blocked_state_rollup_audit_validation_success",
    "p641_p0_today_closeout_plan_p0_local_closeout_package_ready",
    "p641_p0_today_closeout_plan_validation_success",
    "p605_review_draft_formal_boundary_drafts_counted_as_formal_decisions",
    "parallel_hard_gate_execution_receipts_formal_decision_written_rows",
    "review_draft_formal_decision_rows",
    "review_draft_rows_counted_as_formal_decisions",
}

REQUIRED_BLOCKED_CAPABILITIES = {
    "model_quality_claim",
    "customer_delivery",
    "approved_for_ordering",
    "IP/FTO conclusion",
    "external tool production use",
    "advanced feature cache execution",
}

REQUIRED_LIVE_VOLATILE_PATHS = {
    "reports/safe_training_pipeline_run.json",
    "reports/data_lake_live_content_integrity_validation_report.json",
}


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def load_json_snapshot(path: Path) -> tuple[dict[str, Any], Optional[str]]:
    if not path.is_file():
        return {}, None
    raw = path.read_bytes()
    data = json.loads(raw.decode("utf-8"))
    return data, hashlib.sha256(raw).hexdigest()


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def fsync_directory(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def write_json_atomic(path: Path, payload: dict[str, Any], *, fail_before_replace: bool = False) -> None:
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
        if fail_before_replace:
            raise RuntimeError("simulated_local_release_consistency_receipt_failure_before_replace")
        os.replace(temp_path, path)
        fsync_directory(path.parent)
    finally:
        if temp_path.exists():
            temp_path.unlink()


def acquire_receipt_lock(path: Path, timeout_seconds: float):
    path.parent.mkdir(parents=True, exist_ok=True)
    handle = path.open("a+")
    deadline = time.monotonic() + max(timeout_seconds, 0.0)
    while True:
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            handle.seek(0)
            handle.truncate()
            handle.write(f"pid={os.getpid()}\n")
            handle.flush()
            os.fsync(handle.fileno())
            return handle
        except BlockingIOError:
            if time.monotonic() >= deadline:
                handle.close()
                return None
            time.sleep(0.05)


def build_receipt_provenance(
    *,
    release_path: Path,
    release_sha256: Optional[str],
    data_lake_path: Path,
    data_lake_sha256: Optional[str],
    live_integrity_path: Path,
    live_integrity_sha256: Optional[str],
    contract_policy_path: Path,
    contract_policy_sha256: Optional[str],
    semantic_policy_path: Path,
    semantic_policy_sha256: Optional[str],
    output_path: Path,
    lock_path: Path,
) -> dict[str, Any]:
    validator_script = Path(__file__).resolve()
    return {
        "validator_script_path": str(validator_script),
        "validator_script_sha256": sha256(validator_script),
        "release_path": str(release_path.resolve()),
        "release_sha256": release_sha256,
        "data_lake_path": str(data_lake_path.resolve()),
        "data_lake_sha256": data_lake_sha256,
        "live_integrity_path": str(live_integrity_path.resolve()),
        "live_integrity_sha256": live_integrity_sha256,
        "contract_policy_path": str(contract_policy_path.resolve()),
        "contract_policy_sha256": contract_policy_sha256,
        "semantic_policy_path": str(semantic_policy_path.resolve()),
        "semantic_policy_sha256": semantic_policy_sha256,
        "output_path": str(output_path.resolve()),
        "lock_path": str(lock_path.resolve()),
        "lock_acquired": True,
        "receipt_atomic_commit": True,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate local release manifest fail-closed consistency")
    parser.add_argument("--release", type=Path, default=RELEASE)
    parser.add_argument("--data-lake", type=Path, default=DATA_LAKE)
    parser.add_argument("--live-integrity", type=Path, default=LIVE_CONTENT_INTEGRITY)
    parser.add_argument("--contract-policy", type=Path, default=CONTRACT_POLICY)
    parser.add_argument("--semantic-policy", type=Path, default=SEMANTIC_POLICY)
    parser.add_argument("--output", type=Path, default=OUT)
    parser.add_argument("--lock-path", type=Path, default=LOCK_PATH)
    parser.add_argument("--lock-timeout-seconds", type=float, default=30.0)
    parser.add_argument("--fail-before-replace", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()
    defer_safe_pipeline_terminal = os.environ.get("KWB_DEFER_SAFE_PIPELINE_TERMINAL") == "1"

    output_path = args.output.resolve()
    lock_path = args.lock_path.resolve()
    lock_handle = acquire_receipt_lock(lock_path, args.lock_timeout_seconds)
    if lock_handle is None:
        print(json.dumps({
            "success": False,
            "error": "local_release_consistency_lock_timeout",
            "lock_path": str(lock_path),
            "output_preserved": output_path.exists(),
        }, ensure_ascii=False))
        return 1

    release, release_sha256 = load_json_snapshot(args.release)
    data_lake, data_lake_sha256 = load_json_snapshot(args.data_lake)
    claim_matrix = load_json(CLAIM_MATRIX)
    claim_policy_anchor = load_json(CLAIM_POLICY_ANCHOR)
    claim_policy_anchor_regression = load_json(CLAIM_POLICY_ANCHOR_REGRESSION)
    claim_promotion = load_json(CLAIM_PROMOTION)
    claim_matrix_fail_closed_policy = load_json(CLAIM_MATRIX_POLICY)
    claim_matrix_policy_current = load_json(CLAIM_MATRIX_POLICY_CURRENT)
    claim_matrix_policy_current_regression = load_json(CLAIM_MATRIX_POLICY_CURRENT_REGRESSION)
    human_decision_pending_index = load_json(HUMAN_DECISION_PENDING_INDEX)
    human_backlog = load_json(HUMAN_BACKLOG)
    human_backlog_validation = load_json(HUMAN_BACKLOG_VALIDATION)
    review_draft_boundary = load_json(REVIEW_DRAFT_BOUNDARY)
    model_claim_consistency = load_json(MODEL_CLAIM_CONSISTENCY)
    promotion_board = load_json(PROMOTION_BOARD)
    promotion_validation = load_json(PROMOTION_VALIDATION)
    promotion_regression = load_json(PROMOTION_REGRESSION)
    live_integrity, live_integrity_sha256 = load_json_snapshot(args.live_integrity)
    contract_policy, contract_policy_sha256 = load_json_snapshot(args.contract_policy)
    semantic_policy, semantic_policy_sha256 = load_json_snapshot(args.semantic_policy)
    semantic_policy_current = load_json(SEMANTIC_POLICY_CURRENT)
    semantic_policy_current_regression = load_json(SEMANTIC_POLICY_CURRENT_REGRESSION)
    semantic_policy_atomicity_regression = load_json(SEMANTIC_POLICY_ATOMICITY_REGRESSION)
    release_guard_order = load_json(RELEASE_GUARD_ORDER)
    release_guard_order_regression = load_json(RELEASE_GUARD_ORDER_REGRESSION)
    release_guard_order_current = load_json(RELEASE_GUARD_ORDER_CURRENT)
    release_guard_order_current_regression = load_json(RELEASE_GUARD_ORDER_CURRENT_REGRESSION)
    release_guard_order_atomicity_regression = load_json(RELEASE_GUARD_ORDER_ATOMICITY_REGRESSION)
    execution_wave_pair_atomicity_regression = load_json(EXECUTION_WAVE_PAIR_ATOMICITY_REGRESSION)
    execution_receipt_proof_current = load_json(EXECUTION_RECEIPT_PROOF_CURRENT)
    execution_receipt_proof_current_regression = load_json(EXECUTION_RECEIPT_PROOF_CURRENT_REGRESSION)
    semantic_inputs = build_semantic_inputs({
        "release": release,
        "data_lake": data_lake,
        "live_integrity": live_integrity,
        "contract_policy": contract_policy,
        "semantic_policy": semantic_policy,
    })
    sync_receipt = load_json(SYNC_RECEIPT)
    sync_marker_regression = load_json(SYNC_MARKER_REGRESSION)
    sync_marker_regression_current = load_json(SYNC_MARKER_REGRESSION_CURRENT)
    sync_marker_regression_current_regression = load_json(SYNC_MARKER_REGRESSION_CURRENT_REGRESSION)
    sync_marker_regression_atomicity = load_json(SYNC_MARKER_REGRESSION_ATOMICITY)
    sync_policy = load_json(SYNC_POLICY)
    sync_policy_regression = load_json(SYNC_POLICY_REGRESSION)
    sync_current = load_json(SYNC_CURRENT)
    sync_current_regression = load_json(SYNC_CURRENT_REGRESSION)
    sync_terminal_regression = load_json(SYNC_TERMINAL_REGRESSION)
    safe_pipeline_current = load_json(SAFE_PIPELINE_CURRENT)
    terminal_defer_mode_regression = load_json(TERMINAL_DEFER_MODE_REGRESSION)
    post_source_receipt_validation = load_json(POST_SOURCE_RECEIPT_VALIDATION)
    post_source_receipt_regression = load_json(POST_SOURCE_RECEIPT_REGRESSION)
    post_source_validation_current = load_json(POST_SOURCE_VALIDATION_CURRENT)
    post_source_validation_current_regression = load_json(POST_SOURCE_VALIDATION_CURRENT_REGRESSION)
    post_source_independent_policy = load_json(POST_SOURCE_INDEPENDENT_POLICY)
    post_source_independent_policy_regression = load_json(POST_SOURCE_INDEPENDENT_POLICY_REGRESSION)
    post_source_independent_policy_current = load_json(POST_SOURCE_INDEPENDENT_POLICY_CURRENT)
    post_source_independent_policy_current_regression = load_json(POST_SOURCE_INDEPENDENT_POLICY_CURRENT_REGRESSION)
    consistency_atomicity_regression = load_json(CONSISTENCY_ATOMICITY_REGRESSION)
    safety_guard_atomicity_regression = load_json(SAFETY_GUARD_ATOMICITY_REGRESSION)
    safety_guard_current = load_json(SAFETY_GUARD_CURRENT)
    safety_guard_current_regression = load_json(SAFETY_GUARD_CURRENT_REGRESSION)
    safety_guard_current_regression_atomicity = load_json(SAFETY_GUARD_CURRENT_REGRESSION_ATOMICITY)
    summary = release.get("readiness_summary") or {}
    artifacts = data_lake.get("artifacts") or []
    artifact_by_path = {
        str(item.get("path")): item for item in artifacts
        if isinstance(item, dict) and item.get("path")
    }
    artifact_paths = [str(item.get("path") or "") for item in artifacts if isinstance(item, dict)]
    unique_artifact_paths = set(artifact_paths)
    duplicate_final_paths = sorted({path for path in artifact_paths if artifact_paths.count(path) > 1})
    unsafe_artifact_paths = sorted(
        path
        for path in artifact_paths
        if not path
        or PurePosixPath(path).is_absolute()
        or ".." in PurePosixPath(path).parts
        or "\\" in path
        or str(PurePosixPath(path)) != path
    )
    failures: list[dict[str, Any]] = []
    if safety_guard_atomicity_regression.get("success") is not True or safety_guard_atomicity_regression.get("case_count") != 5 or safety_guard_atomicity_regression.get("passed_case_count") != 5 or safety_guard_atomicity_regression.get("failed_case_count") != 0 or safety_guard_atomicity_regression.get("real_inputs_mutated") is not False:
        failures.append({"check": "safety_guard_atomicity_regression_current", "observed": {"success": safety_guard_atomicity_regression.get("success"), "case_count": safety_guard_atomicity_regression.get("case_count"), "passed_case_count": safety_guard_atomicity_regression.get("passed_case_count"), "failed_case_count": safety_guard_atomicity_regression.get("failed_case_count"), "real_inputs_mutated": safety_guard_atomicity_regression.get("real_inputs_mutated")}, "expected": {"success": True, "case_count": 5, "passed_case_count": 5, "failed_case_count": 0, "real_inputs_mutated": False}})
    for field, expected in {"regression_script_path": str(SAFETY_GUARD_ATOMICITY_REGRESSION_SCRIPT.resolve()), "regression_script_sha256": sha256(SAFETY_GUARD_ATOMICITY_REGRESSION_SCRIPT), "validator_script_path": str((AI_ROOT / "scripts" / "validate_local_release_safety_guard_links.py").resolve()), "validator_script_sha256": sha256(AI_ROOT / "scripts" / "validate_local_release_safety_guard_links.py"), "output_path": str(SAFETY_GUARD_ATOMICITY_REGRESSION.resolve()), "lock_path": str((AI_ROOT / "reports" / ".local_release_safety_guard_links.lock").resolve()), "lock_acquired": True, "atomic_commit": True}.items():
        if safety_guard_atomicity_regression.get(field) != expected:
            failures.append({"check": "safety_guard_atomicity_regression_binding", "field": field, "observed": safety_guard_atomicity_regression.get(field), "expected": expected})
    if safety_guard_current_regression_atomicity.get("success") is not True or safety_guard_current_regression_atomicity.get("case_count") != 5 or safety_guard_current_regression_atomicity.get("passed_case_count") != 5 or safety_guard_current_regression_atomicity.get("failed_case_count") != 0 or safety_guard_current_regression_atomicity.get("real_inputs_mutated") is not False or safety_guard_current_regression_atomicity.get("isolated_fixture") is not True:
        failures.append({"check": "safety_guard_current_regression_atomicity_current", "observed": {"success": safety_guard_current_regression_atomicity.get("success"), "case_count": safety_guard_current_regression_atomicity.get("case_count"), "passed_case_count": safety_guard_current_regression_atomicity.get("passed_case_count"), "failed_case_count": safety_guard_current_regression_atomicity.get("failed_case_count"), "real_inputs_mutated": safety_guard_current_regression_atomicity.get("real_inputs_mutated"), "isolated_fixture": safety_guard_current_regression_atomicity.get("isolated_fixture")}, "expected": {"success": True, "case_count": 5, "passed_case_count": 5, "failed_case_count": 0, "real_inputs_mutated": False, "isolated_fixture": True}})
    for field, expected in {"regression_script_path": str(SAFETY_GUARD_CURRENT_REGRESSION_ATOMICITY_SCRIPT.resolve()), "regression_script_sha256": sha256(SAFETY_GUARD_CURRENT_REGRESSION_ATOMICITY_SCRIPT), "current_validator_script_path": str(SAFETY_GUARD_CURRENT_SCRIPT.resolve()), "current_validator_script_sha256": sha256(SAFETY_GUARD_CURRENT_SCRIPT), "current_regression_script_path": str(SAFETY_GUARD_CURRENT_REGRESSION_SCRIPT.resolve()), "current_regression_script_sha256": sha256(SAFETY_GUARD_CURRENT_REGRESSION_SCRIPT), "output_path": str(SAFETY_GUARD_CURRENT_REGRESSION_ATOMICITY.resolve()), "lock_path": str((AI_ROOT / "reports" / ".local_release_safety_guard_links.lock").resolve()), "lock_acquired": True, "atomic_commit": True}.items():
        if safety_guard_current_regression_atomicity.get(field) != expected:
            failures.append({"check": "safety_guard_current_regression_atomicity_binding", "field": field, "observed": safety_guard_current_regression_atomicity.get(field), "expected": expected})
    if not defer_safe_pipeline_terminal:
        expected_safety_guard_link_count = len(REQUIRED_GUARD_LINKS)
        if safety_guard_current.get("success") is not True or safety_guard_current.get("failure_count") != 0 or safety_guard_current.get("guard_link_count") != expected_safety_guard_link_count:
            failures.append({"check": "safety_guard_current_success", "observed": {"success": safety_guard_current.get("success"), "failure_count": safety_guard_current.get("failure_count"), "guard_link_count": safety_guard_current.get("guard_link_count")}, "expected": {"success": True, "failure_count": 0, "guard_link_count": expected_safety_guard_link_count}})
        for field, expected in {"current_validator_script_path": str(SAFETY_GUARD_CURRENT_SCRIPT.resolve()), "current_validator_script_sha256": sha256(SAFETY_GUARD_CURRENT_SCRIPT), "output_path": str(SAFETY_GUARD_CURRENT.resolve()), "lock_path": str((AI_ROOT / "reports" / ".local_release_safety_guard_links.lock").resolve()), "lock_acquired": True, "atomic_commit": True}.items():
            if safety_guard_current.get(field) != expected:
                failures.append({"check": "safety_guard_current_binding", "field": field, "observed": safety_guard_current.get(field), "expected": expected})
        if safety_guard_current_regression.get("success") is not True or safety_guard_current_regression.get("case_count") != 12 or safety_guard_current_regression.get("passed_case_count") != 12 or safety_guard_current_regression.get("failed_case_count") != 0 or safety_guard_current_regression.get("real_inputs_mutated") is not False:
            failures.append({"check": "safety_guard_current_regression_success", "observed": {"success": safety_guard_current_regression.get("success"), "case_count": safety_guard_current_regression.get("case_count"), "passed_case_count": safety_guard_current_regression.get("passed_case_count"), "failed_case_count": safety_guard_current_regression.get("failed_case_count"), "real_inputs_mutated": safety_guard_current_regression.get("real_inputs_mutated")}, "expected": {"success": True, "case_count": 12, "passed_case_count": 12, "failed_case_count": 0, "real_inputs_mutated": False}})
        for field, expected in {"regression_script_path": str(SAFETY_GUARD_CURRENT_REGRESSION_SCRIPT.resolve()), "regression_script_sha256": sha256(SAFETY_GUARD_CURRENT_REGRESSION_SCRIPT), "current_validator_script_path": str(SAFETY_GUARD_CURRENT_SCRIPT.resolve()), "current_validator_script_sha256": sha256(SAFETY_GUARD_CURRENT_SCRIPT), "output_path": str(SAFETY_GUARD_CURRENT_REGRESSION.resolve()), "lock_path": str((AI_ROOT / "reports" / ".local_release_safety_guard_links.lock").resolve()), "lock_acquired": True, "atomic_commit": True}.items():
            if safety_guard_current_regression.get(field) != expected:
                failures.append({"check": "safety_guard_current_regression_binding", "field": field, "observed": safety_guard_current_regression.get(field), "expected": expected})

    if release.get("release_ready") is not False:
        failures.append({"check": "release_ready_false", "observed": release.get("release_ready"), "expected": False})
    if release.get("local_only") is not True:
        failures.append({"check": "local_only_true", "observed": release.get("local_only"), "expected": True})
    if release.get("artifact_count") != len(artifacts):
        failures.append({"check": "artifact_count_matches_data_lake", "observed": release.get("artifact_count"), "expected": len(artifacts)})
    if len(unique_artifact_paths) != len(artifacts):
        failures.append({"check": "artifact_paths_unique", "observed": len(unique_artifact_paths), "expected": len(artifacts), "duplicate_paths": duplicate_final_paths})
    if unsafe_artifact_paths:
        failures.append({"check": "artifact_paths_safe_relative", "observed": unsafe_artifact_paths, "expected": []})
    manifest_metadata = {
        "artifact_rows": len(artifacts),
        "unique_path_rows": len(unique_artifact_paths),
        "deduplicated_input_rows": int(data_lake.get("source_artifact_rows") or 0) - len(artifacts),
        "duplicate_input_path_rows": len(data_lake.get("duplicate_input_paths") or []),
    }
    for field, expected in manifest_metadata.items():
        if data_lake.get(field) != expected:
            failures.append({"check": "data_lake_manifest_metadata_parity", "field": field, "observed": data_lake.get(field), "expected": expected})
    if not isinstance(data_lake.get("source_artifact_rows"), int) or isinstance(data_lake.get("source_artifact_rows"), bool) or data_lake.get("source_artifact_rows") < len(artifacts):
        failures.append({"check": "source_artifact_rows_valid", "observed": data_lake.get("source_artifact_rows"), "expected": f">={len(artifacts)} integer"})
    if len(artifacts) < MIN_EXPECTED_ARTIFACT_COUNT:
        failures.append({"check": "artifact_count_minimum", "observed": len(artifacts), "expected_at_least": MIN_EXPECTED_ARTIFACT_COUNT})
    if release.get("missing_artifacts") not in ([], None):
        failures.append({"check": "missing_artifacts_empty", "observed": release.get("missing_artifacts"), "expected": []})

    contract_policy_summary_values = {
        "release_input_contract_policy_module_path": contract_policy.get("contract_module_path"),
        "release_input_contract_policy_module_sha256": contract_policy.get("contract_module_sha256"),
        "release_input_contract_policy_expected_version": contract_policy.get("expected_contract_version"),
        "release_input_contract_policy_expected_excluded_paths": contract_policy.get("expected_excluded_paths"),
        "release_input_contract_policy_expected_test_vector_sha256": contract_policy.get("expected_test_vector_sha256"),
    }
    for field, expected in contract_policy_summary_values.items():
        if summary.get(field) != expected:
            failures.append({"check": "contract_policy_summary_matches_report", "field": field, "observed": summary.get(field), "expected": expected})
    if contract_policy.get("success") is not True or contract_policy.get("failure_count") != 0:
        failures.append({"check": "contract_policy_success", "observed": {"success": contract_policy.get("success"), "failure_count": contract_policy.get("failure_count")}, "expected": {"success": True, "failure_count": 0}})
    if contract_policy.get("contract_module_path") != str(CONTRACT_MODULE.resolve()):
        failures.append({"check": "contract_policy_module_path_canonical", "observed": contract_policy.get("contract_module_path"), "expected": str(CONTRACT_MODULE.resolve())})
    current_contract_module_sha256 = hashlib.sha256(CONTRACT_MODULE.read_bytes()).hexdigest() if CONTRACT_MODULE.is_file() else None
    contract_module_artifact = artifact_by_path.get("scripts/data_lake_release_input_contract.py") or {}
    if contract_policy.get("contract_module_sha256") != current_contract_module_sha256:
        failures.append({"check": "contract_policy_module_sha256_current", "observed": contract_policy.get("contract_module_sha256"), "expected": current_contract_module_sha256})
    if contract_module_artifact.get("sha256") != current_contract_module_sha256:
        failures.append({"check": "contract_policy_module_sha256_matches_data_lake", "observed": contract_module_artifact.get("sha256"), "expected": current_contract_module_sha256})
    if contract_policy.get("expected_contract_version") != POLICY_EXPECTED_VERSION:
        failures.append({"check": "contract_policy_version_exact", "observed": contract_policy.get("expected_contract_version"), "expected": POLICY_EXPECTED_VERSION})
    if set(contract_policy.get("expected_excluded_paths") or []) != POLICY_EXPECTED_EXCLUDED_PATHS:
        failures.append({"check": "contract_policy_excluded_paths_exact", "observed": contract_policy.get("expected_excluded_paths"), "expected": sorted(POLICY_EXPECTED_EXCLUDED_PATHS)})
    if contract_policy.get("expected_test_vector_sha256") != POLICY_EXPECTED_TEST_VECTOR_SHA256:
        failures.append({"check": "contract_policy_test_vector_sha256_exact", "observed": contract_policy.get("expected_test_vector_sha256"), "expected": POLICY_EXPECTED_TEST_VECTOR_SHA256})
    semantic_policy_summary_values = {
        "local_release_consistency_semantic_policy_success": semantic_policy.get("success"),
        "local_release_consistency_semantic_policy_failures": semantic_policy.get("failure_count"),
        "local_release_consistency_semantic_policy_version": semantic_policy.get("expected_contract_version"),
        "local_release_consistency_semantic_policy_canonical_sha256": semantic_policy.get("expected_canonical_policy_sha256"),
        "local_release_consistency_semantic_policy_test_vector_sha256": semantic_policy.get("expected_test_vector_sha256"),
    }
    for field, expected in semantic_policy_summary_values.items():
        if summary.get(field) != expected:
            failures.append({"check": "semantic_policy_summary_matches_report", "field": field, "observed": summary.get(field), "expected": expected})
    if semantic_policy.get("success") is not True or semantic_policy.get("failure_count") != 0:
        failures.append({"check": "semantic_policy_success", "observed": {"success": semantic_policy.get("success"), "failure_count": semantic_policy.get("failure_count")}, "expected": {"success": True, "failure_count": 0}})
    if semantic_policy.get("policy_script_path") != str(SEMANTIC_POLICY_SCRIPT.resolve()):
        failures.append({"check": "semantic_policy_script_path_canonical", "observed": semantic_policy.get("policy_script_path"), "expected": str(SEMANTIC_POLICY_SCRIPT.resolve())})
    if semantic_policy.get("policy_script_sha256") != sha256(SEMANTIC_POLICY_SCRIPT):
        failures.append({"check": "semantic_policy_script_sha256_current", "observed": semantic_policy.get("policy_script_sha256"), "expected": sha256(SEMANTIC_POLICY_SCRIPT)})
    for field, expected in {
        "contract_module_path": str(SEMANTIC_CONTRACT_MODULE.resolve()),
        "contract_module_sha256": sha256(SEMANTIC_CONTRACT_MODULE),
        "policy_output_path": str(args.semantic_policy.resolve()),
        "policy_lock_path": str(SEMANTIC_POLICY_LOCK.resolve()),
        "policy_lock_acquired": True,
        "policy_atomic_commit": True,
    }.items():
        if semantic_policy.get(field) != expected:
            failures.append({"check": "semantic_policy_provenance_current", "field": field, "observed": semantic_policy.get(field), "expected": expected})
    for field, expected in {
        "expected_contract_version": SEMANTIC_POLICY_EXPECTED_VERSION,
        "expected_input_roles": list(EXPECTED_INPUT_ROLES),
        "expected_data_lake_semantic_excluded_paths": list(EXPECTED_DATA_LAKE_SEMANTIC_EXCLUDED_PATHS),
        "expected_release_summary_normalized_fields": list(EXPECTED_RELEASE_SUMMARY_NORMALIZED_FIELDS),
        "expected_live_normalized_fields": list(EXPECTED_LIVE_NORMALIZED_FIELDS),
        "expected_release_summary_excluded_fields": list(EXPECTED_RELEASE_SUMMARY_EXCLUDED_FIELDS),
        "expected_live_projection_fields": list(EXPECTED_LIVE_FIELDS),
        "expected_contract_policy_projection_fields": list(EXPECTED_CONTRACT_POLICY_FIELDS),
        "expected_canonical_policy_sha256": EXPECTED_CANONICAL_POLICY_SHA256,
        "expected_test_vector_sha256": EXPECTED_TEST_VECTOR_SHA256,
        "expected_shared_contract_test_vector_sha256": EXPECTED_SHARED_CONTRACT_TEST_VECTOR_SHA256,
    }.items():
        if semantic_policy.get(field) != expected:
            failures.append({"check": "semantic_policy_anchor_exact", "field": field, "observed": semantic_policy.get(field), "expected": expected})
    semantic_policy_current_summary_values = {
        "local_release_consistency_semantic_policy_current_success": semantic_policy_current.get("success"),
        "local_release_consistency_semantic_policy_current_failures": semantic_policy_current.get("failure_count"),
        "local_release_consistency_semantic_policy_current_regression_success": semantic_policy_current_regression.get("success"),
        "local_release_consistency_semantic_policy_current_regression_failed_rows": semantic_policy_current_regression.get("failed_case_count"),
        "local_release_consistency_semantic_policy_atomicity_regression_success": semantic_policy_atomicity_regression.get("success"),
        "local_release_consistency_semantic_policy_atomicity_regression_failed_rows": semantic_policy_atomicity_regression.get("failed_case_count"),
    }
    release_guard_order_summary_values = {
        "enzyme_agent_release_guard_order_success": release_guard_order.get("success"),
        "enzyme_agent_release_guard_order_failures": release_guard_order.get("failure_count"),
        "enzyme_agent_release_guard_order_regression_success": release_guard_order_regression.get("success"),
        "enzyme_agent_release_guard_order_regression_failed_rows": release_guard_order_regression.get("failed_rows"),
        "enzyme_agent_release_guard_order_current_success": release_guard_order_current.get("success"),
        "enzyme_agent_release_guard_order_current_failures": release_guard_order_current.get("failure_count"),
        "enzyme_agent_release_guard_order_current_regression_success": release_guard_order_current_regression.get("success"),
        "enzyme_agent_release_guard_order_current_regression_failed_rows": release_guard_order_current_regression.get("failed_case_count"),
        "enzyme_agent_release_guard_order_atomicity_regression_success": release_guard_order_atomicity_regression.get("success"),
        "enzyme_agent_release_guard_order_atomicity_regression_failed_rows": release_guard_order_atomicity_regression.get("failed_case_count"),
    }
    for field, expected in release_guard_order_summary_values.items():
        if summary.get(field) != expected:
            failures.append({"check": "release_guard_order_summary_matches_report", "field": field, "observed": summary.get(field), "expected": expected})
    for report_name, report in (
        ("release_guard_order", release_guard_order),
        ("release_guard_order_regression", release_guard_order_regression),
        ("release_guard_order_current", release_guard_order_current),
        ("release_guard_order_current_regression", release_guard_order_current_regression),
        ("release_guard_order_atomicity_regression", release_guard_order_atomicity_regression),
        ("execution_wave_pair_atomicity_regression", execution_wave_pair_atomicity_regression),
    ):
        if report.get("success") is not True:
            failures.append({"check": f"{report_name}_success", "observed": report.get("success"), "expected": True})
    receipt_proof_summary_values = {
        "enzyme_agent_execution_receipt_proof_current_success": execution_receipt_proof_current.get("success"),
        "enzyme_agent_execution_receipt_proof_current_failures": execution_receipt_proof_current.get("failure_count"),
        "enzyme_agent_execution_receipt_proof_current_sha256": sha256(EXECUTION_RECEIPT_PROOF_CURRENT),
        "enzyme_agent_execution_receipt_proof_current_regression_success": execution_receipt_proof_current_regression.get("success"),
        "enzyme_agent_execution_receipt_proof_current_regression_failed_rows": execution_receipt_proof_current_regression.get("failed_case_count"),
        "enzyme_agent_execution_receipt_proof_current_regression_sha256": sha256(EXECUTION_RECEIPT_PROOF_CURRENT_REGRESSION),
    }
    for field, expected in receipt_proof_summary_values.items():
        if summary.get(field) != expected:
            failures.append({"check": "execution_receipt_proof_summary_matches_current", "field": field, "observed": summary.get(field), "expected": expected})
    if execution_receipt_proof_current.get("success") is not True or execution_receipt_proof_current.get("failure_count") != 0:
        failures.append({"check": "execution_receipt_proof_current_success", "observed": {"success": execution_receipt_proof_current.get("success"), "failure_count": execution_receipt_proof_current.get("failure_count")}, "expected": {"success": True, "failure_count": 0}})
    if execution_receipt_proof_current_regression.get("success") is not True or execution_receipt_proof_current_regression.get("case_count") != 11 or execution_receipt_proof_current_regression.get("passed_case_count") != 11 or execution_receipt_proof_current_regression.get("failed_case_count") != 0 or execution_receipt_proof_current_regression.get("real_inputs_mutated") is not False:
        failures.append({"check": "execution_receipt_proof_current_regression_success", "observed": {"success": execution_receipt_proof_current_regression.get("success"), "case_count": execution_receipt_proof_current_regression.get("case_count"), "passed_case_count": execution_receipt_proof_current_regression.get("passed_case_count"), "failed_case_count": execution_receipt_proof_current_regression.get("failed_case_count"), "real_inputs_mutated": execution_receipt_proof_current_regression.get("real_inputs_mutated")}, "expected": {"success": True, "case_count": 11, "passed_case_count": 11, "failed_case_count": 0, "real_inputs_mutated": False}})
    if release_guard_order.get("failure_count") != 0 or release_guard_order.get("observed_command_count") != 41:
        failures.append({"check": "release_guard_order_contract_current", "observed": {"failure_count": release_guard_order.get("failure_count"), "observed_command_count": release_guard_order.get("observed_command_count")}, "expected": {"failure_count": 0, "observed_command_count": 41}})
    if release_guard_order_regression.get("failed_rows") != 0 or release_guard_order_regression.get("passed_rows") != 8 or release_guard_order_regression.get("real_inputs_mutated") is not False:
        failures.append({"check": "release_guard_order_regression_current", "observed": {"failed_rows": release_guard_order_regression.get("failed_rows"), "passed_rows": release_guard_order_regression.get("passed_rows"), "real_inputs_mutated": release_guard_order_regression.get("real_inputs_mutated")}, "expected": {"failed_rows": 0, "passed_rows": 8, "real_inputs_mutated": False}})
    if release_guard_order_current.get("failure_count") != 0 or release_guard_order_current.get("current_atomic_commit") is not True or release_guard_order_current.get("current_lock_acquired") is not True:
        failures.append({"check": "release_guard_order_current_atomic_current", "observed": {"failure_count": release_guard_order_current.get("failure_count"), "current_atomic_commit": release_guard_order_current.get("current_atomic_commit"), "current_lock_acquired": release_guard_order_current.get("current_lock_acquired")}, "expected": {"failure_count": 0, "current_atomic_commit": True, "current_lock_acquired": True}})
    if release_guard_order_current_regression.get("failed_case_count") != 0 or release_guard_order_current_regression.get("case_count") != 17 or release_guard_order_current_regression.get("real_inputs_mutated") is not False:
        failures.append({"check": "release_guard_order_current_regression_current", "observed": {"failed_case_count": release_guard_order_current_regression.get("failed_case_count"), "case_count": release_guard_order_current_regression.get("case_count"), "real_inputs_mutated": release_guard_order_current_regression.get("real_inputs_mutated")}, "expected": {"failed_case_count": 0, "case_count": 17, "real_inputs_mutated": False}})
    for field, expected in {
        "regression_script_path": str(RELEASE_GUARD_ORDER_CURRENT_REGRESSION_SCRIPT.resolve()),
        "regression_script_sha256": hashlib.sha256(RELEASE_GUARD_ORDER_CURRENT_REGRESSION_SCRIPT.read_bytes()).hexdigest() if RELEASE_GUARD_ORDER_CURRENT_REGRESSION_SCRIPT.is_file() else None,
        "current_validator_script_path": str(RELEASE_GUARD_ORDER_CURRENT_SCRIPT.resolve()),
        "current_validator_script_sha256": hashlib.sha256(RELEASE_GUARD_ORDER_CURRENT_SCRIPT.read_bytes()).hexdigest() if RELEASE_GUARD_ORDER_CURRENT_SCRIPT.is_file() else None,
        "output_path": str(RELEASE_GUARD_ORDER_CURRENT_REGRESSION.resolve()),
        "lock_path": str((AI_ROOT / "reports" / ".enzyme_agent_controlled_release_guard_order.lock").resolve()),
        "lock_acquired": True,
        "atomic_commit": True,
    }.items():
        if release_guard_order_current_regression.get(field) != expected:
            failures.append({"check": "release_guard_order_current_regression_binding", "field": field, "observed": release_guard_order_current_regression.get(field), "expected": expected})
    if release_guard_order_atomicity_regression.get("case_count") != 11 or release_guard_order_atomicity_regression.get("passed_case_count") != 11 or release_guard_order_atomicity_regression.get("failed_case_count") != 0 or release_guard_order_atomicity_regression.get("real_inputs_mutated") is not False:
        failures.append({"check": "release_guard_order_atomicity_regression_current", "observed": {"case_count": release_guard_order_atomicity_regression.get("case_count"), "passed_case_count": release_guard_order_atomicity_regression.get("passed_case_count"), "failed_case_count": release_guard_order_atomicity_regression.get("failed_case_count"), "real_inputs_mutated": release_guard_order_atomicity_regression.get("real_inputs_mutated")}, "expected": {"case_count": 11, "passed_case_count": 11, "failed_case_count": 0, "real_inputs_mutated": False}})
    for field, expected in {
        "regression_script_path": str(RELEASE_GUARD_ORDER_ATOMICITY_REGRESSION_SCRIPT.resolve()),
        "regression_script_sha256": hashlib.sha256(RELEASE_GUARD_ORDER_ATOMICITY_REGRESSION_SCRIPT.read_bytes()).hexdigest() if RELEASE_GUARD_ORDER_ATOMICITY_REGRESSION_SCRIPT.is_file() else None,
        "signer_script_path": str(RELEASE_GUARD_ORDER_SCRIPT.resolve()),
        "signer_script_sha256": hashlib.sha256(RELEASE_GUARD_ORDER_SCRIPT.read_bytes()).hexdigest() if RELEASE_GUARD_ORDER_SCRIPT.is_file() else None,
        "order_regression_script_path": str(RELEASE_GUARD_ORDER_REGRESSION_SCRIPT.resolve()),
        "order_regression_script_sha256": hashlib.sha256(RELEASE_GUARD_ORDER_REGRESSION_SCRIPT.read_bytes()).hexdigest() if RELEASE_GUARD_ORDER_REGRESSION_SCRIPT.is_file() else None,
        "current_validator_script_path": str(RELEASE_GUARD_ORDER_CURRENT_SCRIPT.resolve()),
        "current_validator_script_sha256": hashlib.sha256(RELEASE_GUARD_ORDER_CURRENT_SCRIPT.read_bytes()).hexdigest() if RELEASE_GUARD_ORDER_CURRENT_SCRIPT.is_file() else None,
        "current_regression_script_path": str(RELEASE_GUARD_ORDER_CURRENT_REGRESSION_SCRIPT.resolve()),
        "current_regression_script_sha256": hashlib.sha256(RELEASE_GUARD_ORDER_CURRENT_REGRESSION_SCRIPT.read_bytes()).hexdigest() if RELEASE_GUARD_ORDER_CURRENT_REGRESSION_SCRIPT.is_file() else None,
        "output_path": str(RELEASE_GUARD_ORDER_ATOMICITY_REGRESSION.resolve()),
        "lock_path": str((AI_ROOT / "reports" / ".enzyme_agent_controlled_release_guard_order.lock").resolve()),
        "lock_acquired": True,
        "atomic_commit": True,
    }.items():
        if release_guard_order_atomicity_regression.get(field) != expected:
            failures.append({"check": "release_guard_order_atomicity_regression_binding", "field": field, "observed": release_guard_order_atomicity_regression.get(field), "expected": expected})
    if execution_wave_pair_atomicity_regression.get("case_count") != 5 or execution_wave_pair_atomicity_regression.get("passed_case_count") != 5 or execution_wave_pair_atomicity_regression.get("failed_case_count") != 0 or execution_wave_pair_atomicity_regression.get("real_inputs_mutated") is not False:
        failures.append({"check": "execution_wave_pair_atomicity_regression_current", "observed": {"case_count": execution_wave_pair_atomicity_regression.get("case_count"), "passed_case_count": execution_wave_pair_atomicity_regression.get("passed_case_count"), "failed_case_count": execution_wave_pair_atomicity_regression.get("failed_case_count"), "real_inputs_mutated": execution_wave_pair_atomicity_regression.get("real_inputs_mutated")}, "expected": {"case_count": 5, "passed_case_count": 5, "failed_case_count": 0, "real_inputs_mutated": False}})
    for field, expected in {
        "regression_script_path": str(EXECUTION_WAVE_PAIR_ATOMICITY_REGRESSION_SCRIPT.resolve()),
        "regression_script_sha256": hashlib.sha256(EXECUTION_WAVE_PAIR_ATOMICITY_REGRESSION_SCRIPT.read_bytes()).hexdigest() if EXECUTION_WAVE_PAIR_ATOMICITY_REGRESSION_SCRIPT.is_file() else None,
        "wave_script_path": str(RELEASE_GUARD_ORDER_WAVE_SCRIPT.resolve()),
        "wave_script_sha256": hashlib.sha256(RELEASE_GUARD_ORDER_WAVE_SCRIPT.read_bytes()).hexdigest() if RELEASE_GUARD_ORDER_WAVE_SCRIPT.is_file() else None,
        "output_path": str(EXECUTION_WAVE_PAIR_ATOMICITY_REGRESSION.resolve()),
        "lock_path": str((AI_ROOT / "reports" / ".enzyme_agent_controlled_execution_wave.lock").resolve()),
        "lock_acquired": True,
        "atomic_commit": True,
    }.items():
        if execution_wave_pair_atomicity_regression.get(field) != expected:
            failures.append({"check": "execution_wave_pair_atomicity_regression_binding", "field": field, "observed": execution_wave_pair_atomicity_regression.get(field), "expected": expected})
    current_bindings = {
        "validation_report_path": str(RELEASE_GUARD_ORDER.resolve()),
        "validation_report_sha256": hashlib.sha256(RELEASE_GUARD_ORDER.read_bytes()).hexdigest() if RELEASE_GUARD_ORDER.is_file() else None,
        "regression_report_path": str(RELEASE_GUARD_ORDER_REGRESSION.resolve()),
        "regression_report_sha256": hashlib.sha256(RELEASE_GUARD_ORDER_REGRESSION.read_bytes()).hexdigest() if RELEASE_GUARD_ORDER_REGRESSION.is_file() else None,
        "validator_script_path": str(RELEASE_GUARD_ORDER_SCRIPT.resolve()),
        "validator_script_sha256": hashlib.sha256(RELEASE_GUARD_ORDER_SCRIPT.read_bytes()).hexdigest() if RELEASE_GUARD_ORDER_SCRIPT.is_file() else None,
        "regression_script_path": str(RELEASE_GUARD_ORDER_REGRESSION_SCRIPT.resolve()),
        "regression_script_sha256": hashlib.sha256(RELEASE_GUARD_ORDER_REGRESSION_SCRIPT.read_bytes()).hexdigest() if RELEASE_GUARD_ORDER_REGRESSION_SCRIPT.is_file() else None,
        "wave_script_path": str(RELEASE_GUARD_ORDER_WAVE_SCRIPT.resolve()),
        "wave_script_sha256": hashlib.sha256(RELEASE_GUARD_ORDER_WAVE_SCRIPT.read_bytes()).hexdigest() if RELEASE_GUARD_ORDER_WAVE_SCRIPT.is_file() else None,
        "current_validator_script_path": str(RELEASE_GUARD_ORDER_CURRENT_SCRIPT.resolve()),
        "current_validator_script_sha256": hashlib.sha256(RELEASE_GUARD_ORDER_CURRENT_SCRIPT.read_bytes()).hexdigest() if RELEASE_GUARD_ORDER_CURRENT_SCRIPT.is_file() else None,
        "current_output_path": str(RELEASE_GUARD_ORDER_CURRENT.resolve()),
        "current_lock_path": str((AI_ROOT / "reports" / ".enzyme_agent_controlled_release_guard_order.lock").resolve()),
        "current_atomic_commit": True,
    }
    for field, expected in current_bindings.items():
        if release_guard_order_current.get(field) != expected:
            failures.append({"check": "release_guard_order_current_binding", "field": field, "observed": release_guard_order_current.get(field), "expected": expected})
    for field, expected in semantic_policy_current_summary_values.items():
        if summary.get(field) != expected:
            failures.append({"check": "semantic_policy_current_summary_matches_report", "field": field, "observed": summary.get(field), "expected": expected})
    if semantic_policy_current.get("success") is not True or semantic_policy_current.get("failure_count") != 0:
        failures.append({"check": "semantic_policy_current_success", "observed": {"success": semantic_policy_current.get("success"), "failure_count": semantic_policy_current.get("failure_count")}, "expected": {"success": True, "failure_count": 0}})
    expected_semantic_policy_current = {
        "policy_report_path": str(args.semantic_policy.resolve()),
        "policy_report_sha256": semantic_policy_sha256,
        "policy_script_path": str(SEMANTIC_POLICY_SCRIPT.resolve()),
        "policy_script_sha256": sha256(SEMANTIC_POLICY_SCRIPT),
        "contract_module_path": str(SEMANTIC_CONTRACT_MODULE.resolve()),
        "contract_module_sha256": sha256(SEMANTIC_CONTRACT_MODULE),
        "current_validator_script_path": str(SEMANTIC_POLICY_CURRENT_SCRIPT.resolve()),
        "current_validator_script_sha256": sha256(SEMANTIC_POLICY_CURRENT_SCRIPT),
        "current_output_path": str(SEMANTIC_POLICY_CURRENT.resolve()),
        "current_lock_path": str(SEMANTIC_POLICY_LOCK.resolve()),
        "current_lock_acquired": True,
        "current_atomic_commit": True,
    }
    for field, expected in expected_semantic_policy_current.items():
        if semantic_policy_current.get(field) != expected:
            failures.append({"check": "semantic_policy_current_provenance", "field": field, "observed": semantic_policy_current.get(field), "expected": expected})
    if semantic_policy_current_regression.get("success") is not True or semantic_policy_current_regression.get("case_count") != 16 or semantic_policy_current_regression.get("passed_case_count") != 16 or semantic_policy_current_regression.get("failed_case_count") != 0 or semantic_policy_current_regression.get("isolated_fixture") is not True or semantic_policy_current_regression.get("real_inputs_mutated") is not False:
        failures.append({"check": "semantic_policy_current_regression_success", "observed": {"success": semantic_policy_current_regression.get("success"), "case_count": semantic_policy_current_regression.get("case_count"), "passed_case_count": semantic_policy_current_regression.get("passed_case_count"), "failed_case_count": semantic_policy_current_regression.get("failed_case_count"), "isolated_fixture": semantic_policy_current_regression.get("isolated_fixture"), "real_inputs_mutated": semantic_policy_current_regression.get("real_inputs_mutated")}, "expected": {"success": True, "case_count": 16, "passed_case_count": 16, "failed_case_count": 0, "isolated_fixture": True, "real_inputs_mutated": False}})
    for field, expected in {
        "regression_script_path": str(SEMANTIC_POLICY_CURRENT_REGRESSION_SCRIPT.resolve()),
        "regression_script_sha256": sha256(SEMANTIC_POLICY_CURRENT_REGRESSION_SCRIPT),
        "current_validator_script_path": str(SEMANTIC_POLICY_CURRENT_SCRIPT.resolve()),
        "current_validator_script_sha256": sha256(SEMANTIC_POLICY_CURRENT_SCRIPT),
    }.items():
        if semantic_policy_current_regression.get(field) != expected:
            failures.append({"check": "semantic_policy_current_regression_provenance", "field": field, "observed": semantic_policy_current_regression.get(field), "expected": expected})
    if semantic_policy_atomicity_regression.get("success") is not True or semantic_policy_atomicity_regression.get("case_count") != 7 or semantic_policy_atomicity_regression.get("passed_case_count") != 7 or semantic_policy_atomicity_regression.get("failed_case_count") != 0 or semantic_policy_atomicity_regression.get("isolated_fixture") is not True or semantic_policy_atomicity_regression.get("real_inputs_mutated") is not False:
        failures.append({"check": "semantic_policy_atomicity_regression_success", "observed": {"success": semantic_policy_atomicity_regression.get("success"), "case_count": semantic_policy_atomicity_regression.get("case_count"), "passed_case_count": semantic_policy_atomicity_regression.get("passed_case_count"), "failed_case_count": semantic_policy_atomicity_regression.get("failed_case_count"), "isolated_fixture": semantic_policy_atomicity_regression.get("isolated_fixture"), "real_inputs_mutated": semantic_policy_atomicity_regression.get("real_inputs_mutated")}, "expected": {"success": True, "case_count": 7, "passed_case_count": 7, "failed_case_count": 0, "isolated_fixture": True, "real_inputs_mutated": False}})
    for field, expected in {
        "regression_script_path": str(SEMANTIC_POLICY_ATOMICITY_REGRESSION_SCRIPT.resolve()),
        "regression_script_sha256": sha256(SEMANTIC_POLICY_ATOMICITY_REGRESSION_SCRIPT),
        "policy_script_path": str(SEMANTIC_POLICY_SCRIPT.resolve()),
        "policy_script_sha256": sha256(SEMANTIC_POLICY_SCRIPT),
        "current_validator_script_path": str(SEMANTIC_POLICY_CURRENT_SCRIPT.resolve()),
        "current_validator_script_sha256": sha256(SEMANTIC_POLICY_CURRENT_SCRIPT),
    }.items():
        if semantic_policy_atomicity_regression.get(field) != expected:
            failures.append({"check": "semantic_policy_atomicity_regression_provenance", "field": field, "observed": semantic_policy_atomicity_regression.get(field), "expected": expected})

    sync_policy_summary_values = {
        "stage25_operator_docs_dynamic_sync_contract_version": sync_receipt.get("contract_version"),
        "stage25_operator_docs_dynamic_sync_contract_sha256": sync_receipt.get("contract_sha256"),
        "stage25_operator_docs_dynamic_sync_provenance_rows": sync_receipt.get("provenance_row_count"),
        "stage25_operator_docs_dynamic_sync_provenance_sha256": sync_receipt.get("provenance_sha256"),
        "stage25_operator_docs_dynamic_sync_observed_provenance_sha256": sync_receipt.get("observed_provenance_sha256"),
        "stage25_operator_docs_dynamic_sync_lock_path": sync_receipt.get("lock_path"),
        "stage25_operator_docs_dynamic_sync_output_path": sync_receipt.get("observed_output_path"),
        "stage25_operator_docs_sync_contract_policy_module_path": sync_policy.get("contract_module_path"),
        "stage25_operator_docs_sync_contract_policy_module_sha256": sync_policy.get("contract_module_sha256"),
        "stage25_operator_docs_sync_contract_policy_expected_version": sync_policy.get("expected_contract_version"),
        "stage25_operator_docs_sync_contract_policy_expected_contract_sha256": sync_policy.get("expected_contract_sha256"),
        "stage25_operator_docs_sync_contract_policy_expected_semantic_projection_version": sync_policy.get("expected_semantic_projection_version"),
        "stage25_operator_docs_sync_contract_policy_expected_semantic_projection_test_vector_sha256": sync_policy.get("expected_semantic_projection_test_vector_sha256"),
    }
    sync_current_summary_values = {
        "stage25_operator_docs_sync_current_receipt_target_rows": sync_current.get("target_rows"),
        "stage25_operator_docs_sync_current_receipt_stale_rows": sync_current.get("stale_rows"),
        "stage25_operator_docs_sync_current_receipt_provenance_rows": sync_current.get("provenance_rows"),
        "stage25_operator_docs_sync_current_receipt_semantic_provenance_rows": sync_current.get("semantic_provenance_rows"),
        "stage25_operator_docs_sync_current_receipt_semantic_projection_version": sync_current.get("semantic_projection_version"),
        "stage25_operator_docs_sync_current_receipt_semantic_projection_test_vector_sha256": sync_current.get("semantic_projection_test_vector_sha256"),
        "stage25_operator_docs_sync_current_receipt_path": sync_current.get("receipt_path"),
        "stage25_operator_docs_sync_current_receipt_sha256": sync_current.get("receipt_sha256"),
        "stage25_operator_docs_sync_current_receipt_contract_version": sync_current.get("contract_version"),
        "stage25_operator_docs_sync_current_receipt_contract_sha256": sync_current.get("contract_sha256"),
    }
    marker_regression_summary_values = {
        "stage25_operator_docs_dynamic_sync_regression_success": bool(sync_marker_regression.get("success")),
        "stage25_operator_docs_dynamic_sync_regression_failed_rows": sync_marker_regression.get("failed_rows"),
        "stage25_operator_docs_dynamic_sync_regression_sha256": hashlib.sha256(SYNC_MARKER_REGRESSION.read_bytes()).hexdigest() if SYNC_MARKER_REGRESSION.is_file() else None,
        "stage25_operator_docs_dynamic_sync_regression_current_success": bool(sync_marker_regression_current.get("success")),
        "stage25_operator_docs_dynamic_sync_regression_current_failures": sync_marker_regression_current.get("failure_count"),
        "stage25_operator_docs_dynamic_sync_regression_current_sha256": hashlib.sha256(SYNC_MARKER_REGRESSION_CURRENT.read_bytes()).hexdigest() if SYNC_MARKER_REGRESSION_CURRENT.is_file() else None,
        "stage25_operator_docs_dynamic_sync_regression_current_regression_success": bool(sync_marker_regression_current_regression.get("success")),
        "stage25_operator_docs_dynamic_sync_regression_current_regression_failures": sync_marker_regression_current_regression.get("failure_count"),
        "stage25_operator_docs_dynamic_sync_regression_current_regression_sha256": hashlib.sha256(SYNC_MARKER_REGRESSION_CURRENT_REGRESSION.read_bytes()).hexdigest() if SYNC_MARKER_REGRESSION_CURRENT_REGRESSION.is_file() else None,
        "stage25_operator_docs_dynamic_sync_regression_atomicity_success": bool(sync_marker_regression_atomicity.get("success")),
        "stage25_operator_docs_dynamic_sync_regression_atomicity_failures": sync_marker_regression_atomicity.get("failure_count"),
        "stage25_operator_docs_dynamic_sync_regression_atomicity_sha256": hashlib.sha256(SYNC_MARKER_REGRESSION_ATOMICITY.read_bytes()).hexdigest() if SYNC_MARKER_REGRESSION_ATOMICITY.is_file() else None,
    }
    for field, expected in {**sync_policy_summary_values, **sync_current_summary_values, **marker_regression_summary_values}.items():
        if summary.get(field) != expected:
            failures.append({"check": "operator_docs_sync_summary_matches_source", "field": field, "observed": summary.get(field), "expected": expected})

    current_sync_contract_sha256 = hashlib.sha256(SYNC_CONTRACT_MODULE.read_bytes()).hexdigest() if SYNC_CONTRACT_MODULE.is_file() else None
    sync_contract_artifact = artifact_by_path.get("scripts/stage25_operator_docs_sync_contract.py") or {}
    if sync_policy.get("success") is not True or sync_policy.get("failure_count") != 0:
        failures.append({"check": "operator_docs_sync_policy_success", "observed": {"success": sync_policy.get("success"), "failure_count": sync_policy.get("failure_count")}, "expected": {"success": True, "failure_count": 0}})
    if sync_policy.get("contract_module_path") != str(SYNC_CONTRACT_MODULE.resolve()):
        failures.append({"check": "operator_docs_sync_policy_module_path_canonical", "observed": sync_policy.get("contract_module_path"), "expected": str(SYNC_CONTRACT_MODULE.resolve())})
    if sync_policy.get("contract_module_sha256") != current_sync_contract_sha256:
        failures.append({"check": "operator_docs_sync_policy_module_sha_current", "observed": sync_policy.get("contract_module_sha256"), "expected": current_sync_contract_sha256})
    if sync_contract_artifact.get("sha256") != current_sync_contract_sha256:
        failures.append({"check": "operator_docs_sync_contract_sha_matches_data_lake", "observed": sync_contract_artifact.get("sha256"), "expected": current_sync_contract_sha256})
    if sync_policy.get("expected_contract_version") != SYNC_POLICY_EXPECTED_VERSION:
        failures.append({"check": "operator_docs_sync_policy_version_exact", "observed": sync_policy.get("expected_contract_version"), "expected": SYNC_POLICY_EXPECTED_VERSION})
    if sync_policy.get("expected_contract_sha256") != SYNC_POLICY_EXPECTED_CONTRACT_SHA256:
        failures.append({"check": "operator_docs_sync_policy_contract_sha_exact", "observed": sync_policy.get("expected_contract_sha256"), "expected": SYNC_POLICY_EXPECTED_CONTRACT_SHA256})
    if sync_policy.get("expected_semantic_projection_version") != SYNC_POLICY_EXPECTED_SEMANTIC_PROJECTION_VERSION:
        failures.append({"check": "operator_docs_sync_policy_semantic_projection_version_exact", "observed": sync_policy.get("expected_semantic_projection_version"), "expected": SYNC_POLICY_EXPECTED_SEMANTIC_PROJECTION_VERSION})
    if sync_policy.get("expected_semantic_projection_test_vector_sha256") != SYNC_POLICY_EXPECTED_SEMANTIC_PROJECTION_TEST_VECTOR_SHA256:
        failures.append({"check": "operator_docs_sync_policy_semantic_projection_test_vector_exact", "observed": sync_policy.get("expected_semantic_projection_test_vector_sha256"), "expected": SYNC_POLICY_EXPECTED_SEMANTIC_PROJECTION_TEST_VECTOR_SHA256})
    observed_projection_specs = tuple(
        (str(row.get("role")), tuple(row.get("fields") or []))
        for row in sync_policy.get("expected_semantic_projection_specs") or []
    )
    if observed_projection_specs != SYNC_POLICY_EXPECTED_SEMANTIC_PROJECTION_SPECS:
        failures.append({"check": "operator_docs_sync_policy_semantic_projection_specs_exact", "observed": sync_policy.get("expected_semantic_projection_specs"), "expected": [{"role": role, "fields": list(fields)} for role, fields in SYNC_POLICY_EXPECTED_SEMANTIC_PROJECTION_SPECS]})
    if tuple(tuple(row) for row in sync_policy.get("expected_target_specs") or []) != SYNC_POLICY_EXPECTED_TARGET_SPECS:
        failures.append({"check": "operator_docs_sync_policy_targets_exact", "observed": sync_policy.get("expected_target_specs"), "expected": [list(row) for row in SYNC_POLICY_EXPECTED_TARGET_SPECS]})
    if tuple(sync_policy.get("expected_slots") or []) != SYNC_POLICY_EXPECTED_SLOTS:
        failures.append({"check": "operator_docs_sync_policy_slots_exact", "observed": sync_policy.get("expected_slots"), "expected": list(SYNC_POLICY_EXPECTED_SLOTS)})
    if tuple(tuple(row) for row in sync_policy.get("expected_upstream_input_specs") or []) != SYNC_POLICY_EXPECTED_UPSTREAM_INPUT_SPECS:
        failures.append({"check": "operator_docs_sync_policy_upstream_inputs_exact", "observed": sync_policy.get("expected_upstream_input_specs"), "expected": [list(row) for row in SYNC_POLICY_EXPECTED_UPSTREAM_INPUT_SPECS]})
    if sync_receipt.get("success") is not True or sync_receipt.get("failure_count") != 0 or sync_receipt.get("receipt_atomic_commit") is not True:
        failures.append({"check": "operator_docs_sync_receipt_success", "observed": {"success": sync_receipt.get("success"), "failure_count": sync_receipt.get("failure_count"), "receipt_atomic_commit": sync_receipt.get("receipt_atomic_commit")}, "expected": {"success": True, "failure_count": 0, "receipt_atomic_commit": True}})
    expected_sync_output = str((AI_ROOT / SYNC_POLICY_EXPECTED_OUTPUT_PATH_ID.split(":", 1)[1]).resolve())
    expected_sync_lock = str((AI_ROOT / SYNC_POLICY_EXPECTED_LOCK_PATH_ID.split(":", 1)[1]).resolve())
    if sync_receipt.get("observed_output_path") != expected_sync_output or sync_receipt.get("lock_path") != expected_sync_lock:
        failures.append({"check": "operator_docs_sync_receipt_paths_canonical", "observed": {"output": sync_receipt.get("observed_output_path"), "lock": sync_receipt.get("lock_path")}, "expected": {"output": expected_sync_output, "lock": expected_sync_lock}})
    if sync_receipt.get("contract_version") != SYNC_POLICY_EXPECTED_VERSION or sync_receipt.get("contract_sha256") != SYNC_POLICY_EXPECTED_CONTRACT_SHA256:
        failures.append({"check": "operator_docs_sync_receipt_contract_exact", "observed": {"version": sync_receipt.get("contract_version"), "sha256": sync_receipt.get("contract_sha256")}, "expected": {"version": SYNC_POLICY_EXPECTED_VERSION, "sha256": SYNC_POLICY_EXPECTED_CONTRACT_SHA256}})
    expected_sync_target_rows = len(SYNC_POLICY_EXPECTED_TARGET_SPECS) * len(SYNC_POLICY_EXPECTED_SLOTS)
    if sync_receipt.get("target_rows") != expected_sync_target_rows or sync_receipt.get("stale_rows") != 0 or sync_receipt.get("provenance_row_count") != len(SYNC_POLICY_EXPECTED_UPSTREAM_INPUT_SPECS):
        failures.append({"check": "operator_docs_sync_receipt_counts_exact", "observed": {"target_rows": sync_receipt.get("target_rows"), "stale_rows": sync_receipt.get("stale_rows"), "provenance_rows": sync_receipt.get("provenance_row_count")}, "expected": {"target_rows": expected_sync_target_rows, "stale_rows": 0, "provenance_rows": len(SYNC_POLICY_EXPECTED_UPSTREAM_INPUT_SPECS)}})
    if sync_current.get("semantic_provenance_rows") != len(SYNC_POLICY_EXPECTED_SEMANTIC_PROJECTION_SPECS):
        failures.append({"check": "operator_docs_sync_semantic_provenance_rows_exact", "observed": sync_current.get("semantic_provenance_rows"), "expected": len(SYNC_POLICY_EXPECTED_SEMANTIC_PROJECTION_SPECS)})
    current_sync_receipt_sha256 = hashlib.sha256(SYNC_RECEIPT.read_bytes()).hexdigest() if SYNC_RECEIPT.is_file() else None
    sync_receipt_artifact = artifact_by_path.get("reports/stage25_operator_docs_dynamic_status_sync_report.json") or {}
    if sync_current.get("success") is not True or sync_current.get("failure_count") != 0:
        failures.append({"check": "operator_docs_sync_current_validation_success", "observed": {"success": sync_current.get("success"), "failure_count": sync_current.get("failure_count")}, "expected": {"success": True, "failure_count": 0}})
    if sync_current.get("receipt_path") != str(SYNC_RECEIPT.resolve()) or sync_current.get("receipt_sha256") != current_sync_receipt_sha256:
        failures.append({"check": "operator_docs_sync_current_receipt_binding", "observed": {"path": sync_current.get("receipt_path"), "sha256": sync_current.get("receipt_sha256")}, "expected": {"path": str(SYNC_RECEIPT.resolve()), "sha256": current_sync_receipt_sha256}})
    if sync_receipt_artifact.get("sha256") != current_sync_receipt_sha256:
        failures.append({"check": "operator_docs_sync_receipt_sha_matches_data_lake", "observed": sync_receipt_artifact.get("sha256"), "expected": current_sync_receipt_sha256})
    marker_lock = str(SYNC_MARKER_REGRESSION_LOCK.resolve())
    marker_report_sha = hashlib.sha256(SYNC_MARKER_REGRESSION.read_bytes()).hexdigest() if SYNC_MARKER_REGRESSION.is_file() else None
    marker_current_sha = hashlib.sha256(SYNC_MARKER_REGRESSION_CURRENT.read_bytes()).hexdigest() if SYNC_MARKER_REGRESSION_CURRENT.is_file() else None
    marker_current_regression_sha = hashlib.sha256(SYNC_MARKER_REGRESSION_CURRENT_REGRESSION.read_bytes()).hexdigest() if SYNC_MARKER_REGRESSION_CURRENT_REGRESSION.is_file() else None
    marker_atomicity_sha = hashlib.sha256(SYNC_MARKER_REGRESSION_ATOMICITY.read_bytes()).hexdigest() if SYNC_MARKER_REGRESSION_ATOMICITY.is_file() else None
    expected_marker_scripts = {
        "regression_script_sha256": hashlib.sha256(SYNC_MARKER_REGRESSION_SCRIPT.read_bytes()).hexdigest(),
        "sync_script_sha256": hashlib.sha256((AI_ROOT / "scripts" / "sync_stage25_operator_docs_dynamic_status.py").read_bytes()).hexdigest(),
        "proof_io_sha256": hashlib.sha256(SYNC_MARKER_REGRESSION_PROOF_IO.read_bytes()).hexdigest(),
    }
    if sync_marker_regression.get("success") is not True or sync_marker_regression.get("case_rows") != 13 or sync_marker_regression.get("passed_rows") != 13 or sync_marker_regression.get("failed_rows") != 0 or sync_marker_regression.get("real_inputs_mutated") is not False:
        failures.append({"check": "operator_docs_marker_regression_success", "observed": {"success": sync_marker_regression.get("success"), "case_rows": sync_marker_regression.get("case_rows"), "passed_rows": sync_marker_regression.get("passed_rows"), "failed_rows": sync_marker_regression.get("failed_rows"), "real_inputs_mutated": sync_marker_regression.get("real_inputs_mutated")}, "expected": {"success": True, "case_rows": 13, "passed_rows": 13, "failed_rows": 0, "real_inputs_mutated": False}})
    if sync_marker_regression.get("output_path") != str(SYNC_MARKER_REGRESSION.resolve()) or sync_marker_regression.get("lock_path") != marker_lock or sync_marker_regression.get("lock_acquired") is not True or sync_marker_regression.get("atomic_commit") is not True:
        failures.append({"check": "operator_docs_marker_regression_commit_provenance", "observed": {"output": sync_marker_regression.get("output_path"), "lock": sync_marker_regression.get("lock_path"), "lock_acquired": sync_marker_regression.get("lock_acquired"), "atomic_commit": sync_marker_regression.get("atomic_commit")}, "expected": {"output": str(SYNC_MARKER_REGRESSION.resolve()), "lock": marker_lock, "lock_acquired": True, "atomic_commit": True}})
    for field, expected in expected_marker_scripts.items():
        if sync_marker_regression.get(field) != expected:
            failures.append({"check": "operator_docs_marker_regression_script_provenance", "field": field, "observed": sync_marker_regression.get(field), "expected": expected})
    if sync_marker_regression_current.get("success") is not True or sync_marker_regression_current.get("failure_count") != 0 or sync_marker_regression_current.get("case_count") != 13 or sync_marker_regression_current.get("regression_report_sha256") != marker_report_sha:
        failures.append({"check": "operator_docs_marker_regression_current_success", "observed": {"success": sync_marker_regression_current.get("success"), "failure_count": sync_marker_regression_current.get("failure_count"), "case_count": sync_marker_regression_current.get("case_count"), "regression_report_sha256": sync_marker_regression_current.get("regression_report_sha256")}, "expected": {"success": True, "failure_count": 0, "case_count": 13, "regression_report_sha256": marker_report_sha}})
    if sync_marker_regression_current.get("current_validator_script_sha256") != hashlib.sha256(SYNC_MARKER_REGRESSION_CURRENT_SCRIPT.read_bytes()).hexdigest() or sync_marker_regression_current.get("output_path") != str(SYNC_MARKER_REGRESSION_CURRENT.resolve()) or sync_marker_regression_current.get("lock_path") != marker_lock or sync_marker_regression_current.get("atomic_commit") is not True:
        failures.append({"check": "operator_docs_marker_regression_current_provenance", "observed": {"validator_sha": sync_marker_regression_current.get("current_validator_script_sha256"), "output": sync_marker_regression_current.get("output_path"), "lock": sync_marker_regression_current.get("lock_path"), "atomic_commit": sync_marker_regression_current.get("atomic_commit")}, "expected": {"validator_sha": hashlib.sha256(SYNC_MARKER_REGRESSION_CURRENT_SCRIPT.read_bytes()).hexdigest(), "output": str(SYNC_MARKER_REGRESSION_CURRENT.resolve()), "lock": marker_lock, "atomic_commit": True}})
    if sync_marker_regression_current_regression.get("success") is not True or sync_marker_regression_current_regression.get("failure_count") != 0 or sync_marker_regression_current_regression.get("passed_case_count") != 14 or sync_marker_regression_current_regression.get("real_inputs_mutated") is not False:
        failures.append({"check": "operator_docs_marker_regression_current_regression_success", "observed": {"success": sync_marker_regression_current_regression.get("success"), "failure_count": sync_marker_regression_current_regression.get("failure_count"), "passed_case_count": sync_marker_regression_current_regression.get("passed_case_count"), "real_inputs_mutated": sync_marker_regression_current_regression.get("real_inputs_mutated")}, "expected": {"success": True, "failure_count": 0, "passed_case_count": 14, "real_inputs_mutated": False}})
    if sync_marker_regression_current_regression.get("regression_script_sha256") != hashlib.sha256(SYNC_MARKER_REGRESSION_CURRENT_REGRESSION_SCRIPT.read_bytes()).hexdigest() or sync_marker_regression_current_regression.get("output_path") != str(SYNC_MARKER_REGRESSION_CURRENT_REGRESSION.resolve()) or sync_marker_regression_current_regression.get("lock_path") != marker_lock or sync_marker_regression_current_regression.get("atomic_commit") is not True:
        failures.append({"check": "operator_docs_marker_regression_current_regression_provenance", "observed": {"script_sha": sync_marker_regression_current_regression.get("regression_script_sha256"), "output": sync_marker_regression_current_regression.get("output_path"), "lock": sync_marker_regression_current_regression.get("lock_path"), "atomic_commit": sync_marker_regression_current_regression.get("atomic_commit")}, "expected": {"script_sha": hashlib.sha256(SYNC_MARKER_REGRESSION_CURRENT_REGRESSION_SCRIPT.read_bytes()).hexdigest(), "output": str(SYNC_MARKER_REGRESSION_CURRENT_REGRESSION.resolve()), "lock": marker_lock, "atomic_commit": True}})
    if sync_marker_regression_atomicity.get("success") is not True or sync_marker_regression_atomicity.get("failure_count") != 0 or sync_marker_regression_atomicity.get("passed_case_count") != 7 or sync_marker_regression_atomicity.get("real_inputs_mutated") is not False:
        failures.append({"check": "operator_docs_marker_regression_atomicity_success", "observed": {"success": sync_marker_regression_atomicity.get("success"), "failure_count": sync_marker_regression_atomicity.get("failure_count"), "passed_case_count": sync_marker_regression_atomicity.get("passed_case_count"), "real_inputs_mutated": sync_marker_regression_atomicity.get("real_inputs_mutated")}, "expected": {"success": True, "failure_count": 0, "passed_case_count": 7, "real_inputs_mutated": False}})
    if sync_marker_regression_atomicity.get("atomicity_script_sha256") != hashlib.sha256(SYNC_MARKER_REGRESSION_ATOMICITY_SCRIPT.read_bytes()).hexdigest() or sync_marker_regression_atomicity.get("output_path") != str(SYNC_MARKER_REGRESSION_ATOMICITY.resolve()) or sync_marker_regression_atomicity.get("lock_path") != marker_lock or sync_marker_regression_atomicity.get("atomic_commit") is not True:
        failures.append({"check": "operator_docs_marker_regression_atomicity_provenance", "observed": {"script_sha": sync_marker_regression_atomicity.get("atomicity_script_sha256"), "output": sync_marker_regression_atomicity.get("output_path"), "lock": sync_marker_regression_atomicity.get("lock_path"), "atomic_commit": sync_marker_regression_atomicity.get("atomic_commit")}, "expected": {"script_sha": hashlib.sha256(SYNC_MARKER_REGRESSION_ATOMICITY_SCRIPT.read_bytes()).hexdigest(), "output": str(SYNC_MARKER_REGRESSION_ATOMICITY.resolve()), "lock": marker_lock, "atomic_commit": True}})
    for path, observed_sha in ((SYNC_MARKER_REGRESSION, marker_report_sha), (SYNC_MARKER_REGRESSION_CURRENT, marker_current_sha), (SYNC_MARKER_REGRESSION_CURRENT_REGRESSION, marker_current_regression_sha), (SYNC_MARKER_REGRESSION_ATOMICITY, marker_atomicity_sha)):
        artifact = artifact_by_path.get(str(path.relative_to(AI_ROOT))) or {}
        if artifact.get("sha256") != observed_sha:
            failures.append({"check": "operator_docs_marker_proof_sha_matches_data_lake", "path": str(path), "observed": artifact.get("sha256"), "expected": observed_sha})
    if sync_policy_regression.get("success") is not True or sync_policy_regression.get("failed_rows") != 0 or sync_policy_regression.get("real_inputs_mutated") is not False:
        failures.append({"check": "operator_docs_sync_policy_regression_success", "observed": {"success": sync_policy_regression.get("success"), "failed_rows": sync_policy_regression.get("failed_rows"), "real_inputs_mutated": sync_policy_regression.get("real_inputs_mutated")}, "expected": {"success": True, "failed_rows": 0, "real_inputs_mutated": False}})
    if sync_current_regression.get("success") is not True or sync_current_regression.get("failed_rows") != 0 or sync_current_regression.get("real_inputs_mutated") is not False:
        failures.append({"check": "operator_docs_sync_current_regression_success", "observed": {"success": sync_current_regression.get("success"), "failed_rows": sync_current_regression.get("failed_rows"), "real_inputs_mutated": sync_current_regression.get("real_inputs_mutated")}, "expected": {"success": True, "failed_rows": 0, "real_inputs_mutated": False}})
    if sync_terminal_regression.get("success") is not True or sync_terminal_regression.get("failed_rows") != 0 or sync_terminal_regression.get("real_inputs_mutated") is not False:
        failures.append({"check": "operator_docs_sync_terminal_regression_success", "observed": {"success": sync_terminal_regression.get("success"), "failed_rows": sync_terminal_regression.get("failed_rows"), "real_inputs_mutated": sync_terminal_regression.get("real_inputs_mutated")}, "expected": {"success": True, "failed_rows": 0, "real_inputs_mutated": False}})
    safe_pipeline_current_summary_values: dict[str, Any] = {}
    if terminal_defer_mode_regression.get("success") is not True or terminal_defer_mode_regression.get("failed_rows") != 0 or terminal_defer_mode_regression.get("real_inputs_mutated") is not False:
        failures.append({"check": "terminal_defer_mode_regression_success", "observed": {"success": terminal_defer_mode_regression.get("success"), "failed_rows": terminal_defer_mode_regression.get("failed_rows"), "real_inputs_mutated": terminal_defer_mode_regression.get("real_inputs_mutated")}, "expected": {"success": True, "failed_rows": 0, "real_inputs_mutated": False}})
    if post_source_receipt_validation.get("receipt_valid") is not True or post_source_receipt_validation.get("failure_count") != 0:
        failures.append({"check": "post_source_receipt_current_validation_success", "observed": {"receipt_valid": post_source_receipt_validation.get("receipt_valid"), "failure_count": post_source_receipt_validation.get("failure_count")}, "expected": {"receipt_valid": True, "failure_count": 0}})
    if post_source_receipt_regression.get("failure_count") != 0 or post_source_receipt_regression.get("isolated_fixture") is not True or post_source_receipt_regression.get("real_inputs_mutated") is not False or post_source_receipt_regression.get("passed_case_count") != post_source_receipt_regression.get("case_count"):
        failures.append({"check": "post_source_receipt_regression_success", "observed": {"failure_count": post_source_receipt_regression.get("failure_count"), "isolated_fixture": post_source_receipt_regression.get("isolated_fixture"), "real_inputs_mutated": post_source_receipt_regression.get("real_inputs_mutated"), "passed_case_count": post_source_receipt_regression.get("passed_case_count"), "case_count": post_source_receipt_regression.get("case_count")}, "expected": {"failure_count": 0, "isolated_fixture": True, "real_inputs_mutated": False, "passed_case_count": "case_count"}})
    current_post_source_bindings = {
        "validation_report_path": str(POST_SOURCE_RECEIPT_VALIDATION.resolve()),
        "validation_report_sha256": hashlib.sha256(POST_SOURCE_RECEIPT_VALIDATION.read_bytes()).hexdigest() if POST_SOURCE_RECEIPT_VALIDATION.is_file() else None,
        "receipt_path": str(POST_SOURCE_RECEIPT.resolve()),
        "receipt_sha256": hashlib.sha256(POST_SOURCE_RECEIPT.read_bytes()).hexdigest() if POST_SOURCE_RECEIPT.is_file() else None,
        "validator_script_path": str(POST_SOURCE_VALIDATOR.resolve()),
        "validator_script_sha256": hashlib.sha256(POST_SOURCE_VALIDATOR.read_bytes()).hexdigest() if POST_SOURCE_VALIDATOR.is_file() else None,
        "current_validator_script_path": str(POST_SOURCE_VALIDATION_CURRENT_VALIDATOR.resolve()),
        "current_validator_script_sha256": hashlib.sha256(POST_SOURCE_VALIDATION_CURRENT_VALIDATOR.read_bytes()).hexdigest() if POST_SOURCE_VALIDATION_CURRENT_VALIDATOR.is_file() else None,
        "current_validation_output_path": str(POST_SOURCE_VALIDATION_CURRENT.resolve()),
        "current_validation_lock_path": str(POST_SOURCE_LOCK.resolve()),
        "current_validation_atomic_commit": True,
    }
    if post_source_validation_current.get("success") is not True or post_source_validation_current.get("failure_count") != 0:
        failures.append({"check": "post_source_validation_current_success", "observed": {"success": post_source_validation_current.get("success"), "failure_count": post_source_validation_current.get("failure_count")}, "expected": {"success": True, "failure_count": 0}})
    for field, expected in current_post_source_bindings.items():
        if post_source_validation_current.get(field) != expected:
            failures.append({"check": "post_source_validation_current_binding", "field": field, "observed": post_source_validation_current.get(field), "expected": expected})
    expected_current_regression_path = str(POST_SOURCE_VALIDATION_CURRENT_REGRESSION_SCRIPT.resolve())
    expected_current_regression_sha = hashlib.sha256(POST_SOURCE_VALIDATION_CURRENT_REGRESSION_SCRIPT.read_bytes()).hexdigest() if POST_SOURCE_VALIDATION_CURRENT_REGRESSION_SCRIPT.is_file() else None
    if post_source_validation_current_regression.get("success") is not True or post_source_validation_current_regression.get("failure_count") != 0 or post_source_validation_current_regression.get("failed_case_count") != 0 or post_source_validation_current_regression.get("passed_case_count") != post_source_validation_current_regression.get("case_count") or post_source_validation_current_regression.get("isolated_fixture") is not True or post_source_validation_current_regression.get("real_inputs_mutated") is not False:
        failures.append({"check": "post_source_validation_current_regression_success", "observed": {"success": post_source_validation_current_regression.get("success"), "failure_count": post_source_validation_current_regression.get("failure_count"), "failed_case_count": post_source_validation_current_regression.get("failed_case_count"), "passed_case_count": post_source_validation_current_regression.get("passed_case_count"), "case_count": post_source_validation_current_regression.get("case_count"), "isolated_fixture": post_source_validation_current_regression.get("isolated_fixture"), "real_inputs_mutated": post_source_validation_current_regression.get("real_inputs_mutated")}, "expected": {"success": True, "failure_count": 0, "failed_case_count": 0, "passed_case_count": "case_count", "isolated_fixture": True, "real_inputs_mutated": False}})
    if post_source_validation_current_regression.get("regression_script_path") != expected_current_regression_path or post_source_validation_current_regression.get("regression_script_sha256") != expected_current_regression_sha:
        failures.append({"check": "post_source_validation_current_regression_script_current", "observed": {"path": post_source_validation_current_regression.get("regression_script_path"), "sha256": post_source_validation_current_regression.get("regression_script_sha256")}, "expected": {"path": expected_current_regression_path, "sha256": expected_current_regression_sha}})
    expected_post_source_policy = {
        "policy_version": "stage25-post-source-drop-independent-policy-v1",
        "policy_script_path": str(POST_SOURCE_INDEPENDENT_POLICY_SCRIPT.resolve()),
        "policy_script_sha256": hashlib.sha256(POST_SOURCE_INDEPENDENT_POLICY_SCRIPT.read_bytes()).hexdigest() if POST_SOURCE_INDEPENDENT_POLICY_SCRIPT.is_file() else None,
        "builder_path": str((AI_ROOT / "scripts" / "build_stage25_post_source_drop_rerun_receipt_20260806.py").resolve()),
        "builder_sha256": hashlib.sha256((AI_ROOT / "scripts" / "build_stage25_post_source_drop_rerun_receipt_20260806.py").read_bytes()).hexdigest(),
        "validator_path": str(POST_SOURCE_VALIDATOR.resolve()),
        "validator_sha256": hashlib.sha256(POST_SOURCE_VALIDATOR.read_bytes()).hexdigest() if POST_SOURCE_VALIDATOR.is_file() else None,
        "receipt_path": str(POST_SOURCE_RECEIPT.resolve()),
        "receipt_sha256": hashlib.sha256(POST_SOURCE_RECEIPT.read_bytes()).hexdigest() if POST_SOURCE_RECEIPT.is_file() else None,
        "validation_path": str(POST_SOURCE_RECEIPT_VALIDATION.resolve()),
        "validation_sha256": hashlib.sha256(POST_SOURCE_RECEIPT_VALIDATION.read_bytes()).hexdigest() if POST_SOURCE_RECEIPT_VALIDATION.is_file() else None,
        "expected_builder_contract_version": "stage25-post-source-drop-rerun-receipt-v2",
        "expected_receipt_schema_version": 2,
        "expected_validation_schema_version": 3,
        "expected_command_contract_schema_version": 1,
        "expected_command_rows": 62,
        "expected_command_test_vector_sha256": "d35a00f41ae05a4bb9febabd61a0450d3f521d9f3297ff202fad6206e539e2eb",
        "observed_builder_command_test_vector_sha256": "d35a00f41ae05a4bb9febabd61a0450d3f521d9f3297ff202fad6206e539e2eb",
        "observed_receipt_command_test_vector_sha256": "d35a00f41ae05a4bb9febabd61a0450d3f521d9f3297ff202fad6206e539e2eb",
        "policy_output_path": str(POST_SOURCE_INDEPENDENT_POLICY.resolve()),
        "policy_lock_path": str(POST_SOURCE_LOCK.resolve()),
        "policy_atomic_commit": True,
        "safe_for_model_claim": False,
        "release_ready": False,
    }
    if post_source_independent_policy.get("success") is not True or post_source_independent_policy.get("failure_count") != 0:
        failures.append({"check": "post_source_independent_policy_success", "observed": {"success": post_source_independent_policy.get("success"), "failure_count": post_source_independent_policy.get("failure_count")}, "expected": {"success": True, "failure_count": 0}})
    for field, expected in expected_post_source_policy.items():
        if post_source_independent_policy.get(field) != expected:
            failures.append({"check": "post_source_independent_policy_current", "field": field, "observed": post_source_independent_policy.get(field), "expected": expected})
    expected_policy_regression_path = str(POST_SOURCE_INDEPENDENT_POLICY_REGRESSION_SCRIPT.resolve())
    expected_policy_regression_sha = hashlib.sha256(POST_SOURCE_INDEPENDENT_POLICY_REGRESSION_SCRIPT.read_bytes()).hexdigest() if POST_SOURCE_INDEPENDENT_POLICY_REGRESSION_SCRIPT.is_file() else None
    if post_source_independent_policy_regression.get("success") is not True or post_source_independent_policy_regression.get("failure_count") != 0 or post_source_independent_policy_regression.get("failed_case_count") != 0 or post_source_independent_policy_regression.get("passed_case_count") != post_source_independent_policy_regression.get("case_count") or post_source_independent_policy_regression.get("isolated_fixture") is not True or post_source_independent_policy_regression.get("real_inputs_mutated") is not False:
        failures.append({"check": "post_source_independent_policy_regression_success", "observed": {"success": post_source_independent_policy_regression.get("success"), "failure_count": post_source_independent_policy_regression.get("failure_count"), "failed_case_count": post_source_independent_policy_regression.get("failed_case_count"), "passed_case_count": post_source_independent_policy_regression.get("passed_case_count"), "case_count": post_source_independent_policy_regression.get("case_count"), "isolated_fixture": post_source_independent_policy_regression.get("isolated_fixture"), "real_inputs_mutated": post_source_independent_policy_regression.get("real_inputs_mutated")}, "expected": {"success": True, "failure_count": 0, "failed_case_count": 0, "passed_case_count": "case_count", "isolated_fixture": True, "real_inputs_mutated": False}})
    if post_source_independent_policy_regression.get("regression_script_path") != expected_policy_regression_path or post_source_independent_policy_regression.get("regression_script_sha256") != expected_policy_regression_sha:
        failures.append({"check": "post_source_independent_policy_regression_script_current", "observed": {"path": post_source_independent_policy_regression.get("regression_script_path"), "sha256": post_source_independent_policy_regression.get("regression_script_sha256")}, "expected": {"path": expected_policy_regression_path, "sha256": expected_policy_regression_sha}})
    current_policy_report_sha = hashlib.sha256(POST_SOURCE_INDEPENDENT_POLICY.read_bytes()).hexdigest() if POST_SOURCE_INDEPENDENT_POLICY.is_file() else None
    current_policy_validator_sha = hashlib.sha256(POST_SOURCE_INDEPENDENT_POLICY_CURRENT_VALIDATOR.read_bytes()).hexdigest() if POST_SOURCE_INDEPENDENT_POLICY_CURRENT_VALIDATOR.is_file() else None
    expected_policy_current = {
        "policy_report_path": str(POST_SOURCE_INDEPENDENT_POLICY.resolve()),
        "policy_report_sha256": current_policy_report_sha,
        "policy_script_path": str(POST_SOURCE_INDEPENDENT_POLICY_SCRIPT.resolve()),
        "policy_script_sha256": hashlib.sha256(POST_SOURCE_INDEPENDENT_POLICY_SCRIPT.read_bytes()).hexdigest() if POST_SOURCE_INDEPENDENT_POLICY_SCRIPT.is_file() else None,
        "builder_path": str((AI_ROOT / "scripts" / "build_stage25_post_source_drop_rerun_receipt_20260806.py").resolve()),
        "builder_sha256": hashlib.sha256((AI_ROOT / "scripts" / "build_stage25_post_source_drop_rerun_receipt_20260806.py").read_bytes()).hexdigest(),
        "validator_path": str(POST_SOURCE_VALIDATOR.resolve()),
        "validator_sha256": hashlib.sha256(POST_SOURCE_VALIDATOR.read_bytes()).hexdigest() if POST_SOURCE_VALIDATOR.is_file() else None,
        "receipt_path": str(POST_SOURCE_RECEIPT.resolve()),
        "receipt_sha256": hashlib.sha256(POST_SOURCE_RECEIPT.read_bytes()).hexdigest() if POST_SOURCE_RECEIPT.is_file() else None,
        "validation_path": str(POST_SOURCE_RECEIPT_VALIDATION.resolve()),
        "validation_sha256": hashlib.sha256(POST_SOURCE_RECEIPT_VALIDATION.read_bytes()).hexdigest() if POST_SOURCE_RECEIPT_VALIDATION.is_file() else None,
        "current_validator_script_path": str(POST_SOURCE_INDEPENDENT_POLICY_CURRENT_VALIDATOR.resolve()),
        "current_validator_script_sha256": current_policy_validator_sha,
        "current_output_path": str(POST_SOURCE_INDEPENDENT_POLICY_CURRENT.resolve()),
        "current_lock_path": str(POST_SOURCE_LOCK.resolve()),
        "current_atomic_commit": True,
        "expected_policy_version": "stage25-post-source-drop-independent-policy-v1",
        "expected_command_rows": 62,
        "expected_command_vector_sha256": "d35a00f41ae05a4bb9febabd61a0450d3f521d9f3297ff202fad6206e539e2eb",
        "safe_for_model_claim": False,
        "release_ready": False,
    }
    if post_source_independent_policy_current.get("success") is not True or post_source_independent_policy_current.get("failure_count") != 0:
        failures.append({"check": "post_source_independent_policy_current_success", "observed": {"success": post_source_independent_policy_current.get("success"), "failure_count": post_source_independent_policy_current.get("failure_count")}, "expected": {"success": True, "failure_count": 0}})
    for field, expected in expected_policy_current.items():
        if post_source_independent_policy_current.get(field) != expected:
            failures.append({"check": "post_source_independent_policy_current_binding", "field": field, "observed": post_source_independent_policy_current.get(field), "expected": expected})
    policy_artifact = artifact_by_path.get("reports/stage25_post_source_drop_rerun_independent_policy_validation_20260810.json") or {}
    if policy_artifact.get("sha256") != current_policy_report_sha:
        failures.append({"check": "post_source_independent_policy_sha_matches_data_lake", "observed": policy_artifact.get("sha256"), "expected": current_policy_report_sha})
    current_policy_artifact = artifact_by_path.get("reports/stage25_post_source_drop_rerun_independent_policy_current_20260810.json") or {}
    current_policy_report_sha = hashlib.sha256(POST_SOURCE_INDEPENDENT_POLICY_CURRENT.read_bytes()).hexdigest() if POST_SOURCE_INDEPENDENT_POLICY_CURRENT.is_file() else None
    if current_policy_artifact.get("sha256") != current_policy_report_sha:
        failures.append({"check": "post_source_independent_policy_current_sha_matches_data_lake", "observed": current_policy_artifact.get("sha256"), "expected": current_policy_report_sha})
    expected_policy_current_regression_path = str(POST_SOURCE_INDEPENDENT_POLICY_CURRENT_REGRESSION_SCRIPT.resolve())
    expected_policy_current_regression_sha = hashlib.sha256(POST_SOURCE_INDEPENDENT_POLICY_CURRENT_REGRESSION_SCRIPT.read_bytes()).hexdigest() if POST_SOURCE_INDEPENDENT_POLICY_CURRENT_REGRESSION_SCRIPT.is_file() else None
    if post_source_independent_policy_current_regression.get("success") is not True or post_source_independent_policy_current_regression.get("failure_count") != 0 or post_source_independent_policy_current_regression.get("case_count") != 16 or post_source_independent_policy_current_regression.get("passed_case_count") != 16 or post_source_independent_policy_current_regression.get("failed_case_count") != 0 or post_source_independent_policy_current_regression.get("isolated_fixture") is not True or post_source_independent_policy_current_regression.get("real_inputs_mutated") is not False:
        failures.append({"check": "post_source_independent_policy_current_regression_success", "observed": {"success": post_source_independent_policy_current_regression.get("success"), "failure_count": post_source_independent_policy_current_regression.get("failure_count"), "case_count": post_source_independent_policy_current_regression.get("case_count"), "passed_case_count": post_source_independent_policy_current_regression.get("passed_case_count"), "failed_case_count": post_source_independent_policy_current_regression.get("failed_case_count"), "isolated_fixture": post_source_independent_policy_current_regression.get("isolated_fixture"), "real_inputs_mutated": post_source_independent_policy_current_regression.get("real_inputs_mutated")}, "expected": {"success": True, "failure_count": 0, "case_count": 16, "passed_case_count": 16, "failed_case_count": 0, "isolated_fixture": True, "real_inputs_mutated": False}})
    if post_source_independent_policy_current_regression.get("regression_script_path") != expected_policy_current_regression_path or post_source_independent_policy_current_regression.get("regression_script_sha256") != expected_policy_current_regression_sha:
        failures.append({"check": "post_source_independent_policy_current_regression_script_current", "observed": {"path": post_source_independent_policy_current_regression.get("regression_script_path"), "sha256": post_source_independent_policy_current_regression.get("regression_script_sha256")}, "expected": {"path": expected_policy_current_regression_path, "sha256": expected_policy_current_regression_sha}})
    expected_atomicity_regression_path = str(CONSISTENCY_ATOMICITY_REGRESSION_SCRIPT.resolve())
    expected_atomicity_regression_sha = sha256(CONSISTENCY_ATOMICITY_REGRESSION_SCRIPT) if CONSISTENCY_ATOMICITY_REGRESSION_SCRIPT.is_file() else None
    current_validator_script = Path(__file__).resolve()
    if consistency_atomicity_regression.get("success") is not True or consistency_atomicity_regression.get("failure_count") != 0 or consistency_atomicity_regression.get("case_count") != 5 or consistency_atomicity_regression.get("passed_case_count") != 5 or consistency_atomicity_regression.get("failed_case_count") != 0 or consistency_atomicity_regression.get("isolated_fixture") is not True or consistency_atomicity_regression.get("real_inputs_mutated") is not False:
        failures.append({"check": "local_release_consistency_receipt_atomicity_regression_success", "observed": {"success": consistency_atomicity_regression.get("success"), "failure_count": consistency_atomicity_regression.get("failure_count"), "case_count": consistency_atomicity_regression.get("case_count"), "passed_case_count": consistency_atomicity_regression.get("passed_case_count"), "failed_case_count": consistency_atomicity_regression.get("failed_case_count"), "isolated_fixture": consistency_atomicity_regression.get("isolated_fixture"), "real_inputs_mutated": consistency_atomicity_regression.get("real_inputs_mutated")}, "expected": {"success": True, "failure_count": 0, "case_count": 5, "passed_case_count": 5, "failed_case_count": 0, "isolated_fixture": True, "real_inputs_mutated": False}})
    if consistency_atomicity_regression.get("regression_script_path") != expected_atomicity_regression_path or consistency_atomicity_regression.get("regression_script_sha256") != expected_atomicity_regression_sha or consistency_atomicity_regression.get("validator_script_path") != str(current_validator_script) or consistency_atomicity_regression.get("validator_script_sha256") != sha256(current_validator_script):
        failures.append({"check": "local_release_consistency_receipt_atomicity_regression_scripts_current", "observed": {"regression_path": consistency_atomicity_regression.get("regression_script_path"), "regression_sha256": consistency_atomicity_regression.get("regression_script_sha256"), "validator_path": consistency_atomicity_regression.get("validator_script_path"), "validator_sha256": consistency_atomicity_regression.get("validator_script_sha256")}, "expected": {"regression_path": expected_atomicity_regression_path, "regression_sha256": expected_atomicity_regression_sha, "validator_path": str(current_validator_script), "validator_sha256": sha256(current_validator_script)}})
    document_hash_by_path = {str(row.get("path")): row for row in sync_receipt.get("document_hashes") or []}
    for document in (NEXT_OPERATOR_DOC, DAILY_OPERATOR_DOC):
        current_sha = hashlib.sha256(document.read_bytes()).hexdigest() if document.is_file() else None
        if (document_hash_by_path.get(str(document.resolve())) or {}).get("after_sha256") != current_sha:
            failures.append({"check": "operator_docs_sync_document_sha_current", "path": str(document.resolve()), "observed": (document_hash_by_path.get(str(document.resolve())) or {}).get("after_sha256"), "expected": current_sha})

    release_contract = build_release_input_contract(data_lake)
    release_excluded_paths = release_contract["excluded_paths"]
    live_summary_values = {
        "data_lake_live_content_integrity_validated_root": live_integrity.get("validated_root"),
        "data_lake_live_content_integrity_validated_manifest_path": live_integrity.get("validated_manifest_path"),
        "data_lake_live_content_integrity_release_input_contract_version": live_integrity.get("release_input_contract_version"),
        "data_lake_live_content_integrity_release_input_contract_sha256": live_integrity.get("release_input_contract_sha256"),
        "data_lake_live_content_integrity_release_input_artifact_rows": live_integrity.get("release_input_artifact_rows"),
        "data_lake_live_content_integrity_release_input_excluded_paths": live_integrity.get("release_input_excluded_paths"),
        "data_lake_live_content_integrity_artifact_rows": live_integrity.get("artifact_rows"),
        "data_lake_live_content_integrity_strict_verified_rows": live_integrity.get("strict_verified_rows"),
        "data_lake_live_content_integrity_volatile_rows": live_integrity.get("volatile_existence_only_rows"),
    }
    for field, expected in live_summary_values.items():
        if summary.get(field) != expected:
            failures.append({"check": "live_integrity_summary_matches_report", "field": field, "observed": summary.get(field), "expected": expected})
    if live_integrity.get("success") is not True or live_integrity.get("failure_count") != 0:
        failures.append({"check": "canonical_live_integrity_success", "observed": {"success": live_integrity.get("success"), "failure_count": live_integrity.get("failure_count")}, "expected": {"success": True, "failure_count": 0}})
    if live_integrity.get("validated_root") != str(AI_ROOT):
        failures.append({"check": "canonical_live_integrity_root", "observed": live_integrity.get("validated_root"), "expected": str(AI_ROOT)})
    if live_integrity.get("validated_manifest_path") != str(DATA_LAKE.resolve()):
        failures.append({"check": "canonical_live_integrity_manifest_path", "observed": live_integrity.get("validated_manifest_path"), "expected": str(DATA_LAKE.resolve())})
    current_manifest_sha256 = hashlib.sha256(args.data_lake.read_bytes()).hexdigest() if args.data_lake.is_file() else None
    if live_integrity.get("validated_manifest_sha256") != current_manifest_sha256:
        failures.append({"check": "canonical_live_integrity_manifest_sha256", "observed": live_integrity.get("validated_manifest_sha256"), "expected": current_manifest_sha256})
    if live_integrity.get("release_input_contract_version") != CONTRACT_VERSION:
        failures.append({"check": "canonical_live_integrity_release_input_contract_version", "observed": live_integrity.get("release_input_contract_version"), "expected": CONTRACT_VERSION})
    if live_integrity.get("release_input_contract_sha256") != release_contract["sha256"]:
        failures.append({"check": "canonical_live_integrity_release_input_contract_sha256", "observed": live_integrity.get("release_input_contract_sha256"), "expected": release_contract["sha256"]})
    if live_integrity.get("release_input_artifact_rows") != release_contract["artifact_rows"]:
        failures.append({"check": "canonical_live_integrity_release_input_artifact_rows", "observed": live_integrity.get("release_input_artifact_rows"), "expected": release_contract["artifact_rows"]})
    if live_integrity.get("release_input_excluded_paths") != release_excluded_paths or set(release_excluded_paths) != RELEASE_INPUT_EXCLUDED_PATHS:
        failures.append({"check": "canonical_live_integrity_release_input_excluded_paths", "observed": live_integrity.get("release_input_excluded_paths"), "expected": sorted(RELEASE_INPUT_EXCLUDED_PATHS)})
    if live_integrity.get("artifact_rows") != len(artifacts):
        failures.append({"check": "canonical_live_integrity_artifact_rows", "observed": live_integrity.get("artifact_rows"), "expected": len(artifacts)})
    strict_rows = live_integrity.get("strict_verified_rows")
    volatile_rows = live_integrity.get("volatile_existence_only_rows")
    if not isinstance(strict_rows, int) or isinstance(strict_rows, bool) or not isinstance(volatile_rows, int) or isinstance(volatile_rows, bool) or strict_rows + volatile_rows != len(artifacts):
        failures.append({"check": "canonical_live_integrity_decomposition", "observed": {"strict": strict_rows, "volatile": volatile_rows}, "expected": len(artifacts)})
    configured_volatile = set(live_integrity.get("configured_volatile_existence_only_paths") or [])
    observed_volatile = set(live_integrity.get("volatile_existence_only_paths") or [])
    if configured_volatile != REQUIRED_LIVE_VOLATILE_PATHS or observed_volatile != REQUIRED_LIVE_VOLATILE_PATHS:
        failures.append({"check": "canonical_live_integrity_volatile_paths", "observed": {"configured": sorted(configured_volatile), "observed": sorted(observed_volatile)}, "expected": sorted(REQUIRED_LIVE_VOLATILE_PATHS)})
    for field in ("missing_rows", "unsafe_path_rows", "size_mismatch_rows", "sha256_mismatch_rows", "row_mismatch_rows"):
        if live_integrity.get(field) != 0:
            failures.append({"check": "canonical_live_integrity_zero_mismatch", "field": field, "observed": live_integrity.get(field), "expected": 0})

    blocked_capabilities = set(release.get("blocked_capabilities") or [])
    if not REQUIRED_BLOCKED_CAPABILITIES.issubset(blocked_capabilities):
        failures.append({
            "check": "required_blocked_capabilities_present",
            "missing": sorted(REQUIRED_BLOCKED_CAPABILITIES - blocked_capabilities),
            "observed": sorted(blocked_capabilities),
        })

    for field in sorted(REQUIRED_SUCCESS_SUMMARY_FLAGS):
        if defer_safe_pipeline_terminal and (field.startswith("stage25_fail_closed_validation_current_receipt_") or field.startswith("safe_training_pipeline_current_receipt_") or field.startswith("local_release_safety_guard_links_current_")):
            continue
        if summary.get(field) is not True:
            failures.append({"check": "summary_success_flag_true", "field": field, "observed": summary.get(field), "expected": True})
    for field in sorted(REQUIRED_ZERO_SUMMARY_FIELDS):
        if defer_safe_pipeline_terminal and (field.startswith("stage25_fail_closed_validation_current_receipt_") or field.startswith("safe_training_pipeline_current_receipt_") or field.startswith("local_release_safety_guard_links_current_")):
            continue
        if summary.get(field) != 0:
            failures.append({"check": "summary_zero_field", "field": field, "observed": summary.get(field), "expected": 0})
    for field in sorted(REQUIRED_FALSE_RISK_SUMMARY_FIELDS):
        if summary.get(field) is not False:
            failures.append({"check": "summary_false_risk_field", "field": field, "observed": summary.get(field), "expected": False})
    for field in sorted(REQUIRED_ZERO_RISK_SUMMARY_FIELDS):
        if summary.get(field) != 0:
            failures.append({"check": "summary_zero_risk_field", "field": field, "observed": summary.get(field), "expected": 0})
    discovered_risk_fields = {
        field
        for field in summary
        if any(token in field for token in HIGH_RISK_SUMMARY_TOKENS)
    }
    classified_risk_fields = (
        REQUIRED_FALSE_RISK_SUMMARY_FIELDS
        | REQUIRED_ZERO_RISK_SUMMARY_FIELDS
        | AUDITED_SOURCE_BOUND_RISK_SUMMARY_FIELDS
    )
    unclassified_risk_fields = sorted(discovered_risk_fields - classified_risk_fields)
    if unclassified_risk_fields:
        failures.append({
            "check": "unclassified_high_risk_summary_fields",
            "observed": unclassified_risk_fields,
            "expected": [],
        })
    missing_audited_risk_fields = sorted(AUDITED_SOURCE_BOUND_RISK_SUMMARY_FIELDS - set(summary))
    if missing_audited_risk_fields:
        failures.append({
            "check": "audited_source_bound_risk_summary_fields_present",
            "observed_missing": missing_audited_risk_fields,
            "expected": [],
        })
    dynamic_summary_values = {
        "human_decision_backlog_open_items": human_backlog.get("open_items"),
        "human_decision_backlog_missing_rows": human_backlog.get("total_missing_rows"),
        "human_decision_backlog_fail_closed_consistency_open_items": human_backlog_validation.get("open_items"),
        "human_decision_backlog_fail_closed_consistency_missing_rows": human_backlog_validation.get("total_missing_rows"),
        "review_draft_total_rows": review_draft_boundary.get("total_review_draft_rows"),
        "review_draft_formal_decision_rows": review_draft_boundary.get("total_formal_decision_rows"),
        "review_draft_rows_counted_as_formal_decisions": review_draft_boundary.get("draft_rows_counted_as_formal_decisions"),
        "model_claim_fail_closed_consistency_strict_rows": model_claim_consistency.get("strict_rows"),
        "model_claim_fail_closed_consistency_claim_eligible_rows": model_claim_consistency.get("claim_eligible_rows"),
    }
    for field, expected in dynamic_summary_values.items():
        if not isinstance(expected, int) or isinstance(expected, bool) or expected < 0:
            failures.append({"check": "dynamic_source_nonnegative_integer", "field": field, "observed": expected, "expected": ">=0 integer"})
        if summary.get(field) != expected:
            failures.append({"check": "summary_matches_dynamic_source", "field": field, "observed": summary.get(field), "expected": expected})
    promotion_summary_values = {
        "ready_to_verify_promotion_audit_rows": promotion_board.get("audit_rows"),
        "ready_to_verify_promotion_local_artifact_rows": promotion_board.get("local_artifact_completion_rows"),
        "ready_to_verify_promotion_verified_blocked_rows": promotion_board.get("verified_blocked_rows"),
        "ready_to_verify_promotion_automatic_rows": promotion_board.get("automatic_promotion_rows"),
        "ready_to_verify_promotion_validation_success": promotion_validation.get("success"),
        "ready_to_verify_promotion_validation_failures": promotion_validation.get("failure_count"),
        "ready_to_verify_promotion_regression_success": promotion_regression.get("success"),
        "ready_to_verify_promotion_regression_failed_rows": promotion_regression.get("failed_rows"),
    }
    for field, expected in promotion_summary_values.items():
        if summary.get(field) != expected:
            failures.append({"check": "promotion_summary_matches_source", "field": field, "observed": summary.get(field), "expected": expected})
    for source_name, source in (
        ("human_backlog_validation", human_backlog_validation),
        ("review_draft_boundary", review_draft_boundary),
        ("model_claim_consistency", model_claim_consistency),
    ):
        if source.get("success") is not True:
            failures.append({"check": f"{source_name}_success", "observed": source.get("success"), "expected": True})
        if source.get("failures") not in ([], None):
            failures.append({"check": f"{source_name}_failures_empty", "observed": source.get("failures"), "expected": []})
        if source.get("safe_for_model_claim") is not False:
            failures.append({"check": f"{source_name}_safe_for_model_claim_false", "observed": source.get("safe_for_model_claim"), "expected": False})
    if human_backlog.get("ready_items") != 0:
        failures.append({"check": "human_backlog_ready_items_zero", "observed": human_backlog.get("ready_items"), "expected": 0})
    if review_draft_boundary.get("draft_rows_counted_as_formal_decisions") != 0:
        failures.append({"check": "review_drafts_not_formal_decisions", "observed": review_draft_boundary.get("draft_rows_counted_as_formal_decisions"), "expected": 0})
    if model_claim_consistency.get("release_ready") is not False:
        failures.append({"check": "model_claim_consistency_release_ready_false", "observed": model_claim_consistency.get("release_ready"), "expected": False})
    for field in ("automatic_promotion_rows", "workstream_completion_ready_rows", "execution_ready_rows", "safe_for_training_import_rows", "safe_for_model_claim_rows", "customer_delivery_ready_rows", "release_ready_rows", "selected_variant_rows"):
        if promotion_board.get(field) != 0:
            failures.append({"check": "promotion_board_downstream_rows_zero", "field": field, "observed": promotion_board.get(field), "expected": 0})
    if promotion_validation.get("success") is not True or promotion_validation.get("failure_count") != 0:
        failures.append({"check": "promotion_validation_success", "observed": {"success": promotion_validation.get("success"), "failure_count": promotion_validation.get("failure_count")}, "expected": {"success": True, "failure_count": 0}})
    if promotion_validation.get("safe_for_model_claim") is not False or promotion_validation.get("release_ready") is not False:
        failures.append({"check": "promotion_validation_claim_release_false", "observed": {"safe_for_model_claim": promotion_validation.get("safe_for_model_claim"), "release_ready": promotion_validation.get("release_ready")}, "expected": {"safe_for_model_claim": False, "release_ready": False}})
    if promotion_regression.get("success") is not True or promotion_regression.get("failed_rows") != 0 or promotion_regression.get("real_inputs_mutated") is not False:
        failures.append({"check": "promotion_regression_success", "observed": {"success": promotion_regression.get("success"), "failed_rows": promotion_regression.get("failed_rows"), "real_inputs_mutated": promotion_regression.get("real_inputs_mutated")}, "expected": {"success": True, "failed_rows": 0, "real_inputs_mutated": False}})
    pending_index_rows = human_decision_pending_index.get("indexed_rows")
    if not isinstance(pending_index_rows, int) or isinstance(pending_index_rows, bool) or pending_index_rows <= 0:
        failures.append({"check": "pending_index_rows_positive_integer", "observed": pending_index_rows, "expected": ">0 integer"})
    if summary.get("human_decision_pending_index_rows") != pending_index_rows:
        failures.append({
            "check": "summary_matches_pending_index",
            "field": "human_decision_pending_index_rows",
            "observed": summary.get("human_decision_pending_index_rows"),
            "expected": pending_index_rows,
        })
    claim_allowed = claim_matrix.get("claims_allowed")
    claim_blocked = claim_matrix.get("claims_blocked")
    if summary.get("claim_matrix_allowed_claims") != claim_allowed:
        failures.append({
            "check": "summary_matches_claim_matrix",
            "field": "claim_matrix_allowed_claims",
            "observed": summary.get("claim_matrix_allowed_claims"),
            "expected": claim_allowed,
        })
    if summary.get("claim_matrix_blocked_claims") != claim_blocked:
        failures.append({
            "check": "summary_matches_claim_matrix",
            "field": "claim_matrix_blocked_claims",
            "observed": summary.get("claim_matrix_blocked_claims"),
            "expected": claim_blocked,
        })
    claim_policy_bindings = {
        "claim_promotion_decision_validation_success": claim_promotion.get("success"),
        "claim_promotion_decision_validation_failures": claim_promotion.get("failure_count"),
        "claim_promotion_decision_success": claim_promotion.get("ready_for_claim_promotion"),
        "claim_promotion_template_rows": claim_promotion.get("template_rows"),
        "claim_promotion_template_matches_expected_contract": claim_promotion.get("template_matches_expected_contract"),
        "claim_promotion_target_claim_rows": claim_promotion.get("target_claim_rows"),
        "claim_promotion_requirement_name": claim_promotion.get("claim_promotion_requirement_name"),
        "claim_promotion_target_claim_rows_with_contract_requirement": claim_promotion.get("target_claim_rows_with_promotion_contract_requirement"),
        "claim_promotion_target_claim_rows_with_contract_requirement_passed": claim_promotion.get("target_claim_rows_with_promotion_contract_requirement_passed"),
        "claim_promotion_target_claim_contract_requirement_complete": claim_promotion.get("target_claim_promotion_contract_requirement_complete"),
        "claim_promotion_target_claim_rows_with_contract_requirement_evidence": claim_promotion.get("target_claim_rows_with_promotion_contract_requirement_evidence"),
        "claim_promotion_target_claim_contract_requirement_evidence_complete": claim_promotion.get("target_claim_promotion_contract_requirement_evidence_complete"),
        "claim_promotion_required_evidence_artifact_count": claim_promotion.get("required_evidence_artifact_count"),
        "claim_promotion_required_evidence_artifacts": claim_promotion.get("required_evidence_artifacts"),
        "claim_promotion_required_validation_report_count": claim_promotion.get("required_validation_report_count"),
        "claim_promotion_required_validation_reports": claim_promotion.get("required_validation_reports"),
        "claim_promotion_decision_rows": claim_promotion.get("decision_rows"),
        "claim_promotion_approved_rows": claim_promotion.get("approved_rows"),
        "claim_promotion_missing_decisions": len(claim_promotion.get("missing_promotion_decisions") or []),
        "claim_promotion_validation_failures": len(claim_promotion.get("error_counts") or {}),
        "claim_policy_anchor_success": claim_policy_anchor.get("success"),
        "claim_policy_anchor_failures": claim_policy_anchor.get("failure_count"),
        "claim_policy_anchor_regression_success": claim_policy_anchor_regression.get("success"),
        "claim_policy_anchor_regression_passed_cases": claim_policy_anchor_regression.get("passed_case_count"),
        "claim_policy_anchor_regression_failed_rows": claim_policy_anchor_regression.get("failed_rows"),
        "claim_policy_anchor_regression_real_inputs_mutated": claim_policy_anchor_regression.get("real_inputs_mutated"),
        "claim_policy_version": claim_matrix_fail_closed_policy.get("policy_version"),
        "claim_policy_canonical_sha256": claim_matrix_fail_closed_policy.get("canonical_policy_sha256"),
        "claim_policy_test_vector_sha256": claim_matrix_fail_closed_policy.get("policy_test_vector_sha256"),
        "claim_matrix_source_parity_success": claim_matrix_fail_closed_policy.get("source_parity_success"),
        "claim_matrix_canonical_claim_ids": claim_matrix_fail_closed_policy.get("canonical_claim_ids"),
        "claim_matrix_all_claims_ready": claim_matrix_fail_closed_policy.get("all_claims_ready"),
        "claim_matrix_not_ready_claim_ids": claim_matrix_fail_closed_policy.get("not_ready_claim_ids"),
        "claim_matrix_promotion_policy_allows_all_claims": claim_matrix_fail_closed_policy.get("promotion_policy_allows_all_claims"),
        "claim_matrix_policy_current_success": claim_matrix_policy_current.get("success"),
        "claim_matrix_policy_current_failures": claim_matrix_policy_current.get("failure_count"),
        "claim_matrix_policy_current_regression_success": claim_matrix_policy_current_regression.get("success"),
        "claim_matrix_policy_current_regression_passed_cases": claim_matrix_policy_current_regression.get("passed_case_count"),
        "claim_matrix_policy_current_regression_failed_rows": claim_matrix_policy_current_regression.get("failed_rows"),
        "claim_matrix_policy_current_regression_real_inputs_mutated": claim_matrix_policy_current_regression.get("real_inputs_mutated"),
    }
    for field, expected in claim_policy_bindings.items():
        if summary.get(field) != expected:
            failures.append({
                "check": "summary_matches_claim_matrix_policy",
                "field": field,
                "observed": summary.get(field),
                "expected": expected,
            })
    if claim_promotion.get("required_validation_report_count") != 6:
        failures.append({
            "check": "claim_promotion_required_validation_report_count",
            "observed": claim_promotion.get("required_validation_report_count"),
            "expected": 6,
        })
    expected_required_reports = [
        "reports/claim_readiness_matrix.json",
        "reports/claim_readiness_matrix_fail_closed_policy_current_validation_report.json",
        "reports/claim_readiness_policy_anchor_validation_report.json",
        "reports/local_release_guard_coverage_validation_report.json",
        "reports/local_release_manifest.json",
        "reports/master_readiness_board_validation_report.json",
    ]
    if claim_promotion.get("required_validation_reports") != expected_required_reports:
        failures.append({
            "check": "claim_promotion_required_validation_reports",
            "observed": claim_promotion.get("required_validation_reports"),
            "expected": expected_required_reports,
        })
    expected_required_evidence_artifacts = [
        "reports/claim_readiness_matrix.json",
        "reports/local_release_manifest.json",
        "reports/master_readiness_board.json",
    ]
    if claim_promotion.get("required_evidence_artifact_count") != 3:
        failures.append({
            "check": "claim_promotion_required_evidence_artifact_count",
            "observed": claim_promotion.get("required_evidence_artifact_count"),
            "expected": 3,
        })
    if claim_promotion.get("required_evidence_artifacts") != expected_required_evidence_artifacts:
        failures.append({
            "check": "claim_promotion_required_evidence_artifacts",
            "observed": claim_promotion.get("required_evidence_artifacts"),
            "expected": expected_required_evidence_artifacts,
        })
    if claim_promotion.get("claim_promotion_requirement_name") != "claim-promotion evidence contract valid":
        failures.append({
            "check": "claim_promotion_requirement_name",
            "observed": claim_promotion.get("claim_promotion_requirement_name"),
            "expected": "claim-promotion evidence contract valid",
        })
    if claim_promotion.get("target_claim_rows_with_promotion_contract_requirement") != 9:
        failures.append({
            "check": "claim_promotion_target_claim_rows_with_contract_requirement",
            "observed": claim_promotion.get("target_claim_rows_with_promotion_contract_requirement"),
            "expected": 9,
        })
    if claim_promotion.get("target_claim_rows_with_promotion_contract_requirement_passed") != 9:
        failures.append({
            "check": "claim_promotion_target_claim_rows_with_contract_requirement_passed",
            "observed": claim_promotion.get("target_claim_rows_with_promotion_contract_requirement_passed"),
            "expected": 9,
        })
    if claim_promotion.get("target_claim_promotion_contract_requirement_complete") is not True:
        failures.append({
            "check": "claim_promotion_target_claim_contract_requirement_complete",
            "observed": claim_promotion.get("target_claim_promotion_contract_requirement_complete"),
            "expected": True,
        })
    if claim_promotion.get("target_claim_rows_with_promotion_contract_requirement_evidence") != 9:
        failures.append({
            "check": "claim_promotion_target_claim_rows_with_contract_requirement_evidence",
            "observed": claim_promotion.get("target_claim_rows_with_promotion_contract_requirement_evidence"),
            "expected": 9,
        })
    if claim_promotion.get("target_claim_promotion_contract_requirement_evidence_complete") is not True:
        failures.append({
            "check": "claim_promotion_target_claim_contract_requirement_evidence_complete",
            "observed": claim_promotion.get("target_claim_promotion_contract_requirement_evidence_complete"),
            "expected": True,
        })
    if claim_matrix_policy_current_regression.get("passed_case_count") != 11:
        failures.append({
            "check": "claim_matrix_policy_current_regression_passed_cases",
            "observed": claim_matrix_policy_current_regression.get("passed_case_count"),
            "expected": 11,
        })
    if claim_policy_anchor_regression.get("passed_case_count") != 8:
        failures.append({
            "check": "claim_policy_anchor_regression_passed_cases",
            "observed": claim_policy_anchor_regression.get("passed_case_count"),
            "expected": 8,
        })

    if summary.get("top_tier_model_ready_receipts_safe_for_training_import") is not False:
        failures.append({
            "check": "top_tier_ready_receipts_safe_for_training_import_false",
            "observed": summary.get("top_tier_model_ready_receipts_safe_for_training_import"),
            "expected": False,
        })
    if summary.get("top_tier_model_ready_receipts_safe_for_model_claim") is not False:
        failures.append({
            "check": "top_tier_ready_receipts_safe_for_model_claim_false",
            "observed": summary.get("top_tier_model_ready_receipts_safe_for_model_claim"),
            "expected": False,
        })

    report = {
        "schema_version": 2,
        "mode": "local_release_manifest_fail_closed_consistency",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "local_only": True,
        "success": not failures,
        "release_ready": release.get("release_ready"),
        "artifact_count": release.get("artifact_count"),
        "data_lake_artifact_count": len(artifacts),
        "data_lake_unique_path_rows": len(unique_artifact_paths),
        "data_lake_duplicate_final_paths": duplicate_final_paths,
        "data_lake_unsafe_artifact_paths": unsafe_artifact_paths,
        "data_lake_manifest_metadata": manifest_metadata,
        "min_expected_artifact_count": MIN_EXPECTED_ARTIFACT_COUNT,
        "missing_artifacts": release.get("missing_artifacts"),
        "checked_success_summary_flags": sorted(REQUIRED_SUCCESS_SUMMARY_FLAGS),
        "checked_zero_summary_fields": sorted(REQUIRED_ZERO_SUMMARY_FIELDS),
        "checked_false_risk_summary_fields": sorted(REQUIRED_FALSE_RISK_SUMMARY_FIELDS),
        "checked_zero_risk_summary_fields": sorted(REQUIRED_ZERO_RISK_SUMMARY_FIELDS),
        "high_risk_summary_tokens": sorted(HIGH_RISK_SUMMARY_TOKENS),
        "discovered_high_risk_summary_fields": sorted(discovered_risk_fields),
        "audited_source_bound_risk_summary_fields": sorted(AUDITED_SOURCE_BOUND_RISK_SUMMARY_FIELDS),
        "unclassified_high_risk_summary_fields": unclassified_risk_fields,
        "checked_dynamic_source_summary_values": dynamic_summary_values,
        "checked_promotion_summary_values": promotion_summary_values,
        "checked_live_integrity_summary_values": live_summary_values,
        "checked_contract_policy_summary_values": contract_policy_summary_values,
        "checked_semantic_policy_summary_values": semantic_policy_summary_values,
        "checked_operator_docs_sync_policy_summary_values": sync_policy_summary_values,
        "checked_operator_docs_sync_current_summary_values": sync_current_summary_values,
        "checked_safe_pipeline_current_summary_values": safe_pipeline_current_summary_values,
        "checked_dynamic_summary_values": {
            "claim_matrix_allowed_claims": claim_allowed,
            "claim_matrix_blocked_claims": claim_blocked,
            "human_decision_pending_index_rows": pending_index_rows,
            **dynamic_summary_values,
            **promotion_summary_values,
        },
        "failures": failures,
        "failure_count": len(failures),
        "safe_for_training_pipeline": not failures,
        "safe_for_model_claim": False,
        "safe_pipeline_terminal_deferred": defer_safe_pipeline_terminal,
        "semantic_contract_module_path": str(SEMANTIC_CONTRACT_MODULE.resolve()),
        "semantic_contract_module_sha256": sha256(SEMANTIC_CONTRACT_MODULE),
        "semantic_contract_version": CONSISTENCY_SEMANTIC_CONTRACT_VERSION,
        "semantic_contract_test_vector_sha256": consistency_semantic_test_vector_sha256(),
        **{
            "semantic_input_rows": semantic_inputs["input_rows"],
            "semantic_inputs_sha256": semantic_inputs["sha256"],
            "semantic_inputs": semantic_inputs["rows"],
        },
        **build_receipt_provenance(
            release_path=args.release,
            release_sha256=release_sha256,
            data_lake_path=args.data_lake,
            data_lake_sha256=data_lake_sha256,
            live_integrity_path=args.live_integrity,
            live_integrity_sha256=live_integrity_sha256,
            contract_policy_path=args.contract_policy,
            contract_policy_sha256=contract_policy_sha256,
            semantic_policy_path=args.semantic_policy,
            semantic_policy_sha256=semantic_policy_sha256,
            output_path=output_path,
            lock_path=lock_path,
        ),
        "policy": "The local release manifest is an internal review package only. It must keep release, model claim and training-import gates fail-closed while surfacing all unresolved human and data gates.",
    }
    try:
        write_json_atomic(output_path, report, fail_before_replace=args.fail_before_replace)
    except Exception as exc:
        lock_handle.close()
        print(json.dumps({
            "success": False,
            "error": f"receipt_commit_failed:{type(exc).__name__}:{exc}",
            "output": str(output_path),
        }, ensure_ascii=False))
        return 1
    lock_handle.close()
    print(json.dumps({
        "success": report["success"],
        "release_ready": report["release_ready"],
        "artifact_count": report["artifact_count"],
        "failures": len(failures),
        "output": str(output_path),
    }, ensure_ascii=False))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
