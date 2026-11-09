"""Input gates for non-enzyme protein R&D specialty workflows."""

from __future__ import annotations

from typing import Any

from app.tools.human_target_antibody_contracts import contract_schemas, contract_summaries
from app.tools.registry import ToolRegistry


_WORKFLOWS: dict[str, dict[str, Any]] = {
    "human_membrane_offtarget": {
        "required": ["target_antigen", "binder_type"],
        "recommended": ["known_epitope", "binder_sequence", "indication", "format"],
        "contract_names": [
            "HumanProteinProfile",
            "ExpressionSafetyProfile",
            "ExtracellularAccessibility",
            "EpitopeSimilarity",
            "OffTargetRisk",
        ],
        "blocked_claims": [
            "do not claim experimental off-target binding from in-silico similarity",
            "do not rank healthy risk from full-length similarity alone",
            "do not mix RNA expression with protein surface abundance without labels",
            "do not write database versions unless a manifest was read",
        ],
    },
    "ligand_receptor_query": {
        "required": ["ligand"],
        "recommended": ["species", "affinity_cutoff", "tissue_context"],
        "contract_names": ["HumanProteinProfile", "ExpressionSafetyProfile"],
        "blocked_claims": [
            "do not call a receptor high-affinity without affinity value/source",
            "do not conflate receptor expression with ligand binding evidence",
        ],
    },
    "pathway_membrane_query": {
        "required": ["pathway"],
        "recommended": ["species", "localization_filter", "disease_axes"],
        "contract_names": ["PathwayRelation", "HumanProteinProfile"],
        "blocked_claims": [
            "do not infer tumor/immune/fibrosis role from pathway membership alone",
            "do not include intracellular-only proteins when membrane/extracellular filter is requested",
        ],
    },
    "antibody_humanization": {
        "required": ["vh_sequence", "vl_sequence", "light_chain_type"],
        "recommended": ["species", "numbering_scheme", "antigen", "binding_epitope", "framework_conservatism"],
        "contract_names": [
            "AntibodyChainProfile",
            "GermlineMatch",
            "HumanizationProposal",
            "DevelopabilityProfile",
        ],
        "blocked_claims": [
            "do not promise affinity retention without antigen/epitope or experimental data",
            "do not humanize incomplete or unnumbered antibody chains",
            "do not mix kappa and lambda assumptions",
        ],
    },
}


def _normalize_workflow(value: str) -> str:
    lower = str(value or "").strip().lower()
    if "muc16" in lower or "offtarget" in lower or "脱靶" in lower or "膜蛋白" in lower:
        return "human_membrane_offtarget"
    if "cxcl12" in lower or "receptor" in lower or "配体" in lower or "受体" in lower:
        return "ligand_receptor_query"
    if "tgf" in lower or "pathway" in lower or "通路" in lower:
        return "pathway_membrane_query"
    if "humanization" in lower or "antibody" in lower or "人源化" in lower or "抗体" in lower:
        return "antibody_humanization"
    return lower


def bio_specialty_input_gate(
    workflow: str,
    inputs: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Validate first-layer inputs for human target/antibody specialty workflows."""
    key = _normalize_workflow(workflow)
    definition = _WORKFLOWS.get(key)
    if not definition:
        return {
            "status": "blocked",
            "workflow": key or "unknown",
            "blocked_reason": "unknown_workflow",
            "supported_workflows": sorted(_WORKFLOWS),
        }

    payload = inputs if isinstance(inputs, dict) else {}
    missing_required = [field for field in definition["required"] if not payload.get(field)]
    missing_recommended = [field for field in definition["recommended"] if not payload.get(field)]
    status = "ready" if not missing_required else "blocked"
    contract_names = definition["contract_names"]
    return {
        "status": status,
        "workflow": key,
        "missing_required": missing_required,
        "missing_recommended": missing_recommended,
        "data_contracts": contract_summaries(contract_names),
        "data_contract_schemas": contract_schemas(contract_names),
        "evidence_status": "schema_only_no_retrieval",
        "claim_eligible": False,
        "model_claim_ready": False,
        "release_ready": False,
        "blocked_claims": definition["blocked_claims"],
        "next_actions": (
            ["Proceed to evidence retrieval with versioned source manifests."]
            if status == "ready"
            else [f"Collect required input: {field}" for field in missing_required]
        ),
        "report_boundary": (
            "Report may define candidate-evidence workflow; no final biological conclusion before source retrieval."
            if status == "ready"
            else "Ask for missing inputs; do not run broad search or produce final recommendations."
        ),
    }


ToolRegistry.register(
    name="bio_specialty_input_gate",
    description=(
        "Validate first-layer inputs and data contracts for human membrane off-target, "
        "ligand-receptor, pathway, and antibody humanization workflows."
    ),
    parameters={
        "type": "object",
        "properties": {
            "workflow": {
                "type": "string",
                "description": "human_membrane_offtarget, ligand_receptor_query, pathway_membrane_query, antibody_humanization, or natural-language workflow.",
            },
            "inputs": {
                "type": "object",
                "description": "Workflow inputs such as target_antigen, binder_type, vh_sequence, vl_sequence, pathway, ligand.",
            },
        },
        "required": ["workflow"],
    },
    handler=bio_specialty_input_gate,
    category="analysis",
    timeout_seconds=30,
)
