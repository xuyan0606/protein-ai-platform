"""Separate asynchronous task receipts from usable scientific evidence."""

from __future__ import annotations

import json
from typing import Any

from app.core.tool_outcome import normalize_tool_result

_PENDING = {'submitted', 'pending', 'running', 'waiting', 'submitting', 'retry', 'retrying', 'queued', 'started'}
_UNAVAILABLE = {'blocked', 'failed', 'failure', 'canceled', 'cancelled', 'revoked', 'degraded', 'stale_cache', 'not_available', 'not_run', 'skipped', 'error'}

def parse_tool_payload(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        parsed = value
    elif isinstance(value, str):
        try:
            parsed = json.loads(value)
        except (TypeError, ValueError):
            return {}
    else:
        return {}
    if not isinstance(parsed, dict):
        return {}
    # Scheduler wrappers can finish while the actual tool result is blocked.
    # Read the inner status before treating the record as scientific evidence.
    for _ in range(3):
        inner = parsed.get("result")
        if not isinstance(inner, dict) or "status" not in inner:
            break
        parsed = inner
    return parsed


def result_status(execution: str, result: Any) -> dict[str, str]:
    """Separate a scheduler outcome, data usability and scientific coverage.

    Usable data never automatically means the user's scientific question has
    been answered. Claim/coverage assessment belongs to the report producer.
    """
    state = str(execution or '').lower()
    payload = parse_tool_payload(result)
    if payload.get('tool') and isinstance(payload.get('result'), dict):
        payload = payload['result']
    inner = str(payload.get('status') or '').lower()
    source = payload.get('evidence_source')
    source_status = source.get('status') if isinstance(source, dict) else None
    if state in _UNAVAILABLE:
        quality = 'unavailable'
    elif state in _PENDING or inner in _PENDING:
        quality = 'pending'
    elif inner in _UNAVAILABLE or source_status in {'blocked', 'degraded'}:
        quality = 'unavailable'
    elif state not in {'completed', 'succeeded', 'success'} or not payload:
        quality = 'invalid'
    elif inner == 'partial':
        quality = 'partial'
    elif (inner in {'completed_no_hit', 'no_hit'} or
          (payload.get('results_count') == 0 and payload.get('search_executed') is not False and not payload.get('query_structure'))):
        quality = 'empty'
    else:
        quality = 'usable'
    display = {'usable': 'completed', 'partial': 'partial', 'empty': 'empty',
               'unavailable': 'blocked', 'invalid': 'blocked', 'pending': inner or state}[quality]
    return {
        'execution_status': 'succeeded' if state in {'completed', 'success'} else state,
        'result_status': quality, 'display_status': display,
        'claim_applicability': 'requires_validation' if quality == 'usable' else 'limited' if quality in {'partial', 'empty'} else 'not_applicable',
        'question_coverage': 'pending' if quality == 'pending' else 'unresolved' if quality in {'invalid', 'unavailable'} else 'not_assessed',
    }


def classify_task_evidence(tool_results: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    """Partition tool records without promoting queued or unusable results.

    A completed scheduler state is insufficient when the tool payload itself is
    blocked/failed or contains no result.  Such entries remain task receipts or
    rejected terminal records, never evidence inputs for claim/candidate logic.
    """
    evidence: list[dict[str, Any]] = []
    receipts: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    records: list[dict[str, Any]] = []
    for item in tool_results:
        if not isinstance(item, dict):
            continue
        state = str(item.get("status") or "").lower()
        payload = parse_tool_payload(item.get("result"))
        assessment = result_status(state, payload)
        task_status = state or "unknown"
        outcome = normalize_tool_result(payload) if payload else None
        if assessment["result_status"] == "pending":
            tool_status = "submitted"
        elif state in {"completed", "succeeded", "success"}:
            tool_status = outcome.status if outcome else "failed"
        else:
            tool_status = state or "failed"
        evidence_status = (
            "usable"
            if tool_status == "completed" and outcome is not None and outcome.claim_eligible
            else "receipt"
            if tool_status == "submitted"
            else "rejected"
        )
        source = payload.get("evidence_source")
        source_status = str(source.get("status") or "").lower() if isinstance(source, dict) else ""
        if evidence_status == "usable" and (assessment["result_status"] in {"invalid", "unavailable"} or source_status in {"blocked", "degraded"} or str(payload.get("status") or "").lower() in {"stale_cache"}):
            evidence_status = "rejected"
        records.append({
            "tool_name": item.get("tool_name"),
            "analysis_state": assessment,
            "task_status": task_status,
            "tool_status": tool_status,
            "evidence_status": evidence_status,
            **({"input_id": item.get("input_id")} if item.get("input_id") else {}),
        })
        if evidence_status == "receipt":
            receipts.append(item)
        elif evidence_status == "usable":
            evidence.append(item)
        else:
            rejected.append(item)
    return {
        "scientific_evidence": evidence,
        "task_receipts": receipts,
        "rejected_terminal_results": rejected,
        "records": records,
    }
