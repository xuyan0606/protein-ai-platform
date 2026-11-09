#!/usr/bin/env python3
"""sync_to_outline.py — Batch sync enzyme database to Outline Wiki.

Syncs enzyme records from the local SQLite/PostgreSQL database to Outline
as structured Markdown documents, organized by EC classification.

Usage:
    python scripts/sync_to_outline.py                          # Full sync
    python scripts/sync_to_outline.py --dry-run                # Preview only
    python scripts/sync_to_outline.py --limit 100              # First 100 records
    python scripts/sync_to_outline.py --category "EC.3"        # Only hydrolases

Environment:
    OUTLINE_API_URL:    Outline API base URL (default: http://localhost:3001/api)
    OUTLINE_API_TOKEN:  Outline API key (required)
    DATABASE_URL:       PostgreSQL connection string (or use --sqlite)
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import logging
from pathlib import Path

# Add backend to path for imports
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# EC Classification hierarchy
# ---------------------------------------------------------------------------
EC_CLASSES = {
    "EC.1": {"name": "Oxidoreductases", "desc": "Catalyze oxidation/reduction reactions"},
    "EC.2": {"name": "Transferases", "desc": "Transfer functional groups between molecules"},
    "EC.3": {"name": "Hydrolases", "desc": "Catalyze hydrolysis reactions"},
    "EC.4": {"name": "Lyases", "desc": "Cleave bonds by means other than hydrolysis or oxidation"},
    "EC.5": {"name": "Isomerases", "desc": "Catalyze isomerization changes within a single molecule"},
    "EC.6": {"name": "Ligases", "desc": "Join two molecules with covalent bonds"},
    "EC.7": {"name": "Translocases", "desc": "Catalyze movement of ions or molecules across membranes"},
}


def format_enzyme_markdown(enzyme: dict) -> str:
    """Format a single enzyme record as Markdown for Outline."""
    lines = []

    name = enzyme.get("name", "Unknown enzyme")
    ec = enzyme.get("ec_number", "N/A")
    uniprot_id = enzyme.get("uniprot_id", "N/A")
    organism = enzyme.get("organism", "N/A")
    sequence = enzyme.get("sequence", "")
    length = len(sequence) if sequence else enzyme.get("length", 0)

    lines.append(f"# {name}\n")
    lines.append(f"**EC Number**: {ec}  ")
    lines.append(f"**UniProt ID**: [{uniprot_id}](https://www.uniprot.org/uniprot/{uniprot_id})  ")
    lines.append(f"**Organism**: {organism}  ")
    lines.append(f"**Length**: {length} aa\n")

    # Sequence
    if sequence:
        lines.append("## Sequence\n")
        lines.append("```")
        lines.append(f">{uniprot_id} {name}")
        # Wrap at 60 chars per line (FASTA format)
        for i in range(0, len(sequence), 60):
            lines.append(sequence[i:i + 60])
        lines.append("```\n")

    # Properties
    props = enzyme.get("properties", {})
    if props:
        lines.append("## Physicochemical Properties\n")
        if "molecular_weight_kda" in props:
            lines.append(f"- **MW**: {props['molecular_weight_kda']:.1f} kDa")
        if "isoelectric_point" in props:
            lines.append(f"- **pI**: {props['isoelectric_point']:.2f}")
        if "gravy" in props:
            lines.append(f"- **GRAVY**: {props['gravy']:.3f}")
        if "stability" in props:
            lines.append(f"- **Stability**: {props['stability']}")
        lines.append("")

    # Function
    function = enzyme.get("function", "")
    if function:
        lines.append("## Function\n")
        lines.append(f"{function}\n")

    # Catalytic activity
    activity = enzyme.get("catalytic_activity", "")
    if activity:
        lines.append("## Catalytic Activity\n")
        lines.append(f"{activity}\n")

    # Keywords
    keywords = enzyme.get("keywords", [])
    if keywords:
        lines.append("## Keywords\n")
        lines.append(", ".join(keywords))
        lines.append("")

    lines.append("---")
    lines.append(f"*Source: Protein AI Platform Enzyme Database — {uniprot_id}*")

    return "\n".join(lines)


def format_ec_summary_markdown(ec_prefix: str, enzymes: list[dict]) -> str:
    """Generate a summary document for an EC class."""
    info = EC_CLASSES.get(ec_prefix, {"name": ec_prefix, "desc": ""})
    lines = [
        f"# {ec_prefix}: {info['name']}\n",
        f"{info['desc']}\n",
        f"**Total enzymes**: {len(enzymes)}\n",
        "## Enzyme List\n",
        "| EC Number | Name | UniProt ID | Organism | Length |",
        "|-----------|------|------------|----------|--------|",
    ]
    for e in enzymes:
        ec = e.get("ec_number", "N/A")
        name = e.get("name", "Unknown")[:40]
        uid = e.get("uniprot_id", "N/A")
        org = e.get("organism", "N/A")[:25]
        seq = e.get("sequence", "")
        length = len(seq) if seq else e.get("length", 0)
        lines.append(f"| {ec} | {name} | {uid} | {org} | {length} |")

    lines.append("")
    lines.append(f"*Auto-generated from Protein AI Platform — {len(enzymes)} enzymes*")

    return "\n".join(lines)


async def load_enzymes_from_db(
    category: str | None = None,
    limit: int | None = None,
) -> list[dict]:
    """Load enzyme records from the database.

    For MVP, generates sample enzyme data. In production, queries PostgreSQL.
    """
    # Try to import and query the actual database
    try:
        from app.core.database import async_session
        from sqlalchemy import text

        enzymes = []
        async with async_session() as session:
            query = "SELECT * FROM enzymes"
            params = {}
            if category:
                query += " WHERE ec_number LIKE :cat"
                params["cat"] = f"{category}%"
            if limit:
                query += f" LIMIT {limit}"

            result = await session.execute(text(query), params)
            for row in result:
                enzyme = dict(row._mapping)
                enzymes.append(enzyme)

        logger.info("Loaded %d enzymes from database", len(enzymes))
        return enzymes
    except Exception as e:
        logger.warning("Database not available (%s), generating sample data", e)

    # Fallback: generate sample enzyme data for testing
    sample_enzymes = []
    ec_prefixes = list(EC_CLASSES.keys())

    for i in range(min(limit or 50, 50)):
        ec_prefix = ec_prefixes[i % len(ec_prefixes)]
        ec_class_num = ec_prefix.split(".")[1]
        sample_enzymes.append({
            "name": f"Sample {EC_CLASSES[ec_prefix]['name']} {i + 1}",
            "ec_number": f"{ec_class_num}.{(i % 99) + 1}.{(i % 20) + 1}.{(i % 500) + 1}",
            "uniprot_id": f"P{10000 + i:05d}",
            "organism": ["Escherichia coli", "Bacillus subtilis", "Saccharomyces cerevisiae",
                         "Thermus thermophilus", "Homo sapiens"][i % 5],
            "sequence": "M" + "ACDEFGHIKLMNPQRSTVWY" * (10 + i % 20),
            "length": 0,
            "properties": {
                "molecular_weight_kda": 25.0 + i * 2.3,
                "isoelectric_point": 5.5 + (i % 50) * 0.1,
                "gravy": -0.5 + (i % 10) * 0.12,
                "stability": "stable" if i % 3 != 0 else "unstable",
            },
            "function": f"Catalyzes the {EC_CLASSES[ec_prefix]['name'].lower()} reaction.",
            "catalytic_activity": f"A {EC_CLASSES[ec_prefix]['name'].lower()} substrate.",
            "keywords": ["enzyme", EC_CLASSES[ec_prefix]["name"].lower()],
        })

    if category:
        cat_num = category.replace("EC.", "")
        sample_enzymes = [
            e for e in sample_enzymes
            if e["ec_number"].startswith(f"{cat_num}.")
        ]

    logger.info("Generated %d sample enzymes", len(sample_enzymes))
    return sample_enzymes


async def sync_to_outline(
    dry_run: bool = False,
    limit: int | None = None,
    category: str | None = None,
):
    """Main sync logic: load enzymes → create collections → upload documents."""
    from app.services.outline_client import OutlineClient

    client = OutlineClient()

    # 1. Health check
    if not dry_run:
        healthy = await client.health_check()
        if not healthy:
            logger.error("Outline API not reachable or not authenticated. Check OUTLINE_API_TOKEN.")
            return

    # 2. Load enzymes
    enzymes = await load_enzymes_from_db(category=category, limit=limit)
    if not enzymes:
        logger.warning("No enzymes to sync.")
        return

    # 3. Group by EC class
    ec_groups: dict[str, list[dict]] = {}
    for e in enzymes:
        ec = e.get("ec_number", "")
        ec_prefix = f"EC.{ec.split('.')[0]}" if ec else "EC.0"
        ec_groups.setdefault(ec_prefix, []).append(e)

    logger.info(
        "Sync plan: %d enzymes in %d EC classes",
        len(enzymes), len(ec_groups),
    )

    # 4. Create or find the main collection
    collection_id = None
    if not dry_run:
        collections = await client.list_collections()
        for c in collections:
            if c.get("name") == "酶数据库":
                collection_id = c["id"]
                break
        if not collection_id:
            col = await client.create_collection(
                "酶数据库",
                "Protein AI Platform — Enzyme database synced from local records",
            )
            collection_id = col.get("id")
    else:
        collection_id = "DRY_RUN_COLLECTION"

    # 5. Sync each EC class
    synced = 0
    skipped = 0
    for ec_prefix, group in sorted(ec_groups.items()):
        info = EC_CLASSES.get(ec_prefix, {"name": ec_prefix, "desc": ""})
        logger.info("  %s (%s): %d enzymes", ec_prefix, info["name"], len(group))

        if dry_run:
            for e in group:
                logger.info("    [DRY RUN] Would create: %s (%s)", e["name"], e["uniprot_id"])
                synced += 1
            continue

        # Check for existing documents (idempotent — skip by UniProt ID)
        existing_docs = await client.list_documents(collection_id)
        existing_titles = {d.get("title", "") for d in existing_docs}

        # Create EC summary document
        summary_title = f"{ec_prefix}: {info['name']} — Summary"
        if summary_title not in existing_titles:
            summary_md = format_ec_summary_markdown(ec_prefix, group)
            await client.create_document(summary_title, summary_md, collection_id)
            logger.info("    Created summary: %s", summary_title)

        # Create individual enzyme documents (batch of 50)
        for i, enzyme in enumerate(group):
            title = f"{enzyme.get('uniprot_id', 'Unknown')} — {enzyme.get('name', 'Unknown enzyme')}"

            # Idempotent: skip if already exists
            if title in existing_titles:
                skipped += 1
                continue

            md = format_enzyme_markdown(enzyme)
            await client.create_document(title, md, collection_id)
            synced += 1

            # Rate limiting: pause every 50 docs
            if synced % 50 == 0:
                logger.info("    Synced %d documents, pausing...", synced)
                await asyncio.sleep(1.0)

    logger.info("Sync complete: %d created, %d skipped (already exist)", synced, skipped)


def main():
    parser = argparse.ArgumentParser(description="Sync enzyme database to Outline Wiki")
    parser.add_argument("--dry-run", action="store_true", help="Preview without writing")
    parser.add_argument("--limit", type=int, default=None, help="Max records to sync")
    parser.add_argument("--category", type=str, default=None, help="EC category filter (e.g., EC.3)")
    args = parser.parse_args()

    if not os.getenv("OUTLINE_API_TOKEN") and not args.dry_run:
        logger.error("OUTLINE_API_TOKEN not set. Use --dry-run for preview.")
        sys.exit(1)

    asyncio.run(sync_to_outline(
        dry_run=args.dry_run,
        limit=args.limit,
        category=args.category,
    ))


if __name__ == "__main__":
    main()
