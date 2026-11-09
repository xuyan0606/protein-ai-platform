"""Tests for the shared annotation query service."""

from sqlalchemy import select


async def _seed(session):
    from app.models.domain import (
        CatalyticResidue,
        CatalyticSite,
        DomainArchitecture,
        ECNumber,
        EnzymeECLink,
        EnzymeInterProLink,
        EnzymeRecord,
        InterProEntry,
        PfamDomain,
        SignalPeptidePrediction,
        Taxonomy,
    )

    tax = Taxonomy(ncbi_taxid=562, scientific_name="Escherichia coli")
    session.add(tax)
    await session.flush()

    enzyme = EnzymeRecord(
        uniprot_id="QTEST1",
        entry_name="QTEST1_ECOLI",
        sequence="MKKRLFALALALALAGCAQAASAPVAVDNGTQATVTVEGQ",
        seq_length=41,
        protein_name="Query Service Demo Enzyme",
        gene_name="qsvc",
        taxonomy_id=tax.id,
        function_annotation="Demo annotation service target",
    )
    session.add(enzyme)
    await session.flush()

    ec = ECNumber(ec_number="3.1.1.3", name="Triacylglycerol lipase", level1="3")
    session.add(ec)
    await session.flush()
    session.add(EnzymeECLink(enzyme_id=enzyme.id, ec_id=ec.id, is_primary=True))

    pfam = PfamDomain(pfam_id="PF00561", name="Abhydrolase_1", description="Alpha/beta hydrolase fold")
    session.add(pfam)
    await session.flush()
    session.add(DomainArchitecture(enzyme_id=enzyme.id, domain_id=pfam.id, start_pos=5, end_pos=39, evalue=1e-20))

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
            enzyme_id=enzyme.id,
            interpro_entry_id=interpro.id,
            start_pos=5,
            end_pos=39,
            score=91.2,
            evidence="service_test",
        )
    )

    site = CatalyticSite(
        enzyme_id=enzyme.id,
        source="service_test",
        mechanism_name="Demo catalytic center",
        reaction_text="Hydrolysis demo",
    )
    session.add(site)
    await session.flush()
    session.add(
        CatalyticResidue(
            site_id=site.id,
            residue_pos=17,
            residue_aa="S",
            role="nucleophile",
            confidence=0.94,
        )
    )

    session.add(
        SignalPeptidePrediction(
            enzyme_id=enzyme.id,
            sequence_hash="service_hash",
            has_signal=True,
            cleavage_site="C17|A",
            model_name="service_seed",
            raw_json={
                "found": True,
                "query": {"uniprot_id": "QTEST1", "sequence_length": 41},
                "has_signal_peptide": True,
                "confidence": 0.92,
                "predicted_type": "Sec/SPI",
                "cleavage_site": "C17|A",
                "regions": {
                    "n_region": {"start": 1, "end": 5, "positive_residues": 3},
                    "h_region": {"start": 7, "end": 24, "hydrophobic_ratio": 0.88},
                    "c_region": {"start": 13, "end": 17},
                },
                "model": "service_seed",
                "cache": {"hit": True, "source": "database"},
            },
        )
    )
    await session.commit()


class TestAnnotationQueryService:
    async def test_get_enzyme_with_annotations(self, session):
        from app.services.annotation_query_service import AnnotationQueryService

        await _seed(session)
        service = AnnotationQueryService(session)
        enzyme = await service.get_enzyme_with_annotations("QTEST1")

        assert enzyme is not None
        assert enzyme.uniprot_id == "QTEST1"
        assert len(enzyme.interpro_links) == 1
        assert len(enzyme.catalytic_sites) == 1

    async def test_build_payloads(self, session):
        from app.services.annotation_query_service import AnnotationQueryService

        await _seed(session)
        service = AnnotationQueryService(session)
        enzyme = await service.get_enzyme_with_annotations("QTEST1")
        assert enzyme is not None

        annotations = service.build_annotations_payload(enzyme)
        catalytic = service.build_catalytic_sites_payload(enzyme)
        signal = service.build_signal_peptide_payload(enzyme)

        assert annotations["counts"]["interpro_annotations"] == 1
        assert annotations["pfam_domains"][0]["pfam_id"] == "PF00561"
        assert catalytic["protected_positions"] == [17]
        profile = catalytic["mechanism_profile"]
        assert profile["source_coordinate"]["positions"] == [17]
        assert profile["user_coordinate"]["status"] == "verified"
        assert profile["user_coordinate"]["positions"] == [17]
        residue = profile["catalytic_residues"][0]
        assert residue["source_coordinate"]["position"] == 17
        assert residue["user_coordinate"]["position"] == 17
        assert residue["user_coordinate"]["status"] == "verified"
        assert profile["report_contract"]["claim_status"] == "SUPPORTED"
        assert profile["report_contract"]["can_report_user_coordinate"] is True
        assert profile["report_contract"]["must_not_claim_complete_mechanism"] is True
        assert profile["report_contract"]["must_not_claim_second_shell"] is True
        assert signal is not None
        assert signal["has_signal_peptide"] is True

    async def test_get_protein_summary(self, session):
        from app.services.annotation_query_service import AnnotationQueryService

        await _seed(session)
        service = AnnotationQueryService(session)
        payload = await service.get_protein_summary("QTEST1")

        assert payload is not None
        assert payload["uniprot_id"] == "QTEST1"
        assert payload["counts"]["interpro_annotations"] == 1
        assert payload["counts"]["catalytic_sites"] == 1
        assert payload["annotation_summary"]["protected_positions"] == [17]
