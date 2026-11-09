#!/usr/bin/env python3
"""Run bounded live black-box checks against the chat AI endpoint.

Credentials are read from LIVE_AI_EMAIL/LIVE_AI_PASSWORD or from stdin with
--credentials-from-stdin. The script never prints tokens or passwords.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CASES = (
    "missing_thermostability_task",
    "targetless_binder_design",
    "residue_numbering_without_structure",
)


@dataclass
class CaseResult:
    id: str
    status: str
    detail: str
    tools_seen: list[str]
    conversation_id: int | None = None
    duration_seconds: float = 0.0


def _read_credentials_from_stdin() -> tuple[str, str]:
    raw = sys.stdin.read().strip()
    if not raw:
        return "", ""
    payload = json.loads(raw)
    return str(payload.get("email", "")).strip(), str(payload.get("password", "")).strip()


def _load_cases(path: Path, selected_ids: set[str]) -> list[dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    cases = [case for case in payload if case.get("id") in selected_ids]
    missing = selected_ids - {case.get("id") for case in cases}
    if missing:
      raise ValueError(f"case id(s) not found: {', '.join(sorted(missing))}")
    return cases


def _request_json(
    url: str,
    *,
    method: str = "GET",
    token: str | None = None,
    payload: dict[str, Any] | None = None,
    timeout: int = 30,
) -> tuple[int, dict[str, Any]]:
    body = json.dumps(payload or {}, ensure_ascii=False).encode("utf-8") if payload is not None else None
    headers = {"Accept": "application/json"}
    if payload is not None:
        headers["Content-Type"] = "application/json"
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            text = response.read().decode("utf-8", errors="replace")
            return response.status, json.loads(text) if text.strip() else {}
    except urllib.error.HTTPError as exc:
        text = exc.read().decode("utf-8", errors="replace")
        try:
            parsed = json.loads(text) if text.strip() else {}
        except json.JSONDecodeError:
            parsed = {"detail": text[:300]}
        return exc.code, parsed


def _parse_sse_frames(response) -> list[dict[str, Any]]:
    frames: list[dict[str, Any]] = []
    data_lines: list[str] = []
    for raw_line in response:
        line = raw_line.decode("utf-8", errors="replace").rstrip("\n")
        if not line:
            if data_lines:
                data = "\n".join(data_lines)
                try:
                    frames.append(json.loads(data))
                except json.JSONDecodeError:
                    frames.append({"type": "raw", "content": data})
                data_lines = []
            continue
        if line.startswith("data:"):
            data_lines.append(line[5:].lstrip())
    if data_lines:
        data = "\n".join(data_lines)
        try:
            frames.append(json.loads(data))
        except json.JSONDecodeError:
            frames.append({"type": "raw", "content": data})
    return frames


def _stream_chat(
    base_url: str,
    token: str,
    message: str,
    *,
    model: str | None,
    timeout: int,
) -> list[dict[str, Any]]:
    payload: dict[str, Any] = {"message": message, "history": []}
    if model:
        payload["model"] = model
    request = urllib.request.Request(
        f"{base_url.rstrip('/')}/api/chat/stream",
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={
            "Accept": "text/event-stream",
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token}",
        },
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        if response.status != 200:
            raise RuntimeError(f"chat stream returned HTTP {response.status}")
        return _parse_sse_frames(response)


def _tools_from_frames(frames: list[dict[str, Any]]) -> list[str]:
    tools: list[str] = []
    for frame in frames:
        if frame.get("type") != "state":
            continue
        for step in frame.get("plan") or []:
            tool = step.get("tool_name")
            if isinstance(tool, str) and tool not in tools:
                tools.append(tool)
        for step in frame.get("step_results") or []:
            tool = step.get("tool")
            if isinstance(tool, str) and tool not in tools:
                tools.append(tool)
    return tools


def _conversation_id(frames: list[dict[str, Any]]) -> int | None:
    for frame in reversed(frames):
        conv_id = frame.get("conversation_id")
        if isinstance(conv_id, int):
            return conv_id
    return None


def _joined_text(frames: list[dict[str, Any]]) -> str:
    return "".join(str(frame.get("content", "")) for frame in frames if frame.get("type") == "text")


def _case_passes(case: dict[str, Any], frames: list[dict[str, Any]]) -> tuple[bool, str, list[str], int | None]:
    tools = _tools_from_frames(frames)
    raw = json.dumps(frames, ensure_ascii=False)
    conv_id = _conversation_id(frames)
    if not any(frame.get("type") == "done" for frame in frames):
        return False, "stream did not emit done frame", tools, conv_id
    forbidden = [tool for tool in case.get("forbidden_tools", []) if tool in tools or tool in raw]
    if forbidden:
        return False, f"forbidden tool(s) appeared: {', '.join(forbidden)}", tools, conv_id
    missing_required = [tool for tool in case.get("required_tools", []) if tool not in tools]
    if missing_required:
        return False, f"required tool(s) not observed: {', '.join(missing_required)}", tools, conv_id
    if case.get("expect_clarification"):
        text = _joined_text(frames)
        markers = ("不足", "补充", "提供", "序列", "结构", "目标", "clarify", "provide")
        if not any(marker.lower() in text.lower() for marker in markers):
            return False, "expected clarification text was not observed", tools, conv_id
    return True, "chat stream contract passed", tools, conv_id


def _delete_conversation(base_url: str, token: str, conversation_id: int | None) -> None:
    if conversation_id is None:
        return
    _request_json(
        f"{base_url.rstrip('/')}/api/conversations/{conversation_id}",
        method="DELETE",
        token=token,
        timeout=15,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default=os.getenv("FRONTEND_BASE_URL", "http://120.27.108.138"))
    parser.add_argument("--cases", default=",".join(DEFAULT_CASES), help="Comma-separated eval case ids")
    parser.add_argument("--case-file", default=str(PROJECT_ROOT / "backend/tests/enzyme_agent_eval_cases.json"))
    parser.add_argument("--model", default=os.getenv("LIVE_AI_MODEL", ""))
    parser.add_argument("--timeout", type=int, default=int(os.getenv("LIVE_AI_TIMEOUT", "90")))
    parser.add_argument("--json", action="store_true", help="Emit JSON")
    parser.add_argument("--require-live", action="store_true", help="Return non-zero when credentials are missing")
    parser.add_argument("--credentials-from-stdin", action="store_true", help="Read {'email','password'} JSON from stdin")
    args = parser.parse_args()

    email = os.getenv("LIVE_AI_EMAIL", "").strip()
    password = os.getenv("LIVE_AI_PASSWORD", "").strip()
    if args.credentials_from_stdin:
        email, password = _read_credentials_from_stdin()

    if not email or not password:
        payload = {
            "summary": {
                "status": "blocked" if args.require_live else "planned",
                "failed": 0,
                "blocked": 1 if args.require_live else 0,
                "planned": 0 if args.require_live else 1,
                "total": 1,
            },
            "base_url": args.base_url,
            "results": [
                {
                    "id": "live_ai_credentials",
                    "status": "blocked" if args.require_live else "planned",
                    "detail": "set LIVE_AI_EMAIL/LIVE_AI_PASSWORD or pass --credentials-from-stdin; secrets are not printed",
                }
            ],
        }
        if args.json:
            print(json.dumps(payload, indent=2, ensure_ascii=False))
        else:
            item = payload["results"][0]
            print(f"{item['id']}\t{item['status']}\t{item['detail']}")
        return 1 if args.require_live else 0

    status, login_payload = _request_json(
        f"{args.base_url.rstrip('/')}/api/auth/login",
        method="POST",
        payload={"email": email, "password": password},
        timeout=30,
    )
    if status != 200 or not login_payload.get("access_token"):
        payload = {
            "summary": {"status": "failed", "failed": 1, "blocked": 0, "planned": 0, "total": 1},
            "base_url": args.base_url,
            "results": [{"id": "live_ai_login", "status": "failed", "detail": f"login HTTP {status}"}],
        }
        print(json.dumps(payload, indent=2, ensure_ascii=False) if args.json else "live_ai_login\tfailed\tlogin failed")
        return 1

    token = str(login_payload["access_token"])
    selected_ids = {item.strip() for item in args.cases.split(",") if item.strip()}
    cases = _load_cases(Path(args.case_file), selected_ids)
    results: list[CaseResult] = []
    for case in cases:
        started = time.time()
        conv_id: int | None = None
        try:
            frames = _stream_chat(args.base_url, token, str(case["message"]), model=args.model or None, timeout=args.timeout)
            ok, detail, tools, conv_id = _case_passes(case, frames)
            results.append(
                CaseResult(
                    id=str(case["id"]),
                    status="passed" if ok else "failed",
                    detail=detail,
                    tools_seen=tools,
                    conversation_id=conv_id,
                    duration_seconds=round(time.time() - started, 2),
                )
            )
        except Exception as exc:
            results.append(
                CaseResult(
                    id=str(case["id"]),
                    status="failed",
                    detail=str(exc)[:500],
                    tools_seen=[],
                    conversation_id=conv_id,
                    duration_seconds=round(time.time() - started, 2),
                )
            )
        finally:
            _delete_conversation(args.base_url, token, conv_id)

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
    if args.json:
        print(json.dumps(payload, indent=2, ensure_ascii=False))
    else:
        for result in results:
            print(f"{result.id}\t{result.status}\t{result.detail}\ttools={','.join(result.tools_seen) or '-'}")
        print(f"summary\t{payload['summary']['status']}\t{failed} failed / {len(results)} total")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
