"""User notices describe evidence gaps and asynchronous state without raw JSON."""
from app.core.agent_graph import AgentOrchestrator, ChatSnapshot


def test_identity_gate_notice_names_missing_evidence_without_json_dump():
    agent = AgentOrchestrator()
    agent._snapshot = ChatSnapshot(stage='execute')
    result = {'status':'blocked','objective':'thermostability',
        'foundation_gate': {'status':'blocked','missing':[
            'identity_status must be identified.', 'guardrail.status must be ready.',
            'protected catalytic/key positions are not available.']},
        'missing_evidence':['identity_status must be identified.', 'guardrail.status must be ready.',
            'protected catalytic/key positions are not available.']}
    agent._record_execution_outcome('enzyme_objective_module_plan', 'blocked', str(result), result)
    text = agent._format_execution_notices(agent._snapshot.task_contract)
    assert '酶身份尚未确认' in text
    assert '催化' in text and '保护位点' in text
    assert 'foundation_gate' not in text and '{' not in text
    assert not agent._snapshot.task_contract.get('fallback_trace')


def test_background_notice_points_to_live_card_instead_of_naked_api_url():
    agent = AgentOrchestrator()
    agent._snapshot = ChatSnapshot(stage='execute')
    result = {'task_id':'job-1','status':'submitted','status_url':'/api/tools/tasks/job-1'}
    agent._record_execution_outcome('blast_search','submitted',result=result)
    text = agent._format_execution_notices(agent._snapshot.task_contract)
    assert '任务卡片' in text and '提交时' in text
    assert '/api/tools/tasks/' not in text
    assert '无同源命中' in text
