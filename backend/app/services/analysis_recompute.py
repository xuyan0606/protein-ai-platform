"""Explicit, versioned recomputation contracts for asynchronous evidence."""

from __future__ import annotations

import hashlib
import json
import secrets
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.strategy_checkpoint import AnalysisEvidenceSnapshot
from app.services.task_evidence import classify_task_evidence


def build_recompute_decision(
    *,
    analysis_fingerprint: str | None,
    tool_results: list[dict[str, Any]],
    requested: bool,
) -> dict[str, Any]:
    """Decide whether a new analysis version may be calculated.

    This function intentionally never mutates a report.  Callers must create a
    new report revision only after this returns `recompute_ready` and retain the
    returned evidence fingerprint with that revision.
    """
    partition = classify_task_evidence(tool_results)
    receipts = partition["task_receipts"]
    rejected = partition["rejected_terminal_results"]
    evidence = partition["scientific_evidence"]
    task_ids = [
        str(item.get("task_id") or "")
        for item in receipts + rejected + evidence
        if isinstance(item, dict) and item.get("task_id")
    ]
    if not requested:
        return {
            "status": "explicit_recompute_required",
            "report_mutation_allowed": False,
            "reason": "Async task completion never changes an existing analysis/report revision automatically.",
            "pending_task_count": len(receipts),
            "rejected_task_count": len(rejected),
            "task_ids": task_ids,
        }
    if receipts:
        return {
            "status": "tasks_not_terminal",
            "report_mutation_allowed": False,
            "pending_task_count": len(receipts),
            "rejected_task_count": len(rejected),
            "task_ids": task_ids,
        }
    if rejected:
        return {
            "status": "terminal_task_result_rejected",
            "report_mutation_allowed": False,
            "pending_task_count": 0,
            "rejected_task_count": len(rejected),
            "task_ids": task_ids,
        }
    evidence_payload = [
        {
            "tool_name": item.get("tool_name"),
            "status": item.get("status"),
            "result": item.get("result"),
            "task_id": item.get("task_id"),
        }
        for item in evidence
    ]
    encoded = json.dumps(
        {"analysis_fingerprint": analysis_fingerprint, "evidence": evidence_payload},
        sort_keys=True,
        default=str,
        ensure_ascii=True,
    ).encode("utf-8")
    return {
        "status": "recompute_ready",
        "report_mutation_allowed": True,
        "base_analysis_fingerprint": analysis_fingerprint,
        "evidence_snapshot_fingerprint": hashlib.sha256(encoded).hexdigest(),
        "scientific_evidence_count": len(evidence),
        "task_ids": task_ids,
        "required_action": "Create a new analysis/report revision and rerun CandidateDecision with this evidence snapshot.",
    }


async def persist_recompute_snapshot(
    session: AsyncSession,
    *,
    user_id: int,
    conversation_id: int | None,
    decision: dict[str, Any],
    task_snapshot: list[dict[str, Any]],
) -> dict[str, Any]:
    """Persist a new immutable snapshot after the explicit gate succeeds."""
    if decision.get("status") != "recompute_ready":
        raise ValueError("Only recompute_ready decisions may be persisted")
    snapshot_id = f"ars_{secrets.token_urlsafe(18)}"
    row = AnalysisEvidenceSnapshot(
        snapshot_id=snapshot_id,
        user_id=int(user_id),
        conversation_id=conversation_id,
        base_analysis_fingerprint=decision.get("base_analysis_fingerprint"),
        evidence_snapshot_fingerprint=str(decision["evidence_snapshot_fingerprint"]),
        task_ids=[str(item.get("task_id")) for item in task_snapshot if item.get("task_id")],
        evidence_payload=task_snapshot,
    )
    session.add(row)
    await session.flush()
    return {
        "snapshot_id": row.snapshot_id,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "conversation_id": row.conversation_id,
        "evidence_snapshot_fingerprint": row.evidence_snapshot_fingerprint,
    }
