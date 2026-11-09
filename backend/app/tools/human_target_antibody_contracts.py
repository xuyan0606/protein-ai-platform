"""Schema-only contracts for human target and antibody specialty workflows."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class SpecialtyContract:
    name: str
    required_fields: tuple[str, ...]
    evidence_boundary: str
    description: str

    def summary(self) -> str:
        return f"{self.name}: {self.description}"

    def schema(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "required_fields": list(self.required_fields),
            "evidence_boundary": self.evidence_boundary,
            "description": self.description,
            "schema_only": True,
        }


HumanProteinProfile = SpecialtyContract(
    name="HumanProteinProfile",
    required_fields=("uniprot_accession", "species", "isoform", "localization_evidence"),
    evidence_boundary="schema_only_no_retrieval",
    description="UniProt accession, isoform, topology, localization, and extracellular regions.",
)

ExpressionSafetyProfile = SpecialtyContract(
    name="ExpressionSafetyProfile",
    required_fields=("source", "source_version", "tissue_or_cell_type", "expression_measure", "evidence_type"),
    evidence_boundary="schema_only_no_retrieval",
    description="Normal tissue and cell-type expression with source and version labels.",
)

PathwayRelation = SpecialtyContract(
    name="PathwayRelation",
    required_fields=("source", "source_pathway_id", "role", "evidence_type"),
    evidence_boundary="schema_only_no_retrieval",
    description="Reactome, GO, or source pathway relation and role.",
)

AntibodyChainProfile = SpecialtyContract(
    name="AntibodyChainProfile",
    required_fields=("chain", "sequence", "numbering_scheme", "cdr_boundaries", "framework_boundaries"),
    evidence_boundary="schema_only_no_numbering_runtime",
    description="VH/VL type, numbering scheme, and CDR/framework boundaries.",
)

GermlineMatch = SpecialtyContract(
    name="GermlineMatch",
    required_fields=("chain", "species", "v_gene", "j_gene", "identity", "method"),
    evidence_boundary="schema_only_no_germline_search",
    description="Human V/J germline candidates, identity, and matching method.",
)

HumanizationProposal = SpecialtyContract(
    name="HumanizationProposal",
    required_fields=("framework_changes", "cdr_retention", "rationale", "assumptions"),
    evidence_boundary="schema_only_no_affinity_claim",
    description="Framework changes, CDR retention, and Vernier/backmutation rationale.",
)

DevelopabilityProfile = SpecialtyContract(
    name="DevelopabilityProfile",
    required_fields=("liabilities", "aggregation_risk", "ptm_risk", "expression_risk", "method"),
    evidence_boundary="schema_only_no_developability_prediction",
    description="Liabilities, aggregation, PTM, and expression-risk labels.",
)

EpitopeSimilarity = SpecialtyContract(
    name="EpitopeSimilarity",
    required_fields=("query_epitope", "target_region", "method", "artifact_provenance"),
    evidence_boundary="schema_only_no_similarity_runtime",
    description="Sequence, structure, or epitope similarity with method and artifact provenance.",
)

OffTargetRisk = SpecialtyContract(
    name="OffTargetRisk",
    required_fields=(
        "candidate_target",
        "extracellular_accessibility",
        "epitope_similarity",
        "healthy_expression",
        "risk_rationale",
    ),
    evidence_boundary="schema_only_no_offtarget_runtime",
    description="Candidate off-target risk record with accessibility, similarity, healthy expression, and rationale.",
)

ExtracellularAccessibility = SpecialtyContract(
    name="ExtracellularAccessibility",
    required_fields=("topology_source", "accessible_region", "evidence_type", "source_version"),
    evidence_boundary="schema_only_no_topology_lookup",
    description="Topology, signal peptide/GPI, and accessible ectodomain or loop.",
)


CONTRACTS: dict[str, SpecialtyContract] = {
    contract.name: contract
    for contract in (
        HumanProteinProfile,
        ExpressionSafetyProfile,
        PathwayRelation,
        AntibodyChainProfile,
        GermlineMatch,
        HumanizationProposal,
        DevelopabilityProfile,
        EpitopeSimilarity,
        OffTargetRisk,
        ExtracellularAccessibility,
    )
}


def contract_summaries(names: list[str]) -> list[str]:
    return [CONTRACTS[name].summary() for name in names if name in CONTRACTS]


def contract_schemas(names: list[str]) -> list[dict[str, Any]]:
    return [CONTRACTS[name].schema() for name in names if name in CONTRACTS]


def missing_contract_fields(contract_name: str, payload: dict[str, Any] | None) -> list[str]:
    """Return missing required fields; unknown contracts fail closed."""
    contract = CONTRACTS.get(str(contract_name or ""))
    if not contract:
        return ["unknown_contract"]
    data = payload if isinstance(payload, dict) else {}
    return [field for field in contract.required_fields if not data.get(field)]


def schema_audit_record(contract_name: str, payload: dict[str, Any] | None) -> dict[str, Any]:
    missing = missing_contract_fields(contract_name, payload)
    return {
        "contract": contract_name,
        "status": "ready" if not missing else "blocked",
        "missing_fields": missing,
        "schema_only": True,
        "claim_eligible": False,
        "model_claim_ready": False,
        "release_ready": False,
    }
