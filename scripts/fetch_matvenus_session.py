#!/usr/bin/env python3
"""Fetch a Matvenus session JSON using the local Chrome login state.

This helper deliberately keeps credentials in memory only. It prints status
metadata, but never prints decrypted cookie values, bearer tokens, or keychain
secrets.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request
from dataclasses import dataclass
from http.cookiejar import CookieJar
from pathlib import Path
from typing import Any


DEFAULT_COOKIES_DB = (
    Path.home() / "Library/Application Support/Google/Chrome/Default/Cookies"
)
DEFAULT_API_BASE = "https://matvenus.com/research-system/api"


@dataclass(frozen=True)
class CookieValue:
    host_key: str
    name: str
    value: str


def _chrome_safe_storage_password() -> bytes:
    result = subprocess.run(
        ["security", "find-generic-password", "-w", "-s", "Chrome Safe Storage"],
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=False,
    )
    if result.returncode != 0 or not result.stdout.strip():
        raise RuntimeError(
            "Cannot read Chrome Safe Storage from macOS Keychain. "
            "Unlock Chrome login state or export the Matvenus session JSON manually."
        )
    return result.stdout.rstrip(b"\n")


def _derive_chrome_key(password: bytes) -> bytes:
    return hashlib.pbkdf2_hmac("sha1", password, b"saltysalt", 1003, dklen=16)


def _decrypt_chrome_v10(encrypted_value: bytes, key: bytes, host_key: str) -> str:
    if not encrypted_value:
        return ""
    if not encrypted_value.startswith(b"v10"):
        raise RuntimeError("Unsupported Chrome cookie encryption prefix")

    result = subprocess.run(
        [
            "openssl",
            "enc",
            "-aes-128-cbc",
            "-d",
            "-K",
            key.hex(),
            "-iv",
            (b" " * 16).hex(),
            "-nopad",
        ],
        input=encrypted_value[3:],
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if result.returncode != 0:
        raise RuntimeError("OpenSSL failed to decrypt a Chrome cookie")
    padded = result.stdout
    if not padded:
        return ""
    pad_len = padded[-1]
    if pad_len < 1 or pad_len > 16:
        raise RuntimeError("Invalid Chrome cookie padding")
    plaintext = padded[:-pad_len]
    host_digest = hashlib.sha256(host_key.encode("utf-8")).digest()
    if plaintext.startswith(host_digest):
        plaintext = plaintext[len(host_digest) :]
    return plaintext.decode("utf-8")


def _copy_cookie_db(source: Path) -> Path:
    if not source.exists():
        raise FileNotFoundError(f"Chrome Cookies DB not found: {source}")
    temp_dir = Path(tempfile.mkdtemp(prefix="matvenus-cookies-"))
    target = temp_dir / "Cookies"
    shutil.copy2(source, target)
    return target


def load_matvenus_cookies(cookies_db: Path) -> dict[str, CookieValue]:
    copied_db = _copy_cookie_db(cookies_db)
    key = _derive_chrome_key(_chrome_safe_storage_password())

    rows: list[tuple[str, str, str, bytes]] = []
    with sqlite3.connect(copied_db) as conn:
        rows = conn.execute(
            """
            select host_key, name, value, encrypted_value
            from cookies
            where host_key like '%matvenus.com%'
            order by host_key, name
            """
        ).fetchall()

    cookies: dict[str, CookieValue] = {}
    for host_key, name, value, encrypted_value in rows:
        decoded = value or _decrypt_chrome_v10(encrypted_value, key, host_key)
        if decoded:
            cookies[name] = CookieValue(host_key=host_key, name=name, value=decoded)
    return cookies


def _cookie_header(cookies: dict[str, CookieValue]) -> str:
    return "; ".join(f"{cookie.name}={cookie.value}" for cookie in cookies.values())


def fetch_session(
    *,
    session_id: str,
    api_base: str,
    path_template: str,
    cookies: dict[str, CookieValue],
    timeout: int,
) -> tuple[int, str, bytes]:
    access_token = cookies.get("access_token")
    if access_token is None:
        raise RuntimeError("Matvenus access_token cookie was not found")

    path = path_template.format(session_id=session_id).lstrip("/")
    url = f"{api_base.rstrip('/')}/{path}"
    headers = {
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        "Authorization": f"Bearer {access_token.value}",
        "Cookie": _cookie_header(cookies),
        "Referer": f"https://matvenus.com/chat/agent/{session_id}",
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126 Safari/537.36"
        ),
    }
    request = urllib.request.Request(url, headers=headers, method="GET")
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.status, response.headers.get("content-type", ""), response.read()
    except urllib.error.HTTPError as exc:
        return exc.code, exc.headers.get("content-type", ""), exc.read()


def write_response(output: Path, body: bytes, content_type: str) -> str:
    text = body.decode("utf-8", errors="replace")
    try:
        payload: Any = json.loads(text)
    except json.JSONDecodeError:
        output.write_text(text, encoding="utf-8")
        return "text"

    output.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    if "application/json" not in content_type.lower():
        return "json-nonstandard-content-type"
    return "json"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("session_id", help="Matvenus session UUID")
    parser.add_argument("-o", "--output", type=Path, required=True)
    parser.add_argument("--cookies-db", type=Path, default=DEFAULT_COOKIES_DB)
    parser.add_argument("--api-base", default=DEFAULT_API_BASE)
    parser.add_argument("--path-template", default="/session/{session_id}")
    parser.add_argument("--timeout", type=int, default=30)
    args = parser.parse_args()

    try:
        cookies = load_matvenus_cookies(args.cookies_db)
        status, content_type, body = fetch_session(
            session_id=args.session_id,
            api_base=args.api_base,
            path_template=args.path_template,
            cookies=cookies,
            timeout=args.timeout,
        )
        kind = write_response(args.output, body, content_type)
    except Exception as exc:
        print(f"failed: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1

    cookie_names = ", ".join(sorted(cookies))
    print(
        f"status={status} kind={kind} bytes={len(body)} "
        f"cookies=[{cookie_names}] output={args.output}"
    )
    return 0 if 200 <= status < 300 else 2


if __name__ == "__main__":
    raise SystemExit(main())
