"""Proxy Outline Wiki through the backend to allow iframe embedding.

Outline sets X-Frame-Options: SAMEORIGIN which blocks iframe embedding.
This proxy removes that header so Outline can be embedded in the platform.

The proxy is registered as the LAST router in main.py, so it only catches
requests that don't match any backend API route.

Architecture
------------
  Browser ──► backend:8000/* ──► outline:3001/*   (HTTP proxy)
  Browser ──► backend:8000/realtime/* ──ws──► outline:3001/realtime/*  (WS relay)

Defaults are production-safe Docker service names.  Override via env:
  OUTLINE_URL     — HTTP target  (default: http://outline:3001)
  OUTLINE_WS_URL  — WS target    (default: ws://outline:3001)
"""

from __future__ import annotations

import asyncio
import logging
import os
import re
import time
from dataclasses import dataclass
from typing import Optional
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import httpx
from fastapi import APIRouter, Request, WebSocket, WebSocketDisconnect
from starlette.responses import RedirectResponse, Response, StreamingResponse
from starlette.types import Send, Scope

logger = logging.getLogger(__name__)

router = APIRouter()
OUTLINE_OIDC_START_ROUTE = "/wiki/auth/oidc"

# ---------------------------------------------------------------------------
# Configuration — all defaults are correct for Docker deployment
# ---------------------------------------------------------------------------

# Docker DNS: "outline" = outline container, port 3001 = Outline's PORT env
OUTLINE_URL = os.getenv("OUTLINE_URL", "http://outline:3001")
OUTLINE_WS_URL = os.getenv("OUTLINE_WS_URL", OUTLINE_URL.replace("http", "ws", 1))

# ---------------------------------------------------------------------------
# Circuit breaker — prevent cascading 502s when Outline is down
# ---------------------------------------------------------------------------

# After this many consecutive failures, stop trying for COOLDOWN seconds.
FAILURE_THRESHOLD = 5
COOLDOWN_SECONDS = 30
RETRY_ATTEMPTS = 3          # per-request retries
RETRY_BACKOFF_BASE = 0.5    # seconds: 0.5 → 1.0 → 2.0


@dataclass
class _CircuitBreaker:
    """Simple in-process circuit breaker.  Shared across all requests."""

    failures: int = 0
    last_failure: float = 0.0
    opened_at: float = 0.0

    @property
    def is_open(self) -> bool:
        if self.failures < FAILURE_THRESHOLD:
            return False
        if time.monotonic() - self.opened_at < COOLDOWN_SECONDS:
            return True
        # Cooldown expired → half-open (allow one probe)
        self.failures = 0
        return False

    def record_success(self) -> None:
        self.failures = 0

    def record_failure(self) -> None:
        self.failures += 1
        self.last_failure = time.monotonic()
        if self.failures >= FAILURE_THRESHOLD:
            self.opened_at = time.monotonic()


_cb = _CircuitBreaker()


def _circuit_breaker_ok() -> tuple[bool, str]:
    """Return (can_proceed, status_message)."""
    if not _cb.is_open:
        return True, ""
    remaining = COOLDOWN_SECONDS - (time.monotonic() - _cb.opened_at)
    return False, f"circuit open — retry in {remaining:.0f}s"


# ---------------------------------------------------------------------------
# Header processing
# ---------------------------------------------------------------------------

# Strip these from Outline's response (they block iframe embedding)
STRIP_RESPONSE_HEADERS = {"x-frame-options", "content-security-policy"}

# Don't forward these from client to Outline.
# `accept-encoding` is forced to `identity` so Outline always returns
# plain HTML/JS. This avoids compressed bytes leaking through the proxy
# without matching browser-facing encoding headers.
SKIP_FORWARD_HEADERS = {"host", "origin", "referer", "accept-encoding"}

# Node.js may combine multiple Set-Cookie headers into one comma-separated
# value. Split on ", " only when followed by a cookie name (alphanum + "="),
# not when followed by a digit (which is part of expires=Day, 27 Jun 2026).
_SET_COOKIE_SPLIT_RE = re.compile(r", (?=[a-zA-Z][\w-]*=)")

# ---------------------------------------------------------------------------
# Response wrapper
# ---------------------------------------------------------------------------


class _ProxyResponse(StreamingResponse):
    """StreamingResponse that preserves duplicate headers (e.g. Set-Cookie)."""

    def __init__(self, *args, raw_headers: list[tuple[str, str]] | None = None, **kwargs):
        self._raw_headers = raw_headers or []
        super().__init__(*args, **kwargs)

    async def __call__(self, scope: Scope, receive, send: Send) -> None:
        async def _send(message):
            if message["type"] == "http.response.start":
                message["headers"] = [
                    (k.encode("latin-1"), v.encode("latin-1"))
                    for k, v in self._raw_headers
                ]
            await send(message)

        await super().__call__(scope, receive, _send)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _build_proxy_headers(request: Request) -> dict[str, str]:
    """Build clean headers to forward to Outline."""
    headers = {
        k: v
        for k, v in request.headers.items()
        if k.lower() not in SKIP_FORWARD_HEADERS
    }
    forwarded_host = _first_forwarded_value(request.headers.get("x-forwarded-host"))
    headers["x-forwarded-host"] = forwarded_host or request.headers.get("host", "")
    headers["x-forwarded-proto"] = _request_scheme(request)
    headers["accept-encoding"] = "identity"
    forwarded_port = _first_forwarded_value(request.headers.get("x-forwarded-port"))
    if forwarded_port:
        headers["x-forwarded-port"] = forwarded_port
    return headers


def _build_ws_proxy_headers(websocket: WebSocket) -> dict[str, str]:
    """Build headers for backend -> Outline WebSocket handshakes."""
    headers: dict[str, str] = {}
    forwarded_host = _first_forwarded_value(websocket.headers.get("x-forwarded-host"))
    forwarded_proto = _first_forwarded_value(websocket.headers.get("x-forwarded-proto"))
    forwarded_port = _first_forwarded_value(websocket.headers.get("x-forwarded-port"))

    for name in ("cookie", "user-agent", "authorization"):
        value = websocket.headers.get(name)
        if value:
            headers[name] = value

    headers["x-forwarded-host"] = forwarded_host or websocket.headers.get("host", "")
    headers["x-forwarded-proto"] = forwarded_proto or "http"
    if forwarded_port:
        headers["x-forwarded-port"] = forwarded_port
    return headers


def _first_forwarded_value(value: str | None) -> str | None:
    if not value:
        return None
    first = value.split(",", 1)[0].strip()
    return first or None


def _request_scheme(request: Request) -> str:
    return _first_forwarded_value(request.headers.get("x-forwarded-proto")) or request.url.scheme or "http"


def _request_host(request: Request) -> str:
    return (
        _first_forwarded_value(request.headers.get("x-forwarded-host"))
        or request.headers.get("host")
        or request.url.netloc
    )


def _public_origin(request: Request) -> str:
    return f"{_request_scheme(request)}://{_request_host(request)}".rstrip("/")


def _public_ws_origin(request: Request) -> str:
    scheme = "wss" if _request_scheme(request) == "https" else "ws"
    return f"{scheme}://{_request_host(request)}".rstrip("/")


def _known_public_hosts() -> set[str]:
    hosts = {"localhost", "localhost:4200", "frontend:3000", "backend:8000", "outline:3001"}
    for env_name in ("PUBLIC_BASE_URL", "FRONTEND_URL", "OIDC_ISSUER", "OUTLINE_PUBLIC_URL", "OUTLINE_URL"):
        value = os.getenv(env_name, "").strip()
        if value:
            parsed = urlsplit(value)
            if parsed.netloc:
                hosts.add(parsed.netloc)
    return hosts


def _rewrite_public_url(request: Request, value: str) -> str:
    parsed = urlsplit(value)
    if not parsed.scheme or not parsed.netloc:
        return value
    if parsed.netloc not in _known_public_hosts():
        return value
    public_origin = _public_ws_origin(request) if parsed.scheme in {"ws", "wss"} else _public_origin(request)
    public = urlsplit(public_origin)
    return urlunsplit((public.scheme, public.netloc, parsed.path, parsed.query, parsed.fragment))


def _rewrite_location(request: Request, value: str) -> str:
    rewritten = _rewrite_public_url(request, value)
    parsed = urlsplit(rewritten)
    if not parsed.query:
        return rewritten

    changed = rewritten != value
    query_items: list[tuple[str, str]] = []
    for key, item_value in parse_qsl(parsed.query, keep_blank_values=True):
        if key == "redirect_uri":
            next_value = _rewrite_public_url(request, item_value)
            changed = changed or next_value != item_value
            item_value = next_value
        query_items.append((key, item_value))

    if not changed:
        return rewritten

    return urlunsplit(
        (
            parsed.scheme,
            parsed.netloc,
            parsed.path,
            urlencode(query_items),
            parsed.fragment,
        )
    )


def _sanitize_response_headers(
    request: Request,
    headers: list[tuple[str, str]],
) -> list[tuple[str, str]]:
    """Split combined Set-Cookie headers and rewrite internal redirect hosts."""
    result: list[tuple[str, str]] = []
    for k, v in headers:
        lower = k.lower()
        if lower in STRIP_RESPONSE_HEADERS:
            continue
        if lower == "set-cookie":
            for cookie in _SET_COOKIE_SPLIT_RE.split(v):
                cookie = cookie.strip()
                if cookie.lower().startswith("accesstoken="):
                    cookie = re.sub(r";\s*path=[^;]*", "", cookie, flags=re.I)
                    cookie = f"{cookie}; Path=/"
                result.append((k, cookie))
        elif lower == "location":
            result.append((k, _rewrite_location(request, v)))
        elif lower in {"content-length", "content-encoding"}:
            continue
        else:
            result.append((k, v))
    return result


def _rewrite_response_content(request: Request, content: bytes, content_type: str | None) -> bytes:
    if not content or not content_type:
        return content

    lower_content_type = content_type.lower()
    if "text/html" not in lower_content_type and "application/javascript" not in lower_content_type:
        return content

    try:
        text = content.decode("utf-8")
    except UnicodeDecodeError:
        return content

    replacements: dict[str, str] = {}
    for env_name in ("PUBLIC_BASE_URL", "FRONTEND_URL", "OIDC_ISSUER", "OUTLINE_PUBLIC_URL", "OUTLINE_URL"):
        value = os.getenv(env_name, "").strip().rstrip("/")
        if not value:
            continue
        rewritten = _rewrite_public_url(request, value)
        if rewritten != value:
            replacements[value] = rewritten

    public_origin = _public_origin(request)
    public_ws_origin = _public_ws_origin(request)
    derived_pairs = {
        "http://localhost:4200": public_origin,
        "https://localhost": public_origin,
        "http://localhost:4200/wiki": f"{public_origin}/wiki",
        "https://localhost/wiki": f"{public_origin}/wiki",
        "ws://localhost:4200": public_ws_origin,
        "wss://localhost": public_ws_origin,
        "ws://localhost:4200/wiki": f"{public_ws_origin}/wiki",
        "wss://localhost/wiki": f"{public_ws_origin}/wiki",
    }
    for source, target in derived_pairs.items():
        if source != target:
            replacements[source] = target

    rewritten_text = text
    for source, target in replacements.items():
        rewritten_text = rewritten_text.replace(source, target)

    if rewritten_text == text:
        return content
    return rewritten_text.encode("utf-8")


def _target_url(path: str) -> str:
    """Build the full target URL including query string."""
    # query is handled by the caller since we don't have access to request.url here
    return f"{OUTLINE_URL}/{path}" if path else OUTLINE_URL


def _strip_wiki_prefix(path: str) -> str:
    """Map browser-visible /wiki/* requests back to Outline's internal paths."""
    if path == "wiki":
        return ""
    if path.startswith("wiki/"):
        return path.removeprefix("wiki/")
    return path


async def _has_valid_outline_session(request: Request) -> bool:
    """Check whether the current Outline accessToken cookie still works.

    Browsers can retain stale Outline cookies across proxy/config changes.
    When that happens the wiki iframe keeps loading with an invalid session and
    never re-enters the OIDC flow, producing repeated 401/403 errors in the UI.
    """
    if not request.cookies.get("accessToken"):
        return False

    headers = {
        "cookie": request.headers.get("cookie", ""),
        "accept-encoding": "identity",
    }

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(
                f"{OUTLINE_URL}/api/auth.info",
                headers=headers,
                content=b"{}",
            )
            return response.status_code == 200
    except Exception as exc:
        logger.warning("Outline session validation failed: %s", exc)
        return False


async def _maybe_bootstrap_outline_session(
    request: Request,
    path: str,
) -> RedirectResponse | None:
    """Send platform-authenticated users through Outline OIDC before wiki loads."""
    if request.method not in {"GET", "HEAD"}:
        return None

    normalized = path.strip("/")
    if normalized in {"", "wiki"} or normalized.startswith("wiki/"):
        if normalized == "wiki/auth/oidc" or normalized.startswith("wiki/auth/oidc/"):
            return None

        if normalized == "wiki/auth/oidc.callback" or normalized.startswith("wiki/auth/oidc.callback/"):
            return None

        # Keep wiki and agent auth unified: anonymous browsers should re-enter
        # the platform login/OIDC flow before Outline boots its SPA. This
        # avoids Outline's own auth.info probe surfacing noisy 401/page errors.
        if not request.cookies.get("pa_token"):
            return RedirectResponse(url=OUTLINE_OIDC_START_ROUTE, status_code=302)

        if await _has_valid_outline_session(request):
            return None

        response = RedirectResponse(url=OUTLINE_OIDC_START_ROUTE, status_code=302)
        response.delete_cookie("accessToken", path="/", samesite="lax")
        response.delete_cookie("csrfToken", path="/", samesite="lax")
        response.delete_cookie("lastSignedIn", path="/", samesite="lax")
        return response

    return None


# ---------------------------------------------------------------------------
# Core proxy logic
# ---------------------------------------------------------------------------


async def _proxy(request: Request, path: str = "") -> Response | StreamingResponse:
    """Forward request to Outline, stripping X-Frame-Options.

    Includes:
    - Circuit breaker (fails fast when Outline is down)
    - Per-request retries (3x with backoff: 0.5s → 1.0s → 2.0s)
    - Proper header handling (strips frame blockers, splits Set-Cookie)
    """

    # ---- Circuit breaker ---------------------------------------------------
    can_proceed, reason = _circuit_breaker_ok()
    if not can_proceed:
        return StreamingResponse(
            iter([f'{{"error": "Wiki unavailable", "detail": "{reason}"}}'.encode()]),
            status_code=503,
            media_type="application/json",
        )

    # ---- Prepare request ---------------------------------------------------
    headers = _build_proxy_headers(request)
    body = await request.body() if request.method in ("POST", "PUT", "PATCH") else None

    path = _strip_wiki_prefix(path)
    target = f"{OUTLINE_URL}/{path}" if path else OUTLINE_URL
    query = str(request.url.query)
    if query:
        target += f"?{query}"

    # ---- Send with retries ------------------------------------------------
    last_error: Optional[Exception] = None

    for attempt in range(1, RETRY_ATTEMPTS + 1):
        client = httpx.AsyncClient(timeout=30.0)
        try:
            req = client.build_request(
                request.method, target, headers=headers, content=body
            )
            resp = await client.send(req, stream=False)

            # Success
            _cb.record_success()
            rewritten_content = _rewrite_response_content(
                request,
                resp.content,
                resp.headers.get("content-type"),
            )
            raw_headers = _sanitize_response_headers(request, list(resp.headers.multi_items()))
            return _ProxyResponse(
                content=iter([rewritten_content]),
                status_code=resp.status_code,
                raw_headers=raw_headers,
                media_type=resp.headers.get("content-type"),
            )

        except httpx.ConnectError as e:
            last_error = e
            logger.warning(
                "Outline proxy: connect refused (attempt %s/%s) — %s", attempt, RETRY_ATTEMPTS, e
            )
        except httpx.TimeoutException as e:
            last_error = e
            logger.warning(
                "Outline proxy: timeout (attempt %s/%s) — %s", attempt, RETRY_ATTEMPTS, e
            )
        except httpx.RequestError as e:
            last_error = e
            logger.warning(
                "Outline proxy: request error (attempt %s/%s) — %s", attempt, RETRY_ATTEMPTS, e
            )
        finally:
            await client.aclose()

        # Backoff before retry (skip on last attempt)
        if attempt < RETRY_ATTEMPTS:
            await asyncio.sleep(RETRY_BACKOFF_BASE * (2 ** (attempt - 1)))

    # All retries exhausted
    _cb.record_failure()
    logger.error("Outline proxy: all %s attempts failed — %s", RETRY_ATTEMPTS, last_error)
    return StreamingResponse(
        iter([b'{"error":"Wiki unavailable","detail":"Cannot reach Outline after retries. It may be starting up."}']),
        status_code=502,
        media_type="application/json",
    )


# ---------------------------------------------------------------------------
# WebSocket proxy for realtime collaboration (Socket.IO)
# ---------------------------------------------------------------------------


@router.websocket("/realtime/")
async def proxy_websocket_realtime(websocket: WebSocket):
    """Proxy Socket.IO WebSocket to Outline."""
    await _proxy_websocket(websocket, "realtime")


@router.websocket("/realtime/{path:path}")
async def proxy_websocket_realtime_path(websocket: WebSocket, path: str = ""):
    """Proxy Socket.IO WebSocket with path to Outline."""
    target = f"realtime/{path}" if path else "realtime"
    await _proxy_websocket(websocket, target)


@router.websocket("/wiki/{path:path}")
async def proxy_websocket_wiki_path(websocket: WebSocket, path: str):
    """Proxy Outline collaboration/document WebSockets under /wiki/*."""
    await _proxy_websocket(websocket, f"wiki/{path}")


async def _proxy_websocket(client_ws: WebSocket, path: str) -> None:
    """Bidirectionally relay WebSocket messages between client and Outline."""
    import websockets
    origin = _first_forwarded_value(client_ws.headers.get("origin")) or _public_origin(client_ws)  # type: ignore[arg-type]
    headers = _build_ws_proxy_headers(client_ws)
    target_path = _strip_wiki_prefix(path).strip("/")
    outline_ws_url = f"{OUTLINE_WS_URL}/{target_path}" if target_path else OUTLINE_WS_URL
    if client_ws.url.query:
        outline_ws_url = f"{outline_ws_url}?{client_ws.url.query}"

    try:
        async with websockets.connect(
            outline_ws_url,
            origin=origin,
            additional_headers=headers,
            compression=None,
            user_agent_header=None,
        ) as outline_ws:
            await client_ws.accept()

            async def client_to_outline():
                try:
                    while True:
                        message = await client_ws.receive()
                        message_type = message.get("type")
                        if message_type == "websocket.disconnect":
                            break
                        if message_type != "websocket.receive":
                            continue
                        if message.get("text") is not None:
                            await outline_ws.send(message["text"])
                        elif message.get("bytes") is not None:
                            await outline_ws.send(message["bytes"])
                except (WebSocketDisconnect, websockets.ConnectionClosed):
                    pass

            async def outline_to_client():
                try:
                    while True:
                        data = await outline_ws.recv()
                        if isinstance(data, str):
                            await client_ws.send_text(data)
                        else:
                            await client_ws.send_bytes(data)
                except (websockets.ConnectionClosed, WebSocketDisconnect):
                    pass

            done, pending = await asyncio.wait(
                [
                    asyncio.create_task(client_to_outline()),
                    asyncio.create_task(outline_to_client()),
                ],
                return_when=asyncio.FIRST_COMPLETED,
            )
            for task in pending:
                task.cancel()

    except (websockets.ConnectionClosed, OSError) as e:
        logger.debug(f"WebSocket relay closed: {e}")
        await client_ws.close()
    except WebSocketDisconnect:
        pass
    except Exception:
        logger.exception("WebSocket proxy error")
        await client_ws.close(code=1011)


# ---------------------------------------------------------------------------
# Catch-all HTTP routes (must be registered LAST in main.py)
# ---------------------------------------------------------------------------
#
# These catch every request that didn't match a real API route and forward
# it to Outline.  Outline returns its own SPA which the browser renders
# directly — no sub-path rewriting, no `/wiki` prefix confusion.
#
# The cookie-aware redirect below sends logged-in platform users straight
# to OIDC (bypassing Outline's own login page), which avoids a noisy 401
# before the redirect.


@router.api_route(
    "/{path:path}",
    methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"],
    include_in_schema=False,
)
async def proxy_with_path(request: Request, path: str):
    redirect = await _maybe_bootstrap_outline_session(request, path)
    if redirect is not None:
        return redirect
    return await _proxy(request, path)


@router.api_route("/wiki", methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"], include_in_schema=False)
async def proxy_wiki_root(request: Request):
    redirect = await _maybe_bootstrap_outline_session(request, "wiki")
    if redirect is not None:
        return redirect
    return await _proxy(request, "wiki")


@router.api_route("/wiki/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"], include_in_schema=False)
async def proxy_wiki_path(request: Request, path: str):
    redirect = await _maybe_bootstrap_outline_session(request, f"wiki/{path}")
    if redirect is not None:
        return redirect
    return await _proxy(request, f"wiki/{path}")


@router.api_route("/", methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"], include_in_schema=False)
async def proxy_root(request: Request):
    redirect = await _maybe_bootstrap_outline_session(request, "")
    if redirect is not None:
        return redirect
    return await _proxy(request)


# ---------------------------------------------------------------------------
# Startup check — warn early if Outline is unreachable
# ---------------------------------------------------------------------------


async def check_outline_reachable(timeout: float = 5.0) -> bool:
    """Called during backend startup.  Returns True if Outline responds."""
    client = httpx.AsyncClient(timeout=timeout)
    try:
        resp = await client.get(f"{OUTLINE_URL}/auth/login")
        logger.info("Outline reachable at %s (HTTP %s)", OUTLINE_URL, resp.status_code)
        return True
    except httpx.ConnectError:
        logger.warning(
            "Outline not reachable at %s — Wiki proxy will start in degraded mode. "
            "It will recover automatically once Outline is healthy.",
            OUTLINE_URL,
        )
        return False
    except Exception as e:
        logger.warning("Outline startup check failed: %s", e)
        return False
    finally:
        await client.aclose()
