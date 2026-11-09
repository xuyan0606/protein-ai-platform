"""Black-box tests: data API endpoints via HTTP client."""

import json
import sqlite3

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.core.config import settings
from app.core.security import create_access_token
from app.models.enzyme_metadata_curation import EnzymeMetadataCurationBatch, EnzymeMetadataCurationRecord
from app.models.experiment_feedback import ExperimentFeedbackRecord
from app.models.lipase_curation import LipaseCurationBatch, LipaseCurationRecord
from app.models.strategy_checkpoint import WetLabCalibrationRun
from app.models.user import User


async def _create_user(session, email: str, role: str = "researcher") -> User:
    user = User(
        email=email,
        hashed_password=User.hash_password("password123"),
        name="Data API User",
        role=role,
    )
    session.add(user)
    await session.flush()
    return user


async def _seed(session) -> dict:
    """Seed minimal test data and return IDs."""
    from app.models.domain import (
        EnzymeRecord, Taxonomy, ECNumber, EnzymeECLink,
        KineticParameter, StabilityRecord, SubstrateCompound,
        ReactionEquation, DirectedEvolutionEntry, DatabaseCrossRef, KVStore,
        InterProEntry, EnzymeInterProLink,
        CatalyticSite, CatalyticResidue,
        SignalPeptidePrediction,
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

    rxn = ReactionEquation(
        rhea_id=99999,
        equation="test_substrate = test_product",
        reactants=[{"name": "test_substrate"}],
        products=[{"name": "test_product"}],
        ec_numbers=["1.1.1.99"],
    )
    session.add(rxn)

    evo = DirectedEvolutionEntry(enzyme_id=enzyme.id, mutagenesis_method="error-prone PCR", rounds=2, fold_improvement=12.0)
    session.add(evo)

    xref = DatabaseCrossRef(enzyme_id=enzyme.id, source_db="pdb", source_id="1TST")
    session.add(xref)

    kv = KVStore(key="ingest:uniprot:hash", value="abc123")
    session.add(kv)

    interpro = InterProEntry(
        interpro_id="IPR029058",
        entry_type="domain",
        name="Alpha/beta hydrolase fold",
        source_db="interpro",
        go_terms=["GO:0003824 catalytic activity"],
    )
    session.add(interpro)
    await session.flush()

    session.add(
        EnzymeInterProLink(
            enzyme_id=enzyme.id,
            interpro_entry_id=interpro.id,
            start_pos=2,
            end_pos=9,
            score=77.7,
            evidence="test_seed",
        )
    )

    site = CatalyticSite(
        enzyme_id=enzyme.id,
        source="test_seed",
        mechanism_name="Hydrolase guardrail",
        reaction_text="Demo catalytic site for API tests",
    )
    session.add(site)
    await session.flush()
    session.add(
        CatalyticResidue(
            site_id=site.id,
            residue_pos=3,
            residue_aa="W",
            role="nucleophile",
            confidence=0.9,
        )
    )

    session.add(
        SignalPeptidePrediction(
            enzyme_id=enzyme.id,
            sequence_hash="api_seed_hash",
            has_signal=False,
            cleavage_site=None,
            model_name="api_test_model",
            raw_json={
                "found": True,
                "query": {"uniprot_id": "P00001", "sequence_length": 10},
                "has_signal_peptide": False,
                "confidence": 0.15,
                "predicted_type": "none",
                "cleavage_site": None,
                "regions": {
                    "n_region": {"start": 1, "end": 5, "positive_residues": 0},
                    "h_region": {"start": 7, "end": 10, "hydrophobic_ratio": 0.2},
                    "c_region": {"start": 6, "end": None}
                },
                "model": "api_test_model",
                "cache": {"hit": True, "source": "database"}
            },
        )
    )

    await session.commit()
    return {"enzyme_id": enzyme.id, "ec_id": ec.id}


def _create_lipase_test_db(path):
    conn = sqlite3.connect(path)
    conn.executescript(
        """
        PRAGMA foreign_keys=ON;
        CREATE TABLE papers (
            id INTEGER PRIMARY KEY,
            paper_key TEXT NOT NULL UNIQUE,
            citation TEXT NOT NULL,
            title TEXT,
            authors TEXT,
            journal TEXT,
            year INTEGER,
            doi TEXT,
            pmid TEXT,
            enzyme_name TEXT,
            engineering_objective TEXT,
            lock_status TEXT,
            ready_for_db TEXT,
            notes TEXT
        );
        CREATE TABLE paper_aliases (
            id INTEGER PRIMARY KEY,
            alias_key TEXT NOT NULL,
            canonical_paper_id INTEGER NOT NULL,
            alias_type TEXT,
            note TEXT,
            UNIQUE(alias_key, canonical_paper_id),
            FOREIGN KEY (canonical_paper_id) REFERENCES papers(id)
        );
        CREATE TABLE variants (
            id INTEGER PRIMARY KEY,
            paper_id INTEGER NOT NULL,
            variant_label TEXT,
            anchor_display TEXT NOT NULL,
            parent_variant_id INTEGER,
            variant_type TEXT,
            summary_payload TEXT,
            notes TEXT,
            FOREIGN KEY (paper_id) REFERENCES papers(id),
            FOREIGN KEY (parent_variant_id) REFERENCES variants(id)
        );
        CREATE TABLE variant_mutations (
            id INTEGER PRIMARY KEY,
            variant_id INTEGER NOT NULL,
            mutation_code TEXT NOT NULL,
            residue_from TEXT,
            position INTEGER,
            residue_to TEXT,
            sort_order INTEGER,
            UNIQUE(variant_id, mutation_code, sort_order),
            FOREIGN KEY (variant_id) REFERENCES variants(id)
        );
        CREATE TABLE evidence_claims (
            id INTEGER PRIMARY KEY,
            paper_id INTEGER NOT NULL,
            variant_id INTEGER,
            claim_group TEXT,
            evidence_level TEXT NOT NULL,
            direct_evidence TEXT NOT NULL,
            evidence_source_location TEXT,
            claim_summary TEXT,
            known_payload TEXT,
            source_granularity TEXT,
            notes TEXT,
            FOREIGN KEY (paper_id) REFERENCES papers(id),
            FOREIGN KEY (variant_id) REFERENCES variants(id)
        );
        CREATE TABLE substrates (
            id INTEGER PRIMARY KEY,
            substrate_name TEXT NOT NULL UNIQUE,
            substrate_role TEXT,
            notes TEXT
        );
        CREATE TABLE claim_substrates (
            id INTEGER PRIMARY KEY,
            claim_id INTEGER NOT NULL,
            substrate_id INTEGER NOT NULL,
            relation_type TEXT,
            note TEXT,
            UNIQUE(claim_id, substrate_id, relation_type),
            FOREIGN KEY (claim_id) REFERENCES evidence_claims(id),
            FOREIGN KEY (substrate_id) REFERENCES substrates(id)
        );
        CREATE TABLE metrics (
            id INTEGER PRIMARY KEY,
            claim_id INTEGER NOT NULL,
            metric_type TEXT NOT NULL,
            metric_value TEXT,
            metric_unit TEXT,
            direction TEXT,
            condition_text TEXT,
            is_quantified INTEGER NOT NULL DEFAULT 0,
            notes TEXT,
            FOREIGN KEY (claim_id) REFERENCES evidence_claims(id)
        );
        CREATE TABLE comparators (
            id INTEGER PRIMARY KEY,
            claim_id INTEGER NOT NULL,
            comparator_label TEXT NOT NULL,
            comparator_type TEXT,
            baseline_value TEXT,
            baseline_unit TEXT,
            baseline_status TEXT,
            notes TEXT,
            FOREIGN KEY (claim_id) REFERENCES evidence_claims(id)
        );
        CREATE TABLE unresolved_gaps (
            id INTEGER PRIMARY KEY,
            paper_id INTEGER,
            variant_id INTEGER,
            claim_id INTEGER,
            gap_type TEXT NOT NULL,
            gap_detail TEXT NOT NULL,
            priority TEXT,
            status TEXT,
            blocker_reason TEXT,
            FOREIGN KEY (paper_id) REFERENCES papers(id),
            FOREIGN KEY (variant_id) REFERENCES variants(id),
            FOREIGN KEY (claim_id) REFERENCES evidence_claims(id)
        );
        CREATE TABLE lineage_notes (
            id INTEGER PRIMARY KEY,
            paper_id INTEGER,
            variant_id INTEGER,
            note_type TEXT,
            note_text TEXT NOT NULL,
            FOREIGN KEY (paper_id) REFERENCES papers(id),
            FOREIGN KEY (variant_id) REFERENCES variants(id)
        );

        INSERT INTO papers (id, paper_key, citation, year, enzyme_name, engineering_objective, lock_status, ready_for_db)
        VALUES (1, 'Xie_2014', 'Xie 2014 CALB stability', 2014, 'Candida antarctica lipase B (CALB)', 'kinetic stability', 'citation_locked', 'provisional_yes');
        INSERT INTO variants (id, paper_id, variant_label, anchor_display, variant_type, summary_payload)
        VALUES (1, 1, 'D223G/L278M', 'D223G/L278M', 'combination', '13-fold half-life increase');
        INSERT INTO variant_mutations (variant_id, mutation_code, residue_from, position, residue_to, sort_order)
        VALUES (1, 'D223G', 'D', 223, 'G', 1), (1, 'L278M', 'L', 278, 'M', 2);
        INSERT INTO evidence_claims (id, paper_id, variant_id, claim_group, evidence_level, direct_evidence, claim_summary, source_granularity)
        VALUES (1, 1, 1, 'kinetic_stability', 'article_level', 't1/2 increased at 48 C', 'D223G/L278M improves half-life', 'table');
        INSERT INTO metrics (claim_id, metric_type, metric_value, metric_unit, direction, condition_text, is_quantified)
        VALUES (1, 'half_life', '49', 'min', 'increase', 'at 48 C', 1);
        INSERT INTO substrates (id, substrate_name, substrate_role)
        VALUES (1, 'p-nitrophenyl butyrate', 'assay_substrate');
        INSERT INTO claim_substrates (claim_id, substrate_id, relation_type)
        VALUES (1, 1, 'assay');
        INSERT INTO comparators (claim_id, comparator_label, comparator_type)
        VALUES (1, 'wild type', 'baseline');
        INSERT INTO unresolved_gaps (paper_id, variant_id, claim_id, gap_type, gap_detail, priority, status)
        VALUES (1, 1, 1, 'missing_wt_baseline', 'WT baseline value not captured', 'high', 'open');
        INSERT INTO lineage_notes (paper_id, variant_id, note_type, note_text)
        VALUES (1, 1, 'lineage', 'Best variant in Xie 2014');
        INSERT INTO paper_aliases (alias_key, canonical_paper_id, alias_type)
        VALUES ('PMID:24448805', 1, 'pmid');
        """
    )
    conn.commit()
    conn.close()
    return path


def _create_simple_enzyme_test_db(root):
    db_dir = root / "acid-protease-db"
    db_dir.mkdir(parents=True, exist_ok=True)
    path = db_dir / "acid_protease.db"
    conn = sqlite3.connect(path)
    conn.executescript(
        """
        CREATE TABLE papers (
            id TEXT PRIMARY KEY,
            title TEXT,
            author TEXT,
            journal TEXT,
            year INTEGER,
            doi TEXT,
            pmid TEXT,
            access TEXT,
            priority TEXT,
            lab TEXT,
            category TEXT,
            quality TEXT,
            notes TEXT
        );
        CREATE TABLE variants (
            id TEXT PRIMARY KEY,
            eid TEXT,
            pid TEXT,
            name TEXT,
            norm TEXT,
            mtype TEXT,
            cnt INTEGER,
            sm TEXT,
            bg TEXT,
            effect TEXT
        );
        CREATE TABLE measurements (
            mid INTEGER PRIMARY KEY,
            vid TEXT,
            pid TEXT,
            cat TEXT,
            prop TEXT,
            val REAL,
            unit TEXT,
            wt REAL,
            fc REAL,
            dir TEXT,
            temp REAL,
            pH REAL,
            sub TEXT,
            src TEXT,
            conf TEXT
        );
        INSERT INTO papers (id, title, author, journal, year, access, priority, quality, notes)
        VALUES
            ('AP_OK', 'Accepted A paper', 'A', 'J', 2024, 'oa', 'high', 'A', ''),
            ('AP_PRIORITY_ONLY', 'Priority-only paper', 'D', 'J', 2024, 'oa', 'high', 'B', ''),
            ('AP_TABLE_BOUNDARY', 'A paper with table boundary row', 'E', 'J', 2024, 'oa', 'source_table_reconciled', 'A', ''),
            ('AP_B', 'B paper', 'B', 'J', 2024, 'preprint', 'medium', 'B', ''),
            ('AP_HOLD', 'Hold paper', 'C', 'J', 2024, 'hold', 'hold', 'non_exportable', ''),
            ('AP_PATENT_A', 'Patent A paper', 'P', 'US20160168555', 2024, 'patent', 'high', 'A', ''),
            ('AP_PREPRINT_A', 'Preprint A paper', 'R', 'bioRxiv', 2024, 'preprint', 'high', 'A', ''),
            ('AP_BOUNDARY_A', 'Boundary A paper', 'S', 'J', 2024, 'oa', 'metadata_source_conflict_hold_boundary', 'A', '');
        INSERT INTO variants (id, pid, name)
        VALUES
            ('V_OK', 'AP_OK', 'A1G'),
            ('V_PRIORITY_ONLY', 'AP_PRIORITY_ONLY', 'P1G'),
            ('V_TABLE_BOUNDARY', 'AP_TABLE_BOUNDARY', 'T1G'),
            ('V_B', 'AP_B', 'B1G'),
            ('V_HOLD', 'AP_HOLD', 'H1G'),
            ('V_PATENT_A', 'AP_PATENT_A', 'P1G'),
            ('V_PREPRINT_A', 'AP_PREPRINT_A', 'R1G'),
            ('V_BOUNDARY_A', 'AP_BOUNDARY_A', 'S1G');
        INSERT INTO measurements (mid, vid, pid, cat, prop, val, unit, src, conf)
        VALUES
            (1, 'V_OK', 'AP_OK', 'stability', 'Tm', 70.0, 'C', 'source_table', 'A'),
            (2, 'V_PRIORITY_ONLY', 'AP_PRIORITY_ONLY', 'stability', 'Tm', 66.0, 'C', 'source_table', 'B'),
            (3, 'V_TABLE_BOUNDARY', 'AP_TABLE_BOUNDARY', 'stability', 'Tm', 64.0, 'C', 'Table 1', 'table_not_detectable_boundary'),
            (4, 'V_B', 'AP_B', 'stability', 'Tm', 65.0, 'C', 'preprint', 'B'),
            (5, 'V_HOLD', 'AP_HOLD', 'stability', 'Tm', 60.0, 'C', 'hold', 'non_exportable'),
            (6, 'V_PATENT_A', 'AP_PATENT_A', 'stability', 'Tm', 62.0, 'C', 'patent', 'A'),
            (7, 'V_PREPRINT_A', 'AP_PREPRINT_A', 'stability', 'Tm', 63.0, 'C', 'preprint', 'A'),
            (8, 'V_BOUNDARY_A', 'AP_BOUNDARY_A', 'stability', 'Tm', 61.0, 'C', 'source_table', 'A');
        """
    )
    conn.commit()
    conn.close()
    (db_dir / "enzyme_metadata_policy_decisions_20260805.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "family": "acid_protease",
                "created_at": "2026-08-05",
                "scope": "test policy decisions",
                "export_safe": False,
                "decisions": [
                    {
                        "paper_id": "AP_PATENT_A",
                        "record_type": "patent",
                        "decision": "keep_doi_pmid_blank",
                        "review_status": "manual_required",
                        "export_safe": False,
                    },
                    {
                        "paper_id": "AP_PREPRINT_A",
                        "record_type": "preprint_to_version_of_record",
                        "decision": "manual_identity_upgrade_required",
                        "review_status": "manual_required",
                        "export_safe": False,
                    },
                ],
            }
        ),
        encoding="utf-8",
    )
    return path


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


class TestBenchmarkEndpoints:
    async def test_data_readiness_endpoint_reports_components(self, client: AsyncClient):
        resp = await client.get("/api/data/readiness")
        assert resp.status_code == 200
        data = resp.json()
        assert data["summary"] in {"live-ready", "demo-ready", "partial", "empty"}
        assert "root" in data
        assert "components" in data
        for key in ["annotations", "sifts", "pdb", "alphafold", "foldseek", "smoke_query"]:
            assert key in data["components"]
            assert "status" in data["components"][key]
            assert "version" in data["components"][key]
            assert "updated_at" in data["components"][key]
            assert "missing_items" in data["components"][key]
        assert "updates" in data
        assert "manifest_count" in data["updates"]
        assert "failure_count" in data["updates"]
        assert isinstance(data["updates"]["manifests"], list)
        assert "version_comparison" in data
        assert "next_actions" in data

    async def test_tool_capabilities_endpoint_exposes_scientific_boundaries(self, client: AsyncClient):
        resp = await client.get("/api/data/tool-capabilities")

        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ready"
        assert data["summary"]["unknown_count"] == 0
        by_tool = {row["tool"]: row for row in data["capabilities"]}
        assert by_tool["alphafold2_folding"]["capability_status"] == "proxy"
        assert by_tool["gromacs_md"]["capability_status"] == "real_runtime_gated"
        assert "weak TM-score" in by_tool["structure_search_foldseek"]["boundary"]
        assert "not external SIFTS/UniProt mapping" in by_tool["residue_mapping_sifts"]["boundary"]

    async def test_admin_data_readiness_requires_admin(self, client: AsyncClient, session):
        user = await _create_user(session, "data-readiness-user@example.com")
        await session.commit()
        client.cookies.set("pa_token", create_access_token(user.id))

        resp = await client.get("/api/data/admin/readiness")

        assert resp.status_code == 403

    async def test_admin_data_readiness_reports_components(self, client: AsyncClient, session):
        admin = await _create_user(session, "data-readiness-admin@example.com", role="admin")
        await session.commit()
        client.cookies.set("pa_token", create_access_token(admin.id))

        resp = await client.get("/api/data/admin/readiness")

        assert resp.status_code == 200
        data = resp.json()
        assert data["admin"]["read_only"] is True
        assert data["admin"]["view"] == "data-management"
        assert data["admin"]["user_id"] == admin.id
        for key in ["annotations", "sifts", "pdb", "alphafold", "foldseek", "smoke_query"]:
            assert key in data["components"]
            assert "status" in data["components"][key]
            assert "failure_reason" in data["components"][key]
            assert isinstance(data["components"][key]["missing_items"], list)

    async def test_admin_data_updates_filter_and_import_dry_run(self, client: AsyncClient, session):
        admin = await _create_user(session, "data-updates-admin@example.com", role="admin")
        await session.commit()
        client.cookies.set("pa_token", create_access_token(admin.id))

        updates_resp = await client.get("/api/data/admin/updates", params={"component": "manual_import"})
        import_resp = await client.post(
            "/api/data/admin/import",
            json={
                "annotations": "/tmp/not-required-for-dry-run/annotations",
                "pdb": "/tmp/not-required-for-dry-run/pdb",
                "dry_run": True,
                "symlink": True,
            },
        )

        assert updates_resp.status_code == 200
        updates_data = updates_resp.json()
        assert updates_data["admin"]["read_only"] is True
        assert isinstance(updates_data["updates"], list)
        assert import_resp.status_code == 200
        import_data = import_resp.json()
        assert import_data["status"] == "planned"
        assert import_data["plan"]["dry_run"] is True
        assert "--annotations" in import_data["plan"]["command"]

    async def test_lipase_db_status_reports_readonly_quality(self, client: AsyncClient, tmp_path, monkeypatch):
        db_path = _create_lipase_test_db(tmp_path / "lipase.db")
        monkeypatch.setattr(settings, "LIPASE_DB_PATH", str(db_path))

        resp = await client.get("/api/data/lipase/status")

        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ready"
        assert data["read_only"] is True
        assert data["quality"]["integrity_check"] == "ok"
        assert data["quality"]["foreign_key_issues"] == []
        assert data["summary"]["paper_count"] == 1
        assert data["summary"]["variant_count"] == 1
        assert data["summary"]["claim_count"] == 1
        assert data["missing_tables"] == []

    async def test_lipase_variants_returns_evidence_rows(self, client: AsyncClient, tmp_path, monkeypatch):
        db_path = _create_lipase_test_db(tmp_path / "lipase.db")
        monkeypatch.setattr(settings, "LIPASE_DB_PATH", str(db_path))

        resp = await client.get("/api/data/lipase/variants", params={"q": "D223G", "limit": 5})

        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ready"
        assert data["count"] == 1
        row = data["variants"][0]
        assert row["paper_key"] == "Xie_2014"
        assert row["variant_label"] == "D223G/L278M"
        assert "D223G" in row["mutations"]
        assert row["claim_group"] == "kinetic_stability"
        assert "half_life" in row["metrics"]

    async def test_lipase_papers_detail_gaps_and_search(self, client: AsyncClient, tmp_path, monkeypatch):
        db_path = _create_lipase_test_db(tmp_path / "lipase.db")
        monkeypatch.setattr(settings, "LIPASE_DB_PATH", str(db_path))

        papers_resp = await client.get("/api/data/lipase/papers", params={"q": "Xie", "limit": 5})
        detail_resp = await client.get("/api/data/lipase/papers/Xie_2014")
        gaps_resp = await client.get("/api/data/lipase/gaps", params={"priority": "high", "status": "open"})
        search_resp = await client.get("/api/data/lipase/search", params={"q": "half", "limit": 10})
        context_resp = await client.get(
            "/api/data/lipase/evidence-context",
            params={"mutations": "D223G", "positions": 223, "q": "half", "limit": 10},
        )

        assert papers_resp.status_code == 200
        papers = papers_resp.json()
        assert papers["count"] == 1
        assert papers["papers"][0]["paper_key"] == "Xie_2014"
        assert papers["papers"][0]["variant_count"] == 1

        assert detail_resp.status_code == 200
        detail = detail_resp.json()
        assert detail["paper"]["paper_key"] == "Xie_2014"
        assert detail["counts"]["variants"] == 1
        assert detail["claims"][0]["claim_group"] == "kinetic_stability"
        assert detail["gaps"][0]["gap_type"] == "missing_wt_baseline"

        assert gaps_resp.status_code == 200
        gaps = gaps_resp.json()
        assert gaps["count"] == 1
        assert gaps["gaps"][0]["priority"] == "high"

        assert search_resp.status_code == 200
        search = search_resp.json()
        assert search["status"] == "ready"
        assert search["counts"]["claims"] == 1
        assert search["results"]["claims"][0]["paper_key"] == "Xie_2014"

        assert context_resp.status_code == 200
        context = context_resp.json()
        assert context["status"] == "ready"
        assert context["requested_mutations"] == ["D223G"]
        assert context["requested_positions"] == [223]
        assert context["counts"]["exact_mutation_matches"] == 1
        assert context["exact_mutation_matches"][0]["mutation_code"] == "D223G"
        assert context["counts"]["position_matches"] >= 1

    async def test_lipase_evidence_queries_exclude_hold_rows_by_default(self, client: AsyncClient, tmp_path, monkeypatch):
        db_path = _create_lipase_test_db(tmp_path / "lipase.db")
        with sqlite3.connect(db_path) as conn:
            conn.executescript(
                """
                INSERT INTO papers (id, paper_key, citation, year, enzyme_name, engineering_objective, lock_status, ready_for_db)
                VALUES (2, 'BTL2_hold_payload', 'BTL2 hold payload', 2019, 'BTL2', 'solvent tolerance', 'citation_locked_provisional', 'hold_payload');
                INSERT INTO variants (id, paper_id, variant_label, anchor_display, variant_type, summary_payload)
                VALUES (2, 2, 'D223G hold', 'D223G', 'single', 'hold-only payload');
                INSERT INTO variant_mutations (variant_id, mutation_code, residue_from, position, residue_to, sort_order)
                VALUES (2, 'D223G', 'D', 223, 'G', 1);
                INSERT INTO evidence_claims (id, paper_id, variant_id, claim_group, evidence_level, direct_evidence, claim_summary, source_granularity)
                VALUES (2, 2, 2, 'hold_payload', 'article_level', 'hold-only half-life claim', 'D223G hold half-life payload', 'table');
                """
            )
        monkeypatch.setattr(settings, "LIPASE_DB_PATH", str(db_path))

        variants_resp = await client.get("/api/data/lipase/variants", params={"q": "D223G", "limit": 10})
        search_resp = await client.get("/api/data/lipase/search", params={"q": "half", "limit": 10})
        context_resp = await client.get(
            "/api/data/lipase/evidence-context",
            params={"mutations": "D223G", "positions": 223, "q": "half", "limit": 10},
        )
        audit_resp = await client.get(
            "/api/data/lipase/evidence-context",
            params={"mutations": "D223G", "positions": 223, "q": "half", "limit": 10, "include_non_ready": True},
        )

        assert variants_resp.status_code == 200
        variants = variants_resp.json()
        assert variants["evidence_scope"] == "provisional_ready"
        assert variants["count"] == 1
        assert {row["paper_key"] for row in variants["variants"]} == {"Xie_2014"}

        assert search_resp.status_code == 200
        search = search_resp.json()
        assert search["evidence_scope"] == "provisional_ready"
        assert search["counts"]["claims"] == 1
        assert {row["paper_key"] for row in search["results"]["claims"]} == {"Xie_2014"}

        assert context_resp.status_code == 200
        context = context_resp.json()
        assert context["evidence_scope"] == "provisional_ready"
        assert {row["paper_key"] for row in context["exact_mutation_matches"]} == {"Xie_2014"}

        assert audit_resp.status_code == 200
        audit_context = audit_resp.json()
        assert audit_context["evidence_scope"] == "all_readiness_states"
        assert "BTL2_hold_payload" in {row["paper_key"] for row in audit_context["exact_mutation_matches"]}

    async def test_lipase_paper_detail_not_found(self, client: AsyncClient, tmp_path, monkeypatch):
        db_path = _create_lipase_test_db(tmp_path / "lipase.db")
        monkeypatch.setattr(settings, "LIPASE_DB_PATH", str(db_path))

        resp = await client.get("/api/data/lipase/papers/unknown")

        assert resp.status_code == 404

    async def test_simple_enzyme_export_safe_measurements_are_a_only(self, client: AsyncClient, tmp_path, monkeypatch):
        _create_simple_enzyme_test_db(tmp_path)
        monkeypatch.setattr(settings, "ENZYME_DB_ROOT", str(tmp_path))

        browser_resp = await client.get(
            "/api/data/enzyme-dbs/acid_protease/measurements",
            params={"q": "AP", "limit": 10},
        )
        export_resp = await client.get(
            "/api/data/enzyme-dbs/acid_protease/export-safe/measurements",
            params={"q": "AP", "limit": 10},
        )

        assert browser_resp.status_code == 200
        browser = browser_resp.json()
        assert browser["export_scope"] == "browser_audit"
        assert browser["export_safe"] is False
        assert browser["count"] == 8
        assert {row["pid"] for row in browser["measurements"]} == {
            "AP_OK",
            "AP_PRIORITY_ONLY",
            "AP_TABLE_BOUNDARY",
            "AP_B",
            "AP_HOLD",
            "AP_PATENT_A",
            "AP_PREPRINT_A",
            "AP_BOUNDARY_A",
        }
        assert all(row["export_safe"] is False for row in browser["measurements"])

        assert export_resp.status_code == 200
        export_safe = export_resp.json()
        assert export_safe["export_scope"] == "compact_high_confidence_a_only"
        assert export_safe["export_safe"] is True
        assert export_safe["count"] == 1
        row = export_safe["measurements"][0]
        assert row["export_safe"] is True
        assert row["pid"] == "AP_OK"
        assert row["paper_quality"] == "A"
        assert row["conf"] == "A"
        assert "AP_TABLE_BOUNDARY" not in {item["pid"] for item in export_safe["measurements"]}
        assert "AP_PATENT_A" not in {item["pid"] for item in export_safe["measurements"]}
        assert "AP_PREPRINT_A" not in {item["pid"] for item in export_safe["measurements"]}
        assert "AP_BOUNDARY_A" not in {item["pid"] for item in export_safe["measurements"]}

    async def test_simple_enzyme_missing_database_is_not_reported_as_empty_ready(self, client: AsyncClient, tmp_path, monkeypatch):
        monkeypatch.setattr(settings, "ENZYME_DB_ROOT", str(tmp_path / "not-mounted"))

        status_resp = await client.get("/api/data/enzyme-dbs/acid_protease/status")
        papers_resp = await client.get("/api/data/enzyme-dbs/acid_protease/papers")
        variants_resp = await client.get("/api/data/enzyme-dbs/acid_protease/variants")
        measurements_resp = await client.get("/api/data/enzyme-dbs/acid_protease/measurements")
        search_resp = await client.get("/api/data/enzyme-dbs/acid_protease/search", params={"q": "activity"})

        assert status_resp.json()["status"] == "missing"
        for response, key in (
            (papers_resp, "papers"),
            (variants_resp, "variants"),
            (measurements_resp, "measurements"),
        ):
            payload = response.json()
            assert payload["status"] == "missing_database"
            assert payload[key] == []
            assert "not mounted" in payload["error"]
        search = search_resp.json()
        assert search["status"] == "missing_database"
        assert search["results"] == {"papers": [], "variants": [], "measurements": []}

    async def test_simple_enzyme_status_reports_metadata_quality_summary(self, client: AsyncClient, tmp_path, monkeypatch):
        _create_simple_enzyme_test_db(tmp_path)
        monkeypatch.setattr(settings, "ENZYME_DB_ROOT", str(tmp_path))

        resp = await client.get("/api/data/enzyme-dbs/acid_protease/status")

        assert resp.status_code == 200
        data = resp.json()
        summary = data["metadata_quality"]
        policy_decisions = data["metadata_policy_decisions"]
        assert policy_decisions["status"] == "ok"
        assert policy_decisions["manifest_count"] == 1
        assert policy_decisions["decision_count"] == 2
        assert policy_decisions["record_types"] == ["patent", "preprint_to_version_of_record"]
        assert policy_decisions["review_statuses"] == ["manual_required"]
        assert summary["missing_doi"] == 8
        assert summary["missing_pmid"] == 8
        assert summary["metadata_gap_count"] == 16
        assert summary["patent_like_sources"] == 1
        assert summary["preprint_papers"] == 2
        assert summary["boundary_papers"] == 1
        assert summary["boundary_measurements"] == 1
        assert summary["policy_excluded_papers"] == 5
        assert summary["policy_excluded_measurements"] == 5
        assert summary["non_exportable_markers"] == ["hold", "boundary", "non_exportable", "patent", "preprint"]
        assert summary["export_policy"]["patent_metadata"] == "keep_out_of_doi_pmid_until_policy_exists"
        assert summary["export_policy"]["preprint_version_of_record"] == "manual_identity_upgrade_required"
        assert summary["export_policy"]["blocked_markers"] == [
            "hold",
            "boundary",
            "non_exportable",
            "patent",
            "preprint",
        ]
        assert summary["hold_papers"] == 2
        assert summary["hold_measurements"] == 1
        assert summary["export_safe_measurements"] == 1
        assert summary["browser_scope"] == "audit_includes_hold_rows"

    async def test_simple_enzyme_policy_decisions_preview_is_admin_dry_run(self, client: AsyncClient, session, tmp_path, monkeypatch):
        _create_simple_enzyme_test_db(tmp_path)
        monkeypatch.setattr(settings, "ENZYME_DB_ROOT", str(tmp_path))
        researcher = await _create_user(session, "enzyme-policy-preview-user@example.com")
        admin = await _create_user(session, "enzyme-policy-preview-admin@example.com", role="admin")
        await session.commit()

        client.cookies.set("pa_token", create_access_token(researcher.id))
        forbidden = await client.post("/api/data/enzyme-dbs/acid_protease/policy-decisions/preview")
        assert forbidden.status_code == 403

        client.cookies.set("pa_token", create_access_token(admin.id))
        resp = await client.post("/api/data/enzyme-dbs/acid_protease/policy-decisions/preview")

        assert resp.status_code == 200
        data = resp.json()
        assert data["dry_run"] is True
        assert data["read_only_source_db"] is True
        assert data["confirmation_required"] is True
        assert data["confirmation_token"] == "MANUAL_ENZYME_POLICY_DECISION_REVIEW"
        assert data["manifest"]["record_count"] == 2
        assert data["manifest"]["record_types"] == ["patent", "preprint_to_version_of_record"]
        assert data["export_payload"]["target"] == "manual_enzyme_db_curation_or_upgrade_script"
        assert {row["paper_id"] for row in data["export_payload"]["records"]} == {"AP_PATENT_A", "AP_PREPRINT_A"}
        assert data["reviewer_user_id"] == admin.id

    async def test_simple_enzyme_policy_decisions_publish_is_fail_closed(self, client: AsyncClient, session, tmp_path, monkeypatch):
        db_path = _create_simple_enzyme_test_db(tmp_path)
        monkeypatch.setattr(settings, "ENZYME_DB_ROOT", str(tmp_path))
        researcher = await _create_user(session, "enzyme-policy-publish-user@example.com")
        admin = await _create_user(session, "enzyme-policy-publish-admin@example.com", role="admin")
        await session.commit()

        before_stat = db_path.stat()
        with sqlite3.connect(db_path) as conn:
            before_rows = conn.execute(
                """
                SELECT id, doi, pmid, access, priority, quality, notes
                FROM papers
                WHERE id IN ('AP_PATENT_A', 'AP_PREPRINT_A', 'AP_BOUNDARY_A')
                ORDER BY id
                """
            ).fetchall()

        client.cookies.set("pa_token", create_access_token(researcher.id))
        forbidden = await client.post(
            "/api/data/enzyme-dbs/acid_protease/policy-decisions/publish",
            json={"dry_run": True},
        )
        assert forbidden.status_code == 403

        client.cookies.set("pa_token", create_access_token(admin.id))
        dry_run = await client.post(
            "/api/data/enzyme-dbs/acid_protease/policy-decisions/publish",
            json={"dry_run": True},
        )
        assert dry_run.status_code == 200
        planned = dry_run.json()
        assert planned["dry_run"] is True
        assert planned["read_only_source_db"] is True
        assert planned["sqlite_mutated"] is False
        assert planned["sqlite_mutation_allowed"] is False
        assert planned["export_safe"] is False
        assert planned["export_safe_released"] is False
        assert planned["publish_status"] == "planned"
        assert planned["confirmation_token"] == "MANUAL_ENZYME_POLICY_DECISION_REVIEW"

        wrong_token = await client.post(
            "/api/data/enzyme-dbs/acid_protease/policy-decisions/publish",
            json={"dry_run": False, "confirmation": "WRONG"},
        )
        assert wrong_token.status_code == 422

        blocked_resp = await client.post(
            "/api/data/enzyme-dbs/acid_protease/policy-decisions/publish",
            json={"dry_run": False, "confirmation": "MANUAL_ENZYME_POLICY_DECISION_REVIEW"},
        )
        assert blocked_resp.status_code == 409
        blocked = blocked_resp.json()["detail"]
        assert blocked["dry_run"] is False
        assert blocked["blocked"] is True
        assert blocked["publish_status"] == "blocked"
        assert blocked["sqlite_mutated"] is False
        assert blocked["sqlite_mutation_allowed"] is False
        assert blocked["export_safe"] is False
        assert blocked["export_safe_released"] is False
        assert blocked["release_plan"]["apply_supported"] is False
        assert "manual_upgrade_script_required" == blocked["release_plan"]["mode"]

        after_stat = db_path.stat()
        assert after_stat.st_size == before_stat.st_size
        assert after_stat.st_mtime_ns == before_stat.st_mtime_ns
        for suffix in ("-wal", "-journal", "-shm"):
            assert not db_path.with_name(db_path.name + suffix).exists()
        with sqlite3.connect(db_path) as conn:
            after_rows = conn.execute(
                """
                SELECT id, doi, pmid, access, priority, quality, notes
                FROM papers
                WHERE id IN ('AP_PATENT_A', 'AP_PREPRINT_A', 'AP_BOUNDARY_A')
                ORDER BY id
                """
            ).fetchall()
            assert conn.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        assert after_rows == before_rows

        export_resp = await client.get("/api/data/enzyme-dbs/acid_protease/export-safe/measurements")
        export_safe = export_resp.json()
        assert export_safe["count"] == 1
        assert {item["pid"] for item in export_safe["measurements"]} == {"AP_OK"}
        assert "AP_PATENT_A" not in {item["pid"] for item in export_safe["measurements"]}
        assert "AP_PREPRINT_A" not in {item["pid"] for item in export_safe["measurements"]}
        assert "AP_BOUNDARY_A" not in {item["pid"] for item in export_safe["measurements"]}
        assert "AP_TABLE_BOUNDARY" not in {item["pid"] for item in export_safe["measurements"]}

    async def test_enzyme_metadata_policy_decisions_materialize_to_internal_queue_only(self, client: AsyncClient, session, tmp_path, monkeypatch):
        db_path = _create_simple_enzyme_test_db(tmp_path)
        monkeypatch.setattr(settings, "ENZYME_DB_ROOT", str(tmp_path))
        researcher = await _create_user(session, "enzyme-metadata-queue-user@example.com")
        admin = await _create_user(session, "enzyme-metadata-queue-admin@example.com", role="admin")
        await session.commit()
        before_stat = db_path.stat()

        client.cookies.set("pa_token", create_access_token(researcher.id))
        forbidden = await client.post(
            "/api/data/enzyme-dbs/acid_protease/metadata-curation/materialize",
            json={"dry_run": True},
        )
        assert forbidden.status_code == 403

        client.cookies.set("pa_token", create_access_token(admin.id))
        dry_run_resp = await client.post(
            "/api/data/enzyme-dbs/acid_protease/metadata-curation/materialize",
            json={"dry_run": True},
        )
        materialize_resp = await client.post(
            "/api/data/enzyme-dbs/acid_protease/metadata-curation/materialize",
            json={"dry_run": False},
        )
        repeat_resp = await client.post(
            "/api/data/enzyme-dbs/acid_protease/metadata-curation/materialize",
            json={"dry_run": False},
        )

        assert dry_run_resp.status_code == 200
        dry_run = dry_run_resp.json()
        assert dry_run["dry_run"] is True
        assert dry_run["planned_count"] == 2
        assert dry_run["sqlite_mutated"] is False
        assert dry_run["export_safe_released"] is False

        assert materialize_resp.status_code == 200
        materialized = materialize_resp.json()
        assert materialized["status"] == "materialized"
        assert materialized["dry_run"] is False
        assert materialized["planned_count"] == 2
        assert materialized["skipped_count"] == 0
        assert materialized["sqlite_mutated"] is False
        assert materialized["export_safe_released"] is False

        assert repeat_resp.status_code == 200
        repeated = repeat_resp.json()
        assert repeated["planned_count"] == 0
        assert repeated["skipped_count"] == 2

        list_resp = await client.get(
            "/api/data/enzyme-metadata/curation-records",
            params={"family": "acid_protease", "status": "queued"},
        )
        assert list_resp.status_code == 200
        listed = list_resp.json()
        assert listed["count"] == 2
        paper_ids = {record["paper_id"] for record in listed["records"]}
        assert paper_ids == {"AP_PATENT_A", "AP_PREPRINT_A"}
        assert {record["status"] for record in listed["records"]} == {"queued"}
        assert {record["created_by_user_id"] for record in listed["records"]} == {admin.id}

        stored_records = (await session.execute(select(EnzymeMetadataCurationRecord))).scalars().all()
        assert len(stored_records) == 2
        assert {record.decision_payload["export_safe"] for record in stored_records} == {False}

        after_stat = db_path.stat()
        assert after_stat.st_size == before_stat.st_size
        assert after_stat.st_mtime_ns == before_stat.st_mtime_ns
        with sqlite3.connect(db_path) as conn:
            assert conn.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        export_resp = await client.get("/api/data/enzyme-dbs/acid_protease/export-safe/measurements")
        assert export_resp.json()["count"] == 1

    async def test_enzyme_metadata_curation_review_batch_archive_keeps_external_db_read_only(self, client: AsyncClient, session, tmp_path, monkeypatch):
        db_path = _create_simple_enzyme_test_db(tmp_path)
        monkeypatch.setattr(settings, "ENZYME_DB_ROOT", str(tmp_path))
        admin = await _create_user(session, "enzyme-metadata-batch-admin@example.com", role="admin")
        await session.commit()
        before_stat = db_path.stat()

        client.cookies.set("pa_token", create_access_token(admin.id))
        materialize_resp = await client.post(
            "/api/data/enzyme-dbs/acid_protease/metadata-curation/materialize",
            json={"dry_run": False},
        )
        record_id = materialize_resp.json()["planned_records"][0]["paper_id"]
        listed_resp = await client.get(
            "/api/data/enzyme-metadata/curation-records",
            params={"family": "acid_protease", "status": "queued"},
        )
        queued_records = listed_resp.json()["records"]
        accepted_id = next(record["id"] for record in queued_records if record["paper_id"] == record_id)

        review_resp = await client.patch(
            f"/api/data/enzyme-metadata/curation-records/{accepted_id}/review",
            json={"status": "accepted", "reviewer_notes": "Identity requires family-specific upgrade script"},
        )
        direct_archive_resp = await client.patch(
            f"/api/data/enzyme-metadata/curation-records/{accepted_id}/review",
            json={"status": "archived", "reviewer_notes": "Should use batch archive"},
        )
        dry_run_batch_resp = await client.post(
            "/api/data/enzyme-metadata/curation-batches",
            json={"record_ids": [accepted_id], "dry_run": True},
        )
        create_batch_resp = await client.post(
            "/api/data/enzyme-metadata/curation-batches",
            json={"record_ids": [accepted_id], "dry_run": False},
        )

        assert review_resp.status_code == 200
        assert review_resp.json()["record"]["status"] == "accepted"
        assert direct_archive_resp.status_code == 422
        assert "batch workflow" in direct_archive_resp.json()["detail"]
        assert dry_run_batch_resp.status_code == 200
        batch_preview = dry_run_batch_resp.json()
        assert batch_preview["manifest"]["record_count"] == 1
        assert batch_preview["export_payload"]["sqlite_mutated"] is False
        assert batch_preview["export_payload"]["export_safe_released"] is False
        assert batch_preview["confirmation_token"] == "MANUAL_ENZYME_POLICY_DECISION_REVIEW"

        assert create_batch_resp.status_code == 200
        batch = create_batch_resp.json()["batch"]
        assert batch["status"] == "prepared"
        assert batch["record_ids"] == [accepted_id]

        wrong_archive_resp = await client.patch(
            f"/api/data/enzyme-metadata/curation-batches/{batch['id']}/archive",
            json={"confirmation": "wrong"},
        )
        archive_resp = await client.patch(
            f"/api/data/enzyme-metadata/curation-batches/{batch['id']}/archive",
            json={
                "confirmation": "MANUAL_ENZYME_POLICY_DECISION_REVIEW",
                "reviewer_notes": "Archived for future dry-run/backup/apply script",
            },
        )
        batches_resp = await client.get(
            "/api/data/enzyme-metadata/curation-batches",
            params={"status": "archived", "family": "acid_protease"},
        )

        assert wrong_archive_resp.status_code == 422
        assert archive_resp.status_code == 200
        archived = archive_resp.json()["batch"]
        assert archived["status"] == "archived"
        assert archived["archived_by_user_id"] == admin.id
        assert archived["export_payload"]["target"] == "manual_family_specific_metadata_upgrade_script"
        assert archived["export_payload"]["sqlite_mutated"] is False
        assert archived["export_payload"]["export_safe_released"] is False
        assert batches_resp.status_code == 200
        assert batches_resp.json()["count"] == 1

        stored_record = (
            await session.execute(
                select(EnzymeMetadataCurationRecord).where(EnzymeMetadataCurationRecord.id == accepted_id)
            )
        ).scalar_one()
        stored_batch = (
            await session.execute(select(EnzymeMetadataCurationBatch).where(EnzymeMetadataCurationBatch.id == batch["id"]))
        ).scalar_one()
        assert stored_record.status == "archived"
        assert stored_batch.status == "archived"

        after_stat = db_path.stat()
        assert after_stat.st_size == before_stat.st_size
        assert after_stat.st_mtime_ns == before_stat.st_mtime_ns
        with sqlite3.connect(db_path) as conn:
            assert conn.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        export_resp = await client.get("/api/data/enzyme-dbs/acid_protease/export-safe/measurements")
        assert export_resp.json()["count"] == 1

    async def test_experiment_feedback_records_go_decision_and_user_isolation(self, client: AsyncClient, session):
        owner = await _create_user(session, "experiment-feedback-owner@example.com")
        other = await _create_user(session, "experiment-feedback-other@example.com")
        await session.commit()

        client.cookies.set("pa_token", create_access_token(owner.id))
        submit_resp = await client.post(
            "/api/data/experiment-feedback",
            json={
                "enzyme_name": "KWB lipase",
                "variant_name": "M1",
                "parent_variant": "WT",
                "mutations": ["a10v"],
                "assay_payload": {"assay": "pNP ester activity"},
                "metrics_payload": {
                    "activity_retention_pct": 91,
                    "tm_delta_c": 2.4,
                    "soluble_expression_pct_wt": 96,
                },
                "quality_payload": {"sec_monomer_pct": 94},
                "notes": "First validated stability single mutant",
            },
        )

        client.cookies.set("pa_token", create_access_token(other.id))
        await client.post(
            "/api/data/experiment-feedback",
            json={
                "enzyme_name": "KWB lipase",
                "variant_name": "M2",
                "parent_variant": "WT",
                "mutations": ["D80N"],
                "metrics_payload": {"activity_retention_pct": 35, "tm_delta_c": -1},
                "quality_payload": {"sec_monomer_pct": 95},
            },
        )

        client.cookies.set("pa_token", create_access_token(owner.id))
        list_resp = await client.get("/api/data/experiment-feedback")
        summary_resp = await client.get("/api/data/experiment-feedback/summary")
        go_filter_resp = await client.get("/api/data/experiment-feedback", params={"decision": "go"})

        assert submit_resp.status_code == 200
        record = submit_resp.json()["record"]
        assert record["mutations"] == ["A10V"]
        assert record["interpretation_payload"]["decision"] == "go"
        assert record["interpretation_payload"]["strategy"] == "eligible_for_combination_design"
        assert set(record["interpretation_payload"]["positive_flags"]) >= {
            "activity_retention_ok",
            "tm_improved",
            "soluble_expression_ok",
            "sec_monomer_ok",
        }

        assert list_resp.status_code == 200
        assert list_resp.json()["count"] == 1
        assert list_resp.json()["records"][0]["created_by_user_id"] == owner.id
        assert go_filter_resp.status_code == 200
        assert go_filter_resp.json()["count"] == 1

        assert summary_resp.status_code == 200
        summary = summary_resp.json()
        assert summary["count"] == 1
        assert summary["decision_counts"]["go"] == 1
        assert summary["validated_single_mutants"][0]["mutation"] == "A10V"
        assert summary["next_strategy"] == "validate_one_more_orthogonal_single_mutant"
        assert summary["effect_classification_counts"]["unresolved"] == 1

        stored = (await session.execute(select(ExperimentFeedbackRecord))).scalars().all()
        assert len(stored) == 2

    async def test_experiment_feedback_iteration_plan_requires_protein_normalized_evidence(self, client: AsyncClient, session):
        owner = await _create_user(session, "experiment-feedback-plan@example.com")
        await session.commit()
        client.cookies.set("pa_token", create_access_token(owner.id))

        for mutation in ("A10V", "D80N"):
            response = await client.post(
                "/api/data/experiment-feedback",
                json={
                    "enzyme_name": "KWB lipase",
                    "variant_name": mutation,
                    "mutations": [mutation],
                    "assay_payload": {"sample_type": "purified_enzyme"},
                    "metrics_payload": {
                        "specific_activity_fold_vs_wt": 1.25,
                        "activity_retention_pct": 92,
                        "soluble_expression_pct_wt": 100,
                    },
                    "quality_payload": {"sec_monomer_pct": 95},
                },
            )
            assert response.status_code == 200

        plan_response = await client.post(
            "/api/data/experiment-feedback/iteration-plan",
            json={
                "enzyme_name": "KWB lipase",
                "objective": "specific_activity",
                "mechanism_tags": {
                    "A10V": ["core_packing", "activity_gain"],
                    "D80N": ["surface_charge", "activity_gain"],
                },
                "structural_distances": {"A10V:D80N": 20.0},
            },
        )

        assert plan_response.status_code == 200
        plan = plan_response.json()
        assert plan["status"] == "ready"
        assert plan["pair_candidates"][0]["label"] == "validated_singletons_pending_pair_test"

    async def test_wet_lab_calibration_preview_and_run_are_conservative(self, client: AsyncClient, session):
        owner = await _create_user(session, "wet-lab-calibration@example.com")
        await session.commit()
        client.cookies.set("pa_token", create_access_token(owner.id))

        for mutation in ("A10V", "D80N", "G120S"):
            response = await client.post(
                "/api/data/experiment-feedback",
                json={
                    "enzyme_name": "KWB lipase",
                    "variant_name": mutation,
                    "mutations": [mutation],
                    "assay_payload": {
                        "assay_type": "specific_activity",
                        "substrate": "pNP-C8",
                        "ph": 7.0,
                        "temperature_c": 37,
                        "sample_type": "purified_enzyme",
                    },
                    "metrics_payload": {
                        "specific_activity_fold_vs_wt": 1.3,
                        "activity_retention_pct": 90,
                        "soluble_expression_pct_wt": 95,
                    },
                    "quality_payload": {"sec_monomer_pct": 95},
                },
            )
            assert response.status_code == 200

        preview = await client.get(
            "/api/data/experiment-feedback/calibration-preview",
            params={"enzyme_name": "KWB lipase", "objective": "specific_activity"},
        )
        assert preview.status_code == 200
        payload = preview.json()
        assert payload["measured_variant_count"] == 3
        assert payload["go_count"] == 3
        assert payload["hit_rate"] == 1.0
        assert payload["evidence_level"] == "wet_lab_feedback"
        assert payload["data_quality_grade"] == "feedback_supported"
        assert "wet_lab_calibrated requires >=12" in payload["promotion_rule"]

        run_resp = await client.post(
            "/api/data/experiment-feedback/calibration-runs",
            json={"enzyme_name": "KWB lipase", "objective": "specific_activity"},
        )
        assert run_resp.status_code == 200
        calibration = run_resp.json()["calibration"]
        assert calibration["measured_variant_count"] == 3
        assert calibration["evidence_level"] == "wet_lab_feedback"

        duplicate_resp = await client.post(
            "/api/data/experiment-feedback/calibration-runs",
            json={"enzyme_name": "KWB lipase", "objective": "specific_activity"},
        )
        assert duplicate_resp.status_code == 200
        assert duplicate_resp.json()["calibration"]["id"] == calibration["id"]

        list_resp = await client.get("/api/data/experiment-feedback/calibration-runs")
        assert list_resp.status_code == 200
        assert list_resp.json()["records"][0]["dataset_fingerprint"] == calibration["dataset_fingerprint"]

        stored = (await session.execute(select(WetLabCalibrationRun))).scalars().all()
        assert len(stored) == 1

    async def test_lipase_curation_records_submit_and_admin_review(self, client: AsyncClient, session):
        researcher = await _create_user(session, "lipase-curation-user@example.com")
        admin = await _create_user(session, "lipase-curation-admin@example.com", role="admin")
        await session.commit()

        client.cookies.set("pa_token", create_access_token(researcher.id))
        submit_resp = await client.post(
            "/api/data/lipase/curation-records",
            json={
                "source_type": "tool_feedback",
                "paper_key": "Xie_2014",
                "mutation_code": "D223G",
                "position": 223,
                "linked_task_id": "audit-poll-task-id",
                "feedback_payload": {"used_in_recommendation": True},
                "notes": "Candidate accepted by user for follow-up experiment",
            },
        )
        list_as_user_resp = await client.get("/api/data/lipase/curation-records")

        assert submit_resp.status_code == 200
        submitted = submit_resp.json()["record"]
        assert submitted["status"] == "submitted"
        assert submitted["created_by_user_id"] == researcher.id
        assert submitted["feedback_payload"]["used_in_recommendation"] is True
        assert list_as_user_resp.status_code == 403

        stored = (await session.execute(select(LipaseCurationRecord))).scalar_one()
        assert stored.mutation_code == "D223G"

        client.cookies.set("pa_token", create_access_token(admin.id))
        list_resp = await client.get("/api/data/lipase/curation-records", params={"status": "submitted"})
        review_resp = await client.patch(
            f"/api/data/lipase/curation-records/{submitted['id']}/review",
            json={"status": "accepted", "reviewer_notes": "Ready for curated DB import batch"},
        )
        direct_publish_resp = await client.patch(
            f"/api/data/lipase/curation-records/{submitted['id']}/review",
            json={"status": "published", "reviewer_notes": "Should use batch publish"},
        )

        assert list_resp.status_code == 200
        assert list_resp.json()["count"] == 1
        assert review_resp.status_code == 200
        assert direct_publish_resp.status_code == 422
        assert "batch workflow" in direct_publish_resp.json()["detail"]
        reviewed = review_resp.json()["record"]
        assert reviewed["status"] == "accepted"
        assert reviewed["reviewed_by_user_id"] == admin.id
        assert reviewed["reviewer_notes"] == "Ready for curated DB import batch"

    async def test_lipase_curation_batch_requires_accepted_records_and_publish_confirmation(self, client: AsyncClient, session):
        researcher = await _create_user(session, "lipase-curation-batch-user@example.com")
        admin = await _create_user(session, "lipase-curation-batch-admin@example.com", role="admin")
        await session.commit()

        client.cookies.set("pa_token", create_access_token(researcher.id))
        submit_resp = await client.post(
            "/api/data/lipase/curation-records",
            json={
                "source_type": "literature",
                "paper_key": "New_Lipase_2026",
                "title": "New thermostable lipase evidence",
                "mutation_code": "A10V",
                "position": 10,
                "evidence_payload": {"metric": "half_life", "direction": "improved"},
            },
        )
        record_id = submit_resp.json()["record"]["id"]

        client.cookies.set("pa_token", create_access_token(admin.id))
        await client.patch(
            f"/api/data/lipase/curation-records/{record_id}/review",
            json={"status": "accepted", "reviewer_notes": "Source checked"},
        )

        dry_run_resp = await client.post(
            "/api/data/lipase/curation-batches",
            json={"record_ids": [record_id], "dry_run": True},
        )
        invalid_dry_run_resp = await client.post(
            "/api/data/lipase/curation-batches",
            json={"record_ids": [record_id, 999999], "dry_run": True},
        )
        create_resp = await client.post(
            "/api/data/lipase/curation-batches",
            json={"record_ids": [record_id], "dry_run": False},
        )

        assert dry_run_resp.status_code == 200
        dry_run = dry_run_resp.json()
        assert dry_run["status"] == "planned"
        assert dry_run["manifest"]["record_count"] == 1
        assert dry_run["export_payload"]["read_only_source_db"] is True
        assert dry_run["confirmation_token"] == "PUBLISH_LIPASE_CURATION_BATCH"
        assert invalid_dry_run_resp.status_code == 422
        assert "missing_or_unaccepted" in invalid_dry_run_resp.json()["detail"]

        assert create_resp.status_code == 200
        batch = create_resp.json()["batch"]
        assert batch["status"] == "prepared"
        assert batch["record_ids"] == [record_id]

        wrong_publish_resp = await client.patch(
            f"/api/data/lipase/curation-batches/{batch['id']}/publish",
            json={"confirmation": "wrong"},
        )
        publish_resp = await client.patch(
            f"/api/data/lipase/curation-batches/{batch['id']}/publish",
            json={"confirmation": "PUBLISH_LIPASE_CURATION_BATCH", "reviewer_notes": "Published through manual release"},
        )
        list_resp = await client.get("/api/data/lipase/curation-batches", params={"status": "published"})

        assert wrong_publish_resp.status_code == 422
        assert publish_resp.status_code == 200
        published = publish_resp.json()["batch"]
        assert published["status"] == "published"
        assert published["published_by_user_id"] == admin.id
        assert published["reviewer_notes"] == "Published through manual release"
        assert list_resp.status_code == 200
        assert list_resp.json()["count"] == 1

        stored_record = (await session.execute(select(LipaseCurationRecord).where(LipaseCurationRecord.id == record_id))).scalar_one()
        stored_batch = (await session.execute(select(LipaseCurationBatch).where(LipaseCurationBatch.id == batch["id"]))).scalar_one()
        assert stored_record.status == "published"
        assert stored_batch.status == "published"

    async def test_list_benchmarks(self, client: AsyncClient):
        resp = await client.get("/api/data/benchmarks")
        assert resp.status_code == 200
        data = resp.json()
        assert data["count"] >= 1
        case = next(item for item in data["benchmarks"] if item["id"] == "venus-15b")
        assert case["sequence_length"] == 486
        assert case["candidate_mutation_count"] == 4
        assert case["maturity"] in {"delivery-ready", "bundle-ready", "structure-ready", "staged", "seed-only"}
        assert case["bundle_download_url"] == "/api/data/benchmarks/venus-15b/bundle/download"
        assert case["asset_status"]["source_bundle_ready"] is True
        assert case["asset_status"]["foldseek_indexed"] is True
        assert case["asset_counts"]["foldseek_pdb_entries"] == 1
        assert "discovered_reference_docs" in case["asset_counts"]
        assert "bundle_ready" in case["asset_status"]
        assert "bundle_archive_ready" in case["asset_status"]
        assert "reference_docs_ready" in case["asset_status"]

    async def test_get_benchmark_case(self, client: AsyncClient):
        resp = await client.get("/api/data/benchmarks/venus-15b")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "venus-15b"
        assert data["program"] == "Venus-15B淀粉酶项目"
        assert data["target_ph_range"]["focus"] == 4.5
        assert data["candidate_mutations"][0]["mutation"] == "M204H"
        assert data["paths"]["source_bundle_dir"]["exists"] is True
        assert data["paths"]["deploy_structure_file"]["relative_path"] == "deploy_data/pdb/local_cases/15B-AAP-noCa.pdb"
        assert data["paths"]["incoming_alphafold_dir"]["exists"] is True
        assert data["status"]["foldseek_indexed"] is True
        assert data["status"]["asset_counts"]["foldseek_pdb_entries"] == 1
        assert "discovery_report_ready" in data["status"]
        assert "bundle_ready" in data["status"]
        assert "bundle_archive_ready" in data["status"]
        assert "reference_doc_manifest_ready" in data["status"]
        assert "bundle" in data
        assert data["bundle"]["download_url"] == "/api/data/benchmarks/venus-15b/bundle/download"

    async def test_download_benchmark_bundle(self, client: AsyncClient):
        resp = await client.get("/api/data/benchmarks/venus-15b/bundle/download")
        assert resp.status_code == 200
        assert resp.headers["content-type"].startswith("application/gzip")

    async def test_head_benchmark_bundle(self, client: AsyncClient):
        resp = await client.head("/api/data/benchmarks/venus-15b/bundle/download")
        assert resp.status_code == 200
        assert resp.headers["content-type"].startswith("application/gzip")
        assert resp.content == b""

    async def test_benchmark_case_not_found(self, client: AsyncClient):
        resp = await client.get("/api/data/benchmarks/unknown-case")
        assert resp.status_code == 404


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
        assert data["counts"]["interpro_annotations"] == 1
        assert data["counts"]["catalytic_sites"] == 1
        assert data["annotation_summary"]["protected_positions"] == [3]

    async def test_protein_annotations(self, client: AsyncClient, session):
        await _seed(session)

        resp = await client.get("/api/data/protein/P00001/annotations")
        assert resp.status_code == 200
        data = resp.json()
        assert data["counts"]["interpro_annotations"] == 1
        assert data["annotations"][0]["interpro_id"] == "IPR029058"

    async def test_protein_catalytic_sites(self, client: AsyncClient, session):
        await _seed(session)

        resp = await client.get("/api/data/protein/P00001/catalytic-sites")
        assert resp.status_code == 200
        data = resp.json()
        assert data["count"] == 1
        assert data["protected_positions"] == [3]
        assert data["sites"][0]["residues"][0]["role"] == "nucleophile"
        assert data["mechanism_profile"]["schema_version"] == "catalytic_mechanism_profile_v1"
        assert data["mechanism_profile"]["first_shell_positions"] == [3]
        assert data["mechanism_profile"]["user_coordinate"]["status"] == "verified"
        assert data["mechanism_profile"]["report_contract"]["claim_status"] == "SUPPORTED"
        assert data["mechanism_profile"]["report_contract"]["must_not_claim_second_shell"] is True

    async def test_protein_signal_peptide(self, client: AsyncClient, session):
        await _seed(session)

        resp = await client.get("/api/data/protein/P00001/signal-peptide")
        assert resp.status_code == 200
        data = resp.json()
        assert data["found"] is True
        assert data["has_signal_peptide"] is False

    async def test_protein_annotation_bundle(self, client: AsyncClient, session):
        await _seed(session)

        resp = await client.get("/api/data/protein/P00001/annotation-bundle")
        assert resp.status_code == 200
        data = resp.json()
        assert data["found"] is True
        assert data["interpro"]["summary"]["curated_interpro_count"] == 1
        assert data["catalytic_sites"]["protected_positions"] == [3]
        assert data["signal_peptide"]["has_signal_peptide"] is False

    async def test_protein_reaction_profile(self, client: AsyncClient, session):
        await _seed(session)

        resp = await client.get("/api/data/protein/P00001/reaction-profile")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ready"
        assert data["reaction_candidates"][0]["rhea_id"] == 99999
        assert data["reaction_candidates"][0]["matched_ec_numbers"] == ["1.1.1.99"]
        assert data["reaction_candidates"][0]["match_basis"] == "exact_local_ec_intersection"
        assert data["claim_context"]["reaction_claim_status"] == "SUPPORTED"
        assert data["claim_context"]["substrate_scope_status"] == "SUPPORTED"
        assert data["report_contract"]["must_label_local_exact_ec_mapping"] is True
        assert data["evidence_source"]["live_query_executed"] is False

    async def test_protein_reaction_profile_not_found(self, client: AsyncClient):
        resp = await client.get("/api/data/protein/UNKNOWN/reaction-profile")
        assert resp.status_code == 404

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
        assert counts["interpro_entries"] >= 1
        assert counts["catalytic_sites"] >= 1
        assert counts["signal_peptide_predictions"] >= 1

        assert data["data_scope"] == "browser_stats_full_domain_plus_deploy_assets"
        assert data["export_safe"] is False
        assert data["import_scope"]["deploy_data_import"] == "file_staging_only"
        assert (
            data["import_scope"]["sqlite_to_pg_domain_import"]
            == "full_domain_restore_not_export_safe_not_training_safe_not_a_only"
        )
        assert "ingest:uniprot:hash" in data["ingestion_hashes"]

    async def test_stats_uses_deploy_data_fallback_when_database_empty(self, client: AsyncClient, tmp_path, monkeypatch):
        annotations = tmp_path / "annotations"
        annotations.mkdir()
        (annotations / "base.json").write_text(
            json.dumps(
                [
                    {
                        "taxonomy": {"ncbi_taxid": 1390},
                        "enzyme": {"uniprot_id": "P00692"},
                        "ec_numbers": [{"ec_number": "3.2.1.1"}],
                        "pfam_domains": [{"pfam_id": "PF00128"}],
                    }
                ]
            ),
            encoding="utf-8",
        )
        (annotations / "interpro.json").write_text(json.dumps([{"interpro_id": "IPR006047"}]), encoding="utf-8")
        (annotations / "mcsa.json").write_text(
            json.dumps([{"reaction_text": "hydrolysis", "residues": [{"residue_pos": 1}, {"residue_pos": 2}]}]),
            encoding="utf-8",
        )
        (annotations / "signalp.json").write_text(json.dumps([{"uniprot_id": "P00692"}]), encoding="utf-8")

        monkeypatch.setattr(
            "app.api.data.collect_deploy_data_readiness",
            lambda: {
                "root": {"path": str(tmp_path), "exists": True},
                "components": {
                    "pdb": {"count": 8},
                    "alphafold": {"count": 5},
                    "sifts": {"count": 7},
                },
            },
        )
        monkeypatch.setattr(
            "app.api.data.collect_lipase_db_status",
            lambda: {
                "status": "ready",
                "summary": {
                    "variant_count": 12,
                    "claim_count": 12,
                    "metric_count": 12,
                    "substrate_count": 7,
                },
            },
        )

        resp = await client.get("/api/data/stats")
        assert resp.status_code == 200
        data = resp.json()
        counts = data["counts"]
        assert data["database_counts"]["enzyme_records"] == 0
        assert data["asset_counts"]["enzyme_records"] == 1
        assert counts["enzyme_records"] == 1
        assert counts["ec_numbers"] == 1
        assert counts["pdb_structures"] == 8
        assert counts["alphafold_structures"] == 5
        assert counts["kinetic_parameters"] == 12
        assert counts["stability_records"] == 12
        assert counts["substrate_compounds"] == 7
        assert counts["reaction_equations"] == 1
        assert data["data_scope"] == "browser_stats_full_domain_plus_deploy_assets"
        assert data["export_safe"] is False
        assert (
            data["import_scope"]["sqlite_to_pg_domain_import"]
            == "full_domain_restore_not_export_safe_not_training_safe_not_a_only"
        )
