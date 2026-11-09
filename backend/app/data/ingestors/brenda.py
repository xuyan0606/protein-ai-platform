"""BRENDA enzyme kinetics ingestor.

Strategy: BRENDA provides text-file downloads (brenda_download.txt) via
academic license at https://www.brenda-enzymes.org/. The file is a structured
flat-file format with enzyme kinetic parameters organized by EC number.

Parse format:
    ENZYME_CLASS::EC 1.1.1.1
    PROTEIN::...
    KM::substrate=..., value=..., units=...
    KCAT::substrate=..., value=..., units=...

For initial integration without a BRENDA license, this ingestor operates in
standby mode — it ingests only if a brenda_download.txt is placed in the
cache directory.

License: Academic subscription required (free for academic use).
https://www.brenda-enzymes.org/request/license.php
"""

from __future__ import annotations

import logging
import re
from pathlib import Path

from sqlalchemy import select, insert

from app.data.base_ingestor import BaseIngestor
from app.data.ingestor_registry import register
from app.models.domain import EnzymeRecord, ECNumber, EnzymeECLink, KineticParameter

logger = logging.getLogger(__name__)


@register("brenda")
class BRENDAIngestor(BaseIngestor):
    """Parse BRENDA text dump and store kinetic parameters.

    Expects `brenda_download.txt` in cache_dir.
    """

    source_name = "brenda"
    chunk_size = 200

    async def _download_raw(self) -> Path:
        """BRENDA requires manual download. Return path if file exists."""
        path = self.cache_dir / "brenda_download.txt"
        if path.exists():
            logger.info("brenda: found local file %s (%.1f MB)", path, path.stat().st_size / 1e6)
            return path
        logger.warning("brenda: no brenda_download.txt found in %s — place the file there or request academic license", self.cache_dir)
        # Create empty placeholder
        path.write_text("")
        return path

    async def _parse_raw(self, raw_path: Path) -> list[dict]:
        """Parse BRENDA flat-file format into kinetic parameter dicts."""
        if raw_path.stat().st_size == 0:
            return []

        text = raw_path.read_text(encoding="latin-1", errors="replace")
        entries = []
        current_ec = None
        current_protein = None

        for line in text.splitlines():
            line = line.strip()
            if not line:
                continue

            if line.startswith("ENZYME_CLASS::"):
                current_ec = line.split("::", 1)[1].strip()
                if current_ec.upper().startswith("EC "):
                    current_ec = current_ec[3:]
                continue

            if line.startswith("PROTEIN::"):
                current_protein = line.split("::", 1)[1].strip()
                continue

            # Parse kinetic parameters: KM, KCAT, KI, etc.
            m = re.match(r"^(KM|KCAT|KI|Kcat/Km|VMAX|IC50)::(.+)", line)
            if m and current_ec:
                param_type = m.group(1).upper().replace("KCAT/KM", "Kcat/Km")
                fields = _parse_param_fields(m.group(2))
                entries.append({
                    "ec_number": current_ec,
                    "protein_name": current_protein,
                    "param_type": param_type,
                    "substrate_name": fields.get("substrate"),
                    "value": fields.get("value"),
                    "unit": fields.get("unit"),
                    "mutant": fields.get("mutant"),
                    "organism": fields.get("organism"),
                    "comment": fields.get("comment"),
                })

        logger.info("brenda: parsed %d kinetic entries from file", len(entries))
        return entries

    async def _store_batch(self, batch: list[dict]) -> tuple[int, int]:
        created, updated = 0, 0
        for entry in batch:
            try:
                # Find enzyme by EC number
                ec_str = entry["ec_number"]
                ec_row = await self.db.execute(
                    select(ECNumber.id).where(ECNumber.ec_number == ec_str)
                )
                ec_id = ec_row.scalar()
                if not ec_id:
                    continue

                # Find enzyme linked to this EC
                link_row = await self.db.execute(
                    select(EnzymeECLink.enzyme_id).where(EnzymeECLink.ec_id == ec_id)
                )
                enzyme_id = link_row.scalar()
                if not enzyme_id:
                    continue

                kp = KineticParameter(
                    enzyme_id=enzyme_id,
                    source_db="brenda",
                    param_type=entry["param_type"],
                    substrate_name=entry.get("substrate_name"),
                    value=entry.get("value"),
                    unit=entry.get("unit"),
                    mutant=entry.get("mutant"),
                    organism_name=entry.get("organism"),
                    comment=entry.get("comment"),
                )
                self.db.add(kp)
                created += 1
            except Exception:
                logger.exception("brenda store failed")
        await self.db.commit()
        return created, updated


def _parse_param_fields(text: str) -> dict:
    """Parse BRENDA field format: key1=val1, key2=val2"""
    result = {}
    for part in text.split(","):
        part = part.strip()
        if "=" in part:
            k, v = part.split("=", 1)
            k = k.strip().lower()
            v = v.strip().strip("'\"")
            if k == "value":
                try:
                    result[k] = float(v)
                except (ValueError, TypeError):
                    result[k] = None
            else:
                result[k] = v
    return result
