"""In-memory sliding-window rate limiter for FastAPI.

Lightweight, zero-dependency rate limiter suitable for single-process deployments.
For multi-process/clustered deployments, replace with Redis-backed implementation.

Usage as a FastAPI dependency:
    from app.core.rate_limiter import rate_limit

    @router.post("/login")
    async def login(..., _rl=Depends(rate_limit("login", max_requests=5, window=60))):
        ...
"""

from __future__ import annotations

import time
from collections import defaultdict
from typing import Callable

from fastapi import HTTPException, Request, status


class _SlidingWindow:
    """Per-key sliding window counter."""

    def __init__(self):
        self._hits: dict[str, list[float]] = defaultdict(list)

    def is_allowed(self, key: str, max_requests: int, window_seconds: int) -> bool:
        now = time.time()
        cutoff = now - window_seconds

        # Prune old entries
        hits = self._hits[key]
        self._hits[key] = [t for t in hits if t > cutoff]

        if len(self._hits[key]) >= max_requests:
            return False

        self._hits[key].append(now)
        return True

    def cleanup(self, max_age: int = 600) -> None:
        """Remove stale keys to prevent memory leaks."""
        now = time.time()
        stale_keys = [
            k for k, v in self._hits.items()
            if not v or (now - v[-1]) > max_age
        ]
        for k in stale_keys:
            del self._hits[k]


# Module-level singleton
_window = _SlidingWindow()


def rate_limit(
    namespace: str,
    max_requests: int = 10,
    window: int = 60,
) -> Callable:
    """Create a rate-limiting dependency function for FastAPI.

    Usage:
        @router.post("/login")
        async def login(..., _rl=Depends(rate_limit("login", 10, 60))):
            ...

    Args:
        namespace: Unique identifier for this rate limit bucket.
        max_requests: Maximum requests allowed per window.
        window: Time window in seconds.

    Returns:
        An async dependency function (NOT a Depends wrapper).
    """
    async def _check(request: Request) -> None:
        client_ip = request.client.host if request.client else "unknown"
        key = f"{namespace}:{client_ip}"

        if not _window.is_allowed(key, max_requests, window):
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Too many requests. Please try again in {window} seconds.",
                headers={"Retry-After": str(window)},
            )

    return _check
