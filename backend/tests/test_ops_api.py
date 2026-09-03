"""Regression tests for operational summary API."""

from datetime import datetime, timedelta, timezone

import pytest

from app.api import ops as ops_api
from app.core.config import settings
from app.core.security import create_access_token
from app.models.tool_call import ToolTaskAudit
from app.models.user import User
from app.services.ops_notifications import DeliveryAttempt, _DELIVERY_STATE


@pytest.fixture(autouse=True)
def reset_ops_summary_cache():
    ops_api._ops_summary_cache = None
    yield
    ops_api._ops_summary_cache = None


async def _create_user(session, email: str, role: str = "user") -> User:
    user = User(
        email=email,
        hashed_password=User.hash_password("password123"),
        name="Ops User",
        role=role,
    )
    session.add(user)
    await session.flush()
    return user


async def test_ops_summary_requires_auth(client):
    response = await client.get("/api/ops/summary")

    assert response.status_code == 401


async def test_health_endpoint_returns_user_visible_runtime_status(client):
    response = await client.get("/api/health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["service"] == "protein-ai-platform"
    assert isinstance(body["tools_registered"], int)
    assert body["message"]


async def test_ops_summary_returns_read_only_runtime_snapshot(client, session):
    user = await _create_user(session, "ops-summary@example.com")
    session.add(
        ToolTaskAudit(
            task_id="ops-failed-task-id",
            user_id=user.id,
            tool_name="gromacs_md",
            status="failed",
            queue="md_cpu",
            error="GROMACS timeout",
            submitted_at=datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(minutes=45),
            terminal_recorded_at=datetime.now(timezone.utc).replace(tzinfo=None),
        )
    )
    await session.commit()
    client.cookies.set("pa_token", create_access_token(user.id))

    await client.get("/api/health")
    response = await client.get("/api/ops/summary")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] in {"ok", "degraded", "critical"}
    assert body["data"]["summary"] in {"live-ready", "demo-ready", "partial", "empty"}
    assert body["workers"]["md"]["queue"] == "md_cpu"
    assert body["workers"]["ligand"]["queue"] == "ligand_cpu"
    assert body["workers"]["default"]["queue"] == "default"
    assert "disk" in body["storage"]
    assert "monitoring" in body
    assert "runtime" in body
    assert "requests" in body
    assert "task_audits" in body
    assert "notifications" in body
    assert "redis" in body["runtime"]
    assert "celery" in body["runtime"]
    assert body["requests"]["sample_count"] >= 1
    assert body["task_audits"]["failure_counts"]["timeout"] >= 1
    assert body["notifications"]["delivery"] in {"disabled", "enabled"}
    assert isinstance(body["monitoring"]["checks"], list)
    assert isinstance(body["monitoring"]["alerts"], list)
    assert any(check["name"] == "worker.md_profile" for check in body["monitoring"]["checks"])
    assert any(check["name"] == "runtime.redis" for check in body["monitoring"]["checks"])
    assert any(check["name"] == "runtime.celery_workers" for check in body["monitoring"]["checks"])
    assert any(check["name"] == "http.slow_requests" for check in body["monitoring"]["checks"])
    assert any(check["name"] == "tasks.failure_trend" for check in body["monitoring"]["checks"])
    assert any(check["name"] == "notifications.webhook" for check in body["monitoring"]["checks"])
    assert body["notifications"]["policy"]["mode"] == "controlled_dispatch"

    cached_response = await client.get("/api/ops/summary")
    assert cached_response.status_code == 200
    assert cached_response.json()["cached"] is True


async def test_ops_alert_dispatch_requires_admin(client, session):
    user = await _create_user(session, "ops-alert-user@example.com")
    await session.commit()
    client.cookies.set("pa_token", create_access_token(user.id))

    response = await client.post("/api/ops/alerts/dispatch")

    assert response.status_code == 403


async def test_ops_alert_dispatch_defaults_to_dry_run(client, session):
    _DELIVERY_STATE.clear()
    admin = await _create_user(session, "ops-alert-admin-dry-run@example.com", role="admin")
    await session.commit()
    client.cookies.set("pa_token", create_access_token(admin.id))

    response = await client.post("/api/ops/alerts/dispatch")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "planned"
    assert body["dry_run"] is True
    assert body["policy"]["mode"] == "controlled_dispatch"


async def test_ops_alert_dispatch_sends_and_silences_repeated_alerts(client, session, monkeypatch):
    _DELIVERY_STATE.clear()
    admin = await _create_user(session, "ops-alert-admin-send@example.com", role="admin")
    for index in range(3):
        session.add(
            ToolTaskAudit(
                task_id=f"ops-send-failed-task-{index}",
                user_id=admin.id,
                tool_name="gromacs_md",
                status="failed",
                queue="md_cpu",
                error="GROMACS timeout",
                submitted_at=datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(minutes=45 + index),
                terminal_recorded_at=datetime.now(timezone.utc).replace(tzinfo=None),
            )
        )
    await session.commit()
    client.cookies.set("pa_token", create_access_token(admin.id))

    calls = []

    def fake_post_json(url, payload, timeout):
        calls.append({"url": url, "payload": payload, "timeout": timeout})
        return DeliveryAttempt(status_code=200, ok=True)

    monkeypatch.setattr(settings, "OPS_ALERT_WEBHOOK_ENABLED", True)
    monkeypatch.setattr(settings, "OPS_ALERT_WEBHOOK_URL", "http://alerts.example.local/webhook")
    monkeypatch.setattr(settings, "OPS_ALERT_WEBHOOK_RETRY_ATTEMPTS", 2)
    monkeypatch.setattr(settings, "OPS_ALERT_WEBHOOK_TIMEOUT_SECONDS", 0.1)
    monkeypatch.setattr("app.services.ops_notifications._post_json", fake_post_json)

    sent = await client.post("/api/ops/alerts/dispatch?dry_run=false")
    repeated = await client.post("/api/ops/alerts/dispatch?dry_run=false")

    assert sent.status_code == 200
    assert repeated.status_code == 200
    sent_body = sent.json()
    repeated_body = repeated.json()
    assert sent_body["status"] == "sent"
    assert sent_body["attempts"][0]["ok"] is True
    assert calls and calls[0]["payload"]["alert_count"] >= 1
    assert repeated_body["status"] == "skipped"
    assert repeated_body["reason"] == "silenced"
