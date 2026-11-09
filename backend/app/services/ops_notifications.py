"""Controlled external notification delivery for operational alerts."""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass
from typing import Any
from urllib import request
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse

from app.core.config import settings


_DELIVERY_STATE: dict[str, dict[str, Any]] = {}


@dataclass
class DeliveryAttempt:
    status_code: int | None
    ok: bool
    error: str | None = None


def notification_policy(alerts: list[dict[str, Any]], notification: dict[str, Any]) -> dict[str, Any]:
    """Return delivery policy metadata without sending network requests."""
    url = str(notification.get("target") or settings.OPS_ALERT_WEBHOOK_URL or "").strip()
    parsed = urlparse(url) if url else None
    enabled = bool(notification.get("enabled", settings.OPS_ALERT_WEBHOOK_ENABLED))
    valid_url = bool(parsed and parsed.scheme in {"http", "https"} and parsed.netloc)
    fingerprint = alert_fingerprint(alerts) if alerts else ""
    state = _DELIVERY_STATE.get(fingerprint, {}) if fingerprint else {}
    now = time.time()
    last_sent_at = state.get("last_sent_at")
    muted_until = float(last_sent_at or 0) + settings.OPS_ALERT_SILENCE_SECONDS if last_sent_at else 0
    silenced = bool(muted_until and muted_until > now)

    if not alerts:
        delivery_status = "no_alerts"
    elif not enabled:
        delivery_status = "disabled"
    elif not url:
        delivery_status = "not_configured"
    elif not valid_url:
        delivery_status = "invalid_url"
    elif silenced:
        delivery_status = "silenced"
    else:
        delivery_status = "ready"

    return {
        "mode": "controlled_dispatch",
        "enabled": enabled,
        "configured": bool(url),
        "valid_url_shape": valid_url,
        "delivery_status": delivery_status,
        "silence_seconds": settings.OPS_ALERT_SILENCE_SECONDS,
        "retry_attempts": settings.OPS_ALERT_WEBHOOK_RETRY_ATTEMPTS,
        "timeout_seconds": settings.OPS_ALERT_WEBHOOK_TIMEOUT_SECONDS,
        "escalate_after_count": settings.OPS_ALERT_ESCALATE_AFTER_COUNT,
        "fingerprint": fingerprint,
        "last_sent_at": last_sent_at,
        "muted_until": int(muted_until) if muted_until else None,
        "consecutive_failures": int(state.get("consecutive_failures") or 0),
    }


def alert_fingerprint(alerts: list[dict[str, Any]]) -> str:
    compact = [
        {
            "name": alert.get("name"),
            "status": alert.get("status"),
            "severity": alert.get("severity"),
        }
        for alert in sorted(alerts, key=lambda item: str(item.get("name") or ""))
    ]
    payload = json.dumps(compact, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def _payload(alerts: list[dict[str, Any]], *, summary_status: str, fingerprint: str) -> dict[str, Any]:
    severity_rank = {"info": 0, "warning": 1, "critical": 2}
    max_severity = max((str(alert.get("severity") or "info") for alert in alerts), key=lambda item: severity_rank.get(item, 0), default="info")
    state = _DELIVERY_STATE.get(fingerprint, {})
    consecutive_failures = int(state.get("consecutive_failures") or 0)
    escalated = max_severity == "critical" or consecutive_failures >= max(settings.OPS_ALERT_ESCALATE_AFTER_COUNT - 1, 0)
    return {
        "source": "protein-ai-platform",
        "summary_status": summary_status,
        "severity": max_severity,
        "escalated": escalated,
        "fingerprint": fingerprint,
        "alert_count": len(alerts),
        "alerts": [
            {
                "name": alert.get("name"),
                "status": alert.get("status"),
                "severity": alert.get("severity"),
                "message": alert.get("message"),
            }
            for alert in alerts[:20]
        ],
    }


def _post_json(url: str, payload: dict[str, Any], timeout: float) -> DeliveryAttempt:
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = request.Request(
        url,
        data=body,
        headers={"Content-Type": "application/json", "User-Agent": "protein-ai-platform-ops"},
        method="POST",
    )
    try:
        with request.urlopen(req, timeout=timeout) as response:
            status_code = int(getattr(response, "status", 0) or response.getcode())
            return DeliveryAttempt(status_code=status_code, ok=200 <= status_code < 300)
    except HTTPError as exc:
        return DeliveryAttempt(status_code=exc.code, ok=False, error=str(exc))
    except URLError as exc:
        return DeliveryAttempt(status_code=None, ok=False, error=str(exc.reason))
    except Exception as exc:
        return DeliveryAttempt(status_code=None, ok=False, error=str(exc))


def dispatch_alert_notification(
    alerts: list[dict[str, Any]],
    notification: dict[str, Any],
    *,
    summary_status: str,
    dry_run: bool = True,
    force: bool = False,
) -> dict[str, Any]:
    """Send or preview an operational alert notification."""
    policy = notification_policy(alerts, notification)
    fingerprint = policy["fingerprint"]
    url = str(notification.get("target") or settings.OPS_ALERT_WEBHOOK_URL or "").strip()
    if policy["delivery_status"] == "silenced" and force:
        policy = {**policy, "delivery_status": "ready", "forced": True}

    if dry_run:
        return {
            "status": "planned",
            "dry_run": True,
            "policy": policy,
            "payload": _payload(alerts, summary_status=summary_status, fingerprint=fingerprint) if alerts else {},
        }

    if policy["delivery_status"] != "ready":
        return {
            "status": "skipped",
            "dry_run": False,
            "reason": policy["delivery_status"],
            "policy": policy,
        }

    payload = _payload(alerts, summary_status=summary_status, fingerprint=fingerprint)
    attempts: list[dict[str, Any]] = []
    max_attempts = max(int(settings.OPS_ALERT_WEBHOOK_RETRY_ATTEMPTS or 1), 1)
    timeout = max(float(settings.OPS_ALERT_WEBHOOK_TIMEOUT_SECONDS or 1.0), 0.1)
    for attempt_no in range(1, max_attempts + 1):
        result = _post_json(url, payload, timeout)
        attempts.append({"attempt": attempt_no, "status_code": result.status_code, "ok": result.ok, "error": result.error})
        if result.ok:
            _DELIVERY_STATE[fingerprint] = {
                "last_sent_at": time.time(),
                "consecutive_failures": 0,
                "last_status_code": result.status_code,
            }
            return {
                "status": "sent",
                "dry_run": False,
                "attempts": attempts,
                "policy": policy,
                "payload": payload,
            }

    state = _DELIVERY_STATE.setdefault(fingerprint, {})
    state["consecutive_failures"] = int(state.get("consecutive_failures") or 0) + 1
    state["last_error"] = attempts[-1].get("error") if attempts else "unknown"
    return {
        "status": "failed",
        "dry_run": False,
        "attempts": attempts,
        "policy": {**policy, "consecutive_failures": state["consecutive_failures"]},
        "payload": payload,
    }
