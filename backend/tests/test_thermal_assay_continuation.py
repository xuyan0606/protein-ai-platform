"""A user's answer to an optional condition prompt must not restart the task."""
import json

import pytest

from app.core.agent_graph import AgentOrchestrator
from app.services.engineering_goal_semantics import merge_thermal_assay, thermal_objective
from app.services.enzyme_task_context import active_task_history, explicit_new_task
from app.services.enzyme_workflow_runtime import evaluate_enzyme_workflow_runtime

ORIGIN = ('项目：耐热改造。提高热稳定性，输出10个候选位点；不要BLAST；只分析链A。\n'
          '[Attached files: object_name: uploads/user_3/source.pdb]')
HISTORY = [{'role': 'user', 'content': ORIGIN},
           {'role': 'assistant', 'content': '热稳定性探索分析；实验条件未知，可后续补充。'}]
FULL = ('热稳定性评价指标：剩余酶活；处理条件：95度，5min；当前残余酶活：30%；'
        '目标残余酶活：80%；测定pH：4.5-4.8；缓冲液：磷酸盐缓冲液')


@pytest.mark.parametrize('text', [
    '不要再开一个新的对话分析，只补充pH：4.5',
    '不是新对话，是上一个项目的补充',
    '不要重新开任务，沿用原结构',
])
def test_negated_task_reset_keeps_original_upload_and_goal(text):
    assert not explicit_new_task(text)
    scoped = active_task_history(HISTORY + [{'role': 'user', 'content': text}])
    assert scoped[0]['content'] == ORIGIN
    context = AgentOrchestrator._build_context_for_message(text, HISTORY)
    assert 'source.pdb' in context and '热稳定性' in context


@pytest.mark.parametrize('text', [FULL, '95℃，5分钟', '缓冲液：磷酸盐缓冲液；辅因子：Ca离子',
                                       '测定pH：4.5', '实验条件未知，先不补充'])
def test_optional_condition_answer_is_an_input_update_not_a_new_goal(text):
    contract = evaluate_enzyme_workflow_runtime(text, HISTORY)
    assert contract['intent'] == 'INPUT_UPDATE'
    assert contract['task_relation'] == 'ASSAY_UPDATE'
    assert contract['workflow_id'] == 'WF-STABILITY'
    assert contract['known_inputs'] == ['structure']
    assert 'blast_search' in contract['forbidden_tools']
    assert contract['chain_ids'] == ['A']


def test_short_values_keep_prior_endpoint_without_guessing_percentages():
    merged = merge_thermal_assay(['评价指标：剩余酶活；95℃，5分钟', '当前30%，希望80%', 'pH：4.5'])
    assert merged['baseline_residual_activity_pct'] == 30
    assert merged['target_residual_activity_pct'] == 80
    assert merged['temperature_c'] == 95 and merged['duration_min'] == 5
    assert merged['ph'] == 4.5
    assert 'baseline_residual_activity_pct' not in merge_thermal_assay(['当前30%，希望80%'])


def test_bare_conditions_are_inherited_by_the_next_explicit_execution():
    history = HISTORY + [{'role': 'user', 'content': FULL},
                         {'role': 'user', 'content': '温度改为90℃，时间改为10分钟'},
                         {'role': 'user', 'content': '当前40%，希望85%'}]
    context = AgentOrchestrator._build_context_for_message('按原目标继续调用工具给我位点', history)
    assay = thermal_objective(context)
    assert assay['temperature_c'] == 90 and assay['duration_min'] == 10
    assert assay['baseline_residual_activity_pct'] == 40 and assay['target_residual_activity_pct'] == 85
    assert assay['buffer'] == '磷酸盐缓冲液'
    assert '输出10个突变位点' in context and 'source.pdb' in context


def test_measured_ph_does_not_replace_thermal_goal_on_the_next_turn():
    history = HISTORY + [{'role': 'user', 'content': '测定pH：4.5'}]
    contract = evaluate_enzyme_workflow_runtime('继续按原目标调用工具给我位点', history)
    assert contract['workflow_id'] == 'WF-STABILITY'
    assert 'blast_search' in contract['forbidden_tools']
    assert contract['chain_ids'] == ['A']


def test_a_positive_reset_after_a_negative_clause_still_starts_a_new_task():
    assert explicit_new_task('不是新对话的问题。现在另一个新任务：分析另一条序列')


def test_explicit_endpoint_change_replaces_the_old_endpoint():
    merged = merge_thermal_assay([FULL, '评价指标改为Tm，Tm为75℃'])
    assert merged['endpoint'] == 'tm'


def test_exploration_report_does_not_present_an_empty_required_form():
    from app.services.thermostability_report import render_thermostability_report
    report = render_thermostability_report({'schema_version': 'thermostability_candidates_v1',
        'analysis_mode': 'exploration', 'status': 'partial', 'objective': {}})
    assert report.count('未知；后续可补充') == 0
    assert '| 热处理温度' not in report and '| 酶活测定方法' not in report
    assert '可选' in report


@pytest.mark.asyncio
@pytest.mark.parametrize('question', ['为啥不能输出位点？', '残基编号对不上我的序列啊'])
async def test_actual_result_complaints_explain_receipts_without_new_planning(monkeypatch, question):
    agent = AgentOrchestrator()
    async def forbidden(*args, **kwargs):
        raise AssertionError('Reviewing failed output must not restart analysis')
    monkeypatch.setattr(agent, '_call_llm', forbidden)
    monkeypatch.setattr(agent, '_build_pdb_preflight_summary', forbidden)
    payload = {'schema_version': 'thermostability_candidates_v1', 'status': 'partial',
               'analysis_mode': 'exploration', 'objective': {}, 'preliminary_candidates': [],
               'branches': {'colabfold': {'status': 'blocked', 'blocked_reason': 'COLABFOLD_LOCAL_MSA_PATH is required'},
                            'ddgun': {'status': 'not_run', 'reason': 'no_eligible_hypotheses'},
                            'esm': {'status': 'not_run', 'reason': 'no_eligible_hypotheses'}}}
    history = HISTORY + [{'role': 'assistant', 'content': '报告', 'tool_evidence': [
        {'tool_name': 'thermostability_candidate_workflow', 'status': 'completed', 'result': payload}]}]
    events = [json.loads(e) async for e in agent.stream_chat(question, history, agent_control='plan_only')]
    assert not any(e.get('plan') for e in events)
    reply = ''.join(e.get('content', '') for e in events if e.get('type') == 'text')
    assert 'COLABFOLD_LOCAL_MSA_PATH' in reply and 'no_eligible_hypotheses' in reply
    assert '当前回执没有具体候选行' in reply


@pytest.mark.parametrize('text', [
    'pH改为4.5，然后按原目标继续调用工具给我位点',
    '补充95℃，5分钟；重新分析当前结构',
    '改成提高表达量',
    '新任务：提高另一个蛋白热稳定性',
])
def test_actual_reanalysis_target_changes_and_new_tasks_are_not_data_only(text):
    assert evaluate_enzyme_workflow_runtime(text, HISTORY)['task_relation'] != 'ASSAY_UPDATE'


@pytest.mark.asyncio
async def test_stream_acknowledges_multiple_answers_without_model_planning_or_execution(monkeypatch):
    agent = AgentOrchestrator()
    async def forbidden(*args, **kwargs):
        raise AssertionError('A data-only update must not plan, call a model, or pre-read the upload')
    monkeypatch.setattr(agent, '_call_llm', forbidden)
    monkeypatch.setattr(agent, '_build_pdb_preflight_summary', forbidden)
    history = list(HISTORY)
    for text in [FULL, '温度改为90℃，时间改为10分钟', '当前40%，希望85%']:
        events = [json.loads(e) async for e in agent.stream_chat(text, history, agent_control='plan_only')]
        state = [e for e in events if e.get('type') == 'state'][-1]
        assert state['stage'] == 'done'
        assert not state['plan'] and not state['step_results']
        assert not state.get('waiting_for')
        assert state['task_contract']['task_relation'] == 'ASSAY_UPDATE'
        reply = ''.join(e.get('content', '') for e in events if e.get('type') == 'text')
        assert '热稳定性' in reply and '10' in reply
        assert '未知；后续可补充' not in reply and '请补充' not in reply
        assert any(e.get('type') == 'done' for e in events)
        history += [{'role': 'user', 'content': text}, {'role': 'assistant', 'content': reply}]
    assert '90' in reply and '10' in reply and '40' in reply and '85' in reply and '4.5' in reply


@pytest.mark.asyncio
async def test_database_reload_recovers_supplemented_conditions_without_client_history(session):
    from app.api.chat import _load_conversation_history_for_agent
    from app.models.conversation import Conversation, Message
    from app.models.user import User
    user = User(email='assay-continuation@example.com', name='QA', hashed_password='unused')
    session.add(user)
    await session.flush()
    conv = Conversation(user_id=user.id, title='assay update')
    session.add(conv)
    await session.flush()
    for text in [ORIGIN, FULL, '当前40%，希望85%']:
        session.add(Message(conversation_id=conv.id, role='user', content=text))
    current = Message(conversation_id=conv.id, role='user', content='按原目标继续调用工具给我位点')
    session.add(current)
    await session.flush()
    history = await _load_conversation_history_for_agent(session, conversation_id=conv.id,
        current_message_id=current.id, request_history=[])
    context = AgentOrchestrator._build_context_for_message(current.content, history)
    assert 'source.pdb' in context and '输出10个突变位点' in context
    assert thermal_objective(context)['target_residual_activity_pct'] == 85


@pytest.mark.asyncio
async def test_resumed_signed_plan_keeps_thermal_goal_after_ph_supplement(monkeypatch):
    """Catch planning reselecting the last pH measurement as a new objective."""
    from app.tools.registry import ToolRegistry
    ToolRegistry.discover()
    agent = AgentOrchestrator()
    async def no_model(*args, **kwargs):
        raise AssertionError('This continuation needs deterministic planning only')
    async def empty(*args, **kwargs):
        return ''
    async def download(name):
        assert name == 'uploads/user_3/source.pdb'
        names = ['ALA', 'CYS', 'ASP', 'GLU', 'PHE', 'GLY', 'HIS', 'ILE', 'LYS', 'LEU',
                 'MET', 'ASN', 'PRO', 'GLN', 'ARG', 'SER', 'THR', 'VAL', 'TRP', 'TYR']
        return (''.join(f'ATOM  {i:5d}  CA  {aa} A{i:4d}    {i*3.:8.3f}{0.:8.3f}{0.:8.3f}  1.00 20.00           C\n'
                        for i, aa in enumerate(names, 1)) + 'END\n').encode()
    monkeypatch.setattr('app.services.storage.download_file', download)
    monkeypatch.setattr(agent, '_call_llm', no_model)
    monkeypatch.setattr(agent, '_get_experience_hints', empty)
    monkeypatch.setattr(agent, '_research_pi', empty)
    preflight = await agent._build_pdb_preflight_summary(ORIGIN)
    assert preflight['status'] == 'readable' and preflight['chains'], preflight
    history = list(HISTORY)
    for text in [FULL, '温度改为90℃，时间改为10分钟', '当前40%，希望85%',
                 '不要再开一个新的对话分析，只补充pH：4.5']:
        events = [json.loads(e) async for e in agent.stream_chat(text, history, agent_control='plan_only')]
        reply = ''.join(e.get('content', '') for e in events if e.get('type') == 'text')
        history += [{'role': 'user', 'content': text}, {'role': 'assistant', 'content': reply}]
    events = [json.loads(e) async for e in agent.stream_chat(
        '按原目标继续调用工具给我位点', history, agent_control='plan_only')]
    state = [e for e in events if e.get('type') == 'state'][-1]
    workflows = [s for s in state['plan'] if s['tool_name'] == 'thermostability_candidate_workflow']
    assert workflows, json.dumps(events, ensure_ascii=False)
    params = workflows[0]['params']
    assert params['assay_budget'] == 10
    assert params['objective']['temperature_c'] == 90 and params['objective']['duration_min'] == 10
    assert params['objective']['baseline_residual_activity_pct'] == 40
    assert params['objective']['target_residual_activity_pct'] == 85
    assert params['objective']['ph'] == 4.5 and params['objective']['buffer'] == '磷酸盐缓冲液'
    assert params['chain_id'] == 'A'
    # Public SSE deliberately hides object paths and internal evidence scope.
    signed = next(s for s in agent._snapshot.raw_plan_payload if s['tool_name'] == 'thermostability_candidate_workflow')
    assert signed['params']['evidence_scope']['pdb_object_name'] == 'uploads/user_3/source.pdb'
    assert 'blast_search' not in [s['tool_name'] for s in state['plan']]
    assert state['strategy_signature'] and not state['step_results']


@pytest.mark.asyncio
@pytest.mark.parametrize('control', ['plan_only', 'revise_plan'])
async def test_http_data_update_invalidates_stale_pending_plan_and_survives_reload(session, monkeypatch, control):
    from app.api import chat as chat_api
    from app.models.conversation import Conversation, Message
    from app.models.user import User
    from app.models.strategy_checkpoint import StrategyCheckpoint
    from app.services.strategy_checkpoint import persist_strategy_checkpoint, get_active_strategy_checkpoint
    from sqlalchemy import select
    user = User(email=f'assay-http-{control}@example.com', name='QA', hashed_password='unused')
    session.add(user)
    await session.flush()
    conv = Conversation(user_id=user.id, title='assay continuation')
    session.add(conv)
    await session.flush()
    uid, cid = user.id, conv.id
    session.add(Message(conversation_id=cid, role='user', content=ORIGIN))
    old = await persist_strategy_checkpoint(session, user_id=uid, conversation_id=cid, project_id=None,
        task_text=ORIGIN, task_fingerprint='old-task', strategy_signature='old-signature',
        plan_payload=[{'id': 1, 'tool_name': 'thermostability_candidate_workflow', 'params': {'objective': {}}}])
    await session.commit()
    async def forbidden(*args, **kwargs):
        raise AssertionError('Data-only HTTP turn may not call model, planner, or upload pre-read')
    async def no_background(**kwargs):
        # Finalization normally uses a fresh production DB connection for
        # title/wiki publishing. Persist the answer using this isolated DB.
        session.add(Message(conversation_id=cid, role='assistant', content=''.join(kwargs['full_response'])))
        await session.commit()
    monkeypatch.setattr(AgentOrchestrator, '_call_llm', forbidden)
    monkeypatch.setattr(AgentOrchestrator, '_build_pdb_preflight_summary', forbidden)
    monkeypatch.setattr(chat_api, '_finalize_chat_response', no_background)
    response = await chat_api.stream_chat(chat_api.ChatRequest(message=FULL,
        conversation_id=cid, agent_control=control), db=session, current_user={'id': uid})
    frames = ''.join([frame async for frame in response.body_iterator])
    assert '"type": "error"' not in frames
    assert '"type": "done"' in frames
    assert 'ASSAY_UPDATE' in frames
    assert await get_active_strategy_checkpoint(session, user_id=uid, conversation_id=cid) is None
    rows = (await session.execute(select(StrategyCheckpoint).where(StrategyCheckpoint.conversation_id == cid))).scalars().all()
    assert len(rows) == 1 and rows[0].id == old['id'] and rows[0].status == 'superseded'
    history = await chat_api._load_conversation_history_for_agent(session, conversation_id=cid,
        current_message_id=None, request_history=[])
    context = AgentOrchestrator._build_context_for_message('按原目标继续调用工具给我位点', history)
    assert 'source.pdb' in context and thermal_objective(context)['target_residual_activity_pct'] == 80
