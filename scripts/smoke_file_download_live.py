#!/usr/bin/env python3
"""Verify live upload/download/delete compatibility through the platform API.

This exercises the configured storage backend indirectly through /api/files.
Credentials are read from LIVE_AI_EMAIL/LIVE_AI_PASSWORD or stdin with
--credentials-from-stdin. The script never prints tokens or passwords.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import asdict, dataclass
from typing import Any


@dataclass
class StepResult:
    name: str
    status: str
    detail: str


def _read_credentials_from_stdin() -> tuple[str, str]:
    raw = sys.stdin.read().strip()
    if not raw:
        return "", ""
    payload = json.loads(raw)
    return str(payload.get("email", "")).strip(), str(payload.get("password", "")).strip()


def _request(
    url: str,
    *,
    method: str = "GET",
    token: str | None = None,
    headers: dict[str, str] | None = None,
    body: bytes | None = None,
    timeout: int = 30,
) -> tuple[int, dict[str, str], bytes]:
    request_headers = dict(headers or {})
    if token:
        request_headers["Authorization"] = f"Bearer {token}"
    request = urllib.request.Request(url, data=body, headers=request_headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.status, dict(response.headers.items()), response.read()
    except urllib.error.HTTPError as exc:
        return exc.code, dict(exc.headers.items()), exc.read()


def _json_body(data: bytes) -> dict[str, Any]:
    try:
        return json.loads(data.decode("utf-8", errors="replace")) if data else {}
    except json.JSONDecodeError:
        return {}


def _login(base_url: str, email: str, password: str) -> tuple[int, dict[str, Any]]:
    body = json.dumps({"email": email, "password": password}).encode("utf-8")
    status, _, data = _request(
        f"{base_url.rstrip('/')}/api/auth/login",
        method="POST",
        headers={"Content-Type": "application/json", "Accept": "application/json"},
        body=body,
    )
    return status, _json_body(data)


def _multipart_upload_body(field_name: str, filename: str, content: bytes, content_type: str) -> tuple[str, bytes]:
    boundary = f"----protein-ai-smoke-{int(time.time() * 1000)}"
    lines = [
        f"--{boundary}\r\n".encode(),
        f'Content-Disposition: form-data; name="{field_name}"; filename="{filename}"\r\n'.encode(),
        f"Content-Type: {content_type}\r\n\r\n".encode(),
        content,
        b"\r\n",
        f"--{boundary}--\r\n".encode(),
    ]
    return boundary, b"".join(lines)


def _emit(payload: dict[str, Any], *, json_output: bool) -> None:
    if json_output:
        print(json.dumps(payload, indent=2, ensure_ascii=False))
        return
    for item in payload["results"]:
        print(f"{item['name']}\t{item['status']}\t{item['detail']}")
    summary = payload["summary"]
    print(f"summary\t{summary['status']}\t{summary['failed']} failed / {summary['total']} total")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default=os.getenv("FRONTEND_BASE_URL", "http://120.27.108.138"))
    parser.add_argument("--json", action="store_true", help="Emit JSON")
    parser.add_argument("--require-live", action="store_true", help="Return non-zero when credentials are missing")
    parser.add_argument("--credentials-from-stdin", action="store_true", help="Read {'email','password'} JSON from stdin")
    args = parser.parse_args()

    email = os.getenv("LIVE_AI_EMAIL", "").strip()
    password = os.getenv("LIVE_AI_PASSWORD", "").strip()
    if args.credentials_from_stdin:
        email, password = _read_credentials_from_stdin()

    if not email or not password:
        status = "blocked" if args.require_live else "planned"
        payload = {
            "summary": {
                "status": status,
                "failed": 0,
                "blocked": 1 if args.require_live else 0,
                "planned": 0 if args.require_live else 1,
                "total": 1,
                "passwords_printed": False,
            },
            "base_url": args.base_url,
            "results": [
                asdict(StepResult("live_file_credentials", status, "set LIVE_AI_EMAIL/LIVE_AI_PASSWORD or pass --credentials-from-stdin"))
            ],
        }
        _emit(payload, json_output=args.json)
        return 1 if args.require_live else 0

    results: list[StepResult] = []
    object_name: str | None = None
    token = ""
    try:
        login_status, login_payload = _login(args.base_url, email, password)
        if login_status != 200 or not login_payload.get("access_token"):
            results.append(StepResult("login", "failed", f"HTTP {login_status}"))
            raise RuntimeError("login failed")
        token = str(login_payload["access_token"])
        user_id = login_payload.get("user", {}).get("id")
        results.append(StepResult("login", "passed", "authenticated"))

        content = f"protein-ai-live-download-smoke {int(time.time())}\n".encode("utf-8")
        filename = "protein-ai-live-download-smoke.txt"
        boundary, body = _multipart_upload_body("file", filename, content, "text/plain")
        upload_status, _, upload_body = _request(
            f"{args.base_url.rstrip('/')}/api/files/upload",
            method="POST",
            token=token,
            headers={"Content-Type": f"multipart/form-data; boundary={boundary}", "Accept": "application/json"},
            body=body,
            timeout=60,
        )
        upload_payload = _json_body(upload_body)
        object_name = str(upload_payload.get("object_name") or "")
        download_url = str(upload_payload.get("download_url") or "")
        if upload_status != 200 or not object_name or not download_url:
            results.append(StepResult("upload", "failed", f"HTTP {upload_status}; object_name_present={bool(object_name)}"))
            raise RuntimeError("upload failed")
        if not object_name.startswith(f"uploads/user_{user_id}/"):
            results.append(StepResult("upload_scope", "failed", "object was not stored under current user prefix"))
            raise RuntimeError("upload scope failed")
        results.append(StepResult("upload", "passed", "small text object uploaded through /api/files/upload"))

        normalized_url = urllib.parse.urljoin(args.base_url.rstrip("/") + "/", download_url.lstrip("/"))
        if "filename=" not in normalized_url:
            separator = "&" if "?" in normalized_url else "?"
            normalized_url = f"{normalized_url}{separator}filename={urllib.parse.quote(filename)}"
        download_status, download_headers, download_body = _request(normalized_url, token=token, timeout=60)
        content_disposition = next((value for key, value in download_headers.items() if key.lower() == "content-disposition"), "")
        content_type = next((value for key, value in download_headers.items() if key.lower() == "content-type"), "")
        if download_status != 200 or download_body != content:
            results.append(StepResult("download", "failed", f"HTTP {download_status}; bytes_match={download_body == content}"))
            raise RuntimeError("download failed")
        if filename not in content_disposition:
            results.append(StepResult("download_headers", "failed", "Content-Disposition filename missing"))
            raise RuntimeError("download headers failed")
        if not content_type.startswith("text/plain"):
            results.append(StepResult("download_headers", "failed", f"unexpected Content-Type {content_type}"))
            raise RuntimeError("download headers failed")
        results.append(StepResult("download", "passed", "download body and browser-facing headers verified"))
    except Exception as exc:
        if not results or results[-1].status != "failed":
            results.append(StepResult("exception", "failed", str(exc)[:500]))
    finally:
        if token and object_name:
            delete_status, _, _ = _request(
                f"{args.base_url.rstrip('/')}/api/files/{urllib.parse.quote(object_name, safe='')}",
                method="DELETE",
                token=token,
                timeout=30,
            )
            results.append(
                StepResult(
                    "cleanup",
                    "passed" if delete_status in {200, 404} else "failed",
                    f"delete HTTP {delete_status}",
                )
            )

    failed = sum(1 for result in results if result.status == "failed")
    payload = {
        "summary": {
            "status": "failed" if failed else "passed",
            "failed": failed,
            "blocked": 0,
            "planned": 0,
            "total": len(results),
            "passwords_printed": False,
        },
        "base_url": args.base_url,
        "results": [asdict(result) for result in results],
    }
    _emit(payload, json_output=args.json)
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
