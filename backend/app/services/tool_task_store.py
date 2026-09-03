"""Persistent ownership metadata for async tool tasks."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from app.services.tool_cache import get_json, set_json

_TASK_OWNER_NAMESPACE = "protein_ai:tool_task_owner"
_TOOL_ARTIFACT_OWNER_NAMESPACE = "protein_ai:tool_artifact_owner"
_TASK_OWNER_TTL_SECONDS = 60 * 60 * 24


def _owner_key(task_id: str) -> str:
    return f"{_TASK_OWNER_NAMESPACE}:{task_id}"


def _artifact_owner_key(object_name: str) -> str:
    return f"{_TOOL_ARTIFACT_OWNER_NAMESPACE}:{object_name}"


async def record_tool_task_owner(task_id: str, user_id: int | str, tool_name: str) -> None:
    """Persist the user that submitted a tool task.

    The Redis-backed cache layer keeps ownership visible across API process
    restarts and multiple API instances. Its local fallback preserves test and
    degraded single-process behavior when Redis is unavailable.
    """
    await set_json(
        _owner_key(task_id),
        {
            "user_id": int(user_id),
            "tool": tool_name,
            "submitted_at": datetime.now(UTC).isoformat(),
        },
        ttl_seconds=_TASK_OWNER_TTL_SECONDS,
    )


async def get_tool_task_owner(task_id: str) -> dict[str, Any] | None:
    """Return persisted ownership metadata for a submitted tool task."""
    owner = await get_json(_owner_key(task_id))
    if not owner:
        return None
    try:
        owner["user_id"] = int(owner["user_id"])
    except (KeyError, TypeError, ValueError):
        return None
    return owner


async def record_tool_task_cancel_requested(task_id: str, user_id: int | str) -> dict[str, Any] | None:
    """Mark a submitted tool task as cancellation-requested."""
    owner = await get_tool_task_owner(task_id)
    if owner is None:
        return None

    owner["cancel_requested"] = True
    owner["cancel_requested_by"] = int(user_id)
    owner["cancel_requested_at"] = datetime.now(UTC).isoformat()
    await set_json(_owner_key(task_id), owner, ttl_seconds=_TASK_OWNER_TTL_SECONDS)
    return owner


async def record_tool_task_runtime_policy(
    task_id: str,
    *,
    queue: str,
    soft_time_limit: int,
    time_limit: int,
) -> dict[str, Any] | None:
    """Persist queue/timeout policy used for a submitted task."""
    owner = await get_tool_task_owner(task_id)
    if owner is None:
        return None
    owner["queue"] = queue
    owner["soft_time_limit"] = int(soft_time_limit)
    owner["time_limit"] = int(time_limit)
    await set_json(_owner_key(task_id), owner, ttl_seconds=_TASK_OWNER_TTL_SECONDS)
    return owner


async def record_tool_task_terminal_state(task_id: str, status: str) -> dict[str, Any] | None:
    """Persist the latest terminal/converged task status."""
    owner = await get_tool_task_owner(task_id)
    if owner is None:
        return None
    owner["terminal_status"] = status
    owner["terminal_recorded_at"] = datetime.now(UTC).isoformat()
    if status == "canceled" and not owner.get("cancel_effective_at"):
        owner["cancel_effective_at"] = owner["terminal_recorded_at"]
    await set_json(_owner_key(task_id), owner, ttl_seconds=_TASK_OWNER_TTL_SECONDS)
    return owner


async def record_tool_artifact_owner(
    object_name: str,
    user_id: int | str,
    *,
    tool_name: str,
    task_id: str | None = None,
) -> None:
    """Persist the user allowed to download a generated tool artifact."""
    await set_json(
        _artifact_owner_key(object_name),
        {
            "object_name": object_name,
            "user_id": int(user_id),
            "tool": tool_name,
            "task_id": task_id,
            "recorded_at": datetime.now(UTC).isoformat(),
        },
        ttl_seconds=_TASK_OWNER_TTL_SECONDS,
    )


async def get_tool_artifact_owner(object_name: str) -> dict[str, Any] | None:
    """Return persisted ownership metadata for a generated tool artifact."""
    owner = await get_json(_artifact_owner_key(object_name))
    if not owner:
        return None
    try:
        owner["user_id"] = int(owner["user_id"])
    except (KeyError, TypeError, ValueError):
        return None
    if "tool_name" not in owner and owner.get("tool"):
        owner["tool_name"] = owner["tool"]
    return owner
