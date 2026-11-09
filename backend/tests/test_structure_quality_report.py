"""Quality reports answer the selected question without relaxing evidence gates."""
import copy
import json

import pytest

from app.core.agent_graph import AgentOrchestrator
from app.services.structure_questions import question_answers

TASK = '仅本地检查结构质量，不要联网，不设计突变。\n[Attached files: name: sample.pdb, object_name: uploads/user_999/sample.pdb]'


def records(method='X-RAY DIFFRACTION', *, chain='A'):
    return [
        {'tool_name': 'structure_search_foldseek', 'status': 'completed', 'result': json.dumps({
            'status': 'completed', 'search_executed': False,
            'query_structure': {'method': method, 'resolution': 1.55, 'r_factor': 0.157,
                'total_residues': 46, 'total_atoms': 327, 'chain_count': 1,
                'chains': [{'chain_id': chain, 'residue_count': 46, 'atom_count': 327}],
                'seqres_by_chain': {chain: 46}, 'seqres_length': 46}})},
        {'tool_name': 'build_site_structure_function_features', 'status': 'completed', 'chain_id': chain,
         'result': json.dumps({'status': 'completed', 'chain_id': chain, 'feature_count': 46,
            'summary': {'feature_count': 46, 'ca_available_count': 46, 'backbone_torsion_status': 'computed'},
            'features': [{'position': 1, 'pdb_position': f'{chain}:1', 'has_ca': True,
                'risk_flags': ['missing_uniprot_mapping'], 'phi_deg': None, 'psi_deg': 147.66}]})},
    ]


def test_quality_objective_decomposition_does_not_expand_unrequested_topics():
    lines = '\n'.join(AgentOrchestrator._build_objective_decomposition_lines(TASK))
    assert '结构质量' in lines
    assert '家族注释' not in lines and '序列性质' not in lines
    assert '实验数据用于后续定量性质判断' not in lines


def test_quality_report_explains_metrics_and_scopes_advice():
    report = AgentOrchestrator()._build_fallback_report(TASK, records())
    assert '# 结构质量分析报告' in report
    assert '拟合' in report and '分辨率' in report and '1.55' in report
    assert 'R-free' in report and 'Ramachandran' in report and 'clashscore' in report
    assert '完整实验质量判断还需对应实验数据' not in report
    assert '比活力需同一底物' not in report and '热稳定性需测指定温度' not in report
    assert '催化位点距离(A)' not in report and 'missing_uniprot_mapping' not in report
    assert '湿实验验证 | 必需' not in report
    assert '结构质量合格' not in report


def test_quality_question_answer_is_more_than_a_tool_count():
    row = question_answers('检查结构质量', records())[0]
    assert row['status'] == 'partly_answered'
    assert '1.55' in row['answer'] and '0.157' in row['answer']
    assert '拟合' in row['answer'] and '46' in row['answer']
    assert 'Ramachandran' in row['boundary']
    assert set(row['evidence_ids']) == {'E1', 'E2'}


@pytest.mark.parametrize('method', ['THEORETICAL MODEL', 'SOLUTION NMR', 'ELECTRON MICROSCOPY', None])
def test_non_crystallographic_sources_do_not_inherit_xray_interpretation(method):
    row = question_answers('检查结构质量', records(method))[0]
    assert 'R-factor=0.157' not in row['answer']
    assert 'R-work' not in row['answer']
    if method == 'THEORETICAL MODEL':
        assert '预测' in row['answer'] and '置信' in row['boundary']
    elif method == 'SOLUTION NMR':
        assert '集合' in row['boundary']
    elif method == 'ELECTRON MICROSCOPY':
        assert '图' in row['boundary']
    else:
        assert '方法未提供' in row['answer']


@pytest.mark.parametrize('value', [-1, float('nan'), float('inf'), True])
def test_invalid_metrics_are_not_reported_as_measured_values(value):
    rows = records()
    payload = json.loads(rows[0]['result'])
    payload['query_structure'].update(resolution=value, r_factor=value)
    rows[0]['result'] = json.dumps(payload)
    row = question_answers('检查结构质量', rows)[0]
    assert '分辨率=' not in row['answer'] and 'R-factor=' not in row['answer']
    assert '缺失或无效' in row['boundary']


def test_unusable_payloads_never_supply_quality_metrics():
    rows = records()
    for row in rows:
        payload = json.loads(row['result']);payload['status'] = 'blocked';row['result'] = json.dumps(payload)
    answer = question_answers('检查结构质量', rows)[0]
    assert answer['status'] == 'unresolved' and not answer['evidence_ids']
    assert '1.55' not in answer['answer']


def test_quality_multichain_and_thermal_requests_keep_their_boundaries():
    rows = records()
    structure = json.loads(rows[0]['result'])
    structure['query_structure']['chains'].append({'chain_id': 'B', 'residue_count': 7, 'atom_count': 40})
    structure['query_structure'].update(chain_count=2, total_residues=53, total_atoms=367,
                                      seqres_by_chain={'A':46,'B':9}, seqres_length=55)
    rows[0]['result'] = json.dumps(structure)
    second = copy.deepcopy(rows[1]);second['chain_id'] = 'B'
    payload = json.loads(second['result']);payload.update(chain_id='B', feature_count=7, features=[{'pdb_position':'B:2'}])
    payload['summary'] = {'feature_count':7,'ca_available_count':6};second['result'] = json.dumps(payload)
    report = AgentOrchestrator()._build_fallback_report(TASK, rows + [second])
    assert '链 A' in report and '链 B' in report
    assert '链B SEQRES=9 aa、坐标=7 aa' in report
    assert 'CA 可用=6' in report and 'CA 可用=46' in report
    thermal = AgentOrchestrator()._build_fallback_report(TASK.replace('检查结构质量', '检查结构质量和热稳定性'), records())
    assert 'Tm' in thermal and '热稳定性' in thermal


@pytest.mark.parametrize('method', ['THEORETICAL MODEL', 'SOLUTION NMR', 'ELECTRON MICROSCOPY', None])
def test_full_report_does_not_reintroduce_uninterpretable_crystal_metrics(method):
    report = AgentOrchestrator()._build_fallback_report(TASK, records(method))
    assert 'R-factor=0.157' not in report and '分辨率=1.55' not in report


def test_quality_table_preserves_zero_and_does_not_mutate_tool_evidence():
    rows = records()
    payload = json.loads(rows[1]['result'])
    payload['features'][0].update(b_factor=0, rel_sasa=0, phi_deg=0, psi_deg=None, contact_count_ca_8a=0)
    rows[1]['result'] = json.dumps(payload)
    before = copy.deepcopy(rows)
    report = AgentOrchestrator()._build_fallback_report(TASK, rows)
    assert '| A:1 | NA | 0 | 0 | 0/NA | 0 |' in report
    assert rows == before


def test_r_free_is_interpreted_only_when_returned_and_not_estimated():
    rows = records()
    structure = json.loads(rows[0]['result'])
    structure['query_structure']['r_free'] = 0.194
    rows[0]['result'] = json.dumps(structure)
    row = question_answers('检查结构质量', rows)[0]
    assert 'R-free=0.194' in row['answer'] and '检验集' in row['answer']
    assert '未提供有效 R-free' not in row['boundary']


def test_quality_answer_does_not_call_file_wide_b_factor_a_chain_statistic():
    rows = records()
    structure = json.loads(rows[0]['result'])
    structure['query_structure']['b_factor_stats'] = {'mean':9.68}
    rows[0]['result'] = json.dumps(structure)
    row = question_answers('检查结构质量', rows)[0]
    assert '原文件蛋白原子' in row['answer'] and '不是独立的逐链统计' in row['answer']
