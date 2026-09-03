"""Separate asynchronous task receipts from usable scientific evidence."""

from __future__ import annotations

import json
from typing import Any


_NON_EVIDENCE_PAYLOAD_STATUSES = {"submitted", "pending", "running", "blocked", "failed", "failure", "canceled", "cancelled", "revoked"}


def _payload(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if not isinstance(value, str):
        return {}
    try:
        parsed = json.loads(value)
    except (TypeError, ValueError):
        return {}
    return parsed if isinstance(parsed, dict) else {}


def classify_task_evidence(tool_results: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    """Partition tool records without promoting queued or unusable results.

    A completed scheduler state is insufficient when the tool payload itself is
    blocked/failed or contains no result.  Such entries remain task receipts or
    rejected terminal records, never evidence inputs for claim/candidate logic.
    """
    evidence: list[dict[str, Any]] = []
    receipts: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    for item in tool_results:
        if not isinstance(item, dict):
            continue
        state = str(item.get("status") or "").lower()
        payload = _payload(item.get("result"))
        payload_state = str(payload.get("status") or "").lower()
        if state in {"submitted", "pending", "running"}:
            receipts.append(item)
        elif state == "completed" and payload_state not in _NON_EVIDENCE_PAYLOAD_STATUSES and bool(payload or item.get("result")):
            evidence.append(item)
        else:
            rejected.append(item)
    return {
        "scientific_evidence": evidence,
        "task_receipts": receipts,
        "rejected_terminal_results": rejected,
    }
