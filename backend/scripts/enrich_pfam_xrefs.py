"""Enrich Pfam cross-references from UniProt API and populate domain tables.

Fetches cross-reference data for enzymes missing Pfam annotations,
stores to database_crossrefs, then populates pfam_domains and domain_architecture.

Uses high-concurrency individual UniProt lookups (batch endpoint has field-name issues).

Usage:
    python scripts/enrich_pfam_xrefs.py [--limit N] [--concurrency 30]
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

from sqlalchemy import select, insert

from app.core.database import session_scope
from app.models.domain import (
    EnzymeRecord, DatabaseCrossRef, PfamDomain, DomainArchitecture,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

UNIPROT_REST = "https://rest.uniprot.org/uniprotkb"


async def fetch_single(client: httpx.AsyncClient, uniprot_id: str, sem: asyncio.Semaphore) -> dict | None:
    """Fetch a single UniProt entry to get cross-references."""
    async with sem:
        try:
            resp = await client.get(
                f"{UNIPROT_REST}/{uniprot_id}?format=json",
                timeout=30.0,
            )
            if resp.status_code == 200:
                return resp.json()
            return None
        except Exception:
            return None


def extract_xrefs(entry: dict) -> list[dict]:
    """Extract Pfam and PDB cross-references from a UniProt entry."""
    xrefs = []
    for ref in entry.get("uniProtKBCrossReferences", []):
        db_type = ref.get("database", "").lower()
        db_id = ref.get("id", "")
        if db_type in ("pfam", "pdb") and db_id:
            xrefs.append({"source_db": db_type, "source_id": db_id})
    return xrefs


async def main(limit: int = 0, concurrency: int = 30):
    # 1. Get enzymes that don't have Pfam cross-refs yet
    async with session_scope() as db:
        from sqlalchemy import func

        existing_xref_enzymes = await db.execute(
            select(DatabaseCrossRef.enzyme_id)
            .where(DatabaseCrossRef.source_db == "pfam")
            .distinct()
        )
        existing_ids = {r[0] for r in existing_xref_enzymes}
        logger.info("Enzymes already with Pfam xrefs: %d", len(existing_ids))

        rows = await db.execute(
            select(EnzymeRecord.id, EnzymeRecord.uniprot_id)
            .where(
                EnzymeRecord.sequence.isnot(None),
                EnzymeRecord.sequence != "",
            )
            .order_by(EnzymeRecord.id)
        )
        all_enzymes = [(r[0], r[1]) for r in rows.fetchall()]

    to_process = [(eid, uid) for eid, uid in all_enzymes if eid not in existing_ids]
    if limit > 0:
        to_process = to_process[:limit]

    total = len(to_process)
    logger.info("Enzymes to enrich: %d (concurrency=%d)", total, concurrency)

    if total == 0:
        logger.info("All enzymes have Pfam xrefs. Nothing to do.")
        return

    # 2. Fetch cross-references from UniProt with high concurrency
    sem = asyncio.Semaphore(concurrency)
    xrefs_inserted = 0
    fetched = 0

    async def fetch_one(eid: int, uid: str):
        entry = await fetch_single(client, uid, sem)
        return eid, uid, entry

    async with httpx.AsyncClient(timeout=30.0) as client:
        pending = [asyncio.ensure_future(fetch_one(eid, uid)) for eid, uid in to_process]

        # Collect results and batch-insert
        batch_buffer: list[tuple[int, str, list[dict]]] = []  # (enzyme_id, uniprot_id, [xrefs])

        for done in asyncio.as_completed(pending):
            eid, uid, entry = await done
            fetched += 1

            if entry:
                xrefs = extract_xrefs(entry)
                if xrefs:
                    batch_buffer.append((eid, uid, xrefs))

            # Insert in batches of 100
            if len(batch_buffer) >= 100:
                async with session_scope() as db:
                    n = await _insert_xrefs(db, batch_buffer)
                    xrefs_inserted += n
                batch_buffer = []
                await asyncio.sleep(0.2)  # rate limit

            if fetched % 500 == 0:
                logger.info("Fetched %d/%d, xrefs inserted: %d", fetched, total, xrefs_inserted)

        # Flush remaining
        if batch_buffer:
            async with session_scope() as db:
                n = await _insert_xrefs(db, batch_buffer)
                xrefs_inserted += n

    logger.info("Fetch done. Total xrefs inserted: %d", xrefs_inserted)

    # 3. Build Pfam domain architecture from xrefs
    logger.info("Building Pfam domain architecture...")
    pfam_domains_created = 0
    arch_links = 0

    async with session_scope() as db:
        rows = await db.execute(
            select(DatabaseCrossRef).where(DatabaseCrossRef.source_db == "pfam")
        )
        pfam_xrefs = rows.scalars().all()
        logger.info("Processing %d Pfam cross-references", len(pfam_xrefs))

        for xref in pfam_xrefs:
            try:
                domain_row = await db.execute(
                    select(PfamDomain).where(PfamDomain.pfam_id == xref.source_id)
                )
                domain = domain_row.scalar()
                if not domain:
                    domain = PfamDomain(pfam_id=xref.source_id)
                    db.add(domain)
                    await db.flush()
                    pfam_domains_created += 1

                stmt = insert(DomainArchitecture).values(
                    enzyme_id=xref.enzyme_id,
                    domain_id=domain.id,
                    start_pos=0,
                    end_pos=0,
                )
                stmt = stmt.on_conflict_do_nothing(
                    index_elements=["enzyme_id", "domain_id", "start_pos"]
                )
                await db.execute(stmt)
                arch_links += 1
            except Exception:
                logger.exception("Pfam link failed for enzyme %d", xref.enzyme_id)

        await db.commit()

    logger.info("Done. Pfam domains: %d, architecture links: %d", pfam_domains_created, arch_links)


async def _insert_xrefs(db, batch: list[tuple[int, str, list[dict]]]) -> int:
    """Insert cross-references for a batch of enzymes. Returns count inserted."""
    n = 0
    for enzyme_id, uniprot_id, xrefs in batch:
        for xref in xrefs:
            existing = await db.execute(
                select(DatabaseCrossRef.id).where(
                    DatabaseCrossRef.enzyme_id == enzyme_id,
                    DatabaseCrossRef.source_db == xref["source_db"],
                )
            )
            if existing.scalar():
                continue
            db.add(DatabaseCrossRef(
                enzyme_id=enzyme_id,
                source_db=xref["source_db"],
                source_id=xref["source_id"],
                source_url=_xref_url(xref["source_db"], xref["source_id"]),
                last_synced=datetime.now(timezone.utc),
            ))
            n += 1
    if n > 0:
        await db.commit()
    return n


def _xref_url(db_type: str, db_id: str) -> str | None:
    prefixes = {
        "pdb": f"https://www.rcsb.org/structure/{db_id}",
        "pfam": f"https://pfam.xfam.org/family/{db_id}",
        "brenda": f"https://www.brenda-enzymes.org/enzyme.php?ecno={db_id}",
    }
    return prefixes.get(db_type)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Enrich Pfam/PDB cross-references from UniProt")
    parser.add_argument("--limit", type=int, default=1000)
    parser.add_argument("--concurrency", type=int, default=30)
    args = parser.parse_args()
    asyncio.run(main(limit=args.limit, concurrency=args.concurrency))
