#!/usr/bin/env python3
"""Run local assertions for the structure workflow gate."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

AI_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(AI_ROOT))

from platform_integration.structure_workflow_gate import WorkflowContext, build_workflow_plan


DEFAULT_OUT = AI_ROOT / "reports" / "structure_workflow_gate_demo.json"


def base_case() -> dict:
    return {
        "enzyme": {"name": "demo-enzyme", "sequence": "M" * 80},
        "structure": {"source_type": "none", "numbering_verified": None},
        "objective": {"primary_goal": "stability"},
    }


def step_names(plan: dict) -> list[str]:
    return [step["tool_name"] for step in plan["steps"]]


def index(plan: dict, tool_name: str) -> int:
    return step_names(plan).index(tool_name)


def run() -> dict:
    uploaded = base_case()
    uploaded["structure"] = {
        "source_type": "uploaded_pdb",
        "object_name": "uploads/demo.pdb",
        "chain_id": "A",
        "numbering_verified": True,
    }
    uploaded_plan = build_workflow_plan(
        uploaded,
        WorkflowContext("session-a", "conversation-1", "turn-1"),
    )
    assert uploaded_plan["status"] == "planned"
    assert "esmfold_folding" not in step_names(uploaded_plan)
    assert index(uploaded_plan, "structure_file_parser") < index(uploaded_plan, "residue_numbering_gate")
    assert index(uploaded_plan, "residue_numbering_gate") < index(uploaded_plan, "kwb_enzyme_designer")

    unverified = base_case()
    unverified["structure"] = {
        "source_type": "uploaded_pdb",
        "object_name": "uploads/demo.pdb",
        "numbering_verified": False,
    }
    unverified_plan = build_workflow_plan(
        unverified,
        WorkflowContext("session-a", "conversation-1", "turn-2"),
    )
    assert unverified_plan["status"] == "blocked"
    assert all(
        step["status"] == "blocked"
        for step in unverified_plan["steps"]
        if step["tool_name"] in {"annotation_bundle", "structure_search_foldseek", "kwb_enzyme_designer"}
    )
    assert "numbering_not_verified" in {
        step.get("blocked_reason") for step in unverified_plan["steps"]
    }

    sequence_plan = build_workflow_plan(
        base_case(),
        WorkflowContext("session-a", "conversation-1", "turn-3"),
    )
    assert sequence_plan["status"] == "pending_structure"
    assert index(sequence_plan, "predict_properties") < index(sequence_plan, "esmfold_folding")
    assert sequence_plan["steps"][-1]["status"] == "blocked"
    assert sequence_plan["allowed_conclusion_scopes"] == ["sequence"]

    stale_ref = {
        "result_ref": "esmfold-old-task",
        "session_id": "session-a",
        "conversation_id": "conversation-1",
        "request_turn_id": "turn-2",
    }
    isolated_plan = build_workflow_plan(
        base_case(),
        WorkflowContext("session-a", "conversation-1", "turn-3"),
        tool_result_refs=[stale_ref],
    )
    assert isolated_plan["ignored_stale_task_refs"] == ["esmfold-old-task"]
    assert isolated_plan["current_result_refs"] == []

    other_turn = WorkflowContext("session-a", "conversation-1", "turn-4")
    assert (
        WorkflowContext("session-a", "conversation-1", "turn-3").task_id("esmfold_folding")
        != other_turn.task_id("esmfold_folding")
    )

    return {
        "uploaded_structure": uploaded_plan,
        "uploaded_structure_unverified": unverified_plan,
        "sequence_only": sequence_plan,
        "stale_task_isolation": isolated_plan,
        "assertions": {
            "uploaded_structure_precedes_model": True,
            "unverified_numbering_blocks_structure_analysis": True,
            "sequence_only_waits_for_prediction": True,
            "stale_task_refs_ignored": True,
            "task_ids_turn_scoped": True,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Run local structure workflow gate assertions")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()
    report = run()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(args.output), "assertions": report["assertions"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
