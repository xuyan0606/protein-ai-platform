"""Durable BLAST jobs: one remote request per Celery invocation."""
from __future__ import annotations

import json
import hashlib
import time
from datetime import datetime, timezone

import httpx
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.config import settings
from app.models.domain import KVStore
from app.models.tool_call import ToolTaskAudit
from app.services.tool_task_audit import update_task_audit_from_status
from app.services.evidence_source_status import evidence_source_status
from app.services.ncbi_api import NCBIRateLimitError
from app.tools.blast_search import submit_blast, poll_blast, _result_payload

TERMINAL = {"completed", "failed", "degraded", "canceled"}


async def read_blast_job(session: AsyncSession, task_id: str, *, lock: bool = False) -> tuple[KVStore | None, dict]:
    if lock and session.bind.dialect.name == "postgresql":
        # Also serialize creation/cancel when a checkpoint row does not yet exist.
        key = int.from_bytes(hashlib.sha256(f"blast-job:{task_id}".encode()).digest()[:8], "big", signed=True)
        await session.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": key})
    query = select(KVStore).where(KVStore.key == f"blast-job:{task_id}").execution_options(populate_existing=True)
    if lock:
        query = query.with_for_update()
    row = (await session.execute(query)).scalar_one_or_none()
    return row, json.loads(row.value) if row else {}


async def save_blast_job(session: AsyncSession, row: KVStore, job: dict) -> dict:
    row.value = json.dumps(job, ensure_ascii=False)
    await sync_blast_job_audit(session, job)
    await session.commit()  # RID must survive worker exit before Celery retry
    return job


async def sync_blast_job_audit(session: AsyncSession, job: dict) -> None:
    """Keep the owned audit and durable checkpoint in the same transaction."""
    audit = (await session.execute(
        select(ToolTaskAudit).where(ToolTaskAudit.task_id == job["task_id"]).with_for_update()
    )).scalar_one_or_none()
    if audit is None:
        # Dispatch can finish before the API commits ownership. Submission
        # reconciles the checkpoint once its audit row exists.
        return
    status = job_status(job)
    await update_task_audit_from_status(
        session, task_id=job["task_id"], owner={"user_id": audit.user_id}, status=status,
    )
    audit.error = status["error"]
    if job["status"] in TERMINAL:
        audit.terminal_recorded_at = audit.terminal_recorded_at or datetime.now(timezone.utc)
    else:
        # A resumed RID is active again; don't retain an expired round's error
        # or result as though the resumed search had already finished.
        audit.terminal_recorded_at = None
        audit.result_summary = None
    await session.flush()


async def cancel_blast_job(session: AsyncSession, task_id: str) -> dict:
    row, job = await read_blast_job(session, task_id, lock=True)
    if job.get("status") in {"completed", "failed", "canceled"}:
        return job
    if row is None:
        row = KVStore(key=f"blast-job:{task_id}", value="{}")
        session.add(row)
    job.update(task_id=task_id, status="canceled", result=None, stage="canceled", message="已取消后续查询。")
    return await save_blast_job(session, row, job)


def job_status(job: dict) -> dict:
    status = job["status"]
    return {"task_id": job["task_id"], "status": status, "result": job.get("result"),
            "error": job.get("error") if status in TERMINAL - {"completed"} else None,
            "progress": 100 if status in TERMINAL else 0, "stage": job.get("stage"),
            "message": job.get("message"), "rid": job.get("rid"),
            "next_poll_at": job.get("next_poll_at"), "deadline_at": job.get("deadline_at"),
            "last_checked_at": job.get("last_checked_at"), "can_resume": status == "degraded" and bool(job.get("rid"))}


def _finish(job: dict, *, status: str, code: str, message: str) -> None:
    p = job["params"]
    job.update(status=status, stage=code.lower(), error=message, message=message)
    job["result"] = _result_payload(seq=p["sequence"], program=p["program"], database=p["database"], hits=[],
        status=status, error_code=code, warning=message,
        evidence_source=evidence_source_status(source="NCBI BLAST", status="degraded", mode="durable_job",
            live_query_executed=False, reason=code))
    job["result"]["rid"] = job.get("rid")


async def advance_blast_job(session: AsyncSession, task_id: str, params: dict, *, now: float | None = None) -> dict:
    """Resume the saved RID; do not sleep inside a worker slot."""
    clock = time.time if now is None else lambda: now
    now = clock()
    row, job = await read_blast_job(session, task_id, lock=True)
    if not row:
        normalized = {"sequence": str(params.get("sequence", "")).strip().upper(),
                      "program": params.get("program", "blastp"), "database": params.get("database", "nr"),
                      "max_results": int(params.get("max_results", 10))}
        job = {"task_id": task_id, "params": normalized, "status": "submitting", "rid": None,
               "created_at": now, "deadline_at": now + settings.BLAST_BACKGROUND_WAIT_SECONDS,
               "network_errors": 0, "result": None, "next_poll_at": now + 120}
        row = KVStore(key=f"blast-job:{task_id}", value="{}")
        session.add(row)
        await save_blast_job(session, row, job)
        try:
            rid, estimate = await submit_blast(**normalized)
        except (httpx.HTTPError, RuntimeError, ValueError) as exc:
            row, job = await read_blast_job(session, task_id, lock=True)
            if job["status"] == "canceled":
                return job
            _finish(job, status="failed", code="BLAST_SUBMISSION_UNCONFIRMED",
                    message=f"NCBI 提交未确认；为避免重复提交已停止，请重新发起搜索。{type(exc).__name__}")
        else:
            row, job = await read_blast_job(session, task_id, lock=True)
            if job["status"] == "canceled":
                job["rid"] = rid
                return await save_blast_job(session, row, job)
            job.update(rid=rid, status="waiting", stage="ncbi_waiting", message="NCBI 正在处理，后台将持续查询。",
                       next_poll_at=clock() + max(60, min(estimate, 300)))
        return await save_blast_job(session, row, job)
    if job["status"] in TERMINAL:
        return job
    if not job.get("rid"):
        if now < job.get("next_poll_at", 0):
            return job
        _finish(job, status="failed", code="BLAST_SUBMISSION_UNCONFIRMED",
                message="提交时服务中断，未保存 NCBI 编号；为避免重复提交已停止，请重新发起搜索。")
        return await save_blast_job(session, row, job)
    if now >= job["deadline_at"]:
        _finish(job, status="degraded", code="BLAST_WAIT_EXPIRED",
                message="已达到本轮后台等待上限，尚未获得结果；可继续查询原任务。此状态不表示无同源命中。")
        return await save_blast_job(session, row, job)
    if now < job.get("next_poll_at", 0):
        return job
    job["last_checked_at"] = now
    try:
        hits = await poll_blast(job["rid"], job["params"]["max_results"])
    except (httpx.HTTPError, NCBIRateLimitError) as exc:
        job["network_errors"] += 1
        job.update(stage="ncbi_retrying", message="NCBI 暂时连接异常，已保留任务并安排重试。",
                   last_network_error=type(exc).__name__)
        delay = min(300, 60 * 2 ** min(job["network_errors"], 3))
        if isinstance(exc, NCBIRateLimitError):
            try:
                delay = max(delay, min(1800, int(exc.retry_after or 60)))
            except ValueError:
                pass
    except RuntimeError as exc:
        _finish(job, status="failed", code="BLAST_REMOTE_FAILED", message=str(exc))
        return await save_blast_job(session, row, job)
    else:
        delay = 60
        if hits is not None:
            p = job["params"]
            payload = _result_payload(seq=p["sequence"], program=p["program"], database=p["database"], hits=hits,
                evidence_source=evidence_source_status(source="NCBI BLAST", status="live", mode="durable_ncbi_blast",
                    live_query_executed=True, details={"rid": job["rid"], "retrieved_at": now}))
            payload["rid"] = job["rid"]
            job.update(status="completed", stage="completed", completed_at=now, result=payload,
                       message=f"同源搜索已完成，获得 {len(hits)} 个命中；可生成更新报告。")
            return await save_blast_job(session, row, job)
        job.update(stage="ncbi_waiting", message="NCBI 正在处理，后台将持续查询。")
    job.update(status="waiting", next_poll_at=clock() + delay)
    return await save_blast_job(session, row, job)


async def run_worker_blast_step(task_id: str, params: dict) -> dict:
    # Celery creates a new event loop per invocation: do not share asyncpg pools.
    engine = create_async_engine(settings.DATABASE_URL, poolclass=NullPool)
    try:
        async with AsyncSession(engine, expire_on_commit=False) as session:
            return await advance_blast_job(session, task_id, params)
    finally:
        await engine.dispose()
