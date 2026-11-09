"""Evidence source status helpers for live/degraded/blocked reporting."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


def evidence_source_status(
    *,
    source: str,
    status: str,
    mode: str,
    live_query_executed: bool,
    version: str | None = None,
    endpoint: str | None = None,
    reason: str | None = None,
    details: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Return a normalized evidence-source status payload.

    `status` is intentionally coarse:
    - live: a current external query or real live data source was used.
    - degraded: local cache, imported data, stale cache, or heuristic fallback.
    - blocked: input, network, runtime, or policy prevented usable evidence.
    """
    normalized = status if status in {"live", "degraded", "blocked"} else "blocked"
    payload: dict[str, Any] = {
        "source": source,
        "status": normalized,
        "mode": mode,
        "live_query_executed": bool(live_query_executed),
        "checked_at": datetime.now(timezone.utc).isoformat(),
    }
    if version:
        payload["version"] = version
    if endpoint:
        payload["endpoint"] = endpoint
    if reason:
        payload["reason"] = reason
    if details:
        payload["details"] = details
    return payload


def blocked_evidence_source(source: str, reason: str) -> dict[str, Any]:
    return evidence_source_status(
        source=source,
        status="blocked",
        mode="input_or_runtime_blocked",
        live_query_executed=False,
        reason=reason,
    )
