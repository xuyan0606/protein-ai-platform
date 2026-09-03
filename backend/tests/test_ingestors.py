"""White-box tests: ingestor framework, registry, base class."""

import json
import tempfile
from pathlib import Path

import pytest
from sqlalchemy import select


class TestIngestorRegistry:
    def test_register_and_list(self):
        from app.data.base_ingestor import BaseIngestor, IngestReport
        from app.data.ingestor_registry import register, list_sources, _registry

        # Clear for test
        _registry.clear()

        @register("test_source")
        class TestIngestor(BaseIngestor):
            source_name = "test_source"

            async def _download_raw(self) -> Path:
                p = self.cache_dir / "test.json"
                p.write_text(json.dumps([{"id": 1, "name": "test"}]))
                return p

            async def _store_batch(self, batch):
                return (len(batch), 0)

        assert "test_source" in list_sources()
        assert list_sources() == ["test_source"]
        _registry.clear()

    async def test_ingest_source_unknown(self):
        from app.data.ingestor_registry import ingest_source
        with pytest.raises(KeyError, match="unknown"):
            await ingest_source("nonexistent", None)


class TestIngestReport:
    def test_report_basics(self):
        from app.data.base_ingestor import IngestReport, IngestStatus
        r = IngestReport(source="test")
        assert r.status == IngestStatus.PENDING
        assert r.total_processed == 0
        d = r.to_dict()
        assert d["source"] == "test"
        assert d["status"] == "pending"

    def test_report_with_data(self):
        from app.data.base_ingestor import IngestReport, IngestStatus
        from datetime import datetime, timezone
        r = IngestReport(
            source="test", status=IngestStatus.COMPLETED,
            items_created=10, items_updated=3, items_skipped=2, items_failed=1,
            started_at=datetime.now(timezone.utc),
            finished_at=datetime.now(timezone.utc),
        )
        assert r.total_processed == 15
        d = r.to_dict()
        assert d["items_created"] == 10
        assert d["items_failed"] == 1


class TestBaseIngestor:
    def test_file_hash(self):
        from app.data.base_ingestor import BaseIngestor
        p = Path(tempfile.gettempdir()) / "test_hash.txt"
        p.write_text("hello world")
        h1 = BaseIngestor._file_hash(p)
        h2 = BaseIngestor._file_hash(p)
        assert h1 == h2
        p.write_text("different content")
        h3 = BaseIngestor._file_hash(p)
        assert h1 != h3
        p.unlink(missing_ok=True)

    def test_directory_hash(self):
        from app.data.base_ingestor import BaseIngestor
        d = Path(tempfile.mkdtemp(prefix="test_hash_dir_"))
        try:
            (d / "a.json").write_text('{"a": 1}')
            (d / "nested").mkdir()
            (d / "nested" / "b.json").write_text('{"b": 2}')
            h1 = BaseIngestor._file_hash(d)
            h2 = BaseIngestor._file_hash(d)
            assert h1 == h2
            (d / "nested" / "b.json").write_text('{"b": 3}')
            assert BaseIngestor._file_hash(d) != h1
        finally:
            for child in sorted(d.rglob("*"), reverse=True):
                if child.is_file():
                    child.unlink()
                else:
                    child.rmdir()
            d.rmdir()


class TestIngestorRun:
    async def test_run_pipeline(self, session):
        """Test full run() pipeline with a minimal test ingestor."""
        from app.data.base_ingestor import BaseIngestor, IngestStatus
        from app.data.ingestor_registry import register, _registry

        _registry.clear()

        @register("mini_test")
        class MiniIngestor(BaseIngestor):
            source_name = "mini_test"
            chunk_size = 5

            async def _download_raw(self) -> Path:
                p = self.cache_dir / "mini.json"
                p.write_text(json.dumps([{"n": i} for i in range(12)]))
                return p

            async def _store_batch(self, batch):
                for item in batch:
                    session.add(MiniRecord(n=item["n"]))
                await session.commit()
                return (len(batch), 0)

        from app.models.base import Base as DeclBase
        from sqlalchemy.orm import Mapped, mapped_column
        from sqlalchemy import Integer

        class MiniRecord(DeclBase):
            __tablename__ = "mini_test_records"
            id: Mapped[int] = mapped_column(Integer, primary_key=True)
            n: Mapped[int] = mapped_column(Integer)

        # Create the test table
        async with session.bind.begin() as conn:
            await conn.run_sync(DeclBase.metadata.create_all)

        from app.data.ingestor_registry import ingest_source
        report = await ingest_source("mini_test", session, force=True)

        assert report.status == IngestStatus.COMPLETED
        assert report.items_created == 12
        assert report.errors == []

        # Verify data persisted
        rows = await session.execute(select(MiniRecord.n))
        ns = sorted(r[0] for r in rows.fetchall())
        assert ns == list(range(12))

        # Cleanup
        async with session.bind.begin() as conn:
            await conn.run_sync(DeclBase.metadata.drop_all)
        _registry.clear()

    async def test_local_annotations_ingestor(self, session, monkeypatch):
        from app.data.ingestor_registry import ingest_source
        import app.data.ingestors.local_annotations  # noqa: F401
        from app.core.config import settings
        from app.models.domain import (
            EnzymeRecord,
            EnzymeInterProLink,
            CatalyticSite,
            SignalPeptidePrediction,
        )
        from sqlalchemy import func

        fixture_dir = Path(__file__).resolve().parent.parent / "app" / "data" / "fixtures" / "local_annotations"
        monkeypatch.setattr(settings, "LOCAL_ANNOTATION_FIXTURE_PATH", str(fixture_dir))

        report = await ingest_source("local_annotations", session, force=True)
        assert report.status.value == "completed"
        assert report.items_failed == 0

        enzyme_rows = await session.execute(
            select(EnzymeRecord.uniprot_id).where(EnzymeRecord.uniprot_id.in_(["DEMO388A", "SIGDEMO1"]))
        )
        assert sorted(row[0] for row in enzyme_rows.fetchall()) == ["DEMO388A", "SIGDEMO1"]

        interpro_count = await session.scalar(select(func.count()).select_from(EnzymeInterProLink))
        catalytic_count = await session.scalar(select(func.count()).select_from(CatalyticSite))
        signal_count = await session.scalar(select(func.count()).select_from(SignalPeptidePrediction))
        assert interpro_count >= 1
        assert catalytic_count >= 1
        assert signal_count >= 2

    def test_local_annotations_structured_fixture_parser(self):
        from app.data.ingestors.local_annotations import _parse_structured_fixture

        fixture_dir = Path(__file__).resolve().parent.parent / "app" / "data" / "fixtures" / "local_annotations"
        records = _parse_structured_fixture(fixture_dir)
        by_id = {record["enzyme"]["uniprot_id"]: record for record in records}

        assert sorted(by_id) == ["DEMO388A", "SIGDEMO1"]
        assert by_id["DEMO388A"]["enzyme"]["source_version"] == "2026-07-04"
        assert len(by_id["DEMO388A"]["interpro_annotations"]) >= 3
        assert len(by_id["DEMO388A"]["catalytic_sites"]) == 1
        assert by_id["SIGDEMO1"]["signal_peptide_prediction"]["has_signal_peptide"] is True

    def test_local_annotations_structured_fixture_parser_supports_csv_tsv(self, tmp_path):
        from app.data.ingestors.local_annotations import _parse_structured_fixture

        (tmp_path / "metadata.json").write_text(
            json.dumps(
                {
                    "dataset_name": "tabular-demo",
                    "dataset_version": "2026-07-04-tabular",
                    "default_source_db": "tabular_demo",
                }
            ),
            encoding="utf-8",
        )
        (tmp_path / "base.csv").write_text(
            "\n".join(
                [
                    "uniprot_id,name,sequence,scientific_name,ec_numbers,pfam_domains",
                    'TAB001,Tabular enzyme,MSTNPKPQRITESTSEQ,Tabular species,"[{""ec_number"": ""3.2.1.4"", ""description"": ""demo ec"", ""is_primary"": true}]","[{""pfam_id"": ""PF00001"", ""name"": ""Demo domain"", ""start_pos"": 2, ""end_pos"": 8}]"',
                ]
            ),
            encoding="utf-8",
        )
        (tmp_path / "interpro.tsv").write_text(
            "\n".join(
                [
                    "uniprot_id\tinterpro_id\tentry_type\tname\tsource_db\tstart_pos\tend_pos",
                    "TAB001\tIPR000001\tDomain\tTabular domain\tinterpro\t2\t9",
                ]
            ),
            encoding="utf-8",
        )
        (tmp_path / "signalp.csv").write_text(
            "\n".join(
                [
                    "uniprot_id,has_signal_peptide,probability,predicted_cleavage_pos,model",
                    "TAB001,true,0.98,23,signalp6",
                ]
            ),
            encoding="utf-8",
        )

        records = _parse_structured_fixture(tmp_path)

        assert len(records) == 1
        record = records[0]
        assert record["enzyme"]["uniprot_id"] == "TAB001"
        assert record["enzyme"]["source_version"] == "2026-07-04-tabular"
        assert record["taxonomy"]["scientific_name"] == "Tabular species"
        assert record["ec_numbers"][0]["ec_number"] == "3.2.1.4"
        assert record["pfam_domains"][0]["pfam_id"] == "PF00001"
        assert record["interpro_annotations"][0]["interpro_id"] == "IPR000001"
        assert record["signal_peptide_prediction"]["has_signal_peptide"] is True

    def test_taxonomy_aliases_match_model_fields(self):
        from app.services.annotation_dataset_service import _normalize_taxonomy_payload

        payload = _normalize_taxonomy_payload(
            {
                "scientific_name": "Bacillus amyloliquefaciens",
                "kingdom": "Bacteria",
                "class_name": "Bacilli",
                "order_name": "Bacillales",
                "species": "Bacillus amyloliquefaciens",
                "unexpected": "ignored",
            }
        )

        assert payload["superkingdom"] == "Bacteria"
        assert payload["tax_class"] == "Bacilli"
        assert payload["order_"] == "Bacillales"
        assert "kingdom" not in payload
        assert "class_name" not in payload
        assert "order_name" not in payload
        assert "species" not in payload
        assert "unexpected" not in payload
