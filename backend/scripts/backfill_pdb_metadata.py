"""Backfill PDB structure metadata (title, method, resolution, deposited_at).

Queries the RCSB PDB REST API in batches to populate metadata for PDB structures
that were ingested with only the PDB ID and chain info.

Usage:
    python scripts/backfill_pdb_metadata.py [--batch-size 50] [--limit N]
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select, update
from app.core.database import session_scope
from app.models.domain import PDBStructure

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

RCSB_API = "https://data.rcsb.org/rest/v1/core/entry"


async def fetch_pdb_batch(client: httpx.AsyncClient, pdb_ids: list[str]) -> dict[str, dict]:
    """Fetch metadata for a batch of PDB IDs from RCSB API.

    Uses the GraphQL-style batch endpoint to get multiple entries at once.
    """
    if not pdb_ids:
        return {}

    # RCSB REST API: POST to /core/entry with JSON body
    # Returns entry-level metadata: struct_keywords, exptl (method), refine (resolution)
    try:
        ids_query = ",".join(pdb_ids[:50])  # Batch up to 50 per request
        resp = await client.get(
            f"{RCSB_API}/{ids_query}"
        )
        if resp.status_code == 200:
            data = resp.json()
            return data if isinstance(data, dict) else {}
        elif resp.status_code == 404:
            return {}
        else:
            logger.warning("RCSB API returned %d for batch", resp.status_code)
            return {}
    except Exception as e:
        logger.warning("RCSB API error: %s", e)
        return {}


def extract_metadata(entry: dict) -> dict:
    """Extract title, method, resolution, deposited_at from RCSB entry dict."""
    meta = {}

    # Title
    struct = entry.get("struct", {})
    title = struct.get("title", "")
    if title:
        meta["title"] = title

    # Method (experimental method)
    exptl = entry.get("exptl", [])
    if exptl:
        meta["method"] = exptl[0].get("method", "")

    # Resolution
    refine = entry.get("refine", [])
    if refine:
        res = refine[0].get("ls_d_res_high")
        if res is not None:
            meta["resolution"] = float(res)

    # Deposition date
    audit = entry.get("audit_author", [])
    # Actually get from rcsb_accession_info
    rcsb = entry.get("rcsb_accession_info", {})
    dep_date = rcsb.get("deposit_date") or rcsb.get("initial_deposition_date")
    if dep_date:
        try:
            meta["deposited_at"] = datetime.fromisoformat(dep_date.replace("Z", "+00:00"))
        except (ValueError, AttributeError):
            pass

    return meta


async def backfill(batch_size: int = 50, limit: int = 0):
    """Main backfill routine."""
    async with session_scope() as db:
        # Get all PDB IDs that need metadata
        q = select(PDBStructure.id, PDBStructure.pdb_id).where(
            PDBStructure.method.is_(None)
        )
        if limit > 0:
            q = q.limit(limit)
        rows = (await db.execute(q)).fetchall()

        total = len(rows)
        logger.info("Found %d PDB entries missing metadata", total)

        if total == 0:
            logger.info("All PDB entries have metadata. Nothing to do.")
            return

        updated = 0
        async with httpx.AsyncClient(timeout=30.0) as client:
            for i in range(0, total, batch_size):
                batch = rows[i : i + batch_size]
                pdb_ids = [r[1] for r in batch]

                try:
                    data = await fetch_pdb_batch(client, pdb_ids)

                    # Process each entry
                    for db_id, pdb_id in batch:
                        entry_data = data.get(pdb_id, {}) if isinstance(data, dict) else {}
                        if not entry_data:
                            # Try fetching individually
                            try:
                                resp = await client.get(f"{RCSB_API}/{pdb_id}")
                                if resp.status_code == 200:
                                    entry_data = resp.json()
                            except Exception:
                                pass

                        if not entry_data:
                            continue

                        meta = extract_metadata(entry_data)
                        if not meta:
                            continue

                        stmt = update(PDBStructure).where(PDBStructure.id == db_id).values(**meta)
                        await db.execute(stmt)
                        updated += 1

                except Exception as e:
                    logger.warning("Batch error: %s", e)

                if (i + batch_size) % 500 == 0:
                    await db.commit()
                    logger.info("Progress: %d/%d, updated %d", min(i + batch_size, total), total, updated)

                # Rate limit
                await asyncio.sleep(0.5)

            await db.commit()

        logger.info("Done. Updated %d/%d PDB entries with metadata", updated, total)


def main():
    parser = argparse.ArgumentParser(description="Backfill PDB structure metadata")
    parser.add_argument("--batch-size", type=int, default=50)
    parser.add_argument("--limit", type=int, default=0)
    args = parser.parse_args()

    asyncio.run(backfill(batch_size=args.batch_size, limit=args.limit))


if __name__ == "__main__":
    main()
