"""Live conversation regressions: preserve requirements and explain actual receipts."""
from copy import deepcopy
from types import SimpleNamespace
import json

import pytest

from app.core.agent_graph import AgentOrchestrator
from app.services.enzyme_workflow_runtime import evaluate_enzyme_workflow_runtime

TASK = ('基于4UZU链A提高热稳定性，最终必须输出 10 个具体的原残基→目标残基突变。'
        '实验条件未知时按探索性候选处理。\n'
        '[Attached files: name: 4UZU.pdb, object_name: uploads/user_3/current.pdb]')


def evidence_history():
    payload = {
        'schema_version': 'thermostability_candidates_v1', 'status': 'partial',
        'analysis_mode': 'exploration', 'sequence_sha256': 'current-sequence',
        'candidate_counts': {'screened': 60, 'requested_positions': 10, 'returned_positions': 1, 'shortfall': 9},
        'structure_feature_receipt': {'status': 'completed', 'rows_evaluated': 479},
        'selection_policy': 'unique_positions_pareto_then_ddgun_then_deterministic_order',
        'branches': {'ddgun': {'status': 'completed', 'algorithm_commit': 'real-test-version',
                               'database_version': 'real-test-database'},
                     'esm': {'status': 'blocked', 'blocked_reason': 'runtime_unavailable'}},
        'preliminary_candidates': [{
            'mutation': 'A421V', 'position': 421, 'wild_type': 'A', 'mutant': 'V',
            'structure_position': {'chain_id': 'A', 'residue_number': 424},
            'sources': [{'kind': 'coordinate_packing_probe', 'sequence_sha256': 'current-sequence',
                         'reference': 'build_site_structure_function_features',
                         'features': {'rel_sasa': 0.0, 'contact_count_ca_8a': 13}}],
            'scores': {'ddgun': {'ddg': 2.3, 'unit': 'kcal/mol'}, 'esm_preference': None},
            'risks': ['incomplete_functional_protection']}],
        'candidates': [], 'experimental_plan': {}}
    return [{'role': 'user', 'content': TASK},
            {'role': 'assistant', 'content': '热稳定性工具报告', 'tool_evidence': [
                {'tool_name': 'thermostability_candidate_workflow', 'status': 'completed', 'result': payload},
                {'tool_name': 'blast_search', 'status': 'submitted',
                 'result': {'task_id': 'test-original-task', 'rid': 'ORIGINAL-RID', 'status': 'waiting'}}]}]


@pytest.mark.asyncio
@pytest.mark.parametrize('question,expected', [
    ('你这些位点的逻辑是啥？走的是哪条路线？', ['堆积', 'SASA', 'DDGun', '479', '2.3']),
    ('这些位点是LLM通识输出，还是你真正调用工具后输出的？', ['执行回执', 'DDGun', '60', 'ESM', 'blocked']),
    ('解释作者编号A424V的依据', ['A421V', '424', '2.3']),
])
async def test_receipt_questions_answer_from_evidence_without_model_or_tools(monkeypatch, question, expected):
    agent = AgentOrchestrator()
    async def forbidden(*args, **kwargs):
        raise AssertionError('Receipt explanation must not require LLM or new computation')
    monkeypatch.setattr(agent, '_call_llm', forbidden)
    reply = await agent._chat_reply(question, evidence_history())
    for fact in expected:
        assert fact in reply
    assert '实验' in reply and '未验证' in reply
    assert '本轮是解释' not in reply
    assert 'BLAST' in reply and '等待' in reply


@pytest.mark.asyncio
async def test_unsupported_model_mutation_falls_back_to_actual_evidence(monkeypatch):
    agent = AgentOrchestrator()
    async def invented(*args, **kwargs):
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content='另推荐 D51N'))])
    monkeypatch.setattr(agent, '_call_llm', invented)
    reply = await agent._chat_reply('这份结果还有哪些限制？', evidence_history())
    assert 'D51N' not in reply
    assert 'DDGun' in reply and '2.3' in reply


@pytest.mark.asyncio
@pytest.mark.parametrize('change', ['new_task', 'new_upload', 'new_sequence', 'pending_receipt', 'newer_failed_receipt'])
async def test_explanation_does_not_reuse_foreign_or_unexecuted_receipts(monkeypatch, change):
    history = evidence_history()
    if change == 'new_task':
        history.append({'role': 'user', 'content': '新任务：提高另一个酶的热稳定性'})
    elif change == 'new_upload':
        history.append({'role': 'user', 'content': '[Attached files: object_name: uploads/user_3/other.pdb]'})
    elif change == 'new_sequence':
        history += [{'role': 'user', 'content': '序列：MKTIIALSYIFCLVFADYKDDDDK'},
                    {'role': 'user', 'content': '序列：ACDEFGHIKLMNPQRSTVWYACDEFGHIK'}]
    elif change == 'pending_receipt':
        history[1]['tool_evidence'][0]['status'] = 'pending'
    else:
        receipt = deepcopy(history[1])
        receipt['tool_evidence'][0]['status'] = 'failed'
        receipt['tool_evidence'][0]['result']['status'] = 'blocked'
        history.append(receipt)
    agent = AgentOrchestrator()
    async def invented(*args, **kwargs):
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content='A421V DDGun 2.3'))])
    monkeypatch.setattr(agent, '_call_llm', invented)
    reply = await agent._chat_reply('这些位点是实际调用工具的结果吗？', history)
    assert 'A421V' not in reply and '2.3' not in reply
    assert '回执' in reply


@pytest.mark.parametrize('message,budget', [
    ('那你得对应上平台现有的工具啊？你对应后做一下', 10),
    ('只要8个，按刚才目标继续调用工具给我位点', 8),
    ('请按原目标继续，输出5个具体的原残基到目标残基替换位点', 5),
])
def test_count_survives_explanations_and_latest_edit_wins(message, budget):
    history = evidence_history()
    for _ in range(16):
        history += [{'role': 'user', 'content': '解释计算依据'}, {'role': 'assistant', 'content': '研究假设'}]
    context = AgentOrchestrator._build_context_for_message(message, history)
    assert f'输出{budget}个突变位点' in context
    assert 'current.pdb' in context and '热稳定' in context
    contract = evaluate_enzyme_workflow_runtime(message, history)
    assert contract['intent'] == 'TASK_EXTENSION'
    assert contract['workflow_id'] == 'WF-STABILITY'


def test_question_about_wrong_count_does_not_replace_original_requirement():
    history = evidence_history() + [
        {'role': 'user', 'content': '为什么报告输出12个候选？我没有让你改数量'},
        {'role': 'assistant', 'content': '数量不一致'}]
    context = AgentOrchestrator._build_context_for_message('继续按原目标输出位点', history)
    assert '输出10个突变位点' in context


@pytest.mark.asyncio
async def test_old_receipt_count_mismatch_is_acknowledged_without_rewriting_evidence():
    history = evidence_history()
    counts = history[1]['tool_evidence'][0]['result']['candidate_counts']
    counts.update(requested_positions=12, returned_positions=12, shortfall=0)
    reply = await AgentOrchestrator()._chat_reply('这些候选到底依据什么？', history)
    assert '10' in reply and '12' in reply and '不一致' in reply
    assert counts['requested_positions'] == 12


@pytest.mark.parametrize('message', [
    '请结合平台现有工具重新计算一下',
    '按平台现有的工具跑一遍',
    '你得先匹配可用工具，然后实际执行',
])
def test_clear_tool_execution_phrases_retain_existing_task(message):
    contract = evaluate_enzyme_workflow_runtime(message, evidence_history())
    assert contract['intent'] == 'TASK_EXTENSION'
    assert contract['workflow_id'] == 'WF-STABILITY'


@pytest.mark.asyncio
async def test_actual_followup_stream_explains_then_offers_signed_continuation(monkeypatch):
    from app.tools.registry import ToolRegistry
    ToolRegistry.discover()
    history = evidence_history()
    agent = AgentOrchestrator()
    async def no_model(*args, **kwargs):
        raise AssertionError('No model needed for receipt review or deterministic plan')
    async def empty(*args, **kwargs): return ''
    async def preflight(_):
        return {'status': 'readable', 'chain_count': 1, 'coordinate_sequence': 'ACDEFGHIKLMNPQRSTVWY',
                'chains': [{'chain_id': 'A', 'sequence': 'ACDEFGHIKLMNPQRSTVWY', 'residue_count': 20}],
                'theoretical_model': {'is_theoretical': False, 'templates': []},
                'reference_binding': {'verified': False}, 'nonpolymer_components': []}
    async def download(name):
        assert name == 'uploads/user_3/current.pdb'
        return (''.join(f'ATOM  {i:5d}  CA  {aa} A{i+3:4d}    {i*3.:8.3f}{0.:8.3f}{0.:8.3f}  1.00 20.00           C\n'
                        for i, aa in enumerate(['ALA', 'CYS', 'ASP', 'GLU', 'PHE', 'GLY', 'HIS', 'ILE', 'LYS', 'LEU',
                                                'MET', 'ASN', 'PRO', 'GLN', 'ARG', 'SER', 'THR', 'VAL', 'TRP', 'TYR'], 1)) + 'END\n').encode()
    monkeypatch.setattr('app.services.storage.download_file', download)
    monkeypatch.setattr(agent, '_call_llm', no_model)
    monkeypatch.setattr(agent, '_get_experience_hints', empty)
    monkeypatch.setattr(agent, '_research_pi', empty)
    monkeypatch.setattr(agent, '_build_pdb_preflight_summary', preflight)
    for question in ['你这些位点的逻辑是啥？走的是哪条路线？',
                     '这些位点是LLM通识输出，还是你真正调用工具后输出的？']:
        events = [json.loads(e) async for e in agent.stream_chat(question, history, agent_control='plan_only')]
        reply = ''.join(e.get('content', '') for e in events if e.get('type') == 'text')
        assert 'DDGun' in reply and 'A421V' in reply
        assert not any(e.get('waiting_for') == 'strategy_confirmation' for e in events)
        history += [{'role': 'user', 'content': question}, {'role': 'assistant', 'content': reply}]
    question = '那你得对应上平台现有的工具啊？你对应后做一下'
    events = [json.loads(e) async for e in agent.stream_chat(question, history, agent_control='plan_only')]
    state = [e for e in events if e.get('type') == 'state'][-1]
    workflows = [s for s in state['plan'] if s['tool_name'] == 'thermostability_candidate_workflow']
    assert workflows, json.dumps(events, ensure_ascii=False)
    workflow = workflows[0]
    assert workflow['params']['assay_budget'] == 10
    assert state['strategy_signature']
    assert not state['step_results']
    assert 'blast_search' not in [s['tool_name'] for s in state['plan']]
