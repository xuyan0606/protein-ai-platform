"""ProThermDB stability data ingestor.

Strategy: ProThermDB (https://web.iitm.ac.in/bioinfo2/prothermdb/) provides
downloadable flat files with thermodynamic parameters for protein mutations:
ΔΔG (folding free energy change), ΔTm (melting temperature change), ΔCp, etc.

Format: tab-delimited with columns:
    PDB_ID  MUTATION  DDG  DTM  PH  TEMP  METHOD  REFERENCE  ...

For initial integration without a downloaded copy, this operates in standby mode.
"""

from __future__ import annotations

import csv
import logging
from io import StringIO
from pathlib import Path

from sqlalchemy import select, insert

from app.data.base_ingestor import BaseIngestor
from app.data.ingestor_registry import register
from app.models.domain import EnzymeRecord, PDBStructure, StabilityRecord

logger = logging.getLogger(__name__)


@register("protherm")
class ProThermIngestor(BaseIngestor):
    """Parse ProThermDB flat file and store mutation stability data."""

    source_name = "protherm"
    chunk_size = 200

    async def _download_raw(self) -> Path:
        """ProThermDB requires manual download. Return path if file exists."""
        path = self.cache_dir / "prothermdb.tsv"
        if path.exists():
            logger.info("protherm: found local file %s (%.1f MB)", path, path.stat().st_size / 1e6)
            return path
        logger.warning("protherm: no prothermdb.tsv in %s — download from https://web.iitm.ac.in/bioinfo2/prothermdb/", self.cache_dir)
        path.write_text("")
        return path

    async def _parse_raw(self, raw_path: Path) -> list[dict]:
        """Parse ProThermDB tab-delimited format."""
        if raw_path.stat().st_size == 0:
            return []

        text = raw_path.read_text(encoding="utf-8", errors="replace")
        reader = csv.DictReader(StringIO(text), delimiter="\t")

        records = []
        for row in reader:
            try:
                mut_str = row.get("MUTATION", "")
                wt, pos_str, mt = mut_str[0], mut_str[1:-1], mut_str[-1]
                pos = int(pos_str)
            except (ValueError, IndexError):
                continue

            records.append({
                "pdb_id": row.get("PDB_ID", "").strip(),
                "mutation": mut_str,
                "mutation_pos": pos,
                "wild_type": wt,
                "mutant": mt,
                "ddg": _float_or_none(row.get("DDG")),
                "dtm": _float_or_none(row.get("DTM")),
                "dcp": _float_or_none(row.get("DCP")),
                "ph": _float_or_none(row.get("PH")),
                "temperature_c": _float_or_none(row.get("TEMP")),
                "method": row.get("METHOD", "").strip(),
                "reference": row.get("REFERENCE", "").strip(),
            })

        logger.info("protherm: parsed %d stability records", len(records))
        return records

    async def _store_batch(self, batch: list[dict]) -> tuple[int, int]:
        created, updated = 0, 0
        for entry in batch:
            try:
                # Map PDB ID to enzyme
                pdb_id = entry["pdb_id"]
                row = await self.db.execute(
                    select(PDBStructure.enzyme_id).where(PDBStructure.pdb_id == pdb_id)
                )
                enzyme_id = row.scalar()
                if not enzyme_id:
                    # Try direct PDB lookup (uppercase)
                    row = await self.db.execute(
                        select(PDBStructure.enzyme_id).where(PDBStructure.pdb_id == pdb_id.upper())
                    )
                    enzyme_id = row.scalar()
                if not enzyme_id:
                    continue

                sr = StabilityRecord(
                    enzyme_id=enzyme_id,
                    mutation=entry["mutation"],
                    mutation_pos=entry["mutation_pos"],
                    wild_type=entry["wild_type"],
                    mutant=entry["mutant"],
                    ddg=entry.get("ddg"),
                    dtm=entry.get("dtm"),
                    dcp=entry.get("dcp"),
                    ph=entry.get("ph"),
                    temperature_c=entry.get("temperature_c"),
                    method=entry.get("method"),
                    literature_ref=entry.get("reference"),
                    source_db="protherm",
                )
                self.db.add(sr)
                created += 1
            except Exception:
                logger.exception("protherm store failed: %s", entry.get("mutation"))
        await self.db.commit()
        return created, updated


def _float_or_none(val: str | None) -> float | None:
    if val is None:
        return None
    val = val.strip()
    if not val or val in ("NA", "N/A", "-", ""):
        return None
    try:
        return float(val)
    except (ValueError, TypeError):
        return None
