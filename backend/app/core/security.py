"""JWT authentication and password hashing utilities."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_session
from app.core.jwt_compat import JWTError, decode_jwt, encode_jwt
from app.core.passwords import hash_password, verify_password
bearer_scheme = HTTPBearer(auto_error=False)


# ---------------------------------------------------------------------------
# Token helpers
# ---------------------------------------------------------------------------

def create_access_token(
    subject: str | int,
    expires_delta: timedelta | None = None,
) -> str:
    if expires_delta is None:
        expires_delta = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(subject),
        "iat": now,
        "exp": now + expires_delta,
        "type": "access",
    }
    return encode_jwt(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def create_refresh_token(
    subject: str | int,
    expires_delta: timedelta | None = None,
) -> str:
    if expires_delta is None:
        expires_delta = timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(subject),
        "iat": now,
        "exp": now + expires_delta,
        "type": "refresh",
    }
    return encode_jwt(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def decode_access_token(token: str) -> dict:
    """Decode and validate an access token. Raises JWTError on failure."""
    payload = decode_jwt(
        token,
        settings.SECRET_KEY,
        algorithms=[settings.ALGORITHM],
    )
    if payload.get("type") != "access":
        raise JWTError("Token is not an access token")
    return payload


def decode_refresh_token(token: str) -> dict:
    """Decode and validate a refresh token. Raises JWTError on failure."""
    payload = decode_jwt(
        token,
        settings.SECRET_KEY,
        algorithms=[settings.ALGORITHM],
    )
    if payload.get("type") != "refresh":
        raise JWTError("Token is not a refresh token")
    return payload


# ---------------------------------------------------------------------------
# FastAPI dependency — extract current user from Bearer token
# ---------------------------------------------------------------------------

async def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: AsyncSession = Depends(get_session),
) -> dict:
    """Extract and validate the JWT access token, return user from DB.

    Usage in route::

        @router.get("/me")
        async def me(current_user: dict = Depends(get_current_user)):
            return current_user
    """
    from app.models.user import User  # lazy import to avoid circular deps

    payload: dict | None = None

    if credentials is not None:
        try:
            payload = decode_access_token(credentials.credentials)
        except JWTError:
            payload = None

    # Browser sessions may still have the access token cookie even when
    # localStorage or the Authorization header has drifted out of sync.
    if payload is None:
        access_cookie = request.cookies.get("pa_token")
        if access_cookie:
            try:
                payload = decode_access_token(access_cookie)
            except JWTError:
                payload = None

    # Fallback for stale frontend bundles: if the Bearer token is missing or
    # expired but the browser still has a valid refresh cookie, keep the API
    # session alive instead of hard-failing into a 401 loop.
    if payload is None:
        refresh_cookie = request.cookies.get("refresh_token")
        if refresh_cookie:
            try:
                refresh_payload = decode_refresh_token(refresh_cookie)
                payload = {
                    "sub": refresh_payload.get("sub"),
                    "type": "access",
                }
            except JWTError:
                payload = None

    if payload is None:
        detail = "Missing Authorization header" if credentials is None else "Invalid or expired token"
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=detail,
            headers={"WWW-Authenticate": "Bearer"},
        )

    user_id = payload.get("sub")
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token missing subject",
        )

    # Look up user in DB
    result = await db.execute(select(User).where(User.id == int(user_id)))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is disabled",
        )
    if user.locked_at is not None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is locked",
        )

    return {"id": user.id, "email": user.email, "name": user.name, "role": user.role}


async def require_admin(current_user: dict = Depends(get_current_user)) -> dict:
    """Require platform administrator privileges."""
    if current_user.get("role") != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Administrator privileges required",
        )
    return current_user


async def get_optional_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: AsyncSession = Depends(get_session),
) -> dict | None:
    """Best-effort session probe that never raises 401 for anonymous users.

    This is used by public routes/pages that want to discover whether the
    browser already has a recoverable session without generating console noise
    from expected anonymous requests.
    """
    try:
        return await get_current_user(request=request, credentials=credentials, db=db)
    except HTTPException as exc:
        if exc.status_code == status.HTTP_401_UNAUTHORIZED:
            return None
        raise
