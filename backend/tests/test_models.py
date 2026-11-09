"""White-box tests: domain model creation, relationships, constraints."""

import pytest
from sqlalchemy import select


class TestEnzymeRecord:
    async def test_create_minimal(self, session):
        from app.models.domain import EnzymeRecord
        enzyme = EnzymeRecord(uniprot_id="P12345", sequence="MKWVTF", seq_length=6)
        session.add(enzyme)
        await session.commit()

        row = await session.execute(select(EnzymeRecord).where(EnzymeRecord.uniprot_id == "P12345"))
        e = row.scalar()
        assert e is not None
        assert e.seq_length == 6
        assert e.is_reviewed is False
        assert e.source_db == "uniprot"

    async def test_unique_uniprot_id(self, session):
        from app.models.domain import EnzymeRecord
        e1 = EnzymeRecord(uniprot_id="P00001", sequence="AAAA", seq_length=4)
        e2 = EnzymeRecord(uniprot_id="P00001", sequence="BBBB", seq_length=4)
        session.add_all([e1, e2])
        with pytest.raises(Exception):
            await session.commit()


class TestTaxonomy:
    async def test_create_and_link(self, session):
        from app.models.domain import Taxonomy, EnzymeRecord
        tax = Taxonomy(ncbi_taxid=9606, scientific_name="Homo sapiens", lineage="Eukaryota; Metazoa; Chordata")
        session.add(tax)
        await session.flush()

        enzyme = EnzymeRecord(uniprot_id="P00002", sequence="MKWVTF", seq_length=6, taxonomy_id=tax.id)
        session.add(enzyme)
        await session.commit()

        row = await session.execute(
            select(EnzymeRecord).where(EnzymeRecord.uniprot_id == "P00002")
        )
        e = row.scalar()
        assert e.taxonomy_id == tax.id


class TestECNumbers:
    async def test_create_ec_and_link(self, session):
        from app.models.domain import ECNumber, EnzymeECLink, EnzymeRecord
        ec = ECNumber(ec_number="1.1.1.1", name="Alcohol dehydrogenase", level1="1", level2="1.1", level3="1.1.1")
        session.add(ec)
        await session.flush()

        enzyme = EnzymeRecord(uniprot_id="P00325", sequence="MSTA...", seq_length=374)
        session.add(enzyme)
        await session.flush()

        link = EnzymeECLink(enzyme_id=enzyme.id, ec_id=ec.id, is_primary=True)
        session.add(link)
        await session.commit()

        row = await session.execute(
            select(EnzymeECLink).where(EnzymeECLink.enzyme_id == enzyme.id)
        )
        assert row.scalar() is not None


class TestKineticParameter:
    async def test_create_kinetics(self, session):
        from app.models.domain import EnzymeRecord, KineticParameter
        enzyme = EnzymeRecord(uniprot_id="P00492", sequence="MKT...", seq_length=200)
        session.add(enzyme)
        await session.flush()

        kp = KineticParameter(
            enzyme_id=enzyme.id, source_db="brenda", param_type="Kcat",
            substrate_name="hypoxanthine", value=2.5, unit="1/s",
            ph=7.4, temperature_c=37.0, mutant="wild-type",
        )
        session.add(kp)
        await session.commit()

        row = await session.execute(
            select(KineticParameter).where(KineticParameter.enzyme_id == enzyme.id)
        )
        kps = row.scalars().all()
        assert len(kps) == 1
        assert kps[0].param_type == "Kcat"
        assert kps[0].value == 2.5


class TestStabilityRecord:
    async def test_create_stability(self, session):
        from app.models.domain import EnzymeRecord, StabilityRecord
        enzyme = EnzymeRecord(uniprot_id="P00698", sequence="ML...", seq_length=150)
        session.add(enzyme)
        await session.flush()

        sr = StabilityRecord(
            enzyme_id=enzyme.id, mutation="A23G", mutation_pos=23,
            wild_type="A", mutant="G", ddg=-1.5, dtm=-2.3,
            ph=7.0, temperature_c=25.0, method="DSC",
        )
        session.add(sr)
        await session.commit()

        row = await session.execute(
            select(StabilityRecord).where(StabilityRecord.enzyme_id == enzyme.id)
        )
        recs = row.scalars().all()
        assert len(recs) == 1
        assert recs[0].ddg == -1.5


class TestSubstrateCompound:
    async def test_create_compound(self, session):
        from app.models.domain import SubstrateCompound
        c = SubstrateCompound(pubchem_cid=5957, name="ATP", smiles="C1=NC=...",
                              molecular_formula="C10H16N5O13P3", molecular_weight=507.18,
                              xlogp=-1.2, tpsa=279.1)
        session.add(c)
        await session.commit()

        row = await session.execute(select(SubstrateCompound).where(SubstrateCompound.pubchem_cid == 5957))
        assert row.scalar() is not None


class TestReactionEquation:
    async def test_create_reaction(self, session):
        from app.models.domain import ReactionEquation
        rxn = ReactionEquation(rhea_id=10001, equation="ATP + H2O = ADP + phosphate",
                               reactants=[{"name": "ATP"}], products=[{"name": "ADP"}],
                               ec_numbers=["1.1.1.1"], is_balanced=True)
        session.add(rxn)
        await session.commit()

        row = await session.execute(select(ReactionEquation).where(ReactionEquation.rhea_id == 10001))
        assert row.scalar().equation == "ATP + H2O = ADP + phosphate"


class TestKVStore:
    async def test_kv_upsert(self, session):
        from app.models.domain import KVStore
        kv = KVStore(key="test:key", value="hello")
        session.add(kv)
        await session.commit()

        row = await session.execute(select(KVStore).where(KVStore.key == "test:key"))
        assert row.scalar().value == "hello"

        # Update
        kv2 = KVStore(key="test:key", value="world")
        await session.merge(kv2)
        await session.commit()

        row = await session.execute(select(KVStore).where(KVStore.key == "test:key"))
        assert row.scalar().value == "world"


class TestRelationships:
    async def test_full_enzyme_graph(self, session):
        """Build a complete enzyme entity graph and verify all relationships."""
        from app.models.domain import (
            Taxonomy, EnzymeRecord, ECNumber, EnzymeECLink,
            PDBStructure, KineticParameter, StabilityRecord,
            DirectedEvolutionEntry, DatabaseCrossRef,
        )

        # Taxonomy
        tax = Taxonomy(ncbi_taxid=9606, scientific_name="Homo sapiens")
        session.add(tax)
        await session.flush()

        # Enzyme
        enzyme = EnzymeRecord(
            uniprot_id="P99999", sequence="MKWVTFISLLFLFSSAYS", seq_length=20,
            protein_name="Test Enzyme", gene_name="TEST", taxonomy_id=tax.id,
        )
        session.add(enzyme)
        await session.flush()

        # EC number
        ec = ECNumber(ec_number="3.2.1.1", name="Alpha-amylase", level1="3")
        session.add(ec)
        await session.flush()
        session.add(EnzymeECLink(enzyme_id=enzyme.id, ec_id=ec.id, is_primary=True))

        # PDB structure
        pdb = PDBStructure(pdb_id="1ABC", enzyme_id=enzyme.id, method="X-ray", resolution=2.0)
        session.add(pdb)

        # Kinetics
        kp = KineticParameter(enzyme_id=enzyme.id, source_db="brenda", param_type="Km", value=0.5, unit="mM")
        session.add(kp)

        # Stability
        sr = StabilityRecord(enzyme_id=enzyme.id, mutation="F3A", mutation_pos=3, wild_type="F", mutant="A", ddg=1.2)
        session.add(sr)

        # Evolution
        evo = DirectedEvolutionEntry(
            enzyme_id=enzyme.id, mutagenesis_method="error-prone PCR",
            rounds=3, fold_improvement=15.0, improvement_metric="Kcat/Km",
        )
        session.add(evo)

        # Cross-ref
        xref = DatabaseCrossRef(enzyme_id=enzyme.id, source_db="pdb", source_id="1ABC")
        session.add(xref)

        await session.commit()

        # Verify all
        from sqlalchemy.orm import selectinload
        row = await session.execute(
            select(EnzymeRecord)
            .options(
                selectinload(EnzymeRecord.taxonomy),
                selectinload(EnzymeRecord.ec_numbers),
                selectinload(EnzymeRecord.pdb_structures),
                selectinload(EnzymeRecord.kinetic_params),
                selectinload(EnzymeRecord.stability_records),
                selectinload(EnzymeRecord.evolution_entries),
                selectinload(EnzymeRecord.xrefs),
            )
            .where(EnzymeRecord.uniprot_id == "P99999")
        )
        e = row.scalar()
        assert e.taxonomy.scientific_name == "Homo sapiens"
        assert len(e.ec_numbers) == 1
        assert len(e.pdb_structures) == 1
        assert len(e.kinetic_params) == 1
        assert len(e.stability_records) == 1
        assert len(e.evolution_entries) == 1
        assert len(e.xrefs) == 1
        assert e.kinetic_params[0].value == 0.5
        assert e.stability_records[0].ddg == 1.2
        assert e.evolution_entries[0].fold_improvement == 15.0
