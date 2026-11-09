"""Activity requests on anonymous models gather identity before ranking."""
import json

import pytest

from app.core.agent_graph import AgentOrchestrator
from app.tools.registry import ToolRegistry
from app.services.report_quality_contract import assess_enzyme_report_completion

SEQ = 'ACDEFGHIKLMNPQRSTVWY' * 3
TASK = '提高蛋白的比活力\n[Attached files:\nname: model.pdb, object_name: uploads/test/model.pdb]'


@pytest.fixture
def orch():
    ToolRegistry.discover()
    return AgentOrchestrator()


@pytest.mark.asyncio
@pytest.mark.parametrize('summary', ['', 'GMQE=0.99属于模型质量估计，不代表实验精度或活性。'])
@pytest.mark.parametrize('depth', ['fast', 'standard', 'deep'])
@pytest.mark.parametrize('restriction', ['', '仅本地分析', '不要 BLAST'])
@pytest.mark.parametrize('theoretical', [True, False])
async def test_anonymous_activity_model_gathers_evidence_before_ranking(orch, monkeypatch, depth, restriction, summary, theoretical):
    async def preflight(_):
        return {'status': 'readable', 'chain_count': 1, 'chains': [
            {'chain_id': 'B', 'sequence': SEQ, 'residue_count': len(SEQ), 'residue_range': [3, 62]}],
            'theoretical_model': {'is_theoretical': theoretical, 'source': 'SWISS-MODEL', 'templates': []},
            'nonpolymer_components': [], 'reference_binding': {'verified': False}}
    async def experience(*args):
        return ''
    monkeypatch.setattr(orch, '_build_pdb_preflight_summary', preflight)
    monkeypatch.setattr(orch, '_get_experience_hints', experience)
    monkeypatch.setattr('app.core.agent_graph._structure_runtime_capabilities',
                        lambda: {'esm2': False, 'pocket': False, 'foldseek': False})
    task = restriction + '；' + TASK
    if summary:
        task = task[:-1] + ', analysis: ' + json.dumps({'ai_summary': summary}, ensure_ascii=False) + ']'
    rows = await orch._plan_cb(task, '', [], analysis_depth=depth)
    rows = await orch._hydrate_uploaded_pdb_sequence_for_plan(rows, task)
    names = [s.tool_name for s in rows]
    assert {'structure_search_foldseek', 'residue_mapping_sifts', 'enzyme_identity_profile'} <= set(names)
    assert not {'kcat_predict', 'mutation_scan', 'mutation_priority_score', 'protein_benchmark',
                'enzyme_objective_module_plan'} & set(names)
    if restriction:
        assert 'blast_search' not in names
    else:
        assert names.index('blast_search') < names.index('enzyme_identity_profile')
        blast = next(s for s in rows if s.tool_name == 'blast_search')
        assert blast.params['sequence'] == SEQ and blast.params['chain_id'] == 'B'
        assert blast.params['sequence_provenance'] == 'pdb_coordinate_derived'
    context = orch._structure_strategy_context['uploads/test/model.pdb']
    reply = orch._build_plan_confirmation_reply(
        task, rows, research_notes='当前缺少序列，无法继续。',
        pdb_preflight=await preflight(task), strategy_context=context)
    assert '当前缺少序列' not in reply
    assert '本轮完成输入和编号检查' in reply


def rows(status='submitted'):
    return [
        {'tool_name': 'structure_search_foldseek', 'status': 'completed', 'result': json.dumps({
            'status': 'completed', 'query_structure': {'method': 'THEORETICAL MODEL (SWISS-MODEL SERVER)',
            'chain_count': 1, 'total_residues': 60, 'total_atoms': 450,
            'chains': [{'chain_id': 'B', 'residue_count': 60, 'residue_range': [3, 62]}]}})},
        {'tool_name': 'enzyme_identity_profile', 'status': 'completed', 'result': json.dumps({
            'identity_status': 'unresolved', 'guardrail': {'status': 'blocked'},
            'query': {'sequence_length': 60}, 'numbering': {'status': 'verified_for_input_sequence'}})},
        {'tool_name': 'blast_search', 'status': status, 'result': json.dumps({
            'status': status, 'task_id': 'blast-test', 'rid': 'TEST_RID',
            'stage': 'ncbi_retrying', 'status_url': '/api/tools/tasks/blast-test'})},
    ]


def test_waiting_activity_report_uses_existing_sequence_and_concrete_next_step(orch):
    report = orch._build_fallback_report(TASK, rows())
    assert '阶段进展' in report and '60 aa' in report
    assert '不需要重复上传 FASTA' in report
    assert 'blast-test' in report and '不是无同源命中' in report
    assert '底物' in report and 'U/mg' in report
    assert 'kcat 为启发式背景' not in report
    assert '能否下单' not in report and 'No-Go' not in report
    assert len(report) < 2400
    assert assess_enzyme_report_completion(report)['final_status'] == 'NEEDS_REVIEW'


def test_failed_identity_search_is_not_rendered_as_pending(orch):
    report = orch._build_fallback_report(TASK, rows('failed'))
    assert '同源检索仍在进行' not in report


def test_compacted_blocked_scan_preserves_diagnostic_reason(orch):
    payload = {'status': 'blocked', 'code': 'IDENTITY_OR_NUMBERING_NOT_CONFIRMED',
               'reason': 'Family identity has not been confirmed.'}
    compact = json.loads(orch._compact_result('mutation_scan', payload))
    assert compact['reason'] == payload['reason'] and compact['code'] == payload['code']


@pytest.mark.asyncio
async def test_confirmed_gate_is_not_reported_as_tool_failure(orch, monkeypatch):
    async def blocked(*args, **kwargs):
        return {'status': 'blocked', 'reason': 'protected catalytic sites are missing',
                'missing_evidence': ['substrate and assay conditions']}
    monkeypatch.setattr(ToolRegistry, 'execute', blocked)
    monkeypatch.setattr(orch, '_cache_get', lambda _: None)
    plan = [{'id': 1, 'tool_name': 'enzyme_objective_module_plan', 'description': 'objective gate',
             'params': {'objective': 'activity'}}]
    events = [json.loads(raw) async for raw in orch.stream_chat(
        '提高比活力 ' + SEQ, [], agent_control='execute_confirmed', confirmed_plan=plan,
        strategy_signature=orch._plan_signature(plan))]
    states = [e for e in events if e.get('type') == 'state']
    contract = states[-1]['task_contract']
    assert contract['gate_trace'] and not contract.get('fallback_trace')
    text = ''.join(e.get('content', '') for e in events if e.get('type') == 'text')
    assert '目标门控提示' in text and '执行降级提示' not in text
