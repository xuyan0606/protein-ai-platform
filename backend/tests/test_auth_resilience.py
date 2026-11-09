"""Regression tests for auth fallback and logout cleanup."""

from unittest.mock import AsyncMock

from starlette.responses import PlainTextResponse

from app.core.security import create_access_token, create_refresh_token
from app.models.conversation import Conversation
from app.models.user import User


async def _create_user(session, email: str = "user@example.com") -> User:
    user = User(
        email=email,
        hashed_password=User.hash_password("password123"),
        name="Test User",
    )
    session.add(user)
    await session.flush()
    return user


async def test_authenticated_profile_includes_default_role(client, session):
    user = await _create_user(session, email="role-default@example.com")
    await session.commit()
    client.cookies.set("pa_token", create_access_token(user.id))

    response = await client.get("/api/auth/me")

    assert response.status_code == 200
    body = response.json()
    assert body["role"] == "researcher"


async def test_admin_ping_requires_admin_role(client, session):
    user = await _create_user(session, email="role-researcher@example.com")
    await session.commit()
    client.cookies.set("pa_token", create_access_token(user.id))

    response = await client.get("/api/auth/admin/ping")

    assert response.status_code == 403
    assert response.json()["detail"] == "Administrator privileges required"


async def test_admin_ping_allows_admin_role(client, session):
    user = await _create_user(session, email="role-admin@example.com")
    user.role = "admin"
    await session.commit()
    client.cookies.set("pa_token", create_access_token(user.id))

    response = await client.get("/api/auth/admin/ping")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["user"]["role"] == "admin"


async def test_admin_users_requires_admin_role(client, session):
    user = await _create_user(session, email="users-researcher@example.com")
    await session.commit()
    client.cookies.set("pa_token", create_access_token(user.id))

    response = await client.get("/api/auth/admin/users")

    assert response.status_code == 403
    assert response.json()["detail"] == "Administrator privileges required"


async def test_admin_users_lists_users(client, session):
    researcher = await _create_user(session, email="users-list-researcher@example.com")
    admin = await _create_user(session, email="users-list-admin@example.com")
    admin.role = "admin"
    await session.commit()
    client.cookies.set("pa_token", create_access_token(admin.id))

    response = await client.get("/api/auth/admin/users")

    assert response.status_code == 200
    body = response.json()
    assert body["count"] >= 2
    users_by_email = {item["email"]: item for item in body["users"]}
    assert users_by_email[researcher.email]["role"] == "researcher"
    assert users_by_email[admin.email]["role"] == "admin"


async def test_admin_can_update_other_user_role(client, session):
    researcher = await _create_user(session, email="users-role-researcher@example.com")
    admin = await _create_user(session, email="users-role-admin@example.com")
    admin.role = "admin"
    await session.commit()
    client.cookies.set("pa_token", create_access_token(admin.id))

    response = await client.patch(
        f"/api/auth/admin/users/{researcher.id}/role",
        json={"role": "admin"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["id"] == researcher.id
    assert body["role"] == "admin"


async def test_admin_can_disable_user_and_disabled_user_is_rejected(client, session):
    researcher = await _create_user(session, email="users-disable-researcher@example.com")
    admin = await _create_user(session, email="users-disable-admin@example.com")
    admin.role = "admin"
    await session.commit()
    client.cookies.set("pa_token", create_access_token(admin.id))

    update_response = await client.patch(
        f"/api/auth/admin/users/{researcher.id}/status",
        json={"is_active": False, "disabled_reason": "left company"},
    )
    client.cookies.clear()
    login_response = await client.post(
        "/api/auth/login",
        json={"email": researcher.email, "password": "password123"},
    )
    client.cookies.set("pa_token", create_access_token(researcher.id))
    me_response = await client.get("/api/auth/me")

    assert update_response.status_code == 200
    assert update_response.json()["is_active"] is False
    assert update_response.json()["disabled_reason"] == "left company"
    assert login_response.status_code == 403
    assert login_response.json()["detail"] == "User account is disabled"
    assert me_response.status_code == 403
    assert me_response.json()["detail"] == "User account is disabled"


async def test_admin_can_lock_user_and_refresh_is_rejected(client, session):
    researcher = await _create_user(session, email="users-lock-researcher@example.com")
    admin = await _create_user(session, email="users-lock-admin@example.com")
    admin.role = "admin"
    await session.commit()
    client.cookies.set("pa_token", create_access_token(admin.id))

    update_response = await client.patch(
        f"/api/auth/admin/users/{researcher.id}/status",
        json={"locked": True},
    )
    client.cookies.clear()
    client.cookies.set("refresh_token", create_refresh_token(researcher.id))
    refresh_response = await client.post("/api/auth/refresh", json={"refresh_token": None})

    assert update_response.status_code == 200
    assert update_response.json()["locked_at"]
    assert refresh_response.status_code == 403
    assert refresh_response.json()["detail"] == "User account is locked"


async def test_admin_cannot_disable_or_lock_self(client, session):
    admin = await _create_user(session, email="users-self-status-admin@example.com")
    admin.role = "admin"
    await session.commit()
    client.cookies.set("pa_token", create_access_token(admin.id))

    disable_response = await client.patch(
        f"/api/auth/admin/users/{admin.id}/status",
        json={"is_active": False},
    )
    lock_response = await client.patch(
        f"/api/auth/admin/users/{admin.id}/status",
        json={"locked": True},
    )

    assert disable_response.status_code == 400
    assert disable_response.json()["detail"] == "Administrators cannot disable their own account"
    assert lock_response.status_code == 400
    assert lock_response.json()["detail"] == "Administrators cannot lock their own account"


async def test_admin_cannot_demote_self(client, session):
    admin = await _create_user(session, email="users-self-demote-admin@example.com")
    admin.role = "admin"
    await session.commit()
    client.cookies.set("pa_token", create_access_token(admin.id))

    response = await client.patch(
        f"/api/auth/admin/users/{admin.id}/role",
        json={"role": "researcher"},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Administrators cannot demote their own account"


async def test_me_accepts_refresh_cookie_when_bearer_is_invalid(client, session):
    user = await _create_user(session)
    await session.commit()

    refresh_token = create_refresh_token(user.id)
    client.cookies.set("refresh_token", refresh_token)

    response = await client.get(
        "/api/auth/me",
        headers={"Authorization": "Bearer invalid-token"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["id"] == user.id
    assert body["email"] == user.email


async def test_conversations_accept_refresh_cookie_when_bearer_is_invalid(client, session):
    user = await _create_user(session, email="conv@example.com")
    conversation = Conversation(user_id=user.id, title="Recovered Session")
    session.add(conversation)
    await session.commit()

    refresh_token = create_refresh_token(user.id)
    client.cookies.set("refresh_token", refresh_token)

    response = await client.get(
        "/api/conversations",
        headers={"Authorization": "Bearer invalid-token"},
    )

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["title"] == "Recovered Session"


async def test_logout_clears_auth_cookies(client, session):
    user = await _create_user(session, email="logout@example.com")
    await session.commit()

    access_token = create_access_token(user.id)
    refresh_token = create_refresh_token(user.id)

    client.cookies.set("pa_token", access_token)
    client.cookies.set("refresh_token", refresh_token)

    response = await client.post("/api/auth/logout")

    assert response.status_code == 204
    set_cookie_headers = response.headers.get_list("set-cookie")
    assert any("pa_token=" in header and "Max-Age=0" in header for header in set_cookie_headers)
    assert any("refresh_token=" in header and "Max-Age=0" in header for header in set_cookie_headers)


async def test_refresh_accepts_cookie_when_body_token_missing(client, session):
    user = await _create_user(session, email="refresh-cookie@example.com")
    await session.commit()

    refresh_token = create_refresh_token(user.id)
    client.cookies.set("refresh_token", refresh_token)

    response = await client.post("/api/auth/refresh", json={"refresh_token": None})

    assert response.status_code == 200
    body = response.json()
    assert body["user"]["id"] == user.id
    assert body["access_token"]
    assert body["refresh_token"]


async def test_session_accepts_pa_token_cookie_without_authorization_header(client, session):
    user = await _create_user(session, email="session-cookie@example.com")
    await session.commit()

    access_token = create_access_token(user.id)
    client.cookies.set("pa_token", access_token)

    response = await client.get("/api/auth/session")

    assert response.status_code == 200
    body = response.json()
    assert body["authenticated"] is True
    assert body["user"]["id"] == user.id


async def test_oidc_discovery_uses_public_origin(client):
    response = await client.get(
        "/.well-known/openid-configuration",
        headers={
            "host": "proteinai.kevibotech.com",
            "x-forwarded-host": "proteinai.kevibotech.com",
            "x-forwarded-proto": "https",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["issuer"] == "https://proteinai.kevibotech.com"
    assert body["authorization_endpoint"] == "https://proteinai.kevibotech.com/api/oidc/authorize"


async def test_oidc_authorize_redirects_to_public_login(client):
    response = await client.get(
        "/api/oidc/authorize",
        params={
            "client_id": "protein-ai",
            "redirect_uri": "https://proteinai.kevibotech.com/auth/oidc.callback",
            "response_type": "code",
        },
        headers={
            "host": "proteinai.kevibotech.com",
            "x-forwarded-host": "proteinai.kevibotech.com",
            "x-forwarded-proto": "https",
        },
        follow_redirects=False,
    )

    assert response.status_code == 302
    assert response.headers["location"].startswith(
        "https://proteinai.kevibotech.com/login?next=%2Fapi%2Foidc%2Fauthorize"
    )


async def test_oidc_authorize_accepts_localhost_redirect_uri(client):
    response = await client.get(
        "/api/oidc/authorize",
        params={
            "client_id": "protein-ai",
            "redirect_uri": "http://localhost:4200/wiki/auth/oidc.callback",
            "response_type": "code",
        },
        headers={
            "host": "localhost:4200",
            "x-forwarded-host": "localhost:4200",
            "x-forwarded-proto": "http",
        },
        follow_redirects=False,
    )

    assert response.status_code == 302
    assert response.headers["location"].startswith(
        "http://localhost:4200/login?next=%2Fapi%2Foidc%2Fauthorize"
    )


async def test_oidc_entry_redirects_to_outline_wiki_start(client):
    response = await client.get(
        "/auth/oidc",
        headers={
            "host": "localhost:4200",
            "x-forwarded-host": "localhost:4200",
            "x-forwarded-proto": "http",
        },
        follow_redirects=False,
    )

    assert response.status_code == 302
    assert response.headers["location"] == "http://localhost:4200/wiki/auth/oidc"


async def test_wiki_bootstraps_outline_session_from_platform_cookie(client, session):
    user = await _create_user(session, email="wiki-bootstrap@example.com")
    await session.commit()

    client.cookies.set("pa_token", create_access_token(user.id))

    response = await client.get(
        "/wiki/home",
        headers={
            "accept": "text/html",
            "host": "proteinai.kevibotech.com",
            "x-forwarded-host": "proteinai.kevibotech.com",
            "x-forwarded-proto": "https",
        },
        follow_redirects=False,
    )

    assert response.status_code == 302
    assert response.headers["location"] == "/wiki/auth/oidc"


async def test_wiki_oidc_start_bypasses_bootstrap_redirect(client, session, monkeypatch):
    from app.api import outline_proxy

    user = await _create_user(session, email="wiki-start@example.com")
    await session.commit()

    client.cookies.set("pa_token", create_access_token(user.id))

    proxy_mock = AsyncMock(return_value=PlainTextResponse("ok"))

    async def fake_proxy(request, path=""):
        return await proxy_mock(request, path)

    monkeypatch.setattr(outline_proxy, "_proxy", fake_proxy)

    response = await client.get(
        "/wiki/auth/oidc",
        headers={
            "accept": "text/html",
            "host": "proteinai.kevibotech.com",
            "x-forwarded-host": "proteinai.kevibotech.com",
            "x-forwarded-proto": "https",
        },
        follow_redirects=False,
    )

    assert response.status_code == 200
    assert response.text == "ok"
    proxy_mock.assert_awaited_once()


async def test_wiki_oidc_callback_bypasses_bootstrap_redirect(client, session, monkeypatch):
    from app.api import outline_proxy

    user = await _create_user(session, email="wiki-callback@example.com")
    await session.commit()

    client.cookies.set("pa_token", create_access_token(user.id))

    proxy_mock = AsyncMock(return_value=PlainTextResponse("ok"))

    async def fake_proxy(request, path=""):
        return await proxy_mock(request, path)

    monkeypatch.setattr(outline_proxy, "_proxy", fake_proxy)

    response = await client.get(
        "/wiki/auth/oidc.callback?code=test-code",
        headers={
            "accept": "text/html",
            "host": "proteinai.kevibotech.com",
            "x-forwarded-host": "proteinai.kevibotech.com",
            "x-forwarded-proto": "https",
        },
        follow_redirects=False,
    )

    assert response.status_code == 200
    assert response.text == "ok"
    proxy_mock.assert_awaited_once()


async def test_oidc_token_userinfo_and_jwks_round_trip(client, session):
    from app.api import oidc as oidc_api

    user = await _create_user(session, email="oidc-token@example.com")
    await session.commit()

    code = "test-auth-code"
    oidc_api._auth_codes[code] = {
        "client_id": "protein-ai",
        "user_id": user.id,
        "expires_at": 4102444800,
        "nonce": "nonce-123",
        "issuer": "http://localhost:4200",
    }

    token_response = await client.post(
        "/api/oidc/token",
        data={
            "grant_type": "authorization_code",
            "code": code,
            "client_id": "protein-ai",
            "client_secret": "oidc-secret-change-me-in-production",
            "redirect_uri": "http://localhost:4200/wiki/auth/oidc.callback",
        },
    )

    assert token_response.status_code == 200
    tokens = token_response.json()
    assert tokens["token_type"] == "Bearer"
    assert tokens["access_token"]
    assert tokens["id_token"]

    userinfo_response = await client.get(
        "/api/oidc/userinfo",
        headers={"Authorization": f"Bearer {tokens['access_token']}"},
    )

    assert userinfo_response.status_code == 200
    userinfo = userinfo_response.json()
    assert userinfo["sub"] == str(user.id)
    assert userinfo["email"] == user.email
    assert userinfo["name"] == user.name

    jwks_response = await client.get("/api/oidc/jwks")

    assert jwks_response.status_code == 200
    jwks = jwks_response.json()
    assert jwks["keys"][0]["kid"] == "protein-ai-oidc-key"
    assert jwks["keys"][0]["kty"] == "RSA"
    assert "n" in jwks["keys"][0]
    assert "e" in jwks["keys"][0]
