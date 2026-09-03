#!/usr/bin/env python3
"""Local-only adapter stub for future platform integration.

This file is not imported by the production platform. It documents the adapter
boundary the backend can later implement inside its ToolRegistry.
"""

from __future__ import annotations

import argparse
import json
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib import request


DEFAULT_ENDPOINT = "http://127.0.0.1:8765/v1/enzyme-design"


@dataclass(frozen=True)
class KWBToolContext:
    session_id: str
    conversation_id: str | None
    user_id: str
    request_turn_id: str

    @property
    def task_id(self) -> str:
        return f"kwb-{self.session_id}-{self.request_turn_id}-{uuid.uuid4().hex[:8]}"


def build_tool_payload(case: dict[str, Any], context: KWBToolContext) -> dict[str, Any]:
    payload = dict(case)
    payload["_kwb_context"] = {
        "session_id": context.session_id,
        "conversation_id": context.conversation_id,
        "user_id": context.user_id,
        "request_turn_id": context.request_turn_id,
        "task_id": context.task_id,
        "local_only": True,
    }
    return payload


def call_kwb_service(payload: dict[str, Any], endpoint: str = DEFAULT_ENDPOINT, timeout_s: float = 30.0) -> dict[str, Any]:
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = request.Request(
        endpoint,
        data=body,
        headers={"Content-Type": "application/json; charset=utf-8"},
        method="POST",
    )
    with request.urlopen(req, timeout=timeout_s) as response:
        return json.loads(response.read().decode("utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser(description="Call local KWB tool adapter stub")
    parser.add_argument("case_file", type=Path)
    parser.add_argument("--endpoint", default=DEFAULT_ENDPOINT)
    parser.add_argument("--session-id", default="local-demo")
    parser.add_argument("--conversation-id")
    parser.add_argument("--user-id", default="local")
    parser.add_argument("--request-turn-id", default="turn-local")
    args = parser.parse_args()

    case = json.loads(args.case_file.read_text(encoding="utf-8"))
    context = KWBToolContext(
        session_id=args.session_id,
        conversation_id=args.conversation_id,
        user_id=args.user_id,
        request_turn_id=args.request_turn_id,
    )
    payload = build_tool_payload(case, context)
    result = call_kwb_service(payload, endpoint=args.endpoint)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
