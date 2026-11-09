"""Task inputs must outlive the recent chat window without crossing task boundaries."""
from types import SimpleNamespace
import json

import pytest

from app.api.chat import _checkpoint_task_text, _load_conversation_history_for_agent
from app.core.agent_graph import AgentOrchestrator
from app.models.conversation import Conversation, Message
from app.models.user import User
from app.services.enzyme_workflow_runtime import evaluate_enzyme_workflow_runtime
from app.services.engineering_goal_semantics import thermal_objective

ORIGIN = '项目：淀粉酶耐热改造。提高热稳定性，95℃处理5分钟，残余酶活由30%达到至少60%。不要 BLAST。\n[Attached files:\nobject_name: uploads/user_7/source.pdb]'


async def test_computed_candidate_evidence_survives_long_discussion_without_trusting_assistant_lists(session):
    conv = await conversation(session, 'durable-tool-evidence')
    session.add(Message(conversation_id=conv.id, role='user', content=ORIGIN))
    session.add(Message(conversation_id=conv.id, role='assistant', content='工具报告', tool_calls=json.dumps([
        {'name': 'thermostability_candidate_workflow', 'status': 'completed', 'rawResult': json.dumps({
            'schema_version': 'thermostability_candidates_v1', 'sequence_sha256': 'exact',
            'preliminary_candidates': [{'mutation': 'A1V', 'sources': [{'reference': 'coordinates'}]}]})},
        {'name': 'blast_search', 'status': 'submitted', 'rawResult': json.dumps({'task_id': 'original-task', 'rid': 'ORIGINAL'})} ])))
    for i in range(18):
        session.add(Message(conversation_id=conv.id, role='assistant', content='未核验建议 D51N'))
    current = Message(conversation_id=conv.id, role='user', content='解释已有结果')
    session.add(current)
    await session.flush()
    history = await _load_conversation_history_for_agent(session, conversation_id=conv.id,
        current_message_id=current.id, request_history=[])
    evidence = [e for row in history for e in row.get('tool_evidence', [])]
    thermal = next(e for e in evidence if e['tool_name'] == 'thermostability_candidate_workflow')
    assert thermal['result']['preliminary_candidates'][0]['mutation'] == 'A1V'
    assert not any('D51N' in json.dumps(e) for e in evidence)


async def conversation(session, title):
    user = User(email=title+'@example.com', hashed_password='unused', name='QA')
    session.add(user)
    await session.flush()
    conv = Conversation(user_id=user.id, title=title)
    session.add(conv)
    await session.flush()
    return conv


async def save_turns(session, conv, origin):
    session.add(Message(conversation_id=conv.id, role='user', content=origin))
    for index in range(18):
        session.add(Message(conversation_id=conv.id, role='user', content=f'第{index}轮，请详细说明下一步'))
        session.add(Message(conversation_id=conv.id, role='assistant', content=f'第{index}轮说明：目前仍需补充证据'))
    current = Message(conversation_id=conv.id, role='user', content='继续分析')
    session.add(current)
    await session.flush()
    return current


async def test_database_recovers_original_task_after_eighteen_turns(session):
    conv = await conversation(session, 'durable-task')
    current = await save_turns(session, conv, ORIGIN)
    # A separate conversation must never become task memory.
    foreign = await conversation(session, 'foreign-task')
    session.add(Message(conversation_id=foreign.id, role='user', content='其他项目绝不可混入'))
    await session.flush()
    history = await _load_conversation_history_for_agent(session, conversation_id=conv.id,
        current_message_id=current.id, request_history=[])
    contents = '\n'.join(row['content'] for row in history)
    assert ORIGIN in contents
    assert '其他项目' not in contents
    contract = evaluate_enzyme_workflow_runtime('继续分析', history)
    assert contract['workflow_id'] == 'WF-STABILITY'
    assert contract['known_inputs'] == ['structure']
    assert 'blast_search' in contract['forbidden_tools']
    context = AgentOrchestrator._build_context_for_message('继续分析', history)
    assert 'source.pdb' in context and '95' in context and '60%' in context


async def test_old_client_history_cannot_resurrect_task_before_boundary(session):
    conv = await conversation(session, 'new-task-boundary')
    session.add(Message(conversation_id=conv.id, role='user', content=ORIGIN))
    await session.flush()
    current = await save_turns(session, conv, '新任务：提高比活力，序列：MKTIIALSYIFCLVFADYKDDDDK')
    history = await _load_conversation_history_for_agent(session, conversation_id=conv.id,
        current_message_id=current.id, request_history=[{'role':'user','content':ORIGIN}])
    context = AgentOrchestrator._build_context_for_message('继续分析', history)
    assert 'source.pdb' not in context and '95' not in context
    assert '比活力' in context and 'MKTIIALSYIFCLVFADYKDDDDK' in context


async def test_plain_followup_model_receives_project_and_goal_after_many_turns(monkeypatch):
    history = [{'role':'user','content':ORIGIN}]
    for i in range(15):
        history += [{'role':'user','content':f'补充解释第{i}点'}, {'role':'assistant','content':'尚无最终结论'}]
    observed = []
    async def llm(messages, **kwargs):
        observed.extend(messages)
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content='沿用同一项目目标'))])
    agent = AgentOrchestrator()
    monkeypatch.setattr(agent, '_call_llm', llm)
    await agent._chat_reply('下一轮实验怎么安排？', history)
    user_text = '\n'.join(m['content'] for m in observed if m['role']=='user')
    assert '淀粉酶耐热改造' in user_text and '95℃' in user_text and '60%' in user_text
    assert observed[-1]['content'] == '下一轮实验怎么安排？'


async def test_plain_followup_after_new_task_excludes_old_task_from_model(monkeypatch):
    observed = []
    async def llm(messages, **kwargs):
        observed.extend(messages)
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content='新项目'))])
    agent = AgentOrchestrator()
    monkeypatch.setattr(agent, '_call_llm', llm)
    history = [{'role':'user','content':ORIGIN}, {'role':'user','content':'新任务：蛋白表达量优化'}]
    await agent._chat_reply('有哪些限制？', history)
    assert not any('淀粉酶' in m['content'] for m in observed)
    assert any('表达量' in m['content'] for m in observed)


def test_property_followup_does_not_replace_original_numeric_goal():
    history = [{'role':'user','content':ORIGIN},
               {'role':'assistant','content':'尚未放行候选'},
               {'role':'user','content':'热稳定性为什么还没结果？'},
               {'role':'assistant','content':'缺少身份和测定证据'}]
    context = AgentOrchestrator._build_context_for_message('继续分析', history)
    assert '95℃' in context and '30%' in context and '60%' in context


async def test_returning_to_previous_task_preserves_latest_boundary_even_if_text_repeats(session):
    conv = await conversation(session, 'repeated-task')
    first = '新任务：提高热稳定性，序列：MKTIIALSYIFCLVFADYKDDDDK'
    for text in [first, '新任务：提高比活力，序列：AAAAAAAAAAAAAAAAAAAAAA', first]:
        session.add(Message(conversation_id=conv.id, role='user', content=text))
    await session.flush()
    history = await _load_conversation_history_for_agent(session, conversation_id=conv.id,
        current_message_id=None, request_history=[])
    result = evaluate_enzyme_workflow_runtime('继续分析', history)
    assert result['workflow_id'] == 'WF-STABILITY'


def test_continuation_checkpoint_keeps_original_goal_and_input_not_last_chitchat():
    history = [{'role':'user','content':ORIGIN}]
    for i in range(15):
        history += [{'role':'user','content':f'第{i}轮请解释一下'}, {'role':'assistant','content':'补充说明'}]
    checkpoint = _checkpoint_task_text('继续分析', history)
    assert 'source.pdb' in checkpoint and '95℃' in checkpoint and '60%' in checkpoint


def test_same_goal_extension_keeps_assay_values_from_initial_request():
    goal = '提高该酶热稳定性，95℃处理5分钟，目前残余酶活30%，目标至少达到60%。'
    history = [{'role':'user','content':goal+'\n序列：MKTIIALSYIFCLVFADYKDDDDK'}]
    message = '请新增热稳定性突变候选，先给出策略'
    context = AgentOrchestrator._build_context_for_message(message, history)
    objective = thermal_objective(message+'\n'+context)
    assert objective.get('temperature_c') == 95
    assert objective.get('duration_min') == 5
    assert objective.get('baseline_residual_activity_pct') == 30
    assert objective.get('target_residual_activity_pct') == 60


def test_inherited_real_fasta_satisfies_planning_input_gate():
    history = [{'role':'user','content':'提高热稳定性，95℃处理5分钟，目前残余酶活30%，目标至少60%。\n序列：MKTIIALSYIFCLVFADYKDDDDK'}]
    message = '请新增热稳定性突变候选，先给出分析策略。'
    context = AgentOrchestrator._build_context_for_message(message, history)
    assert not AgentOrchestrator._should_clarify_before_tools(message, 'analyze', context)
    assert AgentOrchestrator._should_clarify_before_tools(message, 'analyze', '[Prior FASTA input present]')


def test_explanation_about_goal_is_not_a_replacement_assay():
    history = [{'role':'user','content':'项目：淀粉酶耐热改造。提高热稳定性，95℃处理5分钟，目前残余酶活30%，目标至少60%。\n序列：MKTIIALSYIFCLVFADYKDDDDK'},
        {'role':'user','content':'请解释上面任务的原始热处理条件、当前残余酶活和目标值。只复述已提供的信息，不要调用工具。'},
        {'role':'assistant','content':'95℃5分钟，30%到至少60%。'}]
    message = '请新增热稳定性突变候选，先给出分析策略。'
    context = AgentOrchestrator._build_context_for_message(message, history)
    objective = thermal_objective(message+'\n'+context)
    assert objective.get('temperature_c') == 95
    assert objective.get('baseline_residual_activity_pct') == 30
    assert objective.get('target_residual_activity_pct') == 60
    assert not AgentOrchestrator._task_requests_no_tools(message+'\n'+context)


async def test_long_fasta_conversation_can_reach_signed_plan_without_reentering_input(monkeypatch):
    import json
    agent = AgentOrchestrator()
    async def unavailable_model(*args, **kwargs):
        raise RuntimeError('Controlled unavailable LLM; use production fallback planner')
    async def no_external_research(*args, **kwargs):
        return ''
    monkeypatch.setattr(agent, '_call_llm', unavailable_model)
    monkeypatch.setattr(agent, '_research_pi', no_external_research)
    history = [{'role':'user','content':'提高热稳定性，95℃处理5分钟，目前残余酶活30%，目标至少60%。仅本地分析，不要 BLAST。\n序列：MKTIIALSYIFCLVFADYKDDDDK'}]
    for i in range(18):
        history += [{'role':'assistant','content':f'第{i}轮讨论'}, {'role':'user','content':'请详细说明这个步骤'}]
    events = [json.loads(event) async for event in agent.stream_chat(
        '请新增热稳定性突变候选，先给出分析策略。', history, analysis_depth='fast', agent_control='plan_only')]
    state = next(event for event in reversed(events) if event.get('waiting_for')=='plan_confirmation')
    thermal = next(step for step in state['plan'] if step['tool_name']=='thermostability_candidate_workflow')
    assert thermal['params']['sequence']=='MKTIIALSYIFCLVFADYKDDDDK'
    assert thermal['params']['objective']['target_residual_activity_pct']==60
    assert state['strategy_signature'] and not state.get('step_results')
