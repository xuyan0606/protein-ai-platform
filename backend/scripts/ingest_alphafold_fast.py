"""Fast AlphaFold ingestion using concurrent EBI API calls.

Uses high-concurrency async HTTP to query the EBI AlphaFold DB API
for all enzymes that have PDB structures.

Usage:
    python scripts/ingest_alphafold_fast.py [--concurrency 50] [--limit N]
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select
from app.core.database import session_scope
from app.models.domain import EnzymeRecord, PDBStructure, AlphaFoldStructure

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

AFDB_BASE = "https://alphafold.ebi.ac.uk/api"
AFDB_FILES = "https://alphafold.ebi.ac.uk/files"


async def fetch_af_entry(
    client: httpx.AsyncClient,
    enzyme_id: int,
    uniprot_id: str,
    sem: asyncio.Semaphore,
) -> dict | None:
    """Fetch AlphaFold prediction metadata for a single UniProt ID."""
    async with sem:
        try:
            resp = await client.get(
                f"{AFDB_BASE}/prediction/{uniprot_id}",
                timeout=30.0,
            )
            if resp.status_code == 404:
                return None
            if resp.status_code == 429:
                await asyncio.sleep(2.0)
                return None
            if resp.status_code != 200:
                return None

            data = resp.json()
            entry = data[0] if isinstance(data, list) else data

            model_entity_id = entry.get("modelEntityId") or f"AF-{uniprot_id}-F1"
            version = entry.get("latestVersion") or 4

            return {
                "enzyme_id": enzyme_id,
                "uniprot_id": uniprot_id,
                "entry_id": entry.get("entryId"),
                "model_url": entry.get("modelUrl")
                or f"{AFDB_FILES}/{model_entity_id}-model_v{version}.cif",
                "pae_url": entry.get("paeUrl")
                or f"{AFDB_FILES}/{model_entity_id}-predicted_aligned_error_v{version}.json",
                "plddt_mean": entry.get("globalMetricValue") or entry.get("meanPlddt"),
                "release_date": entry.get("latestVersion"),
            }
        except Exception:
            return None


async def main(concurrency: int = 50, limit: int = 0):
    # Get list of enzymes with PDB structures
    async with session_scope() as db:
        rows = await db.execute(
            select(EnzymeRecord.id, EnzymeRecord.uniprot_id)
            .join(PDBStructure, PDBStructure.enzyme_id == EnzymeRecord.id)
            .distinct()
        )
        pairs = [(r[0], r[1]) for r in rows.fetchall()]

    if limit > 0:
        pairs = pairs[:limit]

    total = len(pairs)
    logger.info("Querying AlphaFold API for %d enzymes (concurrency=%d)", total, concurrency)

    sem = asyncio.Semaphore(concurrency)
    results = []

    async with httpx.AsyncClient(timeout=30.0) as client:
        tasks = [fetch_af_entry(client, eid, uid, sem) for eid, uid in pairs]

        for coro in asyncio.as_completed(tasks):
            result = await coro
            if result:
                results.append(result)
            if len(results) % 500 == 0:
                logger.info("Found %d AF2 predictions so far...", len(results))

    logger.info("%d/%d enzymes have AlphaFold predictions", len(results), total)

    if not results:
        logger.info("No AF predictions found. Nothing to store.")
        return

    # Store in DB
    async with session_scope() as db:
        created = 0
        for r in results:
            # Check if already exists
            existing = await db.execute(
                select(AlphaFoldStructure.id).where(
                    AlphaFoldStructure.enzyme_id == r["enzyme_id"]
                )
            )
            if existing.scalar():
                continue

            af = AlphaFoldStructure(
                enzyme_id=r["enzyme_id"],
                model_url=r.get("model_url"),
                plddt_mean=r.get("plddt_mean"),
                pae_matrix_url=r.get("pae_url"),
            )
            db.add(af)
            created += 1

            if created % 100 == 0:
                await db.commit()
                logger.info("Stored %d AlphaFold structures...", created)

        await db.commit()
        logger.info("Done. Stored %d AlphaFold structures total.", created)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--concurrency", type=int, default=50)
    parser.add_argument("--limit", type=int, default=0)
    args = parser.parse_args()
    asyncio.run(main(concurrency=args.concurrency, limit=args.limit))
