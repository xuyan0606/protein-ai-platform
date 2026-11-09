"""Thermal contract reaches chat and exports without claims of measured success."""
import copy
import json
from unittest.mock import AsyncMock

import pytest

from app.core.agent_graph import AgentOrchestrator, PlanStep
from app.services.report_generator import ReportGenerator
from app.services.thermostability_report import render_thermostability_report


HASH = 'a' * 64


def payload(status='ready_for_review'):
    return {'schema_version': 'thermostability_candidates_v1', 'status': status,
            'sequence_sha256': HASH, 'coordinate_system': 'input_sequence_1based',
            'branches': {'ddgun': {'status': 'completed'},
                         'esm': {'status': 'blocked', 'blocked_reason': 'model_unavailable'},
                         'colabfold': {'status': 'not_requested'}},
            'candidates': [{'mutation': 'A1V', 'position': 1, 'full_length_position': 101,
                            'structure_position': {'chain_id': 'B', 'residue_number': 27, 'insertion_code': 'A'},
                            'sources': [{'kind': 'explicit', 'reference': 'user'}],
                            'risks': ['ligand_contact'], 'missing_evidence': ['experimental_activity'],
                            'scores': {'ddgun': {'ddg': -1.5, 'unit': 'kcal/mol',
                                                'direction': 'positive=increased unfolding stability',
                                                'method': 'DDGun_sequence', 'algorithm_commit': 'abc'},
                                       'esm_preference': None}}],
            'experimental_plan': {'controls': ['WT'], 'single_mutants': ['A1V'],
                                  'replicates': 'predefine', 'selection_policy': 'review',
                                  'combination_design': 'after_single_mutant_feedback'}}


def record(data):
    return {'tool_name': 'thermostability_candidate_workflow', 'status': 'completed',
            'input_id': 'pdb:0', 'chain_id': 'B', 'result': json.dumps(data)}


def test_renderer_keeps_candidates_provenance_risks_scores_and_wt_separate():
    report = render_thermostability_report(payload())
    for text in ['thermostability_candidates_v1', HASH, 'A1V', 'B:27A', 'ligand_contact',
                 'experimental_activity', 'WT', 'DDGun_sequence', 'kcal/mol', '-1.5',
                 'positive=increased unfolding stability', 'ESM', '未计算', 'model_unavailable',
                 'not_requested', '不得相加', '尚未经实验验证']:
        assert text in report
    assert '总分' not in report


@pytest.mark.parametrize('status', ['needs_input', 'blocked', 'no_candidates'])
def test_input_or_gate_block_never_promotes_stale_candidate_rows(status):
    data = payload(status)
    data['required_inputs'] = ['endpoint', 'min_activity_retention_pct']
    data['blockers'] = ['identity_sequence_mismatch']
    report = render_thermostability_report(data)
    assert 'required_inputs' in report and 'min_activity_retention_pct' in report
    assert 'identity_sequence_mismatch' in report
    assert '| A1V |' not in report
    assert '尚未形成可执行的实验候选集合' in report
    assert '已完成推荐' not in report


def test_partial_branch_failure_keeps_existing_hypotheses_and_explicit_limits():
    report = render_thermostability_report(payload('partial'))
    assert '| A1V |' in report
    assert '部分分支不可用' in report
    assert 'model_unavailable' in report


def test_chat_fallback_uses_schema_candidates_instead_of_legacy_tier_keys():
    report = AgentOrchestrator()._build_fallback_report('分析热稳定性', [record(payload())])
    assert HASH in report and '| A1V |' in report and 'B:27A' in report
    assert 'WT' in report and 'thermostability_candidates_v1' in report


@pytest.mark.asyncio
async def test_chat_synthesis_keeps_needs_input_payload_without_calling_llm(monkeypatch):
    orch = AgentOrchestrator()
    monkeypatch.setattr(orch, '_call_llm', AsyncMock(side_effect=AssertionError('Deterministic contract required')))
    data = payload('needs_input')
    data['required_inputs'] = ['endpoint', 'buffer']
    report = await orch._synthesize_sc('分析热稳定性', [record(data)], '', [])
    assert 'required_inputs' in report and 'buffer' in report
    assert '| A1V |' not in report


@pytest.mark.parametrize('final_report', ['模型返回的简短报告', '# 酶蛋白工程分析报告\n\n## 任务理解\n\n阶段报告'])
def test_export_adds_full_thermal_payload_to_generic_or_structured_report(final_report, monkeypatch):
    monkeypatch.setattr(ReportGenerator, '_platform_manifest_markdown', staticmethod(lambda: ''))
    result = ReportGenerator().generate_conversation_report(
        project_name='test', conversation_title='thermal', user_message='分析热稳定性',
        research_notes='', plan=[], tool_results=[record(payload())], final_report=final_report)
    assert HASH in result and '| A1V |' in result and 'WT' in result
    assert 'report_status: "NEEDS_REVIEW"' in result


def test_export_does_not_duplicate_deterministic_renderer(monkeypatch):
    monkeypatch.setattr(ReportGenerator, '_platform_manifest_markdown', staticmethod(lambda: ''))
    data = record(payload())
    final = AgentOrchestrator()._build_fallback_report('分析热稳定性', [data])
    result = ReportGenerator().generate_conversation_report(
        project_name='test', conversation_title='thermal', user_message='分析热稳定性',
        research_notes='', plan=[], tool_results=[data], final_report=final)
    assert result.count('## 热稳定性候选流程') == 1


def test_execution_policy_disables_composite_branches_without_mutating_input():
    params = {'run_ddgun': True, 'run_esm': True, 'run_colabfold': True, 'run_coevolution': True,
              'execution_policy': {'forbidden_tools': ['ddgun_predict']}}
    target = PlanStep(1, 'thermostability_candidate_workflow', '', params=copy.deepcopy(params))
    AgentOrchestrator._apply_thermostability_execution_policy(target, {'forbidden_tools': ['esm2_predict']})
    assert target.params['run_ddgun'] is False and target.params['run_esm'] is False
    assert target.params['run_colabfold'] is True
    assert target.params['forbidden_tools'] == ['ddgun_predict', 'esm2_predict']
    assert params['run_ddgun'] is True
    AgentOrchestrator._apply_thermostability_execution_policy(target, {'offline': True})
    assert target.params['offline'] is True
    assert all(target.params[key] is False for key in ['run_ddgun', 'run_esm', 'run_colabfold', 'run_coevolution'])
