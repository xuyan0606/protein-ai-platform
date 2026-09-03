"""Redis-backed JSON cache with in-process fallback for tool results."""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import time
from dataclasses import dataclass
from typing import Any

from app.core.config import settings

logger = logging.getLogger(__name__)

try:
    import redis.asyncio as redis_asyncio
except Exception:  # pragma: no cover - import guard for minimal runtimes
    redis_asyncio = None


@dataclass
class _LocalEntry:
    payload: dict[str, Any]
    redis_expires_at: float


_redis_client = None
_redis_failed = False
_local_cache: dict[str, _LocalEntry] = {}
_LOCAL_CACHE_MAX = 512


def build_cache_key(namespace: str, params: dict[str, Any]) -> str:
    raw = json.dumps(params, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()
    return f"protein_ai:{namespace}:{digest}"


async def _get_redis():
    global _redis_client, _redis_failed
    if _redis_failed:
        return None
    if _redis_client is None:
        if redis_asyncio is None:
            _redis_failed = True
            return None
        try:
            _redis_client = redis_asyncio.from_url(
                settings.REDIS_URL,
                encoding="utf-8",
                decode_responses=True,
                socket_timeout=2.0,
                socket_connect_timeout=2.0,
                health_check_interval=30,
            )
            await _redis_client.ping()
        except Exception as exc:
            logger.warning("Redis cache unavailable, using local fallback: %s", exc)
            _redis_client = None
            _redis_failed = True
            return None
    return _redis_client


def _local_gc() -> None:
    now = time.time()
    expired = [key for key, entry in _local_cache.items() if entry.redis_expires_at <= now]
    for key in expired:
        _local_cache.pop(key, None)
    while len(_local_cache) > _LOCAL_CACHE_MAX:
        oldest = min(_local_cache, key=lambda key: _local_cache[key].redis_expires_at)
        _local_cache.pop(oldest, None)


async def get_json(key: str) -> dict[str, Any] | None:
    client = await _get_redis()
    if client is not None:
        try:
            raw = await client.get(key)
            return json.loads(raw) if raw else None
        except Exception as exc:
            logger.warning("Redis cache read failed for %s: %s", key, exc)

    _local_gc()
    entry = _local_cache.get(key)
    if not entry:
        return None
    return entry.payload


async def set_json(key: str, payload: dict[str, Any], ttl_seconds: int) -> None:
    client = await _get_redis()
    if client is not None:
        try:
            await client.setex(key, ttl_seconds, json.dumps(payload, ensure_ascii=False, default=str))
            return
        except Exception as exc:
            logger.warning("Redis cache write failed for %s: %s", key, exc)

    _local_gc()
    _local_cache[key] = _LocalEntry(payload=payload, redis_expires_at=time.time() + ttl_seconds)


async def get_cached_result(
    namespace: str,
    params: dict[str, Any],
    *,
    allow_stale: bool = False,
) -> dict[str, Any] | None:
    payload = await get_json(build_cache_key(namespace, params))
    if not payload:
        return None
    now = time.time()
    if not allow_stale and payload.get("expires_at", 0) <= now:
        return None
    value = payload.get("value")
    if isinstance(value, dict):
        value = dict(value)
    if isinstance(value, dict):
        value.setdefault("cache", {})
        value["cache"].update(
            {
                "hit": True,
                "stale": payload.get("expires_at", 0) <= now,
                "backend": "redis" if await _get_redis() is not None else "local",
                "cached_at": payload.get("cached_at"),
                "expires_at": payload.get("expires_at"),
                "stale_until": payload.get("stale_until"),
            }
        )
    return value


async def set_cached_result(
    namespace: str,
    params: dict[str, Any],
    value: dict[str, Any],
    *,
    ttl_seconds: int | None = None,
    stale_ttl_seconds: int | None = None,
) -> None:
    ttl = int(ttl_seconds or settings.SEARCH_CACHE_TTL_SECONDS)
    stale_ttl = int(stale_ttl_seconds or settings.SEARCH_CACHE_STALE_TTL_SECONDS)
    now = time.time()
    payload = {
        "cached_at": now,
        "expires_at": now + ttl,
        "stale_until": now + stale_ttl,
        "value": value,
    }
    await set_json(build_cache_key(namespace, params), payload, stale_ttl)


async def cache_diagnostics() -> dict[str, Any]:
    start = time.perf_counter()
    client = await _get_redis()
    redis_available = False
    error = None
    try:
        if client is not None:
            redis_available = bool(await client.ping())
    except Exception as exc:
        error = str(exc)
    elapsed_ms = round((time.perf_counter() - start) * 1000, 2)
    _local_gc()
    return {
        "redis_available": redis_available,
        "backend": "redis" if redis_available else "local",
        "local_entries": len(_local_cache),
        "latency_ms": elapsed_ms,
        "error": error,
        "ttl_seconds": settings.SEARCH_CACHE_TTL_SECONDS,
        "stale_ttl_seconds": settings.SEARCH_CACHE_STALE_TTL_SECONDS,
    }
