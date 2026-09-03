#!/usr/bin/env python3
"""Local adapter that combines the workflow gate with the rule MVP.

This adapter is deliberately not imported by the production platform. It
models the boundary GPT-5.6 would call: plan first, execute KWB only when the
current structure and numbering gates allow it.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import Any, Iterable


AI_ROOT = Path(__file__).resolve().parents[1]
if str(AI_ROOT) not in sys.path:
    sys.path.insert(0, str(AI_ROOT))

from platform_integration.structure_workflow_gate import (  # noqa: E402
    WorkflowContext,
    build_workflow_plan,
)


RULE_PATH = AI_ROOT / "prototype" / "kwb_enzyme_designer_rule.py"
EVENT_TIME = "2026-07-24T00:00:00+08:00"


def _load_rule_module():
    spec = importlib.util.spec_from_file_location("kwb_enzyme_designer_rule_local", RULE_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load local rule MVP from {RULE_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


RULE_MODULE = _load_rule_module()


def _event(
    *,
    context: WorkflowContext,
    step: dict[str, Any],
    status: str | None = None,
    error_code: str | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "event_id": f"evt-{step['task_id']}",
        "session_id": context.session_id,
        "conversation_id": context.conversation_id,
        "model_name": "KWB-EnzymeDesigner",
        "model_version": "0.1.0-rule-mvp",
        "tool_name": step["tool_name"],
        "tool_params": {
            "task_id": step["task_id"],
            "depends_on": step.get("depends_on", []),
            "local_only": True,
        },
        "stage": step["stage"],
        "stage_title": step["tool_name"],
        "progress_percent": 100 if (status or step["status"]) == "completed" else 0,
        "status": status or step["status"],
        "quality_flags": ["local_only", "workflow_gate_enforced"],
        "created_at": EVENT_TIME,
    }
    if error_code:
        payload["error_code"] = error_code
    if step.get("blocked_reason"):
        payload["error_code"] = step["blocked_reason"]
    return payload


def run_local_adapter(
    case: dict[str, Any],
    context: WorkflowContext,
    completed_tools: Iterable[str] = (),
    tool_result_refs: Iterable[dict[str, Any]] = (),
) -> dict[str, Any]:
    """Return a gated local result envelope for one turn."""

    plan = build_workflow_plan(
        case,
        context,
        completed_tools=completed_tools,
        tool_result_refs=tool_result_refs,
    )
    events = [_event(context=context, step=step) for step in plan["steps"]]
    kwb_step = next(
        (step for step in plan["steps"] if step["tool_name"] == "kwb_enzyme_designer"),
        None,
    )
    result: dict[str, Any] | None = None
    adapter_status = plan["status"]
    error_code = plan.get("error_code")

    if kwb_step and kwb_step["status"] == "planned":
        result = RULE_MODULE.design(case)
        adapter_status = "completed"
        for event in events:
            if event["tool_name"] == "kwb_enzyme_designer":
                event["status"] = "completed"
                event["progress_percent"] = 100
                event["result_ref"] = kwb_step["task_id"]
    elif kwb_step and kwb_step.get("blocked_reason"):
        error_code = kwb_step["blocked_reason"]

    return {
        "status": adapter_status,
        "error_code": error_code,
        "model": {
            "name": "KWB-EnzymeDesigner",
            "version": "0.1.0-rule-mvp",
            "data_version": "local-dev",
        },
        "context": {
            "session_id": context.session_id,
            "conversation_id": context.conversation_id,
            "request_turn_id": context.request_turn_id,
        },
        "workflow": plan,
        "result": result,
        "events": events,
        "quality_flags": ["local_only", "no_production_integration"],
    }
