#!/usr/bin/env python3
"""Build the local enzyme-analysis constraint policy report.

This report is a local-only governance artifact. It records the required order
of analysis, tool-call display contract, database fusion rules, ddG thresholds,
human review gates, Rosetta integration status, and wet-lab validation workflow.
It does not execute external tools or mutate training data.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
OUT = AI_ROOT / "reports" / "enzyme_analysis_constraint_policy_report.json"


def build_policy() -> dict[str, Any]:
    pipeline_order = [
        "input_validation",
        "property_prediction_first",
        "database_and_evidence_fusion",
        "numbering_and_structure_gate",
        "important_mutation_site_prioritization",
        "ddg_or_stability_cross_check",
        "human_review_gate",
        "experiment_workflow_output",
    ]
    tool_sequence = [
        {
            "order": 1,
            "tool": "predict_properties",
            "purpose": "Sequence-level physicochemical prediction before residue claims.",
            "required_when": "sequence is present",
            "blocked_when": "no sequence or user explicitly forbids property prediction",
        },
        {
            "order": 2,
            "tool": "annotation_bundle",
            "purpose": "Combine InterPro/Pfam, catalytic annotations, signal peptide and local annotation evidence.",
            "required_when": "sequence or mapped structure is present",
            "blocked_when": "only PDB without extracted sequence, or user forbids annotation/database lookup",
        },
        {
            "order": 3,
            "tool": "structure_search_foldseek",
            "purpose": "Find structural neighbors when a structure exists.",
            "required_when": "uploaded PDB/mmCIF or trusted predicted structure exists",
            "blocked_when": "sequence-only stage or Foldseek runtime/database unavailable",
        },
        {
            "order": 4,
            "tool": "residue_mapping_sifts",
            "purpose": "Map PDB residue numbering to UniProt/user sequence numbering.",
            "required_when": "structure-dependent residue claims are requested",
            "blocked_when": "no structure or no mapping evidence",
        },
        {
            "order": 5,
            "tool": "residue_numbering_gate",
            "purpose": "Fail closed when residue numbering is not confirmed.",
            "required_when": "projecting literature/database/user mutation sites onto a structure",
            "blocked_when": "numbering relation is unknown or user has not confirmed mapping",
        },
        {
            "order": 6,
            "tool": "mutation_priority_score",
            "purpose": "Rank important mutation sites after property/database/numbering gates.",
            "required_when": "user requests concrete mutation sites or engineering candidates",
            "blocked_when": "no sequence, protected catalytic site, or user forbids mutation scoring",
        },
        {
            "order": 7,
            "tool": "mutation_epistasis_check",
            "purpose": "Check combination risk before recommending multi-mutants.",
            "required_when": "two or more mutations are proposed",
            "blocked_when": "single-mutant feedback or structural distances are missing for high-risk combinations",
        },
        {
            "order": 8,
            "tool": "gromacs_md",
            "purpose": "Optional reviewed stability/trajectory validation; asynchronous only.",
            "required_when": "user explicitly requests MD and runtime/topology are available",
            "blocked_when": "GROMACS/runtime/topology is unavailable or only plan-only conditions are met",
        },
    ]
    return {
        "policy_id": "kwb_enzyme_analysis_constraint_policy",
        "version": "1.0.0",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "local_only": True,
        "summary": (
            "Fixes the default analysis order for enzyme engineering: predict basic "
            "properties first, fuse databases with explicit evidence tiers, rank "
            "important mutation sites only after numbering/structure gates, and "
            "treat ddG/Rosetta results as reviewed evidence rather than automatic truth."
        ),
        "pipeline_order": pipeline_order,
        "tool_sequence": tool_sequence,
        "tool_call_display": {
            "user_confirmation_required_before_execution": True,
            "required_fields": [
                "step_order",
                "tool_name",
                "input_summary",
                "parameter_summary",
                "blocked_or_executed_status",
                "runtime_or_database_readiness",
                "result_preview",
                "evidence_level",
                "manual_review_required",
            ],
            "policy": (
                "Before execution, display the intended tool sequence and parameters. "
                "After confirmation, each tool call must be visible as a structured event/card."
            ),
        },
        "database_fusion_policy": {
            "source_tiers": [
                "tier_0_kwb_wet_lab_feedback",
                "tier_1_curated_local_db_with_reviewed_numbering",
                "tier_2_public_database_with_version_and_mapping",
                "tier_3_computational_prediction",
                "tier_4_weak_or_unreviewed_evidence",
            ],
            "forbidden_merges": [
                "Do not promote weak evidence to training labels without reviewed numbering decisions.",
                "Do not mix predicted ddG, public literature, and wet-lab feedback as one confidence class.",
                "Do not project database residue positions onto PDB structures without residue_numbering_gate.",
                "Do not use model outputs as experimental feedback records.",
            ],
            "priority_rule": (
                "KWB wet-lab feedback overrides predictions. Reviewed local database evidence "
                "overrides unreviewed public hints. Computational predictions remain hypotheses."
            ),
        },
        "mutation_site_rules": {
            "tier_1": "composite_priority >= 7.0 and no high-risk human-review gate is active",
            "tier_2": "5.0 <= composite_priority < 7.0 or useful but requires focused review",
            "tier_3": "composite_priority < 5.0 or low-confidence sequence-only support",
            "no_go": [
                "catalytic residue or active-site core",
                "metal/cofactor binding residue unless target is explicitly metal-dependence engineering",
                "disulfide cysteine or verified structural cysteine",
                "fully conserved family residue without reviewed override",
                "residue numbering mismatch or unconfirmed offset",
                "known single-mutant No-Go wet-lab feedback",
                "predicted severe destabilization with no compensating mechanism",
            ],
            "candidate_set_size": "Prefer 6-10 single mutants for first wet-lab round; combinations require prior single-mutant evidence.",
        },
        "ddg_thresholds": {
            "units": "kcal/mol",
            "sign_convention": "Negative ΔΔG is interpreted as more stable; positive ΔΔG as less stable.",
            "stabilizing": "ΔΔG < -1.0",
            "neutral": "-1.0 <= ΔΔG <= +1.0",
            "watch": "+1.0 < ΔΔG <= +2.0",
            "no_go": "ΔΔG > +2.0 unless reviewed compensating evidence exists",
            "manual_review_band": "-1.0 to +2.0 requires review against activity, expression, active-site distance and evidence tier.",
        },
        "rosetta_integration_status": {
            "status": "not_integrated_as_executable_ddg_tool",
            "current_repository_state": (
                "The platform has RosettaFold structure-prediction modules, but no local "
                "Rosetta/PyRosetta/FoldX mutant ΔΔG execution tool in the AI大模型 local pipeline."
            ),
            "allowed_claim": (
                "May report heuristic or external-tool-readiness status. Must not claim "
                "Rosetta ddG was executed unless a licensed/runtime-verified Rosetta adapter "
                "ran and produced auditable artifacts."
            ),
            "future_adapter_gate": [
                "license_review_approved",
                "runtime_binary_or_pyrosetta_available",
                "input_pdb_chain_numbering_verified",
                "mutation_list_validated",
                "output_ddg_artifacts_with_parameters_and_checksum",
            ],
        },
        "human_review_gates": [
            "residue_numbering_uncertain",
            "active_site_or_pocket_distance_less_than_review_radius",
            "database_evidence_conflict",
            "activity_up_stability_down_tradeoff",
            "ddg_in_manual_review_band",
            "combination_mutation_or_epistasis_risk",
            "substrate_or_ligand_mapping_uncertain",
            "order_ready_sequence_or_customer_deliverable_requested",
        ],
        "experiment_workflow": [
            "select 6-10 single mutants with Go/Watch rationale",
            "manual residue-numbering and active-site guardrail review",
            "primer design and mutagenesis plan outside the model",
            "PCR or synthesis, cloning, and sequence verification",
            "small-scale expression and soluble/insoluble fraction check",
            "purification or clarified lysate normalization",
            "baseline activity assay under WT reference conditions",
            "thermal challenge or DSF/Tm assay for stability",
            "pH/temperature profile when the objective targets process condition shift",
            "replicate analysis, QC flagging, and plate/well-level feedback intake",
            "only after validated single mutants: pairwise combination and epistasis check",
        ],
        "release_gate": {
            "safe_for_model_claim": False,
            "reason": (
                "This policy improves analysis governance and reporting consistency, "
                "but does not create reviewed labels, Rosetta execution, MSA features, "
                "or wet-lab validation."
            ),
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Build enzyme analysis constraint policy report")
    parser.add_argument("--output", type=Path, default=OUT)
    args = parser.parse_args()

    report = build_policy()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "output": str(args.output),
        "pipeline_steps": len(report["pipeline_order"]),
        "tool_steps": len(report["tool_sequence"]),
        "safe_for_model_claim": report["release_gate"]["safe_for_model_claim"],
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
