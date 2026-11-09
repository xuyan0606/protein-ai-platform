"""Canonical terminal outcome semantics shared by tools and orchestration."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal


OutcomeStatus = Literal["completed", "submitted", "blocked", "failed", "timeout"]


@dataclass(frozen=True)
class ToolOutcome:
    status: OutcomeStatus
    terminal: bool
    claim_eligible: bool
    reason: str | None = None


def normalize_tool_exception(exc: BaseException) -> ToolOutcome:
    status: OutcomeStatus = "timeout" if isinstance(exc, TimeoutError) else "failed"
    return ToolOutcome(
        status=status,
        terminal=True,
        claim_eligible=False,
        reason=str(exc) or type(exc).__name__,
    )


def normalize_tool_result(result: Any) -> ToolOutcome:
    if not isinstance(result, dict):
        return ToolOutcome("completed", True, True)

    raw_status = str(result.get("status", "")).strip().lower()
    reason = _reason(result)
    # Optional integrations can terminate without evidence when their
    # credentials are not configured.  This is a terminal workflow outcome,
    # but it must not block independent identity or objective steps.
    if result.get("optional_skip") is True:
        return ToolOutcome("completed", True, False, reason)
    if raw_status == "timeout" or raw_status.startswith("timeout_"):
        return ToolOutcome("timeout", True, False, reason)
    if raw_status.startswith("degraded") and result.get("error_code"):
        return ToolOutcome("failed", True, False, reason)
    if result.get("error") or raw_status in {"failed", "failure", "error", "canceled", "cancelled", "revoked"} or raw_status.startswith("failed_"):
        return ToolOutcome("failed", True, False, reason)
    if result.get("error_code"):
        return ToolOutcome("failed", True, False, reason)
    if raw_status in {"needs_input", "waiting_for_user_input"} or raw_status.startswith(("blocked", "degraded")) or result.get("blocked_reason"):
        return ToolOutcome("blocked", True, False, reason)
    if raw_status in {"submitted", "pending", "running", "queued", "started"}:
        return ToolOutcome("submitted", False, False, reason)
    # A research-only tool really ran and returned data, but its output cannot
    # support a scientific claim.  Report it as completed rather than blocked
    # so downstream traces keep the actual execution outcome, while keeping it
    # out of the usable-evidence set.
    if str(result.get("evidence_level", "")).startswith("research_only"):
        return ToolOutcome("completed", True, False, reason)
    if result.get("claim_eligible") is False:
        return ToolOutcome("blocked", True, False, reason)
    return ToolOutcome(
        "completed",
        True,
        bool(result.get("claim_eligible", True)),
        None,
    )


def _reason(result: dict[str, Any]) -> str | None:
    value = (
        result.get("blocked_reason")
        or result.get("error")
        or result.get("reason")
        or result.get("scientific_boundary")
        or result.get("status")
    )
    return str(value) if value is not None else None
