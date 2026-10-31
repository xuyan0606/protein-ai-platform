"""Configurable agent strategy governance policy."""

from __future__ import annotations

import json
from copy import deepcopy
from functools import lru_cache
from typing import Any

from app.core.config import settings


DEFAULT_AGENT_STRATEGY_POLICY: dict[str, Any] = {
    "version": "2026-08-11",
    "continuation_tokens": [
        "继续", "接着", "上面", "刚才", "前面", "此序列", "该序列", "这个序列",
        "这个蛋白", "该蛋白", "这个酶", "该酶", "这个结构", "该结构",
        "还能", "再", "进一步", "深度分析",
        "continue", "same sequence", "same protein", "above", "previous",
    ],
    "new_task_tokens": [
        "重新开", "新对话", "新的对话", "新任务", "另一个", "另一条", "换一个",
        "换条", "换个", "重新分析", "不要接着", "不是上面", "new task",
        "new conversation", "different sequence", "another sequence", "start over",
    ],
    "followup_reference_tokens": ["它"],
    "followup_synthesis_tokens": [
        "为什么", "原因", "依据", "解释", "展开", "总结", "整理", "表格",
        "哪个", "排序", "风险", "实验方案", "下一步", "怎么做", "复述",
        "why", "explain", "summarize", "table", "rank", "risk", "next step",
    ],
    "execution_tokens": [
        "确认", "执行", "开始", "运行", "重跑", "重新", "跑一下", "调用",
        "execute", "run", "rerun", "start", "call tool",
    ],
    "confirmation_tokens": [
        "是", "确认", "执行", "开始", "开始吧", "继续", "可以", "按上面来",
        "确认执行", "执行上面策略", "按策略执行", "那你开始吧",
        "yes", "ok", "go", "start", "continue", "execute", "confirmed",
    ],
    "max_typed_confirmation_chars": 24,
    "raw_sequence_history_requires_continuation": True,
}


def _list_of_strings(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


def _merge_policy(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    merged = deepcopy(base)
    for key, value in override.items():
        if key.endswith("_tokens"):
            merged[key] = sorted(set(_list_of_strings(merged.get(key)) + _list_of_strings(value)))
        elif key in {"max_typed_confirmation_chars"}:
            try:
                merged[key] = max(1, min(200, int(value)))
            except (TypeError, ValueError):
                continue
        elif key in {"raw_sequence_history_requires_continuation"}:
            merged[key] = bool(value)
        elif key == "version":
            merged[key] = str(value)[:80]
    return merged


@lru_cache(maxsize=1)
def get_agent_strategy_policy() -> dict[str, Any]:
    """Return effective policy and parse status for agent strategy decisions."""
    policy = deepcopy(DEFAULT_AGENT_STRATEGY_POLICY)
    raw = (settings.AGENT_STRATEGY_POLICY_JSON or "").strip()
    parse_error = None
    if raw:
        try:
            override = json.loads(raw)
            if isinstance(override, dict):
                policy = _merge_policy(policy, override)
            else:
                parse_error = "AGENT_STRATEGY_POLICY_JSON must be a JSON object"
        except json.JSONDecodeError as exc:
            parse_error = f"invalid JSON: {exc.msg}"
    return {
        "status": "default" if not raw else ("configured" if parse_error is None else "default_due_to_error"),
        "parse_error": parse_error,
        "policy": policy,
    }


def policy_tokens(name: str) -> tuple[str, ...]:
    snapshot = get_agent_strategy_policy()
    value = snapshot["policy"].get(name)
    return tuple(_list_of_strings(value))
