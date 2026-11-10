"""Incomplete experimental knowledge must permit an honest exploratory analysis."""
import hashlib

from app.core.agent_graph import AgentOrchestrator
from app.core.tool_outcome import normalize_tool_result
from app.services.thermostability_report import render_thermostability_report
from app.services.thermostability_workflow import build_screen
from app.tools.enzyme_objective_module_plan import enzyme_objective_module_plan

SEQ = 'ACDEFGHIKLMNPQRSTVWY' * 3


def test_unknown_assay_and_identity_produce_useful_exploration_without_claims():
    module = enzyme_objective_module_plan(objective='thermostability', analysis_mode='exploration')
    assert module['status'] == 'partial' and module['analysis_allowed']
    assert module['candidate_output_allowed'] is False
    result = build_screen(SEQ, objective_module_plan=module, analysis_mode='exploration')
    assert result['status'] == 'partial'
    assert result['analysis_mode'] == 'exploration' and result['analysis_directions']
    assert result['candidates'] == [] and result['experimental_plan'] == {}
    assert normalize_tool_result(result).status == 'completed'
    assert not normalize_tool_result(result).claim_eligible
    report = render_thermostability_report(result)
    assert '探索分析' in report and '未知' in report and '继续' in report
    assert '请补充' not in report and '流程已阻断' not in report


def test_exploration_report_has_stable_human_readable_target_summary():
    objective = {
        'endpoint': 'residual_activity', 'temperature_c': 95.0,
        'duration_min': 5.0, 'baseline_residual_activity_pct': 30.0,
        'target_residual_activity_pct': 60.0, 'target_comparator': '>=',
    }
    report = render_thermostability_report(
        build_screen(SEQ, objective=objective, analysis_mode='exploration')
    )
    assert '热处理条件：95℃，5 min；残余酶活：30% → 目标：≥60%。' in report
    assert '| 热处理温度（℃） | 95 |' in report
    assert '| 当前残余酶活（%） | 30 |' in report


def test_exploratory_substitutions_keep_known_protections_and_wt_checks():
    identity = {'query': {'sequence_sha256': hashlib.sha256(SEQ.encode()).hexdigest()},
                'identity_status': 'candidate', 'protected_positions': [2]}
    r = build_screen(SEQ, identity_profile=identity, mutations=['A1V', 'C2A', 'V1A'], analysis_mode='exploration')
    assert [x['mutation'] for x in r['preliminary_candidates']] == ['A1V']
    assert r['candidates'] == [] and r['experimental_plan'] == {}
    assert {x['mutation'] for x in r['rejected']} == {'C2A', 'V1A'}
    assert all(x['manual_review_required'] for x in r['preliminary_candidates'])


def test_exploration_never_uses_evidence_for_a_different_sequence():
    r = build_screen(SEQ, identity_profile={'query': {'sequence_sha256': 'wrong'}},
                     mutations=['A1V'], analysis_mode='exploration')
    assert r['status'] == 'blocked' and not r['candidates']


def test_chat_selects_exploration_and_identity_alternative_without_blast_dependency():
    from app.tools.registry import ToolRegistry
    ToolRegistry.discover()
    plan = AgentOrchestrator()._thermal_engineering_plan('提高热稳定性', SEQ, '', 'fast')
    names = [s.tool_name for s in plan]
    assert names.index('enzyme_sequence_identity') < names.index('enzyme_identity_profile')
    for name in ['enzyme_objective_module_plan', 'thermostability_candidate_workflow']:
        assert next(s for s in plan if s.tool_name == name).params['analysis_mode'] == 'exploration'


def test_supplementary_conditions_merge_and_corrections_replace_prior_values():
    from app.services.engineering_goal_semantics import thermal_objective
    history = [{'role': 'user', 'content': '提高热稳定性，95℃5分钟后残余酶活从30%提高到60%。\n序列：'+SEQ},
               {'role': 'user', 'content': '补充：测定pH：7；底物：淀粉；缓冲液：磷酸盐；辅因子：无；酶活测定方法：DNS；未加热酶活保留80%。'}]
    context = AgentOrchestrator._build_context_for_message('继续分析，pH改为6.5，其他条件不变', history)
    objective = thermal_objective('继续分析，pH改为6.5，其他条件不变\n'+context)
    assert objective['temperature_c'] == 95 and objective['target_residual_activity_pct'] == 60
    assert objective['ph'] == 6.5 and objective['cofactors'] == '无'
    assert objective['method'] == 'DNS' and objective['substrate'] == '淀粉'
    assert not objective.get('parsing_conflicts')


def test_exact_identity_reference_hydrates_profile_and_wrong_sequence_is_ignored():
    from app.core.agent_graph import PlanStep
    evidence = {'coordinate_system': {'status': 'verified'}, 'protein': {'uniprot_id': 'P00692'}}
    upstream = PlanStep(1, 'enzyme_sequence_identity', 'identity', {'sequence': SEQ})
    upstream.status = 'completed'
    upstream.result = {'uniprot_id': 'P00692', 'evidence_bundle': evidence}
    step = PlanStep(2, 'enzyme_identity_profile', 'profile', {'sequence': SEQ})
    AgentOrchestrator._hydrate_step_params(step, [upstream])
    assert step.params['evidence_bundle'] == evidence and step.params['uniprot_id'] == 'P00692'
    step = PlanStep(2, 'enzyme_identity_profile', 'profile', {'sequence': SEQ+'A'})
    AgentOrchestrator._hydrate_step_params(step, [upstream])
    assert not step.params.get('evidence_bundle')


def test_unknown_conditions_are_not_false_evidence_and_can_replace_old_values():
    from app.services.engineering_goal_semantics import merge_thermal_assay
    from app.services.thermostability_workflow import assay_gaps
    objective = merge_thermal_assay(['提高热稳定性，pH：7', 'pH：未知；辅因子不需要'])
    assert objective['ph'] is None and objective['cofactors'] == '无'
    assert 'ph' in assay_gaps(objective) and 'cofactors' not in assay_gaps(objective)
    assert 'method' in assay_gaps({'method': '未知'})


def test_added_assay_details_continue_uploaded_thermal_task_without_second_goal():
    from app.services.enzyme_workflow_runtime import evaluate_enzyme_workflow_runtime
    from app.services.engineering_goal_semantics import thermal_objective
    from app.services.property_workflow_governance import PropertyWorkflowRouter
    history = [{'role': 'user', 'content': '提高该酶热稳定性，实验条件未知。不要 BLAST。\n'
                '[Attached files:\nobject_name: uploads/user_1/pdb/input.pdb\n]'},
               {'role': 'assistant', 'content': '热稳定性探索分析'}]
    message = ('补充测定条件后继续热稳定性分析：95℃处理5分钟后残余酶活从30%提高到至少60%；'
               '测定pH：7；底物：淀粉；缓冲液：磷酸盐；辅因子：无；'
               '酶活测定方法：DNS；未加热酶活保留80%。先给策略，不执行。')
    contract = evaluate_enzyme_workflow_runtime(message, history)
    assert contract['intake_status'] == 'READY_FOR_ANALYSIS'
    assert contract['workflow_id'] == 'WF-STABILITY' and 'structure' in contract['known_inputs']
    assert 'blast_search' in contract['forbidden_tools']
    objective = thermal_objective(message)
    assert objective['baseline_residual_activity_pct'] == 30
    assert objective['target_residual_activity_pct'] == 60
    assert objective['min_activity_retention_pct'] == 80 and objective['method'] == 'DNS'
    both = PropertyWorkflowRouter.route(message + '同时提高比活力。')
    assert set(both['optimization_targets']) == {'stability', 'activity'}
    assert both['status'] == 'NEEDS_INPUT'


async def test_unknown_conditions_complete_confirmed_chat_with_local_analysis(monkeypatch):
    import json
    from app.tools.registry import ToolRegistry
    ToolRegistry.discover()
    agent = AgentOrchestrator()
    async def no_research(*args, **kwargs):
        return ''
    monkeypatch.setattr(agent, '_research_pi', no_research)
    monkeypatch.setattr(agent, '_get_experience_hints', no_research)
    monkeypatch.setattr(agent, '_cache_get', lambda _: None)
    monkeypatch.setattr(agent, '_cache_put', lambda *args: None)
    task = '提高热稳定性，所有实验条件未知；仅本地分析。\n序列：'+SEQ
    plan = await agent._plan_cb(task, '', [], analysis_depth='fast')
    raw = [{'id': s.id, 'tool_name': s.tool_name, 'description': s.description, 'params': s.params} for s in plan]
    events = [json.loads(e) async for e in agent.stream_chat(task, [], agent_control='execute_confirmed',
        confirmed_plan=raw, strategy_signature=agent._plan_signature(raw))]
    state = [e for e in events if e.get('type') == 'state'][-1]
    results = state['step_results']
    thermal = next(x for x in results if x['tool'] == 'thermostability_candidate_workflow')
    assert thermal['status'] == 'completed'
    assert not any(x['status'] == 'failed' for x in results)
    report = ''.join(e.get('content', '') for e in events if e.get('type') == 'text')
    assert '热稳定性探索分析' in report and '未知' in report
    assert '按门控阻止执行' not in report and '请补充' not in report
