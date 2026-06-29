"""Auth endpoints — login, register, refresh, profile."""

from __future__ import annotations

import os

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel, EmailStr, Field, field_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_refresh_token,
    get_current_user,
    hash_password,
    verify_password,
)
from app.core.rate_limiter import rate_limit
from app.models.user import User

router = APIRouter()

# Determine if HTTPS is in use (for secure cookie flag)
_USES_HTTPS = os.getenv("USE_HTTPS", "false").lower() in ("true", "1", "yes")


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
    refresh_token: str


class UserProfile(BaseModel):
    id: int
    email: str
    name: str


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
    result = await db.execute(select(User).where(User.email == req.email))
    user = result.scalar_one_or_none()

    if user is None or not User.verify_password(req.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    access_token = create_access_token(subject=user.id)
    refresh_token = create_refresh_token(subject=user.id)

    # Set pa_token cookie for OIDC SSO bridge (Outline integration)
    response.set_cookie(
        key="pa_token",
        value=access_token,
        httponly=True,
        secure=_USES_HTTPS,
        samesite="lax",
        max_age=1800,  # 30 minutes, matches access token expiry
        path="/",
    )

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        user={"id": user.id, "email": user.email, "name": user.name},
    )


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def register(
    req: RegisterRequest,
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

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        user={"id": user.id, "email": user.email, "name": user.name},
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh(
    req: RefreshRequest,
    db: AsyncSession = Depends(get_session),
    _rl=Depends(rate_limit("refresh", max_requests=10, window=60)),
):
    """Exchange a refresh token for a new access + refresh token pair.

    Rate limited: 10 refreshes per minute per IP.
    """
    from jose import JWTError
    try:
        payload = decode_refresh_token(req.refresh_token)
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

    access_token = create_access_token(subject=user.id)
    refresh_token = create_refresh_token(subject=user.id)

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        user={"id": user.id, "email": user.email, "name": user.name},
    )


@router.get("/me", response_model=UserProfile)
async def me(current_user: dict = Depends(get_current_user)):
    """Return the authenticated user's profile."""
    return UserProfile(**current_user)
