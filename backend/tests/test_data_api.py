"""Black-box tests: data API endpoints via HTTP client."""

import pytest
from httpx import AsyncClient
from sqlalchemy import select


async def _seed(session) -> dict:
    """Seed minimal test data and return IDs."""
    from app.models.domain import (
        EnzymeRecord, Taxonomy, ECNumber, EnzymeECLink,
        KineticParameter, StabilityRecord, SubstrateCompound,
        ReactionEquation, DirectedEvolutionEntry, DatabaseCrossRef, KVStore,
    )
    tax = Taxonomy(ncbi_taxid=9606, scientific_name="Homo sapiens")
    session.add(tax)
    await session.flush()

    enzyme = EnzymeRecord(
        uniprot_id="P00001", entry_name="TEST_HUMAN",
        sequence="MKWVTFISLL", seq_length=10,
        protein_name="Test Enzyme Alpha", gene_name="TSTA",
        function_annotation="Catalyzes test reactions",
        catalytic_activity="ATP + H2O = ADP + phosphate",
        taxonomy_id=tax.id, is_reviewed=True,
    )
    session.add(enzyme)
    await session.flush()

    ec = ECNumber(ec_number="1.1.1.99", name="Test oxidoreductase", level1="1", level2="1.1", level3="1.1.1")
    session.add(ec)
    await session.flush()
    session.add(EnzymeECLink(enzyme_id=enzyme.id, ec_id=ec.id, is_primary=True))

    kp = KineticParameter(enzyme_id=enzyme.id, source_db="brenda", param_type="Kcat", substrate_name="test_substrate", value=3.5, unit="1/s", ph=7.0)
    session.add(kp)

    sr = StabilityRecord(enzyme_id=enzyme.id, mutation="A3G", mutation_pos=3, wild_type="A", mutant="G", ddg=-1.2)
    session.add(sr)

    c = SubstrateCompound(pubchem_cid=99999, name="test_substrate", smiles="CCO", molecular_weight=46.07)
    session.add(c)

    rxn = ReactionEquation(rhea_id=99999, equation="test_substrate = test_product", reactants=[{"name": "test_substrate"}], products=[{"name": "test_product"}])
    session.add(rxn)

    evo = DirectedEvolutionEntry(enzyme_id=enzyme.id, mutagenesis_method="error-prone PCR", rounds=2, fold_improvement=12.0)
    session.add(evo)

    xref = DatabaseCrossRef(enzyme_id=enzyme.id, source_db="pdb", source_id="1TST")
    session.add(xref)

    kv = KVStore(key="ingest:uniprot:hash", value="abc123")
    session.add(kv)

    await session.commit()
    return {"enzyme_id": enzyme.id, "ec_id": ec.id}


class TestSearchEndpoint:
    async def test_search_protein(self, client: AsyncClient, session):
        await _seed(session)

        resp = await client.get("/api/data/search?q=Test Enzyme")
        assert resp.status_code == 200
        data = resp.json()
        assert data["query"] == "Test Enzyme"
        assert len(data["results"]["proteins"]) >= 1
        assert data["results"]["proteins"][0]["uniprot_id"] == "P00001"

    async def test_search_substrate(self, client: AsyncClient, session):
        await _seed(session)
        resp = await client.get("/api/data/search?q=test_substrate&category=substrate")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["results"]["substrates"]) >= 1

    async def test_search_empty(self, client: AsyncClient, session):
        resp = await client.get("/api/data/search?q=xyznonexistent999")
        assert resp.status_code == 200
        data = resp.json()
        assert data["results"]["proteins"] == []
        assert data["results"]["substrates"] == []

    async def test_search_missing_query(self, client: AsyncClient, session):
        resp = await client.get("/api/data/search")
        assert resp.status_code == 422  # validation error


class TestProteinEndpoint:
    async def test_get_protein_detail(self, client: AsyncClient, session):
        await _seed(session)

        resp = await client.get("/api/data/protein/P00001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["uniprot_id"] == "P00001"
        assert data["protein_name"] == "Test Enzyme Alpha"
        assert data["gene_name"] == "TSTA"
        assert data["seq_length"] == 10
        assert data["organism"]["taxid"] == 9606
        assert len(data["ec_numbers"]) >= 1
        assert data["counts"]["kinetic_params"] == 1
        assert data["counts"]["stability_records"] == 1

    async def test_protein_not_found(self, client: AsyncClient, session):
        resp = await client.get("/api/data/protein/NONEXIST")
        assert resp.status_code == 404

    async def test_protein_kinetics(self, client: AsyncClient, session):
        await _seed(session)

        resp = await client.get("/api/data/protein/P00001/kinetics")
        assert resp.status_code == 200
        data = resp.json()
        assert data["uniprot_id"] == "P00001"
        assert len(data["parameters"]) == 1
        assert data["parameters"][0]["type"] == "Kcat"
        assert data["parameters"][0]["value"] == 3.5

    async def test_protein_stability(self, client: AsyncClient, session):
        await _seed(session)

        resp = await client.get("/api/data/protein/P00001/stability")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["records"]) == 1
        assert data["records"][0]["ddg"] == -1.2

    async def test_protein_evolution(self, client: AsyncClient, session):
        await _seed(session)

        resp = await client.get("/api/data/protein/P00001/evolution")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["experiments"]) == 1
        assert data["experiments"][0]["fold_improvement"] == 12.0


class TestECEndpoint:
    async def test_get_ec(self, client: AsyncClient, session):
        await _seed(session)

        resp = await client.get("/api/data/ec/1.1.1.99")
        assert resp.status_code == 200
        data = resp.json()
        assert data["ec_number"] == "1.1.1.99"
        assert data["protein_count"] >= 1

    async def test_ec_not_found(self, client: AsyncClient, session):
        resp = await client.get("/api/data/ec/9.9.9.99")
        assert resp.status_code == 404


class TestSubstrateEndpoint:
    async def test_search_by_name(self, client: AsyncClient, session):
        await _seed(session)

        resp = await client.get("/api/data/substrate/test_substrate")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["results"]) >= 1
        assert data["results"][0]["name"] == "test_substrate"

    async def test_search_by_cid(self, client: AsyncClient, session):
        await _seed(session)

        resp = await client.get("/api/data/substrate/99999")
        assert resp.status_code == 200
        data = resp.json()
        assert data["cid"] == 99999


class TestReactionEndpoint:
    async def test_get_reaction(self, client: AsyncClient, session):
        await _seed(session)

        resp = await client.get("/api/data/reaction/99999")
        assert resp.status_code == 200
        data = resp.json()
        assert data["rhea_id"] == 99999

    async def test_reaction_not_found(self, client: AsyncClient, session):
        resp = await client.get("/api/data/reaction/1")
        assert resp.status_code == 404


class TestStatsEndpoint:
    async def test_stats(self, client: AsyncClient, session):
        await _seed(session)

        resp = await client.get("/api/data/stats")
        assert resp.status_code == 200
        data = resp.json()

        counts = data["counts"]
        assert counts["enzyme_records"] >= 1
        assert counts["kinetic_parameters"] >= 1
        assert counts["stability_records"] >= 1
        assert counts["substrate_compounds"] >= 1
        assert counts["reaction_equations"] >= 1
        assert counts["directed_evolution_entries"] >= 1

        assert "ingest:uniprot:hash" in data["ingestion_hashes"]
