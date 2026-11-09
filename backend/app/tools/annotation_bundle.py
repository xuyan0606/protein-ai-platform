"""Unified annotation bundle tool backed by AnnotationFacade."""

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


async def annotation_bundle(
    sequence: str = "",
    uniprot_id: str = "",
    _session: AsyncSession | None = None,
) -> dict:
    """Return InterPro, catalytic guardrail, and signal peptide annotations in one call."""

    async with _use_session(_session) as session:
        facade = AnnotationFacade(session)
        result = await facade.resolve_annotation_bundle(sequence=sequence, uniprot_id=uniprot_id)
    if isinstance(result, dict):
        result.setdefault("capability_status", "evidence_synthesis")
        result.setdefault("evidence_level", "ANNOTATION_SYNTHESIS")
        result.setdefault(
            "report_boundary",
            (
                "聚合本地/审校注释和保守预测证据；只有 evidence_source.status=live 且 "
                "live_query_executed=true 时，才可写成当轮实时 UniProt/InterPro/M-CSA/SignalP 查询。"
            ),
        )
    return result


ToolRegistry.register(
    name="annotation_bundle",
    description=(
        "Unified annotation bundle for protein engineering workflows. "
        "Returns InterPro-style annotations, catalytic-site guardrails, "
        "and signal-peptide prediction in one aggregated response."
    ),
    handler=annotation_bundle,
    is_async=True,
    category="data",
    timeout_seconds=45,
    parameters={
        "type": "object",
        "properties": {
            "sequence": {"type": "string", "description": "Protein amino acid sequence"},
            "uniprot_id": {"type": "string", "description": "UniProt accession if known"},
        },
    },
)
