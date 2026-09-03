"""Celery task scheduler for async GPU protein computation tasks.

Workers connect to Redis broker. Each async tool (alphafold, diffdock, etc.)
is dispatched as a Celery task. Results are stored in Redis and polled by
the API layer for SSE progress notifications.
"""

from __future__ import annotations

from dataclasses import dataclass
import logging
from typing import Any

from celery import Celery
from celery.result import AsyncResult

from app.core.config import settings
from app.core.metrics import tool_calls_total, tool_call_duration_seconds

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class TaskProfile:
    queue: str
    soft_time_limit: int
    time_limit: int

celery_app = Celery(
    "protein_ai",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    broker_connection_retry_on_startup=True,
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    task_soft_time_limit=600,  # 10 min default
    task_time_limit=900,        # 15 min hard limit
)

# Async tool tasks — each corresponds to a registered tool that may
# take longer than the HTTP request timeout.
ASYNC_TOOLS = {
    "alphafold_folding",
    "diffdock_docking",
    "esmfold_folding",
    "proteinmpnn_design",
    "rfdiffusion_design",
    "esm3_generate",
    "ligandmpnn_design",
    "rosettafold_folding",
    "rosettafold_allatom",
    "boltz1_predict",
    "ligand_preprocess",
    "gromacs_md",
    "blast_search",
}

_DEFAULT_TASK_PROFILE = TaskProfile(queue="default", soft_time_limit=600, time_limit=900)
_TASK_PROFILES: dict[str, TaskProfile] = {
    # Real MD is longer-running and should be isolated from lighter async tools.
    "gromacs_md": TaskProfile(queue="md_cpu", soft_time_limit=3600, time_limit=5400),
    # Ligand conversion/docking prep can invoke external chemistry tools.
    "ligand_preprocess": TaskProfile(queue="ligand_cpu", soft_time_limit=1800, time_limit=2700),
    # NCBI BLAST is an external polling workflow; keep chat confirmation responsive.
    "blast_search": TaskProfile(queue="default", soft_time_limit=420, time_limit=600),
}


def get_execution_mode(tool_name: str) -> str:
    """Return the API dispatch mode from the scheduler's authoritative set."""
    return "async_worker" if tool_name in ASYNC_TOOLS else "inline_sync"


def get_task_profile(tool_name: str) -> TaskProfile:
    """Return queue and timeout policy for an async tool."""
    return _TASK_PROFILES.get(tool_name, _DEFAULT_TASK_PROFILE)


def dispatch_tool(tool_name: str, params: dict[str, Any]) -> str:
    """Enqueue an async tool execution. Returns Celery task ID."""
    if tool_name not in ASYNC_TOOLS:
        raise ValueError(f"Tool '{tool_name}' is not an async tool. Use sync execution.")
    profile = get_task_profile(tool_name)
    result = run_tool_task.apply_async(
        args=[tool_name, params],
        queue=profile.queue,
        soft_time_limit=profile.soft_time_limit,
        time_limit=profile.time_limit,
    )
    logger.info("Dispatched %s as task %s", tool_name, result.id)
    return result.id


def _ensure_tool_registry_ready(tool_name: str) -> None:
    """Make worker-side tool registration resilient to lazy process startup."""
    from app.tools.registry import ToolRegistry

    if not ToolRegistry._tools:
        logger.info("Tool registry empty in worker; discovering tools for %s", tool_name)
        ToolRegistry.discover()


def _safe_async_result_snapshot(task_id: str) -> tuple[str, dict[str, Any], Any, str | None]:
    """Read Celery result backend defensively.

    Celery can raise while decoding malformed exception payloads from Redis.
    In that case, downgrade to a failed task payload instead of propagating a 500.
    """
    try:
        result = AsyncResult(task_id, app=celery_app)
    except Exception as exc:
        logger.exception("Failed to create AsyncResult for task %s", task_id)
        return "FAILURE", {}, None, f"Task backend unavailable: {exc}"

    backend_error: str | None = None

    try:
        status = result.state
    except Exception as exc:
        logger.exception("Failed to read Celery task state for %s", task_id)
        status = "FAILURE"
        backend_error = f"Task backend decode error: {exc}"

    try:
        info = result.info
    except Exception as exc:
        logger.exception("Failed to read Celery task info for %s", task_id)
        info = {}
        backend_error = backend_error or f"Task backend decode error: {exc}"

    try:
        raw_result = result.result
    except Exception as exc:
        logger.exception("Failed to read Celery task result for %s", task_id)
        raw_result = None
        backend_error = backend_error or f"Task backend decode error: {exc}"

    if not isinstance(info, dict):
        if info not in (None, ""):
            backend_error = backend_error or f"Task backend returned unexpected payload: {info}"
        info = {}

    return status, info, raw_result, backend_error


def get_task_status(task_id: str) -> dict[str, Any]:
    """Poll the status of a Celery task."""
    status, info, raw_result, backend_error = _safe_async_result_snapshot(task_id)
    if backend_error:
        status = "FAILURE"

    payload_result = info.get("result") if isinstance(info.get("result"), dict) else None
    payload_status = None
    if isinstance(payload_result, dict):
        nested_status = payload_result.get("status")
        if isinstance(nested_status, str) and nested_status.strip():
            payload_status = nested_status.lower()
    if payload_status is None and isinstance(info.get("status"), str):
        payload_status = str(info.get("status")).lower()
    payload_error = (
        info.get("error")
        or (payload_result.get("error") if payload_result else None)
        or backend_error
        or (str(raw_result) if status == "FAILURE" and raw_result else None)
        or (str(raw_result) if status == "REVOKED" and raw_result else None)
    )
    normalized_status = status.lower()
    if normalized_status == "success":
        normalized_status = "completed"
    elif normalized_status == "failure":
        normalized_status = "failed"
    elif normalized_status == "started":
        normalized_status = "running"
    elif normalized_status == "revoked":
        normalized_status = "canceled"
    if status == "SUCCESS" and payload_status in {"failed", "failure"}:
        normalized_status = "failed"
    elif status == "SUCCESS" and payload_status in {"canceled", "cancelled", "revoked"}:
        normalized_status = "canceled"
    return {
        "task_id": task_id,
        "status": normalized_status,
        "result": info.get("result") if status == "SUCCESS" and not backend_error else None,
        "error": payload_error if normalized_status in {"failed", "canceled"} else None,
        "progress": info.get("progress", 100 if status in {"SUCCESS", "FAILURE", "REVOKED"} else 0),
        "message": info.get("message") if isinstance(info.get("message"), str) else None,
        "stage": info.get("stage") if isinstance(info.get("stage"), str) else None,
        "current_step": int(info.get("current_step")) if isinstance(info.get("current_step"), int) else None,
        "total_steps": int(info.get("total_steps")) if isinstance(info.get("total_steps"), int) else None,
    }


def cancel_task(task_id: str) -> bool:
    """Attempt to revoke a running task."""
    celery_app.control.revoke(task_id, terminate=True, signal="SIGTERM")
    logger.info("Revoked task %s", task_id)
    return True


@celery_app.task(bind=True, name="protein_ai.run_tool")
def run_tool_task(self, tool_name: str, params: dict[str, Any]) -> dict[str, Any]:
    """Execute an async protein tool and return results.

    Updates Celery state for progress tracking so the API can relay
    progress via SSE to the frontend.
    """
    import asyncio
    import time
    from app.tools.registry import ToolRegistry

    task_id = self.request.id

    def progress_callback(progress: int, message: str, stage: str, current_step: int, total_steps: int) -> None:
        self.update_state(
            task_id=task_id,
            state="RUNNING",
            meta={
                "progress": max(0, min(100, int(progress))),
                "tool": tool_name,
                "message": message,
                "stage": stage,
                "current_step": max(0, int(current_step)),
                "total_steps": max(0, int(total_steps)),
            },
        )

    self.update_state(
        task_id=task_id,
        state="RUNNING",
        meta={
            "progress": 0,
            "tool": tool_name,
            "message": "Worker accepted task",
            "stage": "queued_in_worker",
            "current_step": 0,
            "total_steps": 0,
        },
    )
    t0 = time.monotonic()

    try:
        _ensure_tool_registry_ready(tool_name)
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        result = loop.run_until_complete(
            ToolRegistry.execute(
                tool_name,
                params,
                internal_params={"progress_callback": progress_callback},
            )
        )
        loop.close()
        self.update_state(task_id=task_id, state="SUCCESS", meta={"progress": 100, "result": result})
        tool_calls_total.labels(tool_name=tool_name, status="success").inc()
        tool_call_duration_seconds.labels(tool_name=tool_name).observe(time.monotonic() - t0)
        return {"status": "completed", "tool": tool_name, "result": result}
    except Exception as exc:
        logger.exception("Task %s (%s) failed", self.request.id, tool_name)
        # Celery's result backend expects exception metadata for FAILURE
        # states. Omitting exc_type creates a second decode error and hides
        # the original tool failure from API polling.
        self.update_state(
            task_id=task_id,
            state="FAILURE",
            meta={
                "progress": 100,
                "error": str(exc),
                "exc_type": type(exc).__name__,
                "exc_message": str(exc),
                "exc_module": type(exc).__module__,
            },
        )
        tool_calls_total.labels(tool_name=tool_name, status="failed").inc()
        tool_call_duration_seconds.labels(tool_name=tool_name).observe(time.monotonic() - t0)
        raise
