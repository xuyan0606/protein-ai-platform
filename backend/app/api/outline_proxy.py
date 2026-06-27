"""Proxy Outline Wiki through the backend to allow iframe embedding.

Outline sets X-Frame-Options: SAMEORIGIN which blocks iframe embedding.
This proxy removes that header so Outline can be embedded in the platform.

The proxy is registered as the LAST router in main.py, so it only catches
requests that don't match any backend API route. Outline's URL is simply
http://localhost:8000/ (no path prefix), which avoids client-side redirect
issues that occur with sub-path deployment.
"""

from __future__ import annotations

import logging
import re

import httpx
from fastapi import APIRouter, Request, Response, WebSocket, WebSocketDisconnect
from starlette.responses import StreamingResponse
from starlette.types import Send, Scope

logger = logging.getLogger(__name__)

router = APIRouter()

OUTLINE_URL = "http://localhost:3002"
OUTLINE_WS_URL = "ws://localhost:3002"

# Headers to strip from Outline's response (they block iframe embedding)
STRIP_HEADERS = {"x-frame-options", "content-security-policy"}

# Headers not to forward to Outline
SKIP_FORWARD_HEADERS = {"host", "origin", "referer"}

# Headers to add to the proxied request
ADD_FORWARD_HEADERS = {
    "x-forwarded-host": "localhost:8000",
}

# Node.js may combine multiple Set-Cookie headers into one comma-separated value.
# Split on ", " only when followed by a cookie name (alphanum + "="), not
# when followed by a digit (which is part of expires=Day, 27 Jun 2026).
_SET_COOKIE_SPLIT = re.compile(r", (?=[a-zA-Z][\w-]*=)")


async def _proxy(request: Request, path: str = "") -> Response:
    """Forward request to Outline, stripping X-Frame-Options."""
    client = httpx.AsyncClient(timeout=30.0)
    try:
        headers = {
            k: v for k, v in request.headers.items()
            if k.lower() not in SKIP_FORWARD_HEADERS
        }
        headers.update(ADD_FORWARD_HEADERS)
        body = await request.body() if request.method in ("POST", "PUT", "PATCH") else None

        target = f"{OUTLINE_URL}/{path}" if path else OUTLINE_URL
        query = str(request.url.query)
        if query:
            target += f"?{query}"

        req = client.build_request(request.method, target, headers=headers, content=body)
        resp = await client.send(req, stream=False)

        # Collect all headers, splitting combined Set-Cookie into individual values
        headers_list: list[tuple[str, str]] = []
        for k, v in resp.headers.multi_items():
            lower = k.lower()
            if lower in STRIP_HEADERS:
                continue
            if lower == "set-cookie":
                for cookie in _SET_COOKIE_SPLIT.split(v):
                    headers_list.append((k, cookie.strip()))
            else:
                headers_list.append((k, v))

        return _ProxyResponse(
            content=iter([resp.content]),
            status_code=resp.status_code,
            raw_headers=headers_list,
            media_type=resp.headers.get("content-type"),
        )
    except httpx.RequestError as e:
        logger.error(f"Outline proxy error: {e}")
        return StreamingResponse(
            iter([b"Outline is not available"]),
            status_code=502,
        )
    finally:
        await client.aclose()


class _ProxyResponse(StreamingResponse):
    """StreamingResponse that preserves duplicate headers (e.g. multiple Set-Cookie)."""

    def __init__(self, *args, raw_headers=None, **kwargs):
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
# WebSocket proxy for realtime collaboration (Socket.IO)
# ---------------------------------------------------------------------------

@router.websocket("/realtime/")
async def proxy_websocket_realtime(websocket: WebSocket):
    """Proxy Socket.IO WebSocket connections to Outline."""
    await _proxy_websocket(websocket)


@router.websocket("/realtime/{path:path}")
async def proxy_websocket_realtime_path(websocket: WebSocket, path: str = ""):
    """Proxy Socket.IO WebSocket connections with path to Outline."""
    await _proxy_websocket(websocket)


async def _proxy_websocket(client_ws: WebSocket) -> None:
    """Bidirectionally relay WebSocket messages between client and Outline."""
    import asyncio

    import websockets

    await client_ws.accept()

    outline_ws_url = f"ws://localhost:3002/realtime/"
    if client_ws.url.query:
        outline_ws_url += f"?{client_ws.url.query}"

    try:
        async with websockets.connect(outline_ws_url) as outline_ws:
            async def client_to_outline():
                try:
                    while True:
                        data = await client_ws.receive_bytes()
                        await outline_ws.send(data)
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

            # Run both directions concurrently
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
    except WebSocketDisconnect:
        pass
    except Exception:
        logger.exception("WebSocket proxy error")


# ---------------------------------------------------------------------------
# Catch-all HTTP routes (must be registered last in main.py)
# ---------------------------------------------------------------------------

@router.api_route("/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"])
async def proxy_with_path(request: Request, path: str):
    return await _proxy(request, path)


@router.api_route("/", methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"])
async def proxy_root(request: Request):
    # If user is logged into the platform but not yet into Outline, jump
    # straight to OIDC auth to skip the Outline login page (avoids 401 noise).
    has_pa_token = request.cookies.get("pa_token")
    has_outline_session = request.cookies.get("accessToken")
    if has_pa_token and not has_outline_session:
        from fastapi.responses import RedirectResponse
        return RedirectResponse(url="/auth/oidc", status_code=302)
    return await _proxy(request)