"""OIDC Provider configuration — RSA keys, client registry, Redis-backed auth codes."""

from __future__ import annotations

import os
from pathlib import Path

from authlib.jose import JsonWebKey

# ---------------------------------------------------------------------------
# RSA key pair for signing OIDC tokens (RS256)
# ---------------------------------------------------------------------------
_KEY_DIR = Path(__file__).resolve().parent.parent.parent  # backend/

with open(_KEY_DIR / "oidc_private_key.pem", "rb") as f:
    OIDC_PRIVATE_KEY = f.read()

with open(_KEY_DIR / "oidc_public_key.pem", "rb") as f:
    OIDC_PUBLIC_KEY = f.read()

_jwk = JsonWebKey.import_key(OIDC_PRIVATE_KEY, {"kty": "RSA"})
OIDC_JWK = dict(_jwk)
OIDC_JWK["kid"] = "protein-ai-oidc-key"
OIDC_JWKS = {"keys": [OIDC_JWK]}

# ---------------------------------------------------------------------------
# OIDC client registry (Outline is the only client for now)
# ---------------------------------------------------------------------------
OIDC_CLIENT_SECRET = os.getenv("OIDC_CLIENT_SECRET", "oidc-secret-change-me-in-production")

def _build_redirect_uris() -> list[str]:
    """Build redirect URIs from env or use defaults for dev."""
    uris_env = os.getenv("OIDC_REDIRECT_URIS", "")
    if uris_env:
        return [u.strip() for u in uris_env.split(",") if u.strip()]
    # Defaults: localhost dev + production domain/IP
    uris = [
        "http://localhost:8000/auth/oidc.callback",
        "http://localhost:3002/auth/oidc.callback",
    ]
    prod_url = os.getenv("OIDC_ISSUER", "")
    if prod_url and "localhost" not in prod_url:
        uris.append(f"{prod_url}/auth/oidc.callback")
        # Outline callback on production
        outline_url = os.getenv("OUTLINE_PUBLIC_URL", "")
        if outline_url:
            uris.append(f"{outline_url}/auth/oidc.callback")
    return uris

OIDC_CLIENTS: dict[str, dict] = {
    "protein-ai": {
        "client_id": "protein-ai",
        "client_secret": OIDC_CLIENT_SECRET,
        "redirect_uris": _build_redirect_uris(),
        "response_types": ["code"],
        "grant_types": ["authorization_code", "refresh_token"],
        "token_endpoint_auth_method": "client_secret_post",
    },
}

# ---------------------------------------------------------------------------
# OIDC issuer URL (must match what Outline sees)
# ---------------------------------------------------------------------------
OIDC_ISSUER = os.getenv("OIDC_ISSUER", "http://localhost:8000")

# Frontend URL (for redirecting unauthenticated users to login)
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:3000")

# Authorization code TTL (seconds)
AUTH_CODE_TTL = 300  # 5 minutes