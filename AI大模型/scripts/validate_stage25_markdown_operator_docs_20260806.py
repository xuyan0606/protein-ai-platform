#!/usr/bin/env python3
"""Validate Stage 25 operator Markdown docs stay fail-closed."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path


AI_ROOT = Path(__file__).resolve().parents[1]
PLATFORM_ROOT = AI_ROOT.parent
OUTPUT = AI_ROOT / "reports" / "stage25_markdown_operator_docs_validation_20260806.json"
HUMAN_BACKLOG_VALIDATION = AI_ROOT / "reports" / "human_decision_backlog_fail_closed_consistency_validation_report.json"
ACTIVITY_RISK_IMPORT_VALIDATION = AI_ROOT / "reports" / "activity_risk_training_import_label_validation_report.json"
FIVE_HEAD_GAP_REPORT = AI_ROOT / "reports" / "five_head_training_sample_gap_queue_report.json"
FIVE_HEAD_EXECUTION_REPORT = AI_ROOT / "reports" / "five_head_training_execution_contract_report.json"
MODEL_ARTIFACT_GUARD_VALIDATION = AI_ROOT / "reports" / "model_artifact_claim_guard_validation_report.json"
STAGE25_RUNNER_REPORT = AI_ROOT / "reports" / "stage25_fail_closed_validation_run_report_20260806.json"
STAGE25_OVERALL_REPORT = AI_ROOT / "reports" / "stage25_overall_fail_closed_index_20260806.json"
STAGE25_HANDOFF_VALIDATION = AI_ROOT / "reports" / "stage25_handoff_bundle_manifest_validation_20260806.json"
STAGE25_RUNNER_SCRIPT = AI_ROOT / "scripts" / "run_stage25_fail_closed_validation_20260806.py"
STAGE25_OVERALL_BUILDER = AI_ROOT / "scripts" / "build_stage25_overall_fail_closed_index_20260806.py"
STAGE25_HANDOFF_BUILDER = AI_ROOT / "scripts" / "build_stage25_handoff_bundle_manifest_20260806.py"
LOCAL_RELEASE_MANIFEST = AI_ROOT / "reports" / "local_release_manifest.json"
POST_SOURCE_RECEIPT_VALIDATION = AI_ROOT / "reports" / "stage25_post_source_drop_rerun_receipt_validation_20260806.json"
POST_SOURCE_DRY_RUN_VALIDATION = AI_ROOT / "reports" / "stage25_post_source_drop_rerun_dry_run_audit_validation_20260806.json"

DOCS = [
    {
        "name": "next_operator_packet",
        "path": AI_ROOT / "reports" / "next_operator_packet_20260806.md",
        "required_terms": [
            "allow_apply=false",
            "external_sqlite_mutated=false",
            "apply_executed=false",
            "export_safe_released=false",
            "release_ready=false",
            "safe_for_model_claim=false",
            "benchmark_ready_for_model_claim=false",
            "release_status=not_released",
            "Identity-only allowlist patch: applied",
            "run_lock_path",
            "command_contract_valid=true",
            "commands_executed=false",
            "outputs_freshness_verified=false",
            "ready_for_source_drop_rerun=false",
            "exact_source_contract=true",
            "inventory_matches_manifest=true",
            "filesystem_state_matches=true",
            "filesystem_integrity_valid=true",
            "planned_metadata_review_rows=4",
            "paper_insert_count=0",
            "ready_for_sqlite_apply_rows=0",
            "proposal_sets_consistent=true",
            "consistent_by_surface_policy",
            "technical_smoke_passed=true",
            "technical_smoke_only=true",
            "parsed_rows=1",
            "formal_runtime_receipt_written=false",
            "approved_for_physical_ddg_runtime=false",
            "technical_smoke_artifact_rows=5",
            "formal_smoke_artifact_present_rows=0",
            "formal_smoke_artifact_missing_rows=5",
            "technical_smoke_substitution_allowed=false",
            "acquisition_integrity_verified=true",
            "receipt_rows=4",
            "public_asset_rows=2",
            "probe_only_rows=2",
            "source_file_obtained_rows=2",
            "source_file_not_obtained_rows=2",
            "zenodo_archive_integrity_verified=true",
            "cm5_sequence_member_verified=true",
            "L15R/S45T/K85P/K231R",
            "dsm4_composition_resolved=false",
            "reviewed_source_locator_rows=0",
            "candidate_rows=2",
            "declared_substitutions_corroborated=true",
            "undeclared_substitution_candidates=L262V",
            "nucleotide_pdb_discrepancy=true",
            "nucleotide_pdb_discrepancy_verified=true",
            "codon262_cross_read_matrix_verified=true",
            "codon262_sequence_member_rows=11",
            "codon262_coverage_rows=9",
            "codon262_no_coverage_rows=2",
            "codon262_wt_codon_rows=8",
            "codon262_variant_codon_rows=1",
            "sequence_text_only_rows=11",
            "quality_bearing_artifact_rows=0",
            "cm5_quality_evidence_available=false",
            "sequencing_artifact_hypothesis_confirmed=false",
            "cm5_independent_replicate_rows=0",
            "other_construct_context_can_resolve_cm5=false",
            "review_fields_empty=true",
            "evidence_rows=11",
            "allowed_adjudication_option_rows=4",
            "decision_rows=0",
            "valid_decision_rows=0",
            "evidence_artifact_rows=0",
            "accepted_review_rows=0",
            "review_bound_evidence_rows=0",
            "unreviewed_evidence_artifact_rows=0",
            "review_binding_valid=true",
            "slot_compatible_evidence_rows=0",
            "slot_incompatible_evidence_rows=0",
            "slot_binding_valid=true",
            "reviewer_bound_evidence_rows=0",
            "missing_review_reviewer_rows=0",
            "reviewer_provenance_valid=true",
            "review_binding_case_rows=3",
            "review_binding_passed_rows=3",
            "review_binding_tamper_case_rows=5",
            "review_binding_tamper_passed_rows=5",
            "forged_sha_rejected_rows=1",
            "cross_bound_review_rejected_rows=1",
            "unsupported_option_rejected_rows=1",
            "slot_class_mismatch_rejected_rows=1",
            "invalid_decision_timestamp_rejected_rows=1",
            "path_safety_case_rows=3",
            "path_safety_passed_rows=3",
            "duplicate_review_id_rejected_rows=1",
            "unsafe_relative_path_rejected_rows=1",
            "missing_artifact_rejected_rows=1",
            "upstream_provenance_case_rows=3",
            "upstream_provenance_passed_rows=3",
            "invalid_upstream_review_intake_rejected_rows=1",
            "stale_review_input_sha_rejected_rows=1",
            "stale_receipt_input_sha_rejected_rows=1",
            "packet_provenance_case_rows=3",
            "packet_provenance_passed_rows=3",
            "invalid_packet_validation_rejected_rows=1",
            "upstream_review_fields_nonempty_rejected_rows=1",
            "allowed_decision_set_drift_rejected_rows=1",
            "real_decision_input_mutated=false",
            "real_review_input_mutated=false",
            "real_receipt_input_mutated=false",
            "discrepancy_resolved_rows=0",
            "slot_rows=4",
            "unique_path_rows=4",
            "present_rows=0",
            "missing_rows=4",
            "filesystem_parity_rows=4",
            "reviewed_evidence_rows=0",
            "ready_for_adjudication_rows=0",
            "file_presence_is_reviewed_evidence=false",
            "probe_rows=4",
            "metadata_only_rows=3",
            "zenodo_archive_only_rows=1",
            "slot_artifact_rows=0",
            "evidence_slot_missing_rows=4",
            "No paywall bypass",
            "request_rows=4",
            "unique_request_rows=4",
            "request_sent_rows=0",
            "outbound_authorization_rows=0",
            "evidence_received_rows=0",
            "completion_ready_rows=0",
            "authorization_rows=0",
            "valid_authorization_rows=0",
            "authorized_send_rows=0",
            "send_ready_candidate_rows=0",
            "external_message_sent=false",
            "send_executor_present=false",
            "blocked_no_authorization_and_no_executor",
            "draft_rows=4",
            "message-approved rows=0",
            "request-sent rows=0",
            "external-message-sent rows=0",
            "evidence-received rows=0",
            "message_draft_validation_valid=true",
            "message_draft_rows=4",
            "message_draft_request_rows=4",
            "message_sha_bound_authorization_rows=0",
            "case_rows=2",
            "passed_rows=2",
            "failed_rows=0",
            "real_authorization_input_mutated=false",
            "receipt_rows=0",
            "valid_receipt_rows=0",
            "present_artifact_rows=0",
            "unreceipted_present_artifact_rows=0",
            "receipt_without_artifact_rows=0",
            "receipt_is_reviewed_evidence=false",
            "review_rows=0",
            "valid_review_rows=0",
            "accepted_for_adjudication_rows=0",
            "unreviewed_valid_receipt_rows=0",
            "review_is_adjudication=false",
            "complete_composition_unambiguous=false",
            "cm5_composition_candidate_resolved=false",
            "cm5_composition_formally_reviewed=false",
            "complete_cm5_candidate_residue_rows=4",
            "mutation_effect_measurement_rows=0",
            "packet_rows=2",
            "reviewer_packet_valid=true",
            "reviewer_rows=2",
            "needs_more_info_rows=2",
            "candidate_ready_for_human_review_rows=2",
            "composition_candidate_resolved_rows=0",
            "dsm4_unresolved_rows=1",
            "cm5_composition_ambiguous_rows=1",
            "nucleotide_pdb_discrepancy_rows=1",
            "approved_rows=0",
            "formal_review_rows=0",
            "reviewed_extraction_rows=0",
            "reviewer_filled_rows=0",
            "source_locator_rows=0",
            "checklist_valid=true",
            "checklist_rows=12",
            "dsm4_rows=5",
            "cm5_rows=7",
            "cm5_l262v_discrepancy_rows=1",
            "missing_rows=12",
            "needs_more_info_rows=12",
            "evidence_supplied_rows=0",
            "reviewed_rows=0",
            "completed_rows=0",
            "audit_valid=true",
            "read_rows=11",
            "covered_rows=9",
            "not_covered_rows=2",
            "ttg_rows=8",
            "gtg_rows=1",
            "cross_read_consensus_supports_wt_leu262=true",
            "cm5_single_read_outlier=true",
            "discrepancy_resolved=false",
            "sequencing_file_rows=12",
            "seq_read_rows=11",
            "sequence_text_only_rows=11",
            "quality_bearing_artifact_rows=0",
            "chromatogram_artifact_rows=0",
            "per_base_quality_artifact_rows=0",
            "cm5_codon_262_raw_text_call=GTG",
            "cm5_quality_evidence_available=false",
            "sequencing_artifact_hypothesis_confirmed=false",
            "structured_locator_candidate_count=7",
            "foldx_buildmodel_technical_smoke_executed=true",
            "foldx_buildmodel_physical_smoke_executed=false",
            "parameterization_dependency_warning_detected=true",
            "parameterization_warning_command_count=2",
            "unrecognized_atom_rows=110",
            "unrecognized_molecule_names=5CM,5NC,SAH",
            "parameterization_review_completed=false",
            "ddg_value_technical_only=true",
            "energetic_interpretation_approved=false",
            "physical_ddg_comparable=false",
            "safe_for_benchmark_intake=false",
            "extraction_candidate_valid=true",
            "table_s1_primer_rows=38",
            "table_s2_disulfide_bridge_rows=4",
            "dsm4_composition_resolved=false",
            "complete_dsm4_residue_rows=0",
            "wt_absolute_baseline_rows=0",
            "measurement_locator_rows=0",
            "reviewed_source_locator_rows=0",
            "candidate_rows=2",
            "cm5_composition_candidate_resolved=false",
            "cm5_composition_formally_reviewed=false",
            "complete_cm5_candidate_residue_rows=4",
            "mutation_effect_measurement_rows=0",
            "allowlist=6",
            "intake_manifest=4",
            "locator_queue=4",
            "apply_plan=7",
            "file presence",
            "reviewed source locators",
            "SQLite apply approval",
            "Do not write SQLite",
        ],
        "forbidden_terms": [
            "111 files checksummed",
            "115 files checksummed",
            "119 files checksummed",
            "121 files checksummed",
            "123 files checksummed",
            "127 files checksummed",
            "131 files checksummed",
            "129 files checksummed",
            "133 files checksummed",
            "command_count=75",
            "summary_count=41",
            "summary_count=42",
            "command_count=77",
            "summary_count=43",
            "command_count=84",
            "summary_count=49",
            "bundle_rows=151",
            "freshness_verified_rows=150",
            "smoke artifacts remain missing",
            "5 remaining smoke/provision artifacts missing",
            "command_count=73",
            "command_count=71",
            "command_count=69",
            "command_count=67",
            "command_count=65",
            "command_count=63",
            "summary_count=40",
            "summary_count=39",
            "summary_count=38",
            "summary_count=37",
            "summary_count=36",
            "bundle_rows=111",
            "bundle_rows=107",
            "command_rows=19",
            "command_rows=20",
            "command_rows=26",
            "artifact_count=1582",
            "artifact_count=1640",
            "command_count=78",
            "summary_count=44",
            "135 files checksummed",
            "freshness_verified_rows=134",
            "command_count=79",
            "summary_count=45",
            "138 files checksummed",
            "bundle_rows=138",
            "freshness_verified_rows=137",
            "it is ready for use after local source files are placed",
            "144 files checksummed",
            "command_count=81",
            "summary_count=47",
            "freshness_verified_rows=143",
        ],
    },
    {
        "name": "daily_report",
        "path": PLATFORM_ROOT / "docs" / "manuals" / "2026-08-06-daily-report.md",
        "required_terms": [
            "Overall status: `validated_but_blocked`",
            "allow_apply=false",
            "external_sqlite_mutated=false",
            "apply_executed=false",
            "export_safe_released=false",
            "release_status=not_released",
            "release_ready=false",
            "safe_for_model_claim=false",
            "benchmark_ready_for_model_claim=false",
            "formal_decision_rows_written=0",
            "run_lock_path",
            "command_contract_valid=true",
            "commands_executed=false",
            "outputs_freshness_verified=false",
            "ready_for_source_drop_rerun=false",
            "exact_source_contract=true",
            "inventory_matches_manifest=true",
            "filesystem_state_matches=true",
            "filesystem_integrity_valid=true",
            "planned_metadata_review_rows=4",
            "paper_insert_count=0",
            "ready_for_sqlite_apply_rows=0",
            "proposal_sets_consistent=true",
            "consistent_by_surface_policy",
            "technical_smoke_passed=true",
            "technical_smoke_only=true",
            "parsed_rows=1",
            "formal_runtime_receipt_written=false",
            "approved_for_physical_ddg_runtime=false",
            "technical_smoke_artifact_rows=5",
            "formal_smoke_artifact_present_rows=0",
            "formal_smoke_artifact_missing_rows=5",
            "technical_smoke_substitution_allowed=false",
            "acquisition_integrity_verified=true",
            "receipt_rows=4",
            "public_asset_rows=2",
            "probe_only_rows=2",
            "source_file_obtained_rows=2",
            "source_file_not_obtained_rows=2",
            "zenodo_archive_integrity_verified=true",
            "cm5_sequence_member_verified=true",
            "L15R/S45T/K85P/K231R",
            "declared_substitutions_corroborated=true",
            "undeclared_substitution_candidates=L262V",
            "nucleotide_pdb_discrepancy=true",
            "nucleotide_pdb_discrepancy_verified=true",
            "codon262_cross_read_matrix_verified=true",
            "codon262_sequence_member_rows=11",
            "codon262_coverage_rows=9",
            "codon262_no_coverage_rows=2",
            "codon262_wt_codon_rows=8",
            "codon262_variant_codon_rows=1",
            "sequence_text_only_rows=11",
            "quality_bearing_artifact_rows=0",
            "cm5_quality_evidence_available=false",
            "sequencing_artifact_hypothesis_confirmed=false",
            "cm5_independent_replicate_rows=0",
            "other_construct_context_can_resolve_cm5=false",
            "review_fields_empty=true",
            "evidence_rows=11",
            "allowed_adjudication_option_rows=4",
            "decision_rows=0",
            "valid_decision_rows=0",
            "evidence_artifact_rows=0",
            "accepted_review_rows=0",
            "review_bound_evidence_rows=0",
            "unreviewed_evidence_artifact_rows=0",
            "review_binding_valid=true",
            "slot_compatible_evidence_rows=0",
            "slot_incompatible_evidence_rows=0",
            "slot_binding_valid=true",
            "reviewer_bound_evidence_rows=0",
            "missing_review_reviewer_rows=0",
            "reviewer_provenance_valid=true",
            "review_binding_case_rows=3",
            "review_binding_passed_rows=3",
            "review_binding_tamper_case_rows=5",
            "review_binding_tamper_passed_rows=5",
            "forged_sha_rejected_rows=1",
            "cross_bound_review_rejected_rows=1",
            "unsupported_option_rejected_rows=1",
            "slot_class_mismatch_rejected_rows=1",
            "invalid_decision_timestamp_rejected_rows=1",
            "path_safety_case_rows=3",
            "path_safety_passed_rows=3",
            "duplicate_review_id_rejected_rows=1",
            "unsafe_relative_path_rejected_rows=1",
            "missing_artifact_rejected_rows=1",
            "upstream_provenance_case_rows=3",
            "upstream_provenance_passed_rows=3",
            "invalid_upstream_review_intake_rejected_rows=1",
            "stale_review_input_sha_rejected_rows=1",
            "stale_receipt_input_sha_rejected_rows=1",
            "packet_provenance_case_rows=3",
            "packet_provenance_passed_rows=3",
            "invalid_packet_validation_rejected_rows=1",
            "upstream_review_fields_nonempty_rejected_rows=1",
            "allowed_decision_set_drift_rejected_rows=1",
            "real_decision_input_mutated=false",
            "real_review_input_mutated=false",
            "real_receipt_input_mutated=false",
            "discrepancy_resolved_rows=0",
            "slot_rows=4",
            "unique_path_rows=4",
            "present_rows=0",
            "missing_rows=4",
            "filesystem_parity_rows=4",
            "reviewed_evidence_rows=0",
            "ready_for_adjudication_rows=0",
            "file_presence_is_reviewed_evidence=false",
            "probe_rows=4",
            "metadata_only_rows=3",
            "zenodo_archive_only_rows=1",
            "slot_artifact_rows=0",
            "evidence_slot_missing_rows=4",
            "No paywall bypass",
            "request_rows=4",
            "unique_request_rows=4",
            "request_sent_rows=0",
            "outbound_authorization_rows=0",
            "evidence_received_rows=0",
            "completion_ready_rows=0",
            "authorization_rows=0",
            "valid_authorization_rows=0",
            "authorized_send_rows=0",
            "send_ready_candidate_rows=0",
            "external_message_sent=false",
            "send_executor_present=false",
            "blocked_no_authorization_and_no_executor",
            "draft_rows=4",
            "message-approved rows=0",
            "request-sent rows=0",
            "external-message-sent rows=0",
            "evidence-received rows=0",
            "message_draft_validation_valid=true",
            "message_draft_rows=4",
            "message_draft_request_rows=4",
            "message_sha_bound_authorization_rows=0",
            "case_rows=2",
            "passed_rows=2",
            "failed_rows=0",
            "real_authorization_input_mutated=false",
            "receipt_rows=0",
            "valid_receipt_rows=0",
            "present_artifact_rows=0",
            "unreceipted_present_artifact_rows=0",
            "receipt_without_artifact_rows=0",
            "receipt_is_reviewed_evidence=false",
            "review_rows=0",
            "valid_review_rows=0",
            "accepted_for_adjudication_rows=0",
            "unreviewed_valid_receipt_rows=0",
            "review_is_adjudication=false",
            "complete_composition_unambiguous=false",
            "cm5_composition_candidate_resolved=false",
            "dsm4_composition_resolved=false",
            "reviewed_source_locator_rows=0",
            "structured_locator_candidate_count=7",
            "foldx_buildmodel_technical_smoke_executed=true",
            "foldx_buildmodel_physical_smoke_executed=false",
            "parameterization_dependency_warning_detected=true",
            "parameterization_warning_command_count=2",
            "unrecognized_atom_rows=110",
            "unrecognized_molecule_names=5CM,5NC,SAH",
            "parameterization_review_completed=false",
            "ddg_value_technical_only=true",
            "energetic_interpretation_approved=false",
            "physical_ddg_comparable=false",
            "safe_for_benchmark_intake=false",
            "extraction_candidate_valid=true",
            "table_s1_primer_rows=38",
            "table_s2_disulfide_bridge_rows=4",
            "dsm4_composition_resolved=false",
            "complete_dsm4_residue_rows=0",
            "wt_absolute_baseline_rows=0",
            "measurement_locator_rows=0",
            "reviewed_source_locator_rows=0",
            "allowlist=6",
            "intake_manifest=4",
            "locator_queue=4",
            "apply_plan=7",
            "file presence",
            "reviewed source locators",
            "SQLite apply approval",
            "does not approve SQLite writes",
            "packet_rows=2",
            "reviewer_packet_valid=true",
            "reviewer_rows=2",
            "needs_more_info_rows=2",
            "candidate_ready_for_human_review_rows=2",
            "composition_candidate_resolved_rows=0",
            "dsm4_unresolved_rows=1",
            "cm5_composition_ambiguous_rows=1",
            "nucleotide_pdb_discrepancy_rows=1",
            "approved_rows=0",
            "formal_review_rows=0",
            "reviewed_extraction_rows=0",
            "reviewer_filled_rows=0",
            "source_locator_rows=0",
            "checklist_valid=true",
            "checklist_rows=12",
            "dsm4_rows=5",
            "cm5_rows=7",
            "cm5_l262v_discrepancy_rows=1",
            "missing_rows=12",
            "needs_more_info_rows=12",
            "evidence_supplied_rows=0",
            "reviewed_rows=0",
            "completed_rows=0",
            "audit_valid=true",
            "read_rows=11",
            "covered_rows=9",
            "not_covered_rows=2",
            "ttg_rows=8",
            "gtg_rows=1",
            "cross_read_consensus_supports_wt_leu262=true",
            "cm5_single_read_outlier=true",
            "discrepancy_resolved=false",
            "sequencing_file_rows=12",
            "seq_read_rows=11",
            "sequence_text_only_rows=11",
            "quality_bearing_artifact_rows=0",
            "chromatogram_artifact_rows=0",
            "per_base_quality_artifact_rows=0",
            "cm5_codon_262_raw_text_call=GTG",
            "cm5_quality_evidence_available=false",
            "sequencing_artifact_hypothesis_confirmed=false",
        ],
        "forbidden_terms": [
            "command_count=44",
            "command_count=78",
            "summary_count=44",
            "bundle_rows=135",
            "command_rows=26",
            "freshness_verified_rows=134",
            "135 files checksummed",
            "command_count=79",
            "summary_count=45",
            "bundle_rows=138",
            "freshness_verified_rows=137",
            "command_count=84",
            "summary_count=49",
            "bundle_rows=151",
            "command_rows=32",
            "freshness_verified_rows=150",
            "command_count=73",
            "command_count=71",
            "command_count=69",
            "command_count=67",
            "command_count=65",
            "command_count=63",
            "summary_count=21",
            "summary_count=40",
            "summary_count=39",
            "summary_count=38",
            "summary_count=37",
            "summary_count=36",
            "bundle_rows=96",
            "bundle_rows=123",
            "bundle_rows=127",
            "bundle_rows=131",
            "bundle_rows=129",
            "bundle_rows=133",
            "bundle_rows=121",
            "bundle_rows=119",
            "bundle_rows=115",
            "bundle_rows=111",
            "bundle_rows=107",
            "command_rows=19",
            "command_rows=20",
            "command_rows=22",
            "artifact_count=1582",
            "artifact_count=1640",
            "command_count=75",
            "summary_count=41",
            "summary_count=42",
            "command_count=77",
            "summary_count=43",
            "smoke artifacts remain missing",
            "5 remaining smoke/provision artifacts missing",
        ],
    },
    {
        "name": "source_acquisition_shortlist",
        "path": AI_ROOT / "reports" / "stage25_source_acquisition_shortlist_20260806.md",
        "required_terms": [
            "Operator shortlist only",
            "file presence",
            "reviewed source locators",
            "SQLite apply approval",
            "Paper ready rows: `0`",
            "Ready for SQLite apply rows: `0`",
            "model claims",
            "release",
        ],
        "forbidden_terms": [],
    },
    {
        "name": "execute_closeout_reviewer_packet",
        "path": AI_ROOT / "reports" / "stage25_execute_closeout_reviewer_packet_20260806.md",
        "required_terms": [
            "allow_apply=false",
            "external_sqlite_mutated=false",
            "export_safe_released=false",
            "release_ready=false",
            "safe_for_model_claim=false",
            "formal_decision_rows_written=0",
            "Do not write SQLite",
            "needs_more_info",
            "fulltext/source-table evidence",
        ],
        "forbidden_terms": [],
    },
]


def load_module(path: Path, module_name: str):
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load module from {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main() -> int:
    failures = []
    doc_results = []
    def require_equal(check: str, observed: object, expected: object) -> None:
        if observed != expected:
            failures.append({"check": check, "observed": observed, "expected": expected})

    backlog = json.loads(HUMAN_BACKLOG_VALIDATION.read_text(encoding="utf-8")) if HUMAN_BACKLOG_VALIDATION.exists() else {}
    if backlog.get("success") is not True:
        failures.append({"check": "human_backlog_validation_success", "observed": backlog.get("success"), "expected": True})
    backlog_open_items = backlog.get("open_items")
    backlog_missing_rows = backlog.get("total_missing_rows")
    dynamic_backlog_terms = [
        f"human_backlog_open_items={backlog_open_items}",
        f"human_backlog_missing_rows={backlog_missing_rows}",
    ]
    activity_import = json.loads(ACTIVITY_RISK_IMPORT_VALIDATION.read_text(encoding="utf-8")) if ACTIVITY_RISK_IMPORT_VALIDATION.exists() else {}
    five_head_gap = json.loads(FIVE_HEAD_GAP_REPORT.read_text(encoding="utf-8")) if FIVE_HEAD_GAP_REPORT.exists() else {}
    five_head_execution = json.loads(FIVE_HEAD_EXECUTION_REPORT.read_text(encoding="utf-8")) if FIVE_HEAD_EXECUTION_REPORT.exists() else {}
    model_guard = json.loads(MODEL_ARTIFACT_GUARD_VALIDATION.read_text(encoding="utf-8")) if MODEL_ARTIFACT_GUARD_VALIDATION.exists() else {}

    import_rows = activity_import.get("training_import_written_rows")
    require_equal("activity_risk_import_validation_success", activity_import.get("success"), True)
    require_equal("activity_risk_import_row_parity", activity_import.get("training_import_label_rows"), import_rows)
    require_equal("activity_risk_training_execution_false", activity_import.get("training_execution_allowed"), False)
    require_equal("activity_risk_safe_for_model_claim_false", activity_import.get("safe_for_model_claim"), False)
    require_equal("activity_risk_release_ready_false", activity_import.get("release_ready"), False)
    require_equal("five_head_current_labels_match_import", five_head_gap.get("current_label_rows"), import_rows)
    require_equal("five_head_gap_status_blocked", five_head_gap.get("status"), "blocked")
    require_equal("five_head_execution_success", five_head_execution.get("success"), True)
    require_equal("five_head_total_rows_match_import", five_head_execution.get("total_head_training_rows"), import_rows)
    require_equal("five_head_ready_head_count_zero", five_head_execution.get("ready_head_count"), 0)
    require_equal("five_head_training_execution_false", five_head_execution.get("training_execution_allowed"), False)
    require_equal("five_head_safe_for_model_claim_false", five_head_execution.get("safe_for_model_claim"), False)
    require_equal("five_head_release_ready_false", five_head_execution.get("release_ready"), False)
    require_equal("model_artifact_guard_success", model_guard.get("success"), True)
    require_equal("claimable_model_artifact_count_zero", model_guard.get("claimable_model_artifact_count"), 0)
    require_equal("production_model_artifact_count_zero", model_guard.get("production_model_artifact_count"), 0)
    require_equal("model_artifact_safe_for_model_claim_false", model_guard.get("safe_for_model_claim"), False)
    require_equal("model_artifact_release_ready_false", model_guard.get("release_ready"), False)
    dynamic_training_terms = [
        f"activity_risk_training_import_written_rows={import_rows}",
        f"five_head_current_label_rows={five_head_gap.get('current_label_rows')}",
        f"five_head_missing_label_rows_total={five_head_gap.get('missing_label_rows_total')}",
        f"five_head_ready_head_count={five_head_execution.get('ready_head_count')}",
        f"five_head_training_execution_allowed={str(five_head_execution.get('training_execution_allowed')).lower()}",
        f"claimable_model_artifact_count={model_guard.get('claimable_model_artifact_count')}",
        f"production_model_artifact_count={model_guard.get('production_model_artifact_count')}",
    ]
    runner_contract = load_module(STAGE25_RUNNER_SCRIPT, "stage25_runner_contract_for_docs")
    overall_contract = load_module(STAGE25_OVERALL_BUILDER, "stage25_overall_contract_for_docs")
    handoff_contract = load_module(STAGE25_HANDOFF_BUILDER, "stage25_handoff_contract_for_docs")
    runner_command_count = len(getattr(runner_contract, "COMMANDS", []))
    summary_count = len(getattr(overall_contract, "INPUTS", {}))
    handoff_rows = handoff_contract.collect_rows()
    handoff_bundle_rows = len(handoff_rows)
    handoff_unique_rows = len({row.get("path") for row in handoff_rows})
    handoff_missing_rows = sum(row.get("exists") is not True for row in handoff_rows)
    handoff_freshness_verified_rows = sum(row.get("freshness_check_mode") == "current_filesystem" for row in handoff_rows)
    handoff_freshness_exempt_rows = handoff_bundle_rows - handoff_freshness_verified_rows
    local_release = json.loads(LOCAL_RELEASE_MANIFEST.read_text(encoding="utf-8")) if LOCAL_RELEASE_MANIFEST.exists() else {}
    if runner_command_count <= 0:
        failures.append({"check": "stage25_runner_command_count_positive", "observed": runner_command_count, "expected": ">0"})
    if summary_count <= 0:
        failures.append({"check": "stage25_overall_summary_contract_positive", "observed": summary_count, "expected": ">0"})
    require_equal("stage25_handoff_unique_rows", handoff_unique_rows, handoff_bundle_rows)
    require_equal("stage25_handoff_missing_rows_zero", handoff_missing_rows, 0)
    require_equal("stage25_handoff_single_freshness_exemption", handoff_freshness_exempt_rows, 1)
    require_equal("local_release_ready_false", local_release.get("release_ready"), False)
    dynamic_stage25_terms = [
        f"command_count={runner_command_count}",
        f"summary_count={summary_count}",
        f"bundle_rows={handoff_bundle_rows}",
        f"freshness_verified_rows={handoff_freshness_verified_rows}",
        f"freshness_exempt_rows={handoff_freshness_exempt_rows}",
        f"artifact_count={local_release.get('artifact_count')}",
    ]
    post_source_receipt = json.loads(POST_SOURCE_RECEIPT_VALIDATION.read_text(encoding="utf-8")) if POST_SOURCE_RECEIPT_VALIDATION.exists() else {}
    post_source_dry_run = json.loads(POST_SOURCE_DRY_RUN_VALIDATION.read_text(encoding="utf-8")) if POST_SOURCE_DRY_RUN_VALIDATION.exists() else {}
    post_source_rows = post_source_receipt.get("command_rows")
    post_source_sha = post_source_receipt.get("command_contract_sha256")
    require_equal("post_source_receipt_valid", post_source_receipt.get("receipt_valid"), True)
    require_equal("post_source_receipt_failure_count_zero", post_source_receipt.get("failure_count"), 0)
    require_equal("post_source_command_contract_valid", post_source_receipt.get("command_contract_valid"), True)
    require_equal("post_source_unique_command_count_parity", post_source_receipt.get("unique_command_name_rows"), post_source_rows)
    require_equal("post_source_sqlite_write_rows_zero", post_source_receipt.get("sqlite_write_command_rows"), 0)
    require_equal("post_source_commands_executed_false", post_source_receipt.get("commands_executed"), False)
    require_equal("post_source_dry_run_valid", post_source_dry_run.get("audit_valid"), True)
    require_equal("post_source_dry_run_failure_count_zero", post_source_dry_run.get("failure_count"), 0)
    require_equal("post_source_dry_run_command_rows_parity", post_source_dry_run.get("command_rows"), post_source_rows)
    require_equal("post_source_dry_run_sha_parity", post_source_dry_run.get("command_contract_sha256"), post_source_sha)
    require_equal("post_source_dry_run_sqlite_rows_zero", post_source_dry_run.get("sqlite_write_command_rows"), 0)
    require_equal("post_source_dry_run_commands_executed_false", post_source_dry_run.get("commands_executed"), False)
    if not isinstance(post_source_sha, str) or len(post_source_sha) != 64:
        failures.append({"check": "post_source_contract_sha256_shape", "observed": post_source_sha, "expected": "64-char sha256"})
    dynamic_post_source_terms = [
        f"post_source_command_rows={post_source_rows}",
        f"post_source_command_contract_sha256={post_source_sha}",
        f"post_source_sqlite_write_command_rows={post_source_receipt.get('sqlite_write_command_rows')}",
        f"post_source_commands_executed={str(post_source_receipt.get('commands_executed')).lower()}",
    ]
    for doc in DOCS:
        path = doc["path"]
        result = {"name": doc["name"], "path": str(path), "exists": path.exists(), "missing_terms": [], "forbidden_terms_present": []}
        if not path.exists():
            failures.append({"check": "markdown_doc_exists", "path": str(path), "observed": "missing", "expected": "present"})
            doc_results.append(result)
            continue
        text = path.read_text(encoding="utf-8")
        required_terms = [*doc["required_terms"]]
        forbidden_terms = [*doc.get("forbidden_terms", [])]
        if doc["name"] in {"next_operator_packet", "daily_report"}:
            required_terms.extend(dynamic_backlog_terms)
            required_terms.extend(dynamic_training_terms)
            required_terms.extend(dynamic_stage25_terms)
            required_terms.extend(dynamic_post_source_terms)
            forbidden_terms.extend(["1188 missing rows", "human_backlog_missing_rows=1188"])
        missing_terms = [term for term in required_terms if term not in text]
        forbidden_terms_present = [term for term in forbidden_terms if term in text]
        result["missing_terms"] = missing_terms
        result["forbidden_terms_present"] = forbidden_terms_present
        if missing_terms:
            failures.append({"check": "markdown_doc_required_terms", "path": str(path), "missing_terms": missing_terms})
        if forbidden_terms_present:
            failures.append({"check": "markdown_doc_forbidden_terms_absent", "path": str(path), "forbidden_terms_present": forbidden_terms_present})
        doc_results.append(result)

    report = {
        "schema_version": 1,
        "created_at": "2026-08-06",
        "mode": "read_only_stage25_markdown_operator_docs_validation",
        "stage": 25,
        "docs_valid": not failures,
        "failure_count": len(failures),
        "failures": failures,
        "docs": doc_results,
        "human_backlog_validation_success": backlog.get("success") is True,
        "human_backlog_open_items": backlog_open_items,
        "human_backlog_missing_rows": backlog_missing_rows,
        "activity_risk_training_import_written_rows": import_rows,
        "five_head_current_label_rows": five_head_gap.get("current_label_rows"),
        "five_head_missing_label_rows_total": five_head_gap.get("missing_label_rows_total"),
        "five_head_ready_head_count": five_head_execution.get("ready_head_count"),
        "five_head_training_execution_allowed": five_head_execution.get("training_execution_allowed"),
        "claimable_model_artifact_count": model_guard.get("claimable_model_artifact_count"),
        "production_model_artifact_count": model_guard.get("production_model_artifact_count"),
        "runner_command_count": runner_command_count,
        "overall_summary_count": summary_count,
        "handoff_bundle_rows": handoff_bundle_rows,
        "handoff_freshness_verified_rows": handoff_freshness_verified_rows,
        "handoff_freshness_exempt_rows": handoff_freshness_exempt_rows,
        "local_release_artifact_count": local_release.get("artifact_count"),
        "post_source_command_rows": post_source_rows,
        "post_source_command_contract_sha256": post_source_sha,
        "post_source_sqlite_write_command_rows": post_source_receipt.get("sqlite_write_command_rows"),
        "post_source_commands_executed": post_source_receipt.get("commands_executed"),
        "allow_apply": False,
        "external_sqlite_mutated": False,
        "export_safe_released": False,
        "release_ready": False,
        "safe_for_model_claim": False,
        "benchmark_ready_for_model_claim": False,
        "release_status": "not_released",
    }
    OUTPUT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(OUTPUT), "docs_valid": report["docs_valid"], "failure_count": report["failure_count"]}, ensure_ascii=False, sort_keys=True))
    return 0 if report["docs_valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
