"""Base class for all data source ingestors.

Standard pipeline: download → parse → validate → store
Supports incremental updates (content-hash diffing) and resumable downloads.
"""

from __future__ import annotations

import hashlib
import json
import tempfile
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, AsyncIterator

import httpx
from sqlalchemy import text, insert, inspect
from sqlalchemy.ext.asyncio import AsyncSession


class IngestStatus(Enum):
    PENDING = "pending"
    DOWNLOADING = "downloading"
    PARSING = "parsing"
    STORING = "storing"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"  # no change detected


@dataclass
class IngestReport:
    source: str
    status: IngestStatus = IngestStatus.PENDING
    items_created: int = 0
    items_updated: int = 0
    items_skipped: int = 0
    items_failed: int = 0
    errors: list[str] = field(default_factory=list)
    started_at: datetime | None = None
    finished_at: datetime | None = None
    content_hash: str | None = None

    @property
    def total_processed(self) -> int:
        return self.items_created + self.items_updated + self.items_skipped

    def to_dict(self) -> dict:
        return {
            "source": self.source,
            "status": self.status.value,
            "items_created": self.items_created,
            "items_updated": self.items_updated,
            "items_skipped": self.items_skipped,
            "items_failed": self.items_failed,
            "errors": self.errors[-10:],
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "finished_at": self.finished_at.isoformat() if self.finished_at else None,
        }


class BaseIngestor(ABC):
    """Abstract ingestor for a single data source.

    Subclass and implement _download_raw(), _parse_records(), _store_batch().
    The run() method orchestrates the full pipeline with error handling and
    incremental-update support via content hash.
    """

    source_name: str = ""           # e.g. "uniprot", "brenda", "pubchem"
    chunk_size: int = 200           # batch size for DB inserts
    request_delay: float = 0.3      # seconds between API requests (rate limiting)

    def __init__(self, db: AsyncSession, cache_dir: Path | None = None):
        self.db = db
        self.cache_dir = cache_dir or Path(tempfile.gettempdir()) / "protein_ai_ingest"
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self._client: httpx.AsyncClient | None = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def run(self, force: bool = False) -> IngestReport:
        """Execute the full ingestion pipeline."""
        report = IngestReport(source=self.source_name, started_at=datetime.now(timezone.utc))
        try:
            report.status = IngestStatus.DOWNLOADING
            raw_path = await self._download_raw()

            if not force and await self._unchanged(raw_path):
                report.status = IngestStatus.SKIPPED
                report.finished_at = datetime.now(timezone.utc)
                return report

            report.status = IngestStatus.PARSING
            records = await self._parse_raw(raw_path)

            report.status = IngestStatus.STORING
            async for batch in self._batch(records):
                try:
                    created, updated = await self._store_batch(batch)
                    report.items_created += created
                    report.items_updated += updated
                except Exception as e:
                    report.items_failed += len(batch)
                    report.errors.append(f"store batch: {e}")

            await self._save_hash(raw_path, report)
            report.status = IngestStatus.COMPLETED
        except Exception as e:
            report.status = IngestStatus.FAILED
            report.errors.append(str(e))
        finally:
            report.finished_at = datetime.now(timezone.utc)
        return report

    # ------------------------------------------------------------------
    # Subclass hooks
    # ------------------------------------------------------------------

    @abstractmethod
    async def _download_raw(self) -> Path:
        """Download source data. Return path to raw file."""
        ...

    async def _parse_raw(self, raw_path: Path) -> list[dict]:
        """Parse raw data into list of record dicts (default: from JSON)."""
        return json.loads(raw_path.read_text())

    @abstractmethod
    async def _store_batch(self, batch: list[dict]) -> tuple[int, int]:
        """Persist one batch to the database. Returns (created, updated)."""
        ...

    # ------------------------------------------------------------------
    # Utilities for subclasses
    # ------------------------------------------------------------------

    @property
    def http(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(60.0),
                headers={"User-Agent": "ProteinAI-DataIngestor/1.0"},
            )
        return self._client

    async def close(self) -> None:
        if self._client:
            await self._client.aclose()
            self._client = None

    async def _upsert(self, model, values: dict, index_elements: list[str], update_keys: list[str] | None = None) -> bool:
        """Dialect-agnostic upsert. Returns True if inserted (created), False if updated.

        Uses the session's bound dialect to pick the right insert() variant
        so on_conflict_do_update works on both SQLite and PostgreSQL.
        """
        from sqlalchemy.dialects import sqlite as sqld, postgresql as pgd

        bind = self.db.get_bind()
        dialect_name = bind.dialect.name if bind else "sqlite"
        insert_fn = pgd.insert if dialect_name == "postgresql" else sqld.insert

        keys = update_keys or [k for k in values if k not in index_elements]
        keys = [k for k in keys if k in values]  # only keys actually in the values dict
        stmt = insert_fn(model).values(**values)
        stmt = stmt.on_conflict_do_update(
            index_elements=index_elements,
            set_={k: values[k] for k in keys},
        )
        result = await self.db.execute(stmt)
        return result.rowcount == 1

    async def _unchanged(self, raw_path: Path) -> bool:
        """Check whether raw content matches the last stored hash."""
        h = self._file_hash(raw_path)
        stored = await self._stored_hash()
        return h == stored

    async def _stored_hash(self) -> str | None:
        row = await self.db.execute(
            text("SELECT value FROM kv_store WHERE key = :k"),
            {"k": f"ingest:{self.source_name}:hash"},
        )
        result = row.scalar()
        return str(result) if result else None

    async def _save_hash(self, raw_path: Path, report: IngestReport) -> None:
        h = self._file_hash(raw_path)
        report.content_hash = h
        await self.db.execute(
            text(
                "INSERT INTO kv_store (key, value) VALUES (:k, :v) "
                "ON CONFLICT (key) DO UPDATE SET value = :v"
            ),
            {"k": f"ingest:{self.source_name}:hash", "v": h},
        )
        await self.db.commit()

    @staticmethod
    def _file_hash(path: Path) -> str:
        sha = hashlib.sha256()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                sha.update(chunk)
        return sha.hexdigest()

    @staticmethod
    async def _batch(records: list[dict], size: int | None = None) -> AsyncIterator[list[dict]]:
        """Yield records in batches."""
        s = size or BaseIngestor.chunk_size
        for i in range(0, len(records), s):
            yield records[i : i + s]
