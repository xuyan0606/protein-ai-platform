#!/usr/bin/env python3
"""Live smoke gate for benchmark bundle HEAD and Range support."""

import argparse
import json
import os
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin
from urllib.request import Request, urlopen


def _base_url(value):
    value = (value or "").strip()
    if not value:
        return ""
    return value if value.endswith("/") else value + "/"


def _request(method, url, headers=None, timeout=20):
    request = Request(url, headers=headers or {}, method=method)
    try:
        response = urlopen(request, timeout=timeout)
    except HTTPError as exc:
        body = exc.read(512).decode("utf-8", errors="replace")
        return {
            "ok": False,
            "status": exc.code,
            "headers": dict(exc.headers.items()),
            "body_preview": body,
        }
    except URLError as exc:
        return {"ok": False, "status": None, "headers": {}, "error": str(exc)}
    with response:
        body = response.read()
        return {
            "ok": 200 <= response.status < 300,
            "status": response.status,
            "headers": dict(response.headers.items()),
            "body": body,
        }


def run(args):
    base_url = _base_url(args.base_url or os.getenv("FRONTEND_BASE_URL") or os.getenv("BACKEND_BASE_URL"))
    if not base_url:
        return {
            "summary": {"status": "blocked"},
            "error": "missing base url; pass --base-url or set FRONTEND_BASE_URL/BACKEND_BASE_URL",
        }

    path = "/api/data/benchmarks/{}/bundle/download".format(args.case_id.strip("/"))
    url = urljoin(base_url, path.lstrip("/"))
    head = _request("HEAD", url, timeout=args.timeout)
    range_resp = _request("GET", url, headers={"Range": "bytes=0-31"}, timeout=args.timeout)

    issues = []
    head_headers = {key.lower(): value for key, value in head.get("headers", {}).items()}
    range_headers = {key.lower(): value for key, value in range_resp.get("headers", {}).items()}
    range_body = range_resp.get("body") or b""

    if head.get("status") != 200:
        issues.append("HEAD expected 200 got {}".format(head.get("status")))
    if not str(head_headers.get("content-type", "")).startswith("application/gzip"):
        issues.append("HEAD content-type is not application/gzip")
    if not head_headers.get("content-length"):
        issues.append("HEAD missing content-length")
    if range_resp.get("status") != 206:
        issues.append("Range GET expected 206 got {}".format(range_resp.get("status")))
    if len(range_body) != 32:
        issues.append("Range GET expected 32 bytes got {}".format(len(range_body)))
    if "bytes 0-31/" not in str(range_headers.get("content-range", "")):
        issues.append("Range GET missing expected content-range")

    return {
        "summary": {
            "status": "failed" if issues else "passed",
            "issues": len(issues),
        },
        "case_id": args.case_id,
        "url": url,
        "head": {
            "status": head.get("status"),
            "content_type": head_headers.get("content-type"),
            "content_length": head_headers.get("content-length"),
            "accept_ranges": head_headers.get("accept-ranges"),
        },
        "range": {
            "status": range_resp.get("status"),
            "content_length": range_headers.get("content-length"),
            "content_range": range_headers.get("content-range"),
            "body_bytes": len(range_body),
        },
        "issues": issues,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", help="Live base URL, e.g. http://120.27.108.138")
    parser.add_argument("--case-id", default="venus-15b")
    parser.add_argument("--timeout", type=int, default=20)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    payload = run(args)
    if args.json:
        print(json.dumps(payload, indent=2, ensure_ascii=False))
    else:
        summary = payload.get("summary", {})
        print("summary\t{}\tissues={}".format(summary.get("status"), summary.get("issues", 0)))
        if payload.get("url"):
            print("url\t{}".format(payload["url"]))
        for issue in payload.get("issues", []):
            print("issue\t{}".format(issue))
    return 0 if payload.get("summary", {}).get("status") == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
