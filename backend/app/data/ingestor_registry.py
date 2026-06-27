"""Registry of all data source ingestors with Celery task dispatch."""

from __future__ import annotations

import logging
from typing import Type

from sqlalchemy.ext.asyncio import AsyncSession

from app.data.base_ingestor import BaseIngestor, IngestReport

logger = logging.getLogger(__name__)

_registry: dict[str, Type[BaseIngestor]] = {}


def register(source_name: str):
    """Decorator that registers an ingestor class under a source name."""
    def wrapper(cls: Type[BaseIngestor]) -> Type[BaseIngestor]:
        cls.source_name = source_name
        _registry[source_name] = cls
        logger.info("registered ingestor: %s", source_name)
        return cls
    return wrapper


def list_sources() -> list[str]:
    return sorted(_registry.keys())


async def ingest_source(source: str, db: AsyncSession, force: bool = False) -> IngestReport:
    """Run a single ingestor by name."""
    cls = _registry.get(source)
    if cls is None:
        raise KeyError(f"unknown data source: {source}")
    ingestor = cls(db)
    try:
        return await ingestor.run(force=force)
    finally:
        await ingestor.close()


async def ingest_all(db: AsyncSession, force: bool = False) -> list[IngestReport]:
    """Run all registered ingestors sequentially."""
    reports = []
    for name in sorted(_registry):
        try:
            report = await ingest_source(name, db, force=force)
            reports.append(report)
        except Exception as e:
            logger.exception("ingestor %s failed: %s", name, e)
            reports.append(IngestReport(source=name, errors=[str(e)]))
    return reports
