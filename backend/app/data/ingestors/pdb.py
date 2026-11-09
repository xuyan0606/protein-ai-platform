"""PDB structure ingestor.

Queries RCSB PDB REST API for enzyme structures, matches to
enzyme_records via UniProt cross-references from GraphQL API.
Uses incremental page-by-page processing.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import select

from app.data.base_ingestor import BaseIngestor
from app.data.ingestor_registry import register
from app.models.domain import EnzymeRecord, PDBStructure

logger = logging.getLogger(__name__)

RCSB_SEARCH = "https://search.rcsb.org/rcsbsearch/v2/query"
RCSB_GRAPHQL = "https://data.rcsb.org/graphql"
PAGE_SIZE = 500


@register("pdb")
class PDBIngestor(BaseIngestor):
    """Fetch enzyme PDB structures via RCSB PDB REST + GraphQL APIs."""

    source_name = "pdb"
    chunk_size = 100

    def _download_raw(self) -> None:
        raise NotImplementedError

    async def run(self, force: bool = False) -> IngestReport:
        from app.data.base_ingestor import IngestReport, IngestStatus

        report = IngestReport(source=self.source_name, started_at=datetime.now(timezone.utc))
        try:
            report.status = IngestStatus.DOWNLOADING

            query = {
                "query": {
                    "type": "terminal",
                    "service": "text",
                    "parameters": {
                        "attribute": "rcsb_polymer_entity.rcsb_ec_lineage.id",
                        "operator": "exists",
                    },
                },
                "return_type": "polymer_entity",
                "request_options": {"paginate": {"start": 0, "rows": PAGE_SIZE}},
            }

            polymer_entities = []
            page = 0

            while True:
                query["request_options"]["paginate"]["start"] = page * PAGE_SIZE
                resp = await self._search_with_retry(query)
                if resp is None:
                    report.status = IngestStatus.FAILED
                    report.errors.append(f"search failed at page {page}")
                    report.finished_at = datetime.now(timezone.utc)
                    return report

                data = resp.json()
                result_set = data.get("result_set", [])
                if not result_set:
                    break

                polymer_entities.extend(r["identifier"] for r in result_set)
                total = data.get("total_count", 0)
                page += 1
                logger.info("pdb: %d/%d polymer entities", len(polymer_entities), total)

                if len(polymer_entities) >= total:
                    break
                await asyncio.sleep(self.request_delay)

            logger.info("pdb: collected %d polymer entity IDs", len(polymer_entities))

            # Process in batches: resolve via GraphQL → match → store
            report.status = IngestStatus.STORING
            for i in range(0, len(polymer_entities), self.chunk_size):
                batch = polymer_entities[i : i + self.chunk_size]
                try:
                    created, updated = await self._store_batch(batch)
                    report.items_created += created
                    report.items_updated += updated
                except Exception as e:
                    report.items_failed += len(batch)
                    report.errors.append(f"store batch {i}: {e}")
                await asyncio.sleep(self.request_delay)

            report.status = IngestStatus.COMPLETED
        except Exception as e:
            report.status = IngestStatus.FAILED
            report.errors.append(str(e))
        finally:
            report.finished_at = datetime.now(timezone.utc)
        return report

    async def _search_with_retry(self, query: dict) -> httpx.Response | None:
        for attempt in range(3):
            try:
                resp = await self.http.post(RCSB_SEARCH, json=query)
                if resp.status_code == 429:
                    await asyncio.sleep(5.0 * (attempt + 1))
                    continue
                resp.raise_for_status()
                return resp
            except Exception as e:
                logger.warning("pdb search attempt %d: %s", attempt, e)
                if attempt < 2:
                    await asyncio.sleep(3.0 * (attempt + 1))
        return None

    async def _store_batch(self, batch: list[str]) -> tuple[int, int]:
        """Resolve polymer entity IDs via GraphQL, match to enzymes, store."""
        # Parse entry_id and entity_id from polymer entity identifiers
        parsed = []
        for pe_id in batch:
            m = re.match(r"^([A-Za-z0-9]+)_(\d+)$", pe_id)
            if m:
                parsed.append((m.group(1), m.group(2)))

        if not parsed:
            return 0, 0

        # Build batch GraphQL query
        q_parts = []
        for entry_id, entity_id in parsed:
            q_parts.append(
                f'pe_{entry_id}_{entity_id}: polymer_entity(entry_id:"{entry_id}", entity_id:"{entity_id}"){{'
                f"rcsb_id "
                f"rcsb_polymer_entity_container_identifiers{{uniprot_ids}} "
                f"entity_poly{{pdbx_strand_id}} "
                f"}}"  # closes polymer_entity selection (inner selections are self-closing via {{}} pairs)
            )

        # Split into sub-batches (GraphQL query size limit)
        created, updated = 0, 0
        for j in range(0, len(q_parts), 20):
            sub_parts = q_parts[j : j + 20]
            gql = "{" + " ".join(sub_parts) + "}"
            try:
                resp = await self.http.post(RCSB_GRAPHQL, json={"query": gql})
                if resp.status_code == 429:
                    await asyncio.sleep(5.0)
                    continue
                if resp.status_code != 200:
                    logger.warning("pdb graphql batch returned %d", resp.status_code)
                    continue

                gql_data = resp.json()
                if "errors" in gql_data:
                    logger.warning("pdb graphql errors: %s", gql_data["errors"][:1])
                    continue

                for key, pe in gql_data.get("data", {}).items():
                    if not pe:
                        continue
                    uniprot_list = (
                        pe.get("rcsb_polymer_entity_container_identifiers", {})
                        .get("uniprot_ids", []) or []
                    )
                    if not uniprot_list:
                        continue

                    # Use first UniProt ID to match
                    uniprot_id = uniprot_list[0]
                    enzyme_row = await self.db.execute(
                        select(EnzymeRecord.id).where(EnzymeRecord.uniprot_id == uniprot_id)
                    )
                    enzyme_id = enzyme_row.scalar()
                    if not enzyme_id:
                        continue

                    pdb_id = pe["rcsb_id"].split("_")[0]
                    chain = pe.get("entity_poly", {}).get("pdbx_strand_id", "?")

                    struct = PDBStructure(
                        pdb_id=pdb_id,
                        enzyme_id=enzyme_id,
                        chain_ids=[chain] if chain else None,
                        pdb_file_path=f"pdb/{pdb_id.lower()}.pdb",
                    )
                    is_new = await self._upsert(
                        PDBStructure, self._orm_values(struct),
                        index_elements=["pdb_id"],
                        update_keys=["chain_ids"],
                    )
                    if is_new:
                        created += 1
                    else:
                        updated += 1
            except Exception as e:
                logger.warning("pdb graphql batch failed: %s", e)
            await asyncio.sleep(0.3)

        await self.db.commit()
        return created, updated

    @staticmethod
    def _orm_values(obj) -> dict:
        return {c.name: getattr(obj, c.name) for c in obj.__table__.columns if getattr(obj, c.name) is not None}
