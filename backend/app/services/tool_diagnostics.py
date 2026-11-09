"""Runtime diagnostics for tools and core dependencies."""

from __future__ import annotations

import time
from collections import Counter
from typing import Any

import httpx
from minio import Minio
from sqlalchemy import text

from app.core.config import settings
from app.core.database import _async_session_factory
from app.services.tool_cache import cache_diagnostics
from app.tools.registry import ToolRegistry


async def _timed(awaitable):
    start = time.perf_counter()
    result = await awaitable
    return result, round((time.perf_counter() - start) * 1000, 2)


async def _check_database(include_table_counts: bool) -> dict[str, Any]:
    details: dict[str, Any] = {"ok": False}
    async with _async_session_factory() as session:
        _, ping_ms = await _timed(session.execute(text("select 1")))
        details.update({"ok": True, "latency_ms": ping_ms})
        if include_table_counts:
            tables = [
                "enzyme_records",
                "kinetic_parameters",
                "stability_records",
                "substrate_compounds",
                "database_crossrefs",
            ]
            counts: dict[str, int] = {}
            for table in tables:
                value = (await session.execute(text(f"select count(*) from {table}"))).scalar_one()
                counts[table] = int(value)
            details["table_counts"] = counts
    return details


async def _check_minio() -> dict[str, Any]:
    start = time.perf_counter()
    client = Minio(
        settings.MINIO_ENDPOINT,
        access_key=settings.MINIO_ACCESS_KEY,
        secret_key=settings.MINIO_SECRET_KEY,
        secure=settings.MINIO_SECURE,
        region=settings.MINIO_REGION or None,
    )
    buckets = [bucket.name for bucket in client.list_buckets()]
    return {
        "ok": True,
        "latency_ms": round((time.perf_counter() - start) * 1000, 2),
        "endpoint": settings.MINIO_ENDPOINT,
        "secure": settings.MINIO_SECURE,
        "bucket_count": len(buckets),
        "buckets": buckets[:10],
    }


async def _check_chromadb() -> dict[str, Any]:
    start = time.perf_counter()
    url = f"http://{settings.CHROMA_HOST}:{settings.CHROMA_PORT}/api/v2/heartbeat"
    async with httpx.AsyncClient(timeout=5.0) as client:
        response = await client.get(url)
        response.raise_for_status()
    return {
        "ok": True,
        "latency_ms": round((time.perf_counter() - start) * 1000, 2),
        "heartbeat": response.text[:120],
        "collections": {"available": True},
    }


async def collect_tool_diagnostics(include_table_counts: bool = False) -> dict[str, Any]:
    ToolRegistry.discover()
    categories = Counter(tool.category for tool in ToolRegistry._tools.values())

    services: dict[str, Any] = {}
    checks = {
        "database": _check_database(include_table_counts),
        "cache": cache_diagnostics(),
        "minio": _check_minio(),
        "chromadb": _check_chromadb(),
    }
    for name, awaitable in checks.items():
        try:
            services[name] = await awaitable
        except Exception as exc:
            services[name] = {"ok": False, "error": str(exc)}

    return {
        "status": "ok",
        "tool_registry": {
            "tool_count": len(ToolRegistry._tools),
            "categories": dict(sorted(categories.items())),
            "tools": sorted(ToolRegistry._tools.keys()),
        },
        "performance_defaults": {
            "search_cache_ttl_seconds": settings.SEARCH_CACHE_TTL_SECONDS,
            "search_cache_stale_ttl_seconds": settings.SEARCH_CACHE_STALE_TTL_SECONDS,
            "blast_poll_budget_seconds": settings.BLAST_POLL_BUDGET_SECONDS,
            "uniprot_search_timeout_seconds": settings.UNIPROT_SEARCH_TIMEOUT_SECONDS,
            "blast_http_read_timeout_seconds": settings.BLAST_HTTP_READ_TIMEOUT_SECONDS,
        },
        "services": services,
    }
