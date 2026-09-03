"""Persistence helpers for versioned enzyme identity classifications."""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.identity_consistency import IdentityConsistencyRecord


def _to_dict(row: IdentityConsistencyRecord) -> dict[str, Any]:
    return {
        "id": row.id,
        "user_id": row.user_id,
        "sequence_hash": row.sequence_hash,
        "model_version": row.model_version,
        "evidence_version": row.evidence_version,
        "identity": row.identity,
        "status": row.status,
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }


async def persist_identity_record(
    session: AsyncSession,
    *,
    user_id: int,
    sequence_hash: str,
    model_version: str | None,
    evidence_version: str | None,
    identity: str,
    status: str,
) -> dict[str, Any]:
    normalized_model_version = model_version or ""
    normalized_evidence_version = evidence_version or ""
    existing = (
        await session.execute(
            select(IdentityConsistencyRecord)
            .where(
                IdentityConsistencyRecord.user_id == user_id,
                IdentityConsistencyRecord.sequence_hash == sequence_hash,
                IdentityConsistencyRecord.model_version == normalized_model_version,
                IdentityConsistencyRecord.evidence_version == normalized_evidence_version,
                IdentityConsistencyRecord.identity == identity,
            )
            .limit(1)
        )
    ).scalar_one_or_none()
    if existing is not None:
        return _to_dict(existing)

    row = IdentityConsistencyRecord(
        user_id=user_id,
        sequence_hash=sequence_hash,
        model_version=normalized_model_version,
        evidence_version=normalized_evidence_version,
        identity=identity,
        status=status,
    )
    session.add(row)
    await session.flush()
    await session.refresh(row)
    return _to_dict(row)


async def get_latest_identity_record(
    session: AsyncSession,
    *,
    user_id: int,
    sequence_hash: str,
    model_version: str | None,
    evidence_version: str | None,
) -> dict[str, Any] | None:
    row = (
        await session.execute(
            select(IdentityConsistencyRecord)
            .where(
                IdentityConsistencyRecord.user_id == user_id,
                IdentityConsistencyRecord.sequence_hash == sequence_hash,
                IdentityConsistencyRecord.model_version == (model_version or ""),
                IdentityConsistencyRecord.evidence_version == (evidence_version or ""),
            )
            .order_by(IdentityConsistencyRecord.created_at.desc(), IdentityConsistencyRecord.id.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    return _to_dict(row) if row else None
