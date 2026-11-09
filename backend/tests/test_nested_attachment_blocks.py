"""Real browser metadata cannot become user instructions or recurse across inputs."""
import json
import pytest
from app.core.agent_graph import AgentOrchestrator


def task():
    analysis = json.dumps({'chains': [{'sequence': 'ACDEFGHIKLMNPQRSTVWY', 'residue_range': [1, 20]}],
                           'summary': 'literal ] and [ with escaped quote " inside JSON; literature keyword is metadata'})
    return ('分别检查两个文件结构质量，仅本地分析。\n[Attached files:\n'
            'name: first.pdb, object_name: uploads/user_1/first.pdb, analysis: '+analysis+'\n'
            'name: second.pdb, object_name: uploads/user_1/second.pdb, analysis: '+analysis+']')


def test_nested_attachment_json_is_removed_as_one_block():
    assert AgentOrchestrator._strip_attachment_metadata(task()).strip() == '分别检查两个文件结构质量，仅本地分析。'


def test_user_revision_after_nested_block_is_preserved():
    value = AgentOrchestrator._strip_attachment_metadata(task()+'\n[用户修改策略要求]\n只分析热稳定性')
    assert value.strip() == '分别检查两个文件结构质量，仅本地分析。\n\n[用户修改策略要求]\n只分析热稳定性'


def test_report_with_nested_metadata_does_not_recurse_or_cross_bind():
    rows = []
    for index, count in enumerate((20, 30)):
        rows.append({'tool_name': 'structure_search_foldseek', 'status': 'completed',
                     'pdb_object_name': f'uploads/user_1/{"first" if index == 0 else "second"}.pdb',
                     'input_id': f'pdb:{index}', 'result': json.dumps({'status': 'completed',
                         'search_executed': False, 'backend': 'input_parser',
                         'query_structure': {'chain_count': 1, 'total_residues': count, 'total_atoms': count*4}})})
    report = AgentOrchestrator()._build_fallback_report(task(), rows)
    assert report.count('## 结构 1:') == report.count('## 结构 2:') == 1
    first, second = report.split('## 结构 2:')
    assert '残基数=20' in first and '残基数=30' not in first
    assert '残基数=30' in second and '残基数=20' not in second
    assert 'literature keyword' not in report


async def test_browser_metadata_keeps_multifile_quality_plan_bound(monkeypatch):
    orch = AgentOrchestrator()
    async def preflight(text):
        name = orch._extract_attached_object_name(text)
        seq = 'ACDEFGHIKLMNPQRSTVWY' if name.endswith('/first.pdb') else 'M'*30
        return {'status': 'readable', 'chains': [{'chain_id': 'A', 'sequence': seq,
                'residue_count': len(seq)}], 'coordinate_sequence': seq,
                'chain_count': 1, 'total_residues': len(seq)}
    async def empty(*args, **kwargs):
        return ''
    async def route(*args, **kwargs):
        return 'analyze'
    monkeypatch.setattr(orch, '_build_pdb_preflight_summary', preflight)
    monkeypatch.setattr(orch, '_get_experience_hints', empty)
    monkeypatch.setattr(orch, '_research_pi', empty)
    monkeypatch.setattr(orch, '_route_intent', route)
    events = [json.loads(e) async for e in orch.stream_chat(task(), [], agent_control='plan_only')]
    assert events[-1]['type'] == 'done'
    rows = orch._snapshot.raw_plan_payload
    assert len(rows) == 6
    assert {r['tool_name'] for r in rows} == {'structure_search_foldseek', 'residue_mapping_sifts', 'build_site_structure_function_features'}
    maps = {r['params']['pdb_object_name']: r['params']['input_sequence'] for r in rows if r['tool_name'] == 'residue_mapping_sifts'}
    assert maps == {'uploads/user_1/first.pdb': 'ACDEFGHIKLMNPQRSTVWY', 'uploads/user_1/second.pdb': 'M'*30}
