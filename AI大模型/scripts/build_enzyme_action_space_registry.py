#!/usr/bin/env python3
"""Build KWB enzyme action-space and tool-contract registry."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
ACTION_OUT = AI_ROOT / "datasets" / "governance" / "enzyme_action_space_registry.jsonl"
CONTRACT_OUT = AI_ROOT / "datasets" / "governance" / "enzyme_tool_contracts.jsonl"
REPORT_OUT = AI_ROOT / "reports" / "enzyme_action_space_registry_report.json"


ACTIONS: list[dict[str, Any]] = [
    {
        "action_id": "act_numbering_review",
        "category": "human_curation",
        "title": "Reviewed residue numbering curation",
        "description": "Review mutation numbering evidence before any label can become strict supervised data.",
        "primary_contract_id": "tool_numbering_curation_validate_apply",
        "input_artifacts": [
            "datasets/curation/numbering_curation_decisions.jsonl",
            "reports/numbering_review_operator_queue.json",
        ],
        "output_artifacts": [
            "reports/numbering_curation_validation_report.json",
            "reports/numbering_curation_apply_report.json",
        ],
        "risk_level": "high",
        "human_confirmation_required": True,
        "writes_formal_decision": True,
        "writes_training_rows": False,
        "safe_for_model_claim": False,
    },
    {
        "action_id": "act_structure_chain_mapping",
        "category": "human_curation",
        "title": "Reviewed structure chain mapping",
        "description": "Validate structure-to-UniProt chain mappings before coordinate graph features are used.",
        "primary_contract_id": "tool_structure_chain_mapping_validate_apply",
        "input_artifacts": [
            "datasets/curation/structure_chain_mapping_decisions.jsonl",
            "reports/structure_chain_dbref_evidence_audit_report.json",
        ],
        "output_artifacts": [
            "reports/structure_chain_mapping_decision_validation_report.json",
            "reports/reviewed_structure_graph_validation_report.json",
        ],
        "risk_level": "high",
        "human_confirmation_required": True,
        "writes_formal_decision": True,
        "writes_training_rows": False,
        "safe_for_model_claim": False,
    },
    {
        "action_id": "act_msa_conservation",
        "category": "feature_generation",
        "title": "MMseqs2 MSA conservation feature generation",
        "description": "Generate and validate homolog-backed conservation features.",
        "primary_contract_id": "tool_msa_mmseqs_cache_validate",
        "input_artifacts": [
            "datasets/curation/msa_conservation_targets.jsonl",
            "reports/mmseqs_homolog_database_manifest.json",
        ],
        "output_artifacts": [
            "reports/msa_conservation_cache_validation_report.json",
            "reports/strict_msa_site_feature_report.json",
        ],
        "risk_level": "medium",
        "human_confirmation_required": False,
        "writes_formal_decision": False,
        "writes_training_rows": False,
        "safe_for_model_claim": False,
    },
    {
        "action_id": "act_ddg_proxy_or_physics",
        "category": "external_tool",
        "title": "ddG proxy or physical backend execution",
        "description": "Run only license/runtime-approved stability backends and preserve negative-ddG-stabilizing convention.",
        "primary_contract_id": "tool_ddg_backend_readiness_probe",
        "input_artifacts": [
            "reports/ddg_backend_readiness_report.json",
            "reports/ddg_backend_runtime_receipt_validation_report.json",
        ],
        "output_artifacts": [
            "reports/thermompnn_venus15b_smoke_report.json",
            "reports/ddg_executable_probe_report.json",
        ],
        "risk_level": "high",
        "human_confirmation_required": True,
        "writes_formal_decision": False,
        "writes_training_rows": False,
        "safe_for_model_claim": False,
    },
    {
        "action_id": "act_wet_lab_feedback_authorization",
        "category": "human_curation",
        "title": "Wet-lab feedback authorization",
        "description": "Authorize real wet-lab metric rows before feedback intake or training eligibility.",
        "primary_contract_id": "tool_wet_lab_feedback_authorization_gate",
        "input_artifacts": [
            "datasets/feedback/wet_lab_mutant_library_feedback_authorizations.jsonl",
            "reports/wet_lab_mutant_library_feedback_authorization_worklist_report.json",
        ],
        "output_artifacts": [
            "reports/wet_lab_mutant_library_feedback_authorization_validation_report.json",
            "reports/wet_lab_mutant_library_feedback_preflight_report.json",
        ],
        "risk_level": "high",
        "human_confirmation_required": True,
        "writes_formal_decision": True,
        "writes_training_rows": False,
        "safe_for_model_claim": False,
    },
    {
        "action_id": "act_fireprot_candidate_review",
        "category": "external_data",
        "title": "FireProt stability candidate review",
        "description": "Keep external stability candidates in draft until license, dedup and reviewed import decisions pass.",
        "primary_contract_id": "tool_fireprot_reviewed_import_gate",
        "input_artifacts": [
            "reports/fireprot_curated_kwb_schema_mapping_report.json",
            "reports/fireprot_dedup_review_decision_validation_report.json",
        ],
        "output_artifacts": [
            "reports/fireprot_reviewed_import_candidate_report.json",
        ],
        "risk_level": "high",
        "human_confirmation_required": True,
        "writes_formal_decision": False,
        "writes_training_rows": False,
        "safe_for_model_claim": False,
    },
    {
        "action_id": "act_benchmark_score_cache",
        "category": "benchmark",
        "title": "Benchmark score cache validation",
        "description": "Validate no-leak benchmark scorecards before any model-quality claim.",
        "primary_contract_id": "tool_benchmark_score_cache_validate",
        "input_artifacts": [
            "reports/benchmark_matrix_report.json",
            "reports/benchmark_score_cache_intake_report.json",
        ],
        "output_artifacts": [
            "reports/benchmark_score_cache_validation_report.json",
        ],
        "risk_level": "high",
        "human_confirmation_required": True,
        "writes_formal_decision": False,
        "writes_training_rows": False,
        "safe_for_model_claim": False,
    },
    {
        "action_id": "act_model_claim_consistency",
        "category": "safety_guard",
        "title": "Model claim fail-closed consistency",
        "description": "Cross-check strict labels, MSA features, receipts and release state before any model claim.",
        "primary_contract_id": "tool_model_claim_fail_closed_consistency",
        "input_artifacts": [
            "reports/repaired_supervised_table_report.json",
            "reports/label_provenance_audit_report.json",
            "reports/strict_msa_site_feature_report.json",
        ],
        "output_artifacts": [
            "reports/model_claim_fail_closed_consistency_report.json",
        ],
        "risk_level": "critical",
        "human_confirmation_required": False,
        "writes_formal_decision": False,
        "writes_training_rows": False,
        "safe_for_model_claim": False,
    },
    {
        "action_id": "act_release_guard_links",
        "category": "safety_guard",
        "title": "Local release safety guard links",
        "description": "Ensure local release review package links all core safety guards.",
        "primary_contract_id": "tool_local_release_safety_guard_links",
        "input_artifacts": [
            "reports/local_release_manifest.json",
            "reports/data_lake_manifest.json",
        ],
        "output_artifacts": [
            "reports/local_release_safety_guard_link_validation_report.json",
        ],
        "risk_level": "critical",
        "human_confirmation_required": False,
        "writes_formal_decision": False,
        "writes_training_rows": False,
        "safe_for_model_claim": False,
    },
    {
        "action_id": "act_know_how_retrieval",
        "category": "know_how",
        "title": "Enzyme know-how retrieval",
        "description": "Retrieve SOP and policy snippets for numbering, ddG, wet-lab QC and customer restrictions.",
        "primary_contract_id": "tool_enzyme_know_how_retrieval_plan",
        "input_artifacts": [
            "reports/enzyme_analysis_constraint_policy_report.json",
            "reports/biomni_deep_source_learning_for_kwb_2026_07_31.md",
        ],
        "output_artifacts": [
            "reports/enzyme_resource_retrieval_plan_report.json",
        ],
        "risk_level": "medium",
        "human_confirmation_required": False,
        "writes_formal_decision": False,
        "writes_training_rows": False,
        "safe_for_model_claim": False,
    },
    {
        "action_id": "act_tool_contract_validation",
        "category": "safety_guard",
        "title": "Enzyme tool contract validation",
        "description": "Validate action-space and tool-contract metadata before controlled agent execution.",
        "primary_contract_id": "tool_enzyme_tool_contract_validator",
        "input_artifacts": [
            "datasets/governance/enzyme_action_space_registry.jsonl",
            "datasets/governance/enzyme_tool_contracts.jsonl",
        ],
        "output_artifacts": [
            "reports/enzyme_tool_contract_validation_report.json",
        ],
        "risk_level": "critical",
        "human_confirmation_required": False,
        "writes_formal_decision": False,
        "writes_training_rows": False,
        "safe_for_model_claim": False,
    },
    {
        "action_id": "act_safe_pipeline",
        "category": "pipeline",
        "title": "Safe training pipeline orchestration",
        "description": "Run all local build and validation steps in fail-closed order.",
        "primary_contract_id": "tool_safe_training_pipeline",
        "input_artifacts": [
            "scripts/run_safe_training_pipeline.py",
        ],
        "output_artifacts": [
            "reports/safe_training_pipeline_run.json",
            "reports/local_release_manifest.json",
        ],
        "risk_level": "critical",
        "human_confirmation_required": False,
        "writes_formal_decision": False,
        "writes_training_rows": False,
        "safe_for_model_claim": False,
    },
]


CONTRACTS: list[dict[str, Any]] = [
    {
        "contract_id": "tool_numbering_curation_validate_apply",
        "tool_name": "numbering curation validate/apply",
        "category": "human_curation",
        "allowed_execution_mode": "manual_only",
        "entrypoints": [
            "scripts/validate_numbering_curation_decisions.py",
            "scripts/apply_numbering_curation.py",
        ],
        "runtime_readiness": "ready_local_script",
        "license_status": "internal_only",
        "human_confirmation_required": True,
        "can_write_formal_decision": False,
        "can_write_training_rows": False,
        "requires_safe_pipeline_after_execution": True,
    },
    {
        "contract_id": "tool_structure_chain_mapping_validate_apply",
        "tool_name": "structure chain mapping validate/apply",
        "category": "human_curation",
        "allowed_execution_mode": "manual_only",
        "entrypoints": [
            "scripts/validate_structure_chain_mapping_decisions.py",
            "scripts/apply_structure_chain_mapping_decisions.py",
        ],
        "runtime_readiness": "ready_local_script",
        "license_status": "internal_only",
        "human_confirmation_required": True,
        "can_write_formal_decision": False,
        "can_write_training_rows": False,
        "requires_safe_pipeline_after_execution": True,
    },
    {
        "contract_id": "tool_msa_mmseqs_cache_validate",
        "tool_name": "MSA MMseqs cache validation",
        "category": "feature_generation",
        "allowed_execution_mode": "local_script",
        "entrypoints": [
            "scripts/build_strict_msa_site_features.py",
            "scripts/validate_msa_conservation_cache.py",
        ],
        "runtime_readiness": "ready_local_runtime_or_cache",
        "license_status": "commercial_review_required_for_external_db_use",
        "human_confirmation_required": False,
        "can_write_formal_decision": False,
        "can_write_training_rows": False,
        "requires_safe_pipeline_after_execution": True,
    },
    {
        "contract_id": "tool_ddg_backend_readiness_probe",
        "tool_name": "ddG backend readiness and smoke",
        "category": "external_tool",
        "allowed_execution_mode": "manual_only",
        "entrypoints": [
            "scripts/probe_ddg_executables.py",
            "scripts/validate_ddg_backend_runtime_receipts.py",
        ],
        "runtime_readiness": "partially_ready_proxy_only",
        "license_status": "physical_backends_not_authorized",
        "human_confirmation_required": True,
        "can_write_formal_decision": False,
        "can_write_training_rows": False,
        "requires_safe_pipeline_after_execution": True,
    },
    {
        "contract_id": "tool_wet_lab_feedback_authorization_gate",
        "tool_name": "wet-lab feedback authorization gate",
        "category": "human_curation",
        "allowed_execution_mode": "manual_only",
        "entrypoints": [
            "scripts/validate_wet_lab_mutant_library_feedback_authorizations.py",
            "scripts/preflight_wet_lab_mutant_library_feedback_intake.py",
        ],
        "runtime_readiness": "ready_local_script",
        "license_status": "internal_wet_lab_requires_human_authorization",
        "human_confirmation_required": True,
        "can_write_formal_decision": False,
        "can_write_training_rows": False,
        "requires_safe_pipeline_after_execution": True,
    },
    {
        "contract_id": "tool_fireprot_reviewed_import_gate",
        "tool_name": "FireProt reviewed import gate",
        "category": "external_data",
        "allowed_execution_mode": "local_script",
        "entrypoints": [
            "scripts/validate_fireprot_dedup_review_decisions.py",
            "scripts/build_fireprot_reviewed_import_candidates.py",
        ],
        "runtime_readiness": "ready_local_script",
        "license_status": "license_scope_not_selected",
        "human_confirmation_required": True,
        "can_write_formal_decision": False,
        "can_write_training_rows": False,
        "requires_safe_pipeline_after_execution": True,
    },
    {
        "contract_id": "tool_benchmark_score_cache_validate",
        "tool_name": "benchmark score cache validation",
        "category": "benchmark",
        "allowed_execution_mode": "local_script",
        "entrypoints": [
            "scripts/validate_benchmark_score_cache_intake.py",
        ],
        "runtime_readiness": "ready_local_script",
        "license_status": "benchmark_license_review_incomplete",
        "human_confirmation_required": True,
        "can_write_formal_decision": False,
        "can_write_training_rows": False,
        "requires_safe_pipeline_after_execution": True,
    },
    {
        "contract_id": "tool_model_claim_fail_closed_consistency",
        "tool_name": "model claim fail-closed consistency validator",
        "category": "safety_guard",
        "allowed_execution_mode": "local_script",
        "entrypoints": [
            "scripts/validate_model_claim_fail_closed_consistency.py",
        ],
        "runtime_readiness": "ready_local_script",
        "license_status": "internal_only",
        "human_confirmation_required": False,
        "can_write_formal_decision": False,
        "can_write_training_rows": False,
        "requires_safe_pipeline_after_execution": False,
    },
    {
        "contract_id": "tool_local_release_safety_guard_links",
        "tool_name": "local release safety guard link validator",
        "category": "safety_guard",
        "allowed_execution_mode": "local_script",
        "entrypoints": [
            "scripts/validate_local_release_safety_guard_links.py",
        ],
        "runtime_readiness": "ready_local_script",
        "license_status": "internal_only",
        "human_confirmation_required": False,
        "can_write_formal_decision": False,
        "can_write_training_rows": False,
        "requires_safe_pipeline_after_execution": False,
    },
    {
        "contract_id": "tool_enzyme_know_how_retrieval_plan",
        "tool_name": "enzyme know-how retrieval planner",
        "category": "know_how",
        "allowed_execution_mode": "read_only",
        "entrypoints": [
            "reports/enzyme_analysis_constraint_policy_report.json",
            "reports/biomni_deep_source_learning_for_kwb_2026_07_31.md",
        ],
        "runtime_readiness": "ready_read_only",
        "license_status": "internal_only",
        "human_confirmation_required": False,
        "can_write_formal_decision": False,
        "can_write_training_rows": False,
        "requires_safe_pipeline_after_execution": False,
    },
    {
        "contract_id": "tool_enzyme_tool_contract_validator",
        "tool_name": "enzyme tool contract validator",
        "category": "safety_guard",
        "allowed_execution_mode": "local_script",
        "entrypoints": [
            "scripts/validate_enzyme_tool_contracts.py",
        ],
        "runtime_readiness": "ready_local_script",
        "license_status": "internal_only",
        "human_confirmation_required": False,
        "can_write_formal_decision": False,
        "can_write_training_rows": False,
        "requires_safe_pipeline_after_execution": False,
    },
    {
        "contract_id": "tool_safe_training_pipeline",
        "tool_name": "safe training pipeline",
        "category": "pipeline",
        "allowed_execution_mode": "local_script",
        "entrypoints": [
            "scripts/run_safe_training_pipeline.py",
        ],
        "runtime_readiness": "ready_local_script",
        "license_status": "internal_only",
        "human_confirmation_required": False,
        "can_write_formal_decision": False,
        "can_write_training_rows": False,
        "requires_safe_pipeline_after_execution": False,
    },
]


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Build enzyme action-space and tool-contract registry")
    parser.add_argument("--actions-output", type=Path, default=ACTION_OUT)
    parser.add_argument("--contracts-output", type=Path, default=CONTRACT_OUT)
    parser.add_argument("--report-output", type=Path, default=REPORT_OUT)
    args = parser.parse_args()

    created_at = datetime.now(timezone.utc).isoformat()
    actions = [{**row, "created_at": created_at, "local_only": True} for row in ACTIONS]
    contracts = [{**row, "created_at": created_at, "local_only": True} for row in CONTRACTS]

    write_jsonl(args.actions_output, actions)
    write_jsonl(args.contracts_output, contracts)

    categories = sorted({row["category"] for row in actions})
    report = {
        "created_at": created_at,
        "local_only": True,
        "action_rows": len(actions),
        "contract_rows": len(contracts),
        "categories": categories,
        "human_confirmation_required_actions": sum(1 for row in actions if row["human_confirmation_required"]),
        "formal_decision_actions": sum(1 for row in actions if row["writes_formal_decision"]),
        "training_write_actions": sum(1 for row in actions if row["writes_training_rows"]),
        "safe_for_model_claim_actions": sum(1 for row in actions if row["safe_for_model_claim"]),
        "blocked_by_policy": True,
        "safe_for_training_import": False,
        "safe_for_model_claim": False,
        "release_ready": False,
        "outputs": {
            "actions": str(args.actions_output.relative_to(AI_ROOT)),
            "contracts": str(args.contracts_output.relative_to(AI_ROOT)),
        },
        "policy": "This registry describes controlled enzyme AI actions inspired by Biomni. It is metadata only and does not execute tools, write formal decisions, write training rows, or release model claims.",
    }
    args.report_output.parent.mkdir(parents=True, exist_ok=True)
    args.report_output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "action_rows": report["action_rows"],
        "contract_rows": report["contract_rows"],
        "training_write_actions": report["training_write_actions"],
        "safe_for_model_claim_actions": report["safe_for_model_claim_actions"],
        "output": str(args.report_output),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
