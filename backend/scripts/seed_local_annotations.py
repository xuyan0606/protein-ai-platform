#!/usr/bin/env python
"""Seed repeatable local InterPro/M-CSA/signal-peptide demo annotations."""

from __future__ import annotations

import asyncio
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


async def main() -> None:
    from app.core.database import dispose_engine, init_db, session_scope
    from app.data.ingestor_registry import ingest_source
    import app.data.ingestors.local_annotations  # noqa: F401

    await init_db()
    async with session_scope() as session:
        report = await ingest_source("local_annotations", session, force=True)
        logger.info("seed result: %s", report.to_dict())
    await dispose_engine()


if __name__ == "__main__":
    asyncio.run(main())
