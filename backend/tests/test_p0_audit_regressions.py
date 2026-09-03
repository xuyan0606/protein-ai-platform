"""P0 audit regression tests for auth, files, chat/SSE, OIDC, and async tasks."""

import pytest
from httpx import ASGITransport, AsyncClient

from app.api.chat import SSE_HEARTBEAT_FRAME, _iter_with_sse_heartbeat
from app.api.projects import ProjectCreate
from app.core.database import get_session
from app.core.rate_limiter import _window
from app.core.security import create_access_token
from app.main import app
from app.models.user import User


@pytest.fixture(autouse=True)
def clear_rate_limit_window():
    _window._hits.clear()
    yield
    _window._hits.clear()


async def _create_user(session, email: str = "p0@example.com") -> User:
    user = User(
        email=email,
        hashed_password=User.hash_password("password123"),
        name="P0 User",
    )
    session.add(user)
    await session.flush()
    return user


async def test_auth_register_rejects_invalid_email_and_long_name(client):
    bad_email = await client.post(
        "/api/auth/register",
        json={"email": "notanemail", "password": "password123", "name": "Bad Email"},
    )
    long_name = await client.post(
        "/api/auth/register",
        json={"email": "long-name@example.com", "password": "password123", "name": "x" * 201},
    )

    assert bad_email.status_code == 422
    assert long_name.status_code == 422


async def test_auth_login_rate_limit_is_enforced(client):
    responses = [
        await client.post(
            "/api/auth/login",
            json={"email": "missing@example.com", "password": "wrong-password"},
        )
        for _ in range(11)
    ]

    assert [response.status_code for response in responses[:10]] == [401] * 10
    assert responses[10].status_code == 429
    assert responses[10].headers["retry-after"] == "60"


async def test_auth_refresh_does_not_mask_internal_decode_errors(session, monkeypatch):
    async def override_get_session():
        yield session

    app.dependency_overrides[get_session] = override_get_session
    monkeypatch.setattr("app.api.auth.decode_refresh_token", lambda token: (_ for _ in ()).throw(RuntimeError("decode backend down")))
    try:
        transport = ASGITransport(app=app, raise_app_exceptions=False)
        async with AsyncClient(transport=transport, base_url="http://test") as isolated_client:
            response = await isolated_client.post("/api/auth/refresh", json={"refresh_token": "opaque-token"})
    finally:
        app.dependency_overrides.pop(get_session, None)

    assert response.status_code == 500


def test_project_name_rejects_empty_and_script_payloads():
    with pytest.raises(ValueError):
        ProjectCreate(name="")
    with pytest.raises(ValueError):
        ProjectCreate(name="   ")
    with pytest.raises(ValueError):
        ProjectCreate(name="<script>alert(1)</script>")


async def test_files_upload_rejects_unsupported_extension(client, session):
    user = await _create_user(session, email="p0-file@example.com")
    await session.commit()
    client.cookies.set("pa_token", create_access_token(user.id))

    response = await client.post(
        "/api/files/upload",
        files={"file": ("payload.sh", b"echo bad", "text/x-shellscript")},
    )

    assert response.status_code == 400
    assert "Unsupported file type" in response.json()["detail"]


async def test_files_download_requires_current_user_prefix(client, session):
    user = await _create_user(session, email="p0-file-download@example.com")
    await session.commit()
    client.cookies.set("pa_token", create_access_token(user.id))

    response = await client.get("/api/files/uploads/user_999/private.pdb/download")

    assert response.status_code == 403


async def test_chat_models_requires_auth_and_allows_authenticated_user(client, session):
    anonymous = await client.get("/api/chat/models")
    assert anonymous.status_code == 401

    user = await _create_user(session, email="p0-chat-models@example.com")
    await session.commit()
    client.cookies.set("pa_token", create_access_token(user.id))

    authenticated = await client.get("/api/chat/models")
    assert authenticated.status_code == 200
    assert isinstance(authenticated.json(), list)


async def test_tools_list_requires_auth_and_allows_authenticated_user(client, session):
    anonymous = await client.get("/api/tools")
    anonymous_detail = await client.get("/api/tools/gromacs_md")
    assert anonymous.status_code == 401
    assert anonymous_detail.status_code == 401

    user = await _create_user(session, email="p0-tools-list@example.com")
    await session.commit()
    client.cookies.set("pa_token", create_access_token(user.id))

    authenticated = await client.get("/api/tools")
    assert authenticated.status_code == 200
    assert "tools" in authenticated.json()


async def test_sse_heartbeat_is_emitted_while_upstream_is_silent():
    async def slow_events():
        yield "first"
        await asyncio_sleep(0.03)
        yield "second"

    import asyncio

    async def asyncio_sleep(seconds: float) -> None:
        await asyncio.sleep(seconds)

    stream = _iter_with_sse_heartbeat(slow_events(), interval=0.01)
    first = await stream.__anext__()
    heartbeat = await stream.__anext__()
    second_or_heartbeat = await stream.__anext__()
    await stream.aclose()

    assert first == "first"
    assert heartbeat == SSE_HEARTBEAT_FRAME
    assert second_or_heartbeat in {SSE_HEARTBEAT_FRAME, "second"}


async def test_oidc_rejects_unregistered_redirect_and_userinfo_without_bearer(client):
    redirect = await client.get(
        "/api/oidc/authorize",
        params={
            "client_id": "protein-ai",
            "redirect_uri": "https://evil.example.com/auth/oidc.callback",
            "response_type": "code",
        },
    )
    userinfo = await client.get("/api/oidc/userinfo")

    assert redirect.status_code == 400
    assert "Invalid redirect_uri" in redirect.json()["detail"]
    assert userinfo.status_code == 401


async def test_async_task_status_and_cancel_require_owner(client, session):
    from app.services.tool_task_store import record_tool_task_owner

    owner = await _create_user(session, email="p0-task-owner@example.com")
    intruder = await _create_user(session, email="p0-task-intruder@example.com")
    await session.commit()
    await record_tool_task_owner("p0-owned-task", owner.id, "gromacs_md")
    client.cookies.set("pa_token", create_access_token(intruder.id))

    status_response = await client.get("/api/tools/tasks/p0-owned-task")
    cancel_response = await client.post("/api/tools/tasks/p0-owned-task/cancel")

    assert status_response.status_code == 403
    assert cancel_response.status_code == 403
