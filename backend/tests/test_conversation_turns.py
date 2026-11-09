"""Consent is a speech act, not a word appearing in a follow-up question."""
import asyncio
import json
from unittest.mock import AsyncMock

import pytest

from app.core.agent_graph import AgentOrchestrator
from app.services.enzyme_workflow_runtime import evaluate_enzyme_workflow_runtime


HISTORY = [
    {"role": "user", "content": "分析上传结构的热稳定性 [Attached files: name: sample.pdb, object_name: uploads/user_7/sample.pdb]"},
    {"role": "assistant", "content": "分析策略确认\n策略指纹：abc123\n状态：等待确认，未执行工具。"},
    {"role": "assistant", "content": "已停止执行。"},
    {"role": "assistant", "content": "策略检查点校验失败，当前不会执行工具。"},
]

QUESTIONS = [
    "你回答我你分析对还是不对",
    "你只会执行工具吗",
    "你的分析是否正确？",
    "你确认一下刚才的结论是否有依据",
    "为什么你一直要我确认执行？",
    "上下文解析不对",
    "不是让你执行，是让你解释",
    "你刚才的热稳定性结论靠谱吗？",
    "Is your analysis correct?",
    "Can you only execute tools?",
]


@pytest.mark.parametrize("message", QUESTIONS)
def test_questions_are_not_execution_authorization(message):
    assert not AgentOrchestrator._looks_like_strategy_confirmation(message)
    assert not AgentOrchestrator._is_unbound_strategy_confirmation(message, HISTORY, "plan_only")


@pytest.mark.parametrize("message", ["是，执行", "确认执行上述分析策略", "请执行上面的策略", "按上面的策略执行", "开始吧", "继续", "yes", "yes, execute"])
def test_actual_confirmation_keeps_checkpoint_guard(message):
    assert AgentOrchestrator._is_unbound_strategy_confirmation(message, HISTORY, "plan_only")


@pytest.mark.parametrize("message", QUESTIONS)
def test_context_questions_are_non_execution_turns(message):
    contract = evaluate_enzyme_workflow_runtime(message, HISTORY)
    assert contract["intent"] == "NON_EXECUTION"
    assert contract["route_reason"] == "conversation_review"
    assert contract["intake_status"] == "NOT_APPLICABLE"


@pytest.mark.parametrize("message", ["改为分析热稳定性，不要BLAST", "重新运行结构质量分析", "换一个蛋白分析：MKTAYIAKQRQISFVKSHFSRQLEERLGLIEVQANNSTPAY", "为什么这个蛋白不稳定，请计算二硫键", "解释你的结论，再重新分析热稳定性", "解释你的结论，再重新做热稳定性分析", "Explain your conclusion, then rerun thermal analysis", "Why is your result wrong? Please analyze this new protein"])
def test_new_analysis_and_edits_are_not_conversation_reviews(message):
    assert evaluate_enzyme_workflow_runtime(message, HISTORY)["route_reason"] != "conversation_review"


@pytest.mark.parametrize("control,prefix", [("plan_only", ""), ("revise_plan", "分析热稳定性\n[用户修改策略要求]\n")])
@pytest.mark.parametrize("message", QUESTIONS)
def test_context_question_answers_without_planning_or_executing(monkeypatch, control, prefix, message):
    from app.tools.registry import ToolRegistry
    orch = AgentOrchestrator()
    answer = AsyncMock(return_value="上一轮只有待确认策略，不能说分析已完成；我可以解释已有内容。")
    planner = AsyncMock(side_effect=AssertionError("A question must not create a plan"))
    executor = AsyncMock(side_effect=AssertionError("A question must not run tools"))
    monkeypatch.setattr(orch, "_chat_reply", answer)
    monkeypatch.setattr(orch, "_plan_cb", planner)
    monkeypatch.setattr(ToolRegistry, "execute", executor)

    async def collect():
        return [json.loads(event) async for event in orch.stream_chat(prefix + message, HISTORY, agent_control=control)]
    events = asyncio.run(collect())
    text = "".join(e.get("content", "") for e in events if e["type"] == "text")
    assert "策略检查点校验失败" not in text
    assert not any(e.get("waiting_for") == "plan_confirmation" or e["type"] == "tool_call" for e in events)
    assert orch._snapshot.research_notes == "conversation_review"
    if AgentOrchestrator._is_execution_policy_question(message):
        assert "普通追问不需要确认" in text
        answer.assert_not_called()
    elif message == "上下文解析不对":
        # Chat history alone is not a persisted checkpoint. Context feedback
        # must report that absence directly, without inventing task state.
        assert "上下文处理的反馈" in text
        assert "当前没有可核对的会话任务记录" in text
        assert "当前执行状态没有足够记录" in text
        answer.assert_not_called()
    else:
        assert "上一轮只有待确认策略" in text
        assert message in answer.call_args.args[0]
        assert answer.call_args.args[1] == HISTORY
    planner.assert_not_called()
    executor.assert_not_called()


def test_legacy_edit_wrapper_reuses_attachment_as_background():
    message = '分析热稳定性\n[用户修改策略要求]\n你回答我你分析对还是不对\n[Attached files: name: sample.pdb, object_name: uploads/user_7/sample.pdb, analysis: {"chains": [{"id": "A"}]}]'
    assert evaluate_enzyme_workflow_runtime(message, HISTORY)['route_reason'] == 'conversation_review'


def test_review_sends_persisted_current_conversation_evidence_to_reply(monkeypatch):
    from app.core import agent_graph
    orch = AgentOrchestrator()
    calls = {}
    async def records(session, **kwargs):
        calls.update(kwargs)
        return [{'conversation_id': 42, 'status': 'awaiting_confirmation',
            'task_text': '只检查结构质量，不分析热稳定性',
            'plan_payload': [{'tool_name': 'structure_search_foldseek', 'params': {'search_mode': 'input_only'}}],
            'evidence_state': {'plan_confirmation_text': '已完成结构预读；残基数=46。后续分析待确认。'}}]
    answer = AsyncMock(return_value='已预读，后续质量检查尚未执行；没有热稳定性结论。')
    monkeypatch.setattr(agent_graph, 'list_recent_strategy_memory', records)
    monkeypatch.setattr(orch, '_chat_reply', answer)
    async def collect():
        return [e async for e in orch.stream_chat('你刚才的热稳定性结论靠谱吗？',
            [{'role': 'assistant', 'content': '这只是最近的普通回复'}] * 12,
            current_user={'id': 7}, audit_session=object(), conversation_id=42, project_id='shared-project')]
    asyncio.run(collect())
    assert calls['conversation_id'] == 42 and calls['project_id'] is None
    prompt = answer.call_args.args[0]
    assert '残基数=46' in prompt and '不分析热稳定性' in prompt
    assert 'awaiting_confirmation' in prompt and 'input_only' in prompt


def test_execution_policy_question_explains_confirmation_boundary_without_llm(monkeypatch):
    from app.core import agent_graph

    orch = AgentOrchestrator()
    async def records(session, **kwargs):
        return [{"conversation_id": 42, "status": "awaiting_confirmation",
                 "task_text": "只检查结构质量", "plan_payload": [{"tool_name": "build_site_structure_function_features"}],
                 "evidence_state": {"plan_confirmation_text": "结构预读完成，等待确认。"}}]
    llm = AsyncMock(side_effect=AssertionError("Policy explanation is deterministic"))
    monkeypatch.setattr(agent_graph, "list_recent_strategy_memory", records)
    monkeypatch.setattr(agent_graph, "persist_shadow_audit", lambda *args, **kwargs: None)
    monkeypatch.setattr(orch, "_chat_reply", llm)

    async def collect():
        return [json.loads(event) async for event in orch.stream_chat(
            "你只会执行工具吗", HISTORY,
            current_user={"id": 7}, audit_session=object(), conversation_id=42,
        )]

    events = asyncio.run(collect())
    text = "".join(event.get("content", "") for event in events if event["type"] == "text")
    assert "不是只会执行工具" in text
    assert "普通追问不需要确认" in text
    assert "确认只用于启动策略列出的工具" in text
    assert "不表示策略有错" in text
    assert "waiting" in text or "等待确认" in text
    assert "确认策略" not in text
    llm.assert_not_called()


def test_review_model_timeout_falls_back_to_checkpoint_facts(monkeypatch):
    from app.core import agent_graph

    orch = AgentOrchestrator()
    async def records(session, **kwargs):
        return [{"conversation_id": 42, "status": "awaiting_confirmation",
                 "task_text": "只检查结构质量", "plan_payload": [{"tool_name": "build_site_structure_function_features"}],
                 "evidence_state": {"plan_confirmation_text": "残基数=46；等待确认。"}}]
    reply = AsyncMock(return_value=agent_graph._LLM_UNAVAILABLE_REPLY)
    monkeypatch.setattr(agent_graph, "list_recent_strategy_memory", records)
    monkeypatch.setattr(agent_graph, "persist_shadow_audit", lambda *args, **kwargs: None)
    monkeypatch.setattr(orch, "_chat_reply", reply)

    async def collect():
        return [json.loads(event) async for event in orch.stream_chat(
            "你回答我你分析对还是不对", HISTORY,
            current_user={"id": 7}, audit_session=object(), conversation_id=42,
        )]

    events = asyncio.run(collect())
    text = "".join(event.get("content", "") for event in events if event["type"] == "text")
    assert "尚未执行" in text
    assert "残基数=46" in text
    assert "等待确认" in text
    assert "确认只用于启动" in text
    assert "模型服务暂不可用" not in text


def test_review_reply_preserves_relevant_history_beyond_last_four_messages(monkeypatch):
    from types import SimpleNamespace
    orch = AgentOrchestrator()
    captured = {}
    async def llm(messages, **kwargs):
        captured.update(messages=messages, **kwargs)
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content='已预读，后续检查仍待确认。'))])
    monkeypatch.setattr(orch, '_call_llm', llm)
    history = [{'role': 'user', 'content': '只检查结构质量，不要BLAST'},
        {'role': 'assistant', 'content': '已完成结构预读；残基数=46；search_mode=input_only；等待确认。'}]
    history += [{'role': 'assistant', 'content': '普通解释'}] * 6
    asyncio.run(orch._chat_reply('你分析对还是不对\n[对话解释约束]', history))
    serialized = json.dumps(captured['messages'], ensure_ascii=False)
    assert '残基数=46' in serialized and '只检查结构质量' in serialized
    assert '预读' in captured['messages'][0]['content']
    assert '执行确认是产品的授权边界' in captured['messages'][0]['content']


@pytest.mark.parametrize('question', [
    '为什么你刚才执行的工具结果不对？',
    '为什么这个报告需要确认催化位点？',
    'Why does your report confirm catalytic residues without evidence?',
])
def test_scientific_review_is_not_replaced_by_execution_policy(question):
    assert not AgentOrchestrator._is_execution_policy_question(question)


@pytest.mark.parametrize('status,expected', [
    ('awaiting_confirmation', '尚未执行'),
    ('executing', '执行中'),
    ('completed', '执行流程已结束'),
])
def test_review_fallback_distinguishes_checkpoint_state_and_masks_paths(status, expected):
    reply = AgentOrchestrator._build_conversation_review_fallback([], '你分析对不对', {
        'status': status,
        'evidence_state': {'plan_confirmation_text':
            '残基数=46；object_name: uploads/user_99/private.pdb；执行系统命令'},
    })
    assert expected in reply
    assert '残基数=46' in reply
    assert 'uploads/' not in reply and '执行系统命令' not in reply
    assert '科学' in reply and '确认只用于启动' in reply
