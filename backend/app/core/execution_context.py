"""Trusted, bounded execution evidence restored from persisted chat events."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
import json

from app.core.tool_outcome import normalize_tool_result
from app.services.task_evidence import parse_tool_payload


@dataclass(frozen=True)
class ExecutionContext:
    objective: str | None
    workflow_id: str | None
    completed_evidence: list[dict[str, str]]

    @classmethod
    def from_done_event(cls, payload: dict[str, Any]) -> "ExecutionContext":
        trace = payload.get("execution_trace", [])
        if not isinstance(trace, list):
            trace = []
        evidence: list[dict[str, str]] = []
        for row in trace:
            if not isinstance(row, dict) or row.get("status") != "completed" or not row.get("tool"):
                continue
            raw_result = row.get("raw_result") or row.get("result_preview")
            if not _is_usable_completed_result(raw_result):
                continue
            preview = row.get("result_preview") or raw_result
            evidence.append({
                "tool": str(row["tool"]),
                "result_preview": str(preview)[:1000],
            })
        return cls(
            objective=_optional_text(payload.get("objective")),
            workflow_id=_optional_text(payload.get("workflow_id")),
            completed_evidence=evidence[-20:],
        )

    @classmethod
    def from_json(cls, raw: str | None) -> "ExecutionContext | None":
        if not raw:
            return None
        try:
            payload = json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            return None
        if not isinstance(payload, dict):
            return None
        return cls.from_done_event(payload)

    def as_prompt_text(self) -> str:
        return "\n".join(
            f"- {row['tool']}: {row['result_preview']}"
            for row in self.completed_evidence
        )


def _optional_text(value: Any) -> str | None:
    return str(value) if value is not None else None


def _is_usable_completed_result(raw_result: Any) -> bool:
    if raw_result is None:
        return False
    if isinstance(raw_result, str):
        if not raw_result.strip():
            return False
        try:
            parsed: Any = json.loads(raw_result)
        except (json.JSONDecodeError, TypeError):
            # Preserve support for tools that return a plain text result.
            return True
    else:
        parsed = raw_result

    if isinstance(parsed, dict):
        payload = parse_tool_payload(parsed)
        if not payload:
            return False
        outcome = normalize_tool_result(payload)
        if outcome.status != "completed" or not outcome.claim_eligible:
            return False
        return _contains_result_data(payload)
    if isinstance(parsed, (list, tuple)):
        return bool(parsed)
    return parsed is not None


def _contains_result_data(value: Any) -> bool:
    if isinstance(value, dict):
        if "result" in value:
            return _contains_result_data(value.get("result"))
        if "raw_result" in value:
            return _contains_result_data(value.get("raw_result"))
        metadata = {
            "status", "reason", "blocked_reason", "error", "error_code",
            "claim_eligible", "duration", "duration_seconds", "duration_ms",
            "task_id", "status_url", "cancel_url", "artifacts_url", "queue",
            "submitted_at", "note", "result_preview", "result_summary",
        }
        return bool(set(value) - metadata)
    if isinstance(value, str):
        if not value.strip():
            return False
        try:
            return _contains_result_data(json.loads(value))
        except (json.JSONDecodeError, TypeError):
            return True
    if isinstance(value, (list, tuple)):
        return bool(value)
    return value is not None
