"""Tool wrapper for fail-closed local WT baseline resolution."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import session_scope
from app.services.wt_baseline_registry import WTBaselineRegistry
from app.tools.registry import ToolRegistry


@asynccontextmanager
async def _use_session(external: AsyncSession | None) -> AsyncGenerator[AsyncSession, None]:
    if external is not None:
        yield external
    else:
        async with session_scope() as session:
            yield session


async def wt_baseline_registry(
    uniprot_id: str,
    metric: str,
    substrate_name: str,
    ph: float | None = None,
    temperature_c: float | None = None,
    buffer: str = "",
    protein_preparation: str = "",
    batch_id: str = "",
    feedback_records: list[dict[str, Any]] | None = None,
    _session: AsyncSession | None = None,
) -> dict[str, Any]:
    """Resolve an exact-condition WT baseline and emit a report claim contract.

    The result's ``report_contract.status`` is ``ready``, ``missing``, or
    ``conflict``.  Only ``ready`` permits WT comparison claims; approximate,
    nearest-condition, cross-batch, and cross-preparation substitutions remain
    disallowed.
    """

    async with _use_session(_session) as session:
        return await WTBaselineRegistry(session).resolve(
            uniprot_id=uniprot_id,
            metric=metric,
            substrate_name=substrate_name,
            ph=ph,
            temperature_c=temperature_c,
            buffer=buffer,
            protein_preparation=protein_preparation,
            batch_id=batch_id,
            feedback_records=feedback_records,
        )


ToolRegistry.register(
    name="wt_baseline_registry",
    description=(
        "Resolve a read-only WT baseline under exact assay conditions. Missing preparation, "
        "batch, QC, or provenance remains blocked; no nearest-condition fallback is used. "
        "Returns a report_contract with ready/missing/conflict claim gating."
    ),
    handler=wt_baseline_registry,
    is_async=True,
    category="data",
    timeout_seconds=30,
    parameters={
        "type": "object",
        "properties": {
            "uniprot_id": {"type": "string"},
            "metric": {"type": "string"},
            "substrate_name": {"type": "string"},
            "ph": {"type": "number"},
            "temperature_c": {"type": "number"},
            "buffer": {"type": "string"},
            "protein_preparation": {"type": "string"},
            "batch_id": {"type": "string"},
            "feedback_records": {"type": "array", "items": {"type": "object"}},
        },
        "required": ["uniprot_id", "metric", "substrate_name"],
    },
)
