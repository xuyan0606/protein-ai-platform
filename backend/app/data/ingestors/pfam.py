"""Pfam domain ingestor.

Strategy: Download Pfam-A.seed from InterPro FTP, parse Stockholm format,
store domain families and residue-level architecture annotations.
Reference: ftp://ftp.ebi.ac.uk/pub/databases/Pfam/current/

For a lightweight first pass, we extract Pfam annotations from UniProt
cross-references (already ingested in UniProtIngestor._store_xrefs).
Full Pfam seed alignment ingest is ~30 GB and deferred to batch mode.
"""

from __future__ import annotations

import logging
from pathlib import Path

from sqlalchemy import select, insert

from app.data.base_ingestor import BaseIngestor
from app.data.ingestor_registry import register
from app.models.domain import EnzymeRecord, PfamDomain, DomainArchitecture, DatabaseCrossRef

logger = logging.getLogger(__name__)


@register("pfam")
class PfamIngestor(BaseIngestor):
    """Build Pfam domain architecture from UniProt xref data (zero-download)."""

    source_name = "pfam"

    async def _download_raw(self) -> Path:
        """No download needed — data comes from existing DatabaseCrossRef records."""
        p = self.cache_dir / "pfam_from_xrefs.json"
        p.write_text("[]")
        return p

    async def _store_batch(self, batch: list[dict]) -> tuple[int, int]:
        """Process Pfam cross-references stored by UniProtIngestor."""
        created, updated = 0, 0

        # Query all Pfam xrefs
        rows = await self.db.execute(
            select(DatabaseCrossRef).where(DatabaseCrossRef.source_db == "pfam")
        )
        xrefs = rows.scalars().all()

        for xref in xrefs:
            try:
                # Get or create PfamDomain
                domain_row = await self.db.execute(
                    select(PfamDomain).where(PfamDomain.pfam_id == xref.source_id)
                )
                domain = domain_row.scalar()
                if not domain:
                    domain = PfamDomain(pfam_id=xref.source_id)
                    self.db.add(domain)
                    await self.db.flush()
                    created += 1

                # Link to enzyme (approximate position from UniProt features)
                # UniProt provides domain positions in features — for pfam xrefs
                # we don't have exact start/end without full Pfam data, so use
                # placeholder positions (will be refined with full Pfam download)
                enzyme = await self.db.execute(
                    select(EnzymeRecord.id).where(EnzymeRecord.id == xref.enzyme_id)
                )
                if enzyme.scalar():
                    arch = DomainArchitecture(
                        enzyme_id=xref.enzyme_id,
                        domain_id=domain.id,
                        start_pos=0,
                        end_pos=0,
                    )
                    # Use raw insert to avoid duplicates
                    stmt = insert(DomainArchitecture).values(
                        enzyme_id=arch.enzyme_id,
                        domain_id=arch.domain_id,
                        start_pos=arch.start_pos,
                        end_pos=arch.end_pos,
                    )
                    stmt = stmt.on_conflict_do_nothing(
                        index_elements=["enzyme_id", "domain_id", "start_pos"]
                    )
                    await self.db.execute(stmt)
                    updated += 1
            except Exception:
                logger.exception("pfam xref failed: %s", xref.source_id)

        await self.db.commit()
        logger.info("pfam: created %d domains, linked %d", created, updated)
        return created, updated
