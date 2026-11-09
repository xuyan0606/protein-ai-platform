#!/usr/bin/env python3
"""Extract readable Markdown from an exported Matvenus chat session JSON.

The script is intentionally offline-only. Export the session JSON from a
logged-in browser, then run this script against that file. It does not request
cookies, tokens, or remote APIs.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


SENSITIVE_KEY_RE = re.compile(r"(token|cookie|authorization|password|secret|api[_-]?key)", re.I)
MESSAGE_KEYS = ("completedMessages", "completed_messages", "messages", "items")


@dataclass
class ExtractedMessage:
    index: int
    role: str
    label: str
    text: str
    step_titles: list[str]
    tool_calls: list[str]


def _redact(value: Any) -> Any:
    if isinstance(value, dict):
        result: dict[str, Any] = {}
        for key, item in value.items():
            if SENSITIVE_KEY_RE.search(str(key)):
                result[str(key)] = "[REDACTED]"
            else:
                result[str(key)] = _redact(item)
        return result
    if isinstance(value, list):
        return [_redact(item) for item in value]
    return value


def _compact_json(value: Any, *, limit: int = 1200) -> str:
    rendered = json.dumps(_redact(value), ensure_ascii=False, indent=2, default=str)
    if len(rendered) <= limit:
        return rendered
    return rendered[:limit].rstrip() + "\n..."


def _message_role(message: dict[str, Any]) -> str:
    raw = str(
        message.get("sender")
        or message.get("role")
        or message.get("author")
        or message.get("agent_type")
        or ""
    ).lower()
    if any(marker in raw for marker in ("human", "user", "client")):
        return "Human"
    if any(marker in raw for marker in ("agent", "assistant", "ai", "bot")):
        return "Agent"
    return "Message"


def _event_role(data: dict[str, Any]) -> str:
    raw = str(data.get("role") or data.get("sender") or "").lower()
    if raw in {"user", "human"}:
        return "Human"
    if raw in {"assistant", "agent", "ai"}:
        return "Agent"
    return _message_role(data)


def _message_label(message: dict[str, Any], role: str) -> str:
    parts = [role]
    node = message.get("node_name") or message.get("model") or message.get("agent_type")
    if node:
        parts.append(str(node))
    msg_id = message.get("msg_id") or message.get("id")
    if msg_id:
        parts.append(str(msg_id)[:12])
    return " / ".join(parts)


def _span_text(span: Any, *, step_titles: list[str], tool_calls: list[str], depth: int = 0) -> str:
    if isinstance(span, str):
        return span
    if not isinstance(span, dict):
        return ""

    span_type = str(span.get("type") or "").lower()
    chunks: list[str] = []

    if span_type in {"text", "markdown"}:
        content = span.get("content") or span.get("text") or ""
        if content:
            chunks.append(str(content))
    elif span_type == "report":
        content = span.get("content") or span.get("text") or ""
        if content:
            chunks.append(str(content))
    elif span_type == "step":
        title = str(span.get("title") or span.get("name") or "Step").strip()
        if title:
            step_titles.append(title)
            heading = "#" * min(6, 4 + depth)
            chunks.append(f"{heading} {title}")
        content = span.get("content") or span.get("text")
        if content:
            chunks.append(str(content))
    elif span_type in {"tool_call", "tool", "tool_result"}:
        name = str(span.get("name") or span.get("tool_name") or span.get("title") or "tool_call")
        tool_calls.append(name)
        details = {
            key: span.get(key)
            for key in ("name", "tool_name", "title", "status", "args", "arguments", "input", "output", "result")
            if key in span
        }
        chunks.append(f"Tool call: `{name}`\n\n```json\n{_compact_json(details)}\n```")
    else:
        for key in ("content", "text", "title"):
            if span.get(key):
                chunks.append(str(span[key]))

    for child_key in ("spans", "children", "items", "steps"):
        children = span.get(child_key)
        if isinstance(children, list):
            for child in children:
                child_text = _span_text(child, step_titles=step_titles, tool_calls=tool_calls, depth=depth + 1)
                if child_text:
                    chunks.append(child_text)

    return "\n\n".join(chunk.strip() for chunk in chunks if chunk and str(chunk).strip())


def _content_item_text(item: Any, *, tool_calls: list[str]) -> str:
    if isinstance(item, str):
        return item
    if not isinstance(item, dict):
        return ""

    item_type = str(item.get("type") or "").lower()
    if item_type in {"text", "report", "markdown"}:
        return str(item.get("text") or item.get("content") or "").strip()
    if item_type == "reasoning":
        text = str(item.get("reasoning") or item.get("text") or "").strip()
        return f"**Reasoning:** {text}" if text else ""
    if item_type in {"tool_call", "tool_call_chunk", "tool_result"}:
        name = str(item.get("name") or item.get("tool_name") or "tool_call")
        tool_calls.append(name)
        details = {
            key: item.get(key)
            for key in ("name", "id", "args", "arguments", "input", "output", "result")
            if key in item
        }
        return f"Tool call: `{name}`\n\n```json\n{_compact_json(details)}\n```"
    if item_type == "file":
        url = item.get("url") or item.get("name") or item.get("file_name")
        mime = item.get("mime_type") or item.get("mime")
        parts = ["File attachment"]
        if mime:
            parts.append(str(mime))
        if url:
            parts.append(str(url))
        return " - ".join(parts)

    for key in ("text", "content", "reasoning"):
        value = item.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def _event_content_text(data: dict[str, Any], *, tool_calls: list[str]) -> str:
    content = data.get("content")
    chunks: list[str] = []
    if isinstance(content, list):
        for item in content:
            text = _content_item_text(item, tool_calls=tool_calls)
            if text:
                chunks.append(text)
    else:
        text = _content_item_text(content, tool_calls=tool_calls)
        if text:
            chunks.append(text)

    if data.get("tool_name"):
        name = str(data.get("tool_name"))
        tool_calls.append(name)
        details = {
            key: data.get(key)
            for key in (
                "tool_name",
                "tool_name_desc",
                "tool_type",
                "tool_call_id",
                "tool_args",
                "content",
            )
            if key in data
        }
        chunks.append(f"Tool call: `{name}`\n\n```json\n{_compact_json(details)}\n```")

    return "\n\n".join(chunk.strip() for chunk in chunks if chunk.strip()).strip()


def _extract_stream_events(payload: dict[str, Any]) -> list[ExtractedMessage]:
    events = payload.get("stream_events")
    if not isinstance(events, list):
        return []

    messages: list[ExtractedMessage] = []
    current_by_msg_id: dict[str, ExtractedMessage] = {}

    for event in events:
        if not isinstance(event, dict) or not isinstance(event.get("data"), dict):
            continue
        data = event["data"]
        msg_id = str(data.get("msg_id") or f"event-{len(messages) + 1}")
        role = _event_role(data)
        node = data.get("node_name")
        step_id = data.get("step_id")
        label_parts = [role]
        if node:
            label_parts.append(str(node))
        if step_id:
            label_parts.append(f"step:{step_id}")
        label_parts.append(msg_id[:12])

        existing = current_by_msg_id.get(msg_id)
        if existing is None:
            existing = ExtractedMessage(
                index=len(messages) + 1,
                role=role,
                label=" / ".join(label_parts),
                text="",
                step_titles=[],
                tool_calls=[],
            )
            current_by_msg_id[msg_id] = existing
            messages.append(existing)

        text = _event_content_text(data, tool_calls=existing.tool_calls)
        if text:
            existing.text = f"{existing.text}\n\n{text}".strip()
        if node:
            existing.step_titles.append(str(node))
        if step_id:
            existing.step_titles.append(str(step_id))

    return messages


def _find_message_list(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, dict):
        for key in MESSAGE_KEYS:
            messages = payload.get(key)
            if _looks_like_messages(messages):
                return [item for item in messages if isinstance(item, dict)]
        for value in payload.values():
            found = _find_message_list(value)
            if found:
                return found
    if isinstance(payload, list) and _looks_like_messages(payload):
        return [item for item in payload if isinstance(item, dict)]
    return []


def _looks_like_messages(value: Any) -> bool:
    if not isinstance(value, list) or not value:
        return False
    dict_items = [item for item in value if isinstance(item, dict)]
    if not dict_items:
        return False
    sample = dict_items[:5]
    return any(
        any(key in item for key in ("spans", "content", "text", "sender", "role", "msg_id"))
        for item in sample
    )


def extract_messages(payload: Any) -> list[ExtractedMessage]:
    if isinstance(payload, dict) and isinstance(payload.get("stream_events"), list):
        return _extract_stream_events(payload)

    messages = _find_message_list(payload)
    extracted: list[ExtractedMessage] = []
    for index, message in enumerate(messages, start=1):
        role = _message_role(message)
        step_titles: list[str] = []
        tool_calls: list[str] = []
        chunks: list[str] = []

        spans = message.get("spans")
        if isinstance(spans, list):
            for span in spans:
                text = _span_text(span, step_titles=step_titles, tool_calls=tool_calls)
                if text:
                    chunks.append(text)

        for key in ("content", "text", "message"):
            value = message.get(key)
            if isinstance(value, str) and value.strip():
                chunks.append(value)

        text = "\n\n".join(chunk.strip() for chunk in chunks if chunk.strip()).strip()
        if not text and message:
            text = f"```json\n{_compact_json(message)}\n```"

        extracted.append(
            ExtractedMessage(
                index=index,
                role=role,
                label=_message_label(message, role),
                text=text,
                step_titles=step_titles,
                tool_calls=tool_calls,
            )
        )
    return extracted


def render_markdown(source: Path, payload: Any, messages: list[ExtractedMessage]) -> str:
    session_id = (
        payload.get("id")
        or payload.get("session_id")
        or payload.get("sessionId")
        if isinstance(payload, dict)
        else None
    )
    agent_steps: list[str] = []
    tool_calls: list[str] = []
    for message in messages:
        if message.role == "Agent":
            agent_steps.extend(message.step_titles)
        tool_calls.extend(message.tool_calls)

    lines = [
        "# Matvenus Session Review",
        "",
        f"- Source file: `{source}`",
        f"- Session ID: `{session_id or 'unknown'}`",
        f"- Messages: `{len(messages)}`",
        "",
        "## Reusable Analysis Trace",
        "",
    ]
    if agent_steps:
        for idx, title in enumerate(dict.fromkeys(agent_steps), start=1):
            lines.append(f"{idx}. {title}")
    else:
        lines.append("- No explicit step spans found; use the conversation section below.")
    if tool_calls:
        lines.extend(["", "## Tool Calls", ""])
        for name in dict.fromkeys(tool_calls):
            lines.append(f"- `{name}`")

    lines.extend(["", "## Conversation", ""])
    for message in messages:
        lines.extend([
            f"### {message.index}. {message.label}",
            "",
            message.text or "_empty message_",
            "",
        ])
    return "\n".join(lines).rstrip() + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("json_file", type=Path, help="Exported Matvenus session JSON file")
    parser.add_argument("-o", "--output", type=Path, help="Write Markdown review to this path")
    parser.add_argument("--json", action="store_true", help="Emit extracted messages as JSON")
    args = parser.parse_args()

    try:
        payload = json.loads(args.json_file.read_text(encoding="utf-8"))
    except FileNotFoundError:
        print(f"File not found: {args.json_file}", file=sys.stderr)
        return 2
    except json.JSONDecodeError as exc:
        print(f"Invalid JSON: {exc}", file=sys.stderr)
        return 2

    messages = extract_messages(payload)
    if args.json:
        print(json.dumps([asdict(message) for message in messages], ensure_ascii=False, indent=2))
        return 0

    markdown = render_markdown(args.json_file, payload, messages)
    if args.output:
        args.output.write_text(markdown, encoding="utf-8")
    else:
        print(markdown, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
