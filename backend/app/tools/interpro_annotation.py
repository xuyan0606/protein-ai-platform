"""InterPro-style family/domain/function annotation tool.

Phase 1 implementation:
- reads curated InterPro records if present in the local database
- falls back to Pfam + sequence motif heuristics when external InterPro data
  has not been ingested yet
"""

from __future__ import annotations

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

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


async def interpro_annotation(
    sequence: str = "",
    uniprot_id: str = "",
    _session: AsyncSession | None = None,
) -> dict[str, Any]:
    """Return InterPro-like family/domain annotations for a sequence or UniProt ID."""

    async with _use_session(_session) as session:
        facade = AnnotationFacade(session)
        return await facade.resolve_interpro_annotation(sequence=sequence, uniprot_id=uniprot_id)


ToolRegistry.register(
    name="interpro_annotation",
    description=(
        "InterPro-style functional annotation for enzymes and proteins. "
        "Returns integrated family/domain/site hints using local InterPro records "
        "if present, existing Pfam domain architecture, and sequence-motif heuristics."
    ),
    handler=interpro_annotation,
    is_async=True,
    category="data",
    timeout_seconds=30,
    parameters={
        "type": "object",
        "properties": {
            "sequence": {"type": "string", "description": "Protein amino acid sequence"},
            "uniprot_id": {"type": "string", "description": "UniProt accession if known"},
        },
    },
)
