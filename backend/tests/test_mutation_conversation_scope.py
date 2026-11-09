"""Distinguish reading existing substitutions from authorizing new computation."""
import pytest
import json
from unittest.mock import AsyncMock

from app.core.agent_graph import AgentOrchestrator
from app.services.enzyme_workflow_runtime import evaluate_enzyme_workflow_runtime


HISTORY = [{'role': 'user', 'content': (
    '分析热稳定性，只分析 B 链，不要 BLAST。\n'
    '[Attached files: name: sample.pdb, object_name: uploads/user_9/sample.pdb]'
)}]


@pytest.mark.parametrize('message', [
    '在报告里增加哪些位点可以突变成什么氨基酸',
    '继续为这个结构计算新的突变候选',
])
def test_new_substitutions_extend_task_with_existing_input_and_constraints(message):
    result = evaluate_enzyme_workflow_runtime(message, HISTORY)
    assert result['task_relation'] == 'TASK_EXTENSION'
    assert result['intake_status'] == 'READY_FOR_ANALYSIS'
    assert result['primary_property'] == 'stability'
    assert result['chain_ids'] == ['B']
    assert 'blast_search' in result['forbidden_tools']
    context = AgentOrchestrator._build_context_for_message(message, HISTORY)
    assert 'uploads/user_9/sample.pdb' in context
    assert '热稳定性' in context
    assert not AgentOrchestrator._is_same_problem_synthesis_followup(message, context)


@pytest.mark.parametrize('message', [
    '解释报告里已有的 G42P，为什么选择脯氨酸？',
    '不要重新计算，只把已有突变建议整理成表格',
])
def test_candidate_explanation_is_non_execution(message):
    result = evaluate_enzyme_workflow_runtime(message, HISTORY)
    assert result['intent'] == 'NON_EXECUTION'
    assert result['route_reason'] == 'existing_candidate_review'


def test_request_to_list_existing_site_substitutions_reuses_report_without_extension():
    history = HISTORY + [{'role': 'assistant', 'content': (
        '## 突变位点探索清单（不可直接排单）\n'
        '| 位点 | 推荐突变 |\n|---|---|\n| A:53 | G52A, G52S |'
    )}]
    result = evaluate_enzyme_workflow_runtime('在报告中增加哪些位点可突变成什么氨基酸', history)
    assert result['intent'] == 'NON_EXECUTION'
    assert result['route_reason'] == 'existing_candidate_review'


def test_request_for_new_substitutions_runs_increment_when_report_has_no_candidate_rows():
    history = HISTORY + [{'role': 'assistant', 'content': (
        '## 突变位点探索清单（未放行）\n本轮没有生成位点候选。'
    )}]
    result = evaluate_enzyme_workflow_runtime('哪些位点可突变成什么氨基酸', history)
    assert result['task_relation'] == 'TASK_EXTENSION'
    assert result['route_reason'] == 'mutation_candidate_request'


def test_asking_for_substitutions_without_goal_requests_goal():
    result = evaluate_enzyme_workflow_runtime('哪些位点可以突变成什么氨基酸？', [
        {'role': 'user', 'content': '检查结构质量，已上传 sample.pdb'},
    ])
    assert result['intake_status'] == 'WAITING_FOR_USER_INPUT'
    assert 'optimization_target' in result['input_gaps']
    assert result['primary_property'] is None


def test_new_upload_does_not_inherit_prior_engineering_goal_or_chain():
    result = evaluate_enzyme_workflow_runtime(
        '新任务，给这个结构设计突变\n[Attached files: name: other.pdb, '
        'object_name: uploads/user_9/other.pdb]', HISTORY,
    )
    assert result['intent'] == 'NEW_TASK'
    assert result['intake_status'] == 'WAITING_FOR_USER_INPUT'
    assert result['primary_property'] is None
    assert result['chain_ids'] == []
    assert result['forbidden_tools'] == []


def test_subsequent_extension_stays_with_latest_structure_not_older_goal():
    history = HISTORY + [{'role': 'user', 'content': (
        '新任务，检查结构质量\n[Attached files: name: other.pdb, '
        'object_name: uploads/user_9/other.pdb]'
    )}]
    result = evaluate_enzyme_workflow_runtime('给这个结构设计突变', history)
    assert result['primary_property'] is None
    assert result['intake_status'] == 'WAITING_FOR_USER_INPUT'
    assert result['chain_ids'] == []
    assert result['forbidden_tools'] == []


def test_explaining_recommended_mutations_does_not_request_new_candidates():
    result = evaluate_enzyme_workflow_runtime('你推荐的突变为什么可靠？', HISTORY)
    assert result['intent'] == 'NON_EXECUTION'


def test_mixed_explanation_and_new_generation_is_not_captured_by_old_review_route():
    message = '解释已有突变的依据，再设计新的突变候选'
    context = AgentOrchestrator._build_context_for_message(message, HISTORY)
    assert not AgentOrchestrator._is_p0_followup_review(message, context, HISTORY)


def test_saved_extension_task_retains_goal_after_intermediate_continue():
    from app.api.chat import _checkpoint_task_text
    text = _checkpoint_task_text('在报告中增加哪些位点可突变成什么氨基酸',
                                 HISTORY + [{'role': 'user', 'content': '继续'}])
    summary = AgentOrchestrator._display_task_summary(text)
    assert '热稳定性' in summary
    assert 'blast_search' in summary
    assert '链 B' in summary
    assert not summary.startswith('继续')


def test_saved_extension_does_not_carry_goal_into_new_upload():
    from app.api.chat import _checkpoint_task_text
    text = _checkpoint_task_text('新任务，设计突变\n[Attached files: name: other.pdb, '
                                 'object_name: uploads/user_9/other.pdb]', HISTORY)
    assert '热稳定性' not in text
    assert 'sample.pdb' not in text


def test_extension_keeps_assay_conditions_with_the_active_objective():
    from app.api.chat import _checkpoint_task_text
    history = [{'role': 'user', 'content': '分析热稳定性，WT Tm=52 C，pH=7.0，不要BLAST。\n'
                '[Attached files: name: sample.pdb, object_name: uploads/user_9/sample.pdb]'},
               {'role': 'user', 'content': '继续'}]
    text = _checkpoint_task_text('增加新的突变候选', history)
    assert 'Tm=52 C' in text
    assert 'pH=7.0' in text


def test_existing_candidate_fallback_quotes_table_without_starting_work():
    history = HISTORY + [{'role': 'assistant', 'content': (
        '# 酶蛋白工程分析报告\n\n## 突变位点探索清单（不可直接排单）\n\n'
        '| 原氨基酸 | 替换氨基酸 |\n|---|---|\n| G42 | P |\n\n'
        '## 下一步\n补实验。'
    )}]
    reply = AgentOrchestrator._history_report_reply(history, '解释已有突变建议')
    assert '| G42 | P |' in reply
    assert '不可直接排单' in reply
    assert '没有运行新工具' in reply


async def test_stream_candidate_review_does_not_plan_or_execute_when_model_unavailable(monkeypatch):
    from app.core import agent_graph
    from app.tools.registry import ToolRegistry
    orch = AgentOrchestrator()
    planner = AsyncMock(side_effect=AssertionError('A review cannot plan'))
    executor = AsyncMock(side_effect=AssertionError('A review cannot run tools'))
    monkeypatch.setattr(orch, '_plan_cb', planner)
    monkeypatch.setattr(ToolRegistry, 'execute', executor)
    monkeypatch.setattr(orch, '_chat_reply', AsyncMock(return_value=agent_graph._LLM_UNAVAILABLE_REPLY))
    history = HISTORY + [{'role': 'assistant', 'content': (
        '# 酶蛋白工程分析报告\n\n## 突变位点探索清单（不可直接排单）\n'
        '| 原氨基酸 | 替换氨基酸 |\n|---|---|\n| G42 | P |\n\n## 下一步\n补实验。'
    )}]
    events = [json.loads(e) async for e in orch.stream_chat('你推荐的突变为什么可靠？', history)]
    reply = ''.join(e.get('content', '') for e in events)
    assert '| G42 | P |' in reply
    assert '不可直接排单' in reply
    assert not any(e['type'] == 'tool_call' or e.get('waiting_for') == 'plan_confirmation' for e in events)
    planner.assert_not_called()
    executor.assert_not_called()


@pytest.mark.parametrize('code', ['A42P', 'G42G', 'G42X', 'G43P'])
def test_malformed_substitutions_do_not_appear_in_recommendation_sections(code):
    report = AgentOrchestrator()._build_fallback_report('设计突变', [{
        'tool_name': 'mutation_priority_score', 'status': 'completed', 'result': {
            'candidate_table_status': 'ready', 'experiment_design_table': [{
                'position': 42, 'wild_type': 'G', 'recommended_mutations': [code],
            }],
        },
    }])
    assert code not in report.split('附录')[0]
    assert '暂无可排单候选' in report


def test_report_separates_wild_type_and_substitution_with_author_numbering():
    report = AgentOrchestrator()._build_fallback_report('为热稳定性设计突变', [{
        'tool_name': 'mutation_priority_score', 'status': 'completed', 'result': {
            'candidate_table_status': 'ready',
            'identity_gate': {'status': 'passed'},
            'objective_gate': {'status': 'ready', 'candidate_output_allowed': True},
            'experiment_design_table': [{
                'position': 42, 'wild_type': 'G', 'pdb_position': 'B:105A',
                'recommended_mutations': ['G42P', 'G42A'],
                'mutation_logic': '局部刚性假设', 'experiment_priority': 'P2-探索',
            }],
        },
    }])
    assert '| 原氨基酸 | 替换氨基酸 |' in report
    assert '| B:105A | G (Gly) | P (Pro)、A (Ala) | G42P, G42A |' in report
    assert '序列位置' in report and '作者编号' in report
    assert '作者编号' in report


def test_report_hides_site_substitutions_when_identity_and_assay_gates_are_blocked():
    report = AgentOrchestrator()._build_fallback_report('提升比活力，哪些位点可突变成什么氨基酸', [
        {'tool_name': 'structure_search_foldseek', 'status': 'completed', 'result': json.dumps({
            'status': 'completed', 'query_structure': {'chain_count': 1, 'total_residues': 194},
        })},
        {'tool_name': 'mutation_priority_score', 'status': 'completed', 'result': json.dumps({
            'status': 'blocked',
            'candidate_table_status': 'blocked_by_identity_gate',
            'identity_gate': {'status': 'exploratory', 'identity_status': 'unresolved'},
            'candidate_decision': {'candidate_output_allowed': False},
            'objective_gate': {'status': 'blocked', 'missing_evidence': ['底物与测定条件']},
            'experiment_design_table': [],
            'tier_2_candidates': [{
                'experiment_priority': 'P2-探索', 'position': 52, 'user_position': 52,
                'pdb_position': 'A:53', 'wild_type': 'G',
                'recommended_mutations': [{'mutation': 'G52A'}, {'mutation': 'G52S'}],
                'candidate_status': 'exploratory',
                'candidate_evidence_status': 'computational_hypothesis',
                'mutation_logic': '表面暴露位点的局部性质假设',
                'risk_flags': ['酶身份未确认', '活性收益未知'],
            }],
        })},
    ])

    assert '探索性候选=0' in report
    assert '问题回答状态**：候选门控未通过' in report
    assert 'G52A' not in report and 'G52S' not in report
    assert '本轮不输出具体突变候选表' in report
    assert '正式候选=0' in report


def test_blocked_identity_does_not_promote_heuristic_sites_to_confirmed_protection():
    report = AgentOrchestrator()._build_fallback_report('分析热稳定性并设计突变', [{
        'tool_name': 'mutation_priority_score', 'status': 'completed', 'result': {
            'candidate_table_status': 'blocked_by_identity_gate',
            'identity_gate': {'status': 'blocked', 'reason': 'identity unresolved'},
            'summary': {'never_mutate_positions': [6, 17, 224]},
        },
    }])
    assert '禁止突变位点**：[6, 17, 224]' not in report
    assert '启发式' in report and '未确认' in report
