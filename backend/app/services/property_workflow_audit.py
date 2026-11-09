"""Persistence helpers for redacted property-workflow shadow decisions."""

from __future__ import annotations

import hashlib
from typing import Any

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.workflow_audit import WorkflowShadowAudit


def _fingerprint(message: str) -> str:
    return hashlib.sha256(str(message or "").encode("utf-8")).hexdigest()


def _redact_route(route: dict[str, Any]) -> dict[str, Any]:
    allowed = {"intent", "status", "workflow_id", "primary_property", "optimization_targets", "secondary_properties", "preservation_constraints", "input_gaps", "route_confidence"}
    return {key: route.get(key) for key in allowed if key in route}


def _redact_comparison(shadow: dict[str, Any]) -> dict[str, Any]:
    comparison = shadow.get("comparison") if isinstance(shadow.get("comparison"), dict) else shadow
    allowed = {"observed_tool_count", "observed_tools", "forbidden_tools", "unmapped_tools", "dispatch_blocked"}
    return {key: comparison.get(key) for key in allowed if key in comparison}


async def persist_shadow_audit(session: AsyncSession, *, user_id: int, conversation_id: int | None, project_id: str | None, message: str, shadow: dict[str, Any]) -> dict[str, Any]:
    route = shadow.get("route") if isinstance(shadow.get("route"), dict) else {}
    row = WorkflowShadowAudit(user_id=int(user_id), conversation_id=conversation_id, project_id=project_id, message_fingerprint=_fingerprint(message), intent=route.get("intent"), workflow_id=route.get("workflow_id"), status=route.get("status"), route_payload=_redact_route(route), comparison_payload=_redact_comparison(shadow))
    session.add(row)
    await session.flush()
    return _serialize(row)


def _serialize(row: WorkflowShadowAudit) -> dict[str, Any]:
    return {"id": row.id, "user_id": row.user_id, "conversation_id": row.conversation_id, "project_id": row.project_id, "governance_version": row.governance_version, "message_fingerprint": row.message_fingerprint, "intent": row.intent, "workflow_id": row.workflow_id, "status": row.status, "route": row.route_payload, "comparison": row.comparison_payload, "created_at": row.created_at.isoformat() if row.created_at else None}


async def list_shadow_audits(session: AsyncSession, *, user_id: int, limit: int = 100) -> list[dict[str, Any]]:
    result = await session.execute(select(WorkflowShadowAudit).where(WorkflowShadowAudit.user_id == int(user_id)).order_by(desc(WorkflowShadowAudit.created_at), desc(WorkflowShadowAudit.id)).limit(max(1, min(int(limit), 500))))
    return [_serialize(row) for row in result.scalars().all()]
