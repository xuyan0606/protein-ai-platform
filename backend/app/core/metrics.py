"""Prometheus metrics for the Protein AI Platform.

Exposes request latency, active SSE connections, tool call counts,
and error rates at /api/metrics (scraped by Prometheus).
"""

from __future__ import annotations

import time
from collections import Counter as PyCounter
from collections import deque
from typing import Awaitable, Callable

from app.core.config import settings
from prometheus_client import Counter, Gauge, Histogram, generate_latest
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response


# ---- Metric definitions ----

http_requests_total = Counter(
    "protein_ai_http_requests_total",
    "Total HTTP requests",
    ["method", "endpoint", "status"],
)

http_request_duration_seconds = Histogram(
    "protein_ai_http_request_duration_seconds",
    "HTTP request latency in seconds",
    ["method", "endpoint"],
    buckets=(0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0),
)

sse_connections_active = Gauge(
    "protein_ai_sse_connections_active",
    "Number of active SSE streaming connections",
)

tool_calls_total = Counter(
    "protein_ai_tool_calls_total",
    "Total tool invocations",
    ["tool_name", "status"],
)

tool_call_duration_seconds = Histogram(
    "protein_ai_tool_call_duration_seconds",
    "Tool execution duration in seconds",
    ["tool_name"],
    buckets=(0.1, 0.5, 1.0, 5.0, 10.0, 30.0, 60.0, 120.0, 300.0, 600.0),
)

celery_tasks_active = Gauge(
    "protein_ai_celery_tasks_active",
    "Active Celery tasks (estimated)",
)

llm_requests_total = Counter(
    "protein_ai_llm_requests_total",
    "Total LLM API calls",
    ["provider", "model", "status"],
)

llm_request_duration_seconds = Histogram(
    "protein_ai_llm_request_duration_seconds",
    "LLM API call latency in seconds",
    ["provider", "model"],
    buckets=(0.1, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0),
)

_RECENT_HTTP_REQUESTS: deque[dict[str, object]] = deque(maxlen=500)


def _group_endpoint(path: str) -> str:
    if path.startswith("/api/"):
        parts = path.split("/")
        return "/".join(p if not p.isdigit() and len(p) < 36 else "{param}" for p in parts)
    return path


def record_http_request(method: str, path: str, status_code: int, duration_seconds: float) -> None:
    endpoint = _group_endpoint(path)
    _RECENT_HTTP_REQUESTS.append(
        {
            "method": method,
            "endpoint": endpoint,
            "status": int(status_code),
            "duration_seconds": round(float(duration_seconds), 4),
            "is_slow": float(duration_seconds) >= settings.OPS_SLOW_REQUEST_THRESHOLD_SECONDS,
            "recorded_at": time.time(),
        }
    )


def http_request_snapshot() -> dict[str, object]:
    requests = list(_RECENT_HTTP_REQUESTS)
    total = len(requests)
    slow = [item for item in requests if item.get("is_slow")]
    errors = [item for item in requests if int(item.get("status") or 0) >= 500]
    statuses = PyCounter(str(item.get("status") or "unknown") for item in requests)
    endpoints = PyCounter(str(item.get("endpoint") or "unknown") for item in requests)
    durations = [float(item.get("duration_seconds") or 0) for item in requests]
    return {
        "window_size": _RECENT_HTTP_REQUESTS.maxlen,
        "sample_count": total,
        "slow_threshold_seconds": settings.OPS_SLOW_REQUEST_THRESHOLD_SECONDS,
        "slow_count": len(slow),
        "error_count": len(errors),
        "status_counts": dict(statuses),
        "top_endpoints": [{"endpoint": endpoint, "count": count} for endpoint, count in endpoints.most_common(8)],
        "duration": {
            "max_seconds": max(durations) if durations else None,
            "mean_seconds": round(sum(durations) / len(durations), 4) if durations else None,
        },
        "recent_slow": slow[-10:],
        "recent_errors": errors[-10:],
    }


class MetricsMiddleware(BaseHTTPMiddleware):
    """Track every HTTP request with method/endpoint/status and latency."""

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        start = time.monotonic()
        response = await call_next(request)
        duration = time.monotonic() - start

        grouped = _group_endpoint(request.url.path)

        http_requests_total.labels(
            method=request.method, endpoint=grouped, status=str(response.status_code)
        ).inc()
        http_request_duration_seconds.labels(
            method=request.method, endpoint=grouped
        ).observe(duration)
        record_http_request(request.method, request.url.path, response.status_code, duration)

        return response


def metrics_response() -> Response:
    """Generate Prometheus text format response."""
    return Response(
        content=generate_latest(),
        media_type="text/plain; version=0.0.4; charset=utf-8",
    )
