"""Persistent strategy checkpoint helpers."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.strategy_checkpoint import StrategyCheckpoint

RECENT_MEMORY_STATUSES = ("awaiting_confirmation", "executing", "completed")


def _checkpoint_to_dict(row: StrategyCheckpoint) -> dict[str, Any]:
    return {
        "id": row.id,
        "user_id": row.user_id,
        "conversation_id": row.conversation_id,
        "project_id": row.project_id,
        "task_text": row.task_text,
        "task_fingerprint": row.task_fingerprint,
        "strategy_signature": row.strategy_signature,
        "revision": row.revision,
        "status": row.status,
        "next_action": row.next_action,
        "plan_payload": row.plan_payload,
        "evidence_state": row.evidence_state,
        "artifacts": row.artifacts,
        "policy_payload": row.policy_payload,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
        "confirmed_at": row.confirmed_at.isoformat() if row.confirmed_at else None,
        "executed_at": row.executed_at.isoformat() if row.executed_at else None,
        "superseded_at": row.superseded_at.isoformat() if row.superseded_at else None,
    }


async def persist_strategy_checkpoint(
    session: AsyncSession,
    *,
    user_id: int,
    conversation_id: int,
    project_id: str | None,
    task_text: str,
    task_fingerprint: str,
    strategy_signature: str,
    plan_payload: list[dict],
    evidence_state: dict | None = None,
    artifacts: dict | None = None,
    policy_payload: dict | None = None,
    next_action: str = "confirm_execute",
) -> dict[str, Any]:
    """Store the latest awaiting checkpoint and supersede older awaiting revisions."""
    now = datetime.now(timezone.utc)
    await session.execute(
        update(StrategyCheckpoint)
        .where(
            StrategyCheckpoint.conversation_id == conversation_id,
            StrategyCheckpoint.user_id == user_id,
            StrategyCheckpoint.status == "awaiting_confirmation",
        )
        .values(status="superseded", superseded_at=now)
    )

    latest_revision = (
        await session.execute(
            select(StrategyCheckpoint.revision)
            .where(StrategyCheckpoint.conversation_id == conversation_id)
            .order_by(StrategyCheckpoint.revision.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    revision = int(latest_revision or 0) + 1

    row = StrategyCheckpoint(
        user_id=user_id,
        conversation_id=conversation_id,
        project_id=project_id,
        task_text=task_text,
        task_fingerprint=task_fingerprint,
        strategy_signature=strategy_signature,
        revision=revision,
        status="awaiting_confirmation",
        next_action=next_action,
        plan_payload=plan_payload,
        evidence_state=evidence_state,
        artifacts=artifacts,
        policy_payload=policy_payload,
    )
    session.add(row)
    await session.flush()
    await session.refresh(row)
    return _checkpoint_to_dict(row)


async def get_active_strategy_checkpoint(
    session: AsyncSession,
    *,
    user_id: int,
    conversation_id: int,
) -> dict[str, Any] | None:
    row = (
        await session.execute(
            select(StrategyCheckpoint)
            .where(
                StrategyCheckpoint.user_id == user_id,
                StrategyCheckpoint.conversation_id == conversation_id,
                StrategyCheckpoint.status == "awaiting_confirmation",
            )
            .order_by(StrategyCheckpoint.revision.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    return _checkpoint_to_dict(row) if row else None


async def list_strategy_checkpoints(
    session: AsyncSession,
    *,
    user_id: int,
    conversation_id: int,
    limit: int = 20,
) -> list[dict[str, Any]]:
    rows = (
        await session.execute(
            select(StrategyCheckpoint)
            .where(
                StrategyCheckpoint.user_id == user_id,
                StrategyCheckpoint.conversation_id == conversation_id,
            )
            .order_by(StrategyCheckpoint.revision.desc())
            .limit(limit)
        )
    ).scalars().all()
    return [_checkpoint_to_dict(row) for row in rows]


async def list_recent_strategy_memory(
    session: AsyncSession,
    *,
    user_id: int,
    conversation_id: int | None = None,
    project_id: str | None = None,
    limit: int = 10,
) -> list[dict[str, Any]]:
    """Return recent non-superseded strategy checkpoints for continuation context."""
    conditions = [
        StrategyCheckpoint.user_id == user_id,
        StrategyCheckpoint.status.in_(RECENT_MEMORY_STATUSES),
    ]
    if project_id:
        conditions.append(StrategyCheckpoint.project_id == project_id)
    elif conversation_id is not None:
        conditions.append(StrategyCheckpoint.conversation_id == conversation_id)
    else:
        return []

    rows = (
        await session.execute(
            select(StrategyCheckpoint)
            .where(*conditions)
            .order_by(
                StrategyCheckpoint.updated_at.desc(),
                StrategyCheckpoint.id.desc(),
            )
            .limit(limit)
        )
    ).scalars().all()
    return [_checkpoint_to_dict(row) for row in rows]


async def mark_strategy_checkpoint_executing(
    session: AsyncSession,
    *,
    checkpoint_id: int,
    user_id: int,
) -> dict[str, Any] | None:
    """Atomically claim an awaiting revision; the caller commits before tools run."""
    now = datetime.now(timezone.utc)
    claimed = await session.execute(
        update(StrategyCheckpoint)
        .where(
            StrategyCheckpoint.id == checkpoint_id,
            StrategyCheckpoint.user_id == user_id,
            StrategyCheckpoint.status == "awaiting_confirmation",
        )
        .values(status="executing", confirmed_at=now, executed_at=now, next_action=None)
    )
    if claimed.rowcount != 1:
        return None
    row = (
        await session.execute(
            select(StrategyCheckpoint).where(
                StrategyCheckpoint.id == checkpoint_id,
                StrategyCheckpoint.user_id == user_id,
            )
        )
    ).scalar_one_or_none()
    if row is None:
        return None
    await session.refresh(row)
    return _checkpoint_to_dict(row)


async def mark_strategy_checkpoint_completed(
    session: AsyncSession,
    *,
    checkpoint_id: int,
    user_id: int,
    evidence_state: dict | None = None,
    artifacts: dict | None = None,
) -> dict[str, Any] | None:
    """Mark a confirmed checkpoint complete and attach execution evidence summary."""
    row = (
        await session.execute(
            select(StrategyCheckpoint).where(
                StrategyCheckpoint.id == checkpoint_id,
                StrategyCheckpoint.user_id == user_id,
            )
        )
    ).scalar_one_or_none()
    if row is None:
        return None
    row.status = "completed"
    row.next_action = None
    row.evidence_state = evidence_state or row.evidence_state
    row.artifacts = artifacts or row.artifacts
    now = datetime.now(timezone.utc)
    row.confirmed_at = row.confirmed_at or now
    row.executed_at = row.executed_at or now
    await session.flush()
    await session.refresh(row)
    return _checkpoint_to_dict(row)
