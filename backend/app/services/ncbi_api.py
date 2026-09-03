"""Shared NCBI request parameter and evidence metadata helpers."""

from __future__ import annotations

from typing import Any, Mapping

import httpx

from app.core.config import settings


_PARAM_BY_API = {
    "blast": "NCBI_API_KEY",
    "pubmed": "api_key",
}

_RATE_LIMIT_POLICY = {
    "blast": (
        "NCBI BLAST requests include NCBI_API_KEY when configured; rate-limit "
        "or HTTP 429 responses fail degraded and surface Retry-After without "
        "automatic sleep/retry."
    ),
    "pubmed": (
        "PubMed E-utilities requests include api_key when configured; HTTP 429 "
        "responses fail degraded and surface Retry-After without automatic "
        "sleep/retry."
    ),
}


class NCBIRateLimitError(RuntimeError):
    """Structured NCBI rate-limit error that never contains the API key."""

    def __init__(
        self,
        *,
        source: str,
        retry_after: str | None = None,
        status_code: int | None = None,
        message: str | None = None,
    ) -> None:
        self.source = source
        self.retry_after = retry_after
        self.status_code = status_code
        self.code = "RATE_LIMITED"
        safe_message = message or "NCBI rate limit exceeded"
        super().__init__(f"{self.code}: {safe_message}")

    def as_details(self) -> dict[str, Any]:
        details: dict[str, Any] = {
            "code": self.code,
            "source": self.source,
        }
        if self.status_code is not None:
            details["status_code"] = self.status_code
        if self.retry_after:
            details["retry_after"] = self.retry_after
        return details


def ncbi_api_key_configured() -> bool:
    return bool((settings.NCBI_API_KEY or "").strip())


def ncbi_request_params(api: str, params: Mapping[str, Any]) -> dict[str, Any]:
    """Return NCBI request params with the correct API-key parameter if set."""
    merged = dict(params)
    key = (settings.NCBI_API_KEY or "").strip()
    if key:
        merged[_PARAM_BY_API[api]] = key
    return merged


def ncbi_rate_limit_policy(api: str) -> str:
    return _RATE_LIMIT_POLICY[api]


def ncbi_evidence_details(
    api: str,
    *,
    extra: Mapping[str, Any] | None = None,
    retry_after_by_source: Mapping[str, str] | None = None,
    error: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Build evidence details for NCBI-backed calls without leaking secrets."""
    details: dict[str, Any] = {
        "api_key_configured": ncbi_api_key_configured(),
        "rate_limit_policy": ncbi_rate_limit_policy(api),
    }
    if extra:
        details.update(dict(extra))
    if retry_after_by_source:
        details["retry_after_by_source"] = dict(retry_after_by_source)
    if error:
        details["error"] = dict(error)
    return details


def retry_after_from_exception(exc: Exception) -> str | None:
    response = getattr(exc, "response", None)
    headers = getattr(response, "headers", None)
    if not headers:
        return None
    retry_after = headers.get("Retry-After")
    return str(retry_after) if retry_after else None


def rate_limit_from_response(
    response: httpx.Response,
    *,
    source: str,
    message: str | None = None,
) -> NCBIRateLimitError | None:
    if response.status_code != 429:
        return None
    return NCBIRateLimitError(
        source=source,
        retry_after=response.headers.get("Retry-After"),
        status_code=response.status_code,
        message=message or "NCBI returned HTTP 429",
    )

