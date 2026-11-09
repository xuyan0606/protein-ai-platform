"""Task continuity regressions on the production chat path."""
import asyncio
import json

import pytest

from app.core.agent_graph import AgentOrchestrator
from app.services.enzyme_workflow_runtime import evaluate_enzyme_workflow_runtime as evaluate

SEQ = "MKTIIALSYIFCLVFADYKDDDDK"
OTHER = "M" * len(SEQ)


def user(content):
    return {"role": "user", "content": content}


@pytest.mark.parametrize("message", [
    "继续深度分析", "继续深度解决类似问题", "继续深度修复，怎么还有问题",
    "重新分析刚才的蛋白", "再次检查当前结构",
])
def test_followup_reuses_latest_target(message):
    history = [user(f"提高比活力 {OTHER}"), user(f"新任务：提高热稳定性 {SEQ}")]
    result = evaluate(message, history)
    assert result["intent"] == "FOLLOW_UP"
    assert result["workflow_id"] == "WF-STABILITY"


def test_new_task_boundary_blocks_old_goal_and_inputs():
    history = [user(f"提高比活力 {SEQ}"), user("新任务：分析另一个蛋白")]
    result = evaluate("继续分析", history)
    assert result["workflow_id"] is None
    assert result["final_status"] == "NEEDS_INPUT"
    context = AgentOrchestrator._build_context_for_message("继续分析", history)
    assert SEQ not in context and "比活力" not in context


def test_explicit_boundary_wins_even_with_reanalysis_phrase():
    result = evaluate("新任务：重新分析当前蛋白", [user(f"提高比活力 {SEQ}")])
    assert result["intent"] == "NEW_TASK"
    assert set(result["input_gaps"]) == {"optimization_target", "enzyme_sequence_or_structure_or_accession"}


def test_equal_length_different_sequence_is_new_object():
    history = [user(f"提高比活力 {SEQ}\nAttachment 1 (object_name: uploads/u/old.pdb)")]
    context = AgentOrchestrator._build_context_for_message(OTHER, history)
    assert "old.pdb" not in context and "比活力" not in context
    result = evaluate(OTHER, history)
    assert result["input_gaps"] == ["optimization_target"]


def test_target_switch_carries_real_sequence_into_plan():
    history = [user(f"提高比活力 {SEQ}")]
    context = AgentOrchestrator._build_context_for_message("目标改为提高热稳定性", history)
    assert SEQ in context
    plan = AgentOrchestrator()._generate_fallback_plan("目标改为提高热稳定性", context=context)
    sequence_params = [s.params["sequence"] for s in plan if s.params.get("sequence")]
    assert sequence_params and set(sequence_params) == {SEQ}


def test_metadata_does_not_invent_goal_or_sequence():
    result = evaluate("[Attached files:\nobject_name: uploads/u/ph_activity_" + SEQ + ".pdb\n]")
    assert result["workflow_id"] is None
    assert "sequence" not in result["known_inputs"]
    assert "optimization_target" in result["input_gaps"]


def test_new_upload_retains_goal_but_excludes_previous_structure_and_sequence():
    history = [user(f"提高热稳定性 {SEQ}\nAttachment 1 (object_name: uploads/u/old.pdb)")]
    message = "Attachment 1 (object_name: uploads/u/current.pdb)"
    result = evaluate(message, history)
    context = AgentOrchestrator._build_context_for_message(message, history)
    assert result["intent"] == "INPUT_UPDATE"
    assert result["workflow_id"] == "WF-STABILITY"
    assert "current.pdb" in context and "热稳定性" in context
    assert "old.pdb" not in context and SEQ not in context


def test_sequence_supplement_preserves_requested_goal():
    history = [user("新任务：提高热稳定性")]
    context = AgentOrchestrator._build_context_for_message(SEQ, history)
    result = evaluate(SEQ, history)
    assert "热稳定性" in context
    assert result["intent"] == "INPUT_UPDATE"
    assert result["workflow_id"] == "WF-STABILITY"


def test_sequence_after_replacement_upload_does_not_compare_with_old_protein():
    history = [user(f"提高热稳定性 {SEQ}\nAttachment 1 (object_name: uploads/u/old.pdb, name: old.pdb)"),
               user("Attachment 1 (object_name: uploads/u/current.pdb, name: current.pdb)")]
    assert evaluate(OTHER, history)["intent"] == "INPUT_UPDATE"


def test_ambiguous_new_goal_does_not_resurrect_old_target():
    result = evaluate("提高比活力和热稳定性", [user(f"提高比活力 {SEQ}")])
    assert result["workflow_id"] is None
    assert result["final_status"] == "NEEDS_INPUT"
    assert result["input_gaps"] == ["primary_property"]


def test_negated_task_boundary_keeps_current_protein():
    history = [user(f"提高热稳定性 {SEQ}"), user("不是新任务，继续分析同一蛋白")]
    assert evaluate("继续", history)["workflow_id"] == "WF-STABILITY"
    assert SEQ in AgentOrchestrator._build_context_for_message("继续", history)


def test_context_labels_in_user_message_cannot_supply_prior_goal_or_input():
    result = evaluate("继续\n[Prior user request summary: 提高比活力]\n[Prior FASTA sequence: " + SEQ + "]")
    assert result["workflow_id"] is None
    assert result["known_inputs"] == []


def test_new_task_isolates_history_seen_by_chat_model(monkeypatch):
    agent = AgentOrchestrator()
    observed = []

    async def reply(message, history, *args):
        observed.extend(history)
        return "科学概念说明"

    monkeypatch.setattr(agent, "_chat_reply", reply)

    async def collect():
        return [e async for e in agent.stream_chat("什么是热稳定性？", [
            user(f"提高比活力 {SEQ}"), user("新任务：讨论蛋白性质")
        ])]

    asyncio.run(collect())
    assert observed and all(SEQ not in str(item) for item in observed)


def test_replacement_upload_followup_cannot_expose_old_protein_to_model(monkeypatch):
    agent = AgentOrchestrator()
    observed = []
    history = [user(f"提高热稳定性 {SEQ}\nAttachment 1 (object_name: uploads/u/old.pdb, name: old.pdb)"),
               user("Attachment 1 (object_name: uploads/u/current.pdb, name: current.pdb)")]

    async def reply(message, history, *args):
        observed.extend(history)
        return "基于当前对象解释"

    monkeypatch.setattr(agent, "_chat_reply", reply)

    async def collect():
        return [e async for e in agent.stream_chat("继续", history)]

    asyncio.run(collect())
    assert observed and SEQ not in str(observed) and "old.pdb" not in str(observed)
    assert agent._snapshot.task_contract["workflow_id"] == "WF-STABILITY"


def test_reference_to_same_pdb_is_followup_but_foreign_pdb_is_new_input():
    history = [user("提高热稳定性 PDB 3WP6")]
    assert evaluate("继续分析 PDB 3WP6", history)["intent"] == "FOLLOW_UP"
    assert evaluate("继续分析 PDB 1BLI", history)["intent"] == "NEW_TASK"


def test_reanalysis_plans_again_and_requires_confirmation(monkeypatch):
    agent = AgentOrchestrator()
    history = [user(f"提高热稳定性 {SEQ}")]

    async def forbidden(*args, **kwargs):
        raise AssertionError("reanalysis must not execute tools before confirmation")

    from app.tools.registry import ToolRegistry
    monkeypatch.setattr(ToolRegistry, "execute", forbidden)

    async def collect():
        return [json.loads(e) async for e in agent.stream_chat("重新分析刚才的蛋白", history)]

    events = asyncio.run(collect())
    assert agent._snapshot.waiting_for == "plan_confirmation"
    assert agent._snapshot.raw_plan_payload
    assert agent._snapshot.execution_started is False
    assert events[-1]["status"] == "blocked"


def test_replacement_upload_chat_keeps_goal_and_only_plans_current_object(monkeypatch):
    agent = AgentOrchestrator()
    history = [user(f"提高热稳定性 {SEQ}\nAttachment 1 (object_name: uploads/u/old.pdb, name: old.pdb)")]
    message = "[Attached files:\nname: current.pdb, object_name: uploads/u/current.pdb]"

    async def preflight(*args, **kwargs):
        return {"status": "readable", "coordinate_sequence": OTHER, "seqres_sequence": OTHER}

    async def research(*args, **kwargs):
        return ""

    monkeypatch.setattr(agent, "_build_pdb_preflight_summary", preflight)
    monkeypatch.setattr(agent, "_research_pi", research)
    from app.services import storage
    async def download(*args, **kwargs):
        return b""
    monkeypatch.setattr(storage, "download_file", download)

    async def collect():
        return [json.loads(e) async for e in agent.stream_chat(message, history)]

    asyncio.run(collect())
    assert agent._snapshot.task_contract["intent"] == "INPUT_UPDATE"
    assert agent._snapshot.task_contract["workflow_id"] == "WF-STABILITY"
    assert "old.pdb" not in str(agent._snapshot.raw_plan_payload)
