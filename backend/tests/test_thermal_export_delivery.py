"""Report artifacts must survive the actual chat transport and rendering path."""
import json
import re

import pytest

from app.core.agent_graph import AgentOrchestrator
from app.services import storage
from app.tools.registry import ToolRegistry


@pytest.mark.asyncio
async def test_owned_csv_downloads_survive_confirmed_chat_and_raw_receipt(monkeypatch, tmp_path):
    ToolRegistry.discover()
    agent = AgentOrchestrator()
    async def no_research(*args, **kwargs):
        return ''
    monkeypatch.setattr(agent, '_research_pi', no_research)
    monkeypatch.setattr(agent, '_get_experience_hints', no_research)
    monkeypatch.setattr(agent, '_cache_get', lambda _: None)
    monkeypatch.setattr(agent, '_cache_put', lambda *args: None)
    monkeypatch.setattr(storage, '_get_minio_client', lambda: None)
    monkeypatch.setattr(storage, '_local_root', tmp_path)
    task = '提高热稳定性，实验条件未知；仅本地分析。\n序列：' + 'ACDEFGHIKLMNPQRSTVWY' * 3
    plan = await agent._plan_cb(task, '', [], analysis_depth='fast')
    raw = [{'id': s.id, 'tool_name': s.tool_name, 'description': s.description, 'params': s.params} for s in plan]
    events = [json.loads(e) async for e in agent.stream_chat(task, [], agent_control='execute_confirmed',
        confirmed_plan=raw, strategy_signature=agent._plan_signature(raw), current_user={'id': 7})]
    state = [e for e in events if e.get('type') == 'state'][-1]
    thermal = next(r for r in state['step_results'] if r['tool'] == 'thermostability_candidate_workflow')
    assert thermal['status'] == 'completed'
    payload = json.loads(thermal['raw_result'])
    report = ''.join(e.get('content', '') for e in events if e.get('type') == 'text')
    links = re.findall(r'\]\((/api/files/uploads/user_7/reports/[a-f0-9]{32}\.csv/download)\)', report)
    assert len(links) == 3, 'Stored CSVs must remain downloadable in the final chat report'
    assert {item['download_url'] for item in payload['review_exports'].values()} == set(links)
    for item in payload['review_exports'].values():
        name = item['download_url'].removeprefix('/api/files/').removesuffix('/download')
        assert (tmp_path / name).read_bytes() == item['content'].encode('utf-8-sig')


@pytest.mark.parametrize('url,user', [
    ('/api/files/uploads/user_8/reports/' + 'a' * 32 + '.csv/download', {'id': 7}),
    ('https://example.com/api/files/uploads/user_7/reports/' + 'a' * 32 + '.csv/download', {'id': 7}),
    ('/api/files/uploads/user_7/private.pdb/download', {'id': 7}),
    ('/api/files/uploads/user_7/reports/../' + 'a' * 32 + '.csv/download', {'id': 7}),
    ('/api/files/uploads/user_7/reports/' + 'a' * 32 + '.csv/download?token=secret', {'id': 7}),
    ('/api/files/uploads/user_7/reports/' + 'a' * 32 + '.csv/download', None),
])
def test_input_or_untrusted_download_paths_remain_redacted(url, user):
    result = {'pdb_object_name': 'uploads/user_7/private.pdb', 'review_exports': {
        'strategy_status': {'download_status': 'ready', 'download_url': url}}}
    serialized = AgentOrchestrator._thermal_result_for_display(result, user)
    payload = json.loads(serialized)
    assert payload['review_exports']['strategy_status']['download_url'] != url
    assert 'private.pdb' not in serialized
