"""Reusable query service for annotation-centric protein lookups."""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.domain import (
    AlphaFoldStructure,
    CatalyticSite,
    DirectedEvolutionEntry,
    DomainArchitecture,
    EnzymeECLink,
    EnzymeInterProLink,
    EnzymeRecord,
    KineticParameter,
    PDBStructure,
    SignalPeptidePrediction,
    StabilityRecord,
    Taxonomy,
)


_CATALYTIC_ROLE_ALIASES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("nucleophile", ("nucleophile", "nucleophilic", "covalent")),
    ("acid_base", ("acid-base", "acid base", "general acid", "general base", "proton")),
    ("metal_binding", ("metal-binding", "metal binding", "metal ligand", "metal coordination")),
    ("cofactor_binding", ("cofactor", "prosthetic group")),
    ("substrate_binding", ("substrate-binding", "substrate binding", "substrate recognition")),
    ("catalytic_structural", ("catalytic structural", "catalytic support", "active-site architecture")),
)

_MECHANISTIC_STEPS_BY_ROLE = {
    "nucleophile": "nucleophilic_attack",
    "acid_base": "proton_transfer",
    "metal_binding": "metal_coordination",
    "cofactor_binding": "cofactor_positioning",
    "substrate_binding": "substrate_positioning",
    "catalytic_structural": "active_site_architecture",
    "unknown": "unknown",
}


def _normalize_catalytic_role(raw_role: object) -> str:
    value = str(raw_role or "").strip().lower()
    if not value:
        return "unknown"
    for normalized, aliases in _CATALYTIC_ROLE_ALIASES:
        if any(alias in value for alias in aliases):
            return normalized
    return "unknown"


def build_catalytic_mechanism_report_contract(
    *,
    status: str,
    coordinate_status: str,
    assignments: list[dict],
    pending_numbering: list[dict],
    blocked_reason: str | None = None,
) -> dict:
    """Return the conservative reporting boundary for a mechanism profile."""

    has_curated_assignments = bool(assignments)
    user_coordinate_verified = coordinate_status == "verified" and has_curated_assignments
    blocked_reasons = [
        str(item.get("reason"))
        for item in pending_numbering
        if isinstance(item, dict) and item.get("reason")
    ]
    if blocked_reason:
        blocked_reasons.insert(0, blocked_reason)
    if not has_curated_assignments and status in {"unknown", "blocked"}:
        blocked_reasons.append("no_curated_catalytic_residue_assignment")

    return {
        "claim_status": (
            "SUPPORTED"
            if user_coordinate_verified
            else "LIMITED"
            if has_curated_assignments
            else "BLOCKED"
        ),
        "can_report_curated_first_shell": has_curated_assignments,
        "can_report_user_coordinate": user_coordinate_verified,
        "requires_manual_numbering_review": bool(pending_numbering),
        "must_not_claim_complete_mechanism": True,
        "must_not_claim_second_shell": True,
        "must_not_claim_experimental_activity_or_mutation_gain": True,
        "must_not_claim_unmapped_coordinates": True,
        "blocked_reasons": sorted(set(blocked_reasons)),
        "assay_required": ["manual_numbering_review"] if pending_numbering else [],
    }


def build_catalytic_mechanism_profile(
    sites: list[dict],
    protected_positions: list[int],
    *,
    coordinate_status: str = "verified",
) -> dict:
    """Build a conservative, local-data-only catalytic mechanism profile.

    Directly curated catalytic residues are first-shell assignments. The
    underlying model has no second-shell or mechanistic-step fields, so those
    fields remain explicitly unknown or role-derived rather than inferred from
    an LLM or generic structure heuristic.
    """

    assignments: list[dict] = []
    pending_numbering: list[dict] = []
    normalized_protected_set: set[int] = set()
    for value in protected_positions:
        try:
            normalized_protected_set.add(int(value))
        except (TypeError, ValueError):
            continue
    normalized_protected = sorted(normalized_protected_set)

    for site in sites:
        if not isinstance(site, dict):
            continue
        site_source = str(site.get("source") or "local_curated_annotation")
        for residue in site.get("residues", []):
            if not isinstance(residue, dict):
                continue
            try:
                position = int(residue.get("position"))
            except (TypeError, ValueError):
                continue

            raw_role = residue.get("role")
            normalized_role = _normalize_catalytic_role(raw_role)
            pdb_chain = residue.get("pdb_chain")
            pdb_residue_no = residue.get("pdb_residue_no")
            has_structure_coordinate = bool(pdb_chain and pdb_residue_no)
            structure_coordinate = (
                {
                    "coordinate_system": "pdb_author",
                    "chain_id": str(pdb_chain),
                    "position": str(pdb_residue_no),
                    "status": "stored_curated_coordinate",
                }
                if has_structure_coordinate
                else None
            )
            user_coordinate = (
                {
                    "coordinate_system": "user_sequence",
                    "position": position,
                    "status": "verified",
                    "mapping_basis": "exact_curated_sequence",
                }
                if coordinate_status == "verified"
                else {
                    "coordinate_system": "user_sequence",
                    "position": None,
                    "status": "pending_numbering" if coordinate_status == "mapping_required" else "unmapped",
                    "mapping_basis": "mapping_required_before_user_coordinate_claim",
                }
            )
            assignment = {
                "source": site_source,
                "source_coordinate": {
                    "coordinate_system": "uniprot_sequence",
                    "position": position,
                },
                "residue": residue.get("residue"),
                "raw_role": raw_role,
                "catalytic_role": normalized_role,
                "role_vocabulary_status": (
                    "normalized_from_local_annotation" if normalized_role != "unknown" else "unknown_role"
                ),
                "catalytic_shell": "first_shell",
                "shell_assignment_status": "directly_curated_residue",
                "mechanistic_step": _MECHANISTIC_STEPS_BY_ROLE[normalized_role],
                "mechanistic_step_status": (
                    "role_derived_not_explicitly_curated"
                    if normalized_role != "unknown"
                    else "unknown"
                ),
                "structure_coordinate": structure_coordinate,
                "user_coordinate": user_coordinate,
                "confidence": residue.get("confidence"),
                "protection_status": "protected",
            }
            assignments.append(assignment)

            if coordinate_status != "verified":
                pending_numbering.append(
                    {
                        "source_position": position,
                        "reason": "input_sequence_mapping_required",
                        "required_coordinate_system": "input_sequence_or_user_project",
                    }
                )
            elif structure_coordinate is None:
                pending_numbering.append(
                    {
                        "source_position": position,
                        "reason": "structure_coordinate_not_annotated",
                        "required_coordinate_system": "pdb_author_when_structure_mapping_is_needed",
                    }
                )

    first_shell_positions = sorted(
        {
            item["source_coordinate"]["position"]
            for item in assignments
            if item.get("catalytic_shell") == "first_shell"
        }
    )
    if assignments:
        status = "ready" if coordinate_status == "verified" else "pending_numbering"
    else:
        status = "guardrail_only" if normalized_protected else "unknown"

    report_contract = build_catalytic_mechanism_report_contract(
        status=status,
        coordinate_status=coordinate_status,
        assignments=assignments,
        pending_numbering=pending_numbering,
    )
    user_coordinate_status = (
        "verified"
        if coordinate_status == "verified" and assignments
        else "pending_numbering"
        if coordinate_status == "mapping_required" and assignments
        else "unavailable"
    )

    return {
        "schema_version": "catalytic_mechanism_profile_v1",
        "status": status,
        "coordinate_status": coordinate_status,
        "source_coordinate": {
            "coordinate_system": "uniprot_sequence",
            "status": "curated_per_residue" if assignments else "unavailable",
            "positions": first_shell_positions,
        },
        "user_coordinate": {
            "coordinate_system": "user_sequence",
            "status": user_coordinate_status,
            "positions": first_shell_positions if user_coordinate_status == "verified" else [],
        },
        "mechanism_names": sorted(
            {
                str(site.get("mechanism_name"))
                for site in sites
                if isinstance(site, dict) and site.get("mechanism_name")
            }
        ),
        "reaction_texts": sorted(
            {
                str(site.get("reaction_text"))
                for site in sites
                if isinstance(site, dict) and site.get("reaction_text")
            }
        ),
        "catalytic_residues": assignments,
        "first_shell_positions": first_shell_positions,
        "second_shell_positions": [],
        "second_shell_status": "unknown_not_annotated_in_local_model",
        "protected_positions": normalized_protected,
        "pending_numbering": pending_numbering,
        "evidence_level": "LOCAL_CURATED" if assignments else "GUARDRAIL_ONLY",
        "report_contract": report_contract,
        "report_boundary": (
            "First-shell assignments come only from stored curated catalytic residues. "
            "Second-shell residues, ligand/cofactor contacts, and full reaction steps are "
            "unknown unless separately imported; mechanistic_step is role-derived, not a "
            "complete curated mechanism."
        ),
    }


class AnnotationQueryService:
    """Single entry point for annotation-focused read operations."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_enzyme(self, uniprot_id: str) -> EnzymeRecord | None:
        row = await self.session.execute(
            select(EnzymeRecord).where(EnzymeRecord.uniprot_id == uniprot_id)
        )
        return row.scalar_one_or_none()

    async def get_enzyme_with_annotations(self, uniprot_id: str) -> EnzymeRecord | None:
        row = await self.session.execute(
            self._enzyme_with_annotations_query().where(EnzymeRecord.uniprot_id == uniprot_id)
        )
        return row.scalar_one_or_none()

    async def get_enzyme_by_exact_sequence_with_annotations(self, sequence: str) -> EnzymeRecord | None:
        """Resolve only exact sequence matches; similarity search belongs to BLAST/HMM tools."""
        row = await self.session.execute(
            self._enzyme_with_annotations_query().where(EnzymeRecord.sequence == sequence)
        )
        return row.scalar_one_or_none()

    @staticmethod
    def _enzyme_with_annotations_query():
        return (
            select(EnzymeRecord)
            .options(
                selectinload(EnzymeRecord.taxonomy),
                selectinload(EnzymeRecord.ec_numbers).selectinload(EnzymeECLink.ec_number),
                selectinload(EnzymeRecord.interpro_links).selectinload(EnzymeInterProLink.interpro_entry),
                selectinload(EnzymeRecord.domains).selectinload(DomainArchitecture.domain),
                selectinload(EnzymeRecord.catalytic_sites).selectinload(CatalyticSite.residues),
                selectinload(EnzymeRecord.signal_peptide_predictions),
                selectinload(EnzymeRecord.pdb_structures),
                selectinload(EnzymeRecord.alphafold_structures),
            )
        )

    async def get_protein_summary(self, uniprot_id: str) -> dict | None:
        enzyme = await self.get_enzyme_with_annotations(uniprot_id)
        if enzyme is None:
            return None

        kp_count = await self.session.scalar(
            select(func.count(KineticParameter.id)).where(KineticParameter.enzyme_id == enzyme.id)
        )
        stab_count = await self.session.scalar(
            select(func.count(StabilityRecord.id)).where(StabilityRecord.enzyme_id == enzyme.id)
        )
        evo_count = await self.session.scalar(
            select(func.count(DirectedEvolutionEntry.id)).where(DirectedEvolutionEntry.enzyme_id == enzyme.id)
        )

        annotations_payload = self.build_annotations_payload(enzyme)
        catalytic_payload = self.build_catalytic_sites_payload(enzyme)
        signal_payload = self.build_signal_peptide_payload(enzyme)

        return {
            "uniprot_id": enzyme.uniprot_id,
            "entry_name": enzyme.entry_name,
            "protein_name": enzyme.protein_name,
            "gene_name": enzyme.gene_name,
            "sequence": enzyme.sequence,
            "seq_length": enzyme.seq_length,
            "function": enzyme.function_annotation,
            "catalytic_activity": enzyme.catalytic_activity,
            "cofactors": enzyme.cofactors,
            "organism": self.taxonomy_to_dict(enzyme.taxonomy),
            "ec_numbers": [
                {"ec": link.ec_number.ec_number, "name": link.ec_number.name, "primary": link.is_primary}
                for link in enzyme.ec_numbers
                if link.ec_number is not None
            ],
            "pdb_structures": [
                {"pdb_id": s.pdb_id, "method": s.method, "resolution": s.resolution}
                for s in enzyme.pdb_structures
            ],
            "annotation_summary": {
                "interpro_annotations": annotations_payload["counts"]["interpro_annotations"],
                "catalytic_sites": catalytic_payload["count"],
                "protected_positions": catalytic_payload["protected_positions"],
                "signal_peptide": signal_payload,
            },
            "alphafold": {
                "plddt_mean": enzyme.alphafold_structures[0].plddt_mean,
                "model_url": enzyme.alphafold_structures[0].model_url,
            } if enzyme.alphafold_structures else None,
            "counts": {
                "kinetic_params": kp_count or 0,
                "stability_records": stab_count or 0,
                "evolution_entries": evo_count or 0,
                "pdb_structures": len(enzyme.pdb_structures),
                "interpro_annotations": annotations_payload["counts"]["interpro_annotations"],
                "catalytic_sites": catalytic_payload["count"],
            },
        }

    def build_annotations_payload(self, enzyme: EnzymeRecord) -> dict:
        annotations = [
            {
                "interpro_id": link.interpro_entry.interpro_id if link.interpro_entry else None,
                "name": link.interpro_entry.name if link.interpro_entry else None,
                "entry_type": link.interpro_entry.entry_type if link.interpro_entry else None,
                "source": link.interpro_entry.source_db if link.interpro_entry else None,
                "go_terms": link.interpro_entry.go_terms if link.interpro_entry else [],
                "start_pos": link.start_pos,
                "end_pos": link.end_pos,
                "score": link.score,
                "evidence": link.evidence,
            }
            for link in enzyme.interpro_links
        ]
        pfam_domains = [
            {
                "pfam_id": arch.domain.pfam_id if arch.domain else None,
                "name": arch.domain.name if arch.domain else None,
                "description": arch.domain.description if arch.domain else None,
                "start_pos": arch.start_pos,
                "end_pos": arch.end_pos,
                "evalue": arch.evalue,
            }
            for arch in enzyme.domains
        ]
        return {
            "uniprot_id": enzyme.uniprot_id,
            "annotations": annotations,
            "pfam_domains": pfam_domains,
            "counts": {
                "interpro_annotations": len(annotations),
                "pfam_domains": len(pfam_domains),
            },
        }

    def build_catalytic_sites_payload(self, enzyme: EnzymeRecord) -> dict:
        sites = []
        protected_positions = set()
        for site in enzyme.catalytic_sites:
            residues = []
            for residue in sorted(site.residues, key=lambda item: item.residue_pos):
                residues.append(
                    {
                        "position": residue.residue_pos,
                        "residue": residue.residue_aa,
                        "role": residue.role,
                        "confidence": residue.confidence,
                        "pdb_chain": residue.pdb_chain,
                        "pdb_residue_no": residue.pdb_residue_no,
                    }
                )
                if residue.residue_pos:
                    protected_positions.add(residue.residue_pos)
            sites.append(
                {
                    "source": site.source,
                    "mechanism_name": site.mechanism_name,
                    "reaction_text": site.reaction_text,
                    "evidence": site.evidence_json,
                    "residues": residues,
                }
            )

        payload = {
            "uniprot_id": enzyme.uniprot_id,
            "sites": sites,
            "protected_positions": sorted(protected_positions),
            "count": len(sites),
        }
        payload["mechanism_profile"] = build_catalytic_mechanism_profile(
            sites,
            payload["protected_positions"],
        )
        return payload

    def build_signal_peptide_payload(self, enzyme: EnzymeRecord) -> dict | None:
        if not enzyme.signal_peptide_predictions:
            return None
        prediction = sorted(
            enzyme.signal_peptide_predictions,
            key=lambda item: item.created_at,
            reverse=True,
        )[0]
        return prediction.raw_json or {
            "found": True,
            "query": {"uniprot_id": enzyme.uniprot_id, "sequence_length": enzyme.seq_length},
            "has_signal_peptide": prediction.has_signal,
            "cleavage_site": prediction.cleavage_site,
            "model": prediction.model_name,
        }

    @staticmethod
    def taxonomy_to_dict(tax: Taxonomy | None) -> dict | None:
        if tax is None:
            return None
        return {
            "taxid": tax.ncbi_taxid,
            "name": tax.scientific_name,
            "common": tax.common_name,
            "lineage": tax.lineage,
        }
