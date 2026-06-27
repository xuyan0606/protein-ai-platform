"""EnzEngDB directed evolution data ingestor.

EnzEngDB (https://enzengdb.a-star.edu.sg/) is a curated database of directed
enzyme evolution experiments. Contains mutation libraries, selection conditions,
and activity improvement data.

Strategy: Parse downloaded dataset (CSV/JSON format from the EnzEngDB web interface
or literature-mined structured data). Operates in standby mode — requires a
local file placed in the cache directory.

Expected CSV columns:
    enzyme_name, uniprot_id, mutagenesis_method, selection_pressure,
    library_size, rounds, best_variant, mutations, initial_activity,
    final_activity, fold_improvement, metric, organism, reference
"""

from __future__ import annotations

import csv
import logging
from io import StringIO
from pathlib import Path

from sqlalchemy import select

from app.data.base_ingestor import BaseIngestor
from app.data.ingestor_registry import register
from app.models.domain import EnzymeRecord, DirectedEvolutionEntry

logger = logging.getLogger(__name__)


@register("enzengdb")
class EnzEngDBIngestor(BaseIngestor):
    """Parse EnzEngDB directed evolution experiments and store to DB."""

    source_name = "enzengdb"
    chunk_size = 100

    async def _download_raw(self) -> Path:
        """EnzEngDB requires manual download. Return path if file exists."""
        for fname in ("enzengdb.csv", "enzengdb.json", "enzengdb.tsv"):
            path = self.cache_dir / fname
            if path.exists():
                logger.info("enzengdb: found %s (%.1f MB)", fname, path.stat().st_size / 1e6)
                return path
        logger.warning("enzengdb: no data file found in %s", self.cache_dir)
        empty = self.cache_dir / "enzengdb_empty.csv"
        empty.write_text("")
        return empty

    async def _parse_raw(self, raw_path: Path) -> list[dict]:
        """Parse CSV/TSV/JSON EnzEngDB format."""
        if raw_path.stat().st_size == 0:
            return []

        text = raw_path.read_text(encoding="utf-8", errors="replace")

        # CSV/TSV
        if raw_path.suffix in (".csv", ".tsv"):
            delimiter = "\t" if raw_path.suffix == ".tsv" else ","
            reader = csv.DictReader(StringIO(text), delimiter=delimiter)
            records = []
            for row in reader:
                records.append({
                    "enzyme_name": row.get("enzyme_name", ""),
                    "uniprot_id": row.get("uniprot_id", ""),
                    "experiment_name": row.get("experiment_name"),
                    "mutagenesis_method": row.get("mutagenesis_method"),
                    "selection_pressure": row.get("selection_pressure"),
                    "library_size": _int_or_none(row.get("library_size")),
                    "rounds": _int_or_none(row.get("rounds")),
                    "best_variant": row.get("best_variant"),
                    "mutations": _list_or_none(row.get("mutations")),
                    "initial_activity": _float_or_none(row.get("initial_activity")),
                    "final_activity": _float_or_none(row.get("final_activity")),
                    "fold_improvement": _float_or_none(row.get("fold_improvement")),
                    "metric": row.get("metric", "Kcat/Km"),
                    "organism": row.get("organism"),
                    "reference": row.get("reference"),
                })
            logger.info("enzengdb: parsed %d experiments", len(records))
            return records

        # JSON
        import json
        data = json.loads(text)
        logger.info("enzengdb: parsed %d experiments from JSON", len(data))
        return data if isinstance(data, list) else data.get("entries", [])

    async def _store_batch(self, batch: list[dict]) -> tuple[int, int]:
        created, updated = 0, 0
        for entry in batch:
            try:
                uid = entry.get("uniprot_id")
                if not uid:
                    continue
                row = await self.db.execute(
                    select(EnzymeRecord.id).where(EnzymeRecord.uniprot_id == uid)
                )
                enzyme_id = row.scalar()
                if not enzyme_id:
                    continue

                evo = DirectedEvolutionEntry(
                    enzyme_id=enzyme_id,
                    experiment_name=entry.get("experiment_name"),
                    mutagenesis_method=entry.get("mutagenesis_method"),
                    selection_pressure=entry.get("selection_pressure"),
                    library_size=entry.get("library_size"),
                    rounds=entry.get("rounds"),
                    best_variant=entry.get("best_variant"),
                    mutations_introduced=entry.get("mutations"),
                    initial_activity=entry.get("initial_activity"),
                    final_activity=entry.get("final_activity"),
                    fold_improvement=entry.get("fold_improvement"),
                    improvement_metric=entry.get("metric"),
                    organism_name=entry.get("organism"),
                    literature_ref=entry.get("reference"),
                )
                self.db.add(evo)
                created += 1
            except Exception:
                logger.exception("enzengdb store failed: %s", entry.get("uniprot_id"))
        await self.db.commit()
        return created, updated


def _int_or_none(val: str | None) -> int | None:
    if val is None:
        return None
    try:
        return int(val)
    except (ValueError, TypeError):
        return None


def _float_or_none(val: str | None) -> float | None:
    if val is None:
        return None
    try:
        return float(val)
    except (ValueError, TypeError):
        return None


def _list_or_none(val: str | None) -> list | None:
    if val is None:
        return None
    val = val.strip()
    if not val:
        return None
    import json
    try:
        return json.loads(val)
    except (json.JSONDecodeError, TypeError):
        return [v.strip() for v in val.split(";") if v.strip()]
