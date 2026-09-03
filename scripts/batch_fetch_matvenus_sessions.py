#!/usr/bin/env python3
"""Batch fetch Matvenus stream-events and render local review files.

Credentials are loaded once from the local Chrome profile and kept in memory.
The script prints only session IDs, titles, statuses, byte counts, and output
paths. It never prints cookie values or bearer tokens.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

from extract_matvenus_session import extract_messages, render_markdown
from fetch_matvenus_session import (
    DEFAULT_API_BASE,
    DEFAULT_COOKIES_DB,
    fetch_session,
    load_matvenus_cookies,
    write_response,
)


def _slug(value: str, *, limit: int = 48) -> str:
    text = re.sub(r"[^\w\u4e00-\u9fff.-]+", "-", value.strip(), flags=re.UNICODE)
    text = re.sub(r"-+", "-", text).strip("-")
    return (text or "untitled")[:limit]


def _load_items(path: Path) -> list[dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload, dict) and isinstance(payload.get("items"), list):
        return [item for item in payload["items"] if isinstance(item, dict)]
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    raise ValueError("Expected a Matvenus session list JSON with an items array")


def _write_index(output_dir: Path, items: list[dict[str, Any]]) -> None:
    compact = [
        {
            "id": item.get("id"),
            "title": item.get("title"),
            "agent_type": item.get("agent_type"),
            "status": item.get("status"),
            "created_at": item.get("created_at"),
            "completed_at": item.get("completed_at"),
            "is_pinned": item.get("is_pinned"),
        }
        for item in items
    ]
    (output_dir / "index.json").write_text(
        json.dumps(compact, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("session_list", type=Path)
    parser.add_argument("-o", "--output-dir", type=Path, default=Path("matvenus-research"))
    parser.add_argument("--cookies-db", type=Path, default=DEFAULT_COOKIES_DB)
    parser.add_argument("--api-base", default=DEFAULT_API_BASE)
    parser.add_argument("--timeout", type=int, default=30)
    parser.add_argument("--limit", type=int, default=0, help="Fetch only the first N sessions")
    args = parser.parse_args()

    try:
        items = _load_items(args.session_list)
        if args.limit > 0:
            items = items[: args.limit]
        args.output_dir.mkdir(parents=True, exist_ok=True)
        (args.output_dir / "raw").mkdir(exist_ok=True)
        (args.output_dir / "reviews").mkdir(exist_ok=True)
        _write_index(args.output_dir, items)

        cookies = load_matvenus_cookies(args.cookies_db)
        for index, item in enumerate(items, start=1):
            session_id = str(item.get("id") or "").strip()
            title = str(item.get("title") or "untitled").strip()
            if not session_id:
                print(f"skip #{index}: missing session id")
                continue

            stem = f"{index:02d}-{_slug(title)}-{session_id[:8]}"
            raw_path = args.output_dir / "raw" / f"{stem}.stream-events.json"
            review_path = args.output_dir / "reviews" / f"{stem}.review.md"

            status, content_type, body = fetch_session(
                session_id=session_id,
                api_base=args.api_base,
                path_template="/session/{session_id}/stream-events",
                cookies=cookies,
                timeout=args.timeout,
            )
            kind = write_response(raw_path, body, content_type)
            if 200 <= status < 300 and kind.startswith("json"):
                payload = json.loads(raw_path.read_text(encoding="utf-8"))
                messages = extract_messages(payload)
                review_path.write_text(
                    render_markdown(raw_path, payload, messages),
                    encoding="utf-8",
                )
                print(
                    f"{index:02d} status={status} messages={len(messages)} "
                    f"bytes={len(body)} title={title} review={review_path}"
                )
            else:
                print(
                    f"{index:02d} status={status} kind={kind} bytes={len(body)} "
                    f"title={title} raw={raw_path}"
                )
        return 0
    except Exception as exc:
        print(f"failed: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
