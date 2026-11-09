"""Small compatibility wrapper around PyJWT for project-local JWT usage."""

from __future__ import annotations

from typing import Any

from jwt import InvalidTokenError
from jwt import decode as _decode
from jwt import encode as _encode

JWTError = InvalidTokenError


def encode_jwt(
    payload: dict[str, Any],
    key: str | bytes,
    *,
    algorithm: str,
    headers: dict[str, Any] | None = None,
) -> str:
    return _encode(payload, key, algorithm=algorithm, headers=headers)


def decode_jwt(
    token: str,
    key: str | bytes,
    *,
    algorithms: list[str],
    options: dict[str, Any] | None = None,
    audience: str | list[str] | None = None,
    issuer: str | None = None,
) -> dict[str, Any]:
    kwargs: dict[str, Any] = {"algorithms": algorithms}
    if options is not None:
        kwargs["options"] = options
    if audience is not None:
        kwargs["audience"] = audience
    if issuer is not None:
        kwargs["issuer"] = issuer
    return _decode(token, key, **kwargs)
