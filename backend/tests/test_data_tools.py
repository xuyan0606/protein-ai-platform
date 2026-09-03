"""White-box tests: agent data lookup tool functions."""

import pytest
from sqlalchemy import select


async def _seed_tools(session):
    from app.models.domain import (
        EnzymeRecord, Taxonomy, ECNumber, EnzymeECLink,
        KineticParameter, StabilityRecord, SubstrateCompound,
        InterProEntry, EnzymeInterProLink,
        CatalyticSite, CatalyticResidue,
        SignalPeptidePrediction,
    )
    tax = Taxonomy(ncbi_taxid=9606, scientific_name="Homo sapiens")
    session.add(tax)
    await session.flush()

    e1 = EnzymeRecord(uniprot_id="P00123", entry_name="TEST1_HUMAN", sequence="MKWVTFIS", seq_length=8, protein_name="Enzyme One", gene_name="ENO1", taxonomy_id=tax.id)
    e2 = EnzymeRecord(uniprot_id="P00456", entry_name="TEST2_HUMAN", sequence="MLLLVTAA", seq_length=8, protein_name="Enzyme Two", gene_name="ENT2", taxonomy_id=tax.id)
    session.add_all([e1, e2])
    await session.flush()

    ec = ECNumber(ec_number="2.7.7.7", name="Test kinase", level1="2")
    session.add(ec)
    await session.flush()
    session.add(EnzymeECLink(enzyme_id=e1.id, ec_id=ec.id, is_primary=True))

    kp = KineticParameter(enzyme_id=e1.id, source_db="brenda", param_type="Kcat", substrate_name="ATP", value=10.0, unit="1/s", ph=7.4, temperature_c=37.0, mutant="wild-type")
    session.add(kp)

    sr = StabilityRecord(enzyme_id=e1.id, mutation="M1A", mutation_pos=1, wild_type="M", mutant="A", ddg=0.5, dtm=1.0)
    session.add(sr)

    c1 = SubstrateCompound(pubchem_cid=5957, name="ATP", smiles="C1=NC=...", molecular_weight=507.18)
    session.add(c1)

    interpro = InterProEntry(
        interpro_id="IPR000073",
        entry_type="family",
        name="Lipase/Esterase alpha/beta hydrolase",
        source_db="interpro",
        go_terms=["GO:0016787 hydrolase activity"],
    )
    session.add(interpro)
    await session.flush()
    session.add(
        EnzymeInterProLink(
            enzyme_id=e1.id,
            interpro_entry_id=interpro.id,
            start_pos=2,
            end_pos=7,
            score=88.0,
            evidence="test_seed",
        )
    )

    site = CatalyticSite(
        enzyme_id=e1.id,
        source="test_seed",
        mechanism_name="Catalytic guardrail",
        reaction_text="Demo catalytic site",
    )
    session.add(site)
    await session.flush()
    session.add(
        CatalyticResidue(
            site_id=site.id,
            residue_pos=3,
            residue_aa="W",
            role="nucleophile",
            confidence=0.91,
        )
    )

    session.add(
        SignalPeptidePrediction(
            enzyme_id=e2.id,
            sequence_hash="6d2d262dfcb3ecc4341d904f866a63e348a7680e2516207e6500434779324730",
            has_signal=True,
            cleavage_site="L4|V",
            model_name="test_model",
            raw_json={
                "found": True,
                "query": {"uniprot_id": "P00456", "sequence_length": 8},
                "has_signal_peptide": True,
                "confidence": 0.91,
                "predicted_type": "Sec/SPI",
                "cleavage_site": "L4|V",
                "regions": {
                    "n_region": {"start": 1, "end": 5, "positive_residues": 2},
                    "h_region": {"start": 7, "end": 8, "hydrophobic_ratio": 0.8},
                    "c_region": {"start": 3, "end": 4},
                },
                "model": "test_model",
                "cache": {"hit": True, "source": "database"},
            },
        )
    )

    await session.commit()
    return {"enzyme1": e1, "enzyme2": e2, "ec": ec}


class TestLookupProtein:
    async def test_by_uniprot_id(self, session):
        from app.tools.data_lookup import lookup_protein
        await _seed_tools(session)

        result = await lookup_protein(uniprot_id="P00123", _session=session)
        assert result["found"] is True
        assert result["protein_name"] == "Enzyme One"
        assert result["gene_name"] == "ENO1"
        assert result["seq_length"] == 8
        assert len(result["ec_numbers"]) == 1

    async def test_by_gene_name(self, session):
        from app.tools.data_lookup import lookup_protein
        await _seed_tools(session)

        result = await lookup_protein(gene_name="ENO1", _session=session)
        assert result["found"] is True
        assert len(result["results"]) == 1

    async def test_by_ec_number(self, session):
        from app.tools.data_lookup import lookup_protein
        await _seed_tools(session)

        result = await lookup_protein(ec_number="2.7.7.7", _session=session)
        assert result["found"] is True
        assert result["ec_name"] == "Test kinase"
        assert result["protein_count"] >= 1

    async def test_not_found(self, session):
        from app.tools.data_lookup import lookup_protein
        result = await lookup_protein(uniprot_id="NONEXIST", _session=session)
        assert result["found"] is False

    async def test_no_args(self, session):
        from app.tools.data_lookup import lookup_protein
        result = await lookup_protein(_session=session)
        assert result["found"] is False
        assert "error" in result


class TestSearchSubstrate:
    async def test_by_name(self, session):
        from app.tools.data_lookup import search_substrate
        await _seed_tools(session)

        result = await search_substrate(query="ATP", _session=session)
        assert result["found"] is True
        assert len(result["results"]) == 1
        assert result["results"][0]["cid"] == 5957

    async def test_by_cid(self, session):
        from app.tools.data_lookup import search_substrate
        await _seed_tools(session)

        result = await search_substrate(cid=5957, _session=session)
        assert result["found"] is True
        assert result["compound"]["name"] == "ATP"

    async def test_not_found(self, session):
        from app.tools.data_lookup import search_substrate
        result = await search_substrate(query="nonexistent_xyz", _session=session)
        assert result["found"] is False


class TestGetKineticParams:
    async def test_kinetics(self, session):
        from app.tools.data_lookup import get_kinetic_params
        await _seed_tools(session)

        result = await get_kinetic_params(uniprot_id="P00123", _session=session)
        assert result["found"] is True
        assert result["total_records"] == 1
        assert result["parameters"][0]["type"] == "Kcat"
        assert result["parameters"][0]["value"] == 10.0
        assert "Kcat" in result["summary"]

    async def test_kinetics_filter(self, session):
        from app.tools.data_lookup import get_kinetic_params
        await _seed_tools(session)

        result = await get_kinetic_params(uniprot_id="P00123", param_type="Km", _session=session)
        assert result["found"] is True
        assert result["total_records"] == 0  # no Km, only Kcat

    async def test_nonexistent_protein(self, session):
        from app.tools.data_lookup import get_kinetic_params
        result = await get_kinetic_params(uniprot_id="NONEXIST", _session=session)
        assert result["found"] is False


class TestGetStabilityData:
    async def test_stability(self, session):
        from app.tools.data_lookup import get_stability_data
        await _seed_tools(session)

        result = await get_stability_data(uniprot_id="P00123", _session=session)
        assert result["found"] is True
        assert result["total_records"] == 1
        assert result["records"][0]["mutation"] == "M1A"
        assert result["records"][0]["ddg"] == 0.5


class TestToolRegistryIntegration:
    async def test_tools_registered(self):
        from app.tools.registry import ToolRegistry
        ToolRegistry.discover()

        assert ToolRegistry.get_tool("annotation_bundle") is not None
        assert ToolRegistry.get_tool("lookup_protein") is not None
        assert ToolRegistry.get_tool("search_substrate") is not None
        assert ToolRegistry.get_tool("get_kinetic_params") is not None
        assert ToolRegistry.get_tool("get_stability_data") is not None
        assert ToolRegistry.get_tool("wt_baseline_registry") is not None
        assert ToolRegistry.get_tool("list_ec_proteins") is not None

        tool = ToolRegistry.get_tool("lookup_protein")
        assert tool.category == "data"
        assert "uniprot_id" in str(tool.parameters)


class TestAnnotationTools:
    async def test_annotation_bundle(self, session):
        from app.tools.annotation_bundle import annotation_bundle
        await _seed_tools(session)

        result = await annotation_bundle(uniprot_id="P00123", _session=session)
        assert result["found"] is True
        assert result["capability_status"] == "evidence_synthesis"
        assert result["evidence_level"] == "ANNOTATION_SYNTHESIS"
        assert "live_query_executed=true" in result["report_boundary"]
        assert result["interpro"]["summary"]["curated_interpro_count"] == 1
        assert result["catalytic_sites"]["protected_positions"] == [3]

    async def test_interpro_annotation_curated(self, session):
        from app.tools.interpro_annotation import interpro_annotation
        await _seed_tools(session)

        result = await interpro_annotation(uniprot_id="P00123", _session=session)
        assert result["found"] is True
        assert result["summary"]["curated_interpro_count"] == 1
        assert result["annotations"][0]["interpro_id"] == "IPR000073"

    async def test_catalytic_site_lookup_curated(self, session):
        from app.tools.catalytic_site_lookup import catalytic_site_lookup
        await _seed_tools(session)

        result = await catalytic_site_lookup(uniprot_id="P00123", _session=session)
        assert result["found"] is True
        assert result["protected_positions"] == [3]
        assert result["curated_sites"][0]["residues"][0]["position"] == 3
        assert result["mechanism_profile"]["status"] == "ready"
        assert result["mechanism_profile"]["first_shell_positions"] == [3]
        assert result["mechanism_profile"]["catalytic_residues"][0]["catalytic_role"] == "nucleophile"

    async def test_signal_peptide_predict_cache_hit(self, session):
        from app.tools.signal_peptide_predict import signal_peptide_predict
        await _seed_tools(session)

        result = await signal_peptide_predict(uniprot_id="P00456", _session=session)
        assert result["found"] is True
        assert result["has_signal_peptide"] is True
        assert result["cache"]["hit"] is True
