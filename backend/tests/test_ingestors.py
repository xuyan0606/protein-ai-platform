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
