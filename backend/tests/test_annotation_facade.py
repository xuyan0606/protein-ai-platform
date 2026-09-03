"""Tests for the unified annotation facade."""

import httpx


async def _seed(session):
    from app.models.domain import (
        CatalyticResidue,
        CatalyticSite,
        DomainArchitecture,
        EnzymeInterProLink,
        EnzymeRecord,
        InterProEntry,
        PfamDomain,
        SignalPeptidePrediction,
        Taxonomy,
    )

    tax = Taxonomy(ncbi_taxid=1423, scientific_name="Bacillus subtilis")
    session.add(tax)
    await session.flush()

    enzyme = EnzymeRecord(
        uniprot_id="FACADE1",
        entry_name="FACADE1_BACSU",
        sequence="MKKRLFALALALALAGCAQAASAPVAVDNGTQATVTVEGQTQNNGSATWQITGGTNVGSVSGYTVNANNNQ",
        seq_length=82,
        protein_name="Facade Demo Enzyme",
        gene_name="facade1",
        taxonomy_id=tax.id,
        function_annotation="Facade annotation demo target",
    )
    session.add(enzyme)
    await session.flush()

    pfam = PfamDomain(pfam_id="PF00561", name="Abhydrolase_1")
    session.add(pfam)
    await session.flush()
    session.add(DomainArchitecture(enzyme_id=enzyme.id, domain_id=pfam.id, start_pos=8, end_pos=72, evalue=1e-12))

    interpro = InterProEntry(
        interpro_id="IPR020937",
        entry_type="site",
        name="Signal peptide",
        source_db="interpro",
        go_terms=["GO:0009306 protein secretion"],
    )
    session.add(interpro)
    await session.flush()
    session.add(
        EnzymeInterProLink(
            enzyme_id=enzyme.id,
            interpro_entry_id=interpro.id,
            start_pos=1,
            end_pos=20,
            score=85.0,
            evidence="facade_test",
        )
    )

    site = CatalyticSite(
        enzyme_id=enzyme.id,
        source="facade_test",
        mechanism_name="Facade catalytic center",
        reaction_text="Facade hydrolysis demo",
    )
    session.add(site)
    await session.flush()
    session.add(
        CatalyticResidue(
            site_id=site.id,
            residue_pos=18,
            residue_aa="S",
            role="nucleophile",
            confidence=0.91,
        )
    )

    session.add(
        SignalPeptidePrediction(
            enzyme_id=enzyme.id,
            sequence_hash="facade_seed",
            has_signal=True,
            cleavage_site="C17|A",
            model_name="facade_seed_model",
            raw_json={
                "found": True,
                "query": {"uniprot_id": "FACADE1", "sequence_length": 82},
                "has_signal_peptide": True,
                "confidence": 0.93,
                "predicted_type": "Sec/SPI",
                "cleavage_site": "C17|A",
                "regions": {
                    "n_region": {"start": 1, "end": 5, "positive_residues": 3},
                    "h_region": {"start": 7, "end": 24, "hydrophobic_ratio": 0.88},
                    "c_region": {"start": 13, "end": 17},
                },
                "model": "facade_seed_model",
                "cache": {"hit": True, "source": "database"},
            },
        )
    )
    await session.commit()


class TestAnnotationFacade:
    async def test_resolve_interpro_annotation(self, session):
        from app.services.annotation_facade import AnnotationFacade

        await _seed(session)
        facade = AnnotationFacade(session)
        payload = await facade.resolve_interpro_annotation(uniprot_id="FACADE1")

        assert payload["found"] is True
        assert payload["summary"]["curated_interpro_count"] == 1
        assert payload["summary"]["pfam_domain_count"] == 1
        assert payload["evidence_source"]["status"] == "degraded"
        assert payload["evidence_source"]["live_query_executed"] is False

    async def test_resolve_catalytic_lookup(self, session):
        from app.services.annotation_facade import AnnotationFacade

        await _seed(session)
        facade = AnnotationFacade(session)
        payload = await facade.resolve_catalytic_site_lookup(uniprot_id="FACADE1")

        assert payload["found"] is True
        assert payload["protected_positions"] == [18]
        assert payload["curated_sites"][0]["residues"][0]["role"] == "nucleophile"
        profile = payload["mechanism_profile"]
        assert profile["schema_version"] == "catalytic_mechanism_profile_v1"
        assert profile["status"] == "ready"
        assert profile["first_shell_positions"] == [18]
        assert profile["second_shell_status"] == "unknown_not_annotated_in_local_model"
        assert profile["catalytic_residues"][0]["catalytic_role"] == "nucleophile"
        assert profile["catalytic_residues"][0]["mechanistic_step"] == "nucleophilic_attack"
        assert profile["pending_numbering"][0]["reason"] == "structure_coordinate_not_annotated"
        assert profile["user_coordinate"]["status"] == "verified"
        assert profile["report_contract"]["claim_status"] == "SUPPORTED"
        assert profile["report_contract"]["requires_manual_numbering_review"] is True
        assert profile["report_contract"]["blocked_reasons"] == ["structure_coordinate_not_annotated"]
        assert payload["evidence_source"]["status"] == "degraded"
        assert payload["evidence_source"]["live_query_executed"] is False

    async def test_catalytic_lookup_requires_numbering_for_sequence_mismatch(self, session):
        from app.services.annotation_facade import AnnotationFacade

        await _seed(session)
        facade = AnnotationFacade(session)
        payload = await facade.resolve_catalytic_site_lookup(
            sequence="A" * 82,
            uniprot_id="FACADE1",
        )

        profile = payload["mechanism_profile"]
        assert profile["status"] == "pending_numbering"
        assert profile["coordinate_status"] == "mapping_required"
        assert profile["user_coordinate"]["status"] == "pending_numbering"
        assert profile["user_coordinate"]["positions"] == []
        assert profile["catalytic_residues"][0]["user_coordinate"]["position"] is None
        assert profile["report_contract"]["claim_status"] == "LIMITED"
        assert profile["report_contract"]["can_report_user_coordinate"] is False
        assert profile["report_contract"]["requires_manual_numbering_review"] is True
        assert profile["pending_numbering"][0]["reason"] == "input_sequence_mapping_required"

    async def test_catalytic_lookup_blocked_profile_has_report_contract(self, session):
        from app.services.annotation_facade import AnnotationFacade

        facade = AnnotationFacade(session)
        payload = await facade.resolve_catalytic_site_lookup()

        profile = payload["mechanism_profile"]
        assert profile["status"] == "blocked"
        assert profile["source_coordinate"]["status"] == "unavailable"
        assert profile["user_coordinate"]["status"] == "unavailable"
        assert profile["report_contract"]["claim_status"] == "BLOCKED"
        assert profile["report_contract"]["can_report_curated_first_shell"] is False
        assert profile["report_contract"]["must_not_claim_complete_mechanism"] is True
        assert "missing sequence or UniProt accession" in profile["report_contract"]["blocked_reasons"]

    async def test_resolve_signal_prediction(self, session):
        from app.services.annotation_facade import AnnotationFacade

        await _seed(session)
        facade = AnnotationFacade(session)
        payload = await facade.resolve_signal_peptide_prediction(uniprot_id="FACADE1")

        assert payload["found"] is True
        assert payload["cache"]["hit"] is True
        assert payload["has_signal_peptide"] is True
        assert payload["evidence_source"]["status"] == "degraded"
        assert payload["evidence_source"]["live_query_executed"] is False

    async def test_resolve_annotation_bundle(self, session):
        from app.services.annotation_facade import AnnotationFacade

        await _seed(session)
        facade = AnnotationFacade(session)
        payload = await facade.resolve_annotation_bundle(uniprot_id="FACADE1")

        assert payload["found"] is True
        assert payload["interpro"]["summary"]["curated_interpro_count"] == 1
        assert payload["catalytic_sites"]["protected_positions"] == [18]
        assert payload["catalytic_sites"]["mechanism_profile"]["first_shell_positions"] == [18]
        assert payload["signal_peptide"]["has_signal_peptide"] is True
        assert payload["evidence_source"]["status"] == "degraded"
        assert payload["evidence_source"]["live_query_executed"] is False
        assert payload["interpro"]["evidence_source"]["status"] == "degraded"
        assert payload["catalytic_sites"]["evidence_source"]["status"] == "degraded"
        assert payload["signal_peptide"]["evidence_source"]["status"] == "degraded"

    async def test_resolve_annotation_bundle_matches_exact_input_sequence(self, session):
        from app.services.annotation_facade import AnnotationFacade

        await _seed(session)
        facade = AnnotationFacade(session)
        payload = await facade.resolve_annotation_bundle(
            sequence="MKKRLFALALALALAGCAQAASAPVAVDNGTQATVTVEGQTQNNGSATWQITGGTNVGSVSGYTVNANNNQ"
        )

        assert payload["query"]["has_curated_enzyme"] is True
        assert payload["query"]["uniprot_id"] == "FACADE1"
        assert payload["coordinate_system"]["status"] == "verified"
        assert payload["catalytic_sites"]["protected_positions"] == [18]

    async def test_missing_input_marks_evidence_source_blocked(self, session):
        from app.services.annotation_facade import AnnotationFacade

        facade = AnnotationFacade(session)

        interpro = await facade.resolve_interpro_annotation()
        catalytic = await facade.resolve_catalytic_site_lookup()
        signal = await facade.resolve_signal_peptide_prediction()
        bundle = await facade.resolve_annotation_bundle()

        assert interpro["evidence_source"]["status"] == "blocked"
        assert catalytic["evidence_source"]["status"] == "blocked"
        assert signal["evidence_source"]["status"] == "blocked"
        assert bundle["evidence_source"]["status"] == "blocked"
        assert interpro["evidence_source"]["live_query_executed"] is False

    async def test_resolve_interpro_annotation_live_success(self, session, monkeypatch):
        from app.services.annotation_facade import AnnotationFacade

        class _Response:
            status_code = 200
            headers: dict[str, str] = {}

            def raise_for_status(self):
                return None

            def json(self):
                return {
                    "results": [
                        {
                            "accession": "IPR000073",
                            "name": "Lipase/Esterase alpha/beta hydrolase",
                            "type": "family",
                            "go_terms": ["GO:0016787 hydrolase activity"],
                            "locations": [{"start": 10, "end": 20}],
                        }
                    ],
                    "metadata": {"count": 1},
                }

        class _Client:
            def __init__(self, *args, **kwargs):
                self.requested_urls: list[str] = []

            async def __aenter__(self):
                return self

            async def __aexit__(self, exc_type, exc, tb):
                return None

            async def get(self, url):
                self.requested_urls.append(url)
                return _Response()

        monkeypatch.setenv("INTERPRO_LIVE_ENABLED", "0")
        monkeypatch.setattr("app.services.interpro_live.httpx.AsyncClient", _Client)

        facade = AnnotationFacade(session)
        payload = await facade.resolve_interpro_annotation(uniprot_id="P12345", live=True)

        assert payload["found"] is True
        assert payload["summary"]["annotation_count"] == 1
        assert payload["annotations"][0]["interpro_id"] == "IPR000073"
        assert payload["annotations"][0]["regions"] == [{"start": 10, "end": 20}]
        assert payload["evidence_source"]["status"] == "live"
        assert payload["evidence_source"]["live_query_executed"] is True

    async def test_resolve_interpro_annotation_live_blocks_on_network_error(self, session, monkeypatch):
        from app.services.annotation_facade import AnnotationFacade

        class _Client:
            def __init__(self, *args, **kwargs):
                pass

            async def __aenter__(self):
                return self

            async def __aexit__(self, exc_type, exc, tb):
                return None

            async def get(self, url):
                raise httpx.ConnectError("unreachable", request=httpx.Request("GET", url))

        monkeypatch.setenv("INTERPRO_LIVE_ENABLED", "0")
        monkeypatch.setattr("app.services.interpro_live.httpx.AsyncClient", _Client)

        facade = AnnotationFacade(session)
        payload = await facade.resolve_interpro_annotation(uniprot_id="P12345", live=True)

        assert payload["found"] is False
        assert payload["evidence_source"]["status"] == "blocked"
        assert payload["evidence_source"]["live_query_executed"] is True
        assert "request_url" in payload["evidence_source"]["details"]

    async def test_resolve_interpro_live_annotation_config_disabled_blocks(self, session, monkeypatch):
        from app.services.annotation_facade import AnnotationFacade

        class _Client:
            def __init__(self, *args, **kwargs):
                raise AssertionError("disabled live lookup must not open an HTTP client")

        monkeypatch.setenv("INTERPRO_LIVE_ENABLED", "0")
        monkeypatch.setattr("app.services.interpro_live.httpx.AsyncClient", _Client)

        facade = AnnotationFacade(session)
        payload = await facade.resolve_interpro_live_annotation(uniprot_id="P12345")

        assert payload["found"] is False
        assert payload["evidence_source"]["status"] == "blocked"
        assert payload["evidence_source"]["live_query_executed"] is False

    async def test_resolve_interpro_annotation_live_config_can_enable(self, session, monkeypatch):
        from app.services.annotation_facade import AnnotationFacade

        class _Response:
            status_code = 200

            def raise_for_status(self):
                return None

            def json(self):
                return {"results": [{"metadata": {"accession": "IPR020937", "name": "Signal peptide", "type": "site"}}]}

        class _Client:
            def __init__(self, *args, **kwargs):
                pass

            async def __aenter__(self):
                return self

            async def __aexit__(self, exc_type, exc, tb):
                return None

            async def get(self, url):
                return _Response()

        monkeypatch.setenv("INTERPRO_LIVE_ENABLED", "1")
        monkeypatch.setattr("app.services.interpro_live.httpx.AsyncClient", _Client)

        facade = AnnotationFacade(session)
        payload = await facade.resolve_interpro_live_annotation(uniprot_id="P12345")

        assert payload["evidence_source"]["status"] == "live"
        assert payload["annotations"][0]["interpro_id"] == "IPR020937"
