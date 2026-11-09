"""Regression of the real heat-challenge goal through the chat planner."""
import importlib
import json

import pytest

from app.core.agent_graph import AgentOrchestrator
from app.services.property_workflow_governance import PropertyWorkflowRouter
from app.tools.registry import ToolRegistry

GOAL = '我需要提高该酶的热稳定性，测定条件是95度5min，我希望剩余酶活能够在60%以上，目前只有30%'
SEQ = ('ACDEFGHIKLMNPQRSTVWY' * 25)[:486]


@pytest.mark.parametrize('metric', ['剩余酶活', '残余酶活', '残余活性', '剩余活性', 'residual activity', 'remaining activity'])
def test_heat_challenge_activity_is_a_stability_endpoint(metric):
    task = GOAL.replace('剩余酶活', metric)
    assert AgentOrchestrator._classify_engineering_objectives(task) == {'thermostability'}
    assert PropertyWorkflowRouter.route(task)['workflow_id'] == 'WF-STABILITY'


def test_heat_assay_numbers_are_preserved_without_inventing_activity_retention_floor():
    objective = AgentOrchestrator._extract_assay_context(GOAL).get('thermal_objective', {})
    assert objective.get('endpoint') == 'residual_activity'
    assert objective.get('temperature_c') == 95
    assert objective.get('duration_min') == 5
    assert objective.get('baseline_residual_activity_pct') == 30
    assert objective.get('target_residual_activity_pct') == 60
    assert objective.get('target_comparator') == '>='
    assert not {'ph', 'substrate', 'method', 'min_activity_retention_pct'} & objective.keys()


@pytest.mark.parametrize('task', [
    '提高热稳定性，同时提高未加热时的比活力',
    'Improve thermal stability and independently increase specific activity',
])
def test_independent_activity_goal_needs_primary_clarification(task):
    assert AgentOrchestrator._classify_engineering_objectives(task) == {'thermostability', 'activity'}
    route = PropertyWorkflowRouter.route(task)
    assert route['status'] == 'NEEDS_INPUT' and 'primary_property' in route['input_gaps']


@pytest.mark.asyncio
@pytest.mark.parametrize('depth', ['fast', 'standard', 'deep'])
@pytest.mark.parametrize('restriction', ['', '禁止联网；', '不要BLAST；'])
@pytest.mark.parametrize('theoretical', [False, True])
async def test_chat_plan_uses_thermal_workflow_for_ordinary_and_theoretical_pdb(monkeypatch, depth, restriction, theoretical):
    ToolRegistry.discover()
    orch = AgentOrchestrator()
    async def preflight(_):
        return {'status': 'readable', 'chain_count': 1, 'coordinate_sequence': SEQ,
                'chains': [{'chain_id': 'A', 'sequence': SEQ, 'residue_count': 486}],
                'theoretical_model': {'is_theoretical': theoretical, 'templates': []},
                'reference_binding': {'verified': False}, 'nonpolymer_components': []}
    async def experience(*args):
        return ''
    monkeypatch.setattr(orch, '_build_pdb_preflight_summary', preflight)
    monkeypatch.setattr(orch, '_get_experience_hints', experience)
    monkeypatch.setattr('app.core.agent_graph._structure_runtime_capabilities', lambda: {})
    task = restriction + GOAL + '\n序列如下：\n' + SEQ + '\n[Attached files:\nname: model.pdb, object_name: uploads/test/model.pdb]'
    plan = await orch._plan_cb(task, '', [], analysis_depth=depth)
    plan = await orch._hydrate_uploaded_pdb_sequence_for_plan(plan, task)
    names = [s.tool_name for s in plan]
    assert not {'kcat_predict', 'mutation_scan', 'mutation_priority_score'} & set(names)
    assert 'thermostability_candidate_workflow' in names
    assert names.index('enzyme_identity_profile') < names.index('enzyme_objective_module_plan') < names.index('thermostability_candidate_workflow')
    if restriction:
        assert 'blast_search' not in names
    else:
        assert names.index('blast_search') < names.index('enzyme_identity_profile')
    workflow = next(s for s in plan if s.tool_name == 'thermostability_candidate_workflow')
    assert workflow.params['sequence'] == SEQ
    assert workflow.params['sequence_provenance'] == 'user_fasta_exact_pdb_match'
    assert workflow.params['objective']['temperature_c'] == 95
    assert workflow.params['objective']['target_residual_activity_pct'] == 60
    assert workflow.params.get('msa_policy', 'local') == 'local'


@pytest.mark.asyncio
async def test_registered_coordinate_scan_accepts_upload_after_legacy_import(monkeypatch):
    ToolRegistry.discover()
    importlib.reload(importlib.import_module('app.tools.stability_feature_scan'))
    pdb = 'ATOM      1  CA  ALA A   1       0.000   0.000   0.000  1.00 20.00           C\nEND\n'
    async def download(name):
        assert name == 'uploads/test/model.pdb'
        return pdb.encode()
    monkeypatch.setattr('app.services.storage.download_file', download)
    result = await ToolRegistry.execute('disulfide_saltbridge_scan', {'pdb_object_name': 'uploads/test/model.pdb', 'chain_id': 'A'})
    assert result['status'] == 'completed' and result['residue_count'] == 1


@pytest.mark.asyncio
async def test_registered_coordinate_scan_keeps_legacy_pdb_parameter():
    ToolRegistry.discover()
    pdb = 'ATOM      1  CA  ALA A   1       0.000   0.000   0.000  1.00 20.00           C\nEND\n'
    result = await ToolRegistry.execute('disulfide_saltbridge_scan', {'protein_pdb': pdb})
    assert result['status'] == 'completed' and result['residue_count'] == 1
    assert result['disulfide_geometry_candidates'] == []
    assert result['existing_salt_bridges'] == []


@pytest.mark.parametrize('text, expected', [
    ('提高热稳定性，90℃处理300秒后残余活性从30%提高到60%', 5),
    ('提高热稳定性，90℃处理0.5小时后残余活性目标60%', 30),
])
def test_heat_duration_unit_conversion(text, expected):
    objective = AgentOrchestrator._extract_assay_context(text)['thermal_objective']
    assert objective['duration_min'] == expected


def test_multiple_heating_conditions_require_clarification():
    from app.services.thermostability_workflow import assay_gaps
    objective = AgentOrchestrator._extract_assay_context('提高热稳定性，90℃和95℃处理5min后剩余酶活目标60%')['thermal_objective']
    assert 'temperature_c' not in objective
    assert objective['parsing_conflicts']['temperature_c'] == [90, 95]
    assert 'temperature_c' in assay_gaps(objective)


@pytest.mark.parametrize('text', ['提高热稳定性，保持活性不下降', '提高热稳定性，不要提高比活力'])
def test_activity_constraint_is_not_an_activity_optimization(text):
    assert AgentOrchestrator._classify_engineering_objectives(text) == {'thermostability'}


def test_protein_sequence_and_attachment_do_not_define_objectives():
    text = '提高热稳定性\n' + 'MKMTMHEATACDEFGHIKLMNPQRSTVWY' * 8 + '\n[Attached files: analysis: 活性提高]'
    assert AgentOrchestrator._classify_engineering_objectives(text) == {'thermostability'}


@pytest.mark.asyncio
async def test_signed_thermal_plan_executes_real_local_tools_and_reports_given_assay(monkeypatch):
    ToolRegistry.discover()
    sequence = 'ACDEFGHIKLMNPQRSTVWY' * 3
    from Bio.SeqUtils import seq3
    pdb = '\n'.join(f'ATOM  {i:5d}  CA  {seq3(aa).upper()} A{i:4d}    '
                    f'{i*3.:8.3f}{0.:8.3f}{0.:8.3f}{1.:6.2f}{20.:6.2f}           C'
                    for i, aa in enumerate(sequence, 1)) + '\nEND\n'
    async def download(_):
        return pdb.encode()
    async def experience(*args):
        return ''
    monkeypatch.setattr('app.services.storage.download_file', download)
    orch = AgentOrchestrator()
    monkeypatch.setattr(orch, '_get_experience_hints', experience)
    monkeypatch.setattr(orch, '_cache_get', lambda _: None)
    monkeypatch.setattr(orch, '_cache_put', lambda *args: None)
    task = '禁止联网；' + GOAL + '\n' + sequence + '\n[Attached files:\nname: model.pdb, object_name: uploads/test/model.pdb]'
    plan = await orch._plan_cb(task, '', [], analysis_depth='deep')
    plan = await orch._hydrate_uploaded_pdb_sequence_for_plan(plan, task)
    raw = [{'id': s.id, 'tool_name': s.tool_name, 'description': s.description, 'params': s.params} for s in plan]
    events = [json.loads(e) async for e in orch.stream_chat(task, [], agent_control='execute_confirmed',
        confirmed_plan=raw, strategy_signature=orch._plan_signature(raw))]
    states = [e for e in events if e.get('type') == 'state']
    results = states[-1].get('step_results', [])
    assert not any(r['status'] == 'failed' for r in results), [r for r in results if r['status'] == 'failed']
    thermal = next(r for r in results if r['tool'] == 'thermostability_candidate_workflow')
    payload = AgentOrchestrator._safe_parse_json(str(thermal['raw_result']))
    assert payload['status'] == 'partial' and payload['analysis_mode'] == 'exploration', payload
    assert payload['objective']['temperature_c'] == 95
    assert payload['objective']['duration_min'] == 5
    assert payload['objective']['baseline_residual_activity_pct'] == 30
    assert payload['objective']['target_residual_activity_pct'] == 60
    assert not {'temperature_c', 'duration_min', 'endpoint'} & set(payload['evidence_gaps'])
    assert not any(r['status'] == 'failed' for r in results), results
    report = ''.join(e.get('content', '') for e in events if e.get('type') == 'text')
    assert '热稳定性探索分析' in report and '95' in report and '60' in report
    assert 'kcat 为启发式' not in report


@pytest.mark.parametrize('text', [
    '95℃5min后剩余酶活从30%提高到60%',
    'Improve remaining activity after heating at 95°C for 5min from 30% to 60%',
])
def test_heat_challenge_implies_stability_without_explicit_stability_word(text):
    assert AgentOrchestrator._classify_engineering_objectives(text) == {'thermostability'}
    assert PropertyWorkflowRouter.route(text)['workflow_id'] == 'WF-STABILITY'


def test_explicit_activity_primary_is_respected_and_excluded_stability_is_not_a_goal():
    task = '提高热稳定性和比活力，主目标是提高比活力'
    objectives = AgentOrchestrator._classify_engineering_objectives(task)
    assert AgentOrchestrator._primary_engineering_goal(objectives, task) == 'activity'
    assert AgentOrchestrator._classify_engineering_objectives('提高比活力，不要优化热稳定性') == {'activity'}


def test_thermal_report_explains_heat_target_and_pending_identity():
    from app.services.thermostability_report import render_thermostability_results
    from app.tools.thermostability_workflow import _finish
    from app.services.thermostability_workflow import build_screen
    objective = AgentOrchestrator._extract_assay_context(GOAL)['thermal_objective']
    payload = _finish(build_screen(SEQ, objective=objective, identity_profile={'identity_status': 'unresolved'}))
    report = render_thermostability_results([
        {'tool_name': 'thermostability_candidate_workflow', 'status': 'blocked', 'result': payload},
        {'tool_name': 'blast_search', 'status': 'submitted', 'result': {'status': 'submitted', 'task_id': 'test-blast', 'rid': 'TEST'}},
    ])
    assert '95℃' in report and '5 min' in report and '30%' in report and '60%' in report
    assert 'test-blast' in report and '异步' in report
    assert '身份' in report


def test_sequence_only_thermal_dependencies_share_sequence_and_chain_scope():
    from app.core.agent_graph import PlanStep
    ToolRegistry.discover()
    orch = AgentOrchestrator()
    plan = orch._generate_fallback_plan(GOAL + '\n' + SEQ)
    identity = next(s for s in plan if s.tool_name == 'enzyme_identity_profile')
    module = next(s for s in plan if s.tool_name == 'enzyme_objective_module_plan')
    thermal = next(s for s in plan if s.tool_name == 'thermostability_candidate_workflow')
    identity.status = 'completed'; identity.result = {'identity_status': 'identified'}
    module.status = 'blocked'; module.result = {'objective': 'thermostability', 'status': 'blocked'}
    orch._bridge_step_params(thermal, [identity, module])
    assert thermal.params['identity_profile'] == identity.result
    assert thermal.params['objective_module_plan'] == module.result


def test_thermal_mapping_hydration_keeps_verified_input_to_author_rows():
    from app.core.agent_graph import PlanStep
    scope = {'pdb_object_name': 'uploads/test/model.pdb', 'chain_id': 'B'}
    thermal = PlanStep(3, 'thermostability_candidate_workflow', 'screen', {'sequence': 'ACD', 'chain_id': 'B', 'evidence_scope': scope})
    rows = [{'source_position': i, 'target_chain_id': 'B', 'target_position': i+10} for i in range(1,4)]
    mapping = PlanStep(1, 'residue_mapping_sifts', 'mapping', {**scope, 'input_sequence': 'ACD'},
                       status='completed', result={'status': 'completed', 'numbering_registry_rows': rows})
    AgentOrchestrator._hydrate_step_params(thermal, [mapping])
    assert thermal.params['mapping_rows'] == rows


def test_assay_ph_is_a_condition_of_the_heat_challenge():
    task = GOAL + '；pH7.5，测活温度37℃'
    assert AgentOrchestrator._classify_engineering_objectives(task) == {'thermostability'}
    assert PropertyWorkflowRouter.route(task)['workflow_id'] == 'WF-STABILITY'
    objective = AgentOrchestrator._extract_assay_context(task)['thermal_objective']
    assert objective['ph'] == 7.5 and objective['temperature_c'] == 95


@pytest.mark.parametrize('restriction', ['禁止联网；', '仅本地分析；', '可以联网分析；'])
def test_connectivity_permission_and_attachment_status_do_not_replace_engineering_goal(restriction):
    task = restriction + GOAL + '\n' + SEQ + '\n[Attached files:\nname: model.pdb, object_name: uploads/test/model.pdb, analysis: {"status":"当前可用"}]'
    orch = AgentOrchestrator()
    assert not orch._is_connectivity_status_request(task)
    assert 'thermostability_candidate_workflow' in [s.tool_name for s in orch._generate_fallback_plan(task)]
