"""Celery task scheduler for async GPU protein computation tasks.

Workers connect to Redis broker. Each async tool (alphafold, diffdock, etc.)
is dispatched as a Celery task. Results are stored in Redis and polled by
the API layer for SSE progress notifications.
"""

from __future__ import annotations

import logging
from typing import Any

from celery import Celery
from celery.result import AsyncResult

from app.core.config import settings
from app.core.metrics import tool_calls_total, tool_call_duration_seconds

logger = logging.getLogger(__name__)

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
    "alphafold2_folding",
    "diffdock_docking",
    "esmfold_folding",
    "proteinmpnn_design",
    "rfdiffusion_design",
    "esm3_generate",
    "ligandmpnn_design",
    "rosettafold_folding",
    "rosettafold_allatom",
    "boltz1_predict",
    "gromacs_md",
}


def dispatch_tool(tool_name: str, params: dict[str, Any]) -> str:
    """Enqueue an async tool execution. Returns Celery task ID."""
    if tool_name not in ASYNC_TOOLS:
        raise ValueError(f"Tool '{tool_name}' is not an async tool. Use sync execution.")
    result = run_tool_task.delay(tool_name, params)
    logger.info("Dispatched %s as task %s", tool_name, result.id)
    return result.id


def get_task_status(task_id: str) -> dict[str, Any]:
    """Poll the status of a Celery task."""
    result = AsyncResult(task_id, app=celery_app)
    status = result.state
    info = result.info if result.info and isinstance(result.info, dict) else {}
    return {
        "task_id": task_id,
        "status": status.lower(),
        "result": info.get("result") if status == "SUCCESS" else None,
        "error": info.get("error") if status == "FAILURE" else None,
        "progress": info.get("progress", 0),
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

    self.update_state(state="RUNNING", meta={"progress": 0, "tool": tool_name})
    t0 = time.monotonic()

    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        result = loop.run_until_complete(ToolRegistry.execute(tool_name, params))
        loop.close()
        self.update_state(state="SUCCESS", meta={"progress": 100, "result": result})
        tool_calls_total.labels(tool_name=tool_name, status="success").inc()
        tool_call_duration_seconds.labels(tool_name=tool_name).observe(time.monotonic() - t0)
        return {"status": "completed", "tool": tool_name, "result": result}
    except Exception as exc:
        logger.exception("Task %s (%s) failed", self.request.id, tool_name)
        self.update_state(state="FAILURE", meta={"progress": 100, "error": str(exc)})
        tool_calls_total.labels(tool_name=tool_name, status="failed").inc()
        tool_call_duration_seconds.labels(tool_name=tool_name).observe(time.monotonic() - t0)
        return {"status": "failed", "tool": tool_name, "error": str(exc)}
