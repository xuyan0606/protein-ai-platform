"""Auth endpoints — login, register, refresh, profile."""

from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel, EmailStr, Field, field_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_refresh_token,
    get_current_user,
    get_optional_current_user,
    hash_password,
    require_admin,
    verify_password,
)
from app.core.rate_limiter import rate_limit
from app.models.user import User

router = APIRouter()

# Determine if HTTPS is in use (for secure cookie flag)
_USES_HTTPS = os.getenv("USE_HTTPS", "false").lower() in ("true", "1", "yes")
_REFRESH_COOKIE_MAX_AGE = int(timedelta(days=7).total_seconds())
_UNIFIED_LOGOUT_COOKIE_NAMES = (
    "pa_token",
    "refresh_token",
    "accessToken",
    "csrfToken",
    "lastSignedIn",
    "oauth_csrf",
    "loggedIn",
    "returnTo",
)


def _set_auth_cookies(response: Response, access_token: str, refresh_token: str) -> None:
    """Keep browser cookies aligned with the JWTs returned in the response body."""
    response.set_cookie(
        key="pa_token",
        value=access_token,
        httponly=True,
        secure=_USES_HTTPS,
        samesite="lax",
        max_age=1800,
        path="/",
    )
    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        httponly=True,
        secure=_USES_HTTPS,
        samesite="lax",
        max_age=_REFRESH_COOKIE_MAX_AGE,
        path="/",
    )


def _clear_auth_cookies(response: Response) -> None:
    """Clear platform auth cookies and Outline cookies on the shared host."""
    for cookie_name in _UNIFIED_LOGOUT_COOKIE_NAMES:
        response.delete_cookie(
            key=cookie_name,
            path="/",
            secure=_USES_HTTPS,
            samesite="lax",
        )


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class LoginRequest(BaseModel):
    email: str
    password: str


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=6, max_length=128)
    name: str = Field(min_length=1, max_length=200)

    @field_validator("name")
    @classmethod
    def name_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Name cannot be empty")
        return v.strip()


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user: dict


class RefreshRequest(BaseModel):
    refresh_token: str | None = None


class UserProfile(BaseModel):
    id: int
    email: str
    name: str
    role: str = "researcher"
    is_active: bool = True
    locked_at: str | None = None
    disabled_reason: str | None = None


class SessionResponse(BaseModel):
    authenticated: bool
    user: UserProfile | None = None


class AdminUserProfile(UserProfile):
    created_at: str | None = None


class AdminUserListResponse(BaseModel):
    count: int
    users: list[AdminUserProfile]


class AdminUserRoleUpdateRequest(BaseModel):
    role: str

    @field_validator("role")
    @classmethod
    def role_must_be_supported(cls, value: str) -> str:
        role = value.strip().lower()
        if role not in {"admin", "researcher"}:
            raise ValueError("Role must be one of: admin, researcher")
        return role


class AdminUserStatusUpdateRequest(BaseModel):
    is_active: bool | None = None
    locked: bool | None = None
    disabled_reason: str | None = Field(default=None, max_length=500)

    @field_validator("disabled_reason")
    @classmethod
    def clean_reason(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None


def _user_payload(user: User) -> dict:
    return {
        "id": user.id,
        "email": user.email,
        "name": user.name,
        "role": user.role,
        "is_active": user.is_active,
        "locked_at": user.locked_at.isoformat() if user.locked_at else None,
        "disabled_reason": user.disabled_reason,
    }


def _admin_user_profile(user: User) -> AdminUserProfile:
    return AdminUserProfile(
        **_user_payload(user),
        created_at=user.created_at.isoformat() if user.created_at else None,
    )


def _assert_user_login_allowed(user: User) -> None:
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User account is disabled")
    if user.locked_at is not None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User account is locked")


def _login_identifiers(identifier: str) -> list[str]:
    """Return database identifiers accepted for a login input."""
    cleaned = identifier.strip()
    if cleaned.lower() == "admin":
        return ["admin@protein.local", "admin"]
    if "@" not in cleaned:
        return [f"{cleaned}@protein.local", cleaned]
    return [cleaned]


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.post("/login", response_model=TokenResponse)
async def login(
    req: LoginRequest,
    response: Response,
    db: AsyncSession = Depends(get_session),
    _rl=Depends(rate_limit("login", max_requests=10, window=60)),
):
    """Authenticate with email/password and return JWT tokens.

    Rate limited: 10 attempts per minute per IP.
    """
    result = await db.execute(select(User).where(User.email.in_(_login_identifiers(req.email))))
    user = result.scalar_one_or_none()

    if user is None or not User.verify_password(req.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )
    _assert_user_login_allowed(user)

    access_token = create_access_token(subject=user.id)
    refresh_token = create_refresh_token(subject=user.id)

    _set_auth_cookies(response, access_token, refresh_token)

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        user=_user_payload(user),
    )


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def register(
    req: RegisterRequest,
    response: Response,
    db: AsyncSession = Depends(get_session),
    _rl=Depends(rate_limit("register", max_requests=5, window=60)),
):
    """Create a new user account and return JWT tokens.

    Rate limited: 5 registrations per minute per IP.
    """
    # Check if email already exists
    result = await db.execute(select(User).where(User.email == req.email))
    if result.scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already registered",
        )

    user = User(
        email=req.email,
        hashed_password=User.hash_password(req.password),
        name=req.name,
    )
    db.add(user)
    await db.flush()

    access_token = create_access_token(subject=user.id)
    refresh_token = create_refresh_token(subject=user.id)

    _set_auth_cookies(response, access_token, refresh_token)

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        user=_user_payload(user),
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh(
    req: RefreshRequest,
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_session),
    _rl=Depends(rate_limit("refresh", max_requests=10, window=60)),
):
    """Exchange a refresh token for a new access + refresh token pair.

    Rate limited: 10 refreshes per minute per IP.
    """
    from app.core.jwt_compat import JWTError
    refresh_token = req.refresh_token or request.cookies.get("refresh_token")
    if not refresh_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing refresh token",
        )
    try:
        payload = decode_refresh_token(refresh_token)
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token",
        )

    try:
        user_id = int(payload["sub"])
    except (KeyError, ValueError, TypeError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Malformed refresh token",
        )

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )
    _assert_user_login_allowed(user)

    access_token = create_access_token(subject=user.id)
    refresh_token = create_refresh_token(subject=user.id)

    _set_auth_cookies(response, access_token, refresh_token)

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        user=_user_payload(user),
    )


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(response: Response):
    """Clear server-managed auth cookies."""
    _clear_auth_cookies(response)
    response.status_code = status.HTTP_204_NO_CONTENT


@router.get("/me", response_model=UserProfile)
async def me(current_user: dict = Depends(get_current_user)):
    """Return the authenticated user's profile."""
    return UserProfile(**current_user)


@router.get("/session", response_model=SessionResponse)
async def session_probe(current_user: dict | None = Depends(get_optional_current_user)):
    """Return session state without emitting 401 for anonymous browsers."""
    if current_user is None:
        return SessionResponse(authenticated=False, user=None)
    return SessionResponse(authenticated=True, user=UserProfile(**current_user))


@router.get("/admin/ping")
async def admin_ping(current_user: dict = Depends(require_admin)):
    """Small protected endpoint used by tests and future admin UI bootstrapping."""
    return {"status": "ok", "user": current_user}


@router.get("/admin/users", response_model=AdminUserListResponse)
async def list_admin_users(
    limit: int = 100,
    current_user: dict = Depends(require_admin),
    db: AsyncSession = Depends(get_session),
):
    """List users for the admin console."""
    bounded_limit = max(1, min(limit, 500))
    result = await db.execute(select(User).order_by(User.created_at.desc(), User.id.desc()).limit(bounded_limit))
    users = [
        _admin_user_profile(user)
        for user in result.scalars().all()
    ]
    return AdminUserListResponse(count=len(users), users=users)


@router.patch("/admin/users/{user_id}/role", response_model=AdminUserProfile)
async def update_admin_user_role(
    user_id: int,
    req: AdminUserRoleUpdateRequest,
    current_user: dict = Depends(require_admin),
    db: AsyncSession = Depends(get_session),
):
    """Update a user's platform role. Admin only."""
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(404, "User not found")

    if int(current_user["id"]) == user.id and user.role == "admin" and req.role != "admin":
        raise HTTPException(400, "Administrators cannot demote their own account")

    user.role = req.role
    await db.flush()
    return _admin_user_profile(user)


@router.patch("/admin/users/{user_id}/status", response_model=AdminUserProfile)
async def update_admin_user_status(
    user_id: int,
    req: AdminUserStatusUpdateRequest,
    current_user: dict = Depends(require_admin),
    db: AsyncSession = Depends(get_session),
):
    """Enable/disable or lock/unlock a user account. Admin only."""
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(404, "User not found")

    if int(current_user["id"]) == user.id:
        if req.is_active is False:
            raise HTTPException(400, "Administrators cannot disable their own account")
        if req.locked is True:
            raise HTTPException(400, "Administrators cannot lock their own account")

    if req.is_active is not None:
        user.is_active = req.is_active
    if req.locked is not None:
        user.locked_at = datetime.now(timezone.utc) if req.locked else None
    if req.disabled_reason is not None or req.is_active is True:
        user.disabled_reason = req.disabled_reason

    await db.flush()
    return _admin_user_profile(user)
