#!/usr/bin/env python3
"""Build a compact dashboard for curation and structure-cache readiness."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
OUT = AI_ROOT / "reports" / "curation_dashboard.json"


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def main() -> int:
    parser = argparse.ArgumentParser(description="Build curation dashboard")
    parser.add_argument("--output", type=Path, default=OUT)
    args = parser.parse_args()

    integrity = load_json(AI_ROOT / "reports" / "mutation_label_integrity_report.json")
    queue = load_json(AI_ROOT / "reports" / "numbering_curation_queue_report.json")
    uniprot_evidence = load_json(AI_ROOT / "reports" / "numbering_uniprot_evidence_report.json")
    isoform_evidence = load_json(AI_ROOT / "reports" / "numbering_isoform_evidence_report.json")
    isoform_candidates = load_json(AI_ROOT / "reports" / "numbering_isoform_review_candidate_report.json")
    pubmed_evidence = load_json(AI_ROOT / "reports" / "numbering_pubmed_evidence_report.json")
    pubmed_abstract = load_json(AI_ROOT / "reports" / "numbering_pubmed_abstract_evidence_report.json")
    review_worklist = load_json(AI_ROOT / "reports" / "numbering_review_worklist_report.json")
    review_packets = load_json(AI_ROOT / "reports" / "numbering_review_packet_report.json")
    review_packet_validation = load_json(AI_ROOT / "reports" / "numbering_review_packet_validation_report.json")
    review_packet_board = load_json(AI_ROOT / "reports" / "numbering_review_packet_board_report.json")
    review_briefing = load_json(AI_ROOT / "reports" / "numbering_review_briefing.json")
    review_briefing_validation = load_json(AI_ROOT / "reports" / "numbering_review_briefing_validation_report.json")
    review_briefing_status = load_json(AI_ROOT / "reports" / "numbering_review_briefing_status_board_report.json")
    review_briefing_status_validation = load_json(AI_ROOT / "reports" / "numbering_review_briefing_status_board_validation_report.json")
    literature_risk = load_json(AI_ROOT / "reports" / "numbering_literature_review_risk_report.json")
    numbering_semantic_conflict = load_json(AI_ROOT / "reports" / "numbering_decision_semantic_conflict_report.json")
    numbering_operator_queue = load_json(AI_ROOT / "reports" / "numbering_review_operator_queue.json")
    batches = load_json(AI_ROOT / "reports" / "curation_batch_report.json")
    batch_status = load_json(AI_ROOT / "reports" / "curation_batch_status_report.json")
    decision_templates = load_json(AI_ROOT / "reports" / "curation_decision_template_report.json")
    validation = load_json(AI_ROOT / "reports" / "numbering_curation_validation_report.json")
    applied = load_json(AI_ROOT / "reports" / "numbering_curation_apply_report.json")
    weak = load_json(AI_ROOT / "reports" / "weak_evidence_index_report.json")
    structure = load_json(AI_ROOT / "reports" / "structure_cache_audit_report.json")
    structure_manifest = load_json(AI_ROOT / "reports" / "structure_cache_expected_manifest.json")
    structure_chain_worklist = load_json(AI_ROOT / "reports" / "structure_chain_mapping_worklist_report.json")
    structure_chain_packets = load_json(AI_ROOT / "reports" / "structure_chain_review_packet_report.json")
    structure_chain_validation = load_json(AI_ROOT / "reports" / "structure_chain_mapping_decision_validation_report.json")
    structure_chain_apply = load_json(AI_ROOT / "reports" / "structure_chain_mapping_apply_report.json")
    readiness = load_json(AI_ROOT / "reports" / "training_readiness_report.json")
    domain_interpro = load_json(AI_ROOT / "reports" / "domain_interpro_evidence_report.json")
    domain_interpro_decisions = load_json(AI_ROOT / "reports" / "domain_interval_interpro_decision_report.json")
    domain_interpro_packets = load_json(AI_ROOT / "reports" / "domain_interpro_review_packet_report.json")
    domain_batches = load_json(AI_ROOT / "reports" / "domain_interval_batch_report.json")
    domain_templates = load_json(AI_ROOT / "reports" / "domain_interval_decision_template_report.json")
    domain_validation = load_json(AI_ROOT / "reports" / "domain_interval_decision_validation_report.json")
    domain_applied = load_json(AI_ROOT / "reports" / "domain_interval_apply_report.json")
    domain_status = load_json(AI_ROOT / "reports" / "domain_interval_batch_status_report.json")
    msa_execution_plan = load_json(AI_ROOT / "reports" / "msa_execution_plan_report.json")
    msa_cache_validation = load_json(AI_ROOT / "reports" / "msa_conservation_cache_validation_report.json")
    msa_runtime = load_json(AI_ROOT / "reports" / "msa_runtime_readiness_report.json")
    msa_runtime_commands = load_json(AI_ROOT / "reports" / "msa_runtime_command_report.json")
    foreign_tools = load_json(AI_ROOT / "reports" / "foreign_tool_readiness_report.json")
    feedback_sources = load_json(AI_ROOT / "reports" / "experiment_feedback_source_discovery_report.json")
    feedback_source_packets = load_json(AI_ROOT / "reports" / "experiment_feedback_source_review_packet_report.json")

    dashboard = {
        "label_integrity": {
            "rows": integrity.get("rows"),
            "verified_rows": integrity.get("verified_rows"),
            "weak_evidence_rows": integrity.get("weak_evidence_rows"),
            "verified_ratio": integrity.get("verified_ratio"),
            "decision": integrity.get("decision"),
        },
        "curation_queue": {
            "queue_rows": queue.get("queue_rows"),
            "semantic_conflict_rows": numbering_semantic_conflict.get("semantic_conflict_rows"),
            "semantic_conflict_open_rows": numbering_semantic_conflict.get("open_conflict_rows"),
            "operator_queue_rows": numbering_operator_queue.get("queue_rows"),
            "operator_queue_open_numbering_rows": numbering_operator_queue.get("open_numbering_rows"),
            "operator_queue_status_counts": numbering_operator_queue.get("operator_status_counts"),
            "operator_queue_top_items": numbering_operator_queue.get("top_items", [])[:10],
            "priority_counts": queue.get("priority_counts"),
            "top_uniprot_groups": queue.get("top_uniprot_groups", [])[:10],
            "public_uniprot_evidence_rows": uniprot_evidence.get("evidence_rows"),
            "public_uniprot_accessions": uniprot_evidence.get("unique_accessions_fetched_or_cached"),
            "reported_wt_matches_current_uniprot": uniprot_evidence.get("reported_wt_matches_current_uniprot"),
            "rows_with_isoform_options": uniprot_evidence.get("rows_with_isoform_options"),
            "isoform_evidence_rows": isoform_evidence.get("rows_with_isoforms_in_scope"),
            "isoform_exact_position_matches": isoform_evidence.get("rows_with_exact_isoform_position_match"),
            "isoform_review_candidate_rows": isoform_candidates.get("candidate_rows"),
            "pubmed_unique_found": pubmed_evidence.get("unique_pmids_found"),
            "pubmed_high_review_risk_rows": pubmed_evidence.get("rows_high_review_risk"),
            "pubmed_abstract_rows_with_signal": pubmed_abstract.get("rows_with_abstract_signal"),
            "pubmed_abstract_mutation_mentions": pubmed_abstract.get("rows_with_reported_mutation_mention"),
            "review_worklist_rows": review_worklist.get("worklist_rows"),
            "review_worklist_bucket_counts": review_worklist.get("bucket_counts"),
            "review_packet_rows": review_packets.get("packet_rows"),
            "review_packet_reports": review_packets.get("packet_reports"),
            "review_packet_validation_rows": review_packet_validation.get("packet_count"),
            "review_packet_validation_valid_packet_rows": review_packet_validation.get("valid_packet_rows"),
            "review_packet_validation_valid_draft_rows": review_packet_validation.get("valid_draft_rows"),
            "review_packet_board_rows": review_packet_board.get("packet_board_rows"),
            "review_packet_board_open_blocked_rows": review_packet_board.get("open_blocked_packet_rows"),
            "review_packet_board_status_counts": review_packet_board.get("packet_status_counts"),
            "review_briefing_rows": len(review_briefing.get("briefing_rows") or []),
            "review_briefing_valid_rows": review_briefing_validation.get("valid_rows"),
            "review_briefing_invalid_rows": review_briefing_validation.get("invalid_rows"),
            "review_briefing_status_rows": review_briefing_status.get("briefing_rows"),
            "review_briefing_status_open_blocked_rows": review_briefing_status.get("open_blocked_briefing_rows"),
            "review_briefing_status_decision_rows_present": review_briefing_status.get("decision_rows_present_for_briefing"),
            "review_briefing_status_valid_rows": review_briefing_status_validation.get("valid_status_rows"),
            "review_briefing_status_invalid_rows": review_briefing_status_validation.get("invalid_status_rows"),
            "review_briefing_status_all_valid": bool(review_briefing_status_validation.get("all_status_rows_valid")),
            "literature_high_risk_rows": literature_risk.get("high_risk_rows"),
            "literature_possible_relevance_rows": literature_risk.get("possible_relevance_rows"),
            "semantic_conflict_top_items": numbering_semantic_conflict.get("top_items", [])[:10],
        },
        "batching": {
            "priority": batches.get("priority"),
            "available_rows": batches.get("available_rows"),
            "batches": len(batches.get("batches", [])),
            "covered_rows": batches.get("covered_rows"),
            "decision_template_rows": decision_templates.get("rows"),
            "decision_coverage": batch_status.get("coverage"),
            "decided_rows": batch_status.get("decided_rows"),
            "undecided_rows": batch_status.get("undecided_rows"),
        },
        "decision_validation": {
            "decision_rows": validation.get("decision_rows"),
            "valid_rows": validation.get("valid_rows"),
            "invalid_rows": validation.get("invalid_rows"),
            "error_counts": validation.get("error_counts"),
        },
        "apply_result": {
            "usable_as_supervised_label": applied.get("usable_as_supervised_label"),
            "status_counts": applied.get("status_counts"),
        },
        "weak_evidence": {
            "rows": weak.get("rows"),
            "groups": weak.get("groups"),
            "evidence_tiers": weak.get("evidence_tiers"),
        },
        "structure_cache": {
            "coordinate_features_ready": structure.get("coordinate_features_ready"),
            "pdb_sample_existing": structure.get("pdb_sample_existing"),
            "alphafold_sample_existing": structure.get("alphafold_sample_existing"),
            "expected_manifest_summary": structure_manifest.get("summary"),
            "chain_mapping_worklist_rows": structure_chain_worklist.get("worklist_rows"),
            "chain_mapping_bucket_counts": structure_chain_worklist.get("bucket_counts"),
            "single_chain_close_candidates": structure_chain_worklist.get("single_chain_close_candidates"),
            "multi_chain_needs_selection": structure_chain_worklist.get("multi_chain_needs_selection"),
            "chain_review_packet_rows": structure_chain_packets.get("packet_rows"),
            "chain_review_packet_reports": structure_chain_packets.get("packet_reports"),
            "chain_mapping_decision_rows": structure_chain_validation.get("decision_rows"),
            "valid_chain_mapping_decision_rows": structure_chain_validation.get("valid_rows"),
            "invalid_chain_mapping_decision_rows": structure_chain_validation.get("invalid_rows"),
            "reviewed_chain_mapping_rows": structure_chain_apply.get("reviewed_chain_mapping_rows"),
            "usable_for_coordinate_features": structure_chain_apply.get("usable_for_coordinate_features"),
        },
        "domain_intervals": {
            "available_rows": domain_batches.get("available_rows"),
            "batch_count": len(domain_batches.get("batches", [])),
            "covered_rows": domain_batches.get("covered_rows"),
            "template_rows": domain_templates.get("rows"),
            "decision_rows": domain_validation.get("decision_rows"),
            "valid_decision_rows": domain_validation.get("valid_rows"),
            "invalid_decision_rows": domain_validation.get("invalid_rows"),
            "curated_output_rows": domain_applied.get("output_rows"),
            "usable_for_position_features": domain_applied.get("usable_for_position_features"),
            "decision_coverage": domain_status.get("coverage"),
            "interpro_evidence_rows": domain_interpro.get("output_rows"),
            "interpro_exact_pfam_interval_rows": domain_interpro.get("rows_with_exact_pfam_interval"),
            "interpro_generated_decisions": domain_interpro_decisions.get("generated_decisions"),
            "interpro_program_reviewed_decisions": domain_interpro_decisions.get("interpro_program_reviewed_decisions"),
            "interpro_merged_decision_rows": domain_interpro_decisions.get("merged_decision_rows"),
            "interpro_unresolved_rows": domain_interpro_packets.get("unresolved_rows"),
            "interpro_review_packet_rows": domain_interpro_packets.get("packet_rows"),
            "interpro_unresolved_bucket_counts": domain_interpro_packets.get("unresolved_bucket_counts"),
        },
        "readiness": {
            "ready_for_supervised_training_pipeline": readiness.get("ready_for_supervised_training_pipeline"),
            "ready_for_supervised_small_model_claim": readiness.get("ready_for_supervised_small_model_claim"),
            "blockers": readiness.get("blockers"),
        },
        "msa_execution": {
            "planned_jobs": msa_execution_plan.get("planned_jobs"),
            "ready_jobs": msa_execution_plan.get("ready_jobs"),
            "blocked_jobs": msa_execution_plan.get("blocked_jobs"),
            "executor_status": msa_execution_plan.get("executor_status"),
            "available_executors": msa_execution_plan.get("available_executors"),
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
        },
        "foreign_tool_readiness": {
            "tool_rows": foreign_tools.get("tool_rows"),
            "ready_for_local_evaluation": foreign_tools.get("ready_for_local_evaluation"),
            "status_counts": foreign_tools.get("status_counts"),
            "commercial_evaluation_allowed_tools": foreign_tools.get("commercial_evaluation_allowed_tools"),
            "license_review_required_tools": foreign_tools.get("license_review_required_tools"),
            "restricted_tools": foreign_tools.get("restricted_tools"),
        },
        "experiment_feedback_sources": {
            "candidate_rows": feedback_sources.get("candidate_rows"),
            "top_candidates": feedback_sources.get("top_candidates", [])[:10],
            "review_packets": feedback_source_packets.get("packets"),
            "review_packet_rows": feedback_source_packets.get("packet_rows"),
            "review_bucket_counts": feedback_source_packets.get("bucket_counts"),
        },
        "next_operational_actions": [
            "curate P0 batch files under datasets/curation/batches",
            "append reviewed decisions to datasets/curation/numbering_curation_decisions.jsonl",
            "use decision_templates only as working copies; do not point apply scripts at template files",
            "review numbering_review_packet_board before manual curation",
            "review numbering_review_briefing_status_board for the first 33 high-priority numbering rows",
            "run validate_numbering_curation_decisions.py before apply_numbering_curation.py",
            "populate local structure cache and rerun audit_structure_cache.py",
            "review numbering_uniprot_evidence.jsonl; evidence is not a curation decision",
            "review structure_chain_review_packets and append only reviewed rows to structure_chain_mapping_decisions.jsonl",
        ],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(dashboard, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "verified_rows": dashboard["label_integrity"]["verified_rows"],
        "queue_rows": dashboard["curation_queue"]["queue_rows"],
        "batch_covered_rows": dashboard["batching"]["covered_rows"],
        "output": str(args.output),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
