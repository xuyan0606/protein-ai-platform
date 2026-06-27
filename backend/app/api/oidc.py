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

from authlib.jose import jwt
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import RedirectResponse, JSONResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.core.oidc_config import (
    AUTH_CODE_TTL,
    OIDC_CLIENTS,
    OIDC_ISSUER,
    OIDC_JWKS,
    OIDC_PRIVATE_KEY,
    FRONTEND_URL,
)
from app.core.security import decode_access_token
from app.models.user import User

logger = logging.getLogger(__name__)

router = APIRouter()

# In-memory auth code store. In production with multiple workers, use Redis.
# Format: {code: {"client_id": ..., "user_id": ..., "expires_at": ...}}
_auth_codes: dict[str, dict] = {}


def _cleanup_expired_codes() -> None:
    now = time.time()
    expired = [c for c, v in _auth_codes.items() if v["expires_at"] < now]
    for c in expired:
        del _auth_codes[c]


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
async def openid_configuration():
    """OIDC Discovery — tells Outline where all endpoints live."""
    return {
        "issuer": OIDC_ISSUER,
        "authorization_endpoint": f"{OIDC_ISSUER}/api/oidc/authorize",
        "token_endpoint": f"{OIDC_ISSUER}/api/oidc/token",
        "userinfo_endpoint": f"{OIDC_ISSUER}/api/oidc/userinfo",
        "jwks_uri": f"{OIDC_ISSUER}/api/oidc/jwks",
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

    # Check if user is already authenticated via pa_token cookie
    user_payload = _get_user_from_cookie(request)

    if user_payload is None:
        # Not logged in → redirect to frontend login page
        from urllib.parse import urlencode
        login_params = urlencode({
            "next": str(request.url),
        })
        return RedirectResponse(
            url=f"{FRONTEND_URL}/login?{login_params}",
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
    }

    # Build redirect back to Outline
    from urllib.parse import urlencode
    params = urlencode({"code": code, "state": state})
    sep = "&" if "?" in redirect_uri else "?"
    return RedirectResponse(url=f"{redirect_uri}{sep}{params}")


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

    # Look up user from DB
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if user is None:
        raise HTTPException(status_code=400, detail="User not found")

    now = int(time.time())
    access_token_claims = {
        "iss": OIDC_ISSUER,
        "sub": str(user.id),
        "aud": [client_id],
        "iat": now,
        "exp": now + 3600,
        "scope": "openid profile email",
    }
    access_token = jwt.encode(
        {"alg": "RS256", "kid": "protein-ai-oidc-key"},
        access_token_claims,
        OIDC_PRIVATE_KEY,
    ).decode()

    id_token_claims = {
        "iss": OIDC_ISSUER,
        "sub": str(user.id),
        "aud": [client_id],
        "iat": now,
        "exp": now + 3600,
        "email": user.email,
        "name": user.name,
        "nonce": auth_entry.get("nonce"),
    }
    id_token = jwt.encode(
        {"alg": "RS256", "kid": "protein-ai-oidc-key"},
        id_token_claims,
        OIDC_PRIVATE_KEY,
    ).decode()

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
        claims = jwt.decode(token, OIDC_JWKS["keys"][0])
        claims.validate()
    except Exception:
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


# ---------------------------------------------------------------------------
# JWKS
# ---------------------------------------------------------------------------

@router.get("/api/oidc/jwks")
async def oidc_jwks():
    """JWKS endpoint — publishes the public key for token verification."""
    return OIDC_JWKS