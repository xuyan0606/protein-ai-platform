"""Exercise the real planning entry point across goals and uploaded structures."""
import copy
import asyncio
import json

import pytest

from app.core.agent_graph import AgentOrchestrator


def message(goal, name='sample.pdb'):
    return f'{goal}\n[Attached files:\nname: {name}, object_name: uploads/user_999/sample.pdb]'


@pytest.fixture
def planner(monkeypatch):
    orch = AgentOrchestrator()
    structure = {
        'status': 'readable', 'display_name': 'sample.pdb', 'chain_count': 1,
        'total_residues': 30, 'total_atoms': 120, 'method': 'X-RAY DIFFRACTION',
        'chains': [{'chain_id': 'B', 'sequence': 'ACDEFGHIKLMNPQRSTVWYACDEFGHIKLM',
                    'residue_count': 30, 'residue_range': [11, 40]}],
        'nonpolymer_components': [], 'disulfide_count': 0,
    }
    structure['coordinate_sequence'] = structure['chains'][0]['sequence']

    async def preflight(task):
        return copy.deepcopy(structure)

    async def experience(*args):
        return ''

    monkeypatch.setattr(orch, '_build_pdb_preflight_summary', preflight)
    monkeypatch.setattr(orch, '_get_experience_hints', experience)
    monkeypatch.setattr('app.core.agent_graph._structure_runtime_capabilities',
                        lambda: {'foldseek': False, 'pocket': False, 'esm2': False}, raising=False)
    return orch, structure


async def plan(orch, goal):
    return await orch._plan_cb(message(goal), '', [], analysis_depth='deep')


async def test_quality_only_does_not_launch_function_prediction_or_ncbi(planner):
    orch, _ = planner
    rows = await plan(orch, '只检查结构质量、缺失残基和坐标编号')
    names = {s.tool_name for s in rows}
    assert names.isdisjoint({'blast_search', 'enzyme_function', 'annotation_bundle',
                             'protein_benchmark', 'ligand_contact_analysis',
                             'structure_pocket_interface_analysis'})
    assert 'build_site_structure_function_features' in names
    assert all(s.params.get('chain_id') != 'A' for s in rows)


async def test_deep_unliganded_single_chain_avoids_empty_contact_tools(planner):
    orch, _ = planner
    rows = await plan(orch, '给我深度分析')
    assert not {'ligand_contact_analysis', 'structure_pocket_interface_analysis'} & {s.tool_name for s in rows}
    assert all(s.params.get('chain_id') in (None, 'B') for s in rows)


async def test_glycan_structure_has_contact_review_not_fake_substrate_pocket(planner):
    orch, structure = planner
    structure['nonpolymer_components'] = [{'component_id': 'NAG', 'chain_id': 'G', 'residue_number': 1}]
    rows = await plan(orch, '给我深度分析')
    assert 'ligand_contact_analysis' in {s.tool_name for s in rows}
    assert 'structure_pocket_interface_analysis' not in {s.tool_name for s in rows}
    contact = next(s for s in rows if s.tool_name == 'ligand_contact_analysis')
    assert '糖' in contact.description


async def test_stability_and_family_requests_produce_different_work(planner):
    orch, _ = planner
    stability = await plan(orch, '分析热稳定性和二硫键，暂不设计突变')
    family = await plan(orch, '用 BLAST 分析家族和同源保守性')
    assert 'disulfide_saltbridge_scan' in {s.tool_name for s in stability}
    assert 'blast_search' not in {s.tool_name for s in stability}
    assert 'blast_search' in {s.tool_name for s in family}
    assert 'disulfide_saltbridge_scan' not in {s.tool_name for s in family}


async def test_local_structure_report_does_not_wait_for_model(planner, monkeypatch):
    orch, _ = planner
    task = message('不要 BLAST，但要分析热稳定性；仅本地分析。')
    rows = await plan(orch, '不要 BLAST，但要分析热稳定性；仅本地分析。')
    results = [
        {'tool_name': row.tool_name, 'status': 'completed',
         'result': json.dumps({'status': 'completed', 'total_residues': 30})}
        for row in rows
    ]
    called = []

    async def unexpected_call(*args, **kwargs):
        called.append(True)
        raise AssertionError('Completed local evidence must render without model latency')

    monkeypatch.setattr(orch, '_call_llm', unexpected_call)
    monkeypatch.setattr(orch, '_get_knowledge_context', unexpected_call)
    report = await orch._synthesize_sc(task, results, '', [])
    assert not called
    assert '按问题回答' in report
    assert '热稳定性' in report


async def test_multichain_plan_binds_each_chain_sequence_and_interface_scope(planner):
    orch, structure = planner
    structure['chain_count'] = 2
    structure['chains'].append({'chain_id': 'C', 'sequence': 'M' * 25,
                                'residue_count': 25, 'residue_range': [1, 25]})
    task = message('深度分析这个复合物的链界面和序列性质')
    rows = await orch._plan_cb(task, '', [], analysis_depth='deep')
    rows = await orch._hydrate_uploaded_pdb_sequence_for_plan(rows, task)
    mappings = [s for s in rows if s.tool_name == 'residue_mapping_sifts']
    assert {s.params['chain_id']: s.params['input_sequence'] for s in mappings} == {
        'B': structure['chains'][0]['sequence'], 'C': 'M' * 25,
    }
    interface = next(s for s in rows if s.tool_name == 'structure_pocket_interface_analysis')
    assert interface.params['chain_scope'] == ['B', 'C']
    assert interface.params['analysis_scope'] == 'interfaces'


async def test_explicit_chain_and_no_external_search_are_respected(planner):
    orch, structure = planner
    structure['chain_count'] = 2
    structure['chains'].append({'chain_id': 'C', 'sequence': 'M' * 25,
                                'residue_count': 25, 'residue_range': [1, 25]})
    rows = await plan(orch, '只分析 C 链结构质量，不要联网检索')
    assert all(s.params.get('chain_id') in (None, 'C') for s in rows)
    assert 'blast_search' not in {s.tool_name for s in rows}
    parse = next(s for s in rows if s.tool_name == 'structure_search_foldseek')
    assert parse.params['search_mode'] == 'input_only'


async def test_confirmation_explains_selected_work_and_preflight_truthfully(planner):
    orch, structure = planner
    task = message('只检查结构质量')
    rows = await orch._plan_cb(task, '', [], analysis_depth='deep')
    reply = orch._build_plan_confirmation_reply(task, rows, pdb_preflight=structure)
    assert '平台人工分析流程 v1' not in reply
    assert '已完成结构预读' in reply
    assert '结构质量' in reply


@pytest.mark.parametrize('depth', ['fast', 'standard', 'deep'])
async def test_explicit_candidates_include_required_foundation_at_every_depth(planner, depth):
    orch, _ = planner
    task = message('分析链B热稳定性，不要BLAST；增加哪些位点可突变成什么氨基酸')
    rows = await orch._plan_cb(task, '', [], analysis_depth=depth)
    rows = await orch._hydrate_uploaded_pdb_sequence_for_plan(rows, task)
    names = {row.tool_name for row in rows}
    assert {'enzyme_identity_profile', 'enzyme_objective_module_plan', 'thermostability_candidate_workflow'} <= names
    assert 'blast_search' not in names
    candidate = next(row for row in rows if row.tool_name == 'thermostability_candidate_workflow')
    assert candidate.params['chain_id'] == 'B'
    assert candidate.params['sequence']


async def test_readable_pdb_confirmation_does_not_show_generic_missing_input_research(planner):
    orch, structure = planner
    task = message('只检查结构质量，不要联网')
    rows = await orch._plan_cb(task, '尚未提供结构文件，无法给出实际质量结论。', [], analysis_depth='deep')
    reply = orch._build_plan_confirmation_reply(
        task, rows,
        research_notes='尚未提供结构文件，无法给出实际质量结论。',
        pdb_preflight=structure,
    )
    assert '已预读上传结构' in reply
    assert '尚未提供结构文件' not in reply
    assert '为什么执行' in reply
    assert '链 B' in reply
    assert 'BLAST' in reply and ('不执行' in reply or '未选择' in reply)


async def test_same_request_is_reproducible_and_changes_are_signed(planner):
    orch, _ = planner
    qc = await plan(orch, '只检查结构质量')
    repeat = await plan(orch, '只检查结构质量')
    homology = await plan(orch, 'BLAST 同源检索')
    assert orch._plan_signature(qc) == orch._plan_signature(repeat)
    assert orch._plan_signature(qc) != orch._plan_signature(homology)


async def test_missing_runtime_is_deferred_instead_of_scheduled(planner):
    orch, structure = planner
    task = message('用 ESM-2 预测功能并用 fpocket 找口袋')
    rows = await orch._plan_cb(task, '', [], analysis_depth='deep')
    assert not {'enzyme_function', 'pocket_residue_lookup'} & {s.tool_name for s in rows}
    reply = orch._build_plan_confirmation_reply(task, rows, pdb_preflight=structure)
    assert 'ESM-2' in reply and 'fpocket' in reply
    assert '暂不执行' in reply


async def test_engineering_keeps_candidate_gates_but_adapts_chain_and_components(planner):
    orch, structure = planner
    rows = await plan(orch, '提高热稳定性，设计突变')
    names = {s.tool_name for s in rows}
    assert {'enzyme_identity_profile', 'enzyme_objective_module_plan', 'thermostability_candidate_workflow'} <= names
    assert not {'ligand_contact_analysis', 'structure_pocket_interface_analysis', 'enzyme_function'} & names
    assert all(s.params.get('chain_id') in (None, 'B') for s in rows)
    identity = next(s for s in rows if s.tool_name == 'enzyme_identity_profile')
    candidate = next(s for s in rows if s.tool_name == 'thermostability_candidate_workflow')
    assert identity.id < candidate.id


async def test_multichain_engineering_requires_a_target_chain(planner):
    orch, structure = planner
    structure['chain_count'] = 2
    structure['chains'].append({'chain_id': 'C', 'sequence': 'M' * 25, 'residue_count': 25})
    rows = await plan(orch, '提高热稳定性，设计突变')
    assert not rows  # Do not silently design mutations for an arbitrary chain.
    context = orch._structure_strategy_context['uploads/user_999/sample.pdb']
    assert '改造链' in context['error']


async def test_interface_scope_works_without_a_bound_ligand():
    from app.tools.structure_pocket_interface_analysis import structure_pocket_interface_analysis

    pdb = ('ATOM      1  CA  ALA B   1       0.000   0.000   0.000  1.00 10.00           C  \n'
           'ATOM      2  CA  ALA C   1       4.000   0.000   0.000  1.00 10.00           C  \n')
    result = await structure_pocket_interface_analysis(pdb_data=pdb, chain_scope=['B', 'C'], analysis_scope='interfaces')
    assert result['status'] == 'completed'
    assert result['chain_interfaces'][0]['chain_ids'] == ['B', 'C']
    assert result['pocket']['status'] == 'not_requested'


async def test_input_only_parser_never_attempts_a_foldseek_search(monkeypatch):
    from app.tools import structure_search_foldseek as tool

    async def forbidden(*args, **kwargs):
        pytest.fail('Input-only quality inspection must not perform remote/cache/search I/O')

    monkeypatch.setattr(tool, 'get_cached_result', forbidden)
    monkeypatch.setattr(tool, '_run_local_foldseek_search', forbidden)
    row = await tool.structure_search_foldseek(pdb_data='HEADER    TEST\n', search_mode='input_only')
    assert row['status'] == 'completed'
    assert row['search_executed'] is False
    assert row['capability_status'] == 'structure_input_qc'


def test_coordinate_geometry_does_not_require_uniprot_projection_gate():
    from app.services.tool_orchestration_contract import validate_tool_plan

    result = validate_tool_plan([
        {'tool_name': 'build_site_structure_function_features', 'params': {'pdb_object_name': 'upload', 'chain_id': 'B'}},
    ], evidence={'has_pdb': True}, enforce_dependency_order=True)
    assert result['allowed'], result
    # Projection requests still need a verified numbering decision.
    projected = validate_tool_plan([
        {'tool_name': 'build_site_structure_function_features', 'params': {'pdb_object_name': 'upload', 'catalytic_positions': [105]}},
    ], evidence={'has_pdb': True}, enforce_dependency_order=True)
    assert any(v.get('dependency') == 'numbering' for v in projected['violations'])


async def test_negated_search_does_not_turn_quality_task_into_family_analysis(planner):
    orch, _ = planner
    rows = await plan(orch, '只检查结构质量，不要 BLAST 同源检索')
    assert not {'enzyme_identity_profile', 'blast_search'} & {s.tool_name for s in rows}


def test_esm_readiness_requires_configured_weights_and_fair_esm(monkeypatch, tmp_path):
    from app.services import structure_strategy as strategy
    from app.ml.config import ml_settings

    monkeypatch.setenv('TORCH_HOME', str(tmp_path))
    monkeypatch.setattr(ml_settings, 'ESM2_MODEL', 'esm2_t6_8M_UR50D')
    cache = tmp_path / 'hub/checkpoints'
    cache.mkdir(parents=True)
    (cache / 'esm2_t33_650M_UR50D.pt').touch()
    monkeypatch.setattr(strategy.importlib.util, 'find_spec', lambda name: object())
    assert not strategy.structure_runtime_capabilities()['esm2']
    (cache / 'esm2_t6_8M_UR50D.pt').touch()
    (cache / 'esm2_t6_8M_UR50D-contact-regression.pt').touch()
    assert strategy.structure_runtime_capabilities()['esm2']
    monkeypatch.setattr(strategy.importlib.util, 'find_spec', lambda name: None if name == 'esm' else object())
    assert not strategy.structure_runtime_capabilities()['esm2']


def test_report_distinguishes_unrequested_search_from_zero_hits():
    orch = AgentOrchestrator()
    report = orch._build_fallback_report('只检查上传 PDB 的质量', [{
        'tool_name': 'structure_search_foldseek', 'status': 'completed',
        'result': json.dumps({'status': 'completed', 'search_mode': 'input_only',
                              'search_executed': False, 'query_structure': {'total_atoms': 120, 'total_residues': 30, 'chain_count': 1}}),
    }])
    assert '未执行结构同源检索' in report
    assert '同源命中数' not in report


async def test_attachment_ai_summary_cannot_request_literature_search(planner):
    orch, _ = planner
    task = ('我要分析这个pdb\n[Attached files:\nname: 1TCA.pdb, '
            'object_name: uploads/user_999/sample.pdb, analysis: '
            '{"ai_summary":"查阅原始论文，核对论文结构验证指标。"}]')
    rows = await orch._plan_cb(task, '', [], analysis_depth='deep')
    names = {s.tool_name for s in rows}
    assert 'literature_live_search' not in names
    assert 'build_site_structure_function_features' in names
    # Explicit literature requests still retain their dedicated workflow.
    explicit = await orch._plan_cb(task.replace('我要分析这个pdb', '查找这个蛋白的最新论文'), '', [], analysis_depth='deep')
    assert 'literature_live_search' in {s.tool_name for s in explicit}


@pytest.mark.parametrize('restriction', ['不分析热稳定性', '不要分析催化功能', "do not analyze stability"])
def test_excluding_one_goal_does_not_disable_all_tools(restriction):
    assert not AgentOrchestrator._task_requests_no_tools('只检查结构质量，' + restriction)


@pytest.mark.parametrize('task', ['不分析', '不要分析。', '只抽取序列，不分析', 'do not analyze', '不要调用工具'])
def test_explicit_no_analysis_still_disables_tools(task):
    assert AgentOrchestrator._task_requests_no_tools(task)


async def test_revision_reuses_upload_and_excludes_negated_goal(planner, monkeypatch):
    orch, _ = planner

    async def research(*args, **kwargs):
        return ''

    monkeypatch.setattr(orch, '_research_pi', research)
    history = [{'role': 'user', 'content': message('仅本地分析热稳定性，不做突变设计')}]
    events = [json.loads(e) async for e in orch.stream_chat(
        '改成仅检查结构质量，不分析热稳定性，不设计突变，不要联网检索。',
        history, agent_control='revise_plan', analysis_depth='deep')]
    assert orch._snapshot.waiting_for == 'plan_confirmation'
    rows = orch._snapshot.raw_plan_payload
    assert rows and all(row['params'].get('pdb_object_name') == 'uploads/user_999/sample.pdb' for row in rows)
    assert not {'disulfide_saltbridge_scan', 'blast_search'} & {row['tool_name'] for row in rows}
    reply = ''.join(e.get('content', '') for e in events)
    assert '抽取结果' not in reply
    assert '**识别目标**：热稳定性' not in reply
    assert orch._snapshot.task_contract['primary_property'] is None


async def test_invalid_chain_error_survives_later_research(planner, monkeypatch):
    orch, _ = planner

    async def late_research(*args, **kwargs):
        await asyncio.sleep(0.01)
        return '未提供文件：这段研究摘要不能覆盖实际预检错误'

    monkeypatch.setattr(orch, '_research_pi', late_research)
    events = [json.loads(e) async for e in orch.stream_chat(
        message('仅本地检查 Z 链的结构质量，只能分析 Z 链'), [], analysis_depth='deep')]
    text = ''.join(e.get('content', '') for e in events)
    assert '结构中没有请求的链 Z' in text and '可用链：B' in text
    assert '未提供文件' not in text
    assert not any(e.get('waiting_for') == 'plan_confirmation' or e.get('next_action') == 'confirm_execute' for e in events)
    assert orch._snapshot.waiting_for == 'clarification'
    assert not orch._snapshot.strategy_signature
    assert not orch._snapshot.raw_plan_payload


async def test_stream_mutation_extension_waits_for_confirmation_with_bound_goal(planner, monkeypatch):
    from unittest.mock import AsyncMock
    from app.tools.registry import ToolRegistry
    orch, _ = planner
    monkeypatch.setattr(orch, '_research_pi', AsyncMock(return_value=''))
    executor = AsyncMock(side_effect=AssertionError('New substitutions need confirmation'))
    monkeypatch.setattr(ToolRegistry, 'execute', executor)
    history = [{'role': 'user', 'content': message('分析热稳定性，只分析 B 链，不要 BLAST')},
               {'role': 'assistant', 'content': '# 蛋白性质分析报告\n已有结构证据。'},
               {'role': 'user', 'content': '继续'},
               {'role': 'assistant', 'content': '热稳定性还需要实验。'}]
    events = [json.loads(e) async for e in orch.stream_chat(
        '在报告中增加哪些位点可突变成什么氨基酸', history, analysis_depth='deep')]
    assert orch._snapshot.waiting_for == 'plan_confirmation'
    rows = orch._snapshot.raw_plan_payload
    names = {r['tool_name'] for r in rows}
    assert {'enzyme_objective_module_plan', 'thermostability_candidate_workflow'} <= names
    assert 'blast_search' not in names
    score = next(r for r in rows if r['tool_name'] == 'thermostability_candidate_workflow')
    assert score['params']['chain_id'] == 'B'
    assert isinstance(score['params']['objective'], dict)
    assert orch._snapshot.task_contract['task_relation'] == 'TASK_EXTENSION'
    assert not any(e['type'] == 'tool_call' for e in events)
    assert orch._snapshot.strategy_signature
    executor.assert_not_called()


def test_multichain_summary_preserves_actual_atom_counts():
    from app.tools.structure_search_foldseek import _structure_summary
    from app.services.evidence_scope import partition_chain_results

    pdb = ('ATOM      1  CA  ALA A   1       0.000   0.000   0.000  1.00 10.00           C  \n'
           'ATOM      2  N   ALA A   1       1.000   0.000   0.000  1.00 10.00           N  \n'
           'ATOM      3  CA  ALA B   1       4.000   0.000   0.000  1.00 10.00           C  \n')
    summary = _structure_summary(pdb)
    groups, _, _ = partition_chain_results([{'tool_name': 'structure_search_foldseek',
        'status': 'completed', 'result': {'query_structure': summary}}])
    assert {chain: json.loads(rows[0]['result'])['query_structure']['total_atoms'] for chain, rows in groups.items()} == {'A': 2, 'B': 1}


def test_unknown_chain_atom_count_is_not_reported_as_zero():
    from app.services.evidence_scope import partition_chain_results

    groups, _, _ = partition_chain_results([{'tool_name': 'structure_search_foldseek',
        'status': 'completed', 'result': {'query_structure': {'chains': [
            {'chain_id': 'A', 'residue_count': 4}, {'chain_id': 'B', 'residue_count': 7}]}}}])
    assert all(json.loads(rows[0]['result'])['query_structure']['total_atoms'] == '未知' for rows in groups.values())


@pytest.mark.parametrize('goal', ['分别检查两个文件的结构质量，仅本地分析', '鉴别结构质量问题，仅本地分析', '区别说明结构质量，仅本地分析'])
async def test_positive_quality_words_containing_bie_are_not_negation(planner, goal):
    orch, _ = planner
    rows = await plan(orch, goal)
    assert {row.tool_name for row in rows} == {'structure_search_foldseek', 'residue_mapping_sifts', 'build_site_structure_function_features'}


async def test_bie_still_excludes_an_explicit_tool(planner):
    orch, _ = planner
    rows = await plan(orch, '分析结构质量，别运行 BLAST，仅本地分析')
    assert 'blast_search' not in {row.tool_name for row in rows}


async def test_mutation_extension_retains_goal_after_intermediate_followup(planner):
    orch, _ = planner
    history = [
        {'role': 'user', 'content': message('分析热稳定性，只分析 B 链，不要 BLAST')},
        {'role': 'user', 'content': '继续'},
    ]
    request = '在报告里增加哪些位点可以突变成什么氨基酸'
    context = orch._build_context_for_message(request, history)
    rows = await orch._plan_cb(request, '', history, context=context, analysis_depth='deep')
    names = {row.tool_name for row in rows}
    assert {'enzyme_objective_module_plan', 'thermostability_candidate_workflow'} <= names
    assert 'blast_search' not in names
    candidate = next(row for row in rows if row.tool_name == 'thermostability_candidate_workflow')
    assert isinstance(candidate.params['objective'], dict)
    assert candidate.params['chain_id'] == 'B'
