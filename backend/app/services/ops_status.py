"""Read-only operational summary for the platform."""

from __future__ import annotations

import os
import shutil
import time
from typing import Any
from urllib.parse import urlparse

from app.core.config import PROJECT_ROOT, settings
from app.core.metrics import http_request_snapshot
from app.services.deploy_data_status import collect_deploy_data_readiness
from app.services.ops_notifications import notification_policy
from app.services.scheduler import celery_app, get_task_profile

_STARTED_AT = time.time()


def _disk_usage(path: str) -> dict[str, Any]:
    usage = shutil.disk_usage(path)
    return {
        "path": path,
        "total_bytes": usage.total,
        "used_bytes": usage.used,
        "free_bytes": usage.free,
        "used_percent": round((usage.used / usage.total) * 100, 2) if usage.total else None,
    }


def _check(name: str, status: str, message: str, *, severity: str = "info", details: dict[str, Any] | None = None) -> dict[str, Any]:
    return {
        "name": name,
        "status": status,
        "severity": severity,
        "message": message,
        "details": details or {},
    }


def _redis_queue_snapshot(queue_names: list[str]) -> dict[str, Any]:
    snapshot: dict[str, Any] = {
        "status": "unknown",
        "broker_url": _redact_url(settings.REDIS_URL),
        "queues": {queue: {"length": None} for queue in queue_names},
        "error": None,
    }
    try:
        import redis

        client = redis.Redis.from_url(settings.REDIS_URL, socket_connect_timeout=1, socket_timeout=1)
        client.ping()
        for queue in queue_names:
            snapshot["queues"][queue] = {"length": int(client.llen(queue))}
        snapshot["status"] = "ok"
    except Exception as exc:
        snapshot["status"] = "unavailable"
        snapshot["error"] = str(exc)
    return snapshot


def _celery_worker_snapshot() -> dict[str, Any]:
    snapshot: dict[str, Any] = {
        "status": "unknown",
        "online_workers": 0,
        "active_tasks": 0,
        "active_by_worker": {},
        "registered_worker_count": 0,
        "error": None,
    }
    try:
        inspector = celery_app.control.inspect(timeout=1)
        ping = inspector.ping() or {}
        active = inspector.active() or {}
        registered = inspector.registered() or {}
        snapshot["status"] = "ok" if ping else "unavailable"
        snapshot["online_workers"] = len(ping)
        snapshot["active_by_worker"] = {worker: len(tasks or []) for worker, tasks in active.items()}
        snapshot["active_tasks"] = sum(snapshot["active_by_worker"].values())
        snapshot["registered_worker_count"] = len(registered)
    except Exception as exc:
        snapshot["status"] = "unavailable"
        snapshot["error"] = str(exc)
    return snapshot


def _redact_url(value: str) -> str:
    parsed = urlparse(value)
    if parsed.password:
        netloc = parsed.netloc.replace(f":{parsed.password}@", ":***@")
        return parsed._replace(netloc=netloc).geturl()
    return value


def _build_checks(
    *,
    deploy: dict[str, Any],
    disk: dict[str, Any],
    workers: dict[str, Any],
    endpoints: dict[str, Any],
    runtime: dict[str, Any],
    requests: dict[str, Any],
    task_audits: dict[str, Any],
) -> list[dict[str, Any]]:
    checks: list[dict[str, Any]] = []
    used_percent = disk.get("used_percent")
    if isinstance(used_percent, (int, float)):
        if used_percent >= 90:
            checks.append(_check("disk.project_root", "critical", "Project disk usage is above 90%.", severity="critical", details=disk))
        elif used_percent >= 80:
            checks.append(_check("disk.project_root", "warning", "Project disk usage is above 80%.", severity="warning", details=disk))
        else:
            checks.append(_check("disk.project_root", "ok", "Project disk usage is within the normal range.", details=disk))

    root = deploy.get("root", {})
    if root.get("exists"):
        checks.append(_check("data.deploy_root", "ok", "deploy_data root exists.", details=root))
    else:
        checks.append(_check("data.deploy_root", "critical", "deploy_data root is missing.", severity="critical", details=root))

    if deploy.get("live_ready"):
        checks.append(_check("data.live_readiness", "ok", "Live structure data is ready."))
    elif deploy.get("summary") == "demo-ready":
        checks.append(_check("data.live_readiness", "warning", "Only demo deploy_data is ready; live gate will still fail.", severity="warning", details={"missing_or_demo_components": deploy.get("missing_or_demo_components", [])}))
    else:
        checks.append(_check("data.live_readiness", "warning", "deploy_data is not live-ready.", severity="warning", details={"summary": deploy.get("summary"), "missing_or_demo_components": deploy.get("missing_or_demo_components", [])}))

    md_worker = workers.get("md", {})
    if md_worker.get("queue") == "md_cpu" and md_worker.get("time_limit", 0) >= 3600:
        checks.append(_check("worker.md_profile", "ok", "MD worker profile is isolated on md_cpu."))
    else:
        checks.append(_check("worker.md_profile", "warning", "MD worker profile is not using the expected queue/time limits.", severity="warning", details=md_worker))

    for key, value in endpoints.items():
        if value:
            checks.append(_check(f"endpoint.{key}", "ok", f"{key} is configured."))
        else:
            checks.append(_check(f"endpoint.{key}", "warning", f"{key} is not configured.", severity="warning"))

    redis_status = runtime.get("redis", {}).get("status")
    if redis_status == "ok":
        checks.append(_check("runtime.redis", "ok", "Redis broker is reachable."))
    else:
        checks.append(_check("runtime.redis", "warning", "Redis broker is not reachable from API runtime.", severity="warning", details=runtime.get("redis", {})))

    celery_status = runtime.get("celery", {}).get("status")
    online_workers = int(runtime.get("celery", {}).get("online_workers") or 0)
    if celery_status == "ok" and online_workers > 0:
        checks.append(_check("runtime.celery_workers", "ok", f"{online_workers} Celery worker(s) responded."))
    else:
        checks.append(_check("runtime.celery_workers", "warning", "No Celery workers responded to inspect ping.", severity="warning", details=runtime.get("celery", {})))

    queue_details = runtime.get("redis", {}).get("queues", {})
    for queue_name, detail in queue_details.items():
        length = detail.get("length") if isinstance(detail, dict) else None
        if isinstance(length, int) and length >= 20:
            checks.append(_check(f"queue.{queue_name}", "warning", f"Queue {queue_name} backlog is {length}.", severity="warning", details={"length": length}))
        elif isinstance(length, int):
            checks.append(_check(f"queue.{queue_name}", "ok", f"Queue {queue_name} backlog is {length}.", details={"length": length}))

    slow_count = int(requests.get("slow_count") or 0)
    error_count = int(requests.get("error_count") or 0)
    if slow_count:
        checks.append(_check("http.slow_requests", "warning", f"{slow_count} slow request(s) in recent memory window.", severity="warning", details=requests))
    else:
        checks.append(_check("http.slow_requests", "ok", "No slow requests in recent memory window.", details={"sample_count": requests.get("sample_count", 0)}))
    if error_count:
        checks.append(_check("http.5xx_errors", "warning", f"{error_count} HTTP 5xx response(s) in recent memory window.", severity="warning", details=requests))
    else:
        checks.append(_check("http.5xx_errors", "ok", "No HTTP 5xx responses in recent memory window.", details={"sample_count": requests.get("sample_count", 0)}))

    alerting = task_audits.get("alerting") if isinstance(task_audits.get("alerting"), dict) else {}
    if alerting.get("status") == "triggered":
        checks.append(_check("tasks.failure_trend", "warning", "Task audit alert thresholds are triggered.", severity="warning", details=task_audits))
    else:
        checks.append(_check("tasks.failure_trend", "ok", "Task audit alert thresholds are not triggered.", details={"total": task_audits.get("total", 0)}))

    return checks


def _external_notification_status() -> dict[str, Any]:
    url = settings.OPS_ALERT_WEBHOOK_URL.strip()
    enabled = bool(settings.OPS_ALERT_WEBHOOK_ENABLED)
    configured = bool(url)
    parsed = urlparse(url) if url else None
    return {
        "enabled": enabled,
        "configured": configured,
        "kind": settings.OPS_ALERT_WEBHOOK_KIND,
        "delivery": "enabled" if enabled and configured else "disabled",
        "target": _redact_url(url) if url else "",
        "valid_url_shape": bool(parsed and parsed.scheme in {"http", "https"} and parsed.netloc) if parsed else False,
        "mode": "status_only",
    }


def _task_audit_ops_summary(task_audit_summary: dict[str, Any] | None) -> dict[str, Any]:
    if not task_audit_summary:
        return {
            "total": 0,
            "failure_counts": {},
            "failure_trend": [],
            "slow_count": 0,
            "alerting": {"status": "ok", "mode": "summary_only", "external_delivery": "not_configured"},
        }
    return {
        "total": task_audit_summary.get("total", 0),
        "failure_counts": task_audit_summary.get("failure_counts", {}),
        "failure_trend": task_audit_summary.get("failure_trend", []),
        "slow_count": task_audit_summary.get("slow_count", 0),
        "alerting": task_audit_summary.get("alerting", {}),
    }


def collect_ops_summary(task_audit_summary: dict[str, Any] | None = None) -> dict[str, Any]:
    """Return a compact status payload for future monitoring dashboards."""
    deploy = collect_deploy_data_readiness()
    md_profile = get_task_profile("gromacs_md")
    ligand_profile = get_task_profile("ligand_preprocess")
    default_profile = get_task_profile("esmfold_folding")
    disk = _disk_usage(str(PROJECT_ROOT))
    workers = {
        "default": {
            "queue": default_profile.queue,
            "soft_time_limit": default_profile.soft_time_limit,
            "time_limit": default_profile.time_limit,
        },
        "md": {
            "queue": md_profile.queue,
            "soft_time_limit": md_profile.soft_time_limit,
            "time_limit": md_profile.time_limit,
        },
        "ligand": {
            "queue": ligand_profile.queue,
            "soft_time_limit": ligand_profile.soft_time_limit,
            "time_limit": ligand_profile.time_limit,
        },
    }
    external_endpoints = {
        "redis_host": settings.REDIS_HOST,
        "postgres_host": settings.POSTGRES_HOST,
        "object_storage_endpoint": settings.MINIO_ENDPOINT,
        "chroma_host": settings.CHROMA_HOST,
    }
    queue_names = sorted({profile["queue"] for profile in workers.values()})
    runtime = {
        "redis": _redis_queue_snapshot(queue_names),
        "celery": _celery_worker_snapshot(),
    }
    requests = http_request_snapshot()
    task_audits = _task_audit_ops_summary(task_audit_summary)
    notification = _external_notification_status()
    checks = _build_checks(
        deploy=deploy,
        disk=disk,
        workers=workers,
        endpoints=external_endpoints,
        runtime=runtime,
        requests=requests,
        task_audits=task_audits,
    )
    if notification["enabled"] and not notification["valid_url_shape"]:
        checks.append(_check("notifications.webhook", "warning", "External notification is enabled but webhook URL is invalid.", severity="warning", details=notification))
    elif notification["enabled"]:
        checks.append(_check("notifications.webhook", "ok", "External notification webhook is configured.", details=notification))
    else:
        checks.append(_check("notifications.webhook", "ok", "External notification delivery is disabled.", details=notification))
    alerts = [check for check in checks if check["status"] != "ok"]
    notification["policy"] = notification_policy(alerts, notification)
    status = "ok" if not alerts else ("critical" if any(alert["severity"] == "critical" for alert in alerts) else "degraded")
    return {
        "status": status,
        "uptime_seconds": int(time.time() - _STARTED_AT),
        "process": {
            "pid": os.getpid(),
            "cwd": os.getcwd(),
        },
        "storage": {
            "project_root": str(PROJECT_ROOT),
            "deploy_data": deploy["root"],
            "disk": disk,
        },
        "data": {
            "summary": deploy["summary"],
            "live_ready": deploy["live_ready"],
            "missing_or_demo_components": deploy["missing_or_demo_components"],
        },
        "workers": workers,
        "runtime": runtime,
        "requests": requests,
        "task_audits": task_audits,
        "notifications": notification,
        "external_endpoints": external_endpoints,
        "monitoring": {
            "checks": checks,
            "alerts": alerts,
            "alert_count": len(alerts),
        },
    }
