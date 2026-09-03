#!/usr/bin/env python3
"""Build the Stage 25 post-source-drop rerun receipt."""

from __future__ import annotations

import json
import hashlib
import fcntl
import os
import sys
import tempfile
from pathlib import Path


AI_ROOT = Path(__file__).resolve().parents[1]
ENZYME_DB_ROOT = Path("/Users/keweibo/科为博/05自动化程序/04研发工作区/酶数据库")
BACKEND_PYTHON = AI_ROOT.parent / "backend/.venv/bin/python"
OUTPUT = AI_ROOT / "reports" / "stage25_post_source_drop_rerun_receipt_20260806.json"
LOCK_PATH = AI_ROOT / "reports" / ".stage25_post_source_drop_rerun_receipt.lock"
BUILDER_CONTRACT_VERSION = "stage25-post-source-drop-rerun-receipt-v2"


COMMANDS = [
    {
        "step": 1,
        "name": "validate_legal_fulltext_intake",
        "cwd": str(ENZYME_DB_ROOT),
        "cmd": [sys.executable, "validate_fulltext_intake_20260806.py"],
        "expected_output": str(ENZYME_DB_ROOT / "fulltext_intake_validation_report_20260806.json"),
        "writes_sqlite": False,
        "blocks_apply_until_passed": True,
    },
    {
        "step": 2,
        "name": "validate_source_locator_review_queue",
        "cwd": str(ENZYME_DB_ROOT),
        "cmd": [sys.executable, "validate_fulltext_source_locator_review_queue_20260806.py"],
        "expected_output": str(ENZYME_DB_ROOT / "fulltext_source_locator_review_queue_validation_report_20260806.json"),
        "writes_sqlite": False,
        "blocks_apply_until_passed": True,
    },
    {
        "step": 3,
        "name": "extract_fulltext_evidence_draft",
        "cwd": str(ENZYME_DB_ROOT),
        "cmd": [sys.executable, "extract_fulltext_evidence_draft_20260806.py"],
        "expected_output": str(ENZYME_DB_ROOT / "fulltext_evidence_draft_20260806.json"),
        "writes_sqlite": False,
        "blocks_apply_until_passed": True,
    },
    {
        "step": 4,
        "name": "build_stage25_reviewer_package",
        "cwd": str(ENZYME_DB_ROOT),
        "cmd": [sys.executable, "build_stage25_reviewer_package_20260806.py"],
        "expected_output": str(ENZYME_DB_ROOT / "stage25_reviewer_package_20260806.json"),
        "writes_sqlite": False,
        "blocks_apply_until_passed": True,
    },
    {
        "step": 5,
        "name": "validate_source_drop_manifest",
        "cwd": str(AI_ROOT),
        "cmd": [sys.executable, "scripts/validate_stage25_source_drop_manifest_20260806.py"],
        "expected_output": str(AI_ROOT / "reports" / "stage25_source_drop_manifest_validation_20260806.json"),
        "writes_sqlite": False,
        "blocks_apply_until_passed": True,
    },
    {
        "step": 6,
        "name": "build_source_drop_inventory",
        "cwd": str(AI_ROOT),
        "cmd": [sys.executable, "scripts/build_stage25_source_drop_inventory_20260806.py"],
        "expected_output": str(AI_ROOT / "reports" / "stage25_source_drop_inventory_20260806.json"),
        "writes_sqlite": False,
        "blocks_apply_until_passed": True,
    },
    {
        "step": 7,
        "name": "validate_source_drop_inventory",
        "cwd": str(AI_ROOT),
        "cmd": [sys.executable, "scripts/validate_stage25_source_drop_inventory_20260806.py"],
        "expected_output": str(AI_ROOT / "reports" / "stage25_source_drop_inventory_validation_20260806.json"),
        "writes_sqlite": False,
        "blocks_apply_until_passed": True,
    },
    {
        "step": 8,
        "name": "validate_source_acquisition_receipts",
        "cwd": str(AI_ROOT),
        "cmd": [sys.executable, "scripts/validate_stage25_source_acquisition_receipts_20260807.py"],
        "expected_output": str(AI_ROOT / "reports" / "stage25_source_acquisition_receipts_validation_20260807.json"),
        "writes_sqlite": False,
        "blocks_apply_until_passed": True,
    },
    {
        "step": 9,
        "name": "validate_source_extraction_candidates",
        "cwd": str(AI_ROOT),
        "cmd": [sys.executable, "scripts/validate_stage25_source_extraction_candidates_20260807.py"],
        "expected_output": str(AI_ROOT / "reports" / "stage25_source_extraction_candidate_validation_20260807.json"),
        "writes_sqlite": False,
        "blocks_apply_until_passed": True,
    },
    {
        "step": 10,
        "name": "validate_source_extraction_candidate_reviewer_packet",
        "cwd": str(AI_ROOT),
        "cmd": [sys.executable, "scripts/validate_stage25_source_extraction_candidate_reviewer_packet_20260807.py"],
        "expected_output": str(AI_ROOT / "reports" / "stage25_source_extraction_candidate_reviewer_packet_validation_20260807.json"),
        "writes_sqlite": False,
        "blocks_apply_until_passed": True,
    },
    {
        "step": 11,
        "name": "validate_source_extraction_reviewer_closure_checklist",
        "cwd": str(AI_ROOT),
        "cmd": [sys.executable, "scripts/validate_stage25_source_extraction_reviewer_closure_checklist_20260807.py"],
        "expected_output": str(AI_ROOT / "reports" / "stage25_source_extraction_reviewer_closure_checklist_validation_20260807.json"),
        "writes_sqlite": False,
        "blocks_apply_until_passed": True,
    },
    {
        "step": 12,
        "name": "build_cm5_codon262_cross_read_audit",
        "cwd": str(AI_ROOT),
        "cmd": [str(BACKEND_PYTHON), "scripts/build_stage25_cm5_codon262_cross_read_audit_20260807.py"],
        "expected_output": str(AI_ROOT / "reports" / "stage25_cm5_codon262_cross_read_audit_20260807.json"),
        "writes_sqlite": False,
        "blocks_apply_until_passed": True,
    },
    {
        "step": 13,
        "name": "validate_cm5_codon262_cross_read_audit",
        "cwd": str(AI_ROOT),
        "cmd": [sys.executable, "scripts/validate_stage25_cm5_codon262_cross_read_audit_20260807.py"],
        "expected_output": str(AI_ROOT / "reports" / "stage25_cm5_codon262_cross_read_audit_validation_20260807.json"),
        "writes_sqlite": False,
        "blocks_apply_until_passed": True,
    },
    {
        "step": 14,
        "name": "build_cm5_codon262_sequence_quality_evidence_audit",
        "cwd": str(AI_ROOT),
        "cmd": [sys.executable, "scripts/build_stage25_cm5_codon262_sequence_quality_evidence_audit_20260807.py"],
        "expected_output": str(AI_ROOT / "reports" / "stage25_cm5_codon262_sequence_quality_evidence_audit_20260807.json"),
        "writes_sqlite": False,
        "blocks_apply_until_passed": True,
    },
    {
        "step": 15,
        "name": "validate_cm5_codon262_sequence_quality_evidence_audit",
        "cwd": str(AI_ROOT),
        "cmd": [sys.executable, "scripts/validate_stage25_cm5_codon262_sequence_quality_evidence_audit_20260807.py"],
        "expected_output": str(AI_ROOT / "reports" / "stage25_cm5_codon262_sequence_quality_evidence_audit_validation_20260807.json"),
        "writes_sqlite": False,
        "blocks_apply_until_passed": True,
    },
    {
        "step": 16,
        "name": "build_cm5_l262v_discrepancy_adjudication_packet",
        "cwd": str(AI_ROOT),
        "cmd": [sys.executable, "scripts/build_stage25_cm5_l262v_discrepancy_adjudication_packet_20260807.py"],
        "expected_output": str(AI_ROOT / "datasets" / "governance" / "stage25_cm5_l262v_discrepancy_adjudication_packet_20260807.jsonl"),
        "writes_sqlite": False,
        "blocks_apply_until_passed": True,
    },
    {
        "step": 17,
        "name": "validate_cm5_l262v_discrepancy_adjudication_packet",
        "cwd": str(AI_ROOT),
        "cmd": [sys.executable, "scripts/validate_stage25_cm5_l262v_discrepancy_adjudication_packet_20260807.py"],
        "expected_output": str(AI_ROOT / "reports" / "stage25_cm5_l262v_discrepancy_adjudication_packet_validation_20260807.json"),
        "writes_sqlite": False,
        "blocks_apply_until_passed": True,
    },
    {
        "step": 19,
        "name": "build_cm5_l262v_adjudication_evidence_intake",
        "cwd": str(AI_ROOT),
        "cmd": [sys.executable, "scripts/build_stage25_cm5_l262v_adjudication_evidence_intake_20260807.py"],
        "expected_output": str(AI_ROOT / "datasets" / "governance" / "stage25_cm5_l262v_adjudication_evidence_intake_20260807.jsonl"),
        "writes_sqlite": False,
        "blocks_apply_until_passed": True,
    },
    {
        "step": 20,
        "name": "validate_cm5_l262v_adjudication_evidence_intake",
        "cwd": str(AI_ROOT),
        "cmd": [sys.executable, "scripts/validate_stage25_cm5_l262v_adjudication_evidence_intake_20260807.py"],
        "expected_output": str(AI_ROOT / "reports" / "stage25_cm5_l262v_adjudication_evidence_intake_validation_20260807.json"),
        "writes_sqlite": False,
        "blocks_apply_until_passed": True,
    },
    {
        "step": 21,
        "name": "validate_cm5_l262v_public_source_probe_receipt",
        "cwd": str(AI_ROOT),
        "cmd": [sys.executable, "scripts/validate_stage25_cm5_l262v_public_source_probe_receipt_20260807.py"],
        "expected_output": str(AI_ROOT / "reports" / "stage25_cm5_l262v_public_source_probe_receipt_validation_20260807.json"),
        "writes_sqlite": False,
        "blocks_apply_until_passed": True,
    },
    {
        "step": 22,
        "name": "build_cm5_l262v_external_evidence_request_packet",
        "cwd": str(AI_ROOT),
        "cmd": [sys.executable, "scripts/build_stage25_cm5_l262v_external_evidence_request_packet_20260807.py"],
        "expected_output": str(AI_ROOT / "datasets" / "governance" / "stage25_cm5_l262v_external_evidence_request_packet_20260807.jsonl"),
        "writes_sqlite": False,
        "blocks_apply_until_passed": True,
    },
    {
        "step": 23,
        "name": "validate_cm5_l262v_external_evidence_request_packet",
        "cwd": str(AI_ROOT),
        "cmd": [sys.executable, "scripts/validate_stage25_cm5_l262v_external_evidence_request_packet_20260807.py"],
        "expected_output": str(AI_ROOT / "reports" / "stage25_cm5_l262v_external_evidence_request_packet_validation_20260807.json"),
        "writes_sqlite": False,
        "blocks_apply_until_passed": True,
    },
    {
        "step": 24,
        "name": "validate_cm5_l262v_external_evidence_receipts",
        "cwd": str(AI_ROOT),
        "cmd": [sys.executable, "scripts/validate_stage25_cm5_l262v_external_evidence_receipts_20260807.py"],
        "expected_output": str(AI_ROOT / "reports" / "stage25_cm5_l262v_external_evidence_receipt_validation_20260807.json"),
        "writes_sqlite": False,
        "blocks_apply_until_passed": True,
    },
    {
        "step": 25,
        "name": "validate_cm5_l262v_external_evidence_reviews",
        "cwd": str(AI_ROOT),
        "cmd": [sys.executable, "scripts/validate_stage25_cm5_l262v_external_evidence_reviews_20260807.py"],
        "expected_output": str(AI_ROOT / "reports" / "stage25_cm5_l262v_external_evidence_review_validation_20260807.json"),
        "writes_sqlite": False,
        "blocks_apply_until_passed": True,
    },
    {
        "step": 26,
        "name": "validate_cm5_l262v_adjudication_decision_intake",
        "cwd": str(AI_ROOT),
        "cmd": [sys.executable, "scripts/validate_stage25_cm5_l262v_adjudication_decision_intake_20260807.py"],
        "expected_output": str(AI_ROOT / "reports" / "stage25_cm5_l262v_adjudication_decision_intake_validation_20260807.json"),
        "writes_sqlite": False,
        "blocks_apply_until_passed": True,
    },
    {
        "step": 27,
        "name": "test_cm5_l262v_adjudication_review_binding",
        "cwd": str(AI_ROOT),
        "cmd": [sys.executable, "scripts/test_stage25_cm5_l262v_adjudication_review_binding_20260807.py"],
        "expected_output": str(AI_ROOT / "reports" / "stage25_cm5_l262v_adjudication_review_binding_regression_20260807.json"),
        "writes_sqlite": False,
        "blocks_apply_until_passed": True,
    },
    {
        "step": 28,
        "name": "test_cm5_l262v_adjudication_review_binding_tamper",
        "cwd": str(AI_ROOT),
        "cmd": [sys.executable, "scripts/test_stage25_cm5_l262v_adjudication_review_binding_tamper_20260807.py"],
        "expected_output": str(AI_ROOT / "reports" / "stage25_cm5_l262v_adjudication_review_binding_tamper_regression_20260807.json"),
        "writes_sqlite": False,
        "blocks_apply_until_passed": True,
    },
    {
        "step": 29,
        "name": "test_cm5_l262v_adjudication_evidence_path_safety",
        "cwd": str(AI_ROOT),
        "cmd": [sys.executable, "scripts/test_stage25_cm5_l262v_adjudication_evidence_path_safety_20260807.py"],
        "expected_output": str(AI_ROOT / "reports" / "stage25_cm5_l262v_adjudication_evidence_path_safety_regression_20260807.json"),
        "writes_sqlite": False,
        "blocks_apply_until_passed": True,
    },
    {
        "step": 30,
        "name": "test_cm5_l262v_adjudication_upstream_review_provenance",
        "cwd": str(AI_ROOT),
        "cmd": [sys.executable, "scripts/test_stage25_cm5_l262v_adjudication_upstream_review_provenance_20260807.py"],
        "expected_output": str(AI_ROOT / "reports" / "stage25_cm5_l262v_adjudication_upstream_review_provenance_regression_20260807.json"),
        "writes_sqlite": False,
        "blocks_apply_until_passed": True,
    },
    {
        "step": 31,
        "name": "test_cm5_l262v_adjudication_upstream_packet_provenance",
        "cwd": str(AI_ROOT),
        "cmd": [sys.executable, "scripts/test_stage25_cm5_l262v_adjudication_upstream_packet_provenance_20260807.py"],
        "expected_output": str(AI_ROOT / "reports" / "stage25_cm5_l262v_adjudication_upstream_packet_provenance_regression_20260807.json"),
        "writes_sqlite": False,
        "blocks_apply_until_passed": True,
    },
    {
        "step": 26,
        "name": "build_cm5_l262v_external_request_message_drafts",
        "cwd": str(AI_ROOT),
        "cmd": [sys.executable, "scripts/build_stage25_cm5_l262v_external_request_message_drafts_20260807.py"],
        "expected_output": str(AI_ROOT / "datasets" / "governance" / "stage25_cm5_l262v_external_request_message_drafts_20260807.jsonl"),
        "writes_sqlite": False,
        "blocks_apply_until_passed": True,
    },
    {
        "step": 27,
        "name": "validate_cm5_l262v_external_request_message_drafts",
        "cwd": str(AI_ROOT),
        "cmd": [sys.executable, "scripts/validate_stage25_cm5_l262v_external_request_message_drafts_20260807.py"],
        "expected_output": str(AI_ROOT / "reports" / "stage25_cm5_l262v_external_request_message_drafts_validation_20260807.json"),
        "writes_sqlite": False,
        "blocks_apply_until_passed": True,
    },
    {
        "step": 28,
        "name": "validate_cm5_l262v_external_request_authorizations",
        "cwd": str(AI_ROOT),
        "cmd": [sys.executable, "scripts/validate_stage25_cm5_l262v_external_request_authorizations_20260807.py"],
        "expected_output": str(AI_ROOT / "reports" / "stage25_cm5_l262v_external_request_authorization_validation_20260807.json"),
        "writes_sqlite": False,
        "blocks_apply_until_passed": True,
    },
    {
        "step": 25,
        "name": "build_cm5_l262v_external_request_send_guard",
        "cwd": str(AI_ROOT),
        "cmd": [sys.executable, "scripts/build_stage25_cm5_l262v_external_request_send_guard_20260807.py"],
        "expected_output": str(AI_ROOT / "reports" / "stage25_cm5_l262v_external_request_send_guard_20260807.json"),
        "writes_sqlite": False,
        "blocks_apply_until_passed": True,
    },
    {
        "step": 26,
        "name": "validate_cm5_l262v_external_request_send_guard",
        "cwd": str(AI_ROOT),
        "cmd": [sys.executable, "scripts/validate_stage25_cm5_l262v_external_request_send_guard_20260807.py"],
        "expected_output": str(AI_ROOT / "reports" / "stage25_cm5_l262v_external_request_send_guard_validation_20260807.json"),
        "writes_sqlite": False,
        "blocks_apply_until_passed": True,
    },
    {
        "step": 27,
        "name": "test_cm5_l262v_external_request_authorization_safety",
        "cwd": str(AI_ROOT),
        "cmd": [sys.executable, "scripts/test_stage25_cm5_l262v_external_request_authorization_safety_20260807.py"],
        "expected_output": str(AI_ROOT / "reports" / "stage25_cm5_l262v_external_request_authorization_safety_regression_20260807.json"),
        "writes_sqlite": False,
        "blocks_apply_until_passed": True,
    },
    {
        "step": 8,
        "name": "build_literature_web_search_receipt",
        "cwd": str(AI_ROOT),
        "cmd": [sys.executable, "scripts/build_stage25_literature_web_search_receipt_20260806.py"],
        "expected_output": str(AI_ROOT / "reports" / "stage25_literature_web_search_receipt_20260806.json"),
        "writes_sqlite": False,
        "blocks_apply_until_passed": True,
    },
    {
        "step": 7,
        "name": "validate_literature_web_search_receipt",
        "cwd": str(AI_ROOT),
        "cmd": [sys.executable, "scripts/validate_stage25_literature_web_search_receipt_20260806.py"],
        "expected_output": str(AI_ROOT / "reports" / "stage25_literature_web_search_receipt_validation_20260806.json"),
        "writes_sqlite": False,
        "blocks_apply_until_passed": True,
    },
    {
        "step": 8,
        "name": "build_source_acquisition_shortlist",
        "cwd": str(AI_ROOT),
        "cmd": [sys.executable, "scripts/build_stage25_source_acquisition_shortlist_20260806.py"],
        "expected_output": str(AI_ROOT / "reports" / "stage25_source_acquisition_shortlist_20260806.json"),
        "writes_sqlite": False,
        "blocks_apply_until_passed": True,
    },
    {
        "step": 9,
        "name": "validate_source_acquisition_shortlist",
        "cwd": str(AI_ROOT),
        "cmd": [sys.executable, "scripts/validate_stage25_source_acquisition_shortlist_20260806.py"],
        "expected_output": str(AI_ROOT / "reports" / "stage25_source_acquisition_shortlist_validation_20260806.json"),
        "writes_sqlite": False,
        "blocks_apply_until_passed": True,
    },
    {
        "step": 10,
        "name": "build_source_drop_extraction_readiness_candidate",
        "cwd": str(AI_ROOT),
        "cmd": [sys.executable, "scripts/build_stage25_source_drop_extraction_readiness_candidate_20260806.py"],
        "expected_output": str(AI_ROOT / "datasets" / "governance" / "stage25_source_drop_extraction_readiness_candidates_20260806.jsonl"),
        "writes_sqlite": False,
        "blocks_apply_until_passed": True,
    },
    {
        "step": 11,
        "name": "validate_source_drop_extraction_readiness_candidate",
        "cwd": str(AI_ROOT),
        "cmd": [sys.executable, "scripts/validate_stage25_source_drop_extraction_readiness_candidates_20260806.py"],
        "expected_output": str(AI_ROOT / "reports" / "stage25_source_drop_extraction_readiness_candidate_validation_20260806.json"),
        "writes_sqlite": False,
        "blocks_apply_until_passed": True,
    },
    {
        "step": 8,
        "name": "validate_reviewed_extraction_output_drafts",
        "cwd": str(AI_ROOT),
        "cmd": [sys.executable, "scripts/validate_stage25_reviewed_extraction_output_drafts_20260806.py"],
        "expected_output": str(AI_ROOT / "reports" / "stage25_reviewed_extraction_output_draft_validation_20260806.json"),
        "writes_sqlite": False,
        "blocks_apply_until_passed": True,
    },
    {
        "step": 9,
        "name": "build_family_apply_transaction_plan",
        "cwd": str(AI_ROOT),
        "cmd": [sys.executable, "scripts/build_stage25_family_apply_transaction_plan_20260806.py"],
        "expected_output": str(AI_ROOT / "reports" / "stage25_family_apply_transaction_plan_validation_20260806.json"),
        "writes_sqlite": False,
        "blocks_apply_until_passed": True,
    },
    {
        "step": 10,
        "name": "validate_family_apply_transaction_plan",
        "cwd": str(AI_ROOT),
        "cmd": [sys.executable, "scripts/validate_stage25_family_apply_transaction_plans_20260806.py"],
        "expected_output": str(AI_ROOT / "reports" / "stage25_family_apply_transaction_plan_validation_20260806.json"),
        "writes_sqlite": False,
        "blocks_apply_until_passed": True,
    },
    {
        "step": 11,
        "name": "build_paper_only_apply_plan",
        "cwd": str(ENZYME_DB_ROOT),
        "cmd": [
            sys.executable,
            "new_paper_candidates_dry_run_importer_20260805.py",
            "--paper-only-apply-dry-run",
            "--apply-plan",
            "stage25_paper_only_apply_plan_20260806.json",
        ],
        "expected_output": str(ENZYME_DB_ROOT / "stage25_paper_only_apply_plan_20260806.json"),
        "writes_sqlite": False,
        "blocks_apply_until_passed": True,
    },
    {
        "step": 12,
        "name": "validate_paper_only_apply_plan",
        "cwd": str(ENZYME_DB_ROOT),
        "cmd": [sys.executable, "validate_stage25_paper_only_apply_plan_20260806.py"],
        "expected_output": str(ENZYME_DB_ROOT / "stage25_paper_only_apply_plan_validation_20260806.json"),
        "writes_sqlite": False,
        "blocks_apply_until_passed": True,
    },
    {
        "step": 13,
        "name": "validate_proposal_set_consistency",
        "cwd": str(ENZYME_DB_ROOT),
        "cmd": [sys.executable, "validate_new_paper_proposal_set_consistency_20260806.py"],
        "expected_output": str(ENZYME_DB_ROOT / "new_paper_proposal_set_consistency_validation_report_20260806.json"),
        "writes_sqlite": False,
        "blocks_apply_until_passed": True,
    },
    {
        "step": 14,
        "name": "build_sqlite_backup_preflight",
        "cwd": str(ENZYME_DB_ROOT),
        "cmd": [sys.executable, "build_stage25_sqlite_backup_preflight_20260806.py"],
        "expected_output": str(ENZYME_DB_ROOT / "stage25_sqlite_backup_preflight_20260806.json"),
        "writes_sqlite": False,
        "blocks_apply_until_passed": True,
    },
    {
        "step": 15,
        "name": "validate_sqlite_backup_preflight",
        "cwd": str(ENZYME_DB_ROOT),
        "cmd": [sys.executable, "validate_stage25_sqlite_backup_preflight_20260806.py"],
        "expected_output": str(ENZYME_DB_ROOT / "stage25_sqlite_backup_preflight_validation_20260806.json"),
        "writes_sqlite": False,
        "blocks_apply_until_passed": True,
    },
    {
        "step": 16,
        "name": "build_stage25_fail_closed_summary",
        "cwd": str(ENZYME_DB_ROOT),
        "cmd": [sys.executable, "build_new_paper_stage25_fail_closed_validation_summary_20260806.py"],
        "expected_output": str(ENZYME_DB_ROOT / "new_paper_stage25_fail_closed_validation_summary_20260806.json"),
        "writes_sqlite": False,
        "blocks_apply_until_passed": True,
    },
    {
        "step": 17,
        "name": "validate_operator_docs_sync_contract_policy",
        "cwd": str(AI_ROOT),
        "cmd": [sys.executable, "scripts/validate_stage25_operator_docs_sync_contract_policy.py"],
        "expected_output": str(AI_ROOT / "reports" / "stage25_operator_docs_sync_contract_policy_validation_report.json"),
        "writes_sqlite": False,
        "blocks_apply_until_passed": True,
    },
    {
        "step": 18,
        "name": "sync_operator_docs_dynamic_status",
        "cwd": str(AI_ROOT),
        "cmd": [sys.executable, "scripts/sync_stage25_operator_docs_dynamic_status.py"],
        "expected_output": str(AI_ROOT / "reports" / "stage25_operator_docs_dynamic_status_sync_report.json"),
        "writes_sqlite": False,
        "blocks_apply_until_passed": True,
    },
    {
        "step": 19,
        "name": "validate_operator_docs_marker_regression",
        "cwd": str(AI_ROOT),
        "cmd": [sys.executable, "scripts/validate_stage25_operator_docs_dynamic_status_sync_regression.py"],
        "expected_output": str(AI_ROOT / "reports" / "stage25_operator_docs_dynamic_status_sync_regression_report.json"),
        "writes_sqlite": False,
        "blocks_apply_until_passed": True,
    },
    {
        "name": "validate_operator_docs_marker_regression_current",
        "cwd": str(AI_ROOT),
        "cmd": [sys.executable, "scripts/validate_stage25_operator_docs_dynamic_status_sync_regression_current.py"],
        "expected_output": str(AI_ROOT / "reports" / "stage25_operator_docs_dynamic_status_sync_regression_current_validation_report.json"),
        "writes_sqlite": False,
        "blocks_apply_until_passed": True,
    },
    {
        "name": "validate_operator_docs_marker_regression_current_regression",
        "cwd": str(AI_ROOT),
        "cmd": [sys.executable, "scripts/validate_stage25_operator_docs_dynamic_status_sync_regression_current_regression.py"],
        "expected_output": str(AI_ROOT / "reports" / "stage25_operator_docs_dynamic_status_sync_regression_current_regression_report.json"),
        "writes_sqlite": False,
        "blocks_apply_until_passed": True,
    },
    {
        "name": "validate_operator_docs_marker_regression_atomicity",
        "cwd": str(AI_ROOT),
        "cmd": [sys.executable, "scripts/validate_stage25_operator_docs_dynamic_status_sync_regression_atomicity_regression.py"],
        "expected_output": str(AI_ROOT / "reports" / "stage25_operator_docs_dynamic_status_sync_regression_atomicity_regression_report.json"),
        "writes_sqlite": False,
        "blocks_apply_until_passed": True,
    },
    {
        "name": "validate_operator_docs_sync_current_receipt",
        "cwd": str(AI_ROOT),
        "cmd": [sys.executable, "scripts/validate_stage25_operator_docs_sync_current_receipt.py"],
        "expected_output": str(AI_ROOT / "reports" / "stage25_operator_docs_sync_current_receipt_validation_report.json"),
        "writes_sqlite": False,
        "blocks_apply_until_passed": True,
    },
    {
        "step": 20,
        "name": "build_data_lake_manifest",
        "cwd": str(AI_ROOT),
        "cmd": [sys.executable, "scripts/build_data_lake_manifest.py"],
        "expected_output": str(AI_ROOT / "reports" / "data_lake_manifest.json"),
        "writes_sqlite": False,
        "blocks_apply_until_passed": True,
    },
    {
        "step": 21,
        "name": "build_local_release_manifest",
        "cwd": str(AI_ROOT),
        "cmd": [sys.executable, "scripts/build_local_release_manifest.py"],
        "expected_output": str(AI_ROOT / "reports" / "local_release_manifest.json"),
        "writes_sqlite": False,
        "blocks_apply_until_passed": True,
    },
    {
        "step": 22,
        "name": "validate_local_release_manifest_fail_closed_consistency",
        "cwd": str(AI_ROOT),
        "cmd": [sys.executable, "scripts/validate_local_release_manifest_fail_closed_consistency.py"],
        "expected_output": str(AI_ROOT / "reports" / "local_release_manifest_fail_closed_consistency_validation_report.json"),
        "writes_sqlite": False,
        "blocks_apply_until_passed": True,
    },
    {
        "step": 23,
        "name": "run_full_stage25_validation_chain",
        "cwd": str(AI_ROOT),
        "cmd": [sys.executable, "scripts/run_stage25_fail_closed_validation_20260806.py"],
        "expected_output": str(AI_ROOT / "reports" / "stage25_fail_closed_validation_run_report_20260806.json"),
        "writes_sqlite": False,
        "blocks_apply_until_passed": True,
    },
]


def normalize_commands() -> list[dict[str, object]]:
    commands = []
    for index, row in enumerate(COMMANDS, start=1):
        normalized = dict(row)
        normalized["step"] = index
        commands.append(normalized)
    return commands


def command_contract_sha256(commands: list[dict[str, object]]) -> str:
    payload = json.dumps(commands, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def fsync_directory(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def write_json_atomic(path: Path, payload: dict[str, object]) -> None:
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


def main() -> int:
    commands = normalize_commands()
    command_names = [str(row["name"]) for row in commands]
    duplicate_command_names = sorted({name for name in command_names if command_names.count(name) > 1})
    receipt = {
        "schema_version": 2,
        "created_at": "2026-08-06",
        "mode": "stage25_post_source_drop_rerun_receipt",
        "stage": 25,
        "rerun_ready": True,
        "command_rows": len(commands),
        "unique_command_name_rows": len(set(command_names)),
        "duplicate_command_names": duplicate_command_names,
        "command_names": command_names,
        "command_contract_schema_version": 1,
        "command_contract_sha256": command_contract_sha256(commands),
        "builder_contract_version": BUILDER_CONTRACT_VERSION,
        "builder_script_path": str(Path(__file__).resolve()),
        "builder_script_sha256": sha256(Path(__file__).resolve()),
        "output_path": str(OUTPUT.resolve()),
        "lock_path": str(LOCK_PATH.resolve()),
        "lock_acquired": True,
        "receipt_atomic_commit": True,
        "sqlite_write_command_rows": sum(1 for row in commands if row["writes_sqlite"]),
        "commands": commands,
        "rerun_trigger": "Run after legally obtained files are placed in 酶数据库/incoming/fulltext or canonical AI大模型 source-drop paths.",
        "completion_condition": "All commands return success; source evidence validators may then mark reviewed extraction and transaction plans ready.",
        "policy": "rerun_ready means the exact non-SQLite command recipe is available. It does not mean source evidence, reviewed extraction, or SQLite apply is ready.",
        "commands_executed": False,
        "commands_executed_rows": 0,
        "source_drop_event_receipted": False,
        "outputs_freshness_verified": False,
        "rerun_completion_receipted": False,
        "source_evidence_ready": False,
        "ready_for_reviewed_extraction": False,
        "ready_for_sqlite_apply": False,
        "external_sqlite_mutated": False,
        "formal_decision_rows_written": 0,
        "apply_executed": False,
        "export_safe_released": False,
        "safe_for_model_claim": False,
        "release_ready": False,
    }
    LOCK_PATH.parent.mkdir(parents=True, exist_ok=True)
    with LOCK_PATH.open("w", encoding="utf-8") as lock_handle:
        fcntl.flock(lock_handle.fileno(), fcntl.LOCK_EX)
        write_json_atomic(OUTPUT, receipt)
    print(json.dumps({"output": str(OUTPUT), "command_rows": receipt["command_rows"], "sqlite_write_command_rows": receipt["sqlite_write_command_rows"]}, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
