"""Database-backed audit trail for async tool tasks."""

from __future__ import annotations

import csv
import io
import json
import platform
import sys
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.tool_call import ToolTaskAudit

SENSITIVE_KEYS = {
    "pdb_data",
    "sdf_data",
    "ligand_3d_data",
    "ligand_pdbqt_data",
    "receptor_pdbqt_data",
    "sequence",
    "authorization",
    "token",
    "password",
    "secret",
}
TERMINAL_STATUSES = {"completed", "success", "failed", "failure", "degraded", "canceled", "revoked"}
SLOW_TASK_SECONDS = 30 * 60
FAILURE_ALERT_THRESHOLD = 3
SLOW_TASK_ALERT_THRESHOLD = 3


@dataclass(frozen=True)
class ToolTaskAuditFilters:
    tool: str | None = None
    status: str | None = None
    queue: str | None = None
    failure_class: str | None = None
    submitted_after: datetime | None = None
    submitted_before: datetime | None = None
    failed_only: bool = False
    slow_only: bool = False


def _runtime_environment() -> dict[str, Any]:
    return {
        "python_version": platform.python_version(),
        "python_executable": sys.executable,
        "platform": platform.platform(),
        "machine": platform.machine(),
    }


def _parse_dt(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def summarize_tool_input(params: dict[str, Any]) -> dict[str, Any]:
    """Store a compact, non-secret input summary instead of raw payloads."""
    summary: dict[str, Any] = {"keys": sorted(params.keys())}
    values: dict[str, Any] = {}
    for key, value in params.items():
        lowered = key.lower()
        if lowered in SENSITIVE_KEYS or any(secret in lowered for secret in ("token", "password", "secret")):
            values[key] = {"redacted": True, "type": type(value).__name__}
        elif isinstance(value, (str, int, float, bool)) or value is None:
            values[key] = value if not isinstance(value, str) or len(value) <= 240 else {"type": "str", "length": len(value)}
        elif isinstance(value, (list, tuple, set)):
            values[key] = {"type": type(value).__name__, "count": len(value)}
        elif isinstance(value, dict):
            values[key] = {"type": "dict", "keys": sorted(str(item) for item in value.keys())[:20]}
        else:
            values[key] = {"type": type(value).__name__}
    summary["values"] = values
    return summary


def summarize_tool_result(status: dict[str, Any]) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    """Extract compact result and artifact summaries from a task status payload."""
    payload = status.get("result")
    if not isinstance(payload, dict):
        return None, None
    nested = payload.get("result")
    result = nested if isinstance(nested, dict) else payload
    if not isinstance(result, dict):
        return None, None

    artifacts = result.get("artifacts") if isinstance(result.get("artifacts"), list) else []
    artifact_manifest = result.get("artifact_manifest") if isinstance(result.get("artifact_manifest"), dict) else None
    summary = {
        "status": result.get("status") or payload.get("status") or status.get("status"),
        "job_id": result.get("job_id"),
        "is_real_md": result.get("is_real_md"),
        "engine": result.get("engine"),
        "artifact_count": len(artifacts),
        "has_artifact_manifest": bool(artifact_manifest),
    }
    interpretation = result.get("interpretation")
    if isinstance(interpretation, dict):
        summary["interpretation"] = {
            "verdict": interpretation.get("verdict"),
            "confidence": interpretation.get("confidence"),
            "evidence_level": interpretation.get("evidence_level"),
        }
    lipase_context = result.get("lipase_evidence_context") if isinstance(result.get("lipase_evidence_context"), dict) else None
    batch_summary = result.get("batch_replicate_summary") if isinstance(result.get("batch_replicate_summary"), dict) else None
    if lipase_context is None and isinstance(batch_summary, dict):
        lipase_context = batch_summary.get("lipase_evidence_context") if isinstance(batch_summary.get("lipase_evidence_context"), dict) else None
    if lipase_context:
        counts = lipase_context.get("counts") if isinstance(lipase_context.get("counts"), dict) else {}
        summary["lipase_evidence"] = {
            "status": lipase_context.get("status"),
            "source": "kwb_lipase_db",
            "exact_mutation_matches": counts.get("exact_mutation_matches"),
            "position_matches": counts.get("position_matches"),
            "search_matches": counts.get("search_matches"),
            "strongest_evidence_level": lipase_context.get("strongest_evidence_level"),
        }
    wild_type = result.get("wild_type") if isinstance(result.get("wild_type"), dict) else {}
    structural = wild_type.get("structural_stability") if isinstance(wild_type.get("structural_stability"), dict) else {}
    compactness = wild_type.get("compactness") if isinstance(wild_type.get("compactness"), dict) else {}
    parameters = wild_type.get("simulation_parameters") if isinstance(wild_type.get("simulation_parameters"), dict) else {}
    if structural or compactness or parameters:
        sasa_change = compactness.get("sasa_change_nm2")
        if sasa_change is None and isinstance(compactness.get("sasa_final_nm2"), (int, float)) and isinstance(compactness.get("sasa_initial_nm2"), (int, float)):
            sasa_change = round(compactness["sasa_final_nm2"] - compactness["sasa_initial_nm2"], 4)
        summary["md_replicate"] = {
            "batch_id": parameters.get("batch_id"),
            "replicate_variant": parameters.get("replicate_variant"),
            "replicate_index": parameters.get("replicate_index"),
            "run_seed": parameters.get("run_seed"),
            "rmsd_drift_nm": structural.get("rmsd_drift_nm"),
            "mean_rmsf_nm": structural.get("mean_rmsf_nm"),
            "rg_change_nm": compactness.get("rg_change_nm"),
            "sasa_change_nm2": sasa_change,
            "is_stable": structural.get("is_stable"),
        }
    return summary, artifact_manifest


def _duration_seconds(row: ToolTaskAudit) -> int | None:
    if not row.submitted_at:
        return None
    end = row.terminal_recorded_at or row.cancel_effective_at
    if not end:
        return None
    try:
        return max(0, int((end - row.submitted_at).total_seconds()))
    except TypeError:
        return None


def _failure_class(row: ToolTaskAudit) -> str | None:
    status = str(row.status or "").lower()
    error = str(row.error or "").lower()
    if status in {"completed", "success"}:
        return None
    if status in {"canceled", "revoked", "cancel_requested"} or row.cancel_requested_at:
        return "canceled"
    if "time limit" in error or "timeout" in error or "timed out" in error:
        return "timeout"
    if "permission" in error or "forbidden" in error or "unauthorized" in error:
        return "permission"
    if "not found" in error or "no such file" in error:
        return "missing_input"
    if "gromacs" in error or "gmx" in error:
        return "md_runtime"
    if status in {"failed", "failure"}:
        return "runtime_error"
    return None


def _serialize_audit(row: ToolTaskAudit) -> dict[str, Any]:
    duration_seconds = _duration_seconds(row)
    return {
        "id": row.id,
        "task_id": row.task_id,
        "user_id": row.user_id,
        "tool": row.tool_name,
        "status": row.status,
        "queue": row.queue,
        "runtime_policy": {
            "soft_time_limit": row.soft_time_limit,
            "time_limit": row.time_limit,
        },
        "progress": row.progress,
        "stage": row.stage,
        "input_summary": row.input_summary,
        "result_summary": row.result_summary,
        "artifact_manifest": row.artifact_manifest,
        "error": row.error,
        "duration_seconds": duration_seconds,
        "failure_class": _failure_class(row),
        "is_slow": bool(duration_seconds is not None and duration_seconds >= SLOW_TASK_SECONDS),
        "runtime_environment": _runtime_environment(),
        "cancel_requested_at": row.cancel_requested_at.isoformat() if row.cancel_requested_at else None,
        "cancel_effective_at": row.cancel_effective_at.isoformat() if row.cancel_effective_at else None,
        "submitted_at": row.submitted_at.isoformat() if row.submitted_at else None,
        "terminal_recorded_at": row.terminal_recorded_at.isoformat() if row.terminal_recorded_at else None,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }


async def record_task_submitted(
    session: AsyncSession,
    *,
    task_id: str,
    user_id: int | str,
    tool_name: str,
    params: dict[str, Any],
    queue: str,
    soft_time_limit: int,
    time_limit: int,
) -> ToolTaskAudit:
    row = ToolTaskAudit(
        task_id=task_id,
        user_id=int(user_id),
        tool_name=tool_name,
        status="submitted",
        queue=queue,
        soft_time_limit=int(soft_time_limit),
        time_limit=int(time_limit),
        progress=0,
        input_summary=summarize_tool_input(params),
    )
    session.add(row)
    await session.flush()
    if tool_name == "blast_search":
        from app.services.blast_jobs import read_blast_job, sync_blast_job_audit

        _, job = await read_blast_job(session, task_id, lock=True)
        if job:
            await sync_blast_job_audit(session, job)
    return row


async def update_task_audit_from_status(
    session: AsyncSession,
    *,
    task_id: str,
    owner: dict[str, Any],
    status: dict[str, Any],
) -> ToolTaskAudit | None:
    result = await session.execute(select(ToolTaskAudit).where(ToolTaskAudit.task_id == task_id))
    row = result.scalar_one_or_none()
    if row is None:
        row = ToolTaskAudit(
            task_id=task_id,
            user_id=int(owner["user_id"]),
            tool_name=str(owner.get("tool") or status.get("tool") or "unknown"),
            submitted_at=_parse_dt(owner.get("submitted_at")),
        )
        session.add(row)

    normalized_status = str(status.get("status") or row.status or "unknown").lower()
    result_summary, artifact_manifest = summarize_tool_result(status)
    row.status = normalized_status
    row.queue = owner.get("queue") or status.get("queue") or row.queue
    row.soft_time_limit = owner.get("soft_time_limit") or status.get("soft_time_limit") or row.soft_time_limit
    row.time_limit = owner.get("time_limit") or status.get("time_limit") or row.time_limit
    row.progress = status.get("progress") if isinstance(status.get("progress"), int) else row.progress
    row.stage = status.get("stage") or row.stage
    row.result_summary = result_summary or row.result_summary
    row.artifact_manifest = artifact_manifest or row.artifact_manifest
    row.error = status.get("error") or row.error
    row.cancel_requested_at = _parse_dt(owner.get("cancel_requested_at")) or row.cancel_requested_at
    row.cancel_effective_at = _parse_dt(owner.get("cancel_effective_at")) or row.cancel_effective_at
    if normalized_status in TERMINAL_STATUSES:
        row.terminal_recorded_at = _parse_dt(owner.get("terminal_recorded_at")) or row.terminal_recorded_at
    await session.flush()
    return row


async def mark_task_cancel_requested(
    session: AsyncSession,
    *,
    task_id: str,
    owner: dict[str, Any],
) -> ToolTaskAudit | None:
    status = {
        "status": "cancel_requested",
        "progress": None,
        "error": None,
    }
    row = await update_task_audit_from_status(session, task_id=task_id, owner=owner, status=status)
    if row is not None:
        row.cancel_requested_at = _parse_dt(owner.get("cancel_requested_at")) or row.cancel_requested_at
        await session.flush()
    return row


async def list_task_audits(session: AsyncSession, *, user_id: int | str, limit: int = 50) -> list[dict[str, Any]]:
    result = await session.execute(
        select(ToolTaskAudit)
        .where(ToolTaskAudit.user_id == int(user_id))
        .order_by(desc(ToolTaskAudit.updated_at), desc(ToolTaskAudit.id))
        .limit(max(1, min(limit, 200)))
    )
    return [_serialize_audit(row) for row in result.scalars().all()]


def _row_batch_id(row: ToolTaskAudit) -> str | None:
    input_summary = row.input_summary if isinstance(row.input_summary, dict) else {}
    input_values = input_summary.get("values") if isinstance(input_summary.get("values"), dict) else {}
    result_summary = row.result_summary if isinstance(row.result_summary, dict) else {}
    md_replicate = result_summary.get("md_replicate") if isinstance(result_summary.get("md_replicate"), dict) else {}
    value = input_values.get("batch_id") or md_replicate.get("batch_id") or result_summary.get("batch_id")
    return str(value).strip() if value else None


async def list_md_replicate_batch_audits(
    session: AsyncSession,
    *,
    user_id: int | str,
    batch_id: str,
    limit: int = 1000,
) -> list[dict[str, Any]]:
    """List current user's GROMACS audit rows for one replicate batch.

    The batch id is stored inside compact JSON summaries, so filtering is kept
    in Python to remain portable across SQLite/PostgreSQL JSON dialects.
    """
    normalized_batch_id = str(batch_id or "").strip()
    if not normalized_batch_id:
        return []
    requested_limit = max(1, min(limit, 5000))
    result = await session.execute(
        select(ToolTaskAudit)
        .where(ToolTaskAudit.user_id == int(user_id), ToolTaskAudit.tool_name == "gromacs_md")
        .order_by(desc(ToolTaskAudit.updated_at), desc(ToolTaskAudit.id))
        .limit(requested_limit)
    )
    rows = [row for row in result.scalars().all() if _row_batch_id(row) == normalized_batch_id]
    return [_serialize_audit(row) for row in rows]


async def list_all_task_audits(session: AsyncSession, *, limit: int = 100) -> list[dict[str, Any]]:
    return await list_all_task_audits_filtered(session, limit=limit)


async def list_all_task_audits_filtered(
    session: AsyncSession,
    *,
    limit: int = 100,
    filters: ToolTaskAuditFilters | None = None,
) -> list[dict[str, Any]]:
    filters = filters or ToolTaskAuditFilters()
    requested_limit = max(1, min(limit, 500))
    fetch_limit = requested_limit
    if filters.failure_class or filters.slow_only:
        fetch_limit = max(requested_limit, 500)

    query = select(ToolTaskAudit)
    if filters.tool:
        query = query.where(ToolTaskAudit.tool_name == filters.tool)
    if filters.status:
        query = query.where(ToolTaskAudit.status == filters.status)
    if filters.queue:
        query = query.where(ToolTaskAudit.queue == filters.queue)
    if filters.submitted_after:
        query = query.where(ToolTaskAudit.submitted_at >= filters.submitted_after)
    if filters.submitted_before:
        query = query.where(ToolTaskAudit.submitted_at <= filters.submitted_before)
    if filters.failed_only:
        query = query.where(ToolTaskAudit.status.in_(("failed", "failure", "canceled", "revoked", "cancel_requested")))

    result = await session.execute(
        query.order_by(desc(ToolTaskAudit.updated_at), desc(ToolTaskAudit.id)).limit(fetch_limit)
    )
    audits = [_serialize_audit(row) for row in result.scalars().all()]
    if filters.failure_class:
        audits = [audit for audit in audits if audit.get("failure_class") == filters.failure_class]
    if filters.slow_only:
        audits = [audit for audit in audits if audit.get("is_slow")]
    return audits[:requested_limit]


def summarize_task_audits(audits: list[dict[str, Any]]) -> dict[str, Any]:
    status_counts: dict[str, int] = {}
    tool_counts: dict[str, int] = {}
    queue_counts: dict[str, int] = {}
    failure_counts: dict[str, int] = {}
    trend_by_day: dict[str, dict[str, Any]] = {}
    slow_count = 0
    durations: list[int] = []
    recent_failures: list[dict[str, Any]] = []

    for audit in audits:
        status = str(audit.get("status") or "unknown")
        tool = str(audit.get("tool") or "unknown")
        queue = str(audit.get("queue") or "unknown")
        status_counts[status] = status_counts.get(status, 0) + 1
        tool_counts[tool] = tool_counts.get(tool, 0) + 1
        queue_counts[queue] = queue_counts.get(queue, 0) + 1
        if audit.get("is_slow"):
            slow_count += 1
        duration = audit.get("duration_seconds")
        if isinstance(duration, int):
            durations.append(duration)
        failure_class = audit.get("failure_class")
        if failure_class:
            failure_counts[str(failure_class)] = failure_counts.get(str(failure_class), 0) + 1
            bucket_source = str(audit.get("terminal_recorded_at") or audit.get("updated_at") or audit.get("submitted_at") or "")
            bucket = bucket_source[:10] if len(bucket_source) >= 10 else "unknown"
            if bucket not in trend_by_day:
                trend_by_day[bucket] = {"date": bucket, "failure_counts": {}, "total_failures": 0}
            trend_by_day[bucket]["failure_counts"][str(failure_class)] = (
                trend_by_day[bucket]["failure_counts"].get(str(failure_class), 0) + 1
            )
            trend_by_day[bucket]["total_failures"] += 1
            if len(recent_failures) < 10:
                recent_failures.append(
                    {
                        "task_id": audit.get("task_id"),
                        "tool": tool,
                        "failure_class": failure_class,
                        "status": status,
                        "updated_at": audit.get("updated_at"),
                    }
                )

    mean_duration = int(sum(durations) / len(durations)) if durations else None
    max_duration = max(durations) if durations else None
    total_failures = sum(failure_counts.values())
    alert_rules = [
        {
            "name": "task_failures",
            "status": "triggered" if total_failures >= FAILURE_ALERT_THRESHOLD else "ok",
            "severity": "warning",
            "threshold": FAILURE_ALERT_THRESHOLD,
            "observed": total_failures,
        },
        {
            "name": "slow_tasks",
            "status": "triggered" if slow_count >= SLOW_TASK_ALERT_THRESHOLD else "ok",
            "severity": "warning",
            "threshold": SLOW_TASK_ALERT_THRESHOLD,
            "observed": slow_count,
        },
    ]
    triggered_rules = [rule for rule in alert_rules if rule["status"] == "triggered"]
    return {
        "total": len(audits),
        "status_counts": status_counts,
        "tool_counts": tool_counts,
        "queue_counts": queue_counts,
        "failure_counts": failure_counts,
        "slow_count": slow_count,
        "duration": {
            "mean_seconds": mean_duration,
            "max_seconds": max_duration,
            "sample_count": len(durations),
        },
        "recent_failures": recent_failures,
        "failure_trend": [trend_by_day[key] for key in sorted(trend_by_day.keys())],
        "alerting": {
            "status": "triggered" if triggered_rules else "ok",
            "mode": "summary_only",
            "external_delivery": "not_configured",
            "rules": alert_rules,
            "recommended_actions": [
                "Configure an external webhook/notifier before enabling delivery.",
                "Use the same filters on /api/tools/admin/tasks/audits/export for incident evidence.",
            ] if triggered_rules else [],
        },
        "runtime_environment": _runtime_environment(),
    }


def serialize_task_audits_csv(audits: list[dict[str, Any]]) -> str:
    """Serialize sanitized task audits for admin export."""
    output = io.StringIO()
    fieldnames = [
        "task_id",
        "user_id",
        "tool",
        "status",
        "queue",
        "progress",
        "stage",
        "soft_time_limit",
        "time_limit",
        "submitted_at",
        "terminal_recorded_at",
        "duration_seconds",
        "failure_class",
        "is_slow",
        "python_version",
        "platform",
        "updated_at",
        "error",
        "input_summary",
        "result_summary",
        "artifact_manifest",
    ]
    writer = csv.DictWriter(output, fieldnames=fieldnames)
    writer.writeheader()
    for audit in audits:
        runtime_policy = audit.get("runtime_policy") if isinstance(audit.get("runtime_policy"), dict) else {}
        writer.writerow(
            {
                "task_id": audit.get("task_id"),
                "user_id": audit.get("user_id"),
                "tool": audit.get("tool"),
                "status": audit.get("status"),
                "queue": audit.get("queue"),
                "progress": audit.get("progress"),
                "stage": audit.get("stage"),
                "soft_time_limit": runtime_policy.get("soft_time_limit"),
                "time_limit": runtime_policy.get("time_limit"),
                "submitted_at": audit.get("submitted_at"),
                "terminal_recorded_at": audit.get("terminal_recorded_at"),
                "duration_seconds": audit.get("duration_seconds"),
                "failure_class": audit.get("failure_class"),
                "is_slow": audit.get("is_slow"),
                "python_version": (audit.get("runtime_environment") or {}).get("python_version") if isinstance(audit.get("runtime_environment"), dict) else None,
                "platform": (audit.get("runtime_environment") or {}).get("platform") if isinstance(audit.get("runtime_environment"), dict) else None,
                "updated_at": audit.get("updated_at"),
                "error": audit.get("error"),
                "input_summary": json.dumps(audit.get("input_summary"), ensure_ascii=False, sort_keys=True),
                "result_summary": json.dumps(audit.get("result_summary"), ensure_ascii=False, sort_keys=True),
                "artifact_manifest": json.dumps(audit.get("artifact_manifest"), ensure_ascii=False, sort_keys=True),
            }
        )
    return output.getvalue()


async def get_task_audit(session: AsyncSession, *, task_id: str, user_id: int | str) -> dict[str, Any] | None:
    result = await session.execute(
        select(ToolTaskAudit).where(
            ToolTaskAudit.task_id == task_id,
            ToolTaskAudit.user_id == int(user_id),
        )
    )
    row = result.scalar_one_or_none()
    return _serialize_audit(row) if row else None


async def get_any_task_audit(session: AsyncSession, *, task_id: str) -> dict[str, Any] | None:
    result = await session.execute(select(ToolTaskAudit).where(ToolTaskAudit.task_id == task_id))
    row = result.scalar_one_or_none()
    return _serialize_audit(row) if row else None
