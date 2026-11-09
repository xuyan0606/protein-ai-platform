"""OIDC Provider API — bridges platform JWT auth to Outline's OIDC requirement.

Implements a minimal OIDC 1.0 provider (authorization code flow) so that
Outline can authenticate against our existing user database without
requiring a separate identity provider.

Endpoints:
    /.well-known/openid-configuration   Discovery
    /api/oidc/authorize                 Authorization (login gate)
    /api/oidc/token                     Token exchange
    /api/oidc/userinfo                  User profile
    /api/oidc/jwks                      Signing key publication
"""

from __future__ import annotations

import json
import logging
import secrets
import time
from datetime import datetime, timezone
from urllib.parse import urlencode, urlsplit

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.responses import RedirectResponse, JSONResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.core.jwt_compat import JWTError, decode_jwt, encode_jwt
from app.core.oidc_config import (
    AUTH_CODE_TTL,
    OIDC_CLIENTS,
    OIDC_ISSUER,
    OIDC_JWKS,
    OIDC_PRIVATE_KEY,
    OIDC_PUBLIC_KEY,
    FRONTEND_URL,
)
from app.core.security import decode_access_token
from app.models.user import User

logger = logging.getLogger(__name__)

router = APIRouter()

# In-memory auth code store. In production with multiple workers, use Redis.
# Format: {code: {"client_id": ..., "user_id": ..., "expires_at": ...}}
_auth_codes: dict[str, dict] = {}
_USES_HTTPS = urlsplit(FRONTEND_URL).scheme == "https"
_LOGOUT_COOKIE_NAMES = (
    "pa_token",
    "refresh_token",
    "accessToken",
    "csrfToken",
    "lastSignedIn",
    "oauth_csrf",
    "loggedIn",
    "returnTo",
)


def _first_forwarded_value(value: str | None) -> str | None:
    if not value:
        return None
    first = value.split(",", 1)[0].strip()
    return first or None


def _is_local_origin(origin: str) -> bool:
    host = urlsplit(origin).hostname or ""
    return host in {"", "localhost", "127.0.0.1"}


def _is_internal_origin(origin: str) -> bool:
    host = urlsplit(origin).hostname or ""
    return host in {"", "frontend", "backend", "outline"}


def _request_origin(request: Request) -> str:
    proto = (
        _first_forwarded_value(request.headers.get("x-forwarded-proto"))
        or request.url.scheme
        or "http"
    )
    forwarded_host = _first_forwarded_value(request.headers.get("x-forwarded-host"))
    request_host = request.headers.get("host") or request.url.netloc
    host = forwarded_host or request_host
    forwarded_port = _first_forwarded_value(request.headers.get("x-forwarded-port"))

    # Prefer the raw Host header when it already carries the browser-visible
    # external port (e.g. localhost:4200). This avoids leaking the proxy's
    # internal listener port such as 8080 into OIDC redirects.
    if request_host and ":" in request_host:
        host = request_host

    # Some proxies forward host without the external port (e.g. "localhost")
    # while preserving the port separately in X-Forwarded-Port. Reattach it so
    # OIDC redirect URI validation can distinguish localhost:4200 from :80.
    if host and forwarded_port and ":" not in host:
        is_default_port = (
            (proto == "http" and forwarded_port == "80")
            or (proto == "https" and forwarded_port == "443")
        )
        if not is_default_port:
            host = f"{host}:{forwarded_port}"
    return f"{proto}://{host}".rstrip("/")


def _browser_origin(request: Request) -> str | None:
    origin = _request_origin(request)
    if not origin or _is_internal_origin(origin):
        return None
    return origin


def _public_frontend_origin(request: Request) -> str:
    request_origin = _browser_origin(request)
    if request_origin:
        return request_origin
    configured = FRONTEND_URL.rstrip("/")
    if configured and not _is_local_origin(configured):
        return configured
    return _request_origin(request)


def _public_issuer(request: Request) -> str:
    request_origin = _browser_origin(request)
    if request_origin:
        return request_origin
    configured = OIDC_ISSUER.rstrip("/")
    if configured and not _is_local_origin(configured):
        return configured
    return _request_origin(request)


def _default_outline_redirect_uri(request: Request) -> str:
    return f"{_public_frontend_origin(request)}/wiki/auth/oidc.callback"


def _allowed_redirect_uris(request: Request, client: dict) -> set[str]:
    uris = set(client.get("redirect_uris", []))
    candidate_origins = {
        _request_origin(request),
        _public_frontend_origin(request),
        _public_issuer(request),
        FRONTEND_URL.rstrip("/"),
        OIDC_ISSUER.rstrip("/"),
    }
    for origin in {origin for origin in candidate_origins if origin and not _is_internal_origin(origin)}:
        uris.add(f"{origin}/auth/oidc.callback")
        uris.add(f"{origin}/wiki/auth/oidc.callback")
    return uris


def _cleanup_expired_codes() -> None:
    now = time.time()
    expired = [c for c, v in _auth_codes.items() if v["expires_at"] < now]
    for c in expired:
        del _auth_codes[c]


def _clear_unified_auth_cookies(response: Response) -> None:
    """Clear platform auth cookies and Outline cookies on the shared host."""
    for cookie_name in _LOGOUT_COOKIE_NAMES:
        response.delete_cookie(
            key=cookie_name,
            path="/",
            secure=_USES_HTTPS,
            samesite="lax",
        )


def _get_user_from_cookie(request: Request) -> dict | None:
    """Extract and validate the user from the pa_token cookie."""
    token = request.cookies.get("pa_token")
    if not token:
        return None
    try:
        payload = decode_access_token(token)
        return payload  # {"sub": user_id, "iat": ..., "exp": ..., "type": "access"}
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Discovery
# ---------------------------------------------------------------------------

@router.get("/.well-known/openid-configuration")
async def openid_configuration(request: Request):
    """OIDC Discovery — tells Outline where all endpoints live."""
    issuer = _public_issuer(request)
    return {
        "issuer": issuer,
        "authorization_endpoint": f"{issuer}/api/oidc/authorize",
        "token_endpoint": f"{issuer}/api/oidc/token",
        "userinfo_endpoint": f"{issuer}/api/oidc/userinfo",
        "jwks_uri": f"{issuer}/api/oidc/jwks",
        "response_types_supported": ["code"],
        "grant_types_supported": ["authorization_code", "refresh_token"],
        "subject_types_supported": ["public"],
        "id_token_signing_alg_values_supported": ["RS256"],
        "token_endpoint_auth_methods_supported": ["client_secret_post"],
        "scopes_supported": ["openid", "profile", "email"],
        "claims_supported": ["sub", "email", "name", "iat", "exp"],
    }


# ---------------------------------------------------------------------------
# Authorization
# ---------------------------------------------------------------------------

@router.get("/api/oidc/authorize")
async def oidc_authorize(
    request: Request,
    client_id: str,
    redirect_uri: str,
    response_type: str = "code",
    scope: str = "openid profile email",
    state: str = "",
    nonce: str = "",
    db: AsyncSession = Depends(get_session),
):
    """OIDC Authorization endpoint.

    Flow:
    1. If user has a valid pa_token cookie → auto-approve, redirect back with code
    2. If no valid cookie → redirect to login page with return URL
    """
    # Validate client
    client = OIDC_CLIENTS.get(client_id)
    if not client:
        raise HTTPException(status_code=400, detail=f"Unknown client: {client_id}")

    if response_type != "code":
        raise HTTPException(status_code=400, detail="Only 'code' response_type is supported")

    # Validate redirect_uri against client's registered URIs (OIDC spec §3.1.2.1)
    registered_uris = _allowed_redirect_uris(request, client)
    if registered_uris and redirect_uri not in registered_uris:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid redirect_uri: not registered for this client",
        )

    # Check if user is already authenticated via pa_token cookie
    user_payload = _get_user_from_cookie(request)

    if user_payload is None:
        # Not logged in → redirect to frontend login page
        # SECURITY: use only path+query to prevent Open Redirect via Host header injection.
        # The frontend will resolve this relative URL against its own origin.
        next_url = request.url.path
        if request.url.query:
            next_url += f"?{request.url.query}"
        login_params = urlencode({
            "next": next_url,
        })
        return RedirectResponse(
            url=f"{_public_frontend_origin(request)}/login?{login_params}",
            status_code=status.HTTP_302_FOUND,
        )

    # User is authenticated — generate authorization code
    _cleanup_expired_codes()
    code = secrets.token_urlsafe(32)
    _auth_codes[code] = {
        "client_id": client_id,
        "user_id": int(user_payload["sub"]),
        "redirect_uri": redirect_uri,
        "expires_at": time.time() + AUTH_CODE_TTL,
        "nonce": nonce,
        "issuer": _public_issuer(request),
    }

    # Build redirect back to Outline
    params = urlencode({"code": code, "state": state})
    sep = "&" if "?" in redirect_uri else "?"
    return RedirectResponse(url=f"{redirect_uri}{sep}{params}")


@router.get("/auth/oidc")
async def oidc_authorize_entry(request: Request):
    """Legacy entrypoint: bounce into Outline's own OIDC start route.

    Outline must initiate the OAuth flow itself so it can generate and verify
    the signed `state` payload plus the `oauth_csrf` cookie. Redirecting
    browsers straight to our provider `/api/oidc/authorize` skips that step and
    leads to `state-mismatch` on callback.
    """
    return RedirectResponse(
        url=f"{_public_frontend_origin(request)}/wiki/auth/oidc",
        status_code=status.HTTP_302_FOUND,
    )


# ---------------------------------------------------------------------------
# Token
# ---------------------------------------------------------------------------

@router.post("/api/oidc/token")
async def oidc_token(
    request: Request,
    db: AsyncSession = Depends(get_session),
):
    """Token endpoint — exchanges authorization code for access_token + id_token."""
    form = await request.form()
    grant_type = form.get("grant_type")
    code = form.get("code")
    client_id = form.get("client_id")
    client_secret = form.get("client_secret")
    redirect_uri = form.get("redirect_uri")

    # Validate client credentials
    client = OIDC_CLIENTS.get(client_id or "")
    if not client or client["client_secret"] != client_secret:
        raise HTTPException(status_code=401, detail="Invalid client credentials")

    if grant_type != "authorization_code":
        raise HTTPException(status_code=400, detail="Unsupported grant_type")

    _cleanup_expired_codes()
    auth_entry = _auth_codes.pop(code, None)

    if auth_entry is None:
        raise HTTPException(status_code=400, detail="Invalid or expired authorization code")

    if auth_entry["client_id"] != client_id:
        raise HTTPException(status_code=400, detail="Client ID mismatch")

    user_id = auth_entry["user_id"]
    issuer = auth_entry.get("issuer") or OIDC_ISSUER

    # Look up user from DB
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if user is None:
        raise HTTPException(status_code=400, detail="User not found")

    now = int(time.time())
    access_token_claims = {
        "iss": issuer,
        "sub": str(user.id),
        "aud": [client_id],
        "iat": now,
        "exp": now + 3600,
        "scope": "openid profile email",
    }
    access_token = encode_jwt(
        access_token_claims,
        OIDC_PRIVATE_KEY,
        algorithm="RS256",
        headers={"kid": "protein-ai-oidc-key"},
    )

    id_token_claims = {
        "iss": issuer,
        "sub": str(user.id),
        "aud": [client_id],
        "iat": now,
        "exp": now + 3600,
        "email": user.email,
        "name": user.name,
        "nonce": auth_entry.get("nonce"),
    }
    id_token = encode_jwt(
        id_token_claims,
        OIDC_PRIVATE_KEY,
        algorithm="RS256",
        headers={"kid": "protein-ai-oidc-key"},
    )

    return {
        "access_token": access_token,
        "token_type": "Bearer",
        "id_token": id_token,
        "expires_in": 3600,
    }


# ---------------------------------------------------------------------------
# UserInfo
# ---------------------------------------------------------------------------

@router.get("/api/oidc/userinfo")
@router.post("/api/oidc/userinfo")
async def oidc_userinfo(request: Request, db: AsyncSession = Depends(get_session)):
    """UserInfo endpoint — returns the authenticated user's profile."""
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing Bearer token")

    token = auth_header[7:]
    try:
        claims = decode_jwt(
            token,
            OIDC_PUBLIC_KEY,
            algorithms=["RS256"],
            options={"verify_aud": False},
        )
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid access token")

    user_id = int(claims["sub"])
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if user is None:
        raise HTTPException(status_code=404, detail="User not found")

    return {
        "sub": str(user.id),
        "email": user.email,
        "name": user.name,
        "email_verified": True,
    }


@router.get("/api/oidc/logout")
async def oidc_logout(request: Request):
    """Unified logout entry used by Outline's OIDC integration."""
    response = RedirectResponse(
        url=f"{_public_frontend_origin(request)}/login",
        status_code=status.HTTP_302_FOUND,
    )
    _clear_unified_auth_cookies(response)
    return response


# ---------------------------------------------------------------------------
# JWKS
# ---------------------------------------------------------------------------

@router.get("/api/oidc/jwks")
async def oidc_jwks():
    """JWKS endpoint — publishes the public key for token verification."""
    return OIDC_JWKS
