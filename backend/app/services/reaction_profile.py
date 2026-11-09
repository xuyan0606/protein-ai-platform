"""Read-only local reaction profile aggregation for enzyme engineering."""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.domain import ReactionEquation
from app.services.annotation_query_service import AnnotationQueryService
from app.services.evidence_source_status import evidence_source_status


def _normalized_ec_numbers(value: object) -> set[str]:
    if not isinstance(value, list):
        return set()
    return {
        item.strip()
        for item in value
        if isinstance(item, str) and item.strip()
    }


def _build_claim_context(
    *,
    status: str,
    reaction_candidates: list[dict[str, Any]],
    gaps: list[str],
) -> dict[str, Any]:
    reaction_supported = status == "ready" and bool(reaction_candidates)
    substrate_supported = any(
        candidate.get("reactants") and candidate.get("products")
        for candidate in reaction_candidates
    )
    blocked_activity_claims: list[str] = []
    assay_required: list[str] = []
    if not reaction_supported:
        blocked_activity_claims.extend(
            [
                "specific_activity_improvement",
                "substrate_scope_optimization",
                "reaction_direction_optimization",
            ]
        )
        assay_required.append("reaction_identity_confirmation")
    if reaction_supported and not substrate_supported:
        blocked_activity_claims.append("substrate_scope_optimization")
        assay_required.append("substrate_scope_assay_or_curated_reactant_product_mapping")

    return {
        "requires_reaction_profile": True,
        "reaction_claim_status": "SUPPORTED" if reaction_supported else "MISSING",
        "substrate_scope_status": "SUPPORTED" if substrate_supported else "MISSING",
        "blocked_activity_claims": blocked_activity_claims,
        "assay_required": assay_required,
        "gaps": gaps,
    }


class ReactionProfileService:
    """Build a conservative profile from already-imported local Rhea rows."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.annotations = AnnotationQueryService(session)

    async def resolve(self, uniprot_id: str) -> dict[str, Any] | None:
        enzyme = await self.annotations.get_enzyme_with_annotations(uniprot_id)
        if enzyme is None:
            return None

        protein_ecs = {
            link.ec_number.ec_number.strip()
            for link in enzyme.ec_numbers
            if link.ec_number is not None and link.ec_number.ec_number
        }
        reaction_candidates: list[dict[str, Any]] = []
        if protein_ecs:
            rows = await self.session.execute(
                select(ReactionEquation).where(ReactionEquation.ec_numbers.is_not(None))
            )
            for reaction in rows.scalars():
                matched_ec_numbers = sorted(protein_ecs & _normalized_ec_numbers(reaction.ec_numbers))
                if not matched_ec_numbers:
                    continue
                reaction_candidates.append(
                    {
                        "rhea_id": reaction.rhea_id,
                        "equation": reaction.equation,
                        "reaction_side": reaction.reaction_side,
                        "reactants": reaction.reactants or [],
                        "products": reaction.products or [],
                        "cofactors": reaction.cofactors or [],
                        "matched_ec_numbers": matched_ec_numbers,
                        "match_basis": "exact_local_ec_intersection",
                        "is_balanced": reaction.is_balanced,
                        "is_transport": reaction.is_transport,
                    }
                )
        reaction_candidates.sort(key=lambda item: (item["rhea_id"], item["equation"] or ""))

        has_local_function_evidence = bool(
            protein_ecs or enzyme.catalytic_activity or enzyme.catalytic_sites
        )
        if reaction_candidates:
            status = "ready"
        elif has_local_function_evidence:
            status = "partial"
        else:
            status = "blocked"

        gaps: list[str] = []
        if not protein_ecs:
            gaps.append("missing_local_ec_assignment")
        if protein_ecs and not reaction_candidates:
            gaps.append("no_exact_local_rhea_ec_match")
        if not has_local_function_evidence:
            gaps.append("missing_local_function_and_catalytic_evidence")

        claim_context = _build_claim_context(
            status=status,
            reaction_candidates=reaction_candidates,
            gaps=gaps,
        )

        return {
            "schema_version": "reaction_profile_v1",
            "found": True,
            "status": status,
            "query": {
                "uniprot_id": enzyme.uniprot_id,
                "local_only": True,
            },
            "evidence_source": evidence_source_status(
                source="reaction_profile",
                status="degraded",
                mode="local_database_exact_ec_aggregation",
                live_query_executed=False,
                version=enzyme.source_version,
                reason="No live Rhea, UniProt, or ChEBI query is executed in this path.",
                details={
                    "protein_ec_count": len(protein_ecs),
                    "exact_local_reaction_count": len(reaction_candidates),
                },
            ),
            "protein": {
                "uniprot_id": enzyme.uniprot_id,
                "protein_name": enzyme.protein_name,
                "catalytic_activity": enzyme.catalytic_activity,
                "cofactors": enzyme.cofactors or [],
                "ec_numbers": [
                    {
                        "ec": link.ec_number.ec_number,
                        "name": link.ec_number.name,
                        "primary": link.is_primary,
                    }
                    for link in enzyme.ec_numbers
                    if link.ec_number is not None
                ],
            },
            "reaction_candidates": reaction_candidates,
            "annotations": {
                "interpro": self.annotations.build_annotations_payload(enzyme),
                "catalytic_sites": self.annotations.build_catalytic_sites_payload(enzyme),
                "signal_peptide": self.annotations.build_signal_peptide_payload(enzyme),
            },
            "gaps": gaps,
            "claim_context": claim_context,
            "report_contract": {
                "show_reaction_profile": True,
                "must_not_claim_activity_or_substrate_optimization_without_reaction": True,
                "must_label_local_exact_ec_mapping": True,
                "assay_required": claim_context["assay_required"],
            },
            "claim_boundary": (
                "Only exact EC intersections against locally imported ReactionEquation rows are "
                "reported. Free-text activity, substrate names, EC prefixes, and family similarity "
                "never create a reaction association. No live query or database write is performed."
            ),
        }
