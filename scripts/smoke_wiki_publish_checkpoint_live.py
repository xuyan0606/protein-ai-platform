#!/usr/bin/env python3
"""Live smoke: publishing to Wiki must not break strategy checkpoint execution.

The script registers a temporary user, creates a plan-only strategy checkpoint,
lists real Wiki collections, publishes a temporary Markdown document to the
first collection, then confirms the original strategy with malformed client
payload. The server-side active checkpoint must remain authoritative.

Secrets, tokens, and passwords are never printed.
"""

import argparse
import json
import secrets
import time
import urllib.error
import urllib.request
from typing import Any, Dict, List, Optional, Tuple


TASK = "请制定提高这个酶比活力的分析策略，序列：MKTAYIAKQRQISFVKSHFSRQLEERLGLIEVQANNSTPAY"
CHECKPOINT_FAILURE_MARKERS = (
    "strategy_signature does not match confirmed_plan",
    "confirmed_plan must be a list",
    "策略检查点校验失败",
)


class Check:
    def __init__(self, name: str, passed: bool, detail: str = "") -> None:
        self.name = name
        self.passed = passed
        self.detail = detail


def _request_json(
    base_url: str,
    path: str,
    *,
    method: str = "GET",
    token: Optional[str] = None,
    payload: Optional[Dict[str, Any]] = None,
    timeout: int = 60,
) -> Tuple[int, Dict[str, Any], str]:
    body = json.dumps(payload or {}, ensure_ascii=False).encode("utf-8") if payload is not None else None
    headers = {"Accept": "application/json"}
    if payload is not None:
        headers["Content-Type"] = "application/json"
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = urllib.request.Request(
        f"{base_url.rstrip('/')}{path}",
        data=body,
        headers=headers,
        method=method,
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read().decode("utf-8", errors="replace")
            parsed = json.loads(raw) if raw.strip() else {}
            return response.status, parsed, raw
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        try:
            parsed = json.loads(raw) if raw.strip() else {}
        except json.JSONDecodeError:
            parsed = {"detail": raw[:300]}
        return exc.code, parsed, raw


def _parse_sse(raw: str) -> List[Dict[str, Any]]:
    frames: List[Dict[str, Any]] = []
    data_lines: List[str] = []
    for line in raw.splitlines():
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
    payload: Dict[str, Any],
    *,
    timeout: int,
) -> Tuple[int, List[Dict[str, Any]], str, float]:
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
    started = time.time()
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read().decode("utf-8", errors="replace")
            return response.status, _parse_sse(raw), raw, time.time() - started
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        return exc.code, _parse_sse(raw), raw, time.time() - started


def _latest_plan_state(frames: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    for frame in reversed(frames):
        if frame.get("type") == "state" and isinstance(frame.get("plan"), list) and frame["plan"]:
            return frame
    return None


def _conversation_id(frames: List[Dict[str, Any]]) -> Optional[int]:
    for frame in reversed(frames):
        conv_id = frame.get("conversation_id")
        if isinstance(conv_id, int):
            return conv_id
    return None


def _tools_from_frames(frames: List[Dict[str, Any]]) -> List[str]:
    tools: List[str] = []
    for frame in frames:
        if frame.get("type") != "state":
            continue
        for step in frame.get("plan") or []:
            tool = step.get("tool_name")
            if isinstance(tool, str) and tool not in tools:
                tools.append(tool)
        for result in frame.get("step_results") or []:
            tool = result.get("tool")
            if isinstance(tool, str) and tool not in tools:
                tools.append(tool)
    return tools


def _add_check(checks: List[Check], name: str, passed: bool, detail: str = "") -> None:
    checks.append(Check(name=name, passed=passed, detail=detail))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://120.27.108.138")
    parser.add_argument("--timeout", type=int, default=180)
    parser.add_argument("--max-execute-seconds", type=float, default=45.0)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    checks: List[Check] = []
    email = f"wiki-checkpoint-smoke-{int(time.time())}-{secrets.token_hex(3)}@example.com"
    password = "Tmp!" + secrets.token_urlsafe(18)
    conv_id: Optional[int] = None

    status, auth_payload, _ = _request_json(
        args.base_url,
        "/api/auth/register",
        method="POST",
        payload={"email": email, "password": password, "name": "Wiki Checkpoint Smoke"},
        timeout=30,
    )
    token = str(auth_payload.get("access_token") or "")
    _add_check(checks, "temp_user_registered", status == 201 and bool(token), f"http={status}")
    if not token:
        return _finish(args, checks, None, [], {}, 0.0, 0.0)

    try:
        plan_status, plan_frames, _plan_raw, plan_duration = _stream_chat(
            args.base_url,
            token,
            {
                "message": TASK,
                "history": [],
                "agent_control": "plan_only",
                "analysis_depth": "fast",
            },
            timeout=args.timeout,
        )
        conv_id = _conversation_id(plan_frames)
        plan_state = _latest_plan_state(plan_frames)
        tools = _tools_from_frames(plan_frames)
        _add_check(checks, "plan_stream_http_200", plan_status == 200, f"http={plan_status}")
        _add_check(checks, "conversation_id_seen", isinstance(conv_id, int), f"conversation_id={conv_id}")
        _add_check(checks, "plan_waiting_for_confirmation", plan_state and plan_state.get("waiting_for") == "plan_confirmation")
        _add_check(checks, "plan_has_signature", bool(plan_state and plan_state.get("strategy_signature")))

        active_before: Dict[str, Any] = {}
        if conv_id is not None:
            active_status, active_before, _ = _request_json(
                args.base_url,
                f"/api/chat/strategy-checkpoints/active?conversation_id={conv_id}",
                token=token,
                timeout=30,
            )
            _add_check(checks, "active_before_publish_http_200", active_status == 200, f"http={active_status}")
            _add_check(checks, "active_before_publish_exists", bool(active_before.get("checkpoint")))

        collections_status, collections, _ = _request_json(
            args.base_url,
            "/api/wiki/collections",
            token=token,
            timeout=60,
        )
        collection_id = ""
        if isinstance(collections, list) and collections:
            collection_id = str(collections[0].get("id") or "")
        _add_check(checks, "wiki_collections_http_200", collections_status == 200, f"http={collections_status}")
        _add_check(checks, "wiki_collection_available", bool(collection_id), f"count={len(collections) if isinstance(collections, list) else 'n/a'}")

        publish_payload: Dict[str, Any] = {}
        if collection_id:
            publish_status, publish_payload, _ = _request_json(
                args.base_url,
                "/api/wiki/publish",
                method="POST",
                token=token,
                payload={
                    "title": f"checkpoint smoke {int(time.time())}",
                    "content": "# Checkpoint Smoke\n\nTemporary live publish verification.",
                    "conversation_id": conv_id,
                    "collection_id": collection_id,
                },
                timeout=90,
            )
            _add_check(checks, "wiki_publish_http_200", publish_status == 200, f"http={publish_status}")
            _add_check(checks, "wiki_publish_outline_doc_created", bool(publish_payload.get("outline_doc_id")))
            _add_check(checks, "wiki_publish_file_record_created", bool(publish_payload.get("file_id")))

        active_after_publish: Dict[str, Any] = {}
        if conv_id is not None:
            active_status, active_after_publish, _ = _request_json(
                args.base_url,
                f"/api/chat/strategy-checkpoints/active?conversation_id={conv_id}",
                token=token,
                timeout=30,
            )
            _add_check(checks, "active_after_publish_http_200", active_status == 200, f"http={active_status}")
            before_sig = (active_before.get("checkpoint") or {}).get("strategy_signature")
            after_sig = (active_after_publish.get("checkpoint") or {}).get("strategy_signature")
            _add_check(checks, "active_checkpoint_survived_publish", bool(before_sig and before_sig == after_sig), str(after_sig or "missing"))

        execute_duration = 0.0
        if conv_id is not None:
            execute_status, execute_frames, execute_raw, execute_duration = _stream_chat(
                args.base_url,
                token,
                {
                    "message": "确认执行上述分析策略",
                    "conversation_id": conv_id,
                    "history": [],
                    "agent_control": "execute_confirmed",
                    "confirmed_plan": {"bad": "shape", "length": 1},
                    "strategy_signature": "stale-after-wiki-publish",
                    "task_fingerprint": "stale-after-wiki-publish",
                },
                timeout=args.timeout,
            )
            execute_tools = _tools_from_frames(execute_frames)
            checkpoint_failures = [marker for marker in CHECKPOINT_FAILURE_MARKERS if marker in execute_raw]
            _add_check(checks, "execute_after_publish_http_200", execute_status == 200, f"http={execute_status}")
            _add_check(checks, "execute_after_publish_stage_seen", any(frame.get("stage") == "execute" for frame in execute_frames))
            _add_check(checks, "execute_after_publish_no_checkpoint_failure", not checkpoint_failures, ",".join(checkpoint_failures))
            _add_check(checks, "execute_after_publish_used_tools", bool(execute_tools), ",".join(execute_tools))
            _add_check(
                checks,
                "execute_after_publish_fast_enough",
                execute_duration <= args.max_execute_seconds,
                f"{execute_duration:.2f}s <= {args.max_execute_seconds:.2f}s",
            )

        payload = _summary(checks, args.base_url, conv_id, tools, publish_payload, plan_duration, execute_duration)
        print(json.dumps(payload, indent=2, ensure_ascii=False) if args.json else _format_text(payload))
        return 0 if payload["summary"]["status"] == "passed" else 1
    finally:
        if token and conv_id is not None:
            _request_json(args.base_url, f"/api/conversations/{conv_id}", method="DELETE", token=token, timeout=15)


def _summary(
    checks: List[Check],
    base_url: str,
    conversation_id: Optional[int],
    tools: List[str],
    publish_payload: Dict[str, Any],
    plan_duration: float,
    execute_duration: float,
) -> Dict[str, Any]:
    failed = [check for check in checks if not check.passed]
    return {
        "summary": {
            "status": "failed" if failed else "passed",
            "failed": len(failed),
            "total": len(checks),
            "tokens_printed": False,
            "passwords_printed": False,
        },
        "base_url": base_url,
        "conversation_id": conversation_id,
        "tools_seen": tools,
        "durations": {
            "plan_seconds": round(plan_duration, 2),
            "execute_seconds": round(execute_duration, 2),
        },
        "wiki_publish": {
            "file_created": bool(publish_payload.get("file_id")),
            "outline_doc_created": bool(publish_payload.get("outline_doc_id")),
            "wiki_url_present": bool(publish_payload.get("wiki_url")),
        },
        "checks": [check.__dict__ for check in checks],
    }


def _format_text(payload: Dict[str, Any]) -> str:
    lines = [
        f"summary\t{payload['summary']['status']}\t{payload['summary']['failed']} failed / {payload['summary']['total']} checks",
        f"durations\tplan={payload['durations']['plan_seconds']}s\texecute={payload['durations']['execute_seconds']}s",
        f"wiki_publish\t{payload['wiki_publish']}",
        f"tools\t{','.join(payload['tools_seen']) or '-'}",
    ]
    for check in payload["checks"]:
        lines.append(f"{check['name']}\t{'passed' if check['passed'] else 'failed'}\t{check['detail']}")
    return "\n".join(lines)


def _finish(
    args: argparse.Namespace,
    checks: List[Check],
    conversation_id: Optional[int],
    tools: List[str],
    publish_payload: Dict[str, Any],
    plan_duration: float,
    execute_duration: float,
) -> int:
    payload = _summary(checks, args.base_url, conversation_id, tools, publish_payload, plan_duration, execute_duration)
    print(json.dumps(payload, indent=2, ensure_ascii=False) if args.json else _format_text(payload))
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
