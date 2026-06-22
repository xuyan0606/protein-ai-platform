"""Prometheus metrics for the Protein AI Platform.

Exposes request latency, active SSE connections, tool call counts,
and error rates at /api/metrics (scraped by Prometheus).
"""

from __future__ import annotations

import time
from typing import Awaitable, Callable

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


class MetricsMiddleware(BaseHTTPMiddleware):
    """Track every HTTP request with method/endpoint/status and latency."""

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        start = time.monotonic()
        response = await call_next(request)
        duration = time.monotonic() - start

        endpoint = request.url.path
        if endpoint.startswith("/api/"):
            # Group dynamic path segments like /api/conversations/42 → /api/conversations/{id}
            parts = endpoint.split("/")
            grouped = "/".join(
                p if not p.isdigit() and len(p) < 36 else "{param}" for p in parts
            )
        else:
            grouped = endpoint

        http_requests_total.labels(
            method=request.method, endpoint=grouped, status=str(response.status_code)
        ).inc()
        http_request_duration_seconds.labels(
            method=request.method, endpoint=grouped
        ).observe(duration)

        return response


def metrics_response() -> Response:
    """Generate Prometheus text format response."""
    return Response(
        content=generate_latest(),
        media_type="text/plain; version=0.0.4; charset=utf-8",
    )
