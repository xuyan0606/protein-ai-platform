#!/usr/bin/env python
"""Run data ingestion for REST-based sources: UniProt, PDB, PubChem, Rhea.

Usage:
    .venv/bin/python scripts/ingest_data.py              # all sources
    .venv/bin/python scripts/ingest_data.py uniprot      # single source
    .venv/bin/python scripts/ingest_data.py --force      # skip hash check
"""

import asyncio
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(levelname)s: %(message)s")
logger = logging.getLogger("ingest")

# Force SQLite for local dev
import os
os.environ.setdefault("USE_SQLITE", "true")


async def main():
    from app.core.database import init_db, dispose_engine, session_scope
    from app.data.ingestor_registry import ingest_source, list_sources

    # Register all ingestors
    import app.data.ingestors.uniprot  # noqa
    import app.data.ingestors.pdb  # noqa
    import app.data.ingestors.pubchem  # noqa
    import app.data.ingestors.rhea  # noqa

    await init_db()
    logger.info("database initialized")

    force = "--force" in sys.argv
    sources = list_sources()
    logger.info("available sources: %s", sources)

    target = [a for a in sys.argv[1:] if not a.startswith("-") and a != "ingest_data.py"]
    if target:
        sources = [s for s in target if s in sources]

    for name in sources:
        logger.info("===== INGESTING: %s =====", name)
        async with session_scope() as session:
            try:
                report = await ingest_source(name, session, force=force)
                d = report.to_dict()
                logger.info("result: %s %s — created=%d updated=%d skipped=%d failed=%d errors=%s",
                    d["source"], d["status"],
                    d["items_created"], d["items_updated"],
                    d["items_skipped"], d["items_failed"],
                    d["errors"][:3])
            except Exception as e:
                logger.exception("ingest %s FAILED", name)

    await dispose_engine()
    logger.info("done")


if __name__ == "__main__":
    asyncio.run(main())
