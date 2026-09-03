"""Deterministic runtime gate for enzyme-property chat requests.

Unlike the legacy shadow router this module is consumed by the chat path.  It
is intentionally side-effect free so each decision can be regression-tested
and stored as part of a task trace later.
"""

from __future__ import annotations

import re
from typing import Any

from app.services.property_workflow_governance import PropertyWorkflowRouter


_CONTINUATION = re.compile(r"^(?:继续|再说|再说人话|这个什么意思|什么意思|展开|详细说说)[。！？!？\s]*$", re.I)
_TARGET_CHANGE = re.compile(r"(?:改成|改为|换成|目标改|改目标)", re.I)
_SEQUENCE = re.compile(r"(?<![A-Z])[ACDEFGHIKLMNPQRSTVWY]{20,}(?![A-Z])", re.I)
_ACCESSION = re.compile(r"\b(?:[OPQ][0-9][A-Z0-9]{3}[0-9]|[A-NR-Z][0-9][A-Z0-9]{3}[0-9])\b", re.I)
_PDB = re.compile(r"\b[0-9][A-Za-z0-9]{3}\b")
_ENZYME_CONCEPT = re.compile(r"酶|蛋白|活性|稳定性|耐热|pH|催化|比活力|特异性|表达|enzyme|protein", re.I)


def _has_target(text: str) -> bool:
    return PropertyWorkflowRouter.route(text).get("primary_property") is not None


def _history_task_text(history: list[dict[str, Any]] | None) -> str:
    return "\n".join(
        str(item.get("content") or "")
        for item in (history or [])
        if isinstance(item, dict) and item.get("role") == "user"
    )


def _known_inputs(text: str) -> list[str]:
    known: list[str] = []
    if _SEQUENCE.search(text):
        known.append("sequence")
    if _ACCESSION.search(text):
        known.append("accession")
    if _PDB.search(text):
        known.append("structure_reference")
    if "上传" in text or ".pdb" in text.lower():
        known.append("structure")
    return known


def _contract(
    *,
    intent: str,
    session_id: str | int | None,
    route: dict[str, Any],
    intake_status: str,
    final_status: str,
    known_inputs: list[str],
    input_gaps: list[str],
    route_reason: str,
) -> dict[str, Any]:
    return {
        "intent": intent,
        "session_id": str(session_id) if session_id is not None else None,
        "intake_status": intake_status,
        "workflow_id": route.get("workflow_id"),
        "route_reason": route_reason,
        "route_confidence": route.get("route_confidence", "high" if route.get("workflow_id") else "low"),
        "primary_property": route.get("primary_property"),
        "optimization_targets": route.get("optimization_targets", []),
        "preservation_constraints": route.get("preservation_constraints", []),
        "known_inputs": known_inputs,
        "input_gaps": input_gaps,
        "final_status": final_status,
        "trace": [],
        "fallback_trace": [],
    }


def evaluate_enzyme_workflow_runtime(
    message: str,
    history: list[dict[str, Any]] | None = None,
    session_id: str | int | None = None,
) -> dict[str, Any]:
    """Classify a chat turn and return the enforceable P0 task contract."""
    text = str(message or "").strip()
    prior_text = _history_task_text(history)
    route = PropertyWorkflowRouter.route(text)
    known_inputs = _known_inputs(text)
    prior_has_target = _has_target(prior_text)

    if route.get("intent") == "NON_EXECUTION" and _ENZYME_CONCEPT.search(text):
        return _contract(intent="NON_EXECUTION", session_id=session_id, route=route,
                         intake_status="NOT_APPLICABLE", final_status="READY",
                         known_inputs=known_inputs, input_gaps=[],
                         route_reason="conceptual_question")

    if _CONTINUATION.match(text) and prior_has_target:
        prior_route = PropertyWorkflowRouter.route(prior_text)
        return _contract(intent="FOLLOW_UP", session_id=session_id, route=prior_route,
                         intake_status="READY_FOR_ANALYSIS", final_status="READY",
                         known_inputs=known_inputs, input_gaps=[],
                         route_reason="continuation_of_existing_task")

    if _TARGET_CHANGE.search(text) and route.get("workflow_id"):
        return _contract(intent="TARGET_CHANGE", session_id=session_id, route=route,
                         intake_status="READY_FOR_ANALYSIS" if (known_inputs or _known_inputs(prior_text)) else "WAITING_FOR_USER_INPUT",
                         final_status="READY" if (known_inputs or _known_inputs(prior_text)) else "NEEDS_INPUT",
                         known_inputs=known_inputs or _known_inputs(prior_text),
                         input_gaps=[] if (known_inputs or _known_inputs(prior_text)) else ["enzyme_sequence_or_structure_or_accession"],
                         route_reason="explicit_target_change")

    if known_inputs and prior_has_target and not _has_target(text):
        prior_route = PropertyWorkflowRouter.route(prior_text)
        return _contract(intent="INPUT_UPDATE", session_id=session_id, route=prior_route,
                         intake_status="READY_FOR_ANALYSIS", final_status="READY",
                         known_inputs=known_inputs, input_gaps=[],
                         route_reason="new_input_for_existing_task")

    if route.get("workflow_id"):
        if known_inputs:
            return _contract(intent="NEW_TASK", session_id=session_id, route=route,
                             intake_status="READY_FOR_ANALYSIS", final_status="READY",
                             known_inputs=known_inputs, input_gaps=[], route_reason="explicit_property_goal")
        intake_route = dict(route)
        intake_route["workflow_id"] = None
        intake_route["route_confidence"] = "low"
        return _contract(intent="NEW_TASK", session_id=session_id, route=intake_route,
                         intake_status="WAITING_FOR_USER_INPUT", final_status="NEEDS_INPUT",
                         known_inputs=[], input_gaps=["enzyme_sequence_or_structure_or_accession"],
                         route_reason="property_goal_requires_enzyme_identity")

    return _contract(intent="NON_EXECUTION", session_id=session_id, route=route,
                     intake_status="NOT_APPLICABLE", final_status="READY",
                     known_inputs=known_inputs, input_gaps=[], route_reason="outside_enzyme_workflow_scope")
