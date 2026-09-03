"""OIDC Provider configuration — RSA keys, client registry, Redis-backed auth codes."""

from __future__ import annotations

import base64
import os
from pathlib import Path

from cryptography.hazmat.primitives.serialization import load_pem_public_key

# ---------------------------------------------------------------------------
# RSA key pair for signing OIDC tokens (RS256)
# ---------------------------------------------------------------------------
_KEY_DIR = Path(__file__).resolve().parent.parent.parent  # backend/


def _read_key_file(env_name: str, filename: str) -> bytes:
    candidates: list[Path] = []
    env_path = os.getenv(env_name)
    if env_path:
        candidates.append(Path(env_path))
    candidates.append(Path("/run/secrets") / filename)
    candidates.append(_KEY_DIR / filename)

    for path in candidates:
        if path.exists():
            return path.read_bytes()

    searched = ", ".join(str(path) for path in candidates)
    raise RuntimeError(
        f"Missing OIDC signing key {filename}. Set {env_name} or mount the key "
        f"under /run/secrets. Searched: {searched}"
    )

OIDC_PRIVATE_KEY = _read_key_file("OIDC_PRIVATE_KEY_PATH", "oidc_private_key.pem")
OIDC_PUBLIC_KEY = _read_key_file("OIDC_PUBLIC_KEY_PATH", "oidc_public_key.pem")

def _base64url_uint(value: int) -> str:
    raw = value.to_bytes(max(1, (value.bit_length() + 7) // 8), "big")
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def _build_rsa_public_jwk(public_key_pem: bytes) -> dict[str, str]:
    key = load_pem_public_key(public_key_pem)
    numbers = key.public_numbers()
    return {
        "kty": "RSA",
        "use": "sig",
        "alg": "RS256",
        "n": _base64url_uint(numbers.n),
        "e": _base64url_uint(numbers.e),
    }


OIDC_JWK = _build_rsa_public_jwk(OIDC_PUBLIC_KEY)
OIDC_JWK["kid"] = "protein-ai-oidc-key"
OIDC_JWKS = {"keys": [OIDC_JWK]}

# ---------------------------------------------------------------------------
# OIDC client registry (Outline is the only client for now)
# ---------------------------------------------------------------------------
OIDC_CLIENT_SECRET = os.getenv("OIDC_CLIENT_SECRET", "oidc-secret-change-me-in-production")
PUBLIC_BASE_URL = os.getenv("PUBLIC_BASE_URL", "").rstrip("/")
DEFAULT_FRONTEND_URL = PUBLIC_BASE_URL or os.getenv("FRONTEND_URL", "http://localhost:4200").rstrip("/")
DEFAULT_OIDC_ISSUER = PUBLIC_BASE_URL or os.getenv("OIDC_ISSUER", "http://localhost:8000").rstrip("/")
DEFAULT_OUTLINE_PUBLIC_URL = (
    os.getenv("OUTLINE_PUBLIC_URL", "").rstrip("/") or f"{DEFAULT_FRONTEND_URL}/wiki"
)

def _build_redirect_uris() -> list[str]:
    """Build redirect URIs from env or use defaults for dev."""
    uris_env = os.getenv("OIDC_REDIRECT_URIS", "")
    if uris_env:
        return [u.strip() for u in uris_env.split(",") if u.strip()]
    # Defaults: localhost dev + production domain/IP
    frontend = DEFAULT_FRONTEND_URL
    uris = [
        "http://localhost:4200/auth/oidc.callback",
        "http://localhost:4200/wiki/auth/oidc.callback",
        f"{frontend}/auth/oidc.callback",       # Outline default (without /wiki prefix)
        f"{frontend}/wiki/auth/oidc.callback",  # Via /wiki sub-path
        "http://localhost:8000/auth/oidc.callback",
        "http://localhost:3002/auth/oidc.callback",
    ]
    prod_url = DEFAULT_OIDC_ISSUER
    if prod_url and "localhost" not in prod_url:
        uris.append(f"{prod_url}/auth/oidc.callback")
        # Outline callback on production
        outline_url = DEFAULT_OUTLINE_PUBLIC_URL
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
OIDC_ISSUER = DEFAULT_OIDC_ISSUER

# Frontend URL (for redirecting unauthenticated users to login)
FRONTEND_URL = DEFAULT_FRONTEND_URL

# Authorization code TTL (seconds)
AUTH_CODE_TTL = 300  # 5 minutes
