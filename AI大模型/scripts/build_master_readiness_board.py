#!/usr/bin/env python3
"""Build a master readiness board across all pending KWB model workstreams."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
OUT = AI_ROOT / "reports" / "master_readiness_board.json"


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def exists(path: str) -> bool:
    return (AI_ROOT / path).exists()


def unique_strings(values: list[Any]) -> list[str]:
    seen = set()
    output = []
    for value in values:
        if not value:
            continue
        text = str(value)
        if text in seen:
            continue
        seen.add(text)
        output.append(text)
    return output


def main() -> int:
    parser = argparse.ArgumentParser(description="Build master readiness board")
    parser.add_argument("--output", type=Path, default=OUT)
    args = parser.parse_args()

    readiness = load_json(AI_ROOT / "reports" / "training_readiness_report.json")
    curation = load_json(AI_ROOT / "reports" / "curation_dashboard.json")
    structure = load_json(AI_ROOT / "reports" / "structure_cache_audit_report.json")
    safe_entry = load_json(AI_ROOT / "reports" / "safe_training_entrypoint_check.json")
    data_quality = load_json(AI_ROOT / "reports" / "data_quality_report.json")
    domain_repair = load_json(AI_ROOT / "reports" / "domain_interval_repair_report.json")
    domain_interpro = load_json(AI_ROOT / "reports" / "domain_interpro_evidence_report.json")
    domain_interpro_decisions = load_json(AI_ROOT / "reports" / "domain_interval_interpro_decision_report.json")
    domain_interpro_packets = load_json(AI_ROOT / "reports" / "domain_interpro_review_packet_report.json")
    domain_multi_occurrence = load_json(AI_ROOT / "reports" / "domain_multi_occurrence_feature_report.json")
    domain_apply = load_json(AI_ROOT / "reports" / "domain_interval_apply_report.json")
    domain_status = load_json(AI_ROOT / "reports" / "domain_interval_batch_status_report.json")
    domain_validation = load_json(AI_ROOT / "reports" / "domain_interval_decision_validation_report.json")
    msa = load_json(AI_ROOT / "reports" / "msa_conservation_readiness_report.json")
    feedback = load_json(AI_ROOT / "reports" / "experiment_feedback_readiness_report.json")
    workflow_gate = load_json(AI_ROOT / "reports" / "structure_workflow_gate_demo.json")
    local_adapter = load_json(AI_ROOT / "reports" / "local_tool_adapter_demo.json")
    numbering_packets = load_json(AI_ROOT / "reports" / "numbering_retrieval_packet_report.json")
    numbering_uniprot = load_json(AI_ROOT / "reports" / "numbering_uniprot_evidence_report.json")
    numbering_isoform = load_json(AI_ROOT / "reports" / "numbering_isoform_evidence_report.json")
    numbering_isoform_candidates = load_json(AI_ROOT / "reports" / "numbering_isoform_review_candidate_report.json")
    numbering_pubmed = load_json(AI_ROOT / "reports" / "numbering_pubmed_evidence_report.json")
    numbering_pubmed_abstract = load_json(AI_ROOT / "reports" / "numbering_pubmed_abstract_evidence_report.json")
    numbering_review_worklist = load_json(AI_ROOT / "reports" / "numbering_review_worklist_report.json")
    numbering_review_packets = load_json(AI_ROOT / "reports" / "numbering_review_packet_report.json")
    numbering_literature_risk = load_json(AI_ROOT / "reports" / "numbering_literature_review_risk_report.json")
    structure_acquisition = load_json(AI_ROOT / "reports" / "structure_acquisition_readiness_report.json")
    structure_chain_worklist = load_json(AI_ROOT / "reports" / "structure_chain_mapping_worklist_report.json")
    structure_chain_autoreview = load_json(AI_ROOT / "reports" / "structure_chain_autoreview_candidate_report.json")
    structure_chain_autoreview_drafts = load_json(AI_ROOT / "reports" / "structure_chain_autoreview_decision_draft_report.json")
    structure_chain_packets = load_json(AI_ROOT / "reports" / "structure_chain_review_packet_report.json")
    structure_chain_validation = load_json(AI_ROOT / "reports" / "structure_chain_mapping_decision_validation_report.json")
    structure_chain_apply = load_json(AI_ROOT / "reports" / "structure_chain_mapping_apply_report.json")
    msa_inputs = load_json(AI_ROOT / "reports" / "msa_executor_readiness_report.json")
    msa_cache_validation = load_json(AI_ROOT / "reports" / "msa_conservation_cache_validation_report.json")
    msa_runtime = load_json(AI_ROOT / "reports" / "msa_runtime_readiness_report.json")
    msa_execution_plan = load_json(AI_ROOT / "reports" / "msa_execution_plan_report.json")
    msa_runtime_commands = load_json(AI_ROOT / "reports" / "msa_runtime_command_report.json")
    foreign_tools = load_json(AI_ROOT / "reports" / "foreign_tool_readiness_report.json")
    feedback_validation = load_json(AI_ROOT / "reports" / "experiment_feedback_intake_validation_report.json")
    feedback_sources = load_json(AI_ROOT / "reports" / "experiment_feedback_source_discovery_report.json")
    feedback_source_packets = load_json(AI_ROOT / "reports" / "experiment_feedback_source_review_packet_report.json")
    feedback_plate_packets = load_json(AI_ROOT / "reports" / "experiment_feedback_plate_review_packet_report.json")
    feedback_plate_validation = load_json(AI_ROOT / "reports" / "experiment_feedback_plate_intake_validation_report.json")
    multitask = load_json(AI_ROOT / "reports" / "multitask_training_readiness_report.json")
    benchmark_matrix = load_json(AI_ROOT / "reports" / "benchmark_matrix_report.json")
    benchmark_plan = load_json(AI_ROOT / "reports" / "benchmark_acquisition_plan_report.json")
    head_card_status = load_json(AI_ROOT / "reports" / "head_model_card_status_report.json")
    sequence_ip = load_json(AI_ROOT / "reports" / "sequence_ip_review_packet_report.json")
    sequence_ip_decisions = load_json(AI_ROOT / "reports" / "sequence_ip_fto_decision_validation_report.json")
    biosecurity = load_json(AI_ROOT / "reports" / "biosecurity_readiness_report.json")
    biosecurity_drafts = load_json(AI_ROOT / "reports" / "biosecurity_screening_draft_report.json")
    biosecurity_decisions = load_json(AI_ROOT / "reports" / "biosecurity_screening_decision_validation_report.json")
    governance = load_json(AI_ROOT / "reports" / "governance_readiness_report.json")
    customer_delivery = load_json(AI_ROOT / "reports" / "customer_delivery_readiness_report.json")
    local_release = load_json(AI_ROOT / "reports" / "local_release_manifest.json")
    local_release_summary = local_release.get("readiness_summary") or {}
    active_learning = load_json(AI_ROOT / "reports" / "active_learning_trial_readiness_report.json")
    parallel_execution = load_json(AI_ROOT / "reports" / "parallel_execution_board.json")
    external_data_validation = load_json(AI_ROOT / "reports" / "external_data_source_registry_validation_report.json")
    acceptance_gates = load_json(AI_ROOT / "reports" / "workstream_acceptance_gates.json")
    license_packets = load_json(AI_ROOT / "reports" / "external_license_review_packet_report.json")
    license_decisions = load_json(AI_ROOT / "reports" / "external_license_review_decision_validation_report.json")
    operator_queue = load_json(AI_ROOT / "reports" / "operator_review_action_queue_report.json")
    operator_action_validation = load_json(AI_ROOT / "reports" / "operator_review_action_decision_validation_report.json")
    operator_status = load_json(AI_ROOT / "reports" / "operator_review_status_report.json")
    workstream_acceptance_decisions = load_json(AI_ROOT / "reports" / "workstream_acceptance_decision_validation_report.json")
    label_provenance = load_json(AI_ROOT / "reports" / "label_provenance_audit_report.json")

    strict_rows = readiness.get("label_integrity", {}).get("strict_supervised_rows") or 0
    coordinate_ready = bool(structure.get("coordinate_features_ready"))
    structure_scope = readiness.get("structure_cache", {}).get("coordinate_features_scope")
    domain = readiness.get("label_integrity", {}).get("domain_architecture", {})
    msa_feature_state = readiness.get("feature_streams", {}).get("msa_conservation", {})
    feedback_rows = readiness.get("rows", {}).get("feedback_features") or 0
    invalid_domain_rows = domain_repair.get("invalid_rows") or 0
    curated_domain_rows = domain_apply.get("output_rows") or 0
    usable_domain_rows = domain_apply.get("usable_for_position_features") or 0
    domain_decision_coverage = domain_status.get("coverage") or 0
    domain_consistency = load_json(AI_ROOT / "reports" / "domain_state_consistency_20260829.json")
    domain_ready = bool(
        domain_consistency.get("consistency", {}).get("ok") is True
        and ((domain_consistency.get("totals", {}).get("single_interval_usable") or 0)
             + (domain_consistency.get("totals", {}).get("multi_occurrence_usable") or 0)) > 0
    )
    structure_missing = structure_acquisition.get("missing") or 0
    structure_present = structure_acquisition.get("present") or 0
    structure_blockers = []
    if not coordinate_ready:
        structure_blockers.append("local PDB/mmCIF/AlphaFold files are missing")
    if structure_missing:
        structure_blockers.append(f"structure cache is partial: {structure_present}/{structure_acquisition.get('entries')} entries present")
    if coordinate_ready:
        structure_blockers.append("chain mapping and sequence-to-structure numbering still require review before model-quality claims")
    usable_chain_mappings = structure_chain_apply.get("usable_for_coordinate_features") or 0
    if coordinate_ready and usable_chain_mappings == 0:
        structure_blockers.append("reviewed chain mapping decisions are 0; coordinate features remain file-level only")

    streams = [
        {
            "stream": "numbering_curation",
            "status": "in_progress",
            "ready": strict_rows >= 100,
            "current": {
                "strict_supervised_rows": strict_rows,
                "claim_eligible_supervised_rows": label_provenance.get("claim_eligible_rows"),
                "synthetic_or_unreceipted_rows": label_provenance.get("synthetic_or_unreceipted_rows"),
                "label_provenance_hard_gate_status": label_provenance.get("hard_gate_status"),
                "decision_coverage": curation.get("batching", {}).get("decision_coverage"),
                "covered_batch_rows": curation.get("batching", {}).get("covered_rows"),
                "retrieval_packets": numbering_packets.get("packets"),
                "retrieval_packet_rows": numbering_packets.get("queue_rows"),
                "retrieval_not_fetched_rows": numbering_packets.get("not_fetched_rows"),
                "public_uniprot_evidence_rows": numbering_uniprot.get("evidence_rows"),
                "public_uniprot_accessions": numbering_uniprot.get("unique_accessions_fetched_or_cached"),
                "reported_wt_matches_current_uniprot": numbering_uniprot.get("reported_wt_matches_current_uniprot"),
                "rows_with_isoform_options": numbering_uniprot.get("rows_with_isoform_options"),
                "isoform_evidence_rows": numbering_isoform.get("rows_with_isoforms_in_scope"),
                "isoform_exact_position_matches": numbering_isoform.get("rows_with_exact_isoform_position_match"),
                "isoform_review_candidate_rows": numbering_isoform_candidates.get("candidate_rows"),
                "pubmed_unique_found": numbering_pubmed.get("unique_pmids_found"),
                "pubmed_high_review_risk_rows": numbering_pubmed.get("rows_high_review_risk"),
                "pubmed_abstract_rows_with_signal": numbering_pubmed_abstract.get("rows_with_abstract_signal"),
                "pubmed_abstract_mutation_mentions": numbering_pubmed_abstract.get("rows_with_reported_mutation_mention"),
                "review_worklist_rows": numbering_review_worklist.get("worklist_rows"),
                "review_worklist_bucket_counts": numbering_review_worklist.get("bucket_counts"),
                "review_packet_rows": numbering_review_packets.get("packet_rows"),
                "review_packet_reports": numbering_review_packets.get("packet_reports"),
                "literature_high_risk_rows": numbering_literature_risk.get("high_risk_rows"),
                "literature_possible_relevance_rows": numbering_literature_risk.get("possible_relevance_rows"),
            },
            "blockers": [
                "need reviewed numbering decisions to reach >=100 strict supervised rows",
                "need non-synthetic source receipts so claim-eligible supervised rows reach >=100",
            ],
            "next_commands": [
                "review datasets/curation/numbering_uniprot_evidence.jsonl",
                "edit datasets/curation/numbering_curation_decisions.jsonl",
                "python3 scripts/run_safe_training_pipeline.py",
            ],
        },
        {
            "stream": "structure_cache",
            "status": "partial_ready" if coordinate_ready else "blocked",
            "ready": bool(coordinate_ready and structure_scope == "full_cache" and not structure_missing and usable_chain_mappings > 0),
            "current": {
                "coordinate_features_ready": coordinate_ready,
                "pdb_sample_existing": structure.get("pdb_sample_existing"),
                "alphafold_sample_existing": structure.get("alphafold_sample_existing"),
                "acquisition_entries": structure_acquisition.get("entries"),
                "acquisition_missing": structure_acquisition.get("missing"),
                "acquisition_cache_root": structure_acquisition.get("cache_root"),
                "chain_mapping_worklist_rows": structure_chain_worklist.get("worklist_rows"),
                "chain_mapping_bucket_counts": structure_chain_worklist.get("bucket_counts"),
                "chain_autoreview_candidate_rows": structure_chain_autoreview.get("candidate_rows"),
                "chain_autoreview_bucket_counts": structure_chain_autoreview.get("bucket_counts"),
                "chain_autoreview_exact_candidates": structure_chain_autoreview.get("exact_sequence_match_candidates"),
                "chain_autoreview_construct_candidates": structure_chain_autoreview.get("construct_or_mutant_candidates"),
                "chain_autoreview_draft_rows": structure_chain_autoreview_drafts.get("draft_rows"),
                "chain_autoreview_accepted_rows": structure_chain_autoreview_drafts.get("accepted_rows"),
                "single_chain_close_candidates": structure_chain_worklist.get("single_chain_close_candidates"),
                "multi_chain_needs_selection": structure_chain_worklist.get("multi_chain_needs_selection"),
                "chain_review_packet_rows": structure_chain_packets.get("packet_rows"),
                "chain_review_packet_reports": structure_chain_packets.get("packet_reports"),
                "chain_mapping_decision_rows": structure_chain_validation.get("decision_rows"),
                "valid_chain_mapping_decision_rows": structure_chain_validation.get("valid_rows"),
                "invalid_chain_mapping_decision_rows": structure_chain_validation.get("invalid_rows"),
                "reviewed_chain_mapping_rows": structure_chain_apply.get("reviewed_chain_mapping_rows"),
                "usable_for_coordinate_features": usable_chain_mappings,
            },
            "blockers": structure_blockers,
            "next_commands": [
                "review datasets/curation/structure_chain_review_packets/*.md",
                "append reviewed rows to datasets/curation/structure_chain_mapping_decisions.jsonl",
                "python3 scripts/run_safe_training_pipeline.py",
            ],
        },
        {
            "stream": "domain_intervals",
            "status": "partial_ready" if domain_ready and (domain_consistency.get("totals", {}).get("unresolved") or 0) else ("ready" if domain_ready else ("in_progress" if curated_domain_rows else "blocked")),
            "ready": bool(domain_ready and not (domain_consistency.get("totals", {}).get("unresolved") or 0)),
            "current": {
                **domain,
                "queued_rows": domain_repair.get("queued_rows"),
                "invalid_rows": domain_repair.get("invalid_rows"),
                "decision_rows": domain_status.get("decided_rows"),
                "decision_coverage": domain_decision_coverage,
                "curated_rows": curated_domain_rows,
                "usable_for_position_features": usable_domain_rows,
                "invalid_decision_rows": domain_validation.get("invalid_rows"),
                "interpro_evidence_rows": domain_interpro.get("output_rows"),
                "interpro_exact_pfam_interval_rows": domain_interpro.get("rows_with_exact_pfam_interval"),
                "interpro_generated_decisions": domain_interpro_decisions.get("generated_decisions"),
                "interpro_program_reviewed_decisions": domain_interpro_decisions.get("interpro_program_reviewed_decisions"),
                "interpro_merged_decision_rows": domain_interpro_decisions.get("merged_decision_rows"),
                "interpro_raw_unresolved_rows": domain_interpro_packets.get("raw_unresolved_rows"),
                "interpro_unresolved_rows": domain_interpro_packets.get("unresolved_rows"),
                "consistency_snapshot": domain_consistency,
                "interpro_review_packet_rows": domain_interpro_packets.get("packet_rows"),
                "interpro_unresolved_bucket_counts": domain_interpro_packets.get("unresolved_bucket_counts"),
                "multi_occurrence_feature_rows": domain_multi_occurrence.get("feature_rows"),
                "multi_occurrence_invalid_rows": domain_multi_occurrence.get("invalid_rows"),
                "multi_occurrence_ready_for_feature_use": domain_multi_occurrence.get("ready_for_feature_use"),
            },
            "blockers": (
                []
                if domain_ready
                else [f"domain interval curation incomplete: {usable_domain_rows}/{invalid_domain_rows} invalid rows have usable intervals"]
            ),
            "next_commands": [
                "edit datasets/curation/domain_interval_decisions.jsonl with reviewed intervals",
                "python3 scripts/run_safe_training_pipeline.py",
                "python3 scripts/enrich_supervised_mutation_features.py",
            ],
        },
        {
            "stream": "msa_conservation",
            "status": "ready" if msa_feature_state.get("ready") else ("runtime_ready" if msa_runtime.get("runtime_ready") else "scaffolded"),
            "ready": bool(msa_feature_state.get("ready")),
            "current": {
                **msa_feature_state,
                "manifest_exists": exists("reports/msa_conservation_manifest.json"),
                "fasta_ready": msa_inputs.get("fasta_ready"),
                "executor_status": msa_inputs.get("executor_status"),
                "available_executors": msa_inputs.get("available_executors"),
                "planned_jobs": msa_execution_plan.get("planned_jobs"),
                "ready_jobs": msa_execution_plan.get("ready_jobs"),
                "blocked_jobs": msa_execution_plan.get("blocked_jobs"),
                "cache_validation_ready": msa_cache_validation.get("ready"),
                "cache_validation_valid_rows": msa_cache_validation.get("valid_rows"),
                "cache_validation_invalid_rows": msa_cache_validation.get("invalid_rows"),
                "cache_validation_manifest_errors": msa_cache_validation.get("manifest_errors"),
                "runtime_ready": msa_runtime.get("runtime_ready"),
                "selected_runtime": msa_runtime.get("selected_runtime"),
                "runtime_blockers": msa_runtime.get("blockers"),
                "docker_daemon_ready": (msa_runtime.get("docker_image") or {}).get("docker_daemon_ready"),
                "trusted_cache_ready": (msa_runtime.get("trusted_cache") or {}).get("ready"),
                "runtime_command_rows": msa_runtime_commands.get("command_rows"),
                "ready_runtime_commands": msa_runtime_commands.get("ready_commands"),
                "blocked_runtime_commands": msa_runtime_commands.get("blocked_commands"),
                "homolog_database_ready": msa_runtime_commands.get("homolog_database_ready"),
                "foreign_tool_status_counts": foreign_tools.get("status_counts"),
                "foreign_tools_ready_for_local_evaluation": foreign_tools.get("ready_for_local_evaluation"),
            },
            "blockers": unique_strings([
                *([] if msa_feature_state.get("ready") else ["MSA conservation feature cache is not validated"]),
                *(msa_cache_validation.get("manifest_errors") or []),
                *(msa_runtime.get("blockers") or []),
                *(msa_runtime_commands.get("blockers") or []),
            ]),
            "next_commands": [
                "install/configure MMseqs2 or trusted MSA cache",
                "rerun python3 scripts/build_msa_input_fastas.py",
                "rerun python3 scripts/run_safe_training_pipeline.py",
            ],
        },
        {
            "stream": "kwb_experiment_feedback",
            "status": "scaffolded" if feedback.get("local_rows") == 0 else ("blocked" if feedback_rows <= 1 else "in_progress"),
            "ready": bool(feedback.get("ready_for_training")),
            "current": {
                "feedback_feature_rows": feedback_rows,
                "local_feedback_rows": feedback.get("local_rows"),
                "reviewed_numbered_rows": feedback.get("reviewed_numbered_rows"),
                "validated_rows": feedback_validation.get("input_rows"),
                "training_eligible_rows": feedback_validation.get("training_eligible_rows"),
                "candidate_source_files": feedback_sources.get("candidate_rows"),
                "top_candidate_sources": feedback_sources.get("top_candidates", [])[:5],
                "source_review_packets": feedback_source_packets.get("packets"),
                "source_review_packet_rows": feedback_source_packets.get("packet_rows"),
                "source_review_bucket_counts": feedback_source_packets.get("bucket_counts"),
                "plate_review_packet_rows": feedback_plate_packets.get("plate_review_packet_rows"),
                "plate_feedback_draft_rows": feedback_plate_packets.get("plate_feedback_draft_rows"),
                "approved_for_plate_intake_rows": feedback_plate_packets.get("approved_for_plate_intake_rows"),
                "plate_intake_rows": feedback_plate_validation.get("input_rows"),
                "plate_training_eligible_rows": feedback_plate_validation.get("training_eligible_rows"),
            },
            "blockers": ["real experiment feedback table not connected locally"],
            "next_commands": [
                "review datasets/feedback/source_review_packets/*.md",
                "write only genuine numbered wet-lab rows to datasets/feedback/experiment_feedback.local.jsonl",
                "python3 scripts/validate_experiment_feedback_intake.py",
            ],
        },
        {
            "stream": "model_training",
            "status": "blocked",
            "ready": bool(readiness.get("ready_for_supervised_small_model_claim")),
            "current": {
                "safe_for_training_pipeline": safe_entry.get("safe_for_training_pipeline"),
                "safe_for_model_claim": safe_entry.get("safe_for_model_claim"),
                "quality_score": readiness.get("quality_score"),
                "multitask_status": multitask.get("status"),
                "multitask_missing_heads": multitask.get("missing_head_labels"),
                "active_learning_ready": active_learning.get("ready"),
                "active_learning_draft_rows": active_learning.get("draft_rows"),
                "active_learning_experiment_submission_allowed": active_learning.get("experiment_submission_allowed"),
                "head_model_card_status_heads": head_card_status.get("heads"),
                "head_model_card_ready_heads": head_card_status.get("ready_heads"),
                "benchmark_acquisition_plan_rows": benchmark_plan.get("plan_rows"),
                "benchmark_scorecards_ready": benchmark_plan.get("scorecards_ready"),
            },
            "blockers": unique_strings([
                *(readiness.get("blockers") or []),
                *(active_learning.get("blockers") or []),
            ]),
            "next_commands": [
                "python3 scripts/run_safe_training_pipeline.py",
                "train GBDT/neural heads only after strict rows >=100 and feature cache ready",
            ],
        },
        {
            "stream": "governance_release",
            "status": "blocked",
            "ready": bool(governance.get("ready") and customer_delivery.get("ready") and local_release.get("release_ready")),
            "current": {
                "governance_ready": governance.get("ready"),
                "governance_blockers": governance.get("blockers"),
                "benchmark_ready_for_model_claim": benchmark_matrix.get("ready_for_model_claim"),
                "sequence_ip_packet_rows": sequence_ip.get("packet_rows"),
                "sequence_ip_fto_decision_rows": sequence_ip_decisions.get("decision_rows"),
                "sequence_ip_fto_valid_decision_rows": sequence_ip_decisions.get("valid_rows"),
                "reviewed_fto_rows": sequence_ip_decisions.get("approved_for_customer_delivery_rows"),
                "sequence_ip_fto_ready_for_delivery": sequence_ip_decisions.get("ready_for_customer_delivery"),
                "biosecurity_ready_for_ordering": biosecurity.get("ready_for_ordering"),
                "order_ready_outputs_detected": biosecurity.get("order_ready_outputs_detected"),
                "biosecurity_screening_draft_rows": biosecurity_drafts.get("draft_rows"),
                "biosecurity_decision_rows": biosecurity_decisions.get("decision_rows"),
                "biosecurity_valid_decision_rows": biosecurity_decisions.get("valid_rows"),
                "biosecurity_approved_for_ordering_rows": biosecurity_decisions.get("approved_for_ordering_rows"),
                "biosecurity_decision_ready_for_ordering": biosecurity_decisions.get("ready_for_ordering"),
                "customer_delivery_ready": customer_delivery.get("ready"),
                "customer_delivery_blockers": customer_delivery.get("blockers"),
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
                "blocked_capabilities": local_release.get("blocked_capabilities"),
                "parallel_execution_status": parallel_execution.get("status"),
                "parallel_execution_workstreams": len(parallel_execution.get("workstreams", [])),
                "external_data_registry_ready": external_data_validation.get("ready"),
                "external_data_ready_sources": external_data_validation.get("ready_sources"),
                "license_review_packet_rows": license_packets.get("packet_rows"),
                "license_review_decision_rows": license_decisions.get("decision_rows"),
                "license_review_valid_decision_rows": license_decisions.get("valid_rows"),
                "license_review_training_approved_rows": license_decisions.get("approved_for_training_rows"),
                "license_review_local_eval_approved_rows": license_decisions.get("approved_for_local_evaluation_rows"),
                "license_review_delivery_approved_rows": license_decisions.get("approved_for_customer_delivery_rows"),
                "license_review_ready_for_delivery": license_decisions.get("ready_for_customer_delivery"),
                "operator_review_action_rows": operator_queue.get("action_rows"),
                "operator_review_decision_rows": operator_action_validation.get("decision_rows"),
                "operator_review_valid_decision_rows": operator_action_validation.get("valid_rows"),
                "operator_review_completed_rows": operator_action_validation.get("completed_rows"),
                "operator_review_all_actions_completed": operator_action_validation.get("all_actions_completed"),
                "operator_review_status_ready": operator_status.get("ready"),
                "operator_review_status_blockers": operator_status.get("blockers"),
                "accepted_workstreams": acceptance_gates.get("accepted_streams"),
                "total_acceptance_gates": acceptance_gates.get("total_streams"),
                "workstream_acceptance_decision_rows": workstream_acceptance_decisions.get("decision_rows"),
                "workstream_human_accepted_streams": workstream_acceptance_decisions.get("accepted_streams"),
                "workstream_all_human_accepted": workstream_acceptance_decisions.get("all_streams_accepted"),
            },
            "blockers": unique_strings([
                *(governance.get("blockers") or []),
                *(customer_delivery.get("blockers") or []),
                *((["external data source registry validation is not ready"] if external_data_validation.get("ready") is False else [])),
                *((["workstream acceptance gates are not complete"] if not acceptance_gates.get("all_accepted") else [])),
                "local release remains an internal review manifest only",
            ]),
            "next_commands": [
                "complete external data/tool license review",
                "complete IP/FTO and biosecurity human review before any customer sequence package",
                "rerun python3 scripts/run_safe_training_pipeline.py",
            ],
        },
        {
            "stream": "platform_integration",
            "status": "local_gate_passed",
            "ready": False,
            "current": {
                "backend_contract": exists("platform_integration/backend_tool_contract.md"),
                "adapter_stub": exists("platform_integration/kwb_tool_adapter_stub.py"),
                "runtime_panel_design": exists("ui/runtime_panel_design.md"),
                "structure_workflow_gate": exists("platform_integration/structure_workflow_gate.py"),
                "workflow_gate_assertions": workflow_gate.get("assertions", {}),
                "local_adapter": exists("platform_integration/kwb_tool_adapter_local.py"),
                "local_adapter_assertions": local_adapter.get("assertions", {}),
                "external_tool_contract": exists("platform_integration/external_tool_adapter_contract.md"),
                "external_tool_adapter_schema": exists("contracts/external_tool_adapter.schema.json"),
                "foreign_tool_registry": exists("config/foreign_tool_registry.local.example.json"),
                "foreign_tool_readiness": foreign_tools.get("status_counts"),
            },
            "blockers": ["production platform integration is not authorized; local gate only"],
            "next_commands": [
                "keep local-only until explicit server update instruction",
            ],
        },
    ]

    board = {
        "overall_status": "blocked_for_model_claim",
        "local_only": True,
        "data_quality_score": data_quality.get("overall_score"),
        "streams": streams,
        "ready_streams": sum(1 for item in streams if item["ready"]),
        "partial_ready_streams": sum(1 for item in streams if item.get("status") in {"partial_ready", "runtime_ready", "local_gate_passed"}),
        "total_streams": len(streams),
        "recommended_order": [
            "numbering_curation",
            "structure_cache",
            "domain_intervals",
            "kwb_experiment_feedback",
            "msa_conservation",
            "model_training",
            "governance_release",
            "platform_integration",
        ],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(board, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "overall_status": board["overall_status"],
        "ready_streams": board["ready_streams"],
        "total_streams": board["total_streams"],
        "output": str(args.output),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
