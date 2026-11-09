"""User intent must not be inferred from uploaded PDB metadata."""

import json

import pytest

from app.services.enzyme_workflow_runtime import evaluate_enzyme_workflow_runtime
from app.services.property_workflow_governance import PropertyWorkflowRouter, WorkflowPolicyValidator


def pdb_message(request):
    # Frontend useChatStream serializes analysisData inside this trailing block.
    analysis = {
        "header": {"classification": "HYDROLASE(CARBOXYLIC ESTERASE)"},
        "unit_cell": {"a": 62.1, "b": 46.7, "c": 92.1, "alpha": 90, "beta": 90, "gamma": 90},
        "compound_annotation": {"molecule": "LIPASE", "ec": "3.1.1.3", "engineered": "YES"},
        "chains": [{"chain_id": "A", "residue_count": 317}],
        "nonpolymer_components": [{"component_id": "NAG", "chain_id": "B", "residue_number": 1}],
    }
    return (
        request + "\n\n[Attached files:\n- name: 1TCA.pdb, "
        "object_name: uploads/user_999/1tca.pdb, analysis: " + json.dumps(analysis) + "]"
    )


def test_neutral_1tca_request_does_not_become_ph_optimization():
    message = pdb_message("我要分析这个pdb")
    assert PropertyWorkflowRouter.route(message)["workflow_id"] is None
    contract = evaluate_enzyme_workflow_runtime(message)
    assert contract["workflow_id"] is None
    assert contract["optimization_targets"] == []
    assert "structure" in contract["known_inputs"]


def test_attachment_metadata_does_not_override_explicit_property_or_history():
    message = pdb_message("提高热稳定性")
    assert PropertyWorkflowRouter.route(message)["workflow_id"] == "WF-STABILITY"
    followup = evaluate_enzyme_workflow_runtime("继续", history=[{"role": "user", "content": message}])
    assert followup["intent"] == "FOLLOW_UP"
    assert followup["workflow_id"] == "WF-STABILITY"


def test_engineered_pdb_annotation_does_not_request_mutation_design():
    from app.core.agent_graph import AgentOrchestrator

    orch = AgentOrchestrator()
    message = pdb_message("我要分析这个pdb")
    assert orch._is_optimization_request(message) is False
    plan = orch._generate_fallback_plan(message, analysis_depth="deep")
    names = {step.tool_name for step in plan}
    assert {"build_site_structure_function_features", "ligand_contact_analysis",
            "structure_pocket_interface_analysis"} <= names
    assert names.isdisjoint({"mutation_priority_score", "mutation_scan", "enzyme_objective_module_plan", "gromacs_md"})


@pytest.mark.parametrize("goal, workflow", [
    ("提高热稳定性", "WF-STABILITY"),
    ("提高目标pH下活性", "WF-PH"),
    ("提高催化效率", "WF-ACTIVITY"),
    ("提高底物特异性", "WF-SPECIFICITY"),
    ("提高可溶性表达", "WF-EXPRESSION"),
])
def test_deep_pdb_plan_structure_evidence_is_allowed_for_property_workflows(goal, workflow):
    from app.core.agent_graph import AgentOrchestrator

    plan = AgentOrchestrator()._generate_fallback_plan(pdb_message(goal), analysis_depth="deep")
    names = [step.tool_name for step in plan]
    assert "build_site_structure_function_features" in names
    result = WorkflowPolicyValidator.validate_declared_tools(workflow, names)
    assert result["unknown_tool_calls"] == []
    assert result["forbidden_tool_calls"] == []
    assert result["status"] == "READY"


async def test_neutral_1tca_reaches_plan_confirmation_without_running_tools(monkeypatch):
    from app.core.agent_graph import AgentOrchestrator
    from app.tools.registry import ToolRegistry

    orch = AgentOrchestrator()

    async def no_research(*args, **kwargs):
        return ""

    async def no_experience(*args, **kwargs):
        return ""

    async def readable_preflight(*args, **kwargs):
        # Storage I/O is stubbed; hydration and both policy gates remain real.
        sequence = "LPSGSDPAFSQPKSVLDAGLTCQGASPSSVSK"
        return {"status": "readable", "coordinate_sequence": sequence, "seqres_sequence": sequence}

    async def unexpected_execution(*args, **kwargs):
        pytest.fail("plan_only must not execute tools")

    monkeypatch.setattr(orch, "_research_pi", no_research)
    monkeypatch.setattr(orch, "_get_experience_hints", no_experience)
    monkeypatch.setattr(orch, "_build_pdb_preflight_summary", readable_preflight)
    monkeypatch.setattr(ToolRegistry, "execute", unexpected_execution)
    events = [json.loads(event) async for event in orch.stream_chat(
        pdb_message("我要分析这个pdb"), [], analysis_depth="deep", agent_control="plan_only",
    )]
    text = "".join(event.get("content", "") for event in events if event["type"] == "text")
    assert "未获准工具" not in text
    assert orch._snapshot.waiting_for == "plan_confirmation"
    assert orch._snapshot.task_contract["workflow_id"] is None
    assert events[-1]["type"] == "done"
