"""Regressions from the 479-residue uploaded-structure conversation."""
import json

import pytest

from app.core.agent_graph import AgentOrchestrator
from app.services.engineering_goal_semantics import merge_thermal_assay, thermal_objective
from app.services.enzyme_task_context import protein_reference
from app.services.enzyme_workflow_runtime import evaluate_enzyme_workflow_runtime
from app.services.property_workflow_governance import PropertyWorkflowRouter
from app.services.thermostability_workflow import assay_gaps

ASSAY = ('热稳定性评价指标：剩余酶活（热处理后酶活与未处理样品的比值）；处理条件：95度，5min；'
         '当前残余酶活：30%；目标残余酶活：80%；未加热酶活保持比例：80%以上；测定pH：4.5-4.8\n'
         '酶活测定方法：国标法；测定底物：可溶性淀粉；缓冲液：磷酸盐缓冲液；辅因子：Ca离子；')
HISTORY = [{'role': 'user', 'content': '我想要提高该酶的热稳定性，必须输出10个突变位点给到我\n'
            '[Attached files:\nname: 4UZU.pdb, object_name: uploads/user_3/test.pdb]'},
           {'role': 'assistant', 'content': '热稳定性探索分析：还未生成具体候选。'}]


def test_assay_substrate_and_activity_floor_do_not_change_engineering_goal():
    route = PropertyWorkflowRouter.route(ASSAY)
    assert route['optimization_targets'] == ['stability']
    contract = evaluate_enzyme_workflow_runtime(ASSAY, HISTORY)
    assert contract['intake_status'] == 'READY_FOR_ANALYSIS'
    assert contract['workflow_id'] == 'WF-STABILITY'
    assert 'structure' in contract['known_inputs']
    assert protein_reference(ASSAY) == ''


def test_main_planner_classification_uses_labelled_assay_semantics():
    assert AgentOrchestrator._classify_engineering_objectives(ASSAY) == {'thermostability'}
    assert AgentOrchestrator._classify_engineering_objectives(
        ASSAY + '\n另外提高可溶表达量') == {'thermostability', 'solubility'}


@pytest.mark.asyncio
async def test_full_supplement_plan_keeps_thermal_workflow(monkeypatch):
    from app.tools.registry import ToolRegistry
    ToolRegistry.discover()
    agent = AgentOrchestrator()
    async def hints(*args): return ''
    async def preflight(_):
        return {'status': 'readable', 'chain_count': 1, 'coordinate_sequence': 'ACDEG',
                'chains': [{'chain_id': 'A', 'sequence': 'ACDEG', 'residue_count': 5}],
                'theoretical_model': {'is_theoretical': False, 'templates': []},
                'reference_binding': {'verified': False}, 'nonpolymer_components': []}
    monkeypatch.setattr(agent, '_get_experience_hints', hints)
    monkeypatch.setattr(agent, '_build_pdb_preflight_summary', preflight)
    context = agent._build_context_for_message(ASSAY, HISTORY)
    plan = await agent._plan_cb(ASSAY, '', HISTORY, context=context)
    workflow = next(s for s in plan if s.tool_name == 'thermostability_candidate_workflow')
    assert workflow.params['assay_budget'] == 10
    assert workflow.params['objective']['ph_range'] == [4.5, 4.8]
    assert workflow.params['objective']['target_residual_activity_pct'] == 80
    assert 'mutation_priority_score' not in [s.tool_name for s in plan]


@pytest.mark.asyncio
async def test_explicit_ten_concrete_substitutions_sets_candidate_budget(monkeypatch):
    from app.tools.registry import ToolRegistry
    ToolRegistry.discover()
    agent = AgentOrchestrator()
    async def hints(*args): return ''
    async def preflight(_):
        return {'status': 'readable', 'chain_count': 1, 'coordinate_sequence': 'ACDEG',
                'chains': [{'chain_id': 'A', 'sequence': 'ACDEG', 'residue_count': 5}],
                'theoretical_model': {'is_theoretical': False, 'templates': []},
                'reference_binding': {'verified': False}, 'nonpolymer_components': []}
    monkeypatch.setattr(agent, '_get_experience_hints', hints)
    monkeypatch.setattr(agent, '_build_pdb_preflight_summary', preflight)
    task = ('基于已上传的 4UZU 链 A，按 PDB 作者编号执行热稳定性突变设计。'
            '最终必须输出 10 个具体的原残基→目标残基突变。实验条件未知时按探索性候选处理。\n'
            '[Attached files: name: 4UZU.pdb, object_name: uploads/user_3/test.pdb]')
    plan = await agent._plan_cb(task, '', [], context='')
    workflow = next(s for s in plan if s.tool_name == 'thermostability_candidate_workflow')
    assert workflow.params['assay_budget'] == 10


@pytest.mark.parametrize('value', ['5min', '5MIN', '2hrs', '1sec', '95度5min'])
def test_durations_are_not_structure_accessions(value):
    assert protein_reference(value) == ''


def test_ph_range_is_preserved_and_later_scalar_or_unknown_replaces_it():
    objective = thermal_objective(ASSAY)
    assert objective.get('ph_range') == [4.5, 4.8]
    assert 'ph' not in objective
    assert assay_gaps(objective) == []
    for later, expected in [('pH改为6.5', 6.5), ('pH：未知', None)]:
        merged = merge_thermal_assay([ASSAY, later])
        assert merged.get('ph') == expected and 'ph_range' not in merged


@pytest.mark.parametrize('message', [
    '你是完全基于你的LLM通识训练找的这些位点吧？？我真正想要的是你去调用工具后，结合工具结果给我输出位点',
    '那你继续，直到给我输出突变位点为止',
    '那你得对应上平台现有的工具啊？你对应后做一下',
])
def test_tool_backed_site_request_retains_thermal_task(message):
    contract = evaluate_enzyme_workflow_runtime(message, HISTORY)
    assert contract['intent'] == 'TASK_EXTENSION'
    assert contract['workflow_id'] == 'WF-STABILITY'
    context = AgentOrchestrator._build_context_for_message(message, HISTORY)
    assert '热稳定性' in context
    assert '10' in context


@pytest.mark.parametrize('message', [
    '不要调用工具做计算，只解释已有结果',
    '你使用了什么工具做分析？',
    '你对应上平台现有的工具做过计算吗？',
])
def test_tool_provenance_questions_and_no_tool_requests_remain_non_execution(message):
    contract = evaluate_enzyme_workflow_runtime(message, HISTORY)
    assert contract['intent'] == 'NON_EXECUTION'


@pytest.mark.asyncio
async def test_input_only_structure_reaches_thermal_mapping(monkeypatch):
    from app.tools.structure_search_foldseek import structure_search_foldseek
    from app.core.agent_graph import PlanStep
    pdb = ''.join(f'ATOM  {i:5d}  CA  {aa} A{i+3:4d}    {i*3.:8.3f}{0.:8.3f}{0.:8.3f}  1.00 20.00           C\n'
                  for i, aa in enumerate(['ALA', 'CYS', 'ASP'], 1))+'END\n'
    async def download(_):
        return pdb.encode()
    monkeypatch.setattr('app.services.storage.download_file', download)
    obj = 'uploads/user_3/test.pdb'
    payload = await structure_search_foldseek(pdb_object_name=obj, search_mode='input_only')
    previous = PlanStep(1, 'structure_search_foldseek', 'read', {'pdb_object_name': obj}, status='completed', result=payload)
    target = PlanStep(2, 'thermostability_candidate_workflow', 'thermal',
                      {'pdb_object_name': obj, 'sequence': 'ACD', 'chain_id': 'A'})
    AgentOrchestrator._hydrate_step_params(target, [previous])
    assert target.params.get('pdb_data', '').startswith('ATOM')
    assert target.params['sequence'] == 'ACD'


def test_thermal_evidence_remains_valid_json_with_every_selected_candidate():
    from app.core.agent_graph import ChatSnapshot
    agent = AgentOrchestrator()
    agent._snapshot = ChatSnapshot(stage='done')
    rows = [{'mutation': f'A{i}V', 'position': i, 'sources': [{'reference': 'coordinates'}],
             'scores': {'ddgun': {'ddg': .5}}, 'risks': ['review']} for i in range(1, 11)]
    payload = {'schema_version': 'thermostability_candidates_v1', 'status': 'partial',
               'analysis_mode': 'exploration', 'sequence_sha256': 'exact-sequence',
               'preliminary_candidates': rows, 'screened_candidates': rows * 6,
               'branches': {'ddgun': {'status': 'completed', 'response_sha256': 'receipt'}},
               'report_markdown': 'r' * 10000}
    raw = json.dumps(payload)
    agent._snapshot.step_results = [{'tool': 'thermostability_candidate_workflow', 'status': 'completed', 'raw_result': raw}]
    saved = json.loads(agent.get_checkpoint_execution_summary()['step_results'][0]['raw_result'])
    model = json.loads(agent._format_tool_result_for_synthesis({'tool_name': 'thermostability_candidate_workflow', 'result': raw}))
    for evidence in [saved, model]:
        assert len(evidence['preliminary_candidates']) == 10
        assert evidence['preliminary_candidates'][-1]['mutation'] == 'A10V'
        assert evidence['branches']['ddgun']['response_sha256'] == 'receipt'


def test_large_feature_summary_is_valid_and_keeps_full_artifact_reference():
    from app.core.agent_graph import ChatSnapshot
    agent = AgentOrchestrator()
    agent._snapshot = ChatSnapshot(stage='done')
    payload = {'status': 'completed', 'feature_count': 479, 'features': [{'position': i, 'data': 'x'*150} for i in range(20)],
               'full_features_download_status': 'ready', 'full_features_download_url': '/api/files/full-features.json'}
    raw = json.dumps(payload)
    agent._snapshot.step_results = [{'tool': 'build_site_structure_function_features', 'raw_result': raw}]
    saved = json.loads(agent.get_checkpoint_execution_summary()['step_results'][0]['raw_result'])
    model = json.loads(agent._format_tool_result_for_synthesis({'tool_name': 'build_site_structure_function_features', 'result': raw}))
    for receipt in [saved, model]:
        assert receipt['feature_count'] == 479
        assert receipt['full_features_download_status'] == 'ready'
    assert model['full_features_download_url'] == '/api/files/full-features.json'
    assert saved['full_features_download_url'] == '[download-url]'


def test_coordinate_handoff_does_not_bloat_or_break_persisted_structure_receipt():
    payload = {'status': 'completed', 'pdb_content': 'ATOM'+(' ' * 160000),
               'query_structure': {'total_residues': 479}, 'search_executed': False}
    compact = json.loads(AgentOrchestrator._compact_result('structure_search_foldseek', payload))
    assert 'pdb_content' not in compact
    assert compact['query_structure']['total_residues'] == 479


@pytest.mark.asyncio
async def test_explanation_cannot_invent_uncomputed_substitutions(monkeypatch):
    from types import SimpleNamespace
    agent = AgentOrchestrator()
    async def ungrounded(*args, **kwargs):
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content='当然可以，建议 D51N、N25D。'))])
    monkeypatch.setattr(agent, '_call_llm', ungrounded)
    reply = await agent._chat_reply('你一定要补全这些信息才能输出吗？？', HISTORY)
    assert 'D51N' not in reply and 'N25D' not in reply
    assert '工具' in reply and '实验条件' in reply


@pytest.mark.asyncio
@pytest.mark.parametrize('message', [
    '那你继续，直到给我输出突变位点为止',
    '那你得对应上平台现有的工具啊？你对应后做一下',
])
async def test_continuing_candidate_work_does_not_submit_duplicate_blast(monkeypatch, message):
    from app.tools.registry import ToolRegistry
    ToolRegistry.discover()
    agent = AgentOrchestrator()
    async def hints(*args): return ''
    monkeypatch.setattr(agent, '_get_experience_hints', hints)
    history = HISTORY + [{'role': 'assistant', 'content': '后台等待', 'tool_evidence': [
        {'tool_name': 'blast_search', 'status': 'submitted', 'result': {'task_id': 'original-blast', 'rid': 'OLD'}}]}]
    context = agent._build_context_for_message(message, history)
    async def preflight(_):
        return {'status': 'readable', 'chain_count': 1, 'coordinate_sequence': 'ACDEG',
                'chains': [{'chain_id': 'A', 'sequence': 'ACDEG', 'residue_count': 5}],
                'theoretical_model': {'is_theoretical': False, 'templates': []},
                'reference_binding': {'verified': False}, 'nonpolymer_components': []}
    monkeypatch.setattr(agent, '_build_pdb_preflight_summary', preflight)
    plan = await agent._plan_cb(message, '', history, context=context)
    assert 'blast_search' not in [s.tool_name for s in plan]
    workflow = next(s for s in plan if s.tool_name == 'thermostability_candidate_workflow')
    assert workflow.params['assay_budget'] == 10


@pytest.mark.asyncio
async def test_ordered_tools_emit_running_progress_before_a_slow_tool_finishes(monkeypatch):
    import asyncio
    from app.tools.registry import ToolRegistry
    ToolRegistry.discover()
    agent = AgentOrchestrator()
    gate = asyncio.Event()
    tool = ToolRegistry._tools['predict_properties']
    async def slow(sequence):
        await gate.wait()
        return {'status': 'completed', 'length': len(sequence)}
    monkeypatch.setattr(tool, 'handler', slow)
    monkeypatch.setattr(tool, 'is_async', True)
    monkeypatch.setattr(agent, '_cache_get', lambda _: None)
    monkeypatch.setattr(agent, '_cache_put', lambda *args: None)
    monkeypatch.setattr(agent, '_requires_ordered_execution', lambda _: True)
    raw = [{'id': 1, 'tool_name': 'predict_properties', 'description': 'properties',
            'params': {'sequence': 'ACDEFGHIKLMNPQRSTVWY'}}]
    async def collect():
        async for event in agent.stream_chat('分析序列 ACDEFGHIKLMNPQRSTVWY', [], agent_control='execute_confirmed',
                    confirmed_plan=raw, strategy_signature=agent._plan_signature(raw)):
            data = json.loads(event)
            if any(s.get('status') == 'running' for s in data.get('plan', [])):
                assert not gate.is_set()
                gate.set()
                return
    await asyncio.wait_for(collect(), timeout=1)
