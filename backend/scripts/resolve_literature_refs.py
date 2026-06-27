"""Resolve literature references from domain tables into structured paper records.

Reads literature_ref fields from kinetic_parameters, stability_records, and
directed_evolution_entries; parses PMID/DOI; batch-fetches metadata from PubMed
E-utilities; and writes results into papers + enzyme_literature_links tables.

Usage:
    python scripts/resolve_literature_refs.py [--dry-run] [--limit N] [--source brenda|protherm|enzengdb|all]
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select
from app.core.database import session_scope
from app.models.domain import KineticParameter, StabilityRecord, DirectedEvolutionEntry
from app.models.literature import Paper, EnzymeLiteratureLink
from app.services.literature_client import LiteratureClient, parse_literature_ref

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Source configuration
# ---------------------------------------------------------------------------
# Maps --source argument → (Model, relation_type, source_label)
SOURCE_MAP = {
    "brenda": {
        "model": KineticParameter,
        "relation_type": "kinetics",
        "source_label": "brenda",
        "filter_col": "source_db",
        "filter_val": "brenda",
    },
    "protherm": {
        "model": StabilityRecord,
        "relation_type": "stability",
        "source_label": "protherm",
        "filter_col": "source_db",
        "filter_val": "protherm",
    },
    "enzengdb": {
        "model": DirectedEvolutionEntry,
        "relation_type": "evolution",
        "source_label": "enzengdb",
        "filter_col": None,
        "filter_val": None,
    },
}

PUBMED_BATCH_SIZE = 200  # PubMed efetch limit


# ---------------------------------------------------------------------------
# Data collection
# ---------------------------------------------------------------------------
async def collect_refs(db, sources: list[str], limit: int) -> list[dict]:
    """Collect (enzyme_id, literature_ref, relation_type, source) tuples from domain tables."""
    collected: list[dict] = []

    for src in sources:
        cfg = SOURCE_MAP[src]
        model = cfg["model"]

        stmt = select(
            model.enzyme_id,
            model.literature_ref,
        ).where(model.literature_ref.isnot(None))

        if cfg["filter_col"]:
            stmt = stmt.where(
                getattr(model, cfg["filter_col"]) == cfg["filter_val"]
            )

        if limit > 0:
            stmt = stmt.limit(limit)

        rows = (await db.execute(stmt)).fetchall()

        for enzyme_id, ref in rows:
            parsed = parse_literature_ref(ref)
            if parsed is None:
                logger.debug("Unparseable ref: %r (enzyme_id=%d)", ref, enzyme_id)
                continue
            ref_type, ref_id = parsed
            collected.append({
                "enzyme_id": enzyme_id,
                "ref_type": ref_type,
                "ref_id": ref_id,
                "relation_type": cfg["relation_type"],
                "source": cfg["source_label"],
                "raw_ref": ref,
            })

    return collected


# ---------------------------------------------------------------------------
# Batch PMID resolution
# ---------------------------------------------------------------------------
async def resolve_all_pmids(
    client: LiteratureClient, pmids: list[str], dry_run: bool
) -> dict[str, object]:
    """Batch-fetch PubMed metadata. Returns {pmid: Paper(dataclass)}."""
    result: dict[str, object] = {}
    for i in range(0, len(pmids), PUBMED_BATCH_SIZE):
        batch = pmids[i : i + PUBMED_BATCH_SIZE]
        logger.info(
            "Fetching PubMed batch %d-%d / %d PMIDs",
            i + 1,
            min(i + PUBMED_BATCH_SIZE, len(pmids)),
            len(pmids),
        )
        try:
            papers = await client.fetch_pubmed(batch)
            for p in papers:
                result[p.pmid] = p
        except Exception:
            logger.exception("PubMed batch fetch failed (offset=%d)", i)

        # Rate-limit pause between batches
        if i + PUBMED_BATCH_SIZE < len(pmids):
            await asyncio.sleep(0.5)

    return result


async def resolve_dois_sequential(
    client: LiteratureClient, dois: list[str]
) -> dict[str, object]:
    """Resolve DOIs one-by-one via Europe PMC. Returns {doi: Paper(dataclass)}."""
    result: dict[str, object] = {}
    for doi in dois:
        try:
            paper = await client.resolve_doi(doi)
            if paper:
                result[doi] = paper
        except Exception:
            logger.warning("DOI resolution failed: %s", doi)
    return result


# ---------------------------------------------------------------------------
# Database write
# ---------------------------------------------------------------------------
async def write_results(
    db,
    entries: list[dict],
    pmid_papers: dict,
    doi_papers: dict,
    dry_run: bool,
) -> dict[str, int]:
    """Write Paper + EnzymeLiteratureLink records. Returns stats dict."""
    stats = {"papers_new": 0, "links_new": 0, "links_skipped": 0, "errors": 0}

    for entry in entries:
        try:
            ref_type = entry["ref_type"]
            ref_id = entry["ref_id"]

            # Look up the resolved paper
            paper = None
            if ref_type == "pmid":
                paper = pmid_papers.get(ref_id)
            elif ref_type == "doi":
                paper = doi_papers.get(ref_id)

            if paper is None:
                stats["errors"] += 1
                logger.debug(
                    "No paper found for %s:%s (enzyme_id=%d)",
                    ref_type, ref_id, entry["enzyme_id"],
                )
                continue

            pmid = paper.pmid
            if not pmid:
                stats["errors"] += 1
                continue

            if dry_run:
                logger.info(
                    "[DRY-RUN] Would insert paper PMID=%s title=%r link enzyme_id=%d",
                    pmid, paper.title[:60], entry["enzyme_id"],
                )
                stats["papers_new"] += 1
                stats["links_new"] += 1
                continue

            # --- Upsert Paper ---
            existing = await db.get(Paper, pmid)
            if existing is None:
                new_paper = Paper(
                    pmid=pmid,
                    doi=paper.doi,
                    title=paper.title or f"PMID:{pmid}",
                    authors=json.dumps(paper.authors) if paper.authors else None,
                    journal=paper.journal or None,
                    year=paper.year,
                    abstract=paper.abstract,
                    mesh_terms=json.dumps(paper.mesh_terms) if paper.mesh_terms else None,
                    citation_count=paper.citation_count,
                    source=paper.source,
                )
                db.add(new_paper)
                stats["papers_new"] += 1

            # --- Upsert EnzymeLiteratureLink ---
            link_q = select(EnzymeLiteratureLink).where(
                EnzymeLiteratureLink.enzyme_id == entry["enzyme_id"],
                EnzymeLiteratureLink.paper_pmid == pmid,
                EnzymeLiteratureLink.relation_type == entry["relation_type"],
            )
            existing_link = (await db.execute(link_q)).scalar_one_or_none()
            if existing_link is None:
                new_link = EnzymeLiteratureLink(
                    enzyme_id=entry["enzyme_id"],
                    paper_pmid=pmid,
                    relation_type=entry["relation_type"],
                    source=entry["source"],
                )
                db.add(new_link)
                stats["links_new"] += 1
            else:
                stats["links_skipped"] += 1

        except Exception:
            stats["errors"] += 1
            logger.exception("Error processing entry: enzyme_id=%d ref=%s", entry["enzyme_id"], entry["raw_ref"])

    if not dry_run:
        await db.commit()

    return stats


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
async def run(sources: list[str], dry_run: bool, limit: int) -> None:
    """Main entry point."""
    client = LiteratureClient()

    async with session_scope() as db:
        # 1. Collect all literature refs
        entries = await collect_refs(db, sources, limit)
        total = len(entries)
        logger.info("Collected %d literature references from %s", total, ", ".join(sources))

        if total == 0:
            logger.info("Nothing to do.")
            return

        # 2. Separate PMIDs and DOIs
        pmids: list[str] = []
        dois: list[str] = []
        seen_pmids: set[str] = set()
        seen_dois: set[str] = set()

        for e in entries:
            if e["ref_type"] == "pmid" and e["ref_id"] not in seen_pmids:
                pmids.append(e["ref_id"])
                seen_pmids.add(e["ref_id"])
            elif e["ref_type"] == "doi" and e["ref_id"] not in seen_dois:
                dois.append(e["ref_id"])
                seen_dois.add(e["ref_id"])

        logger.info("Unique PMIDs: %d, Unique DOIs: %d", len(pmids), len(dois))

        # 3. Check which PMIDs already exist in papers table (skip if present)
        new_pmids: list[str] = pmids
        if not dry_run and pmids:
            existing_q = select(Paper.pmid).where(Paper.pmid.in_(pmids))
            existing_rows = (await db.execute(existing_q)).scalars().all()
            existing_set = set(existing_rows)
            new_pmids = [p for p in pmids if p not in existing_set]
            logger.info("PMIDs already in DB: %d, to fetch: %d", len(existing_set), len(new_pmids))

        # 4. Fetch PubMed metadata in batches
        pmid_papers: dict = {}
        if new_pmids:
            pmid_papers = await resolve_all_pmids(client, new_pmids, dry_run)
            logger.info("Resolved %d/%d PMIDs", len(pmid_papers), len(new_pmids))

        # 5. Resolve DOIs
        doi_papers: dict = {}
        if dois:
            logger.info("Resolving %d DOIs...", len(dois))
            doi_papers = await resolve_dois_sequential(client, dois)
            logger.info("Resolved %d/%d DOIs", len(doi_papers), len(dois))

        # 6. Write results
        stats = await write_results(db, entries, pmid_papers, doi_papers, dry_run)

        # 7. Print summary
        mode = "DRY-RUN" if dry_run else "LIVE"
        logger.info("=" * 60)
        logger.info("[%s] Literature resolution complete", mode)
        logger.info("  Total refs collected : %d", total)
        logger.info("  Unique PMIDs        : %d", len(pmids))
        logger.info("  Unique DOIs         : %d", len(dois))
        logger.info("  Papers inserted     : %d", stats["papers_new"])
        logger.info("  Links inserted      : %d", stats["links_new"])
        logger.info("  Links skipped (dup) : %d", stats["links_skipped"])
        logger.info("  Errors              : %d", stats["errors"])
        logger.info("=" * 60)


def main():
    parser = argparse.ArgumentParser(
        description="Resolve literature_ref fields into papers + enzyme_literature_links"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print what would be done without writing to DB",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="Max rows to read per source table (0 = unlimited)",
    )
    parser.add_argument(
        "--source",
        type=str,
        default="all",
        choices=["brenda", "protherm", "enzengdb", "all"],
        help="Filter by data source (default: all)",
    )
    args = parser.parse_args()

    if args.source == "all":
        sources = list(SOURCE_MAP.keys())
    else:
        sources = [args.source]

    asyncio.run(run(sources=sources, dry_run=args.dry_run, limit=args.limit))


if __name__ == "__main__":
    main()
