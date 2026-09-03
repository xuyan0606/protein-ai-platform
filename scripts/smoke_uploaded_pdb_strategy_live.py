#!/usr/bin/env python3
"""Live black-box regression for uploaded-PDB strategy checkpoints.

The script registers a temporary user, sends the exact HM.pdb-style prompt,
checks the plan-only SSE stream and active checkpoint response for sanitized
uploaded-object metadata, then simulates the confirmation button path.
It never prints access tokens or passwords.
"""

import argparse
import json
import secrets
import time
import urllib.error
import urllib.request
from typing import Any, Dict, List, Optional, Tuple


PROMPT = """提高蛋白比活力

[Attached files:
name: HM.pdb, object_name: uploads/user_2/08b89c1cc55a46aeaa49405d2ce8f3a2.pdb, download_url: /api/files/uploads/user_2/08b89c1cc55a46aeaa49405d2ce8f3a2.pdb/download]"""

LEAK_MARKERS = ("49405", "uploads/user_2", "download_url")
CHECKPOINT_FAILURE_MARKERS = (
    "strategy_signature does not match confirmed_plan",
    "confirmed_plan must be a list",
    "策略检查点校验失败",
)
REPORT_QUALITY_MARKERS = (
    "# 酶蛋白工程分析报告",
    "能否下单",
    "不能直接下单",
    "## 输入与结构证据",
    "## 结构同源与编号映射",
    "## 改造策略及说明",
    "## Objective Module Gate",
    "## 突变位点探索清单（未放行）",
    "0 个可排单候选",
    "本轮未生成位点级突变逻辑",
    "## 探索性验证建议",
)
GENERIC_FALLBACK_MARKERS = (
    "This fallback report is generated",
    "DO NOT MUTATE",
    "## 结论卡片 / 状态摘要",
    "K288E",
    "E275Q",
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
    timeout: int = 30,
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
        f"{base_url.rstrip()}/api/chat/stream",
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


def _content_from_frames(frames: List[Dict[str, Any]]) -> str:
    chunks: List[str] = []
    for frame in frames:
        content = frame.get("content")
        if isinstance(content, str):
            chunks.append(content)
    return "".join(chunks)


def _conversation_id(frames: List[Dict[str, Any]]) -> Optional[int]:
    for frame in reversed(frames):
        conv_id = frame.get("conversation_id")
        if isinstance(conv_id, int):
            return conv_id
    return None


def _contains_any(text: str, markers: Tuple[str, ...]) -> List[str]:
    return [marker for marker in markers if marker in text]


def _missing_any(text: str, markers: Tuple[str, ...]) -> List[str]:
    return [marker for marker in markers if marker not in text]


def _add_check(checks: List[Check], name: str, passed: bool, detail: str = "") -> None:
    checks.append(Check(name=name, passed=passed, detail=detail))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://120.27.108.138")
    parser.add_argument("--timeout", type=int, default=180)
    parser.add_argument("--analysis-depth", choices=("fast", "standard", "deep"), default="standard")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--skip-execute", action="store_true")
    args = parser.parse_args()

    checks: List[Check] = []
    email = f"hm-pdb-smoke-{int(time.time())}-{secrets.token_hex(3)}@example.com"
    password = "Tmp!" + secrets.token_urlsafe(18)
    conv_id: Optional[int] = None

    status, auth_payload, _ = _request_json(
        args.base_url,
        "/api/auth/register",
        method="POST",
        payload={"email": email, "password": password, "name": "HM PDB Smoke"},
        timeout=30,
    )
    token = str(auth_payload.get("access_token") or "")
    _add_check(checks, "temp_user_registered", status == 201 and bool(token), f"http={status}")
    if not token:
        payload = _summary(checks, args.base_url, None, [], {}, 0.0, 0.0)
        print(json.dumps(payload, indent=2, ensure_ascii=False) if args.json else payload["summary"]["status"])
        return 1

    try:
        plan_status, plan_frames, plan_raw, plan_duration = _stream_chat(
            args.base_url,
            token,
            {
                "message": PROMPT,
                "history": [],
                "agent_control": "plan_only",
                "analysis_depth": args.analysis_depth,
            },
            timeout=args.timeout,
        )
        conv_id = _conversation_id(plan_frames)
        tools = _tools_from_frames(plan_frames)
        plan_leaks = _contains_any(plan_raw, LEAK_MARKERS)
        _add_check(checks, "plan_stream_http_200", plan_status == 200, f"http={plan_status}")
        _add_check(checks, "plan_stream_done", any(frame.get("type") == "done" for frame in plan_frames))
        _add_check(checks, "conversation_id_seen", isinstance(conv_id, int), f"conversation_id={conv_id}")
        _add_check(checks, "has_foldseek", "structure_search_foldseek" in tools, ",".join(tools))
        _add_check(checks, "has_sifts", "residue_mapping_sifts" in tools, ",".join(tools))
        if args.analysis_depth == "deep":
            _add_check(checks, "has_blast_deep", "blast_search" in tools, ",".join(tools))
        _add_check(checks, "no_numbering_gate", "residue_numbering_gate" not in tools and "residue_numbering_gate" not in plan_raw)
        _add_check(checks, "no_gromacs", "gromacs_md" not in tools and "gromacs_md" not in plan_raw)
        _add_check(checks, "plan_no_uploaded_metadata_leak", not plan_leaks, ",".join(plan_leaks))
        _add_check(checks, "plan_mentions_hm_name", "HM.pdb" in plan_raw)
        _add_check(checks, "plan_uses_uploaded_mask", "[uploaded-object]" in plan_raw)

        active_payload: Dict[str, Any] = {}
        if conv_id is not None:
            active_status, active_payload, active_raw = _request_json(
                args.base_url,
                f"/api/chat/strategy-checkpoints/active?conversation_id={conv_id}",
                token=token,
                timeout=30,
            )
            active_leaks = _contains_any(active_raw, LEAK_MARKERS)
            _add_check(checks, "active_checkpoint_http_200", active_status == 200, f"http={active_status}")
            _add_check(checks, "active_checkpoint_masked", not active_leaks and "[uploaded-object]" in active_raw, ",".join(active_leaks))
        else:
            _add_check(checks, "active_checkpoint_http_200", False, "missing conversation_id")
            _add_check(checks, "active_checkpoint_masked", False, "missing conversation_id")

        execute_duration = 0.0
        if not args.skip_execute and conv_id is not None:
            execute_status, execute_frames, execute_raw, execute_duration = _stream_chat(
                args.base_url,
                token,
                {
                    "message": "确认执行上述分析策略",
                    "conversation_id": conv_id,
                    "history": [],
                    "agent_control": "execute_confirmed",
                    "confirmed_plan": {"bad": "shape", "length": 1},
                    "strategy_signature": "malformed-client-signature",
                    "task_fingerprint": "malformed-client-task",
                },
                timeout=args.timeout,
            )
            execute_tools = _tools_from_frames(execute_frames)
            execute_text = _content_from_frames(execute_frames) or execute_raw
            checkpoint_failures = _contains_any(execute_raw, CHECKPOINT_FAILURE_MARKERS)
            execute_leaks = _contains_any(execute_raw, LEAK_MARKERS)
            missing_report_markers = _missing_any(execute_text, REPORT_QUALITY_MARKERS)
            generic_fallback_markers = _contains_any(execute_text, GENERIC_FALLBACK_MARKERS)
            _add_check(checks, "execute_stream_http_200", execute_status == 200, f"http={execute_status}")
            _add_check(checks, "execute_no_checkpoint_validation_failure", not checkpoint_failures, ",".join(checkpoint_failures))
            _add_check(checks, "execute_no_gromacs", "gromacs_md" not in execute_tools and "gromacs_md" not in execute_raw, ",".join(execute_tools))
            if args.analysis_depth == "deep":
                _add_check(checks, "execute_has_blast_deep", "blast_search" in execute_tools or "## 序列级专业库检索" in execute_text, ",".join(execute_tools))
            _add_check(checks, "execute_no_numbering_gate", "residue_numbering_gate" not in execute_tools and "residue_numbering_gate" not in execute_raw, ",".join(execute_tools))
            _add_check(checks, "execute_no_uploaded_metadata_leak", not execute_leaks, ",".join(execute_leaks))
            _add_check(checks, "execute_report_has_structure_evidence", not missing_report_markers, ",".join(missing_report_markers))
            _add_check(checks, "execute_report_not_generic_fallback", not generic_fallback_markers, ",".join(generic_fallback_markers))
            max_execute_seconds = 30.0
            _add_check(
                checks,
                "execute_within_expected_budget",
                execute_duration < max_execute_seconds,
                f"{execute_duration:.2f}s <= {max_execute_seconds:.2f}s",
            )

        payload = _summary(checks, args.base_url, conv_id, tools, active_payload, plan_duration, execute_duration)
        print(json.dumps(payload, indent=2, ensure_ascii=False) if args.json else _format_text(payload))
        return 0 if payload["summary"]["status"] == "passed" else 1
    finally:
        if token and conv_id is not None:
            _request_json(
                args.base_url,
                f"/api/conversations/{conv_id}",
                method="DELETE",
                token=token,
                timeout=15,
            )


def _summary(
    checks: List[Check],
    base_url: str,
    conversation_id: Optional[int],
    tools: List[str],
    active_payload: Dict[str, Any],
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
        "active_checkpoint_keys": sorted(active_payload.keys()),
        "checks": [check.__dict__ for check in checks],
    }


def _format_text(payload: Dict[str, Any]) -> str:
    lines = [
        f"summary\t{payload['summary']['status']}\t{payload['summary']['failed']} failed / {payload['summary']['total']} checks",
        f"durations\tplan={payload['durations']['plan_seconds']}s\texecute={payload['durations']['execute_seconds']}s",
        f"tools\t{','.join(payload['tools_seen']) or '-'}",
    ]
    for check in payload["checks"]:
        lines.append(f"{check['name']}\t{'passed' if check['passed'] else 'failed'}\t{check['detail']}")
    return "\n".join(lines)


if __name__ == "__main__":
    raise SystemExit(main())
