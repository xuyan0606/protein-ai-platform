"""Index enzyme sequences into Zvec vector store using ESM-2 embeddings.

Usage:
    python scripts/index_enzyme_vectors.py [--limit N] [--batch-size B]

Fetches enzyme sequences from DB, computes ESM-2 mean embeddings,
and stores them in Zvec for fast semantic enzyme search.
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select

from app.core.database import session_scope
from app.models.domain import EnzymeRecord
from app.ml.embeddings import get_mean_embedding
from app.ml.vector_search import EnzymeVectorSearch

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


async def main(limit: int = 0, batch_size: int = 50, offset: int = 0):
    vs = EnzymeVectorSearch()
    current_count = vs.count()
    logger.info("Zvec index currently has %d vectors", current_count)

    async with session_scope() as db:
        from sqlalchemy import func
        total = await db.scalar(
            select(func.count(EnzymeRecord.id)).where(
                EnzymeRecord.sequence.isnot(None),
                EnzymeRecord.sequence != "",
            )
        )
        logger.info("Total enzymes with sequences: %d", total)

        query = (
            select(EnzymeRecord.id, EnzymeRecord.uniprot_id, EnzymeRecord.sequence)
            .where(
                EnzymeRecord.sequence.isnot(None),
                EnzymeRecord.sequence != "",
            )
            .order_by(EnzymeRecord.id)
            .offset(offset)
        )
        if limit > 0:
            query = query.limit(limit)

        rows = (await db.execute(query)).fetchall()

    logger.info("Fetched %d enzymes. Starting embedding extraction...", len(rows))

    batch_items = []
    indexed = 0
    skipped = 0

    for i, (enzyme_id, uniprot_id, sequence) in enumerate(rows):
        if i % 10 == 0:
            logger.info("Progress: %d/%d (indexed: %d, skipped: %d)", i, len(rows), indexed, skipped)

        try:
            embedding = get_mean_embedding(sequence)
            batch_items.append((enzyme_id, uniprot_id, embedding))

            if len(batch_items) >= batch_size:
                n = vs.index_enzymes_batch(batch_items)
                indexed += n
                batch_items = []
        except Exception as e:
            logger.warning("Skip %s: %s", uniprot_id, e)
            skipped += 1

    if batch_items:
        n = vs.index_enzymes_batch(batch_items)
        indexed += n

    logger.info("Done. Indexed: %d, Skipped: %d, Total in Zvec: %d", indexed, skipped, vs.count())


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Index enzyme vectors into Zvec")
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--batch-size", type=int, default=50)
    parser.add_argument("--offset", type=int, default=0)
    args = parser.parse_args()
    asyncio.run(main(limit=args.limit, batch_size=args.batch_size, offset=args.offset))
