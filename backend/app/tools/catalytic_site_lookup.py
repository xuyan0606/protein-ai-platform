"""Catalytic residue lookup and engineering guardrail tool."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import session_scope
from app.services.annotation_facade import AnnotationFacade
from app.tools.registry import ToolRegistry


@asynccontextmanager
async def _use_session(external: AsyncSession | None) -> AsyncGenerator[AsyncSession, None]:
    if external is not None:
        yield external
    else:
        async with session_scope() as session:
            yield session


async def catalytic_site_lookup(
    sequence: str = "",
    uniprot_id: str = "",
    _session: AsyncSession | None = None,
) -> dict[str, Any]:
    """Look up curated catalytic residues or infer a guardrail set from sequence motifs."""

    async with _use_session(_session) as session:
        facade = AnnotationFacade(session)
        return await facade.resolve_catalytic_site_lookup(sequence=sequence, uniprot_id=uniprot_id)


def _infer_catalytic_residues(sequence: str) -> list[dict[str, Any]]:
    """Expose the shared heuristic for legacy tools that import this helper."""
    return AnnotationFacade._infer_catalytic_residues(sequence)


ToolRegistry.register(
    name="catalytic_site_lookup",
    description=(
        "Lookup or infer catalytic residues for enzyme engineering guardrails. "
        "Returns curated catalytic sites if available locally, otherwise infers "
        "high-risk positions from sequence motifs and enzyme heuristics."
    ),
    handler=catalytic_site_lookup,
    is_async=True,
    category="engineering",
    timeout_seconds=30,
    parameters={
        "type": "object",
        "properties": {
            "sequence": {"type": "string", "description": "Protein amino acid sequence"},
            "uniprot_id": {"type": "string", "description": "UniProt accession if known"},
        },
    },
)
