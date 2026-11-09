"""Rhea reaction equation ingestor.

Queries Rhea REST API for enzyme-catalyzed reaction equations,
reactant/product mappings, and cofactor data. Links by EC number.
"""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import insert

from app.data.base_ingestor import BaseIngestor
from app.data.ingestor_registry import register
from app.models.domain import ReactionEquation

logger = logging.getLogger(__name__)

RHEA_BASE = "https://www.rhea-db.org"


@register("rhea")
class RheaIngestor(BaseIngestor):
    """Fetch reaction equations from Rhea database REST API."""

    source_name = "rhea"
    chunk_size = 100
    request_delay = 0.5

    async def _download_raw(self) -> Path:
        url = f"{RHEA_BASE}/rhea?format=json"
        resp = await self.http.get(url)
        resp.raise_for_status()
        data = resp.json()
        results = data.get("results", [])

        all_reactions = []
        for r in results:
            all_reactions.append({
                "rhea_id": r.get("id"),
                "equation": r.get("equation"),
                "status": r.get("status"),
                "is_balanced": r.get("isBalanced"),
                "is_transport": r.get("isTransport"),
                "ec_numbers": r.get("ec", []),
                "substrates": _extract_participants(r, "substrates"),
                "products": _extract_participants(r, "products"),
            })

        logger.info("rhea: downloaded %d reactions", len(all_reactions))

        out = self.cache_dir / "rhea_reactions.json"
        out.write_text(json.dumps(all_reactions, ensure_ascii=False))
        return out

    async def _store_batch(self, batch: list[dict]) -> tuple[int, int]:
        created, updated = 0, 0
        for r in batch:
            try:
                rxn = ReactionEquation(
                    rhea_id=r["rhea_id"],
                    equation=r.get("equation"),
                    reaction_side=r.get("status"),
                    reactants=r.get("substrates"),
                    products=r.get("products"),
                    ec_numbers=r.get("ec_numbers"),
                    is_balanced=r.get("is_balanced"),
                    is_transport=r.get("is_transport"),
                    source_db="rhea",
                )
                is_new = await self._upsert(
                    ReactionEquation, self._orm_values(rxn),
                    index_elements=["rhea_id"],
                    update_keys=["equation", "ec_numbers"],
                )
                if is_new:
                    created += 1
                else:
                    updated += 1
            except Exception:
                logger.exception("rhea store failed: %s", r.get("rhea_id"))
        await self.db.commit()
        return created, updated

    @staticmethod
    def _orm_values(obj) -> dict:
        return {c.name: getattr(obj, c.name) for c in obj.__table__.columns if getattr(obj, c.name) is not None}


def _extract_participants(r: dict, role: str) -> list[dict]:
    """Extract substrate/product participant data from a Rhea reaction entry."""
    participants = []
    for p in r.get(role, []):
        participants.append({
            "name": p.get("name"),
            "chebi_id": p.get("chebiId"),
            "stoichiometry": p.get("stoichiometry"),
            "smiles": p.get("smiles"),
        })
    return participants
