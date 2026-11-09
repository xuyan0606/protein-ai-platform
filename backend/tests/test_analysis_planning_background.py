"""Input-bound analysis plans must not wait for unrelated model prose."""
import json
import pytest
from app.core.agent_graph import AgentOrchestrator
from app.tools.registry import ToolRegistry


@pytest.mark.asyncio
async def test_structure_analysis_does_not_call_unconsumed_research_model(monkeypatch):
    ToolRegistry.discover()
    agent = AgentOrchestrator()
    calls = []

    async def research(*args, **kwargs):
        calls.append('research')
        return '无法继续研究；本对话永久受限。'

    async def empty(*args, **kwargs):
        return ''

    async def download(name):
        names = ['ALA', 'CYS', 'ASP', 'GLU', 'PHE', 'GLY', 'HIS', 'ILE', 'LYS', 'LEU',
                 'MET', 'ASN', 'PRO', 'GLN', 'ARG', 'SER', 'THR', 'VAL', 'TRP', 'TYR']
        return (''.join(f'ATOM  {i:5d}  CA  {aa} A{i:4d}    {i*3.:8.3f}{0.:8.3f}{0.:8.3f}  1.00 20.00           C\n'
                        for i, aa in enumerate(names, 1)) + 'END\n').encode()

    monkeypatch.setattr('app.services.storage.download_file', download)
    monkeypatch.setattr(agent, '_research_pi', research)
    monkeypatch.setattr(agent, '_get_experience_hints', empty)
    message = '提高这个蛋白热稳定性，给10个探索候选；条件未知；不要BLAST。\n[Attached files: object_name: uploads/user_3/source.pdb]'
    events = [json.loads(e) async for e in agent.stream_chat(message, [], agent_control='plan_only')]
    assert calls == [], 'Deterministic planning does not use research output; do not invoke that model'
    state = [e for e in events if e.get('type') == 'state'][-1]
    assert state['waiting_for'] == 'plan_confirmation'
    assert state['plan'] and state['strategy_signature']
    assert not state['step_results'] and not state['research_notes']
    reply = ''.join(e.get('content', '') for e in events if e.get('type') == 'text')
    assert '永久受限' not in reply and '初步背景' not in reply
