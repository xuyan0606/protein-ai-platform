"""Tests for the local exact-EC reaction profile service."""

from __future__ import annotations

from app.models.domain import ECNumber, EnzymeECLink, EnzymeRecord, ReactionEquation
from app.services.reaction_profile import ReactionProfileService


async def _seed_reaction_profile(session):
    enzyme = EnzymeRecord(
        uniprot_id="RXNTEST1",
        entry_name="RXNTEST1_TEST",
        sequence="MSTNPKPQRKTK",
        seq_length=12,
        protein_name="Reaction Profile Test Enzyme",
    )
    session.add(enzyme)
    await session.flush()
    ec = ECNumber(ec_number="3.2.1.4", name="Test glycosidase")
    session.add(ec)
    await session.flush()
    session.add(EnzymeECLink(enzyme_id=enzyme.id, ec_id=ec.id, is_primary=True))
    session.add_all(
        [
            ReactionEquation(
                rhea_id=1001,
                equation="matched substrate = matched product",
                reactants=["CHEBI:1"],
                products=["CHEBI:2"],
                ec_numbers=["3.2.1.4"],
            ),
            ReactionEquation(
                rhea_id=1002,
                equation="nearby but not exact substrate = product",
                ec_numbers=["3.2.1.99"],
            ),
            ReactionEquation(
                rhea_id=1003,
                equation="malformed EC metadata = product",
                ec_numbers=[3.2, None, ""],
            ),
        ]
    )
    await session.commit()


async def test_reaction_profile_uses_only_exact_local_ec_matches(session):
    await _seed_reaction_profile(session)

    payload = await ReactionProfileService(session).resolve("RXNTEST1")

    assert payload is not None
    assert payload["status"] == "ready"
    assert [item["rhea_id"] for item in payload["reaction_candidates"]] == [1001]
    assert payload["reaction_candidates"][0]["matched_ec_numbers"] == ["3.2.1.4"]
    assert payload["claim_context"]["reaction_claim_status"] == "SUPPORTED"
    assert payload["claim_context"]["substrate_scope_status"] == "SUPPORTED"
    assert payload["claim_context"]["blocked_activity_claims"] == []
    assert payload["report_contract"]["must_not_claim_activity_or_substrate_optimization_without_reaction"] is True
    assert payload["evidence_source"]["live_query_executed"] is False
    assert "Free-text activity" in payload["claim_boundary"]


async def test_reaction_profile_blocks_substrate_scope_when_one_reaction_side_is_missing(session):
    enzyme = EnzymeRecord(
        uniprot_id="RXNPART2",
        entry_name="RXNPART2_TEST",
        sequence="MSTNPKPQRKTA",
        seq_length=12,
        protein_name="Partial Reaction Side Test",
    )
    session.add(enzyme)
    await session.flush()
    ec = ECNumber(ec_number="3.2.1.4", name="Test glycosidase")
    session.add(ec)
    await session.flush()
    session.add(EnzymeECLink(enzyme_id=enzyme.id, ec_id=ec.id, is_primary=True))
    session.add(
        ReactionEquation(
            rhea_id=1004,
            equation="partial reaction metadata",
            reactants=["CHEBI:3"],
            ec_numbers=["3.2.1.4"],
        )
    )
    await session.commit()

    payload = await ReactionProfileService(session).resolve("RXNPART2")

    assert payload is not None
    assert payload["claim_context"]["reaction_claim_status"] == "SUPPORTED"
    assert payload["claim_context"]["substrate_scope_status"] == "MISSING"
    assert payload["claim_context"]["blocked_activity_claims"] == ["substrate_scope_optimization"]
    assert payload["reaction_candidates"][0]["reactants"] == ["CHEBI:3"]
    assert payload["reaction_candidates"][0]["products"] == []


async def test_reaction_profile_is_partial_when_no_exact_local_match(session):
    enzyme = EnzymeRecord(
        uniprot_id="RXNPART1",
        entry_name="RXNPART1_TEST",
        sequence="MSTNPKPQRKTA",
        seq_length=12,
        protein_name="Partial Reaction Profile Test",
        catalytic_activity="A local textual activity annotation",
    )
    session.add(enzyme)
    await session.flush()
    ec = ECNumber(ec_number="2.7.7.7", name="No local Rhea match")
    session.add(ec)
    await session.flush()
    session.add(EnzymeECLink(enzyme_id=enzyme.id, ec_id=ec.id, is_primary=True))
    await session.commit()

    payload = await ReactionProfileService(session).resolve("RXNPART1")

    assert payload is not None
    assert payload["status"] == "partial"
    assert payload["reaction_candidates"] == []
    assert "no_exact_local_rhea_ec_match" in payload["gaps"]
    assert payload["claim_context"]["reaction_claim_status"] == "MISSING"
    assert payload["claim_context"]["blocked_activity_claims"] == [
        "specific_activity_improvement",
        "substrate_scope_optimization",
        "reaction_direction_optimization",
    ]
    assert payload["report_contract"]["assay_required"] == ["reaction_identity_confirmation"]
