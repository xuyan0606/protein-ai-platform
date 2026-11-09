"""AlphaFold structure ingestor.

Fetches AlphaFold2 prediction metadata from EBI AFDB API for enzymes
that have PDB structures (not all 280K — too slow for one-by-one API).
Implements lazy-loading for on-demand protein queries.
"""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import select, insert

from app.data.base_ingestor import BaseIngestor
from app.data.ingestor_registry import register
from app.models.domain import EnzymeRecord, AlphaFoldStructure

logger = logging.getLogger(__name__)

AFDB_BASE = "https://alphafold.ebi.ac.uk/api"
AFDB_FILES = "https://alphafold.ebi.ac.uk/files"


@register("alphafold")
class AlphaFoldIngestor(BaseIngestor):
    """Fetch AlphaFold2 metadata for enzymes with known PDB structures."""

    source_name = "alphafold"
    chunk_size = 50

    def _download_raw(self) -> None:
        raise NotImplementedError

    async def run(self, force: bool = False) -> IngestReport:
        from app.data.base_ingestor import IngestReport, IngestStatus

        report = IngestReport(source=self.source_name, started_at=datetime.now(timezone.utc))
        try:
            report.status = IngestStatus.DOWNLOADING

            # Only query enzymes that have PDB structures (not all 280K)
            rows = await self.db.execute(
                select(EnzymeRecord.uniprot_id, EnzymeRecord.id)
                .where(
                    EnzymeRecord.id.in_(
                        select(EnzymeRecord.id).where(
                            EnzymeRecord.id.in_(
                                select(AlphaFoldStructure.enzyme_id).correlate(AlphaFoldStructure)
                            )
                        )
                    )
                )
            )
            # Actually, just get enzymes with PDB structures
            from app.models.domain import PDBStructure

            rows = await self.db.execute(
                select(EnzymeRecord.uniprot_id).join(
                    PDBStructure, PDBStructure.enzyme_id == EnzymeRecord.id
                ).distinct()
            )
            uniprot_ids = [r[0] for r in rows.fetchall()]
            logger.info("alphafold: checking %d enzymes (those with PDB structures)", len(uniprot_ids))

            if not uniprot_ids:
                report.status = IngestStatus.COMPLETED
                report.finished_at = datetime.now(timezone.utc)
                logger.info("alphafold: no PDB-linked enzymes yet, skipping")
                return report

            # Check each ID against AFDB API
            results = []
            for i, uid in enumerate(uniprot_ids):
                try:
                    resp = await self.http.get(f"{AFDB_BASE}/prediction/{uid}")
                    if resp.status_code == 404:
                        continue
                    if resp.status_code == 429:
                        await asyncio.sleep(5.0)
                        continue
                    if resp.status_code != 200:
                        continue

                    data = resp.json()
                    entry = data[0] if isinstance(data, list) else data
                    results.append({
                        "uniprot_id": uid,
                        "entry_id": entry.get("entryId"),
                        "model_url": entry.get("modelUrl") or f"{AFDB_FILES}/AF-{uid}-F1-model_v4.cif",
                        "pae_url": entry.get("paeUrl") or f"{AFDB_FILES}/AF-{uid}-F1-predicted_aligned_error_v4.json",
                        "plddt_mean": entry.get("globalMetricValue") or entry.get("meanPlddt"),
                        "release_date": entry.get("latestVersion"),
                    })
                    if (i + 1) % 100 == 0:
                        logger.info("alphafold: %d/%d checked, %d found", i + 1, len(uniprot_ids), len(results))
                except Exception:
                    logger.debug("alphafold: %s error", uid)
                await asyncio.sleep(self.request_delay)

            # Cache results
            out = self.cache_dir / "alphafold_metadata.json"
            out.write_text(json.dumps(results, ensure_ascii=False))
            logger.info("alphafold: %d/%d enzymes have AF2 predictions", len(results), len(uniprot_ids))

            # Store batch by batch
            report.status = IngestStatus.STORING
            for i in range(0, len(results), self.chunk_size):
                batch = results[i : i + self.chunk_size]
                try:
                    created, updated = await self._store_batch(batch)
                    report.items_created += created
                    report.items_updated += updated
                except Exception as e:
                    report.items_failed += len(batch)
                    report.errors.append(f"store batch: {e}")

            report.status = IngestStatus.COMPLETED
        except Exception as e:
            report.status = IngestStatus.FAILED
            report.errors.append(str(e))
        finally:
            report.finished_at = datetime.now(timezone.utc)
        return report

    async def _store_batch(self, batch: list[dict]) -> tuple[int, int]:
        created, updated = 0, 0
        for entry in batch:
            try:
                uid = entry["uniprot_id"]
                row = await self.db.execute(
                    select(EnzymeRecord.id).where(EnzymeRecord.uniprot_id == uid)
                )
                enzyme_id = row.scalar()
                if not enzyme_id:
                    continue

                af = AlphaFoldStructure(
                    enzyme_id=enzyme_id,
                    model_url=entry.get("model_url"),
                    plddt_mean=entry.get("plddt_mean"),
                    pae_matrix_url=entry.get("pae_url"),
                    cif_path=None,
                )
                stmt = insert(AlphaFoldStructure).values(**self._orm_values(af))
                stmt = stmt.on_conflict_do_update(
                    index_elements=["enzyme_id"],
                    set_={"model_url": stmt.excluded.model_url, "plddt_mean": stmt.excluded.plddt_mean},
                )
                result = await self.db.execute(stmt)
                if result.rowcount == 1:
                    created += 1
                else:
                    updated += 1
            except Exception:
                logger.exception("alphafold store failed: %s", entry.get("uniprot_id"))
        await self.db.commit()
        return created, updated

    @staticmethod
    def _orm_values(obj) -> dict:
        return {c.name: getattr(obj, c.name) for c in obj.__table__.columns if getattr(obj, c.name) is not None}
