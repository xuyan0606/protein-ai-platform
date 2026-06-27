"""White-box tests: agent data lookup tool functions."""

import pytest
from sqlalchemy import select


async def _seed_tools(session):
    from app.models.domain import (
        EnzymeRecord, Taxonomy, ECNumber, EnzymeECLink,
        KineticParameter, StabilityRecord, SubstrateCompound,
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

        assert ToolRegistry.get_tool("lookup_protein") is not None
        assert ToolRegistry.get_tool("search_substrate") is not None
        assert ToolRegistry.get_tool("get_kinetic_params") is not None
        assert ToolRegistry.get_tool("get_stability_data") is not None
        assert ToolRegistry.get_tool("list_ec_proteins") is not None

        tool = ToolRegistry.get_tool("lookup_protein")
        assert tool.category == "data"
        assert "uniprot_id" in str(tool.parameters)
