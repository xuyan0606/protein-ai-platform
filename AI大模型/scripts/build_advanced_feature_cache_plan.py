#!/usr/bin/env python3
"""Build advanced feature cache plan for P63.

This script creates cache directories and manifests only. It does not run
external models, generate embeddings, fabricate MSA files, or calculate ddG.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
REPORT_OUT = AI_ROOT / "reports" / "advanced_feature_cache_plan_report.json"
MANIFEST_OUT = AI_ROOT / "reports" / "advanced_feature_cache_manifest.json"
JSONL_OUT = AI_ROOT / "datasets" / "governance" / "advanced_feature_adapter_requirements.jsonl"
CACHE_ROOT = AI_ROOT / "cache" / "advanced_features"


FEATURE_FAMILIES = [
    {
        "family_id": "sequence_plm_embeddings",
        "adapter_ids": ["esm2", "esm_c", "esm3_open", "saprot_sequence", "prosst", "protssn"],
        "cache_root": "cache/advanced_features/sequence_plm",
        "expected_artifacts": ["embedding.npy|json", "metadata.json", "input_sequence.sha256", "model_card.json"],
        "required_gates": ["license", "runtime", "model_weight", "sequence_input"],
        "research_priority": "P1",
        "rationale": "Modern mutation ranking needs sequence and structure-aware protein language model representations.",
    },
    {
        "family_id": "msa_conservation",
        "adapter_ids": ["mmseqs2", "hmm_profile", "hhsuite_profile", "trusted_msa_cache"],
        "cache_root": "cache/advanced_features/msa_conservation",
        "expected_artifacts": ["msa.a3m|sto", "conservation.json", "database_metadata.json", "sha256"],
        "required_gates": ["runtime_or_trusted_cache", "homolog_database", "source_database_version", "checksums"],
        "research_priority": "P0",
        "rationale": "Evolutionary conservation remains the first unlock for mutation-effect and OOD risk.",
    },
    {
        "family_id": "structure_graph",
        "adapter_ids": ["structure_parser", "saprot_structure", "prosst_structure_tokens", "residue_neighborhood_graph"],
        "cache_root": "cache/advanced_features/structure_graph",
        "expected_artifacts": ["residue_graph.json", "chain_mapping.json", "structure_tokens.json", "structure.sha256"],
        "required_gates": ["reviewed_structure", "reviewed_chain_mapping", "numbering_verified"],
        "research_priority": "P0",
        "rationale": "Residue neighborhoods, structure tokens and chain mapping are required before structure-aware heads can be trusted.",
    },
    {
        "family_id": "ddg_stability",
        "adapter_ids": ["thermompnn", "rosetta_ddg", "pyrosetta_ddg", "foldx_ddg", "thermompnn_d", "thermompnn_i"],
        "cache_root": "cache/advanced_features/ddg_stability",
        "expected_artifacts": ["ddg_table.json", "parameters.json", "runtime.log", "input_structure.sha256"],
        "required_gates": ["license", "runtime", "reviewed_structure", "mutation_list", "artifact_checksums"],
        "research_priority": "P0",
        "rationale": "Stability needs explicit ddG/proxy-ddG artifacts; Rosetta/FoldX names alone are not evidence.",
    },
    {
        "family_id": "structure_affinity_complex",
        "adapter_ids": ["boltz2", "chai1", "alphafold3_benchmark"],
        "cache_root": "cache/advanced_features/structure_affinity",
        "expected_artifacts": ["complex_prediction.json", "affinity_prediction.json", "input_yaml_or_json.sha256", "runtime.log"],
        "required_gates": ["license", "runtime", "model_weight", "msa_or_template_policy", "ligand_identity_verified"],
        "research_priority": "P1",
        "rationale": "Top-tier enzyme work increasingly needs protein-ligand or biomolecular complex evidence, not protein-only folds.",
    },
    {
        "family_id": "kinetics_function",
        "adapter_ids": ["catpred", "clean", "deep_ec_transformer"],
        "cache_root": "cache/advanced_features/kinetics_function",
        "expected_artifacts": ["kinetics_prediction.json", "ec_consistency.json", "substrate_mapping.json", "runtime.log"],
        "required_gates": ["license", "runtime", "substrate_smiles_verified", "sequence_or_structure_input", "calibration_report"],
        "research_priority": "P1",
        "rationale": "Activity and substrate-fit heads need kinetics/function consistency signals, with conditions and substrate identity preserved.",
    },
    {
        "family_id": "candidate_generation",
        "adapter_ids": ["ligandmpnn", "proteinmpnn", "rfdiffusion2"],
        "cache_root": "cache/advanced_features/candidate_generation",
        "expected_artifacts": ["candidate_sequences.jsonl", "fixed_residue_policy.json", "design_constraints.json", "biosecurity_gate.json"],
        "required_gates": ["license", "runtime", "reviewed_structure", "protected_sites", "human_approval", "biosecurity_screening"],
        "research_priority": "P2",
        "rationale": "Generation should start only after ranking, structure, protected-site and safety gates are in place.",
    },
    {
        "family_id": "benchmark_score_cache",
        "adapter_ids": ["proteingym", "flip2", "atom3d_msp", "fireprotdb_eval", "prothermdb_eval"],
        "cache_root": "cache/advanced_features/benchmarks",
        "expected_artifacts": ["benchmark_scores.json", "split_definition.json", "metric_report.json", "dataset_license.json"],
        "required_gates": ["license", "dataset_version", "split_no_leakage", "metric_definition", "artifact_checksums"],
        "research_priority": "P0",
        "rationale": "A top-tier claim requires external benchmark comparison and leak-resistant splits.",
    },
    {
        "family_id": "wet_lab_feedback_calibration",
        "adapter_ids": ["kwb_experiment_feedback", "kwb_plate_feedback"],
        "cache_root": "cache/advanced_features/wet_lab_feedback",
        "expected_artifacts": ["feedback_features.jsonl", "schema_validation_report.json", "lineage.json"],
        "required_gates": ["schema_valid_feedback", "numbering_verified", "units_conditions_replicates_qc"],
        "research_priority": "P0",
        "rationale": "The defensible moat is KWB wet-lab feedback, plate-level QC and calibration.",
    },
]


ADAPTER_REGISTRY_ALIASES = {
    "alphafold3_benchmark": "alphafold3",
    "saprot_sequence": "saprot",
    "saprot_structure": "saprot",
    "prosst_structure_tokens": "prosst",
    "rosetta_ddg": "rosetta",
    "pyrosetta_ddg": "pyrosetta",
    "foldx_ddg": "foldx",
    "thermompnn_d": "thermompnn",
    "thermompnn_i": "thermompnn",
    "proteinmpnn": "ligandmpnn",
}


RESEARCH_SOURCES = [
    {
        "source_id": "boltz2",
        "url": "https://github.com/jwohlwend/boltz",
        "note": "Open biomolecular interaction and affinity route; still needs local runtime/model-weight/MSA readiness.",
    },
    {
        "source_id": "esm_c",
        "url": "https://github.com/Biohub/esm",
        "note": "Modern ESMC/ESMFold2 representation route; license and weight gates must be explicit.",
    },
    {
        "source_id": "saprot",
        "url": "https://github.com/westlake-repl/SaProt",
        "note": "Structure-aware AA+3Di protein language model route; requires structure token generation and licensing review.",
    },
    {
        "source_id": "prosst",
        "url": "https://github.com/AI4Protein/ProSST",
        "note": "Structure-token mutation-effect route; non-commercial style licensing keeps it isolated unless legal review approves.",
    },
    {
        "source_id": "proteingym",
        "url": "https://github.com/OATML-Markslab/ProteinGym",
        "note": "External mutation-effect benchmark route with DMS and clinical variant score sets.",
    },
    {
        "source_id": "mmseqs2",
        "url": "https://github.com/soedinglab/MMseqs2",
        "note": "Primary MSA/conservation unlock candidate; requires executable plus homolog database/cache manifest.",
    },
    {
        "source_id": "thermompnn",
        "url": "https://github.com/Kuhlman-Lab/ThermoMPNN",
        "note": "Stability ddG proxy baseline candidate; requires reviewed structure and runtime/model-weight readiness.",
    },
    {
        "source_id": "ligandmpnn",
        "url": "https://github.com/dauparas/LigandMPNN",
        "note": "Ligand-aware sequence design candidate generator; must stay behind design constraints and human approval.",
    },
    {
        "source_id": "catpred",
        "url": "https://github.com/maranasgroup/CatPred",
        "note": "Enzyme kinetics kcat/Km/Ki prediction route; requires substrate and condition validation.",
    },
    {
        "source_id": "clean",
        "url": "https://github.com/tttianhao/CLEAN",
        "note": "EC/function consistency route; research-use license requires isolation until reviewed.",
    },
    {
        "source_id": "alphafold3",
        "url": "https://github.com/google-deepmind/alphafold3",
        "note": "Powerful benchmark/isolated structure route; source and weights terms must be treated separately.",
    },
]


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Build advanced feature cache plan")
    parser.add_argument("--report", type=Path, default=REPORT_OUT)
    parser.add_argument("--manifest", type=Path, default=MANIFEST_OUT)
    parser.add_argument("--jsonl", type=Path, default=JSONL_OUT)
    args = parser.parse_args()

    foreign = load_json(AI_ROOT / "reports" / "foreign_tool_readiness_report.json")
    msa = load_json(AI_ROOT / "reports" / "msa_runtime_readiness_report.json")
    feedback = load_json(AI_ROOT / "reports" / "experiment_feedback_intake_validation_report.json")
    numbering = load_json(AI_ROOT / "reports" / "numbering_curation_validation_report.json")
    structure = load_json(AI_ROOT / "reports" / "structure_chain_mapping_decision_validation_report.json")
    ddg_policy = load_json(AI_ROOT / "reports" / "enzyme_analysis_constraint_policy_report.json")

    for family in FEATURE_FAMILIES:
        (AI_ROOT / family["cache_root"]).mkdir(parents=True, exist_ok=True)

    tool_status = {
        str(tool.get("tool_id")): tool
        for tool in foreign.get("tools", [])
        if isinstance(tool, dict) and tool.get("tool_id")
    }
    rows: list[dict[str, Any]] = []
    manifest_families = []
    for family in FEATURE_FAMILIES:
        adapters = []
        for adapter_id in family["adapter_ids"]:
            registry_id = ADAPTER_REGISTRY_ALIASES.get(adapter_id, adapter_id)
            tool = tool_status.get(registry_id, {})
            adapter_ready = bool(tool.get("ready_for_local_evaluation"))
            blockers = []
            if adapter_id in {"trusted_msa_cache"}:
                adapter_ready = bool((msa.get("trusted_cache") or {}).get("ready"))
                blockers = [] if adapter_ready else ["trusted MSA/cache validation not ready"]
            elif adapter_id in {"structure_parser", "residue_neighborhood_graph"}:
                valid_rows = structure.get("valid_rows") or structure.get("reviewed_rows") or 0
                adapter_ready = bool(valid_rows)
                blockers = [] if adapter_ready else ["reviewed structure chain mapping rows are missing or insufficient"]
            elif adapter_id in {"kwb_experiment_feedback", "kwb_plate_feedback"}:
                adapter_ready = (feedback.get("training_eligible_rows") or 0) > 0
                blockers = [] if adapter_ready else ["schema-valid training-eligible feedback rows are missing"]
            elif not adapter_ready:
                blockers = [
                    item for item in [
                        "license not ready" if tool and not tool.get("license_ready") else None,
                        "runtime not ready" if tool and not tool.get("runtime_ready") else None,
                        "data not ready" if tool and not tool.get("data_ready") else None,
                        "model weights not ready" if tool and not tool.get("model_weight_ready") else None,
                        "tool not registered in foreign_tool_readiness_report" if not tool else None,
                    ]
                    if item
                ]
            if adapter_id in {"prosst", "prosst_structure_tokens"}:
                blockers.append("license review required before commercial use")
            if adapter_id in {"clean"}:
                blockers.append("research-use license review required")
            if adapter_id in {"alphafold3_benchmark"}:
                blockers.append("model parameter/output terms require isolated benchmark handling")

            row = {
                "adapter_id": adapter_id,
                "registry_id": registry_id,
                "feature_family": family["family_id"],
                "status": "ready_to_implement" if adapter_ready else "blocked",
                "cache_root": family["cache_root"],
                "required_gates": family["required_gates"],
                "expected_artifacts": family["expected_artifacts"],
                "research_priority": family["research_priority"],
                "rationale": family["rationale"],
                "blockers": blockers,
                "policy": "Adapter plan only; no external execution or fabricated feature artifacts.",
            }
            rows.append(row)
            adapters.append(row)
        family_ready = all(row["status"] == "ready_to_implement" for row in adapters)
        manifest_families.append({
            "family_id": family["family_id"],
            "adapter_ids": family["adapter_ids"],
            "cache_root": family["cache_root"],
            "expected_artifacts": family["expected_artifacts"],
            "required_gates": family["required_gates"],
            "research_priority": family["research_priority"],
            "rationale": family["rationale"],
            "status": "ready_to_implement" if family_ready else "blocked",
        })

    manifest = {
        "manifest_id": "kwb_advanced_feature_cache_manifest",
        "version": "1.0.0",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "local_only": True,
        "feature_families": manifest_families,
        "cache_roots": {family["family_id"]: family["cache_root"] for family in FEATURE_FAMILIES},
        "status": "blocked",
        "research_sources": RESEARCH_SOURCES,
        "policy": "Empty cache plan. Feature files become usable only after validator reports confirm real artifacts and checksums.",
    }
    report = {
        "created_at": manifest["created_at"],
        "local_only": True,
        "manifest": str(args.manifest.relative_to(AI_ROOT) if args.manifest.is_absolute() else args.manifest),
        "jsonl": str(args.jsonl.relative_to(AI_ROOT) if args.jsonl.is_absolute() else args.jsonl),
        "feature_family_rows": len(FEATURE_FAMILIES),
        "adapter_requirement_rows": len(rows),
        "blocked_adapter_rows": sum(1 for row in rows if row["status"] == "blocked"),
        "ready_adapter_rows": sum(1 for row in rows if row["status"] == "ready_to_implement"),
        "current_readiness": {
            "numbering_valid_rows": numbering.get("valid_rows", 0),
            "msa_runtime_ready": msa.get("runtime_ready"),
            "feedback_training_eligible_rows": feedback.get("training_eligible_rows", 0),
            "rosetta_status": (ddg_policy.get("rosetta_integration_status") or {}).get("status"),
        },
        "families": manifest_families,
        "research_sources": RESEARCH_SOURCES,
        "top_tier_assessment": {
            "current_state_is_top_tier": False,
            "reason": "The code now has architecture/cache landing zones, but no real PLM/MSA/ddG/kinetics/benchmark/wet-lab feature artifacts are integrated.",
            "next_code_direction": "Implement validator-first adapters for MMseqs2/cache, reviewed structure graph, ThermoMPNN/Boltz-2/CatPred/ProteinGym in that order.",
        },
        "policy": "Planning and cache directory creation only; no external execution and no synthetic features.",
    }
    write_jsonl(args.jsonl, rows)
    args.manifest.parent.mkdir(parents=True, exist_ok=True)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.manifest.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "feature_family_rows": report["feature_family_rows"],
        "adapter_requirement_rows": report["adapter_requirement_rows"],
        "blocked_adapter_rows": report["blocked_adapter_rows"],
        "output": str(args.report),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
