"""Regressions reproduced against production on 2026-10-24."""

import json

import pytest


@pytest.mark.parametrize("prior,current,expected", [
    (["old.pdb"], ["old.pdb"], True),
    (["old.pdb"], ["new.pdb"], False),
    (["old.pdb"], ["old.pdb", "new.pdb"], False),
    (["old.pdb", "second.pdb"], ["old.pdb", "second.pdb"], True),
    (["old.pdb", "second.pdb"], ["second.pdb", "old.pdb"], True),
    (["old.pdb", "second.pdb"], ["old.pdb"], False),
])
def test_report_followup_requires_the_same_complete_attachment_set(prior, current, expected):
    from app.core.agent_graph import AgentOrchestrator

    def attached(names):
        return "\n[Attached files:\n" + "\n".join(
            f"name: {name}, object_name: uploads/user_7/{name}" for name in names
        ) + "]"

    history = [
        {"role": "user", "content": "检查结构质量" + attached(prior)},
        {"role": "assistant", "content": "# 多结构分析报告\n旧对象的结构证据。"},
    ]
    message = "继续解释这个结构的报告" + attached(current)
    context = AgentOrchestrator._build_context_for_message(message, history)
    assert AgentOrchestrator._is_same_problem_synthesis_followup(message, context) is expected


def test_report_followup_after_removing_attachment_excludes_old_object():
    from app.core.agent_graph import AgentOrchestrator

    first = "[Attached files: name: a.pdb, object_name: uploads/user_7/a.pdb]"
    second = "[Attached files: name: b.pdb, object_name: uploads/user_7/b.pdb]"
    history = [
        {"role": "user", "content": "检查结构质量" + first + second},
        {"role": "assistant", "content": "# 多结构分析报告\n两个文件的报告"},
        {"role": "user", "content": "检查结构质量" + first},
        {"role": "assistant", "content": "# 结构质量分析报告\n仅a文件的报告"},
    ]
    message = "继续解释这个结构的报告" + first
    context = AgentOrchestrator._build_context_for_message(message, history)
    assert "b.pdb" not in context
    assert AgentOrchestrator._is_same_problem_synthesis_followup(message, context)


@pytest.mark.parametrize("goal_edit", ["目标换成比活力", "换成分析比活力", "目标改为比活力", "改目标为比活力"])
@pytest.mark.parametrize("with_attachment", [False, True])
async def test_context_feedback_with_goal_change_reaches_planner(monkeypatch, goal_edit, with_attachment):
    from app.core.agent_graph import AgentOrchestrator

    orch = AgentOrchestrator()
    attachment = " [Attached files: name: a.pdb, object_name: uploads/user_7/a.pdb]"
    history = [{"role": "user", "content": "仅本地分析热稳定性，不要 BLAST" + attachment}]

    async def route(*args, **kwargs):
        return "analyze"

    async def research(*args, **kwargs):
        return ""

    class PlannerReached(Exception):
        pass

    async def plan(*args, **kwargs):
        raise PlannerReached()

    async def no_review(*args, **kwargs):
        pytest.fail("An explicit goal change must not be treated as a report review")

    monkeypatch.setattr(orch, "_route_intent", route)
    monkeypatch.setattr(orch, "_research_pi", research)
    monkeypatch.setattr(orch, "_plan_cb", plan)
    monkeypatch.setattr(orch, "_chat_reply", no_review)
    with pytest.raises(PlannerReached):
        async for _ in orch.stream_chat(
            "上下文解析不对，" + goal_edit + (attachment if with_attachment else ""), history,
        ):
            pass
    assert orch._snapshot.task_contract["intent"] == "TARGET_CHANGE"
    assert orch._snapshot.task_contract["optimization_targets"] == ["activity"]
    assert "blast_search" in orch._snapshot.task_contract["forbidden_tools"]
    assert orch._snapshot.task_contract["offline"]


def test_report_fallback_keeps_completed_report_across_repeated_attachments():
    from app.core.agent_graph import AgentOrchestrator

    a = " [Attached files: name: a.pdb, object_name: uploads/user_7/a.pdb]"
    b = " [Attached files: name: b.pdb, object_name: uploads/user_7/b.pdb]"
    history = [
        {"role": "user", "content": "检查结构质量" + b},
        {"role": "assistant", "content": "# 结构质量分析报告\n- 上传结构摘要：OLD_FILE"},
        {"role": "user", "content": "检查结构质量" + a},
        {"role": "assistant", "content": "# 结构质量分析报告\n- 上传结构摘要：CURRENT_FILE"},
        {"role": "user", "content": "继续解释这个结构的报告" + a},
        {"role": "assistant", "content": "第一次解释"},
    ]
    reply = AgentOrchestrator._history_report_reply(history, "继续解释这个结构的报告" + a)
    assert "CURRENT_FILE" in reply
    assert "OLD_FILE" not in reply
    assert "没有已完成" not in reply


def test_report_fallback_does_not_borrow_previous_object_report_before_current_completion():
    from app.core.agent_graph import AgentOrchestrator

    history = [
        {"role": "user", "content": "检查结构质量 [Attached files: name: a.pdb, object_name: uploads/user_7/a.pdb]"},
        {"role": "assistant", "content": "# 结构质量分析报告\n- 上传结构摘要：OLD_FILE_46aa"},
        {"role": "user", "content": "检查结构质量 [Attached files: name: b.pdb, object_name: uploads/user_7/b.pdb]"},
        {"role": "assistant", "content": "分析策略确认\n等待确认，未执行工具。"},
    ]
    reply = AgentOrchestrator._history_report_reply(history, "继续解释这个结构的报告")
    assert "OLD_FILE" not in reply
    assert "没有已完成" in reply


async def test_large_residue_mapping_remains_complete_in_stream_and_saved_snapshot(monkeypatch):
    from app.core.agent_graph import AgentOrchestrator, PlanStep
    from app.tools.registry import ToolRegistry

    orch = AgentOrchestrator()
    sequence = "ACDEFGHIKLMNPQRSTVWY" * 35
    mapping = [
        {
            "chain_id": "Z", "pdb_residue_number": i - 2,
            "insertion_code": "A" if i == 2 else "",
            "user_sequence_position": i + 1, "residue_aa": aa,
            "source": "input_sequence_exact_coordinate_mapping",
            "mapping_status": "no_verified_uniprot_mapping",
        }
        for i, aa in enumerate(sequence)
    ]
    expected = {"found": True, "mapping_count": len(mapping), "residue_mappings": mapping}
    assert len(json.dumps(expected, indent=2)) > 120000
    plan = [PlanStep(1, "residue_mapping_sifts", "Map input coordinates", {
        "pdb_object_name": "uploads/user_7/large.pdb", "chain_id": "Z",
        "input_sequence": sequence, "sequence_provenance": "pdb_coordinate_derived",
    })]

    async def execute(name, params, **kwargs):
        assert name == "residue_mapping_sifts"
        return expected

    async def synthesize(*args, **kwargs):
        return "仅编号映射已完成；未推断功能和实验性质。"

    monkeypatch.setattr(ToolRegistry, "execute", execute)
    monkeypatch.setattr(orch, "_synthesize_sc", synthesize)
    events = [json.loads(event) async for event in orch.stream_chat(
        "确认执行上述分析策略", [], agent_control="execute_confirmed",
        confirmed_plan=[{"id": s.id, "tool_name": s.tool_name,
                         "description": s.description, "params": s.params} for s in plan],
        strategy_signature=orch._plan_signature(plan),
        task_fingerprint=orch._task_fingerprint("核对上传结构编号", ""),
    )]
    states = [event for event in events if event.get("type") == "state" and event.get("step_results")]
    assert states
    streamed = json.loads(states[-1]["step_results"][0]["raw_result"])
    saved = json.loads(orch.get_snapshot_data()["step_results"][0]["raw_result"])
    assert streamed == saved == expected
    assert streamed["residue_mappings"][-1] == mapping[-1]
    assert streamed["residue_mappings"][2]["pdb_residue_number"] == 0
    assert streamed["residue_mappings"][2]["insertion_code"] == "A"


@pytest.mark.parametrize("status,state_text", [
    ("awaiting_confirmation", "等待确认"),
    ("executing", "执行中"),
    ("completed", "执行结束；结果是否可用、问题是否回答仍需分别核对"),
])
@pytest.mark.parametrize("message", ["上下文解析不对", "你对上下文的解析有误"])
@pytest.mark.parametrize("with_attachment", [False, True])
async def test_context_feedback_uses_saved_task_state_without_model_or_tools(monkeypatch, message, status, state_text, with_attachment):
    from app.core.agent_graph import AgentOrchestrator

    orch = AgentOrchestrator()

    async def no_model_or_tools(*args, **kwargs):
        pytest.fail("Context-state feedback should be answered from the saved checkpoint")

    async def memory(*args, **kwargs):
        return [{"conversation_id": 17, "status": status,
                 "task_text": "不要 BLAST，但要分析热稳定性", "plan_payload": []}]

    monkeypatch.setattr(orch, "_chat_reply", no_model_or_tools)
    monkeypatch.setattr(orch, "_plan_cb", no_model_or_tools)
    monkeypatch.setattr(orch, "_load_recent_strategy_memory_records", memory)
    attachment = " [Attached files: name: a.pdb, object_name: uploads/user_7/a.pdb]" if with_attachment else ""
    events = [json.loads(event) async for event in orch.stream_chat(
        message + attachment, [{"role": "user", "content": "不要 BLAST，但要分析热稳定性" + attachment}],
        conversation_id=17,
    )]
    reply = "".join(event.get("content", "") for event in events if event.get("type") == "text")
    assert "热稳定性" in reply
    assert "不要 BLAST" in reply
    assert "上下文" in reply
    assert state_text in reply
    assert not any(event.get("type") == "tool_call" for event in events)
    assert not any(event.get("waiting_for") == "plan_confirmation" for event in events)
