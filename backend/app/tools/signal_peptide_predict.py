"""Signal peptide prediction with lightweight heuristic fallback."""

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


async def signal_peptide_predict(
    sequence: str = "",
    uniprot_id: str = "",
    _session: AsyncSession | None = None,
) -> dict:
    """Predict whether a protein carries an N-terminal signal peptide."""

    async with _use_session(_session) as session:
        facade = AnnotationFacade(session)
        return await facade.resolve_signal_peptide_prediction(sequence=sequence, uniprot_id=uniprot_id)


ToolRegistry.register(
    name="signal_peptide_predict",
    description=(
        "Predict whether a protein has an N-terminal signal peptide for secretion. "
        "Phase 1 uses a lightweight SignalP-style heuristic and stores results for reuse."
    ),
    handler=signal_peptide_predict,
    is_async=True,
    category="prediction",
    timeout_seconds=30,
    parameters={
        "type": "object",
        "properties": {
            "sequence": {"type": "string", "description": "Protein amino acid sequence"},
            "uniprot_id": {"type": "string", "description": "UniProt accession if known"},
        },
    },
)
