"""Operational status API."""

from __future__ import annotations

import time
from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.core.security import get_current_user, require_admin
from app.services.ops_notifications import dispatch_alert_notification
from app.services.tool_task_audit import list_all_task_audits_filtered, summarize_task_audits, ToolTaskAuditFilters
from app.services.ops_status import collect_ops_summary

router = APIRouter()
OPS_SUMMARY_CACHE_TTL_SECONDS = 30
_ops_summary_cache: tuple[float, dict[str, Any]] | None = None


@router.get("/summary")
async def get_ops_summary(
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Return a read-only operational summary for authenticated users."""
    global _ops_summary_cache
    now = time.monotonic()
    if _ops_summary_cache is not None and now - _ops_summary_cache[0] < OPS_SUMMARY_CACHE_TTL_SECONDS:
        payload = dict(_ops_summary_cache[1])
        payload["cached"] = True
        return payload

    audits = await list_all_task_audits_filtered(
        session,
        limit=200,
        filters=ToolTaskAuditFilters(failed_only=True),
    )
    payload = collect_ops_summary(task_audit_summary=summarize_task_audits(audits))
    payload["cached"] = False
    _ops_summary_cache = (now, payload)
    return payload


@router.post("/alerts/dispatch")
async def dispatch_ops_alerts(
    dry_run: bool = True,
    force: bool = False,
    current_user: dict = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
):
    """Preview or send external operational alerts.

    Defaults to dry-run so a dashboard click cannot accidentally notify external
    systems. Real delivery also requires OPS_ALERT_WEBHOOK_ENABLED=true and a
    valid OPS_ALERT_WEBHOOK_URL.
    """
    audits = await list_all_task_audits_filtered(
        session,
        limit=200,
        filters=ToolTaskAuditFilters(failed_only=True),
    )
    summary = collect_ops_summary(task_audit_summary=summarize_task_audits(audits))
    return dispatch_alert_notification(
        summary["monitoring"]["alerts"],
        summary["notifications"],
        summary_status=summary["status"],
        dry_run=dry_run,
        force=force,
    )
